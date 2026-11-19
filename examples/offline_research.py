#!/usr/bin/env python3
"""Exercise the real CLI with self-authored synthetic evidence; no remote calls."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', default='video-analyzer')
    parser.add_argument('--output', help='new directory for preserved synthetic results')
    args = parser.parse_args()
    executable = shutil.which(args.cli)
    if not executable:
        parser.error('CLI not found: install the core or pass --cli /path/to/video-analyzer')
    executable = str(Path(executable).resolve())
    root = Path(args.output).expanduser().resolve() if args.output else Path(tempfile.mkdtemp(prefix='research-offline-'))
    if args.output:
        root.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        path = root/name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return str(path)
    def cli(*values):
        result = subprocess.run([executable, '--data', str(root/'data'), '--cache', str(root/'cache'), *values],
                                text=True, capture_output=True, check=True)
        return json.loads(result.stdout)
    session = cli('create','--title','Synthetic specification review','--question','What does this synthetic snapshot state?')
    sid = session['id']
    url = 'https://example.com/synthetic-specification'
    source = cli('import-candidates',sid,save('candidates.json',[dict(source_type='web',url=url)]))[0]
    cli('select',sid,source,'--actor','automatic','--reason','Self-authored offline fixture; no external search')
    (root/'page.md').write_text('# Synthetic specification\nThe example device supports mode A.\nOnly laboratory conditions are claimed.\n', encoding='utf-8')
    imported = cli('import-web',sid,save('manifest.json',dict(url=url,title='Synthetic specification',file='page.md',
        format='markdown',retrieved_at='2026-11-19T00:00:00+00:00',capture_method='self-authored synthetic fixture',publisher='Example')))
    eid = cli('evidence',sid,save('evidence.json',dict(source_id=source,artifact_key=imported['artifact_key'],
        claim='The synthetic page states support for mode A.',claim_type='official_spec',support='medium',
        reason='Exact synthetic line quoted',conditions='Synthetic laboratory-only claim',limitations='No real device or measurement',
        product_version='synthetic',verification='Self-authored fixture checked',locator=dict(line_start=2,line_end=2),
        excerpt='The example device supports mode A.')))
    analysis = dict(summary=f'Synthetic page states support for mode A. [E:{eid}]',
        topics=f'Page statement only. [E:{eid}]',comparison='No real product comparison.',
        limitations='Synthetic input; not performance evidence.',conclusion='一般研究分析',evidence_ids=[eid],
        analysis_engine='offline example; human-authored synthetic analysis')
    report = cli('report',sid,save('analysis.json',analysis),'--mode','quick')
    text = Path(report).read_text(encoding='utf-8')
    assert eid in text and url in text, 'Report must resolve evidence to the source'
    assert cli('show',sid)['evidence'][0]['id'] == eid
    result = dict(session=sid,source_id=source,evidence_id=eid,report=report,output=str(root),
                  synthetic=True,network_calls=0,paid_api_calls=0)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
