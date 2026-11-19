#!/usr/bin/env python3
"""Run one explicit local ASR backend. JSON uses original input seconds."""
import argparse
import json
from pathlib import Path
import resource
import subprocess
import tempfile
import time
import wave


def execute(backend, model, audio, language, whisper_cli, offset=0):
    started=time.perf_counter()
    if backend=='faster-whisper':
        from faster_whisper import WhisperModel
        t=time.perf_counter()
        engine=WhisperModel(str(model),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
        loaded=time.perf_counter()
        iterator,info=engine.transcribe(str(audio),language=None if language=='auto' else language,
                    beam_size=1,best_of=1,temperature=0,vad_filter=False,condition_on_previous_text=False)
        items=list(iterator)
        segments=[dict(start=s.start+offset,end=s.end+offset,text=s.text) for s in items]
        raw_backend_output=dict(language=info.language,language_probability=info.language_probability,segments=[dict(start=s.start,end=s.end,text=s.text,avg_logprob=s.avg_logprob,no_speech_prob=s.no_speech_prob,compression_ratio=s.compression_ratio) for s in items])
        timing=dict(load_s=loaded-t,inference_s=time.perf_counter()-loaded)
        acceleration=dict(requested='CPU int8',confirmed='CPU int8',evidence='explicit CTranslate2 device=cpu compute_type=int8')
        memory=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        stderr=''
    else:
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'result'
            cmd=[str(whisper_cli),'-m',str(model),'-f',str(audio),'-l',language,
                 '-t','4','-bs','1','-bo','1','-tp','0','-nf','-mc','0','-oj','-of',str(dest)]
            p=subprocess.run(cmd,text=True,capture_output=True,timeout=3600)
            if p.returncode:
                raise RuntimeError('whisper.cpp failed: '+p.stderr[-2000:])
            raw=json.loads(dest.with_suffix('.json').read_text())
            raw_backend_output=raw
            segments=[dict(start=x['offsets']['from']/1000+offset,end=x['offsets']['to']/1000+offset,text=x['text']) for x in raw['transcription']]
            stderr=p.stderr
            import re
            def timing_value(label):
                m=re.search(label+r'\s*=\s*([\d.]+)\s*ms',stderr)
                return float(m.group(1))/1000 if m else None
            timing=dict(load_s=timing_value('load time'),engine_total_s=timing_value('total time'))
            # Require an actual device/backend log, not merely a Metal-enabled build.
            lines=[line for line in stderr.splitlines() if 'Metal' in line or 'using device' in line or 'GPU name' in line]
            confirmed=any(('Apple M' in line or 'using Metal backend' in line) for line in lines)
            acceleration=dict(requested='Metal',confirmed='Metal' if confirmed else 'unconfirmed',evidence=lines)
            memory=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    with wave.open(str(audio),'rb') as w:
        duration=w.getnframes()/w.getframerate()
    total=time.perf_counter()-started
    return dict(raw_backend_output=raw_backend_output,backend_stderr=stderr,backend=backend,model=str(model),language=language,segments=segments,origin='ASR',
                input_duration_s=duration,offset_s=offset,wall_s=total,rtf=total/duration if duration else None,
                timing=timing,peak_rss_bytes=memory,acceleration=acceleration,
                settings=dict(beam_size=1,best_of=1,temperature=0,vad=False,threads=4,previous_text=False),
                limitations=['Backend precision differs: whisper.cpp default floating point vs CTranslate2 int8.',
                              'Timestamp alignment and transcript quality require human verification.'])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--backend',required=True,choices=['whisper.cpp','faster-whisper'])
    for name in ('model','audio','output','language','whisper-cli'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--offset',type=float,default=0)
    a=p.parse_args()
    result=execute(a.backend,Path(a.model),Path(a.audio),a.language,a.whisper_cli,a.offset)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
