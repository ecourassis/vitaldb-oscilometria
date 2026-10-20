# Aula 04 — Fundamentos de Aprendizado de Máquina, Redes Neurais e Avaliação

Aplicação reprodutível de aprendizado de máquina ao mesmo recorte do **VitalDB v1.0.0** utilizado nas Aulas 01–03. O projeto treina e avalia um modelo de regressão para estimar a pressão arterial média invasiva (`ART_MBP`) e registra predições fora do paciente, métricas com intervalo de confiança, análise de erros e limitações.

## Pergunta e tarefa

**Pergunta exploratória:** medidas não invasivas, frequência cardíaca, características do paciente e tempo intraoperatório permitem estimar a pressão arterial média invasiva de referência?

- Tipo de tarefa: regressão supervisionada.
- Alvo: `art_mbp_mmhg`.
- Unidade do alvo: mmHg.
- Unidade de análise: uma aferição NIBP pareada temporalmente à observação ART mais próxima no mesmo caso.
- Análise secundária: hipotensão definida como `ART_MBP < 65 mmHg`.

## Dados

- Dataset: *VitalDB, a high-fidelity multi-parameter vital signs database in surgical patients*, v1.0.0.
- PhysioNet: https://physionet.org/content/vitaldb/1.0.0/
- DOI: https://doi.org/10.13026/czw8-9p62
- API utilizada na ingestão da Aula 02: https://api.vitaldb.net/

Os cinco Parquets em `data/input/` derivam do produto analítico validado na Aula 03 e acompanham esta entrega. Assim, a execução não depende de download manual nem de conexão com a API.

O recorte contém **30 aferições de 7 pacientes/casos**. Há **6 aferições com ART_MBP abaixo de 65 mmHg**, concentradas em somente dois pacientes.

## Modelo da literatura

Foi escolhido o `RandomForestRegressor`, implementação do algoritmo Random Forest descrito por:

> BREIMAN, Leo. Random Forests. *Machine Learning*, v. 45, p. 5–32, 2001. DOI: https://doi.org/10.1023/A:1010933404324.

Implementação: scikit-learn 1.5.2. Documentação: https://scikit-learn.org/1.5/modules/generated/sklearn.ensemble.RandomForestRegressor.html.

Versão atribuída ao modelo deste projeto: **`rf_art_mbp_v1.0`**.

Configuração fixa, sem busca de hiperparâmetros:

- 300 árvores;
- `min_samples_leaf=2`;
- `random_state=42`;
- `n_jobs=1`.

Os parâmetros foram fixados antes da avaliação. Não houve seleção do modelo com base nos pacientes de teste.

## Entradas e alvo

| Papel | Variáveis |
|---|---|
| Pressão não invasiva | `nibp_sbp_mmhg`, `nibp_mbp_mmhg`, `nibp_dbp_mmhg` |
| Sinal fisiológico | `heart_rate_bpm` |
| Paciente | `age_years`, `sex`, `height_cm`, `weight_kg`, `bmi_kg_m2` |
| Tempo | `time_minutes` |
| Alvo | `art_mbp_mmhg` |

Valores numéricos ausentes são imputados pela mediana calculada exclusivamente no conjunto de treino de cada fold. A variável categórica `sex` é imputada pela moda e codificada por *one-hot encoding*, também dentro do pipeline de treino.

## Prevenção de vazamento

Foi usada validação **Leave-One-Patient-Out**, implementada com `LeaveOneGroupOut` e agrupamento por `patient_id`:

1. um paciente inteiro é reservado como teste;
2. o modelo é treinado nos outros seis pacientes;
3. as aferições do paciente reservado recebem predições;
4. o processo é repetido para todos os sete pacientes.

Desse modo, cada uma das 30 predições foi produzida por um modelo que não teve acesso a nenhuma aferição daquele paciente. O script verifica programaticamente a ausência de sobreposição entre pacientes de treino e teste. Como não houve ajuste de hiperparâmetros, não foi necessário criar conjunto de validação separado; a avaliação final foi feita apenas com as predições dos pacientes deixados de fora.

Após a avaliação, um modelo final é ajustado com todas as aferições e salvo para permitir reprodução e aplicação futura. As métricas relatadas **não** são calculadas com as predições desse modelo final, mas somente com as predições fora do paciente.

## Execução reproduzível no macOS

Recomendação: Python 3.11 ou 3.12. No Terminal, a partir da pasta que contém o projeto:

```bash
cd aula04_machine_learning
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python src/train_and_evaluate.py
```

Se o comando disponível no computador for `python3`, ele pode substituir `python3.12` na criação do ambiente, desde que a versão seja 3.11 ou 3.12.

Saída esperada:

```text
Concluido: 30 predicoes fora do paciente; 7 pacientes.
MAE: 11.18 mmHg | RMSE: 17.19 mmHg
Relatorio: .../outputs/evaluation_report.md
```

## Arquivos de aplicação e resultados

