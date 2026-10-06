# Resultados dos testes de qualidade

## 01_resumo_e_duplicatas

```sql
WITH distinct_rows AS (
    SELECT COUNT(*) AS n FROM (SELECT DISTINCT * FROM fact_bp_measurement)
)
SELECT
    COUNT(*) AS total_registros,
    COUNT(*) - (SELECT n FROM distinct_rows) AS duplicatas_completas,
    COUNT(*) - COUNT(DISTINCT measurement_id) AS ids_duplicados,
    COUNT(*) - COUNT(DISTINCT (case_key, time_key, nibp_mbp_mmhg)) AS duplicatas_no_grao,
    COUNT(DISTINCT case_key) AS casos,
    COUNT(DISTINCT patient_key) AS pacientes
FROM fact_bp_measurement
```

|   total_registros |   duplicatas_completas |   ids_duplicados |   duplicatas_no_grao |   casos |   pacientes |
|------------------:|-----------------------:|-----------------:|---------------------:|--------:|------------:|
|                30 |                      0 |                0 |                    0 |       7 |           7 |

## 02_completude_por_campo

```sql
WITH metricas AS (
    SELECT 'fact_bp_measurement' tabela, 'measurement_id' campo, COUNT(*) total, COUNT(measurement_id) preenchidos FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','patient_key',COUNT(*),COUNT(patient_key) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','case_key',COUNT(*),COUNT(case_key) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','time_key',COUNT(*),COUNT(time_key) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','label_key',COUNT(*),COUNT(label_key) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','nibp_sbp_mmhg',COUNT(*),COUNT(nibp_sbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','nibp_mbp_mmhg',COUNT(*),COUNT(nibp_mbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','nibp_dbp_mmhg',COUNT(*),COUNT(nibp_dbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','art_sbp_mmhg',COUNT(*),COUNT(art_sbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','art_mbp_mmhg',COUNT(*),COUNT(art_mbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','art_dbp_mmhg',COUNT(*),COUNT(art_dbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','heart_rate_bpm',COUNT(*),COUNT(heart_rate_bpm) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','pair_delta_seconds',COUNT(*),COUNT(pair_delta_seconds) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','error_sbp_mmhg',COUNT(*),COUNT(error_sbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','error_mbp_mmhg',COUNT(*),COUNT(error_mbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'fact_bp_measurement','error_dbp_mmhg',COUNT(*),COUNT(error_dbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'dim_patient','sex',COUNT(*),COUNT(sex) FROM dim_patient
    UNION ALL SELECT 'dim_patient','age_years',COUNT(*),COUNT(age_years) FROM dim_patient
    UNION ALL SELECT 'dim_patient','height_cm',COUNT(*),COUNT(height_cm) FROM dim_patient
    UNION ALL SELECT 'dim_patient','weight_kg',COUNT(*),COUNT(weight_kg) FROM dim_patient
    UNION ALL SELECT 'dim_patient','bmi_kg_m2',COUNT(*),COUNT(bmi_kg_m2) FROM dim_patient
    UNION ALL SELECT 'dim_case','department',COUNT(*),COUNT(department) FROM dim_case
    UNION ALL SELECT 'dim_case','operation_type',COUNT(*),COUNT(operation_type) FROM dim_case
    UNION ALL SELECT 'dim_case','approach',COUNT(*),COUNT(approach) FROM dim_case
    UNION ALL SELECT 'dim_case','position',COUNT(*),COUNT(position) FROM dim_case
    UNION ALL SELECT 'dim_case','anesthesia_type',COUNT(*),COUNT(anesthesia_type) FROM dim_case
    UNION ALL SELECT 'dim_case','asa_class',COUNT(*),COUNT(asa_class) FROM dim_case
    UNION ALL SELECT 'dim_case','emergency_operation',COUNT(*),COUNT(emergency_operation) FROM dim_case
)
SELECT tabela, campo, total, total - preenchidos AS nulos,
       ROUND(100.0 * preenchidos / NULLIF(total, 0), 2) AS completude_pct
FROM metricas
ORDER BY tabela, campo
```

