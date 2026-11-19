"""Explicit selected-source orchestration using existing Store, pins and history."""
from pathlib import Path
import json,tempfile,time,resource
import va
from . import VERSION
from .preprocess import prepare_audio,crop_pcm,inspect_wav
from .alignment import number
from . import vad,asr,evidence

def analyze(store,session,source_id,parent_key,source_offset,config=None,clip_start=0,clip_end=None):
    config=config or {}
    if set(config)-{'enabled','vad','asr','asr_enabled','vad_fallback'}:raise ValueError('Unknown audio setting')
    if config.get('enabled') is not True:raise ValueError('audio_analysis.enabled=false; explicit opt-in required')
    vad.validate_config(config.get('vad',{}))
    source=store.allowed(session,source_id);parent_key=store.resolve(parent_key)
    owned=set(source.get('artifacts',{}).values())|{x['key'] for x in source.get('extractions',[])}
    if parent_key not in owned:raise ValueError('Audio artifact does not belong to selected source')
    offset=number(source_offset);clip_start=number(clip_start)
    if offset<0 or clip_start<0:raise ValueError('Negative source mapping')
    parent=store.artifact(session,parent_key);started=time.perf_counter()
    prepared,processing=prepare_audio(parent,store);duration=processing['duration_seconds']
    clip_end=duration if clip_end is None else number(clip_end)
    if not clip_start<clip_end<=duration+1e-6:raise ValueError('Clip outside parent audio')
    if clip_start or clip_end<duration:
        crop_recipe=va.digest(['audio-crop-v1',processing['sha256'],clip_start,clip_end])
        cropped=store.get(crop_recipe)
        if not cropped:
            with tempfile.TemporaryDirectory(dir=store.cache) as tmp:
                path=Path(tmp)/'clip.wav';crop_pcm(prepared,path,clip_start,clip_end)
                cropped=store.put(crop_recipe,'audio-preprocessed',path)
        prepared=cropped;processing.update(artifact_key=store.resolve(crop_recipe),sha256=va.sha(prepared),duration_seconds=inspect_wav(prepared))
    start=offset+round(clip_start*16000)/16000;end=start+processing['duration_seconds']
    source_duration=source.get('metadata',{}).get('duration')
    if source_duration is not None and end>number(source_duration)+1/16000:raise ValueError('Mapping exceeds original source')
    runtime=va.load_runtime();asr_cfg=config.get('asr',{})
    if set(asr_cfg)-{'backend','model','language','max_segment_seconds'}:raise ValueError('Unknown ASR setting')
    vmodel=None;amodel=None
    try:vmodel=vad.identity()
    except (ImportError,FileNotFoundError):pass
    if config.get('asr_enabled',True):
        try:amodel,_=asr.identity(asr_cfg|dict(runtime=runtime))
        except (ImportError,KeyError,FileNotFoundError):pass
    recipe=va.digest(['audio-pipeline',VERSION,[(p.name,va.sha(p)) for p in sorted(Path(__file__).parent.glob('*.py'))],session['id'],source_id,parent_key,va.sha(prepared),start,end,config,vmodel,amodel,runtime['versions'],va.sha(Path(runtime['whisper_cli'])) if Path(runtime['whisper_cli']).is_file() else None,va.sha(Path(__file__).parents[1]/'asr_worker.py')])
    cached=store.get(recipe)
    if cached:
        result=va.read(cached)
        for record in result['evidence']:evidence.validate(record)
        result['cache_hit']=True
    else:
        try:vd=vad.detect_speech_segments(prepared,config.get('vad',{}))
        except Exception as exc:vd=dict(status='failed',segments=None,error=type(exc).__name__+': '+str(exc),model=vmodel,limitations=['VAD unavailable; no negative speech conclusion may be inferred.'])
        try:
            if not config.get('asr_enabled',True):
                ar=dict(status='skipped',segments=[],raw_output=[],limitations=['ASR explicitly disabled.'])
            elif vd['status']=='failed' and not config.get('vad_fallback',True):
                ar=dict(status='skipped',segments=[],raw_output=[],limitations=['VAD failed and fallback disabled.'])
            else:
                ar=asr.transcribe_speech_segments(prepared,vd['segments'],asr_cfg|dict(runtime=runtime,store=store))
        except Exception as exc:ar=dict(status='failed',segments=[],raw_output=[],error=type(exc).__name__+': '+str(exc),model=amodel,limitations=['ASR failed; empty text is not proof of absent speech.'])
        with tempfile.TemporaryDirectory(dir=store.cache) as tmp:
            raw=Path(tmp)/'raw.json';va.write(raw,dict(vad=vd,asr=ar))
            raw_recipe=va.digest([recipe,'raw',va.sha(raw)]);store.put(raw_recipe,'audio-raw',raw)
        raw_path=store.pin(session,raw_recipe)
        # Pin decoded input and per-chunk raw ASR artifacts, preserving their provenance.
        input_path=store.pin(session,processing['artifact_key'])
        for chunk in ar.get('raw_output',[]):store.pin(session,chunk['artifact_key'])
        clip=dict(id=va.digest([source_id,parent_key,start,end,va.sha(prepared)]),parent_artifact_key=parent_key,derived_sha256=va.sha(prepared),source_start_s=start,source_end_s=end,timebase='original_video_seconds',processing={k:processing[k] for k in ('sample_rate','channels','normalization','denoise')}|dict(input_artifact_key=processing['artifact_key'],input_path=input_path))
        vresult=dict(speech_detected=vd['speech_detected'],segments_clip_seconds=vd['segments']) if vd['status']=='completed' else None
        transcript=[dict(s,start=s['start']+start,end=s['end']+start) for s in ar['segments']]
        records=[evidence.make_record(session['id'],source_id,clip,'speech_detection',vresult,vd.get('model'),vd['status'],raw_path,'/vad',recipe,vd['limitations']),evidence.make_record(session['id'],source_id,clip,'asr',dict(segments_source_seconds=transcript,language=ar.get('language'),fallback=ar.get('fallback',False)),ar.get('model',amodel),ar['status'],raw_path,'/asr',recipe,ar['limitations'])]
        cacheable=vd['status']=='completed' and ar['status']!='failed'
        for record in records:record['recipe']['parameters']=dict(config=config,source_offset=offset,clip_start=clip_start,clip_end=clip_end)
        result=dict(cacheable=cacheable,recipe=recipe,evidence=records,raw_artifact_key=store.resolve(raw_recipe),input_artifact_key=processing['artifact_key'],cache_hit=False,wall_seconds=time.perf_counter()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,status='completed' if vd['status']=='completed' and ar['status'] in ('completed','skipped') else 'needs_review')
        # Failures remain auditable but do not become permanent successful cache hits.
        with tempfile.TemporaryDirectory(dir=store.cache) as tmp:
            path=Path(tmp)/'evidence.json';va.write(path,result)
            storage_recipe=recipe if result['cacheable'] else va.digest([recipe,'failure',va.now()])
            cached=store.put(storage_recipe,'audio-evidence',path)
    artifact=store.resolve(recipe) if result['cacheable'] else store.resolve(storage_recipe)
    store.pin(session,artifact)
    links=session.setdefault('audio_analyses',[])
    if not any(x['artifact_key']==artifact for x in links):
        links.append(dict(artifact_key=artifact,source_id=source_id,parent_artifact_key=parent_key,record_ids=[r['record_id'] for r in result['evidence']],created_at=va.now()))
        store.save(session)
    return result
