-- Q1. Cobertura da tabela fato
SELECT
    COUNT(*) AS numero_medicoes,
    COUNT(DISTINCT case_key) AS numero_casos,
    COUNT(DISTINCT patient_key) AS numero_pacientes
FROM fact_bp_measurement;

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
ORDER BY p.sex;

-- Q3. Concordância para hipotensão (ART_MBP < 65 mmHg)
SELECT
    l.art_hypotension,
    l.nibp_hypotension,
    COUNT(*) AS numero_medicoes
FROM fact_bp_measurement AS f
JOIN dim_label AS l USING (label_key)
GROUP BY l.art_hypotension, l.nibp_hypotension
ORDER BY l.art_hypotension, l.nibp_hypotension;

