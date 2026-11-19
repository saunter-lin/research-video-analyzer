"""Round4-compatible sidecars; machine inference never implies human review."""
import re,datetime,json
from pathlib import Path
import va
from .alignment import number

def check_schema(value,schema,path='$'):
    """Dependency-free validator for keywords used in the shipped schema (not a general JSON Schema engine)."""
    if 'anyOf' in schema:
        errors=[]
        for branch in schema['anyOf']:
            try:check_schema(value,branch,path);break
            except ValueError as exc:errors.append(exc)
        else:raise ValueError(path+': no matching schema branch')
    types=schema.get('type',[]);types=[types] if isinstance(types,str) else types
    predicates={'object':lambda x:isinstance(x,dict),'array':lambda x:isinstance(x,list),'string':lambda x:isinstance(x,str),'boolean':lambda x:type(x) is bool,'null':lambda x:x is None,'number':lambda x:type(x) in (int,float),'integer':lambda x:type(x) is int}
    if types and not any(predicates[t](value) for t in types):raise ValueError(path+': wrong type')
    if 'const' in schema and value!=schema['const']:raise ValueError(path+': invalid constant')
    if 'enum' in schema and value not in schema['enum']:raise ValueError(path+': invalid enum')
    if isinstance(value,dict):
        if set(schema.get('required',[]))-set(value):raise ValueError(path+': missing field')
        props=schema.get('properties',{})
        if schema.get('additionalProperties') is False and set(value)-set(props):raise ValueError(path+': unknown field')
        for k,v in value.items():
            if k in props:check_schema(v,props[k],path+'.'+k)
    if isinstance(value,list):
        if len(value)<schema.get('minItems',0):raise ValueError(path+': too few items')
        for i,item in enumerate(value):check_schema(item,schema.get('items',{}),path+'['+str(i)+']')
    if isinstance(value,str):
        if len(value)<schema.get('minLength',0) or ('pattern' in schema and not re.search(schema['pattern'],value)):raise ValueError(path+': invalid string')
    if type(value) in (int,float):
        value=number(value)
        if 'minimum' in schema and value<schema['minimum'] or 'maximum' in schema and value>schema['maximum'] or 'exclusiveMinimum' in schema and value<=schema['exclusiveMinimum']:raise ValueError(path+': outside bounds')
    for branch in schema.get('allOf',[]):check_schema(value,branch,path)
    if 'if' in schema:
        try:check_schema(value,schema['if'],path)
        except ValueError:pass
        else:check_schema(value,schema.get('then',{}),path)

TYPES={'speech_detection','asr','sound_event','noise_interference','quality_estimate','subjective_perception','signal_metrics'}
def validate(record):
    schema=va.read(Path(__file__).parents[2]/'references/audio-evidence.schema.json')
    check_schema(record,schema)
    required={'schema_version','record_id','session_id','source_id','audio_clip','model','analysis_type','status','raw_output','result','confidence','known_limitations','human_confirmation','promotion','recipe','created_at'}
    if set(record)!=required:raise ValueError('Audio evidence fields do not match version 1')
    if record['schema_version']!='audio-evidence/1.0':raise ValueError('Unknown audio schema')
    for value,length in [(record['record_id'],64),(record['session_id'],12),(record['audio_clip']['id'],64),(record['audio_clip']['parent_artifact_key'],64),(record['audio_clip']['derived_sha256'],64),(record['recipe']['sha256'],64),(record['raw_output']['sha256'],64)]:
        if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{'+str(length)+'}',value):raise ValueError('Invalid evidence identity')
    if not isinstance(record['source_id'],str) or not record['source_id']:raise ValueError('Missing source')
    clip=record['audio_clip'];a=number(clip['source_start_s']);b=number(clip['source_end_s'])
    if a<0 or b<=a or clip['timebase']!='original_video_seconds':raise ValueError('Invalid evidence timeline')
    if record['analysis_type'] not in TYPES:raise ValueError('Invalid analysis type')
    if record['status'] not in {'completed','skipped','failed','unsupported','insufficient_input','needs_review'}:raise ValueError('Invalid status')
    confidence=record['confidence']
    if confidence['level'] not in {'undetermined','low','medium','high'} or type(confidence['calibrated']) is not bool:raise ValueError('Invalid confidence')
    if confidence['value'] is not None and not 0<=number(confidence['value'])<=1:raise ValueError('Invalid probability')
    human=record['human_confirmation']
    if type(human['confirmed']) is not bool:raise ValueError('Invalid human verification')
    if human['confirmed'] and (not human['reviewer'] or not human['reviewed_at'] or not human['scope']):raise ValueError('Human confirmation requires review metadata')
    if not record['known_limitations'] or not all(isinstance(s,str) and s for s in record['known_limitations']):raise ValueError('Missing limitations')
    datetime.datetime.fromisoformat(record['created_at'])
    raw=record['raw_output'];path=Path(raw['path'])
    if not path.is_file() or va.sha(path)!=raw['sha256']:raise ValueError('Raw evidence missing or changed')
    parsed=va.read(path)
    selector=raw['selector']
    if not isinstance(selector,str) or not selector.startswith('/'):raise ValueError('Missing JSON selector')
    for token in selector[1:].split('/'):
        token=token.replace('~1','/').replace('~0','~')
        if not isinstance(parsed,dict) or token not in parsed:raise ValueError('Raw selector does not resolve')
        parsed=parsed[token]
    if record['status']=='completed' and record['model'] is None:raise ValueError('Completed inference requires model identity')
    result=record['result']
    if record['status']=='completed' and record['analysis_type']=='speech_detection':
        if type(result['speech_detected']) is not bool:raise ValueError('Speech flag must be boolean')
        spans=result['segments_clip_seconds']
        if result['speech_detected']!=bool(spans):raise ValueError('Inconsistent speech flag')
        for s in spans:
            if not 0<=number(s['start_seconds'])<number(s['end_seconds'])<=b-a+1e-6:raise ValueError('VAD span outside clip')
    if record['analysis_type']=='asr' and result:
        for s in result['segments_source_seconds']:
            if not a<=number(s['start'])<number(s['end'])<=b+1e-6:raise ValueError('ASR span outside source clip')
    return record

def make_record(session_id,source_id,clip,analysis_type,result,model,status,raw_path,selector,recipe,limitations):
    record=dict(schema_version='audio-evidence/1.0',record_id=va.digest([session_id,source_id,clip['id'],analysis_type,recipe,va.sha(raw_path)]),session_id=session_id,source_id=source_id,audio_clip=clip,model=model,analysis_type=analysis_type,status=status,raw_output=dict(path=str(raw_path),sha256=va.sha(raw_path),format='json',selector=selector),result=result,confidence=dict(level='undetermined',value=None,calibrated=False,basis='No calibrated evidence confidence; backend values retained only in raw output.'),known_limitations=limitations,human_confirmation=dict(confirmed=False,reviewer=None,reviewed_at=None,scope=[]),promotion=dict(eligible=False,existing_claim_type='inference',support='undetermined'),recipe=dict(sha256=recipe,adapter_version='1.0.0',parameters={}),created_at=va.now())
    return validate(record)
