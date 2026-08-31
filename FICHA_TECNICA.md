# Ficha técnica do dataset — VitalDB v1.0.0

## 1. Nome e fonte

**Nome oficial:** *VitalDB, a high-fidelity multi-parameter vital signs database in surgical patients*, versão 1.0.0.  
**Provedor selecionado:** PhysioNet.  
**URL:** https://physionet.org/content/vitaldb/1.0.0/  
**DOI da versão:** https://doi.org/10.13026/czw8-9p62  
**Publicação:** Lee HC et al. *Scientific Data* 9, 279 (2022). https://doi.org/10.1038/s41597-022-01411-5

O conjunto contém sinais intraoperatórios sincronizados e informações clínicas de pacientes submetidos a cirurgias não cardíacas no Seoul National University Hospital, República da Coreia.

## 2. Licença e acesso

A distribuição **VitalDB v1.0.0 hospedada no PhysioNet** declara licença **Creative Commons Attribution 4.0 International (CC BY 4.0)**. É permitido compartilhar e adaptar, inclusive comercialmente, desde que seja fornecida atribuição apropriada, indicação da licença e das alterações realizadas.

Há uma divergência que deve ser documentada: o site próprio VitalDB exibe termos CC BY-NC-SA 4.0 e um acordo adicional, enquanto a versão escolhida no PhysioNet declara CC BY 4.0. Para tornar a proveniência inequívoca, este projeto referencia e baixa a versão do PhysioNet. Em eventual redistribuição fora do trabalho acadêmico, recomenda-se confirmar os termos vigentes com o provedor.

O acesso no PhysioNet é aberto, sem credenciamento, condicionado ao cumprimento da licença.

## 3. Tamanho e estrutura

- 6.388 casos cirúrgicos.
- 557.622 trilhas segundo a página do projeto VitalDB; a descrição da versão PhysioNet informa 486.451 trilhas de forma de onda e numéricas. A diferença provavelmente decorre de critérios/versões de contagem e deve ser reportada, não ocultada.
- 196 parâmetros de monitorização intraoperatória, 73 parâmetros clínicos perioperatórios e 34 parâmetros laboratoriais seriados.
- Tamanho descompactado da versão PhysioNet: **95,4 GB**; arquivo ZIP: **94,2 GB**.
- Formatos principais: arquivos binários `.vital`, CSV para metadados e tabelas clínicas; acesso também por API/biblioteca Python.
- Resolução: formas de onda de até 500 Hz; valores numéricos tipicamente a cada 1–7 segundos.

## 4. Variáveis principais

| Variável | Papel | Tipo/formato | Unidade/faixa operacional usada na EDA |
|---|---|---|---|
| `caseid` | identificador anonimizado do caso | inteiro/categórico | 1–6.388 |
| `sex` | entrada/estratificação | categórica | M/F |
| `age` | entrada/estratificação | numérica | anos; validar valores observados |
| `height` | entrada | numérica | cm |
| `weight` | entrada | numérica | kg |
| IMC derivado | entrada | numérica | kg/m² |
| tempo relativo | entrada/pareamento | numérica | segundos desde o início do caso |
| `Solar8000/NIBP_SBP` | medida em avaliação | numérica seriada | mmHg; filtro exploratório 40–260 |
| `Solar8000/NIBP_MBP` | medida em avaliação | numérica seriada | mmHg; filtro exploratório 25–200 |
| `Solar8000/NIBP_DBP` | medida em avaliação | numérica seriada | mmHg; filtro exploratório 20–160 |
| `Solar8000/ART_SBP` | referência | numérica seriada | mmHg; filtro exploratório 40–260 |
| `Solar8000/ART_MBP` | referência/alvo principal | numérica seriada | mmHg; filtro exploratório 25–200 |
| `Solar8000/ART_DBP` | referência | numérica seriada | mmHg; filtro exploratório 20–160 |
| `Solar8000/HR` | entrada contextual | numérica seriada | batimentos/min; filtro 20–220 |

As faixas acima são regras de plausibilidade adotadas para a EDA, e não limites oficiais do equipamento. Valores ausentes são esperados. A documentação não oferece, para cada medida, tamanho do manguito, braço utilizado ou estado do posicionamento.

## 5. Privacidade

Os dados foram anonimizados, datas absolutas foram removidas e os tempos são relativos ao início do caso. Identificadores diretos e informações protegidas foram retirados. O risco não é zero: combinações raras de idade, sexo, medidas corporais, procedimento e trajetória fisiológica podem funcionar como quase-identificadores, especialmente quando ligadas a fontes externas.

Medidas de mitigação:

- não tentar reidentificar participantes;
- não publicar linhas individuais com combinações raras;
- divulgar apenas estatísticas agregadas;
- manter o `caseid` fora de tabelas e figuras públicas sempre que não for necessário;
- limitar a amostra redistribuída ao mínimo e preservar os termos da fonte.

