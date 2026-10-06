"""Executa os testes SQL da Aula 03 e gera relatorio e camadas Silver/Gold."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "quality_checks.sql"
OUTPUTS = ROOT / "outputs"
SILVER = ROOT / "data" / "silver"
GOLD = ROOT / "data" / "gold"


def parse_named_queries(sql_text: str) -> tuple[str, list[tuple[str, str]]]:
    """Separa o bloco de preparacao das consultas marcadas com -- name:."""
    marker = re.compile(r"^-- name: ([\w_]+)\s*$", re.MULTILINE)
    matches = list(marker.finditer(sql_text))
    if not matches:
        raise ValueError("Nenhuma consulta marcada com '-- name:' foi encontrada")
    setup = sql_text[: matches[0].start()]
    queries: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(sql_text)
        query = sql_text[match.end():end].strip().rstrip(";").strip()
        queries.append((match.group(1), query))
    return setup, queries


def main() -> None:
    os.chdir(ROOT)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    SILVER.mkdir(parents=True, exist_ok=True)
    GOLD.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    setup, queries = parse_named_queries(SQL_PATH.read_text(encoding="utf-8"))
    con.execute(setup)

    report = ["# Resultados dos testes de qualidade", ""]
    summary: dict[str, list[dict]] = {}
    frames = {}
    for name, query in queries:
        frame = con.execute(query).fetchdf()
        frames[name] = frame
        summary[name] = json.loads(frame.to_json(orient="records"))
        report.extend([
            f"## {name}", "", "```sql", query, "```", "",
            frame.to_markdown(index=False), "",
        ])

    # Bronze = Parquets recebidos da Aula 02. Silver = dados classificados.
    base_invalid_condition = """
        measurement_id IS NULL OR patient_key IS NULL OR case_key IS NULL
        OR time_key IS NULL OR label_key IS NULL
        OR nibp_mbp_mmhg IS NULL OR art_mbp_mmhg IS NULL
        OR nibp_mbp_mmhg NOT BETWEEN 25 AND 200
        OR art_mbp_mmhg NOT BETWEEN 25 AND 200
        OR pair_delta_seconds NOT BETWEEN 0 AND 30
        OR (nibp_sbp_mmhg IS NOT NULL AND nibp_sbp_mmhg NOT BETWEEN 40 AND 260)
        OR (nibp_dbp_mmhg IS NOT NULL AND nibp_dbp_mmhg NOT BETWEEN 20 AND 160)
        OR (art_sbp_mmhg IS NOT NULL AND art_sbp_mmhg NOT BETWEEN 40 AND 260)
        OR (art_dbp_mmhg IS NOT NULL AND art_dbp_mmhg NOT BETWEEN 20 AND 160)
        OR (heart_rate_bpm IS NOT NULL AND heart_rate_bpm NOT BETWEEN 20 AND 220)
        OR (nibp_sbp_mmhg IS NOT NULL AND nibp_dbp_mmhg IS NOT NULL
            AND (nibp_sbp_mmhg < nibp_mbp_mmhg OR nibp_mbp_mmhg < nibp_dbp_mmhg))
        OR (art_sbp_mmhg IS NOT NULL AND art_dbp_mmhg IS NOT NULL
            AND (art_sbp_mmhg < art_mbp_mmhg OR art_mbp_mmhg < art_dbp_mmhg))
    """
    classification = f"""
        WITH classified AS (
            SELECT f.*,
                   COUNT(*) OVER (PARTITION BY measurement_id) AS duplicate_id_count,
                   COUNT(*) OVER (PARTITION BY case_key, time_key, nibp_mbp_mmhg) AS duplicate_grain_count,
                   (f.art_mbp_mmhg < 65) <> l.art_hypotension AS invalid_art_label,
                   (f.nibp_mbp_mmhg < 65) <> l.nibp_hypotension AS invalid_nibp_label,
                   ((f.art_mbp_mmhg < 65) = (f.nibp_mbp_mmhg < 65)) <>
                       (l.agreement_class = 'concordant') AS invalid_agreement
            FROM fact_bp_measurement f
            LEFT JOIN dim_label l USING (label_key)
        )
    """
    critical_condition = f"""
        ({base_invalid_condition})
        OR duplicate_id_count > 1 OR duplicate_grain_count > 1
        OR invalid_art_label OR invalid_nibp_label OR invalid_agreement
    """
    valid_path = str(SILVER / "fact_bp_measurement_valid.parquet").replace("'", "''")
    quarantine_path = str(SILVER / "fact_bp_measurement_quarantine.parquet").replace("'", "''")
    original_columns = "* EXCLUDE (duplicate_id_count, duplicate_grain_count, invalid_art_label, invalid_nibp_label, invalid_agreement)"
    con.execute(f"COPY ({classification} SELECT {original_columns} FROM classified WHERE NOT ({critical_condition})) TO '{valid_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute(f"COPY ({classification} SELECT {original_columns}, 'regra critica de qualidade' AS quarantine_reason FROM classified WHERE {critical_condition}) TO '{quarantine_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    completeness_path = str(GOLD / "completeness_metrics.parquet").replace("'", "''")
    invalid_path = str(GOLD / "invalid_value_metrics.parquet").replace("'", "''")
    con.register("completeness_frame", frames["02_completude_por_campo"])
    con.register("invalid_frame", frames["03_valores_invalidos_e_consistencia"])
    con.execute(f"COPY completeness_frame TO '{completeness_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.execute(f"COPY invalid_frame TO '{invalid_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    valid_n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{valid_path}')").fetchone()[0]
    quarantine_n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{quarantine_path}')").fetchone()[0]
    report.extend([
        "## Camadas produzidas", "",
        f"- Silver válida: **{valid_n} registros**.",
        f"- Silver em quarentena: **{quarantine_n} registros**.",
        "- Gold: métricas de completude e de valores inválidos em Parquet.", "",
    ])
    summary["camadas"] = [{"silver_validos": valid_n, "silver_quarentena": quarantine_n}]
    (OUTPUTS / "quality_results.md").write_text("\n".join(report), encoding="utf-8")
    (OUTPUTS / "quality_results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    con.close()
    print(f"Concluido: {valid_n} validos; {quarantine_n} em quarentena.")
    print(f"Relatorio: {OUTPUTS / 'quality_results.md'}")


if __name__ == "__main__":
    main()
