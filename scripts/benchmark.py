#!/usr/bin/env python3
"""Benchmark a supplied WAV; fresh-process repeats are not in-process warm inference."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
from va import ROOT, read, write, sha, now, load_runtime


def normalized(text):
    return ''.join(c.lower() for c in unicodedata.normalize('NFKC',text) if unicodedata.category(c)[0] not in ('P','Z','C'))

def distance(a,b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1):
            cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]

def score(reference,hypothesis):
    a,b=normalized(reference),normalized(hypothesis)
    result={'cer_raw':distance(a,b)/len(a) if a else None}
    try:
        from opencc import OpenCC
        cc=OpenCC('t2s')
        a,b=cc.convert(a),cc.convert(b)
        result['cer_script_normalized']=distance(a,b)/len(a) if a else None
    except ImportError:
        result['cer_script_normalized']=None
        result['script_normalization_note']='opencc unavailable; no fabricated normalized score'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio');p.add_argument('--reference');p.add_argument('--language',default='zh')
    p.add_argument('--model',default='base');p.add_argument('--repeats',type=int,default=2)
    p.add_argument('--output',required=True);p.add_argument('--synthetic',action='store_true')
    a=p.parse_args()
    if not 1<=a.repeats<=5:raise ValueError('repeats must be 1..5')
    cfg=load_runtime();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    audio=Path(a.audio).resolve();results=[]
    for backend in ('whisper.cpp','faster-whisper'):
        for i in range(a.repeats):
            dest=out/f'{backend}-{i+1}.json'
            cmd=[sys.executable,ROOT/'scripts/asr_worker.py','--backend',backend,'--model',cfg['models'][backend][a.model],
                 '--audio',audio,'--output',dest,'--language',a.language,'--whisper-cli',cfg['whisper_cli']]
            started=time.perf_counter()
            proc=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=3600)
            if proc.returncode:
                results.append(dict(backend=backend,run=i+1,status='failed',error=proc.stderr[-2000:]));continue
            row=read(dest);row.update(run=i+1,status='success',process_wall_s=time.perf_counter()-started)
            if a.reference:
                row.update(score(Path(a.reference).read_text(),''.join(s['text'] for s in row['segments'])))
            write(dest,row);results.append(row)
    summary=dict(created_at=now(),audio_sha256=sha(audio),synthetic=a.synthetic,model=a.model,runs=results,
        versions=cfg['versions'],limitations=[
        'Each run starts a fresh process and reloads the model. Later runs may benefit from OS caches; true in-process warm inference is not measured.',
        'First run is not a guaranteed cold disk cache. RSS is per ASR process/CLI child and excludes shared GPU allocations.',
        'Synthetic speech is a smoke/performance test, not real-review accuracy validation.',
        'No automatic default backend selection until real Mandarin/mixed-language and sustained-audio validation.'])
    write(out/'summary.json',summary)
    lines=['# Whisper 基準測試','',f'測試日期：{summary["created_at"]}',f'素材：{audio.name}；合成語音：{a.synthetic}',
           '| 後端 | 次數 | 程序秒數 | RTF | RSS MiB | 原始 CER | 繁簡正規化 CER | 加速確認 |',
           '|---|---:|---:|---:|---:|---:|---:|---|']
    for r in results:
        if r['status']!='success':lines.append(f'| {r["backend"]} | {r["run"]} | 失敗 | — | — | — | — | 未確認 |');continue
        def fmt(v):return f'{v:.3f}' if isinstance(v,(int,float)) else '未量測'
        lines.append('| '+' | '.join([r['backend'],str(r['run']),fmt(r['process_wall_s']),fmt(r['rtf']),fmt(r['peak_rss_bytes']/1024**2),fmt(r.get('cer_raw')),fmt(r.get('cer_script_normalized')),r['acceleration']['confirmed']])+' |')
    lines.extend(['','RTF＝ASR worker 秒數／音訊秒數；程序秒數另包含 Python 啟動。','']+summary['limitations'])
    (out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(report=str(out/'report.md'),successful=sum(r['status']=='success' for r in results)),ensure_ascii=False))

if __name__=='__main__':main()