| Arquivo | Conteúdo |
|---|---|
| `outputs/predictions_oof.csv` | Predições em CSV, com IDs da amostra, paciente e caso, fold e versão do modelo |
| `outputs/predictions_oof.parquet` | As mesmas predições em Parquet comprimido |
| `outputs/split_manifest.csv` | Paciente de teste e quantidades por fold; sobreposição igual a zero |
| `outputs/metrics.json` | Métricas pontuais e intervalos de confiança |
| `outputs/evaluation_report.md` | Relatório legível com métricas, matriz de confusão, erros e interpretação |
| `outputs/errors_by_patient.csv` | MAE e viés por paciente |
| `outputs/largest_errors.csv` | Cinco maiores erros absolutos |
| `models/rf_art_mbp_v1.0.joblib` | Pipeline final ajustado em todas as 30 aferições |

A tabela de predições contém `measurement_id`, `patient_id`, `case_id`, papel de avaliação, valor ART de referência, predição, erro, versão do modelo e versão do scikit-learn.

## Métricas e intervalos de confiança

Para regressão:

- erro absoluto médio (MAE);
- raiz do erro quadrático médio (RMSE);
- viés médio (`predição − referência`);
- R² como medida complementar.

Para a análise secundária de hipotensão:

- sensibilidade;
- especificidade;
- acurácia balanceada;
- F1;
- MCC;
- matriz de confusão.

Os intervalos de confiança de 95% foram obtidos por **bootstrap agrupado por paciente**, com 2.000 reamostragens. O paciente, e não a linha individual, é a unidade de reamostragem, preservando a dependência entre aferições do mesmo indivíduo.

## Resultados principais

### Random Forest — regressão

| Métrica | Estimativa | IC 95% |
|---|---:|---:|
| MAE | 11,18 mmHg | 7,24 a 18,42 |
| RMSE | 17,19 mmHg | 9,41 a 28,92 |
| Viés | 1,52 mmHg | −6,48 a 11,36 |
| R² | 0,46 | −0,66 a 0,78 |

Como comparação simples, usar diretamente `NIBP_MBP` para estimar `ART_MBP` produziu MAE de **8,03 mmHg** e RMSE de **15,56 mmHg**, desempenho melhor que o Random Forest neste pequeno recorte.

### Hipotensão derivada da predição

A prevalência observada foi de **20%** — 6 de 30 aferições. O modelo não produziu valores previstos abaixo de 65 mmHg:

- sensibilidade: 0,00;
- especificidade: 1,00;
- acurácia balanceada: 0,50;
- F1: 0,00;
- MCC: 0,00.

Portanto, a especificidade isoladamente alta não representa bom desempenho: ela decorre de o modelo classificar todas as aferições como ausência de hipotensão.

## Análise dos erros

O maior erro ocorreu no único registro do paciente `2440`: ART_MBP de 28 mmHg e predição de 98,70 mmHg, erro absoluto de 70,70 mmHg. Esse caso extremo não tinha exemplos semelhantes suficientes nos demais pacientes usados no treino do respectivo fold.

O comportamento observado é compatível com regressão em direção aos valores mais frequentes: o modelo representou razoavelmente pressões intermediárias, mas falhou nos extremos e não identificou hipotensão. O resultado reforça que maior complexidade não garante melhor desempenho quando a amostra é pequena, pouco diversa e desbalanceada.

## Limitações

- somente 30 aferições e 7 pacientes;
- episódios de hipotensão concentrados em dois pacientes;
- intervalos de confiança amplos e instáveis;
- pacientes cirúrgicos de uma única base;
- múltiplas aferições por paciente, embora tratadas por avaliação agrupada;
- ausência de validação externa;
- hiperparâmetros não otimizados devido ao tamanho da amostra;
- desempenho ruim nos extremos e sensibilidade nula para hipotensão;
- o modelo final salvo foi treinado com todos os dados e não possui estimativa independente adicional de desempenho.

Este trabalho demonstra o pipeline de aprendizado de máquina e sua avaliação. **Não constitui validação clínica de equipamento, não substitui a pressão invasiva e não deve orientar decisões assistenciais.**

## Estrutura do projeto

```text
aula04_machine_learning/
├── README.md
├── MODEL_CARD.md
├── requirements.txt
├── data/
│   ├── README.md
│   └── input/
│       ├── fact_bp_measurement_valid.parquet
│       ├── dim_patient.parquet
│       ├── dim_case.parquet
│       ├── dim_time.parquet
│       └── dim_label.parquet
├── models/
│   └── rf_art_mbp_v1.0.joblib
├── outputs/
│   ├── predictions_oof.csv
│   ├── predictions_oof.parquet
│   ├── split_manifest.csv
│   ├── metrics.json
│   ├── evaluation_report.md
│   ├── errors_by_patient.csv
│   └── largest_errors.csv
├── references/
│   └── references.md
└── src/
    └── train_and_evaluate.py
```

## Reprodução dos pesos

O arquivo `models/rf_art_mbp_v1.0.joblib` acompanha a entrega. Para reproduzi-lo, execute `python src/train_and_evaluate.py`; o script recria as predições, métricas, relatório e modelo final usando os Parquets incluídos e as dependências fixadas.
