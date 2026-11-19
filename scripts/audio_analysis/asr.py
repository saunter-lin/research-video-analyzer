"""Local existing ASR worker, per-interval cache, no automatic model acquisition."""
from pathlib import Path
import json,subprocess,sys,tempfile
import va
from .alignment import normalize_segments,align_transcript
from .preprocess import inspect_wav,crop_pcm,prepare_audio

def identity(config):
    backend=config.get('backend','whisper.cpp');name=config.get('model','base');runtime=config['runtime']
    if backend not in ('whisper.cpp','faster-whisper'):raise ValueError('Unknown local ASR backend')
    path=Path(runtime['models'][backend][name])
    if not path.exists():raise FileNotFoundError('Existing ASR model missing; no download attempted')
    if backend=='whisper.cpp' and not Path(runtime['whisper_cli']).is_file():raise FileNotFoundError('whisper-cli missing')
    weights=va.sha(path) if path.is_file() else va.digest([(str(p.relative_to(path)),va.sha(p)) for p in sorted(path.rglob('*')) if p.is_file()])
    version=runtime['versions'][backend]
    if backend=='faster-whisper':
        import importlib.metadata
        version=importlib.metadata.version('faster-whisper')
    return dict(name='Whisper '+name,version=version,revision=None,weights_sha256=weights,backend=backend,backend_version=version,code_license='MIT',weights_license='MIT'),path

def transcribe_speech_segments(audio_path,speech_segments,config):
    store=config['store'];audio_path,_=prepare_audio(audio_path,store);duration=inspect_wav(audio_path)
    # None means VAD failed, not a negative detection. Empty list always bypasses ASR.
    fallback=speech_segments is None
    if fallback:
        import wave
        with wave.open(str(audio_path),'rb') as wav:
            silent=True
            while data:=wav.readframes(16000):
                if any(data):silent=False;break
        if silent:return dict(status='skipped',segments=[],raw_output=[],fallback=True,language=config.get('language','zh'),limitations=['Digital-zero input; ASR bypassed independently of unavailable VAD.'])
    spans=normalize_segments([dict(start_seconds=0,end_seconds=duration)] if fallback else speech_segments,duration)
    if not spans:return dict(status='skipped',segments=[],raw_output=[],fallback=False,language=config.get('language','zh'),limitations=['No detected speech; ASR was not invoked.'])
    model,path=identity(config);runtime=config['runtime'];maximum=float(config.get('max_segment_seconds',30))
    if not 1<=maximum<=120:raise ValueError('ASR chunk length must be 1–120 seconds')
    tasks=[]
    for s in spans:
        a=s['start_seconds']
        while a<s['end_seconds']-1e-7:
            b=min(s['end_seconds'],a+maximum);tasks.append((a,b));a=b
    output=[];raw=[];warnings=[];hit_count=0
    for start,end in tasks:
        settings=dict(language=config.get('language','zh'),beam_size=1,best_of=1,temperature=0,threads=4,previous_text=False,vad=False)
        recipe=va.digest(['audio-asr-v1',va.sha(audio_path),model,settings,start,end,maximum,va.sha(Path(__file__).parents[1]/'asr_worker.py'),va.sha(Path(runtime['whisper_cli'])) if model['backend']=='whisper.cpp' else runtime['versions'].get('ctranslate2')])
        cached=store.get(recipe)
        if cached:hit_count+=1
        else:
            with tempfile.TemporaryDirectory(dir=store.cache) as tmp:
                clip=Path(tmp)/'segment.wav';dest=Path(tmp)/'result.json'
                crop_pcm(audio_path,clip,start,end)
                command=[sys.executable,str(Path(__file__).parents[1]/'asr_worker.py'),'--backend',model['backend'],'--model',str(path),'--audio',str(clip),'--output',str(dest),'--language',settings['language'],'--whisper-cli',runtime['whisper_cli']]
                proc=subprocess.run(command,text=True,capture_output=True,timeout=3600)
                if proc.returncode:raise RuntimeError('ASR worker failed: '+proc.stderr[-2000:])
                cached=store.put(recipe,'audio-asr',dest)
        parsed=json.loads(cached.read_text())
        # PCM cropping rounds to exact sample indices; map that actual offset.
        actual_start=round(start*16000)/16000;actual_end=round(end*16000)/16000
        aligned,notes=align_transcript(parsed['segments'],actual_start,actual_end-actual_start,duration)
        output.extend(aligned);warnings.extend(notes);raw.append(dict(artifact_key=store.resolve(recipe),output=parsed,offset_seconds=actual_start))
    languages=[]
    for chunk in raw:
        backend=chunk['output'].get('raw_backend_output',{})
        language=backend.get('language') or backend.get('result',{}).get('language')
        if language and language not in languages:languages.append(language)
    if not output:warnings.append('Speech detected or assumed, but ASR returned no usable text; requires review.')
    return dict(status='needs_review' if not output else 'completed',segments=output,raw_output=raw,model=model,fallback=fallback,language=languages[0] if len(languages)==1 else languages or None,requested_language=config.get('language','zh'),cache_hits=hit_count,warnings=warnings,limitations=['ASR text and log probabilities are not acoustic-quality measurements.','ASR timestamps and content require human verification.']+(['VAD failed; existing ASR backend used on complete input in bounded chunks.'] if fallback else []))
