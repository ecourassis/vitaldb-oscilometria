# Dados incluídos

Os cinco arquivos Parquet em `input/` derivam do produto analítico validado na Aula 03 e permitem executar esta entrega sem novo download.

- `fact_bp_measurement_valid.parquet`: aferições consideradas válidas pelas regras da Aula 03;
- `dim_patient.parquet`: dados demográficos anonimizados;
- `dim_case.parquet`: contexto do caso cirúrgico;
- `dim_time.parquet`: tempo relativo e fase intraoperatória;
- `dim_label.parquet`: rótulos de hipotensão e concordância.

Fonte primária: VitalDB v1.0.0, https://physionet.org/content/vitaldb/1.0.0/.
