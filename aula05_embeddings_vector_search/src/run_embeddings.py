from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import onnxruntime as ort
import pandas as pd
from huggingface_hub import hf_hub_download
from sklearn.decomposition import PCA
from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "input"
OUTPUTS = ROOT / "outputs"
FIGURES = ROOT / "figures"
CACHE = ROOT / ".cache" / "huggingface"

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_FILE = "onnx/model_quint8_avx2.onnx"
MODEL_VERSION = "all-MiniLM-L6-v2@1110a243-onnx-int8"
EMBEDDING_DIMENSION = 384
TOP_K = 3
NEAR_DUPLICATE_THRESHOLD = 0.995


def load_data() -> pd.DataFrame:
    query = f"""
        SELECT
            f.measurement_id,
            p.subject_id AS patient_id,
            f.case_key AS case_id,
            f.nibp_sbp_mmhg,
            f.nibp_mbp_mmhg,
            f.nibp_dbp_mmhg,
            f.art_mbp_mmhg,
            f.heart_rate_bpm,
            p.sex,
            p.age_years,
            p.bmi_kg_m2,
            t.time_minutes
        FROM read_parquet('{(DATA / 'fact_bp_measurement_valid.parquet').as_posix()}') f
        JOIN read_parquet('{(DATA / 'dim_patient.parquet').as_posix()}') p USING (patient_key)
        JOIN read_parquet('{(DATA / 'dim_time.parquet').as_posix()}') t USING (time_key)
        ORDER BY f.measurement_id
    """
    frame = duckdb.sql(query).fetchdf()
    frame["patient_id"] = frame["patient_id"].astype(str)
    frame["hypotension_reference"] = frame["art_mbp_mmhg"] < 65
    return frame


