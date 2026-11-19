"""Existing packaged Silero V6 on CPU, bounded windows and no downloads."""
from pathlib import Path
import importlib.metadata,time,wave
import va
from .alignment import normalize_segments,number
from .preprocess import inspect_wav,prepare_audio

DEFAULTS=dict(threshold=0.5,min_speech_duration_ms=0,min_silence_duration_ms=2000,speech_pad_ms=400,window_seconds=60,overlap_seconds=2)

def validate_config(config):
    if set(config)-set(DEFAULTS):raise ValueError('Unknown VAD setting')
    cfg=DEFAULTS|config
    window=number(cfg['window_seconds']);overlap=number(cfg['overlap_seconds'])
    if not 1<=window<=300 or not 0<=overlap<window or round((window-overlap)*16000)<1:raise ValueError('Invalid VAD window')
    if not 0<cfg['threshold']<1 or any(cfg[k]<0 for k in ('min_speech_duration_ms','min_silence_duration_ms','speech_pad_ms')):raise ValueError('Invalid VAD thresholds')
    return cfg

def identity():
    import faster_whisper
    path=Path(faster_whisper.__file__).parent/'assets/silero_vad_v6.onnx'
    if not path.is_file():raise FileNotFoundError('Bundled Silero model unavailable; no download attempted')
    return dict(name='Silero VAD V6 (faster-whisper bundled)',version=importlib.metadata.version('faster-whisper'),revision=None,weights_sha256=va.sha(path),backend='onnxruntime CPU',backend_version=importlib.metadata.version('onnxruntime'),code_license='MIT',weights_license='MIT')

def detect_speech_segments(audio_path,config=None):
    import numpy as np
    import onnxruntime as ort
    from faster_whisper.vad import get_vad_model,get_speech_timestamps,VadOptions
    config=dict(config or {})
    store=config.pop('store',None)
    try:inspect_wav(audio_path)
    except (ValueError,wave.Error,EOFError):
        if store is None:raise ValueError('Noncanonical audio requires config.store for existing preprocessing cache')
        audio_path,_=prepare_audio(audio_path,store)
    cfg=validate_config(config)
    window=cfg['window_seconds'];overlap=cfg['overlap_seconds']
    model_info=identity();duration=inspect_wav(audio_path)
    ort.disable_telemetry_events();t=time.perf_counter();model=get_vad_model();load=time.perf_counter()-t
    if model.session.get_providers()!=['CPUExecutionProvider']:raise RuntimeError('Expected CPU-only Silero')
    options=VadOptions(**{k:cfg[k] for k in ('threshold','min_speech_duration_ms','min_silence_duration_ms','speech_pad_ms')})
    raw=[];spans=[];t=time.perf_counter()
    with wave.open(str(audio_path),'rb') as w:
        total=w.getnframes();pos=0;window_n=round(window*16000);step=round((window-overlap)*16000)
        while pos<total:
            w.setpos(pos);audio=np.frombuffer(w.readframes(window_n),dtype='<i2').astype(np.float32)/32768
            found=get_speech_timestamps(audio,options,sampling_rate=16000)
            raw.append(dict(offset_samples=pos,input_samples=len(audio),segments_samples=found))
            spans.extend(dict(start_seconds=(pos+s['start'])/16000,end_seconds=(pos+s['end'])/16000) for s in found)
            if pos+window_n>=total:break
            pos+=step
    spans=normalize_segments(spans,duration)
    for s in spans:s.update(confidence=None,model_name=model_info['name'],model_version=model_info['version'])
    return dict(status='completed',speech_detected=bool(spans),segments=spans,model=model_info,raw_output=raw,config=cfg,load_seconds=load,inference_seconds=time.perf_counter()-t,duration_seconds=duration,limitations=['VAD is activity prediction, not microphone quality.','No calibrated segment confidence is exposed; confidence is null.','Independent overlapping windows can affect long-audio boundaries.','Exact upstream training revision is unknown; bundled asset hash identifies weights.'])
