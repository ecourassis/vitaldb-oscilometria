"""Gera o notebook do projeto de forma determinística."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "01_eda_vitaldb.ipynb"

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.11"},
}

cells = []
cells.append(nbf.v4.new_markdown_cell("""# EDA — concordância entre NIBP e ART no VitalDB

**Objetivo:** explorar a concordância entre a pressão arterial não invasiva oscilométrica (`NIBP`) e a pressão arterial invasiva (`ART`) no contexto intraoperatório.

O notebook baixa uma amostra determinística do VitalDB, pareia as medidas no tempo, avalia cobertura/diversidade, produz Bland–Altman e testa um modelo exploratório do erro. Ele não substitui validação formal segundo ISO 81060-2.
"""))

cells.append(nbf.v4.new_code_cell("""# No Google Colab, descomente a linha seguinte:
# %pip install -q -r https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPOSITORIO/main/requirements.txt

from pathlib import Path
from datetime import datetime, timezone
import platform, sys, warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
import vitaldb

SEED = 42
N_CASES = 8          # aumente com cautela; o download ficará mais demorado
INTERVAL = 1         # segundos
PAIR_WINDOW = 30     # tolerância máxima para a referência temporal
np.random.seed(SEED)
sns.set_theme(style="whitegrid")

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
(ROOT / "data" / "cache").mkdir(parents=True, exist_ok=True)

print("Execução (UTC):", datetime.now(timezone.utc).isoformat())
print("Python:", sys.version.split()[0], "| Plataforma:", platform.platform())
print("pandas:", pd.__version__, "| numpy:", np.__version__, "| sklearn:", sklearn.__version__)
print({"seed": SEED, "n_cases": N_CASES, "interval_s": INTERVAL, "pair_window_s": PAIR_WINDOW})
"""))

cells.append(nbf.v4.new_markdown_cell("""## 1. Metadados e seleção dos casos

Selecionamos apenas casos que possuem simultaneamente NIBP, ART e frequência cardíaca. A amostra é determinística para que execuções sucessivas usem os mesmos casos.
"""))

cells.append(nbf.v4.new_code_cell("""CASES_URL = "https://api.vitaldb.net/cases"
TRACKS_URL = "https://api.vitaldb.net/trks"

cases = pd.read_csv(CASES_URL)
tracks = pd.read_csv(TRACKS_URL)
display(cases.head())
print("Casos clínicos:", len(cases), "| Registros de trilhas:", len(tracks))
print("Colunas de cases:", list(cases.columns))
print("Colunas de tracks:", list(tracks.columns))
"""))

cells.append(nbf.v4.new_code_cell("""TRACKS = [
    "Solar8000/NIBP_SBP", "Solar8000/NIBP_MBP", "Solar8000/NIBP_DBP",
    "Solar8000/ART_SBP", "Solar8000/ART_MBP", "Solar8000/ART_DBP",
    "Solar8000/HR",
]

name_col = "tname" if "tname" in tracks.columns else "track_names"
eligible = (tracks[tracks[name_col].isin(TRACKS)]
            .groupby("caseid")[name_col].nunique())
eligible_ids = eligible[eligible >= 7].index.to_numpy()
selected_ids = np.sort(np.random.default_rng(SEED).choice(
    eligible_ids, size=min(N_CASES, len(eligible_ids)), replace=False
))
print("Casos elegíveis:", len(eligible_ids))
print("Amostra:", selected_ids.tolist())
"""))

cells.append(nbf.v4.new_markdown_cell("""## 2. Download seletivo e construção da tabela analítica

`load_case` retorna as trilhas em uma grade regular de 1 segundo. Mantemos instantes com NIBP disponível e buscamos a mediana de ART em uma janela de ±30 s. A janela reduz o efeito de ruído pontual, mas pode introduzir erro em mudanças hemodinâmicas rápidas — uma limitação que deve acompanhar os resultados.
"""))

cells.append(nbf.v4.new_code_cell("""def load_one_case(caseid):
    arr = vitaldb.load_case(int(caseid), TRACKS, interval=INTERVAL)
    df = pd.DataFrame(arr, columns=[x.split("/")[-1] for x in TRACKS])
    df["time_s"] = np.arange(len(df)) * INTERVAL
    df["caseid"] = int(caseid)

    # ART suavizada localmente serve como referência temporal da aferição NIBP.
    win = max(3, int(2 * PAIR_WINDOW / INTERVAL) + 1)
    for suffix in ["SBP", "MBP", "DBP"]:
        df[f"ART_{suffix}_ref"] = df[f"ART_{suffix}"].rolling(
            win, center=True, min_periods=1
        ).median()

    # Uma linha por atualização NIBP; remove repetições consecutivas do mesmo triplo.
    nibp_cols = ["NIBP_SBP", "NIBP_MBP", "NIBP_DBP"]
    has_nibp = df[nibp_cols].notna().all(axis=1)
    changed = df[nibp_cols].ne(df[nibp_cols].shift()).any(axis=1)
    return df.loc[has_nibp & changed].copy()

