from __future__ import annotations

import json
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "input"
OUTPUTS = ROOT / "outputs"
MODELS = ROOT / "models"
MODEL_NAME = "RandomForestRegressor"
MODEL_VERSION = "rf_art_mbp_v1.0"
SEED = 42
N_BOOT = 2000

NUMERIC_FEATURES = [
    "nibp_sbp_mmhg",
    "nibp_mbp_mmhg",
    "nibp_dbp_mmhg",
    "heart_rate_bpm",
    "age_years",
    "height_cm",
    "weight_kg",
    "bmi_kg_m2",
    "time_minutes",
]
CATEGORICAL_FEATURES = ["sex"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "art_mbp_mmhg"


def load_analytic_table() -> pd.DataFrame:
    query = f"""
        SELECT
            f.measurement_id,
            p.subject_id AS patient_id,
            f.patient_key,
            f.case_key AS case_id,
            f.time_key,
            f.nibp_sbp_mmhg,
            f.nibp_mbp_mmhg,
            f.nibp_dbp_mmhg,
            f.art_mbp_mmhg,
            f.heart_rate_bpm,
            p.sex,
            p.age_years,
            p.height_cm,
            p.weight_kg,
            p.bmi_kg_m2,
            t.time_minutes
        FROM read_parquet('{(DATA / 'fact_bp_measurement_valid.parquet').as_posix()}') f
        JOIN read_parquet('{(DATA / 'dim_patient.parquet').as_posix()}') p USING (patient_key)
        JOIN read_parquet('{(DATA / 'dim_time.parquet').as_posix()}') t USING (time_key)
        WHERE f.art_mbp_mmhg IS NOT NULL
        ORDER BY f.measurement_id
    """
    return duckdb.sql(query).fetchdf()


def build_model() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([("imputer", SimpleImputer(strategy="median"))]),
                NUMERIC_FEATURES,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    regressor = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=2,
        random_state=SEED,
        n_jobs=1,
    )
    return Pipeline([("preprocess", preprocessor), ("model", regressor)])


def regression_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    return {
        "mae_mmhg": float(mean_absolute_error(y, pred)),
        "rmse_mmhg": float(mean_squared_error(y, pred) ** 0.5),
        "bias_mmhg": float(np.mean(pred - y)),
        "r2": float(r2_score(y, pred)),
    }


