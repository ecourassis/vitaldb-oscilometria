"""Pipeline reprodutível VitalDB -> Parquet/Star Schema -> DuckDB."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
CASES_URL = "https://api.vitaldb.net/cases"
TRACKS_URL = "https://api.vitaldb.net/trks"
SELECTED_CASES = [547, 567, 2738, 2769, 4191, 4480, 4974, 5502]
PAIR_TOLERANCE_SECONDS = 30.0
COMPRESSION = "zstd"

TRACK_MAP = {
    "Solar8000/NIBP_SBP": "nibp_sbp_mmhg",
    "Solar8000/NIBP_MBP": "nibp_mbp_mmhg",
    "Solar8000/NIBP_DBP": "nibp_dbp_mmhg",
    "Solar8000/ART_SBP": "art_sbp_mmhg",
    "Solar8000/ART_MBP": "art_mbp_mmhg",
    "Solar8000/ART_DBP": "art_dbp_mmhg",
    "Solar8000/HR": "heart_rate_bpm",
}

FACT_SCHEMA = pa.schema([
    pa.field("measurement_id", pa.string(), nullable=False),
    pa.field("patient_key", pa.string(), nullable=False),
    pa.field("case_key", pa.string(), nullable=False),
    pa.field("time_key", pa.int64(), nullable=False),
    pa.field("label_key", pa.string(), nullable=False),
    pa.field("nibp_sbp_mmhg", pa.float32()),
    pa.field("nibp_mbp_mmhg", pa.float32(), nullable=False),
    pa.field("nibp_dbp_mmhg", pa.float32()),
    pa.field("art_sbp_mmhg", pa.float32()),
    pa.field("art_mbp_mmhg", pa.float32(), nullable=False),
    pa.field("art_dbp_mmhg", pa.float32()),
    pa.field("heart_rate_bpm", pa.float32()),
    pa.field("pair_delta_seconds", pa.float32(), nullable=False),
    pa.field("error_sbp_mmhg", pa.float32()),
    pa.field("error_mbp_mmhg", pa.float32(), nullable=False),
    pa.field("error_dbp_mmhg", pa.float32()),
])

PATIENT_SCHEMA = pa.schema([
    pa.field("patient_key", pa.string(), nullable=False),
    pa.field("subject_id", pa.string(), nullable=False),
    pa.field("sex", pa.string()),
    pa.field("age_years", pa.float32()),
    pa.field("height_cm", pa.float32()),
    pa.field("weight_kg", pa.float32()),
    pa.field("bmi_kg_m2", pa.float32()),
])

CASE_SCHEMA = pa.schema([
    pa.field("case_key", pa.string(), nullable=False),
    pa.field("case_id", pa.string(), nullable=False),
    pa.field("department", pa.string()),
    pa.field("operation_type", pa.string()),
    pa.field("approach", pa.string()),
    pa.field("position", pa.string()),
    pa.field("anesthesia_type", pa.string()),
    pa.field("asa_class", pa.string()),
    pa.field("emergency_operation", pa.bool_()),
])

TIME_SCHEMA = pa.schema([
    pa.field("time_key", pa.int64(), nullable=False),
    pa.field("time_seconds", pa.float64(), nullable=False),
    pa.field("time_minutes", pa.float32(), nullable=False),
    pa.field("intraoperative_phase", pa.string(), nullable=False),
])

LABEL_SCHEMA = pa.schema([
    pa.field("label_key", pa.string(), nullable=False),
    pa.field("art_hypotension", pa.bool_(), nullable=False),
    pa.field("nibp_hypotension", pa.bool_(), nullable=False),
    pa.field("agreement_class", pa.string(), nullable=False),
])


def download(url: str, path: Path) -> Path:
    """Baixa via HTTPS somente se o arquivo ainda não existir."""
    if path.exists() and path.stat().st_size > 0:
        return path
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def read_numeric_track(tid: str, output_name: str) -> pd.DataFrame:
    """Lê uma trilha numérica preservando seus timestamps irregulares."""
    # requests já descomprime a resposta HTTP quando necessário; salvamos CSV legível.
    path = download(f"https://api.vitaldb.net/{tid}", RAW / f"track_{tid}.csv")
    frame = pd.read_csv(path)
    if frame.shape[1] < 2:
        raise ValueError(f"Trilha {tid} não contém duas colunas")
    frame = frame.iloc[:, :2].copy()
    frame.columns = ["time_seconds", output_name]
    frame["time_seconds"] = pd.to_numeric(frame["time_seconds"], errors="coerce")
    frame[output_name] = pd.to_numeric(frame[output_name], errors="coerce")
    return frame.dropna(subset=["time_seconds", output_name]).sort_values("time_seconds")


def nearest_join(
    left: pd.DataFrame, right: pd.DataFrame, tolerance: float, value_name: str
) -> pd.DataFrame:
    right_time = f"{value_name}_time_seconds"
    right = right.rename(columns={"time_seconds": right_time})
    return pd.merge_asof(
        left.sort_values("time_seconds"), right.sort_values(right_time),
        left_on="time_seconds", right_on=right_time,
        direction="nearest", tolerance=tolerance,
    )


def plausible(frame: pd.DataFrame) -> pd.DataFrame:
    limits = {
        "nibp_sbp_mmhg": (40, 260), "nibp_mbp_mmhg": (25, 200),
        "nibp_dbp_mmhg": (20, 160), "art_sbp_mmhg": (40, 260),
        "art_mbp_mmhg": (25, 200), "art_dbp_mmhg": (20, 160),
        "heart_rate_bpm": (20, 220),
    }
    for col, (low, high) in limits.items():
        if col in frame:
            frame.loc[~frame[col].between(low, high), col] = np.nan
    return frame


def make_fact(tracks: pd.DataFrame, cases: pd.DataFrame) -> pd.DataFrame:
    all_cases = []
    for case_id in SELECTED_CASES:
        available = tracks[(tracks.caseid == case_id) & tracks.tname.isin(TRACK_MAP)]
        tid_by_name = dict(zip(available.tname, available.tid.astype(str)))
        if "Solar8000/NIBP_MBP" not in tid_by_name or "Solar8000/ART_MBP" not in tid_by_name:
            print(f"Caso {case_id}: ignorado, sem NIBP_MBP ou ART_MBP")
            continue

        base = read_numeric_track(tid_by_name["Solar8000/NIBP_MBP"], "nibp_mbp_mmhg")
        # O monitor repete a última leitura NIBP a cada ~2 s. Mantemos apenas
        # mudanças consecutivas, representando novas aferições do manguito.
        base = base.loc[
            base["nibp_mbp_mmhg"].ne(base["nibp_mbp_mmhg"].shift())
        ].copy()
        base = base.rename(columns={"time_seconds": "nibp_time_seconds"})
        base["time_seconds"] = base["nibp_time_seconds"]
        for tname, out_name in TRACK_MAP.items():
            if out_name == "nibp_mbp_mmhg" or tname not in tid_by_name:
                continue
            tolerance = 10.0 if out_name.startswith("nibp_") else PAIR_TOLERANCE_SECONDS
            base = nearest_join(
                base, read_numeric_track(tid_by_name[tname], out_name), tolerance, out_name
            )

        base = plausible(base)
        base = base.dropna(subset=["nibp_mbp_mmhg", "art_mbp_mmhg"]).copy()
        base["pair_delta_seconds"] = (
            base["art_mbp_mmhg_time_seconds"] - base["nibp_time_seconds"]
        ).abs()
        base["case_id"] = str(case_id)
        base["case_key"] = f"CASE-{case_id:05d}"
        subject = cases.loc[cases.caseid == case_id, "subjectid"]
        subject_id = str(int(subject.iloc[0])) if len(subject) and pd.notna(subject.iloc[0]) else f"UNKNOWN-{case_id}"
        base["patient_key"] = f"PAT-{subject_id}"
        all_cases.append(base)
        print(f"Caso {case_id}: {len(base)} aferições pareadas")

    if not all_cases:
        raise RuntimeError("Nenhuma aferição válida foi obtida")
    fact = pd.concat(all_cases, ignore_index=True)
    fact["time_key"] = fact["time_seconds"].round().astype("int64")
    fact["measurement_id"] = [f"M-{c}-{i:05d}" for i, c in enumerate(fact.case_id)]
    fact["error_sbp_mmhg"] = fact.get("nibp_sbp_mmhg") - fact.get("art_sbp_mmhg")
    fact["error_mbp_mmhg"] = fact.nibp_mbp_mmhg - fact.art_mbp_mmhg
    fact["error_dbp_mmhg"] = fact.get("nibp_dbp_mmhg") - fact.get("art_dbp_mmhg")
    art_hypo = fact.art_mbp_mmhg < 65
    nibp_hypo = fact.nibp_mbp_mmhg < 65
    agreement = np.where(art_hypo == nibp_hypo, "concordant", "discordant")
    fact["label_key"] = [f"A{int(a)}-N{int(n)}-{g}" for a, n, g in zip(art_hypo, nibp_hypo, agreement)]
    return fact


def clean_string(series: pd.Series) -> pd.Series:
    result = series.astype("string").str.strip()
    return result.mask(result.isin(["", "-1", "999", "nan", "None"]))


def make_dimensions(fact: pd.DataFrame, cases: pd.DataFrame):
    selected = cases[cases.caseid.astype(str).isin(fact.case_id.unique())].copy()
    patient = pd.DataFrame({
        "patient_key": "PAT-" + selected.subjectid.astype("Int64").astype("string"),
        "subject_id": selected.subjectid.astype("Int64").astype("string"),
        "sex": clean_string(selected.sex),
        "age_years": pd.to_numeric(selected.age, errors="coerce"),
        "height_cm": pd.to_numeric(selected.height, errors="coerce"),
        "weight_kg": pd.to_numeric(selected.weight, errors="coerce"),
        "bmi_kg_m2": pd.to_numeric(selected.bmi, errors="coerce"),
    }).drop_duplicates("patient_key")
    patient.loc[~patient.age_years.between(0, 120), "age_years"] = np.nan
    patient.loc[~patient.height_cm.between(80, 230), "height_cm"] = np.nan
    patient.loc[~patient.weight_kg.between(2, 350), "weight_kg"] = np.nan
    patient.loc[~patient.bmi_kg_m2.between(8, 80), "bmi_kg_m2"] = np.nan

    case = pd.DataFrame({
        "case_key": "CASE-" + selected.caseid.astype(int).astype(str).str.zfill(5),
        "case_id": selected.caseid.astype(int).astype("string"),
        "department": clean_string(selected.department),
        "operation_type": clean_string(selected.optype),
        "approach": clean_string(selected.approach),
        "position": clean_string(selected.position),
        "anesthesia_type": clean_string(selected.ane_type),
        "asa_class": clean_string(selected.asa),
        "emergency_operation": selected.emop.map({0: False, 1: True}).astype("boolean"),
    }).drop_duplicates("case_key")

    time_dim = fact[["time_key"]].drop_duplicates("time_key").copy()
    time_dim["time_seconds"] = time_dim["time_key"].astype(float)
    time_dim["time_minutes"] = time_dim.time_seconds / 60
    time_dim["intraoperative_phase"] = pd.cut(
        time_dim.time_minutes, [-np.inf, 30, 120, np.inf],
        labels=["initial_0_30min", "middle_30_120min", "late_over_120min"],
    ).astype("string")

    label = fact[["label_key"]].drop_duplicates().copy()
    label["art_hypotension"] = label.label_key.str.extract(r"A([01])")[0].eq("1")
    label["nibp_hypotension"] = label.label_key.str.extract(r"N([01])")[0].eq("1")
    label["agreement_class"] = label.label_key.str.rsplit("-", n=1).str[-1]
    return patient, case, time_dim, label


def write_parquet(df: pd.DataFrame, name: str, schema: pa.Schema) -> Path:
    path = PROCESSED / f"{name}.parquet"
    table = pa.Table.from_pandas(df[[f.name for f in schema]], schema=schema, preserve_index=False, safe=True)
    pq.write_table(table, path, compression=COMPRESSION, write_statistics=True)
    return path


def main() -> None:
    for folder in (RAW, PROCESSED, OUTPUTS):
        folder.mkdir(parents=True, exist_ok=True)
    cases_path = download(CASES_URL, RAW / "cases.csv")
    tracks_path = download(TRACKS_URL, RAW / "tracks.csv")
    cases = pd.read_csv(cases_path)
    tracks = pd.read_csv(tracks_path)
    fact = make_fact(tracks, cases)
    patient, case, time_dim, label = make_dimensions(fact, cases)

    fact_cols = [f.name for f in FACT_SCHEMA]
    fact_csv = PROCESSED / "fact_bp_measurement.csv"
    fact[fact_cols].to_csv(fact_csv, index=False)
    paths = {
        "fact_bp_measurement": write_parquet(fact, "fact_bp_measurement", FACT_SCHEMA),
        "dim_patient": write_parquet(patient, "dim_patient", PATIENT_SCHEMA),
        "dim_case": write_parquet(case, "dim_case", CASE_SCHEMA),
        "dim_time": write_parquet(time_dim, "dim_time", TIME_SCHEMA),
        "dim_label": write_parquet(label, "dim_label", LABEL_SCHEMA),
    }

    db_path = PROCESSED / "vitaldb_star.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    for table_name, parquet_path in paths.items():
        safe_path = str(parquet_path).replace("'", "''")
        # Tabelas físicas tornam o arquivo .duckdb portátil; os Parquets também
        # permanecem consultáveis diretamente com read_parquet().
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{safe_path}')")
    query_sql = (ROOT / "sql" / "queries.sql").read_text(encoding="utf-8")
    queries = [q.strip() for q in query_sql.split(";") if q.strip()]
    report = ["# Resultados reproduzíveis", ""]
    timings = []
    for i, query in enumerate(queries, start=1):
        started = time.perf_counter()
        result = con.execute(query).fetchdf()
        elapsed_ms = (time.perf_counter() - started) * 1000
        timings.append(elapsed_ms)
        report += [f"## Consulta {i}", "", "```sql", query, "```", "", result.to_markdown(index=False), "", f"Tempo: {elapsed_ms:.3f} ms", ""]
    con.close()

    csv_size = fact_csv.stat().st_size
    parquet_size = paths["fact_bp_measurement"].stat().st_size
    benchmark = {
        "generated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "fact_rows": len(fact),
        "cases": int(fact.case_key.nunique()),
        "patients": int(fact.patient_key.nunique()),
        "csv_bytes": csv_size,
        "parquet_bytes": parquet_size,
        "parquet_reduction_percent": round(100 * (1 - parquet_size / csv_size), 2),
        "query_times_ms": [round(x, 3) for x in timings],
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [cases_path, tracks_path]
        },
    }
    (OUTPUTS / "benchmark.json").write_text(json.dumps(benchmark, indent=2), encoding="utf-8")
    report += ["## CSV × Parquet", "", f"- CSV da fato: {csv_size:,} bytes", f"- Parquet Zstandard: {parquet_size:,} bytes", f"- Redução: {benchmark['parquet_reduction_percent']}%", ""]
    (OUTPUTS / "query_results.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(benchmark, indent=2))


if __name__ == "__main__":
    main()
