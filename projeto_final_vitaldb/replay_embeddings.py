"""Regenera a busca e gráficos usando vetores históricos, sem inferência nova."""
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

root, archive = Path(sys.argv[1]), Path(sys.argv[2])
spec = importlib.util.spec_from_file_location('original_embeddings', root/'src/run_embeddings.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
historical = pd.read_csv(archive, dtype={'patient_id':str, 'measurement_id':str})
frame = module.load_data()
assert frame.measurement_id.tolist() == historical.measurement_id.tolist()
assert frame.patient_id.tolist() == historical.patient_id.tolist()
assert historical.model_version.eq(module.MODEL_VERSION).all()
assert frame.apply(module.build_clinical_text, axis=1).tolist() == historical.clinical_text.tolist()
assert frame.hypotension_reference.tolist() == historical.hypotension_reference.tolist()
vectors = np.array([json.loads(x) for x in historical.embedding_json], dtype=np.float32)
assert vectors.shape == (len(frame), module.EMBEDDING_DIMENSION)
assert np.isfinite(vectors).all() and np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-5)
module.generate_embeddings = lambda texts: vectors
module.main()
print('ATENÇÃO: vetores históricos verificados; nenhuma nova inferência MiniLM.')