parts, failures = [], []
for cid in selected_ids:
    try:
        part = load_one_case(cid)
        if not part.empty:
            parts.append(part)
        print(f"caseid={cid}: {len(part)} medidas NIBP")
    except Exception as exc:
        failures.append((int(cid), str(exc)))
        warnings.warn(f"Falha no caso {cid}: {exc}")

if not parts:
    raise RuntimeError("Nenhum caso foi carregado. Verifique a conexão e a disponibilidade da API.")

paired = pd.concat(parts, ignore_index=True)
paired = paired.merge(cases, on="caseid", how="left", suffixes=("", "_clinical"))
print("Falhas:", failures)
print("Linhas antes dos filtros:", len(paired))
"""))

cells.append(nbf.v4.new_code_cell("""# Regras exploratórias de plausibilidade; não são limites regulatórios.
ranges = {
    "NIBP_SBP": (40, 260), "NIBP_MBP": (25, 200), "NIBP_DBP": (20, 160),
    "ART_SBP_ref": (40, 260), "ART_MBP_ref": (25, 200), "ART_DBP_ref": (20, 160),
    "HR": (20, 220),
}
mask = pd.Series(True, index=paired.index)
for col, (lo, hi) in ranges.items():
    mask &= paired[col].between(lo, hi)

excluded = int((~mask).sum())
paired = paired.loc[mask].copy()
paired["bmi"] = paired["weight"] / (paired["height"] / 100) ** 2
paired["time_min"] = paired["time_s"] / 60
for suffix in ["SBP", "MBP", "DBP"]:
    paired[f"error_{suffix}"] = paired[f"NIBP_{suffix}"] - paired[f"ART_{suffix}_ref"]
paired["art_hypotension"] = paired["ART_MBP_ref"] < 65
paired["nibp_hypotension"] = paired["NIBP_MBP"] < 65

print("Excluídas por ausência/implausibilidade:", excluded)
print("Pares analíticos:", len(paired), "| Casos:", paired.caseid.nunique())
display(paired.head())
"""))

cells.append(nbf.v4.new_markdown_cell("## 3. Cobertura, diversidade e distribuições"))

cells.append(nbf.v4.new_code_cell("""coverage = pd.DataFrame({
    "tipo": paired.dtypes.astype(str),
    "ausentes_n": paired.isna().sum(),
    "ausentes_pct": (100 * paired.isna().mean()).round(1),
    "unicos": paired.nunique(dropna=True),
}).sort_values("ausentes_pct", ascending=False)
display(coverage.head(20))

demo_cols = [c for c in ["sex", "age", "height", "weight", "bmi"] if c in paired]
display(paired.groupby("caseid")[demo_cols].first().describe(include="all").T)
"""))

cells.append(nbf.v4.new_code_cell("""fig, axes = plt.subplots(2, 2, figsize=(12, 8))
sns.histplot(paired, x="NIBP_MBP", kde=True, ax=axes[0, 0], color="#2a6fbb")
axes[0, 0].set_title("Distribuição da PAM não invasiva")
sns.histplot(paired, x="ART_MBP_ref", kde=True, ax=axes[0, 1], color="#d95f02")
axes[0, 1].set_title("Distribuição da PAM invasiva de referência")
sns.scatterplot(paired, x="ART_MBP_ref", y="NIBP_MBP", hue="sex", alpha=.55, ax=axes[1, 0])
lims = [min(paired.ART_MBP_ref.min(), paired.NIBP_MBP.min()), max(paired.ART_MBP_ref.max(), paired.NIBP_MBP.max())]
axes[1, 0].plot(lims, lims, "k--", linewidth=1)
axes[1, 0].set_title("NIBP vs ART (linha de identidade)")
sns.boxplot(paired, x="sex", y="error_MBP", ax=axes[1, 1])
axes[1, 1].axhline(0, color="black", linestyle="--", linewidth=1)
axes[1, 1].set_title("Erro da PAM por sexo")
plt.tight_layout()
plt.show()
"""))

cells.append(nbf.v4.new_markdown_cell("## 4. Concordância e erro"))

cells.append(nbf.v4.new_code_cell("""rows = []
for suffix in ["SBP", "MBP", "DBP"]:
    y = paired[f"ART_{suffix}_ref"]
    p = paired[f"NIBP_{suffix}"]
    d = p - y
    rows.append({
        "pressao": suffix,
        "n": len(d),
        "vies_medio_mmHg": d.mean(),
        "dp_diferenca_mmHg": d.std(ddof=1),
        "mae_mmHg": mean_absolute_error(y, p),
        "rmse_mmHg": mean_squared_error(y, p) ** 0.5,
        "correlacao_pearson": y.corr(p),
    })
