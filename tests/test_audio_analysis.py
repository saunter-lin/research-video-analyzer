import sys,json,tempfile,unittest,wave,math,struct,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import va
from audio_analysis.preprocess import prepare_audio,inspect_wav
from audio_analysis.alignment import normalize_segments,align_transcript
from audio_analysis.vad import detect_speech_segments
from audio_analysis.asr import transcribe_speech_segments
from audio_analysis.pipeline import analyze
from audio_analysis.evidence import validate

SOURCE='youtube:abcdefghijk'
class Audio(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.store=va.Store(self.root/'data',self.root/'cache');self.session=self.store.create('audio','test',['https://youtu.be/abcdefghijk'])
  self.wav=self.root/'input.wav';self.make(self.wav,48000,2,1,False)
  recipe=va.digest(['fixture']);self.store.put(recipe,'audio',self.wav);self.store.attach(self.session,self.session['sources'][SOURCE],'audio',recipe);self.key=self.store.resolve(recipe)
 def tearDown(self):self.store.db.close();self.tmp.cleanup()
 def make(self,path,rate=16000,channels=1,seconds=1,tone=False):
  with wave.open(str(path),'wb') as w:
   w.setnchannels(channels);w.setsampwidth(2);w.setframerate(rate)
   w.writeframes(b''.join(struct.pack('<h',round(1000*math.sin(i*440*2*math.pi/rate)) if tone else 0)*channels for i in range(round(rate*seconds))))
 def test_conversion_resampling_protection_cache(self):
  before=va.sha(self.wav);p,meta=prepare_audio(self.wav,self.store)
  self.assertEqual(inspect_wav(p),1);self.assertEqual(meta['sample_rate'],16000);self.assertEqual(va.sha(self.wav),before)
  with patch('audio_analysis.preprocess.va.run',side_effect=AssertionError('must hit cache')):self.assertEqual(prepare_audio(self.wav,self.store)[0],p)
  self.make(self.wav,48000,2,1,True);self.assertNotEqual(prepare_audio(self.wav,self.store)[1]['recipe'],meta['recipe'])
 def test_ffmpeg_format(self):
  compressed=self.root/'input.flac';va.run([va.ffmpeg(),'-v','error','-i',str(self.wav),str(compressed)])
  self.assertAlmostEqual(inspect_wav(prepare_audio(compressed,self.store)[0]),1)
 def test_overlap_clamp(self):
  result=normalize_segments([dict(start_seconds=-1,end_seconds=2),dict(start_seconds=1,end_seconds=4),dict(start_seconds=8,end_seconds=11)],10)
  self.assertEqual([(x['start_seconds'],x['end_seconds']) for x in result],[(0,4),(8,10)])
 def test_numeric_rejection(self):
  for bad in [True,float('nan'),'35']:
   with self.assertRaises(ValueError):normalize_segments([dict(start_seconds=bad,end_seconds=3)],4)
 def test_alignment(self):
  result,warning=align_transcript([dict(start=2,end=8,text='hello')],35,13,120)
  self.assertEqual((result[0]['start'],result[0]['end']),(37,43));self.assertFalse(warning)
 def test_alignment_bounds_empty_overlap(self):
  result,warning=align_transcript([dict(start=-1,end=3,text='a'),dict(start=2,end=9,text='b'),dict(start=0,end=1,text=' ')],5,5,10)
  self.assertEqual([(s['start'],s['end']) for s in result],[(5,8),(8,10)]);self.assertTrue(warning)
 def test_silence_vad_real(self):
  result=detect_speech_segments(self.wav,dict(store=self.store))
  self.assertFalse(result['speech_detected']);self.assertEqual(result['segments'],[])
 def test_short_silence(self):
  self.make(self.wav,16000,1,.01)
  self.assertFalse(detect_speech_segments(self.wav)['speech_detected'])
 def test_no_speech_does_not_load_asr(self):
  p,_=prepare_audio(self.wav,self.store)
  with patch('audio_analysis.asr.identity',side_effect=AssertionError('no model')):
   self.assertEqual(transcribe_speech_segments(p,[],dict(store=self.store))['segments'],[])
 def test_missing_model(self):
  p,_=prepare_audio(self.wav,self.store)
  cfg=dict(store=self.store,runtime=dict(models={'whisper.cpp':{'base':str(self.root/'absent')}},whisper_cli='absent'))
  with self.assertRaises(FileNotFoundError):transcribe_speech_segments(p,[dict(start_seconds=0,end_seconds=1)],cfg)
 def test_disabled_unchanged(self):
  before=self.session['revision']
  with self.assertRaisesRegex(ValueError,'enabled=false'):analyze(self.store,self.session,SOURCE,self.key,0)
  self.assertEqual(before,self.session['revision']);self.assertNotIn('audio_analyses',self.session)
 def test_unowned_rejected(self):
  with self.assertRaises(ValueError):analyze(self.store,self.session,SOURCE,'0'*64,0,{'enabled':True})
 def test_source_bounds(self):
  self.session['sources'][SOURCE]['metadata']['duration']=10
  with self.assertRaisesRegex(ValueError,'original source'):analyze(self.store,self.session,SOURCE,self.key,20,{'enabled':True})
 def test_evidence_session_cache_invalidation(self):
  old=list(self.session['evidence']);config={'enabled':True,'asr_enabled':False}
  out=analyze(self.store,self.session,SOURCE,self.key,35,config)
  for record in out['evidence']:self.assertEqual(validate(record)['session_id'],self.session['id']);self.assertFalse(record['human_confirmation']['confirmed'])
  self.assertEqual(self.session['evidence'],old);self.assertEqual(len(self.session['audio_analyses']),1)
  revision=self.session['revision'];again=analyze(self.store,self.session,SOURCE,self.key,35,config)
  self.assertTrue(again['cache_hit']);self.assertEqual(revision,self.session['revision'])
  changed=analyze(self.store,self.session,SOURCE,self.key,35,config|{'vad':{'threshold':.6}})
  self.assertNotEqual(out['recipe'],changed['recipe']);self.assertEqual(len(self.session['audio_analyses']),2)
  broken=json.loads(json.dumps(out['evidence'][0]));broken['human_confirmation']['confirmed']=True
  with self.assertRaises(ValueError):validate(broken)
 def test_vad_failure_fallback(self):
  fake=dict(model=dict(name='synthetic ASR',version='fixture',revision=None,weights_sha256='a'*64,backend='whisper.cpp',backend_version='fixture',code_license='MIT',weights_license='MIT'),status='completed',segments=[dict(start=0,end=1,text='known fake ASR')],raw_output=[],limitations=['test only'])
  self.make(self.wav,16000,1,1,True)
  with patch('audio_analysis.pipeline.vad.detect_speech_segments',side_effect=RuntimeError('test failure')),patch('audio_analysis.pipeline.asr.transcribe_speech_segments',return_value=fake) as worker:
   out=analyze(self.store,self.session,SOURCE,self.key,0,{'enabled':True})
   self.assertIsNone(worker.call_args.args[1]);self.assertEqual(out['status'],'needs_review')
   self.assertEqual(out['evidence'][0]['status'],'failed');self.assertIsNone(out['evidence'][0]['result'])
 def test_asr_failure_is_not_no_speech(self):
  with patch('audio_analysis.pipeline.asr.transcribe_speech_segments',side_effect=RuntimeError('injected')):
   out=analyze(self.store,self.session,SOURCE,self.key,0,{'enabled':True})
   self.assertEqual(out['evidence'][1]['status'],'failed');self.assertEqual(out['status'],'needs_review')
 def test_fallback_digital_zero(self):
  p,_=prepare_audio(self.wav,self.store)
  out=transcribe_speech_segments(p,None,{'store':self.store})
  self.assertEqual(out['segments'],[]);self.assertTrue(out['fallback'])
 def test_raw_tamper_detection(self):
  out=analyze(self.store,self.session,SOURCE,self.key,0,{'enabled':True,'asr_enabled':False})
  record=out['evidence'][0];Path(record['raw_output']['path']).write_text('tampered')
  with self.assertRaises(ValueError):validate(record)
 def test_asr_chunk_cache_offset_and_invalidation(self):
  from audio_analysis import asr
  p,_=prepare_audio(self.wav,self.store);prepare_audio(p,self.store)
  model=dict(backend='whisper.cpp',name='fixture',version='1',weights_sha256='a'*64)
  runtime=va.load_runtime();fixture=self.root/'fake-whisper';fixture.write_text('fixture, not a model');runtime['whisper_cli']=str(fixture);config=dict(store=self.store,runtime=runtime,language='en')
  def worker(command,**kwargs):
   dest=Path(command[command.index('--output')+1]);va.write(dest,dict(segments=[dict(start=.1,end=.5,text='fixture')],raw_backend_output={'result':{'language':'en'}}))
   from types import SimpleNamespace
   return SimpleNamespace(returncode=0,stderr='')
  spans=[dict(start_seconds=.2,end_seconds=.8),dict(start_seconds=.3,end_seconds=.7)]
  with patch('audio_analysis.asr.identity',return_value=(model,Path(runtime['models']['whisper.cpp']['base']))),patch('audio_analysis.asr.subprocess.run',side_effect=worker) as execute:
   first=asr.transcribe_speech_segments(p,spans,config)
   self.assertAlmostEqual(first['segments'][0]['start'],.3);self.assertAlmostEqual(first['segments'][0]['end'],.7)
   self.assertEqual(asr.transcribe_speech_segments(p,spans,config)['cache_hits'],1);self.assertEqual(execute.call_count,1)
   asr.transcribe_speech_segments(p,spans,config|dict(language='zh'));self.assertEqual(execute.call_count,2)
 def test_model_unavailable_vad_fallback_and_retry(self):
  with patch('audio_analysis.pipeline.vad.detect_speech_segments',side_effect=FileNotFoundError('missing model')):
   first=analyze(self.store,self.session,SOURCE,self.key,0,{'enabled':True})
   second=analyze(self.store,self.session,SOURCE,self.key,0,{'enabled':True})
   self.assertFalse(first['cache_hit']);self.assertFalse(second['cache_hit'])
   self.assertEqual(first['evidence'][1]['status'],'skipped')
 def test_bad_config_not_fallback(self):
  with self.assertRaisesRegex(ValueError,'Unknown VAD'):analyze(self.store,self.session,SOURCE,self.key,0,{'enabled':True,'vad':{'typo':1}})
 def test_schema_rejects_bad_model_and_flags(self):
  out=analyze(self.store,self.session,SOURCE,self.key,0,{'enabled':True,'asr_enabled':False})
  for modify in [lambda r:r['model'].update(version=''),lambda r:r['human_confirmation'].update(confirmed='false'),lambda r:r.update(extra='bad')]:
   bad=json.loads(json.dumps(out['evidence'][0]));modify(bad)
   with self.assertRaises(ValueError):validate(bad)
 def test_cli_opt_in_and_default_off(self):
  command=[sys.executable,str(va.ROOT/'scripts/va.py'),'--data',str(self.store.data),'--cache',str(self.store.cache),'audio-analyze',self.session['id'],SOURCE,'--artifact-key',self.key,'--source-offset','0']
  blocked=subprocess.run(command,capture_output=True,text=True)
  self.assertEqual(blocked.returncode,2);self.assertIn('enabled=false',blocked.stderr)
  self.assertEqual(self.store.session(self.session['id'])['revision'],self.session['revision'])
  config=self.root/'config.json';va.write(config,{'asr_enabled':False})
  enabled=subprocess.run(command+['--enable','--config',str(config)],capture_output=True,text=True)
  self.assertEqual(enabled.returncode,0,enabled.stderr)
  self.assertEqual(json.loads(enabled.stdout)['evidence'][0]['result']['speech_detected'],False)
  self.assertIs(va.load_runtime()['audio_analysis']['enabled'],False)
if __name__=='__main__':unittest.main()
