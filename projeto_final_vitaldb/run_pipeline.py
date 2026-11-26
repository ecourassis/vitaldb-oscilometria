"""Orquestrador: execute com Python 3.12, a partir de qualquer diretório."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
A2 = 'aula02_etl_duckdb'
A3 = 'aula03_qualidade_sql'
A4 = 'aula04_machine_learning'
A5 = 'aula05_embeddings_vector_search'
DIMS = ['dim_patient', 'dim_case', 'dim_time', 'dim_label']


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_parquets(source, target, names):
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(source / (name + '.parquet'), target / (name + '.parquet'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['snapshot', 'api'], default='snapshot')
    parser.add_argument('--embeddings', choices=['model', 'archived'], default='model')
    args = parser.parse_args()
    if args.source == 'api' and args.embeddings == 'archived':
        parser.error('A opção archived só é compatível com o snapshot histórico.')
    run = ROOT / 'runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True)
    manifest = {'started_utc': utc(), 'status': 'running', 'source_mode': args.source,
                'embedding_mode': args.embeddings, 'config': json.loads((ROOT/'config.json').read_text()),
                'python': sys.version, 'platform': platform.platform(), 'packages': {}, 'steps': []}
    for line in (ROOT/'requirements.txt').read_text().splitlines():
        name, version = line.split('==')
        try:
            manifest['packages'][name] = {'required': version, 'installed': metadata.version(name)}
        except metadata.PackageNotFoundError:
            manifest['packages'][name] = {'required': version, 'installed': None}
    manifest_path = run/'run_manifest.json'
    def save():
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    def log(message):
        line = f'{utc()} {message}'
        print(line, flush=True)
        with (run/'pipeline.log').open('a', encoding='utf-8') as f:
            f.write(line+'\n')
    def step(name, action):
        entry = {'name': name, 'started_utc': utc(), 'status': 'running'}
        manifest['steps'].append(entry)
        save()
        start = time.perf_counter()
        log('INICIO '+name)
        try:
            action()
            entry['status'] = 'success'
        except Exception as exc:
            entry['status'] = 'failed'
            entry['error'] = repr(exc)
            raise
        finally:
            entry['seconds'] = round(time.perf_counter()-start, 3)
            entry['finished_utc'] = utc()
            log(entry['status'].upper()+' '+name)
            save()
    def script(path, *extra):
        env = dict(os.environ, MPLBACKEND='Agg')
        with subprocess.Popen([sys.executable, str(path), *extra], cwd=path.parent.parent,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, env=env) as proc:
            for line in proc.stdout:
                log(line.rstrip())
            if proc.wait():
                raise RuntimeError(f'{path.name}: código de saída {proc.returncode}')
    def prepare():
        mismatches = [n for n, v in manifest['packages'].items() if v['required'] != v['installed']]
        if mismatches:
            raise RuntimeError('Instale as versões fixadas: '+', '.join(mismatches))
        for name in [A2, A3, A4, A5]:
            dest = run/name
            dest.mkdir()
            for folder in ['src', 'sql', 'metadata']:
                if (SOURCE/name/folder).exists():
                    shutil.copytree(SOURCE/name/folder, dest/folder)
        manifest['source_code_sha256'] = {str(p.relative_to(SOURCE)): sha(p) for p in sorted(SOURCE.glob('*/src/*.py'))}
    def ingest():
        target = run/A2/'data/processed'
        if args.source == 'api':
            script(run/A2/'src/pipeline.py')
            manifest['raw_sha256'] = {p.name: sha(p) for p in sorted((run/A2/'data/raw').glob('*.csv'))}
        else:
            copy_parquets(SOURCE/A2/'data/processed', target, ['fact_bp_measurement']+DIMS)
            # Reexecuta as consultas da Aula 02 sobre o snapshot, sem buscar trilhas.
            import duckdb
            output = run/A2/'outputs'
            output.mkdir()
            with duckdb.connect(str(target/'vitaldb_star.duckdb')) as con:
                for name in ['fact_bp_measurement']+DIMS:
                    path = str(target/(name+'.parquet')).replace("'", "''")
                    con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{path}')")
                queries = (run/A2/'sql/queries.sql').read_text().split(';')
                report = ['# Consultas da Aula 02 — snapshot']
                for i, query in enumerate(q for q in queries if q.strip()):
                    result = con.execute(query).fetchdf()
                    report.extend([f'## Consulta {i+1}', '```sql', query.strip(), '```', result.to_markdown(index=False)])
                (output/'query_results.md').write_text('\n\n'.join(report), encoding='utf-8')
        manifest['input_parquet_sha256'] = {p.name: sha(p) for p in sorted(target.glob('*.parquet'))}
        copy_parquets(target, run/A3/'data/bronze', ['fact_bp_measurement']+DIMS)
    def quality():
        script(run/A3/'src/run_quality_checks.py')
        # Teste adicional de integridade referencial e unicidade das dimensões.
        import duckdb
        with duckdb.connect() as con:
            bronze = run/A3/'data/bronze'
            fact = str(bronze/'fact_bp_measurement.parquet').replace("'", "''")
            for dim, key in zip(DIMS, ['patient_key','case_key','time_key','label_key']):
                path = str(bronze/(dim+'.parquet')).replace("'", "''")
                n, distinct = con.execute(f"SELECT count(*), count(DISTINCT {key}) FROM read_parquet('{path}')").fetchone()
                orphan = con.execute(f"SELECT count(*) FROM read_parquet('{fact}') f LEFT JOIN read_parquet('{path}') d USING ({key}) WHERE d.{key} IS NULL").fetchone()[0]
                if n != distinct or orphan:
                    raise ValueError(f'Integridade referencial: {dim}: {orphan} órfãos')
            counts = json.loads((run/A3/'outputs/quality_results.json').read_text())['camadas'][0]
            if not counts['silver_validos']:
                raise ValueError('Nenhuma aferição válida')
        for name in [A4,A5]:
            target = run/name/'data/input'
            copy_parquets(bronze, target, DIMS)
            copy_parquets(run/A3/'data/silver', target, ['fact_bp_measurement_valid'])
    def ml():
        script(run/A4/'src/train_and_evaluate.py')
    def embeddings():
        if args.embeddings == 'model':
            script(run/A5/'src/run_embeddings.py')
        else:
            script(ROOT/'replay_embeddings.py', str(run/A5), str(SOURCE/A5/'outputs/embeddings.csv'))
    def report():
        script(ROOT/'summarize.py', str(run))
        manifest['results'] = {name: json.loads((run/name/'outputs'/file).read_text()) for name,file in [(A3,'quality_results.json'),(A4,'metrics.json'),(A5,'metrics.json')]}
    try:
        for name, action in [('ambiente',prepare),('ingestao_etl',ingest),('qualidade',quality),('regressao',ml),('embeddings',embeddings),('relatorio',report)]:
            step(name,action)
        manifest['status'] = 'success'
        log(f'Pipeline concluído: {run}')
    except Exception as exc:
        manifest['status'] = 'failed'
        log(f'ERRO: {exc}')
        raise
    finally:
        manifest['finished_utc'] = utc()
        save()


if __name__ == '__main__':
    main()
