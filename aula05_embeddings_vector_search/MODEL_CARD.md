# Ficha do modelo — `all-MiniLM-L6-v2@1110a243-onnx-int8`

## Finalidade neste projeto

Codificar descrições clínicas curtas de aferições do VitalDB em vetores de 384 dimensões para busca de vizinhos por similaridade de cosseno.

## Modelo

- Repositório: `sentence-transformers/all-MiniLM-L6-v2`;
- revisão: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`;
- arquivo: `onnx/model_quint8_avx2.onnx`;
- execução: ONNX Runtime em CPU;
- dimensão do embedding: 384;
- normalização: norma L2.

O modelo é um codificador de sentenças em inglês. As descrições foram construídas em inglês e com um molde fixo. Não houve fine-tuning com dados clínicos nem treinamento com os 30 registros.

## Conteúdo codificado

Sexo, idade, IMC, NIBP sistólica/média/diastólica, frequência cardíaca e tempo relativo desde o início do procedimento.

## Conteúdo excluído

ART, rótulo de hipotensão, identificadores e resultado do modelo da Aula 04. A exclusão evita inserir diretamente a referência clínica ou a identidade do paciente no texto.

## Uso pretendido

Demonstração acadêmica de embeddings, busca vetorial, visualização e auditoria de possível vazamento por paciente. Não é um modelo validado para semântica de valores numéricos clínicos e não deve apoiar decisões assistenciais.