Classificação qualitativa do risco residual: **baixo a moderado**, devido à anonimização, mas com dados clínicos granulares e séries temporais extensas.

## 6. Uso clínico e aprendizado de máquina

**Equipamento/função:** módulo de NIBP do monitor GE Solar 8000M; medição automática por método oscilométrico no ambiente intraoperatório.

**Aplicação potencial:** quantificar o erro e a concordância da medida oscilométrica em relação à pressão arterial invasiva sincronizada, identificar subgrupos/condições de maior discordância e explorar correção algorítmica do erro.

**Pergunta principal:** qual é a concordância entre NIBP e ART pareadas temporalmente?

**Pergunta secundária de classificação:** usando ART como referência retrospectiva, qual é a concordância da NIBP para identificar PAM < 65 mmHg?

**Entradas propostas:** NIBP sistólica/média/diastólica, sexo, idade, peso, altura, IMC, frequência cardíaca, tempo relativo no procedimento e, se disponíveis, contexto anestésico e uso de vasopressores. “Horário” deve ser entendido como tempo relativo intraoperatório; o horário civil foi removido por anonimização.

**Alvos/rótulos:**

1. regressão: erro `NIBP_MBP − ART_MBP` ou diretamente `ART_MBP`;
2. classificação: hipotensão de referência `ART_MBP < 65 mmHg`;
3. desfecho de discordância: `abs(NIBP_MBP − ART_MBP) > 10 mmHg` (limiar exploratório, não regulatório).

**Métodos já relatados para dados de pressão/sinais fisiológicos:** regressão linear e regularizada, random forest, gradient boosting/XGBoost, support vector regression, redes neurais multilayer perceptron, CNN 1D, LSTM/GRU e arquiteturas Transformer. Para este trabalho introdutório, recomenda-se um modelo linear como baseline e Random Forest/Gradient Boosting como comparação, com separação de treino e teste **por paciente/caso**, nunca por linha.

**Métricas:** viés médio, desvio-padrão das diferenças, MAE, RMSE e Bland–Altman para concordância; sensibilidade, especificidade, VPP, VPN, F1 e matriz de confusão para hipotensão. Correlação isolada não mede concordância e não deve ser a métrica principal.

## 7. Avaliação FAIR

Escala: 0 = não atende; 1 = atende pouco; 2 = atende parcialmente; 3 = atende bem; 4 = atende de forma excelente. Pontuação total: **14/16**.

| Princípio | Nota | Justificativa |
|---|---:|---|
| Findable | 4/4 | Nome oficial, página indexável, DOI persistente, versão explícita, citação recomendada e metadados no PhysioNet. |
| Accessible | 4/4 | Download aberto por HTTPS, ZIP, `wget` e S3, além de API/biblioteca Python; licença indicada. O volume de 95,4 GB é uma barreira prática, mas permite acesso seletivo. |
| Interoperable | 3/4 | Há CSV, biblioteca Python e nomes/unidades documentados. O formato `.vital` é especializado e parte da semântica depende de nomes de trilhas do fabricante, sem ontologias clínicas padronizadas como LOINC/SNOMED. |
| Reusable | 3/4 | Licença clara na versão selecionada, artigo de dados, proveniência, métodos e dicionários. Perde um ponto pela divergência de licenças entre os portais e pela ausência de metadados essenciais à validação formal do método oscilométrico. |

## 8. Limitações conhecidas

- Centro único e população majoritariamente/coreana, limitando validade externa.
- Apenas pacientes cirúrgicos; não representa atenção primária, domicílio ou população geral.
- Viés de seleção: ART só é utilizada em pacientes com indicação clínica, geralmente mais complexos.
- Dados coletados em 10 de 31 salas cirúrgicas e em período/contexto tecnológico específico.
- NIBP e ART não são necessariamente simultâneas; o pareamento temporal introduz erro quando a pressão varia rapidamente.
- ART não é padrão perfeito: nivelamento, zeragem, amortecimento da linha e artefatos podem produzir erro.
- Ausência de posição/tamanho do manguito, braço, postura e protocolo controlado.
- Medidas repetidas dentro do mesmo paciente não são independentes.
- Horários absolutos foram removidos; só é possível avaliar tempo relativo.
- Valores ausentes e frequências de amostragem diferentes.
- A comparação retrospectiva não equivale ao protocolo formal ISO 81060-2.
- Modelos podem aprender padrões próprios do hospital, monitor e processo anestésico, com baixa generalização.

## 9. Referências essenciais

1. Lee H, Jung CW. VitalDB v1.0.0. PhysioNet, 2022. https://doi.org/10.13026/czw8-9p62
2. Lee HC et al. VitalDB, a high-fidelity multi-parameter vital signs database in surgical patients. *Scientific Data*. 2022;9:279. https://doi.org/10.1038/s41597-022-01411-5
3. PhysioNet, página da versão e licença: https://physionet.org/content/vitaldb/1.0.0/
4. VitalDB, dicionário de parâmetros: https://vitaldb.net/dataset/

