# Camadas de dados

- `bronze/`: Parquets originais da Aula 02, preservados sem alteração.
- `silver/`: fato validada e registros em quarentena, recriados pelo script.
- `gold/`: métricas de qualidade em formato Parquet, recriadas pelo script.

Os arquivos Silver e Gold podem ser apagados e reproduzidos com:

```bash
python src/run_quality_checks.py
```
