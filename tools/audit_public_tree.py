"""Limited first-party release boundary/secret-pattern audit; emits no matched values."""
from pathlib import Path
import json
import re
import sys

root = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
patterns = {
    'private-home': re.compile(r'/(?:Users)/[^/\s`]+|C:\\Users\\[^\\\s]+'),
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github-token': re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}'),
    'provider-key': re.compile(r'\b(?:sk-[A-Za-z0-9_-]{24,}|AIza[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16})'),
}
forbidden_dirs = {'data','cache','.venv','.models','.tools','.backups','research-ab','__pycache__'}
findings=[];scanned=0
for file in sorted(root.rglob('*')):
    if not file.is_file():continue
    relative=file.relative_to(root)
    if relative.parts[0] in {'.git','build','dist'} or any(part.endswith('.egg-info') for part in relative.parts):continue
    if file.is_symlink():findings.append(dict(file=str(relative),rule='symlink'));continue
    if any(part in forbidden_dirs for part in relative.parts) or file.name=='runtime.json' or file.suffix in {'.sqlite3','.db','.mp4','.wav','.bin','.tflite','.onnx'}:
        findings.append(dict(file=str(relative),rule='forbidden-local-asset'))
    try:content=file.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        findings.append(dict(file=str(relative),rule='unexpected-binary'));continue
    scanned+=1
    for rule,pattern in patterns.items():
        for number,line in enumerate(content.splitlines(),1):
            if pattern.search(line):findings.append(dict(file=str(relative),line=number,rule=rule))
print(json.dumps(dict(files_scanned=scanned,findings=findings,limitations='Pattern audit only; no complete secret, PII, copyright, vulnerability or Git-history certification'),indent=2))
sys.exit(bool(findings))
