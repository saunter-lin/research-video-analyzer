"""Current-process statement-line coverage with stdlib trace; no subprocess coverage."""
from pathlib import Path
import argparse
import json
import sys
import trace
import unittest

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',required=True)
a = p.parse_args()
tracer = trace.Trace(count=True,trace=False,ignoredirs=[sys.prefix,sys.base_prefix])
result = tracer.runfunc(unittest.TextTestRunner(verbosity=2).run,
                        unittest.defaultTestLoader.discover(str(root/'tests')))
counts = tracer.results().counts
rows=[]
for file in sorted((root/'scripts').rglob('*.py')):
    executable = set(trace._find_executable_linenos(str(file)))
    covered = {line for (name,line),count in counts.items() if Path(name).resolve()==file.resolve() and count}
    rows.append(dict(file=str(file.relative_to(root)),statements=len(executable),covered=len(covered & executable)))
total=sum(row['statements'] for row in rows);hit=sum(row['covered'] for row in rows)
Path(a.output).write_text(json.dumps(dict(method='stdlib trace statement lines, parent process only; excludes subprocess/branch coverage',
    tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),statements=total,covered=hit,
    percent=round(hit/total*100,2) if total else 0,files=rows),indent=2)+'\n')
sys.exit(not result.wasSuccessful())
