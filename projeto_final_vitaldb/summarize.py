"""Consolida saídas realmente geradas na execução, com gráficos e exemplos."""
import json
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

run = Path(sys.argv[1])
ml = run/'aula04_machine_learning'/'outputs'
em = run/'aula05_embeddings_vector_search'/'outputs'
quality = run/'aula03_qualidade_sql'/'outputs'
p = pd.read_csv(ml/'predictions_oof.csv',dtype={'patient_id':str})
splits = pd.read_csv(ml/'split_manifest.csv',dtype={'test_patient_id':str})
assert p.measurement_id.is_unique and splits.patient_overlap.eq(0).all()
assert p.groupby('patient_id').fold_id.nunique().eq(1).all()
assert p.patient_id.nunique() == len(splits)
m = json.loads((ml/'metrics.json').read_text())
e = json.loads((em/'metrics.json').read_text())
q = json.loads((quality/'quality_results.json').read_text())['camadas'][0]
assert len(p) == q['silver_validos'] == e['n_samples']
assert p.patient_id.nunique() == e['n_patients']
out = run/'summary'; out.mkdir()
fig, ax = plt.subplots(figsize=(7,6))
x = p.art_mbp_reference_mmhg
for col,label in [('art_mbp_predicted_mmhg','Random Forest'),('baseline_nibp_mbp_mmhg','NIBP original')]:
    ax.scatter(x,p[col],label=label,alpha=.75)
lo,hi = min(x.min(),p.art_mbp_predicted_mmhg.min(),p.baseline_nibp_mbp_mmhg.min()),max(x.max(),p.art_mbp_predicted_mmhg.max(),p.baseline_nibp_mbp_mmhg.max())
ax.plot([lo,hi],[lo,hi],'k--',label='Identidade'); ax.set(xlabel='ART de referência (mmHg)',ylabel='Estimativa (mmHg)',title='Predições fora do paciente'); ax.legend(); fig.tight_layout(); fig.savefig(out/'predicoes.png',dpi=160); plt.close(fig)
fig,ax=plt.subplots(figsize=(6,5))
diff=p.baseline_nibp_mbp_mmhg-x; avg=(p.baseline_nibp_mbp_mmhg+x)/2
ax.scatter(avg,diff); bias=diff.mean(); sd=diff.std(ddof=1)
for val, style in [(bias,'-'),(bias+1.96*sd,'--'),(bias-1.96*sd,'--')]: ax.axhline(val,color='black',linestyle=style)
ax.set(xlabel='Média NIBP e ART (mmHg)',ylabel='NIBP − ART (mmHg)',title='Bland–Altman descritivo da amostra'); fig.tight_layout(); fig.savefig(out/'bland_altman.png',dpi=160); plt.close(fig)
rf=m['random_forest_regression']; base=m['nibp_direct_baseline_regression']; cl=m['random_forest_hypotension_threshold']['point']
rows=[]
for name,item in [('Random Forest',rf),('NIBP original',base)]:
    for metric in ['mae_mmhg','rmse_mmhg']:
        ci=item['cluster_bootstrap_95_ci'][metric]; rows.append([name,metric,item['point'][metric],ci['lower_95'],ci['upper_95']])
table=pd.DataFrame(rows,columns=['metodo','metrica','valor','IC95 inferior','IC95 superior'])
table.to_csv(out/'comparacao.csv',index=False)
examples=p.sort_values('absolute_error_mmhg'); cols=['measurement_id','art_mbp_reference_mmhg','art_mbp_predicted_mmhg','absolute_error_mmhg']; examples=pd.concat([examples.head(2),examples.tail(2)])[cols]
neighbors=pd.read_csv(em/'cross_patient_neighbors.csv'); contrast=neighbors.loc[~neighbors.same_hypotension_label].sort_values('cosine_similarity',ascending=False).head(3)
mode=json.loads((run/'run_manifest.json').read_text())
report=f'''# Síntese da execução

- Fonte: {mode['source_mode']}; embeddings: {mode['embedding_mode']} (archived = vetores históricos, não nova inferência).
- {len(p)} aferições válidas, {p.patient_id.nunique()} pacientes; {q['silver_quarentena']} em quarentena.
- Separação Leave-One-Patient-Out, {len(splits)} folds, sem sobreposição registrada.

## Avaliação do Random Forest (PAM invasiva como alvo)

{table.round(3).to_markdown(index=False)}

O limiar exploratório de hipotensão é ART < 65 mmHg. Matriz de confusão do Random Forest: VP={cl['tp']}, VN={cl['tn']}, FP={cl['fp']}, FN={cl['fn']}; sensibilidade={cl['sensitivity']:.1%}, especificidade={cl['specificity']:.1%}, acurácia balanceada={cl['balanced_accuracy']:.1%}. Não confundir acurácia simples com desempenho em classes raras.

Exemplos de menores e maiores erros absolutos:

{examples.round(2).to_markdown(index=False)}

![Predições](predicoes.png)

![Bland–Altman](bland_altman.png)

## Embeddings

- Top-1 mesmo paciente: {e['top1_same_patient_rate']:.1%}; acaso: {e['random_neighbor_same_patient_probability']:.1%}.
- Top-1 com mesmo rótulo: {e['top1_same_hypotension_label_rate']:.1%} (concordância descritiva, não diagnóstico).
- Textos duplicados: {e['exact_duplicate_text_rows']}; consultas com possível quase duplicata interpaciente: {e['cross_patient_top1_near_duplicate_queries']}.

Exemplos de vizinhos entre pacientes com rótulos divergentes:

{contrast[['query_measurement_id','neighbor_measurement_id','cosine_similarity','same_hypotension_label']].round(4).to_markdown(index=False)}

![PCA](../aula05_embeddings_vector_search/figures/embedding_pca_by_patient.png)

## Limitações

A amostra pequena e as medidas repetidas restringem inferência. O intervalo bootstrap por paciente é exploratório; Bland–Altman simples não ajusta a dependência intrapaciente. A ART pode ter artefatos; a associação temporal, o molde textual e a baixa sensibilidade do modelo limitam a interpretação. Similaridade textual não equivale a relevância fisiológica. Não há validação clínica ou regulatória do equipamento.
'''
(out/'RELATORIO_FINAL.md').write_text(report,encoding='utf-8')
print('Relatório consolidado:',out/'RELATORIO_FINAL.md')