metrics = pd.DataFrame(rows).round(2)
display(metrics)
print("Correlação é apresentada apenas como complemento; não substitui análise de concordância.")
"""))

cells.append(nbf.v4.new_code_cell("""mean_bp = (paired["NIBP_MBP"] + paired["ART_MBP_ref"]) / 2
diff = paired["error_MBP"]
bias = diff.mean()
sd = diff.std(ddof=1)

plt.figure(figsize=(9, 5))
plt.scatter(mean_bp, diff, alpha=.45)
plt.axhline(bias, color="black", label=f"Viés = {bias:.1f}")
plt.axhline(bias + 1.96*sd, color="red", linestyle="--", label=f"LS = {bias+1.96*sd:.1f}")
plt.axhline(bias - 1.96*sd, color="red", linestyle="--", label=f"LI = {bias-1.96*sd:.1f}")
plt.xlabel("Média entre NIBP_MBP e ART_MBP (mmHg)")
plt.ylabel("NIBP_MBP − ART_MBP (mmHg)")
plt.title("Bland–Altman exploratório — PAM")
plt.legend()
plt.show()
"""))

cells.append(nbf.v4.new_markdown_cell("## 5. Classificação exploratória de hipotensão"))

cells.append(nbf.v4.new_code_cell("""cm = confusion_matrix(paired["art_hypotension"], paired["nibp_hypotension"], labels=[False, True])
tn, fp, fn, tp = cm.ravel()
safe = lambda a, b: a / b if b else np.nan
classification = pd.Series({
    "sensibilidade": safe(tp, tp+fn),
    "especificidade": safe(tn, tn+fp),
    "VPP": safe(tp, tp+fp),
    "VPN": safe(tn, tn+fn),
    "prevalencia_ART": paired["art_hypotension"].mean(),
}).round(3)
display(pd.DataFrame(cm, index=["ART não", "ART sim"], columns=["NIBP não", "NIBP sim"]))
display(classification.to_frame("valor"))
"""))

cells.append(nbf.v4.new_markdown_cell("""## 6. ML exploratório: fatores associados ao erro

O alvo é `NIBP_MBP − ART_MBP`. O particionamento é feito por `caseid`, evitando que medidas do mesmo paciente apareçam simultaneamente em treino e teste. Com apenas oito casos, o resultado serve para demonstrar o pipeline, não para conclusão clínica.
"""))

cells.append(nbf.v4.new_code_cell("""candidate_features = ["NIBP_MBP", "HR", "age", "weight", "height", "bmi", "time_min", "sex"]
features = [c for c in candidate_features if c in paired.columns]
model_df = paired[features + ["error_MBP", "caseid"]].copy()

numeric = [c for c in features if c != "sex"]
categorical = [c for c in features if c == "sex"]
pre = ColumnTransformer([
    ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
    ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                      ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
])
model = Pipeline([
    ("pre", pre),
    ("rf", RandomForestRegressor(n_estimators=300, min_samples_leaf=5,
                                  random_state=SEED, n_jobs=-1)),
])

splitter = GroupShuffleSplit(n_splits=1, test_size=.25, random_state=SEED)
train_idx, test_idx = next(splitter.split(model_df, groups=model_df["caseid"]))
train, test = model_df.iloc[train_idx], model_df.iloc[test_idx]
model.fit(train[features], train["error_MBP"])
pred = model.predict(test[features])
baseline = np.repeat(train["error_MBP"].mean(), len(test))

result = pd.DataFrame({
    "modelo": ["baseline_média", "random_forest"],
    "MAE": [mean_absolute_error(test.error_MBP, baseline), mean_absolute_error(test.error_MBP, pred)],
    "RMSE": [mean_squared_error(test.error_MBP, baseline)**.5, mean_squared_error(test.error_MBP, pred)**.5],
}).round(2)
display(result)
print("Casos treino:", train.caseid.nunique(), "| Casos teste:", test.caseid.nunique())
"""))

cells.append(nbf.v4.new_markdown_cell("""## 7. Conclusões e checklist de interpretação

Após executar, descreva: (1) cobertura e número de casos/pares; (2) viés, dispersão, MAE e limites de concordância; (3) desempenho na identificação de PAM < 65 mmHg; (4) heterogeneidade por sexo, idade, IMC e tempo; (5) desempenho do modelo apenas como exploração.

Não conclua que o equipamento é “aprovado” ou “reprovado”. Os dados são observacionais, NIBP e ART têm fontes de erro diferentes e faltam elementos do protocolo normativo. Uma ampliação adequada deve incluir mais casos, análise de sensibilidade da janela temporal, intervalos de confiança por bootstrap agrupado por paciente e validação externa.
"""))

nb["cells"] = cells
nbf.write(nb, OUT)
print(OUT)

