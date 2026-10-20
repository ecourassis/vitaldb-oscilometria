# Ficha do modelo — `rf_art_mbp_v1.0`

## Finalidade

Regressão exploratória da pressão arterial média invasiva (`ART_MBP`) a partir de pressões não invasivas, frequência cardíaca, dados demográficos e tempo relativo intraoperatório.

## Algoritmo

`RandomForestRegressor`, baseado em Breiman (2001), com 300 árvores, `min_samples_leaf=2`, `random_state=42` e execução em um núcleo para favorecer reprodutibilidade.

## Entradas

`nibp_sbp_mmhg`, `nibp_mbp_mmhg`, `nibp_dbp_mmhg`, `heart_rate_bpm`, `age_years`, `height_cm`, `weight_kg`, `bmi_kg_m2`, `time_minutes` e `sex`.

## Alvo

`art_mbp_mmhg`, em mmHg.

## Avaliação

Predições fora do paciente obtidas com `LeaveOneGroupOut`: em cada rodada, todas as aferições de um paciente são reservadas para teste e os demais pacientes formam o treino. Hiperparâmetros foram definidos previamente; não houve ajuste orientado pelo teste.

## Uso pretendido

Demonstração acadêmica de um pipeline reprodutível de aprendizado de máquina e avaliação. Não é dispositivo médico, não substitui monitorização invasiva e não deve orientar decisões clínicas.

## Limitações centrais

Amostra de somente 30 aferições e 7 pacientes, população cirúrgica, dependência entre medidas do mesmo paciente e apenas dois pacientes com episódios de hipotensão de referência. Os intervalos de confiança devem ser interpretados como exploratórios.
