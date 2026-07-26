#!/usr/bin/env python3
"""Run the bundled zero-argument regression tests without external pytest.

The execution environment does not bundle pytest.  This runner supplies only
the tiny fixture/raises/mark surface used by the repository tests, skips the
explicit slow end-to-end test (the full pipeline is already run separately),
and executes all zero-argument test functions in isolated stage subprocesses.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT=Path(__file__).resolve().parents[1]
QC=ROOT/"integrated"/"qc"

CHILD=r'''
import contextlib, importlib.util, inspect, json, pathlib, sys, types, traceback
stage=pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0,str(stage/'src'))

class Raises:
    def __init__(self,error): self.error=error
    def __enter__(self): return self
    def __exit__(self,kind,value,tb):
        if kind is None: raise AssertionError(f"Expected {self.error.__name__}")
        return issubclass(kind,self.error)
class Mark:
    def __getattr__(self,name):
        def decorator(fn): setattr(fn,'_embedded_mark_'+name,True); return fn
        return decorator
def fixture(*args,**kwargs):
    def decorator(fn): setattr(fn,'_embedded_fixture',True); return fn
    return decorator
pytest=types.SimpleNamespace(raises=lambda error:Raises(error),mark=Mark(),fixture=fixture)
sys.modules['pytest']=pytest

passed=[]; skipped=[]; failed=[]
for path in sorted((stage/'tests').glob('test_*.py')):
    name=f"embedded_{stage.name}_{path.stem}"
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec)
    try: spec.loader.exec_module(module)
    except Exception:
        failed.append({'test':str(path.name),'error':traceback.format_exc()}); continue
    for test_name,fn in inspect.getmembers(module,inspect.isfunction):
        if not test_name.startswith('test_'): continue
        label=f"{path.name}::{test_name}"
        if inspect.signature(fn).parameters or getattr(fn,'_embedded_mark_slow',False): skipped.append(label); continue
        try: fn(); passed.append(label)
        except Exception: failed.append({'test':label,'error':traceback.format_exc()})
print(json.dumps({'stage':stage.name,'passed':passed,'skipped':skipped,'failed':failed}))
raise SystemExit(1 if failed else 0)
'''


def main():
    QC.mkdir(parents=True,exist_ok=True)
    reports=[]
    env=os.environ.copy(); env.update({'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONHASHSEED':'0','MPLBACKEND':'Agg','MPLCONFIGDIR':str(ROOT/'.mplconfig')})
    for number in range(1,6):
        stage=ROOT/'stages'/f'stage{number}'
        process=subprocess.run([sys.executable,'-c',CHILD,str(stage)],env=env,text=True,capture_output=True)
        line=process.stdout.strip().splitlines()[-1] if process.stdout.strip() else '{}'
        try: report=json.loads(line)
        except Exception: report={'stage':stage.name,'passed':[],'skipped':[],'failed':[{'test':'runner','error':process.stdout+process.stderr}]}
        report['exit_code']=process.returncode; reports.append(report)
    output={'reports':reports,'passed_count':sum(len(r['passed']) for r in reports),'skipped_count':sum(len(r['skipped']) for r in reports),'failed_count':sum(len(r['failed']) for r in reports)}
    (QC/'embedded_test_report.json').write_text(json.dumps(output,indent=2)+"\n",encoding='utf-8')
    print(json.dumps({k:output[k] for k in ('passed_count','skipped_count','failed_count')},indent=2))
    if output['failed_count']: raise SystemExit(2)


if __name__=='__main__': main()

