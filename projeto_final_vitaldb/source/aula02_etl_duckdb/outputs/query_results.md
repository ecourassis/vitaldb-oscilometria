# Resultados reproduzíveis

## Consulta 1

```sql
-- Q1. Cobertura da tabela fato
SELECT
    COUNT(*) AS numero_medicoes,
    COUNT(DISTINCT case_key) AS numero_casos,
    COUNT(DISTINCT patient_key) AS numero_pacientes
FROM fact_bp_measurement
```

|   numero_medicoes |   numero_casos |   numero_pacientes |
|------------------:|---------------:|-------------------:|
|                30 |              7 |                  7 |

Tempo: 15.622 ms

## Consulta 2

```sql
-- Q2. Idade e erro da PAM por sexo
SELECT
    p.sex,
    COUNT(*) AS numero_medicoes,
    ROUND(AVG(p.age_years), 1) AS idade_media_anos,
    ROUND(AVG(f.error_mbp_mmhg), 2) AS vies_medio_mmhg,
    ROUND(AVG(ABS(f.error_mbp_mmhg)), 2) AS mae_mmhg
FROM fact_bp_measurement AS f
JOIN dim_patient AS p USING (patient_key)
GROUP BY p.sex
ORDER BY p.sex
```

| sex   |   numero_medicoes |   idade_media_anos |   vies_medio_mmhg |   mae_mmhg |
|:------|------------------:|-------------------:|------------------:|-----------:|
| F     |                10 |               56.5 |             -0.2  |      15.4  |
| M     |                20 |               55.4 |              0.05 |       4.35 |

Tempo: 5.654 ms

## Consulta 3

```sql
-- Q3. Concordância para hipotensão (ART_MBP < 65 mmHg)
SELECT
    l.art_hypotension,
    l.nibp_hypotension,
    COUNT(*) AS numero_medicoes
FROM fact_bp_measurement AS f
JOIN dim_label AS l USING (label_key)
GROUP BY l.art_hypotension, l.nibp_hypotension
ORDER BY l.art_hypotension, l.nibp_hypotension
```

| art_hypotension   | nibp_hypotension   |   numero_medicoes |
|:------------------|:-------------------|------------------:|
| False             | False              |                21 |
| False             | True               |                 3 |
| True              | False              |                 2 |
| True              | True               |                 4 |

Tempo: 10.554 ms

## CSV × Parquet

- CSV da fato: 3,537 bytes
- Parquet Zstandard: 11,056 bytes
- Redução: -212.58%