def classification_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    truth = y < 65
    predicted = pred < 65
    tn = int(np.sum(~truth & ~predicted))
    fp = int(np.sum(~truth & predicted))
    fn = int(np.sum(truth & ~predicted))
    tp = int(np.sum(truth & predicted))
    sensitivity = tp / (tp + fn) if (tp + fn) else np.nan
    specificity = tn / (tn + fp) if (tn + fp) else np.nan
    accuracy = (tp + tn) / len(truth) if len(truth) else np.nan
    balanced = (
        (sensitivity + specificity) / 2
        if np.isfinite(sensitivity) and np.isfinite(specificity)
        else np.nan
    )
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    denominator = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
    mcc = ((tp * tn) - (fp * fn)) / denominator if denominator else 0.0
    return {
        "prevalence": float(np.mean(truth)),
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "accuracy": float(accuracy),
        "balanced_accuracy": float(balanced),
        "f1": float(f1),
        "mcc": float(mcc),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def cluster_bootstrap_ci(
    frame: pd.DataFrame,
    prediction_column: str,
    metric_fn,
    metric_names: list[str],
) -> dict[str, dict[str, float]]:
    rng = np.random.default_rng(SEED)
    patients = frame["patient_id"].unique()
    draws: dict[str, list[float]] = {name: [] for name in metric_names}
    for _ in range(N_BOOT):
        sampled = rng.choice(patients, size=len(patients), replace=True)
        pieces = [frame.loc[frame["patient_id"] == patient] for patient in sampled]
        boot = pd.concat(pieces, ignore_index=True)
        values = metric_fn(
            boot["art_mbp_reference_mmhg"].to_numpy(),
            boot[prediction_column].to_numpy(),
        )
        for name in metric_names:
            value = values[name]
            if np.isfinite(value):
                draws[name].append(float(value))
    return {
        name: {
            "lower_95": float(np.percentile(values, 2.5)),
            "upper_95": float(np.percentile(values, 97.5)),
        }
        for name, values in draws.items()
        if values
    }


def save_parquet(frame: pd.DataFrame, destination: Path) -> None:
    connection = duckdb.connect()
    connection.register("output_frame", frame)
    connection.execute(
        f"COPY output_frame TO '{destination.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    connection.close()


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    data = load_analytic_table()
    if data["patient_id"].nunique() < 3:
        raise ValueError("Sao necessarios pelo menos tres pacientes para a avaliacao agrupada.")
    if data["measurement_id"].duplicated().any():
        raise ValueError("measurement_id duplicado; interrompendo para evitar avaliacao incorreta.")

    logo = LeaveOneGroupOut()
    predictions = np.full(len(data), np.nan)
    fold_ids = np.full(len(data), -1, dtype=int)
    train_patient_counts = np.full(len(data), -1, dtype=int)
    manifest_rows = []

    for fold, (train_idx, test_idx) in enumerate(
        logo.split(data[FEATURES], data[TARGET], groups=data["patient_id"]), start=1
    ):
        train_patients = set(data.iloc[train_idx]["patient_id"])
        test_patients = set(data.iloc[test_idx]["patient_id"])
        if train_patients & test_patients:
            raise RuntimeError("Vazamento detectado entre pacientes de treino e teste.")
        model = build_model()
        model.fit(data.iloc[train_idx][FEATURES], data.iloc[train_idx][TARGET])
        predictions[test_idx] = model.predict(data.iloc[test_idx][FEATURES])
        fold_ids[test_idx] = fold
        train_patient_counts[test_idx] = len(train_patients)
        manifest_rows.append(
            {
                "fold_id": fold,
                "test_patient_id": next(iter(test_patients)),
                "n_train_patients": len(train_patients),
                "n_train_samples": len(train_idx),
                "n_test_samples": len(test_idx),
                "patient_overlap": 0,
            }
        )

    if np.isnan(predictions).any():
        raise RuntimeError("Existem amostras sem predicao fora do paciente.")

    result = pd.DataFrame(
        {
            "measurement_id": data["measurement_id"].astype(str),
            "patient_id": data["patient_id"].astype(str),
            "case_id": data["case_id"].astype(str),
            "fold_id": fold_ids,
            "evaluation_role": "held_out_patient_test",
            "art_mbp_reference_mmhg": data[TARGET].astype(float),
            "art_mbp_predicted_mmhg": predictions,
            "prediction_error_mmhg": predictions - data[TARGET].to_numpy(),
            "absolute_error_mmhg": np.abs(predictions - data[TARGET].to_numpy()),
            "baseline_nibp_mbp_mmhg": data["nibp_mbp_mmhg"].astype(float),
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "sklearn_version": sklearn.__version__,
            "n_train_patients": train_patient_counts,
        }
    )

    model_reg = regression_metrics(
        result["art_mbp_reference_mmhg"].to_numpy(),
        result["art_mbp_predicted_mmhg"].to_numpy(),
    )
    baseline_reg = regression_metrics(
        result["art_mbp_reference_mmhg"].to_numpy(),
        result["baseline_nibp_mbp_mmhg"].to_numpy(),
    )
    model_cls = classification_metrics(
        result["art_mbp_reference_mmhg"].to_numpy(),
        result["art_mbp_predicted_mmhg"].to_numpy(),
    )
    baseline_cls = classification_metrics(
        result["art_mbp_reference_mmhg"].to_numpy(),
        result["baseline_nibp_mbp_mmhg"].to_numpy(),
    )

    reg_names = ["mae_mmhg", "rmse_mmhg", "bias_mmhg", "r2"]
    cls_names = ["sensitivity", "specificity", "balanced_accuracy", "f1", "mcc"]
    model_reg_ci = cluster_bootstrap_ci(
        result, "art_mbp_predicted_mmhg", regression_metrics, reg_names
    )
    baseline_reg_ci = cluster_bootstrap_ci(
        result, "baseline_nibp_mbp_mmhg", regression_metrics, reg_names
    )
    model_cls_ci = cluster_bootstrap_ci(
        result, "art_mbp_predicted_mmhg", classification_metrics, cls_names
    )
    baseline_cls_ci = cluster_bootstrap_ci(
        result, "baseline_nibp_mbp_mmhg", classification_metrics, cls_names
    )

    metrics = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "evaluation": "LeaveOneGroupOut por patient_id",
        "n_samples": int(len(result)),
        "n_patients": int(result["patient_id"].nunique()),
        "n_hypotension_reference": int((result["art_mbp_reference_mmhg"] < 65).sum()),
        "random_forest_regression": {"point": model_reg, "cluster_bootstrap_95_ci": model_reg_ci},
        "nibp_direct_baseline_regression": {
            "point": baseline_reg,
            "cluster_bootstrap_95_ci": baseline_reg_ci,
        },
        "random_forest_hypotension_threshold": {
            "point": model_cls,
            "cluster_bootstrap_95_ci": model_cls_ci,
        },
        "nibp_direct_hypotension_threshold": {
            "point": baseline_cls,
            "cluster_bootstrap_95_ci": baseline_cls_ci,
        },
    }

    result.to_csv(OUTPUTS / "predictions_oof.csv", index=False)
    save_parquet(result, OUTPUTS / "predictions_oof.parquet")
    pd.DataFrame(manifest_rows).to_csv(OUTPUTS / "split_manifest.csv", index=False)

    by_patient = (
        result.groupby("patient_id", as_index=False)
        .agg(
            n=("measurement_id", "size"),
            mae_mmhg=("absolute_error_mmhg", "mean"),
            bias_mmhg=("prediction_error_mmhg", "mean"),
            reference_mean_mmhg=("art_mbp_reference_mmhg", "mean"),
            predicted_mean_mmhg=("art_mbp_predicted_mmhg", "mean"),
        )
        .sort_values("mae_mmhg", ascending=False)
    )
    by_patient.to_csv(OUTPUTS / "errors_by_patient.csv", index=False)
    worst = result.nlargest(5, "absolute_error_mmhg")
    worst.to_csv(OUTPUTS / "largest_errors.csv", index=False)

    with (OUTPUTS / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, ensure_ascii=False)

    final_model = build_model()
    final_model.fit(data[FEATURES], data[TARGET])
    joblib.dump(
        {
            "pipeline": final_model,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "features": FEATURES,
            "target": TARGET,
            "training_samples": len(data),
            "training_patients": data["patient_id"].nunique(),
            "sklearn_version": sklearn.__version__,
        },
        MODELS / f"{MODEL_VERSION}.joblib",
    )

    def metric_table(point: dict, ci: dict, names: list[str]) -> pd.DataFrame:
        rows = []
        for name in names:
            interval = ci.get(name, {})
            rows.append(
                {
                    "metrica": name,
                    "estimativa": point[name],
                    "IC95_inferior": interval.get("lower_95", np.nan),
                    "IC95_superior": interval.get("upper_95", np.nan),
                }
            )
        return pd.DataFrame(rows).round(3)

    reg_table = metric_table(model_reg, model_reg_ci, reg_names)
    base_reg_table = metric_table(baseline_reg, baseline_reg_ci, reg_names)
    cls_table = metric_table(model_cls, model_cls_ci, cls_names)
    base_cls_table = metric_table(baseline_cls, baseline_cls_ci, cls_names)
    cm = pd.DataFrame(
        [[model_cls["tn"], model_cls["fp"]], [model_cls["fn"], model_cls["tp"]]],
        index=["ART nao", "ART sim"],
        columns=["Predicao nao", "Predicao sim"],
    )

    report = f"""# Resultados — Aula 04

## Desenho da avaliação

- Modelo: `{MODEL_NAME}`; versão `{MODEL_VERSION}`.
- Alvo: `ART_MBP` em mmHg.
- Avaliação: Leave-One-Patient-Out, com {result['patient_id'].nunique()} folds.
- Amostras: {len(result)}; pacientes: {result['patient_id'].nunique()}.
- Vazamento entre pacientes de treino e teste: **não detectado**.
- Intervalos de confiança: bootstrap de 2.000 reamostragens por paciente.

## Regressão — Random Forest

{reg_table.to_markdown(index=False)}

## Regressão — referência simples NIBP_MBP

{base_reg_table.to_markdown(index=False)}

## Hipotensão derivada da predição — ART_MBP < 65 mmHg

Prevalência de referência: {model_cls['prevalence']:.3f} ({int((result['art_mbp_reference_mmhg'] < 65).sum())}/{len(result)} aferições).

{cls_table.to_markdown(index=False)}

### Matriz de confusão do modelo

{cm.to_markdown()}

## Hipotensão pela referência simples NIBP_MBP < 65 mmHg

{base_cls_table.to_markdown(index=False)}

## Erros por paciente

{by_patient.round(2).to_markdown(index=False)}

## Cinco maiores erros absolutos

{worst[['measurement_id','patient_id','art_mbp_reference_mmhg','art_mbp_predicted_mmhg','prediction_error_mmhg','absolute_error_mmhg']].round(2).to_markdown(index=False)}

## Interpretação e limitações

As predições são estritamente fora do paciente: nenhuma aferição do paciente avaliado apareceu no treino daquele fold. Isso reduz vazamento, mas não resolve a limitação de tamanho amostral. Há somente sete pacientes e os episódios de hipotensão concentram-se em dois deles, tornando as métricas classificatórias e seus intervalos instáveis. O modelo foi aplicado como demonstração acadêmica; não está validado para uso clínico, não estima causalidade e não substitui a pressão invasiva. O modelo final salvo foi reajustado com todas as 30 aferições apenas para permitir reprodução e uso futuro; suas métricas provêm exclusivamente das predições fora do paciente.
"""
    (OUTPUTS / "evaluation_report.md").write_text(report, encoding="utf-8")

    print(f"Concluido: {len(result)} predicoes fora do paciente; {result['patient_id'].nunique()} pacientes.")
    print(f"MAE: {model_reg['mae_mmhg']:.2f} mmHg | RMSE: {model_reg['rmse_mmhg']:.2f} mmHg")
    print(f"Relatorio: {OUTPUTS / 'evaluation_report.md'}")


if __name__ == "__main__":
    main()
