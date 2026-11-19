"""Backend acceptance: real Store/report lifecycle; only external CLI is mocked."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import va
import antigravity_backend as ag


class Backend(unittest.TestCase):
    def setUp(self):
        self.models=patch.object(ag,'available_models',return_value={ag.PRIMARY,*ag.SECONDARY});self.models.start();self.addCleanup(self.models.stop)
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.store=va.Store(self.base/'data',self.base/'cache')
        self.s=self.store.create('耳機講評','作者如何描述通話限制？',['https://www.youtube.com/watch?v=abcdefghijk'])
        p=self.base/'transcript.json';va.write(p,{'segments':[{'start':1,'end':3,'text':'作者表示室內清楚；戶外沒有測試。'}]})
        recipe=va.digest(['fixture']);self.store.put(recipe,'transcript',p)
        src=self.s['sources']['youtube:abcdefghijk'];self.store.attach(self.s,src,'transcript',recipe)
        key=src['artifacts']['transcript']
        e=va.add_evidence(self.store,self.s,dict(source_id=src['id'],claim='作者表示室內通話清楚',
            claim_type='reviewer_opinion',support='low',reason='只有講評',conditions='室內',limitations='無戶外原音',
            product_version='未確認',verification='字幕核對',artifact_key=key,start=1,end=3))
        eid=self.s['evidence'][0]['id'];citation=f'[E:{eid}]'
        self.analysis=dict(summary='作者表示室內清楚 '+citation,topics='作者講評 '+citation,
            comparison='缺少同場對照 '+citation,limitations='僅字幕，無戶外原音。',conclusion='證據不足',evidence_ids=[eid],
            deep=dict(background='研究作者講評，未聆聽原音。',cross_validation='僅一位作者意見 '+citation,
                scenarios='戶外不外推 '+citation,recommendation='保留缺口 '+citation),
            claims_analysis=[dict(evidence_id=eid,source_id=src['id'],claim_type='reviewer_opinion',
                fact_or_opinion='opinion',assessment='作者意見；字幕不能證明實際通話品質。')])

    def tearDown(self):
        self.store.db.close();self.temp.cleanup()

    def result(self,data=None,**kwargs):
        raw=dict(status='SUCCESS',structured_output=data or self.analysis,usage={'input_tokens':100,'output_tokens':50})
        raw.update(kwargs)
        return SimpleNamespace(returncode=0,stdout=json.dumps(raw),stderr='')

    def finish_as_codex(self):
        # Simulates the current-session orchestration receipt, never invokes a Codex API.
        a=self.base/'final.json';va.write(a,self.analysis)
        r=self.base/'review.json';va.write(r,dict(actor='current_codex_session',complete=True,
            analysis_hash=va.digest(self.analysis),session_fingerprint=ag.fingerprint(self.s),
            source_support='核對 claim 與字幕摘錄，僅作者室內講評。',opinion_inference='保留 opinion，沒有性能事實或未標示外推。',
            comparability='沒有第二來源，不能排序。',limitations='無戶外原音，未聆聽。',remaining_work='已以證據不足完成報告，沒有新搜尋。'))
        return ag.finish(self.store,self.s,a,r,'deep')

    def test_normal_end_to_end_report(self):
        before=copy.deepcopy(self.s)
        with patch.object(ag,'invoke',return_value=self.result()) as call:
            state=ag.delegate(self.store,self.s);ag.delegate(self.store,self.s)
        self.assertEqual(call.call_count,1);self.assertEqual(self.s,before)
        self.assertEqual(state['status'],'awaiting_codex_review')
        path=self.finish_as_codex()['report']
        self.assertIn('接手：否',Path(path).read_text());self.assertEqual(state['usage']['input_tokens'],100)

    def test_failures_handoff_and_complete_report_no_retry(self):
        for failure,expected in [(SimpleNamespace(returncode=1,stdout='',stderr='quota exhausted'),'quota_exhausted'),
                                 (FileNotFoundError(),'cli_unavailable'),
                                 (SimpleNamespace(returncode=1,stdout='',stderr='429 rate limit'),'rate_limited'),
                                 (subprocess.TimeoutExpired('agy',1),'timeout'),
                                 (self.result(status='ERROR',error='login required'),'authentication_failed'),
                                 (self.result(data={**self.analysis,'summary':'假的 [E:deadbeef1234]'}),'validation_failed')]:
            with self.subTest(reason=expected):
                import shutil
                shutil.rmtree(ag.directory(self.store,self.s),ignore_errors=True)
                with patch.object(ag,'invoke',side_effect=failure if isinstance(failure,Exception) else None,
                                  return_value=failure) as call:
                    state=ag.delegate(self.store,self.s)
                    self.assertEqual(state['reason'],expected)
                    self.assertTrue(state['disabled']);self.assertNotIn('validated_analysis',state)
                    # Progress persists and subsequent changes do not reset the latch.
                    self.s['gaps'].append('保留缺口');self.store.save(self.s)
                    ag.delegate(self.store,self.s)
                    self.assertEqual(call.call_count,2 if expected=='quota_exhausted' else 1)
                path=self.finish_as_codex()['report']
                self.assertIn('接手：是；原因：'+expected,Path(path).read_text())
                ag.delegate(self.store,self.s)  # completed sticky failure
                self.assertEqual(va.read(ag.directory(self.store,self.s)/'state.json')['status'],'completed')

    def test_gemini_quota_switches_only_once_then_codex(self):
        quota=SimpleNamespace(returncode=1,stdout='',stderr='RESOURCE_EXHAUSTED quota')
        with patch.object(ag,'invoke',side_effect=[quota,self.result()]) as call:
            state=ag.delegate(self.store,self.s)
        self.assertEqual(call.call_count,2)
        self.assertEqual([c.args[-1] for c in call.call_args_list],[ag.PRIMARY,ag.SECONDARY[0]])
        self.assertEqual(state['status'],'awaiting_codex_review')
        self.assertEqual(state['events'][1]['status'],'model_switch')
        self.finish_as_codex()

    def test_both_quotas_exhausted_complete_codex(self):
        quota=SimpleNamespace(returncode=1,stdout='',stderr='quota exhausted')
        with patch.object(ag,'invoke',return_value=quota) as call:
            state=ag.delegate(self.store,self.s);ag.delegate(self.store,self.s)
        self.assertEqual(call.call_count,2);self.assertTrue(state['disabled'])
        self.assertEqual(state['events'][-1]['status'],'codex_handoff')
        self.assertIn('接手：是',Path(self.finish_as_codex()['report']).read_text())

    def test_unverified_or_unavailable_secondary_skipped(self):
        self.models.stop()
        with patch.object(ag,'available_models',return_value={ag.PRIMARY}),patch.object(ag,'invoke',return_value=SimpleNamespace(returncode=1,stdout='',stderr='quota exhausted')) as call:
            state=ag.delegate(self.store,self.s)
        self.assertEqual(call.call_count,1);self.assertEqual(state['status'],'codex_required')

    def test_disabled_only_locks_unfinished_delegation(self):
        with patch.object(ag,'invoke',side_effect=FileNotFoundError()):ag.delegate(self.store,self.s)
        self.finish_as_codex()
        self.s['gaps'].append('新缺口');self.store.save(self.s)
        with patch.object(ag,'invoke',return_value=self.result()) as call: state=ag.delegate(self.store,self.s)
        self.assertEqual(call.call_count,1);self.assertEqual(state['status'],'awaiting_codex_review')
        self.assertFalse(state['disabled']);self.assertEqual(state['disabled_scope'],'delegation')
        self.finish_as_codex()

    def test_preflight_environment_failure_records_safe_diagnostics(self):
        self.models.stop()
        failed=SimpleNamespace(returncode=1,stdout='',stderr=(
            'CLI failed to start - listen tcp 127.0.0.1:0: bind: operation not permitted\n'
            'Authorization: Bearer SECRET_VALUE https://example.test/?token=PRIVATE'))
        with patch.object(ag.shutil,'which',return_value='/safe/bin/agy'),patch.object(ag,'run_process',return_value=failed) as process,patch.object(ag,'invoke') as invoke:
            state=ag.delegate(self.store,self.s);ag.delegate(self.store,self.s)
        self.assertEqual(state['reason'],'cli_environment_blocked')
        self.assertIsNone(state['model']);self.assertIsNone(state['usage'])
        self.assertEqual(process.call_count,1);self.assertFalse(invoke.called)
        diag=state['cli_diagnostic']
        self.assertEqual(diag['stage'],'models_preflight');self.assertEqual(diag['exit_code'],1)
        self.assertEqual(diag['cli_path'],'/safe/bin/agy');self.assertEqual(diag['stdin'],'DEVNULL')
        persisted=va.read(ag.directory(self.store,self.s)/'state.json')
        self.assertNotIn('SECRET_VALUE',json.dumps(persisted));self.assertNotIn('PRIVATE',json.dumps(persisted))
        self.finish_as_codex()
        # Another Session is unaffected even while this attempt was disabled.
        other=copy.deepcopy(self.s);other['id']='abcdef123456'
        with patch.object(ag,'available_models',return_value={ag.PRIMARY}),patch.object(ag,'invoke',return_value=self.result()) as invoke:
            self.assertEqual(ag.delegate(self.store,other)['status'],'awaiting_codex_review')
        self.assertEqual(invoke.call_count,1)

    def test_launch_request_only_describes_host_authorization(self):
        before=copy.deepcopy(self.s)
        with patch.object(ag,'invoke') as invoke:
            request=ag.launch_request(self.store,self.s,60)
        self.assertFalse(invoke.called);self.assertEqual(self.s,before)
        self.assertEqual(request['tool_request']['sandbox_permissions'],'require_escalated')
        self.assertEqual(request['tool_request']['prefix_rule'][-2:],request['argv'][1:3])
        self.assertIn('RESEARCH_DATA_DIR='+str(self.store.data),request['environment'])
        self.assertIn('RESEARCH_CACHE_DIR='+str(self.store.cache),request['environment'])
        self.assertEqual(request['argv'][2:4],['analyze',self.s['id']])
        self.assertFalse((ag.directory(self.store,self.s)/'state.json').exists())
        va.write(ag.directory(self.store,self.s)/'state.json',dict(disabled=True,status='codex_required',reason='cli_environment_blocked'))
        self.assertEqual(ag.launch_request(self.store,self.s)['status'],'codex_required')

    def test_fixed_entry_rejects_arbitrary_execution_and_routes_analysis(self):
        import antigravity_entry as entry
        import contextlib,io
        for args in (['analyze',self.s['id'],'--data','/tmp/elsewhere'],['analyze','bad;touch /tmp/bad'],
                     ['analyze',self.s['id'],'--model','paid'],['shell','echo'],['analyze',self.s['id'],'--timeout','0']):
            with self.subTest(args=args),contextlib.redirect_stderr(io.StringIO()),patch.object(va,'main') as core:
                with self.assertRaises(SystemExit):entry.main(args)
                self.assertFalse(core.called)
        with patch.object(sys,'argv',['antigravity_entry.py']),patch.object(va,'main') as core:
            self.assertEqual(entry.main(['analyze',self.s['id'],'--timeout','60']),0)
            self.assertEqual(sys.argv[1:],['analyze',self.s['id'],'--timeout','60'])
            self.assertEqual(core.call_count,1)

    def test_host_denial_records_handoff_without_model_or_bypass(self):
        with patch.object(ag,'invoke') as invoke:
            state=ag.host_handoff(self.store,self.s,'authorization_denied')
            self.assertEqual(ag.host_handoff(self.store,self.s,'authorization_denied'),state)
            self.assertEqual(ag.launch_request(self.store,self.s)['status'],'codex_required')
        self.assertFalse(invoke.called);self.assertEqual(state['reason'],'authorization_denied')
        self.assertTrue(Path(state['resume_input']).exists())
        self.finish_as_codex()
        self.assertEqual(ag.launch_request(self.store,self.s)['status'],'completed')

    def test_fixed_entry_probe_never_calls_model(self):
        import antigravity_entry as entry
        import contextlib,io
        output=io.StringIO()
        with contextlib.redirect_stdout(output),patch.object(ag,'invoke') as invoke:
            self.assertEqual(entry.main(['probe']),0)
        self.assertFalse(invoke.called);self.assertEqual(json.loads(output.getvalue())['model_calls'],0)

    def test_missing_cli_preflight_is_reported_without_model_call(self):
        self.models.stop()
        with patch.object(ag.shutil,'which',return_value=None),patch.object(ag,'invoke') as invoke:
            state=ag.delegate(self.store,self.s)
        self.assertEqual(state['reason'],'cli_unavailable');self.assertFalse(invoke.called)
        self.assertEqual(state['cli_diagnostic']['stage'],'cli_resolution')
        self.assertIsNone(state['cli_diagnostic']['exit_code'])

    def test_no_evidence_codex_can_complete_quick(self):
        self.s['evidence']=[];self.store.save(self.s)
        with patch.object(ag,'invoke') as call:state=ag.delegate(self.store,self.s)
        self.assertFalse(call.called);self.assertEqual(state['reason'],'no_baseline_evidence')
        self.analysis['evidence_ids']=[];self.analysis['claims_analysis']=[]
        for key in ('summary','topics','comparison'):self.analysis[key]='缺少直接證據，無法判定。'
        for key in self.analysis['deep']:self.analysis['deep'][key]='沒有證據；無法外推。'
        ag.validate(self.analysis,self.s)
        # Deep still obeys its existing citation contract; Quick can disclose gaps.
        a=self.base/'empty.json';va.write(a,self.analysis)
        r=self.base/'empty-review.json';va.write(r,dict(actor='current_codex_session',complete=True,
            analysis_hash=va.digest(self.analysis),session_fingerprint=ag.fingerprint(self.s),
            **{k:'未取得直接證據，以證據不足結案。' for k in ('source_support','opinion_inference','comparability','limitations','remaining_work')}))
        result=ag.finish(self.store,self.s,a,r,'quick')
        self.assertTrue(Path(result['report']).exists())

    def test_validation_blindspots(self):
        variants=[None,[],{}, {**self.analysis,'deep':[]}, {**self.analysis,'claims_analysis':[]},
                  {**self.analysis,'summary':'無來源結論'}, {**self.analysis,'unexpected':'ignored?'}]
        bad=copy.deepcopy(self.analysis);bad['claims_analysis'][0]['source_id']='wrong';variants.append(bad)
        bad=copy.deepcopy(self.analysis);bad['claims_analysis'][0]['fact_or_opinion']='fact';variants.append(bad)
        bad=copy.deepcopy(self.analysis);bad['claims_analysis']*=2;variants.append(bad)
        bad=copy.deepcopy(self.analysis);bad['deep']['scenarios']='假 [E:invalid]';variants.append(bad)
        bad=copy.deepcopy(self.analysis);bad['evidence_ids']*=2;variants.append(bad)
        for payload in variants:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):ag.validate(payload,self.s)
        ag.validate(self.analysis,self.s)

    def test_report_review_gate_and_stale_review(self):
        with patch.object(ag,'invoke',return_value=self.result()): ag.delegate(self.store,self.s)
        p=self.base/'draft.json';va.write(p,self.analysis)
        with self.assertRaisesRegex(ValueError,'backend-finish'):va.report(self.store,self.s,p)
        r=self.base/'review.json';va.write(r,dict(actor='current_codex_session',analysis_hash=va.digest(self.analysis),complete=True,
            session_fingerprint='stale',**{k:'已核對' for k in ('source_support','opinion_inference','comparability','limitations','remaining_work')}))
        with self.assertRaisesRegex(ValueError,'stale'):ag.finish(self.store,self.s,p,r)

    def test_unattended_eof_and_timeout(self):
        # Real child processes prove no terminal input or human click is needed.
        result=ag.run_process([sys.executable,'-c','import sys; print(repr(sys.stdin.read()))'],1)
        self.assertEqual(result.stdout.strip(),"''")
        import time
        start=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            ag.run_process([sys.executable,'-c','import time; time.sleep(30)'],0.1)
        self.assertLess(time.monotonic()-start,2)

    def test_permission_and_payment_never_switch_models(self):
        for message in ('approval required','quota exceeded; payment required','interactive confirmation required'):
            with self.subTest(message=message):
                import shutil
                shutil.rmtree(ag.directory(self.store,self.s),ignore_errors=True)
                with patch.object(ag,'invoke',return_value=SimpleNamespace(returncode=1,stdout='',stderr=message)) as call:
                    state=ag.delegate(self.store,self.s)
                self.assertEqual(call.call_count,1)
                self.assertIn(state['reason'],('interaction_required','payment_required'))
                self.finish_as_codex()

    def test_interrupted_running_never_retried(self):
        va.write(ag.directory(self.store,self.s)/'state.json',dict(status='running',fingerprint=ag.fingerprint(self.s)))
        with patch.object(ag,'invoke') as call:
            state=ag.delegate(self.store,self.s)
            self.assertFalse(call.called);self.assertEqual(state['reason'],'interrupted')

    def test_cli_command_no_paid_api_and_guard(self):
        with patch.object(ag.shutil,'which',side_effect=lambda n:'/usr/bin/'+n),patch.object(ag,'run_process',return_value=self.result()) as run:
            ag.invoke('untrusted prompt',[self.store.data],10,ag.PRIMARY)
        args=run.call_args.args[0]
        self.assertEqual(Path(args[0]).name,'sandbox-exec')
        self.assertEqual(Path(args[3]).name,'agy')
        settings=json.loads(args[args.index('--settings')+1])
        self.assertFalse(settings['useG1Credits']);self.assertEqual(settings['modelProvider'],'')
        self.assertIn('mcp(*)',settings['permissions']['deny'])
        self.assertIn('--sandbox',args);self.assertIn('--disable-slash-commands',args)
        self.assertEqual(args[args.index('--print-timeout')+1],'10s')
        self.assertNotIn('--dangerously-skip-permissions',args)
        self.assertEqual(sum(Path(arg).name in ('agy','curl','python') for arg in args),1)
        self.assertNotEqual(run.call_args.kwargs['cwd'],str(va.ROOT))

if __name__=='__main__':unittest.main()
