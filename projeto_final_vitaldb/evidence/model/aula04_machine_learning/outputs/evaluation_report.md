# Resultados — Aula 04

## Desenho da avaliação

- Modelo: `RandomForestRegressor`; versão `rf_art_mbp_v1.0`.
- Alvo: `ART_MBP` em mmHg.
- Avaliação: Leave-One-Patient-Out, com 7 folds.
- Amostras: 30; pacientes: 7.
- Vazamento entre pacientes de treino e teste: **não detectado**.
- Intervalos de confiança: bootstrap de 2.000 reamostragens por paciente.

## Regressão — Random Forest

| metrica   |   estimativa |   IC95_inferior |   IC95_superior |
|:----------|-------------:|----------------:|----------------:|
| mae_mmhg  |       11.176 |           7.239 |          18.423 |
| rmse_mmhg |       17.19  |           9.407 |          28.918 |
| bias_mmhg |        1.522 |          -6.478 |          11.362 |
| r2        |        0.464 |          -0.66  |           0.777 |

## Regressão — referência simples NIBP_MBP

| metrica   |   estimativa |   IC95_inferior |   IC95_superior |
|:----------|-------------:|----------------:|----------------:|
| mae_mmhg  |        8.033 |           4.079 |          16.913 |
| rmse_mmhg |       15.56  |           5.444 |          29.767 |
| bias_mmhg |       -0.033 |          -5.291 |           9.324 |
| r2        |        0.561 |          -0.641 |           0.942 |

## Hipotensão derivada da predição — ART_MBP < 65 mmHg

Prevalência de referência: 0.200 (6/30 aferições).

| metrica           |   estimativa |   IC95_inferior |   IC95_superior |
|:------------------|-------------:|----------------:|----------------:|
| sensitivity       |          0   |             0   |             0   |
| specificity       |          1   |             1   |             1   |
| balanced_accuracy |          0.5 |             0.5 |             0.5 |
| f1                |          0   |             0   |             0   |
| mcc               |          0   |             0   |             0   |

### Matriz de confusão do modelo

|         |   Predicao nao |   Predicao sim |
|:--------|---------------:|---------------:|
| ART nao |             24 |              0 |
| ART sim |              6 |              0 |

## Hipotensão pela referência simples NIBP_MBP < 65 mmHg

| metrica           |   estimativa |   IC95_inferior |   IC95_superior |
|:------------------|-------------:|----------------:|----------------:|
| sensitivity       |        0.667 |           0     |           0.8   |
| specificity       |        0.875 |           0.636 |           1     |
| balanced_accuracy |        0.771 |           0.345 |           0.9   |
| f1                |        0.615 |           0     |           0.889 |
| mcc               |        0.512 |          -0.167 |           0.878 |

## Erros por paciente

|   patient_id |   n |   mae_mmhg |   bias_mmhg |   reference_mean_mmhg |   predicted_mean_mmhg |
|-------------:|----:|-----------:|------------:|----------------------:|----------------------:|
|         2440 |   1 |      70.7  |       70.7  |                 28    |                 98.7  |
|         2166 |   7 |      12.58 |       12.58 |                 60    |                 72.58 |
|         1916 |   3 |      12.2  |      -12.2  |                119.33 |                107.13 |
|         5626 |   5 |      10.45 |       -8.93 |                 85.2  |                 76.27 |
|         5508 |   5 |       7.96 |       -0.75 |                103.4  |                102.65 |
|         2252 |   4 |       7.18 |       -7.18 |                 87.5  |                 80.32 |
|         3348 |   5 |       3.83 |        0.12 |                 74    |                 74.12 |

## Cinco maiores erros absolutos

| measurement_id   |   patient_id |   art_mbp_reference_mmhg |   art_mbp_predicted_mmhg |   prediction_error_mmhg |   absolute_error_mmhg |
|:-----------------|-------------:|-------------------------:|-------------------------:|------------------------:|----------------------:|
| M-5502-00029     |         2440 |                       28 |                    98.7  |                   70.7  |                 70.7  |
| M-2738-00007     |         2166 |                       44 |                    71    |                   27    |                 27    |
| M-4191-00016     |         5626 |                       98 |                    72.7  |                  -25.3  |                 25.3  |
| M-2769-00015     |         5508 |                      133 |                   111.48 |                  -21.52 |                 21.52 |
| M-4480-00022     |         1916 |                      125 |                   107.68 |                  -17.32 |                 17.32 |

## Interpretação e limitações

As predições são estritamente fora do paciente: nenhuma aferição do paciente avaliado apareceu no treino daquele fold. Isso reduz vazamento, mas não resolve a limitação de tamanho amostral. Há somente sete pacientes e os episódios de hipotensão concentram-se em dois deles, tornando as métricas classificatórias e seus intervalos instáveis. O modelo foi aplicado como demonstração acadêmica; não está validado para uso clínico, não estima causalidade e não substitui a pressão invasiva. O modelo final salvo foi reajustado com todas as 30 aferições apenas para permitir reprodução e uso futuro; suas métricas provêm exclusivamente das predições fora do paciente.