def fmt(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return "unknown"
    return f"{float(value):.{digits}f}"


def build_clinical_text(row: pd.Series) -> str:
    sex = {"F": "female", "M": "male"}.get(str(row["sex"]), "unknown")
    return (
        f"Clinical measurement. Patient sex {sex}, age {fmt(row['age_years'], 0)} years, "
        f"body mass index {fmt(row['bmi_kg_m2'])} kilograms per square meter. "
        f"Non-invasive blood pressure: systolic {fmt(row['nibp_sbp_mmhg'], 0)} millimeters of mercury, "
        f"mean {fmt(row['nibp_mbp_mmhg'], 0)} millimeters of mercury, "
        f"diastolic {fmt(row['nibp_dbp_mmhg'], 0)} millimeters of mercury. "
        f"Heart rate {fmt(row['heart_rate_bpm'], 0)} beats per minute. "
        f"Time {fmt(row['time_minutes'])} minutes after procedure start."
    )


def generate_embeddings(texts: list[str]) -> np.ndarray:
    CACHE.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        cache_dir=CACHE,
    )
    model_path = hf_hub_download(
        repo_id=MODEL_ID,
        filename=MODEL_FILE,
        revision=MODEL_REVISION,
        cache_dir=CACHE,
    )
    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=256,
        return_tensors="np",
    )
    input_names = {item.name for item in session.get_inputs()}
    feed = {
        key: np.asarray(value, dtype=np.int64)
        for key, value in encoded.items()
        if key in input_names
    }
    token_embeddings = session.run(None, feed)[0]
    mask = np.asarray(encoded["attention_mask"], dtype=np.float32)[..., None]
    pooled = (token_embeddings * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    normalized = pooled / np.clip(norms, 1e-12, None)
    if normalized.shape[1] != EMBEDDING_DIMENSION:
        raise RuntimeError(f"Dimensao inesperada: {normalized.shape[1]}")
    return normalized.astype(np.float32)


def save_parquet(frame: pd.DataFrame, path: Path) -> None:
    connection = duckdb.connect()
    connection.register("output_frame", frame)
    connection.execute(
        f"COPY output_frame TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    connection.close()


def make_neighbor_tables(
    frame: pd.DataFrame, embeddings: np.ndarray
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    similarity = embeddings @ embeddings.T
    rows: list[dict] = []
    cross_rows: list[dict] = []
    for i in range(len(frame)):
        scores = similarity[i].copy()
        scores[i] = -np.inf
        order = np.argsort(-scores)
        for rank, j in enumerate(order[:TOP_K], start=1):
            rows.append(
                {
                    "query_measurement_id": frame.iloc[i]["measurement_id"],
                    "query_patient_id": frame.iloc[i]["patient_id"],
                    "neighbor_rank": rank,
                    "neighbor_measurement_id": frame.iloc[j]["measurement_id"],
                    "neighbor_patient_id": frame.iloc[j]["patient_id"],
                    "cosine_similarity": float(scores[j]),
                    "same_patient": bool(frame.iloc[i]["patient_id"] == frame.iloc[j]["patient_id"]),
                    "same_hypotension_label": bool(
                        frame.iloc[i]["hypotension_reference"]
                        == frame.iloc[j]["hypotension_reference"]
                    ),
                    "model_version": MODEL_VERSION,
                }
            )

        cross_order = [
            j for j in order if frame.iloc[j]["patient_id"] != frame.iloc[i]["patient_id"]
        ]
        for rank, j in enumerate(cross_order[:TOP_K], start=1):
            cross_rows.append(
                {
                    "query_measurement_id": frame.iloc[i]["measurement_id"],
                    "query_patient_id": frame.iloc[i]["patient_id"],
                    "neighbor_rank": rank,
                    "neighbor_measurement_id": frame.iloc[j]["measurement_id"],
                    "neighbor_patient_id": frame.iloc[j]["patient_id"],
                    "cosine_similarity": float(scores[j]),
                    "possible_near_duplicate": bool(scores[j] >= NEAR_DUPLICATE_THRESHOLD),
                    "same_hypotension_label": bool(
                        frame.iloc[i]["hypotension_reference"]
                        == frame.iloc[j]["hypotension_reference"]
                    ),
                    "model_version": MODEL_VERSION,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(cross_rows), similarity


def make_figures(frame: pd.DataFrame, embeddings: np.ndarray, similarity: np.ndarray) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    pca = PCA(n_components=2, random_state=42)
    points = pca.fit_transform(embeddings)
    patients = sorted(frame["patient_id"].unique())
    colors = plt.get_cmap("tab10", len(patients))

    fig, ax = plt.subplots(figsize=(10, 7))
    for idx, patient in enumerate(patients):
        mask = frame["patient_id"].eq(patient).to_numpy()
        ax.scatter(
            points[mask, 0],
            points[mask, 1],
            s=75,
            alpha=0.85,
            color=colors(idx),
            label=f"Paciente {patient}",
            edgecolor="white",
            linewidth=0.7,
        )
    hypotension = frame["hypotension_reference"].to_numpy()
    ax.scatter(
        points[hypotension, 0],
        points[hypotension, 1],
        s=170,
        facecolors="none",
        edgecolors="black",
        linewidth=1.5,
        label="ART_MBP < 65 mmHg",
    )
    ax.set_title("Projeção PCA dos embeddings clínicos")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.1f}% da variância)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.1f}% da variância)")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8, ncol=2, loc="best")
    fig.tight_layout()
    fig.savefig(FIGURES / "embedding_pca_by_patient.png", dpi=180)
    plt.close(fig)

    order = np.argsort(frame["patient_id"].astype(int).to_numpy())
    ordered = similarity[np.ix_(order, order)]
    fig, ax = plt.subplots(figsize=(9, 8))
    image = ax.imshow(ordered, vmin=float(ordered.min()), vmax=1.0, cmap="viridis")
    ax.set_title("Matriz de similaridade de cosseno")
    ax.set_xlabel("Amostras ordenadas por paciente")
    ax.set_ylabel("Amostras ordenadas por paciente")
    fig.colorbar(image, ax=ax, label="Similaridade")
    fig.tight_layout()
    fig.savefig(FIGURES / "cosine_similarity_matrix.png", dpi=180)
    plt.close(fig)


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    frame = load_data()
    frame["clinical_text"] = frame.apply(build_clinical_text, axis=1)
    embeddings = generate_embeddings(frame["clinical_text"].tolist())
    neighbors, cross_neighbors, similarity = make_neighbor_tables(frame, embeddings)
    make_figures(frame, embeddings, similarity)

    embedding_frame = frame[
        [
            "measurement_id",
            "patient_id",
            "case_id",
            "hypotension_reference",
            "clinical_text",
        ]
    ].copy()
    embedding_frame["model_id"] = MODEL_ID
    embedding_frame["model_revision"] = MODEL_REVISION
    embedding_frame["model_version"] = MODEL_VERSION
    embedding_frame["embedding_dimension"] = EMBEDDING_DIMENSION
    embedding_frame["embedding"] = [vector.tolist() for vector in embeddings]
    embedding_frame["embedding_json"] = [json.dumps(vector.tolist()) for vector in embeddings]

    csv_frame = embedding_frame.drop(columns=["embedding"])
    csv_frame.to_csv(OUTPUTS / "embeddings.csv", index=False)
    save_parquet(embedding_frame.drop(columns=["embedding_json"]), OUTPUTS / "embeddings.parquet")
    neighbors.to_csv(OUTPUTS / "nearest_neighbors.csv", index=False)
    save_parquet(neighbors, OUTPUTS / "nearest_neighbors.parquet")
    cross_neighbors.to_csv(OUTPUTS / "cross_patient_neighbors.csv", index=False)
    frame[
        ["measurement_id", "patient_id", "case_id", "clinical_text", "hypotension_reference"]
    ].to_csv(OUTPUTS / "clinical_texts.csv", index=False)

    top1 = neighbors.loc[neighbors["neighbor_rank"] == 1]
    top3_same_patient = neighbors.groupby("query_measurement_id")["same_patient"].any()
    counts = frame["patient_id"].value_counts().to_numpy()
    n = len(frame)
    chance_same_patient = float(np.sum(counts * (counts - 1)) / (n * (n - 1)))
    exact_duplicate_rows = int(frame["clinical_text"].duplicated(keep=False).sum())
    cross_top1 = cross_neighbors.loc[cross_neighbors["neighbor_rank"] == 1]
    near_duplicate_queries = int(cross_top1["possible_near_duplicate"].sum())
    metrics = {
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_version": MODEL_VERSION,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "n_samples": n,
        "n_patients": int(frame["patient_id"].nunique()),
        "top1_same_patient_rate": float(top1["same_patient"].mean()),
        "top3_contains_same_patient_rate": float(top3_same_patient.mean()),
        "random_neighbor_same_patient_probability": chance_same_patient,
        "top1_same_hypotension_label_rate": float(top1["same_hypotension_label"].mean()),
        "exact_duplicate_text_rows": exact_duplicate_rows,
        "near_duplicate_threshold": NEAR_DUPLICATE_THRESHOLD,
        "cross_patient_top1_near_duplicate_queries": near_duplicate_queries,
        "cross_patient_top1_similarity_mean": float(cross_top1["cosine_similarity"].mean()),
        "cross_patient_top1_similarity_max": float(cross_top1["cosine_similarity"].max()),
        "same_patient_crosses_grouped_train_test_split": False,
    }
    (OUTPUTS / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    display_top = neighbors.sort_values("cosine_similarity", ascending=False).head(10).copy()
    display_cross = cross_top1.sort_values("cosine_similarity", ascending=False).head(10).copy()
    for table in (display_top, display_cross):
        table["cosine_similarity"] = table["cosine_similarity"].round(4)

    same_rate = metrics["top1_same_patient_rate"]
    chance_rate = metrics["random_neighbor_same_patient_probability"]
    interpretation = (
        "A proporção observada de vizinhos de primeiro nível do mesmo paciente foi superior "
        "à probabilidade de um vizinho aleatório pertencer ao mesmo paciente. Isso sugere que "
        "características repetidas do paciente e o contexto fisiológico influenciaram a vizinhança."
        if same_rate > chance_rate
        else "A proporção observada de vizinhos do mesmo paciente não superou a referência aleatória, "
        "portanto não há evidência descritiva de forte agrupamento por paciente neste pequeno recorte."
    )

    report = f"""# Resultados — embeddings e busca vetorial

## Configuração

- Modelo: `{MODEL_ID}`.
- Revisão fixa: `{MODEL_REVISION}`.
- Versão do artefato: `{MODEL_VERSION}`.
- Dimensão: {EMBEDDING_DIMENSION}.
- Similaridade: cosseno entre embeddings normalizados.
- Amostras: {n}; pacientes: {frame['patient_id'].nunique()}.

## Resultados descritivos

| Indicador | Resultado |
|---|---:|
| Vizinho top-1 do mesmo paciente | {same_rate:.1%} |
| Referência aleatória para mesmo paciente | {chance_rate:.1%} |
| Algum vizinho do mesmo paciente no top-3 | {metrics['top3_contains_same_patient_rate']:.1%} |
| Top-1 com mesmo rótulo de hipotensão | {metrics['top1_same_hypotension_label_rate']:.1%} |
| Textos exatamente duplicados | {exact_duplicate_rows} |
| Consultas com possível quase duplicata entre pacientes (≥ {NEAR_DUPLICATE_THRESHOLD}) | {near_duplicate_queries} |
| Maior similaridade top-1 entre pacientes | {metrics['cross_patient_top1_similarity_max']:.4f} |

## Dez pares mais próximos sem restrição de paciente

{display_top[['query_measurement_id','query_patient_id','neighbor_measurement_id','neighbor_patient_id','cosine_similarity','same_patient','same_hypotension_label']].to_markdown(index=False)}

## Vizinhos de outro paciente — maiores similaridades top-1

{display_cross[['query_measurement_id','query_patient_id','neighbor_measurement_id','neighbor_patient_id','cosine_similarity','possible_near_duplicate','same_hypotension_label']].to_markdown(index=False)}

## Visualizações

![Projeção PCA](../figures/embedding_pca_by_patient.png)

![Matriz de similaridade](../figures/cosine_similarity_matrix.png)

## Interpretação

{interpretation}

As descrições excluíram ART, rótulos, IDs e resultados anteriores. Assim, a busca não recebeu diretamente a resposta nem a identidade do paciente. Mesmo assim, sexo, idade e IMC se repetem dentro do paciente e podem aproximar suas aferições. Em uma divisão aleatória por linha, esses pares poderiam aparecer em treino e teste e produzir estimativas otimistas. A divisão por paciente usada na Aula 04 impede esse vazamento: medições do mesmo paciente nunca cruzam treino e teste.

O rótulo de hipotensão foi usado apenas para interpretação. A concordância entre vizinhos não demonstra capacidade diagnóstica, principalmente porque há somente seis aferições hipotensas concentradas em dois pacientes e predominância da classe não hipotensa.

## Onde a abordagem pode errar

- O MiniLM foi treinado para semântica de linguagem geral, não para distância fisiológica entre números.
- O molde textual é quase igual em todas as linhas; pequenas diferenças numéricas podem produzir similaridades muito altas.
- Uma diferença de 10 mmHg não possui necessariamente no espaço textual o significado clínico esperado.
- A projeção PCA reduz 384 dimensões a duas e pode ocultar ou distorcer relações.
- A amostra tem apenas 30 aferições de sete pacientes.
- Similaridade não implica equivalência clínica, causalidade ou segurança diagnóstica.

Sem validação externa e sem um conjunto rotulado especificamente para relevância de vizinhos, não é possível afirmar que os pares recuperados sejam clinicamente equivalentes. A atividade demonstra corretamente a geração de embeddings, a busca vetorial e a auditoria de vazamento, mas não valida o modelo para uso assistencial.
"""
    (OUTPUTS / "embedding_report.md").write_text(report, encoding="utf-8")

    print(f"Concluido: {n} embeddings; dimensao {EMBEDDING_DIMENSION}; {len(neighbors)} relacoes de vizinhanca.")
    print(f"Top-1 do mesmo paciente: {same_rate:.1%} | referencia aleatoria: {chance_rate:.1%}")
    print(f"Relatorio: {OUTPUTS / 'embedding_report.md'}")


if __name__ == "__main__":
    main()