| tabela              | campo               |   total |   nulos |   completude_pct |
|:--------------------|:--------------------|--------:|--------:|-----------------:|
| dim_case            | anesthesia_type     |       7 |       0 |           100    |
| dim_case            | approach            |       7 |       0 |           100    |
| dim_case            | asa_class           |       7 |       0 |           100    |
| dim_case            | department          |       7 |       0 |           100    |
| dim_case            | emergency_operation |       7 |       0 |           100    |
| dim_case            | operation_type      |       7 |       0 |           100    |
| dim_case            | position            |       7 |       0 |           100    |
| dim_patient         | age_years           |       7 |       0 |           100    |
| dim_patient         | bmi_kg_m2           |       7 |       0 |           100    |
| dim_patient         | height_cm           |       7 |       0 |           100    |
| dim_patient         | sex                 |       7 |       0 |           100    |
| dim_patient         | weight_kg           |       7 |       0 |           100    |
| fact_bp_measurement | art_dbp_mmhg        |      30 |       1 |            96.67 |
| fact_bp_measurement | art_mbp_mmhg        |      30 |       0 |           100    |
| fact_bp_measurement | art_sbp_mmhg        |      30 |       1 |            96.67 |
| fact_bp_measurement | case_key            |      30 |       0 |           100    |
| fact_bp_measurement | error_dbp_mmhg      |      30 |       1 |            96.67 |
| fact_bp_measurement | error_mbp_mmhg      |      30 |       0 |           100    |
| fact_bp_measurement | error_sbp_mmhg      |      30 |       1 |            96.67 |
| fact_bp_measurement | heart_rate_bpm      |      30 |       0 |           100    |
| fact_bp_measurement | label_key           |      30 |       0 |           100    |
| fact_bp_measurement | measurement_id      |      30 |       0 |           100    |
| fact_bp_measurement | nibp_dbp_mmhg       |      30 |       0 |           100    |
| fact_bp_measurement | nibp_mbp_mmhg       |      30 |       0 |           100    |
| fact_bp_measurement | nibp_sbp_mmhg       |      30 |       0 |           100    |
| fact_bp_measurement | pair_delta_seconds  |      30 |       0 |           100    |
| fact_bp_measurement | patient_key         |      30 |       0 |           100    |
| fact_bp_measurement | time_key            |      30 |       0 |           100    |

## 03_valores_invalidos_e_consistencia

