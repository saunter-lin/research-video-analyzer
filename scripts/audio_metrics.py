#!/usr/bin/env python3
"""Published-track auxiliary levels. Not SNR, THD, or product quality scores."""
import argparse
import json
import math
from pathlib import Path
import av
import numpy as np


def metrics(path):
    peak=0.;squares=0.;samples=0;near=0;duration=0.
    with av.open(str(path)) as container:
        stream=next((x for x in container.streams if x.type=='audio'),None)
        if stream is None:raise ValueError('無音軌')
        resampler=av.AudioResampler(format='fltp',layout='mono',rate=48000)
        for frame in container.decode(stream):
            for chunk in resampler.resample(frame):
                x=chunk.to_ndarray().astype(np.float64).ravel()
                if not len(x):continue
                peak=max(peak,float(np.max(np.abs(x))))
                squares+=float(np.dot(x,x));samples+=len(x);near+=int(np.sum(np.abs(x)>=.999))
        for chunk in resampler.resample(None):
            x=chunk.to_ndarray().astype(np.float64).ravel()
            if len(x):
                peak=max(peak,float(np.max(np.abs(x))));squares+=float(np.dot(x,x));samples+=len(x);near+=int(np.sum(np.abs(x)>=.999))
    if not samples:raise ValueError('空音軌')
    rms=math.sqrt(squares/samples)
    return dict(duration_s=samples/48000,peak_dbfs=20*math.log10(peak) if peak else None,
                rms_dbfs=20*math.log10(rms) if rms else None,near_full_scale_fraction=near/samples,
                limitations=['Mono 48kHz analysis copy; no input mutation.','Near-full-scale samples do not prove clipping.','Not SNR or THD; levels cannot rank product microphone quality.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('audio');p.add_argument('--output',required=True);a=p.parse_args()
    Path(a.output).write_text(json.dumps(metrics(a.audio),ensure_ascii=False,indent=2),encoding='utf-8')
