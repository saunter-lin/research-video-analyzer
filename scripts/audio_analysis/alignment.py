"""Numeric interval handling; all intervals are half-open seconds."""
import math

def number(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):
        raise ValueError('Time must be a finite number')
    return float(x)

def normalize_segments(segments, duration):
    duration=number(duration)
    if duration<=0: raise ValueError('Audio duration must be positive')
    result=[]
    for s in segments:
        start=max(0.,min(duration,number(s['start_seconds'])))
        end=max(0.,min(duration,number(s['end_seconds'])))
        if end>start: result.append(dict(start_seconds=start,end_seconds=end))
    merged=[]
    for s in sorted(result,key=lambda x:x['start_seconds']):
        if merged and s['start_seconds']<=merged[-1]['end_seconds']+1e-7:
            merged[-1]['end_seconds']=max(merged[-1]['end_seconds'],s['end_seconds'])
        else: merged.append(s.copy())
    for s in merged:s['duration_seconds']=s['end_seconds']-s['start_seconds']
    return merged

def align_transcript(segments, offset, segment_duration, original_duration):
    offset=number(offset);segment_duration=number(segment_duration);original_duration=number(original_duration)
    if offset<0 or segment_duration<=0 or offset+segment_duration>original_duration+1e-6:
        raise ValueError('Invalid segment mapping')
    result=[];warnings=[];previous=offset
    for s in segments:
        if not s.get('text','').strip():continue
        a=number(s['start']);b=number(s['end'])
        if a<0 or b>segment_duration or b<a:warnings.append('ASR interval clipped/dropped at input boundary')
        a=max(previous,offset+max(0.,min(segment_duration,a)))
        b=min(original_duration,offset+max(0.,min(segment_duration,b)))
        if b<=a:continue
        result.append(dict(s,start=a,end=b));previous=b
    return result,warnings