```sql
SELECT * FROM (
    SELECT 'NIBP_SBP fora de 40-260 mmHg' teste, COUNT(*) FILTER (WHERE nibp_sbp_mmhg NOT BETWEEN 40 AND 260) ocorrencias FROM fact_bp_measurement
    UNION ALL SELECT 'NIBP_MBP fora de 25-200 mmHg', COUNT(*) FILTER (WHERE nibp_mbp_mmhg NOT BETWEEN 25 AND 200) FROM fact_bp_measurement
    UNION ALL SELECT 'NIBP_DBP fora de 20-160 mmHg', COUNT(*) FILTER (WHERE nibp_dbp_mmhg NOT BETWEEN 20 AND 160) FROM fact_bp_measurement
    UNION ALL SELECT 'ART_SBP fora de 40-260 mmHg', COUNT(*) FILTER (WHERE art_sbp_mmhg NOT BETWEEN 40 AND 260) FROM fact_bp_measurement
    UNION ALL SELECT 'ART_MBP fora de 25-200 mmHg', COUNT(*) FILTER (WHERE art_mbp_mmhg NOT BETWEEN 25 AND 200) FROM fact_bp_measurement
    UNION ALL SELECT 'ART_DBP fora de 20-160 mmHg', COUNT(*) FILTER (WHERE art_dbp_mmhg NOT BETWEEN 20 AND 160) FROM fact_bp_measurement
    UNION ALL SELECT 'Frequencia cardiaca fora de 20-220 bpm', COUNT(*) FILTER (WHERE heart_rate_bpm NOT BETWEEN 20 AND 220) FROM fact_bp_measurement
    UNION ALL SELECT 'Pareamento temporal fora de 0-30 s', COUNT(*) FILTER (WHERE pair_delta_seconds NOT BETWEEN 0 AND 30) FROM fact_bp_measurement
    UNION ALL SELECT 'Ordem NIBP inconsistente (SBP >= MBP >= DBP)', COUNT(*) FILTER (WHERE nibp_sbp_mmhg < nibp_mbp_mmhg OR nibp_mbp_mmhg < nibp_dbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'Ordem ART inconsistente (SBP >= MBP >= DBP)', COUNT(*) FILTER (WHERE art_sbp_mmhg < art_mbp_mmhg OR art_mbp_mmhg < art_dbp_mmhg) FROM fact_bp_measurement
    UNION ALL SELECT 'Erro MBP inconsistente com NIBP - ART', COUNT(*) FILTER (WHERE ABS(error_mbp_mmhg - (nibp_mbp_mmhg - art_mbp_mmhg)) > 0.001) FROM fact_bp_measurement
    UNION ALL SELECT 'Rotulo ART de hipotensao inconsistente', COUNT(*) FILTER (WHERE (f.art_mbp_mmhg < 65) <> l.art_hypotension) FROM fact_bp_measurement f JOIN dim_label l USING (label_key)
    UNION ALL SELECT 'Rotulo NIBP de hipotensao inconsistente', COUNT(*) FILTER (WHERE (f.nibp_mbp_mmhg < 65) <> l.nibp_hypotension) FROM fact_bp_measurement f JOIN dim_label l USING (label_key)
    UNION ALL SELECT 'Classe de concordancia inconsistente', COUNT(*) FILTER (WHERE ((f.art_mbp_mmhg < 65) = (f.nibp_mbp_mmhg < 65)) <> (l.agreement_class = 'concordant')) FROM fact_bp_measurement f JOIN dim_label l USING (label_key)
    UNION ALL SELECT 'Sentinelas/strings vazias em chaves', COUNT(*) FILTER (WHERE TRIM(COALESCE(measurement_id,'')) IN ('','-1','999') OR TRIM(COALESCE(patient_key,'')) IN ('','-1','999') OR TRIM(COALESCE(case_key,'')) IN ('','-1','999') OR TRIM(COALESCE(label_key,'')) IN ('','-1','999')) FROM fact_bp_measurement
    UNION ALL SELECT 'Sexo fora do dominio F/M', COUNT(*) FILTER (WHERE sex NOT IN ('F','M')) FROM dim_patient
    UNION ALL SELECT 'Idade fora de 0-120 anos', COUNT(*) FILTER (WHERE age_years NOT BETWEEN 0 AND 120) FROM dim_patient
    UNION ALL SELECT 'Altura fora de 80-230 cm', COUNT(*) FILTER (WHERE height_cm NOT BETWEEN 80 AND 230) FROM dim_patient
    UNION ALL SELECT 'Peso fora de 2-350 kg', COUNT(*) FILTER (WHERE weight_kg NOT BETWEEN 2 AND 350) FROM dim_patient
    UNION ALL SELECT 'IMC fora de 8-80 kg/m2', COUNT(*) FILTER (WHERE bmi_kg_m2 NOT BETWEEN 8 AND 80) FROM dim_patient
) ORDER BY teste
```

| teste                                        |   ocorrencias |
|:---------------------------------------------|--------------:|
| ART_DBP fora de 20-160 mmHg                  |             0 |
| ART_MBP fora de 25-200 mmHg                  |             0 |
| ART_SBP fora de 40-260 mmHg                  |             0 |
| Altura fora de 80-230 cm                     |             0 |
| Classe de concordancia inconsistente         |             0 |
| Erro MBP inconsistente com NIBP - ART        |             0 |
| Frequencia cardiaca fora de 20-220 bpm       |             0 |
| IMC fora de 8-80 kg/m2                       |             0 |
| Idade fora de 0-120 anos                     |             0 |
| NIBP_DBP fora de 20-160 mmHg                 |             0 |
| NIBP_MBP fora de 25-200 mmHg                 |             0 |
| NIBP_SBP fora de 40-260 mmHg                 |             0 |
| Ordem ART inconsistente (SBP >= MBP >= DBP)  |             0 |
| Ordem NIBP inconsistente (SBP >= MBP >= DBP) |             0 |
| Pareamento temporal fora de 0-30 s           |             0 |
| Peso fora de 2-350 kg                        |             0 |
| Rotulo ART de hipotensao inconsistente       |             0 |
| Rotulo NIBP de hipotensao inconsistente      |             0 |
| Sentinelas/strings vazias em chaves          |             0 |
| Sexo fora do dominio F/M                     |             0 |

