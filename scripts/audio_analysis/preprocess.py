"""Read-only source decoding via the existing FFmpeg and Store recipes."""
from pathlib import Path
import tempfile,wave
import va
from .alignment import number

def inspect_wav(path):
    with wave.open(str(path),'rb') as w:
        if w.getnchannels()!=1 or w.getframerate()!=16000 or w.getsampwidth()!=2:
            raise ValueError('Expected mono 16kHz PCM16 WAV')
        duration=w.getnframes()/16000
    if duration<=0:raise ValueError('Empty audio')
    return duration

def prepare_audio(audio_path,store):
    path=Path(audio_path)
    if not path.is_file():raise FileNotFoundError(path)
    recipe=va.digest(['audio-preprocess-v1',va.sha(path),'pcm_s16le',16000,1,va.sha(Path(va.ffmpeg()))])
    cached=store.get(recipe)
    if not cached:
        with tempfile.TemporaryDirectory(dir=store.cache) as temp:
            out=Path(temp)/'mono.wav'
            va.run([va.ffmpeg(),'-nostdin','-v','error','-i',str(path),'-map','0:a:0','-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(out)])
            inspect_wav(out)
            cached=store.put(recipe,'audio-preprocessed',out)
    return cached,dict(recipe=recipe,artifact_key=store.resolve(recipe),sha256=va.sha(cached),duration_seconds=inspect_wav(cached),sample_rate=16000,channels=1,normalization=False,denoise=False)

def crop_pcm(path,dest,start,end):
    start=number(start);end=number(end)
    with wave.open(str(path),'rb') as w:
        n=w.getnframes();a=max(0,min(n,round(start*16000)));b=max(0,min(n,round(end*16000)))
        if b<=a:raise ValueError('Empty crop')
        w.setpos(a);data=w.readframes(b-a)
    with wave.open(str(dest),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(data)
    return a/16000,(b-a)/16000
