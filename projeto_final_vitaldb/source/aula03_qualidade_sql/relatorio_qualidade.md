# Relatório de qualidade dos dados

## Escopo

Foram avaliados os cinco arquivos Parquet produzidos na Aula 02 a partir do VitalDB: uma tabela fato de aferições pareadas de pressão arterial e quatro dimensões — paciente, caso, tempo e rótulo. A análise foi realizada com SQL no DuckDB e pode ser reproduzida por `python src/run_quality_checks.py`.

## Síntese dos achados

- A tabela fato contém 30 aferições, provenientes de 7 casos e 7 pacientes.
- Não foram encontradas linhas completamente duplicadas, identificadores repetidos ou duplicatas no grão analítico.
- Todas as chaves da fato possuem correspondência nas dimensões, e as chaves dimensionais são únicas.
- Identificadores, medidas NIBP, ART média, frequência cardíaca, diferença temporal e erro da PAM apresentam 100% de completude.
- Um registro não possui ART sistólica nem diastólica. Consequentemente, os erros sistólico e diastólico derivados também são nulos. Esses quatro campos apresentam 96,67% de completude.
- Não foram encontradas sentinelas (`-1`, `999` ou texto vazio) nas chaves.
- Não foram encontrados valores fora das faixas operacionais, violações da ordem `SBP >= MBP >= DBP`, pareamentos acima de 30 segundos ou inconsistências nos rótulos de hipotensão.

## Decisões tomadas

| Situação | Decisão | Justificativa |
|---|---|---|
| ART sistólica e diastólica ausentes em `M-5502-00029` | Manter com ressalva | A ART média e a NIBP média estão presentes e válidas, permitindo responder à pergunta principal sobre PAM. |
| Erros sistólico e diastólico ausentes no mesmo registro | Manter como nulo verdadeiro | Os erros dependem das pressões ausentes; imputá-los criaria valores sem evidência observacional. |
| Violação crítica de chave, faixa, grão, coerência ou ausência de PAM | Quarentena | Registros assim poderiam comprometer junções e métricas. Nenhuma ocorrência foi encontrada. |
| Demais registros | Manter | Atenderam às regras declaradas de qualidade. |

O processamento resultou em 30 registros válidos e 0 registros em quarentena. Mesmo vazia, a saída de quarentena é criada para demonstrar e tornar reprodutível a política de tratamento.

## Limitações

- A amostra é pequena e não permite generalização clínica.
- Apenas 7 dos 8 casos previamente selecionados produziram aferições pareadas válidas; o caso 547 não entrou na fato final.
- As faixas fisiológicas são regras operacionais amplas de qualidade, não critérios diagnósticos ou validação de equipamento conforme ISO 81060-2.
- O banco representa pacientes cirúrgicos e pode conter viés de seleção.
- Não existem datas civis no recorte anonimizado; o tempo é relativo ao procedimento.
- Formas de onda brutas não fazem parte do produto tabular, impossibilitando auditoria morfológica dos sinais.

## Conclusão

O recorte apresenta boa qualidade estrutural e consistência interna para fins didáticos e analíticos. A única incompletude identificada afeta campos opcionais em um registro e foi preservada de forma transparente, sem imputação. A análise principal da pressão arterial média permanece possível, mas os resultados devem ser interpretados como demonstração de engenharia de dados, não como evidência clínica conclusiva.