## 04_integridade_dimensional

```sql
SELECT
    COUNT(*) FILTER (WHERE p.patient_key IS NULL) AS fk_paciente_sem_correspondencia,
    COUNT(*) FILTER (WHERE c.case_key IS NULL) AS fk_caso_sem_correspondencia,
    COUNT(*) FILTER (WHERE t.time_key IS NULL) AS fk_tempo_sem_correspondencia,
    COUNT(*) FILTER (WHERE l.label_key IS NULL) AS fk_rotulo_sem_correspondencia,
    (SELECT COUNT(*) - COUNT(DISTINCT patient_key) FROM dim_patient) AS pk_paciente_duplicada,
    (SELECT COUNT(*) - COUNT(DISTINCT case_key) FROM dim_case) AS pk_caso_duplicada,
    (SELECT COUNT(*) - COUNT(DISTINCT time_key) FROM dim_time) AS pk_tempo_duplicada,
    (SELECT COUNT(*) - COUNT(DISTINCT label_key) FROM dim_label) AS pk_rotulo_duplicada
FROM fact_bp_measurement f
LEFT JOIN dim_patient p USING (patient_key)
LEFT JOIN dim_case c USING (case_key)
LEFT JOIN dim_time t USING (time_key)
LEFT JOIN dim_label l USING (label_key)
```

|   fk_paciente_sem_correspondencia |   fk_caso_sem_correspondencia |   fk_tempo_sem_correspondencia |   fk_rotulo_sem_correspondencia |   pk_paciente_duplicada |   pk_caso_duplicada |   pk_tempo_duplicada |   pk_rotulo_duplicada |
|----------------------------------:|------------------------------:|-------------------------------:|--------------------------------:|------------------------:|--------------------:|---------------------:|----------------------:|
|                                 0 |                             0 |                              0 |                               0 |                       0 |                   0 |                    0 |                     0 |

## 05_nulos_detalhados_para_decisao

```sql
SELECT
    measurement_id, case_key, time_key,
    art_sbp_mmhg, art_mbp_mmhg, art_dbp_mmhg,
    error_sbp_mmhg, error_mbp_mmhg, error_dbp_mmhg,
    CASE
        WHEN art_mbp_mmhg IS NULL OR nibp_mbp_mmhg IS NULL THEN 'quarentena: medida central obrigatoria ausente'
        WHEN art_sbp_mmhg IS NULL OR art_dbp_mmhg IS NULL THEN 'manter: PAM valida; pressao lateral opcional ausente'
        ELSE 'valido'
    END AS decisao
FROM fact_bp_measurement
WHERE art_sbp_mmhg IS NULL OR art_dbp_mmhg IS NULL
   OR nibp_sbp_mmhg IS NULL OR nibp_dbp_mmhg IS NULL
   OR art_mbp_mmhg IS NULL OR nibp_mbp_mmhg IS NULL
ORDER BY measurement_id
```

| measurement_id   | case_key   |   time_key |   art_sbp_mmhg |   art_mbp_mmhg |   art_dbp_mmhg |   error_sbp_mmhg |   error_mbp_mmhg |   error_dbp_mmhg | decisao                                              |
|:-----------------|:-----------|-----------:|---------------:|---------------:|---------------:|-----------------:|-----------------:|-----------------:|:-----------------------------------------------------|
| M-5502-00029     | CASE-05502 |       6569 |            nan |             28 |            nan |              nan |               75 |              nan | manter: PAM valida; pressao lateral opcional ausente |

## Camadas produzidas

- Silver válida: **30 registros**.
- Silver em quarentena: **0 registros**.
- Gold: métricas de completude e de valores inválidos em Parquet.
