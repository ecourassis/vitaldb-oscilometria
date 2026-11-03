# Dados incluídos

Os cinco arquivos Parquet em `input/` derivam do produto analítico validado nas Aulas 03 e 04. Eles permitem executar a atividade sem novo download do VitalDB.

- `fact_bp_measurement_valid.parquet`: aferições aprovadas nas regras de qualidade;
- `dim_patient.parquet`: dados demográficos anonimizados;
- `dim_time.parquet`: tempo relativo intraoperatório;
- `dim_label.parquet`: rótulos de hipotensão e concordância;
- `dim_case.parquet`: contexto do caso cirúrgico.

Fonte primária: VitalDB v1.0.0, https://physionet.org/content/vitaldb/1.0.0/.

A pressão arterial invasiva é usada somente como referência para interpretar a vizinhança. Ela não entra no texto enviado ao modelo de embeddings.
