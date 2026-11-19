"""Formal CLI + external orchestration lifecycle, entirely offline."""
import copy
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import va
import research_ledger as ledger


class ResearchLedger(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=va.Store(self.root/'data',self.root/'cache')
        self.addCleanup(self.store.db.close)
        self.s=self.store.create('fixture','指定裝置同場測試',['https://youtu.be/abcdefghijk'])
        self.s['gaps']=['缺同裝置、同環境的原始實測'];self.store.save(self.s)
        self.sid='youtube:abcdefghijk'
        path=self.root/'transcript.json';va.write(path,dict(synthetic=True,text='fixture only'))
        recipe=va.digest(['research-test']);self.store.put(recipe,'transcript',path)
        self.store.attach(self.s,self.s['sources'][self.sid],'transcript',recipe)
        self.key=self.s['sources'][self.sid]['artifacts']['transcript']

    def spec(self,n=5,provider='web',**cost):
        budget=dict(query_groups=1,max_new_sources=0,max_new_candidates=0,cache_bytes=4096,paid_api_calls=0);budget.update(cost)
        return dict(queries=[dict(gap_id=ledger.gaps(self.s)[0]['gap_id'],provider=provider,query=f'fixture original test {i}',
                                  purpose='找可定位同場測試',expected_value='可能補足測試條件，尚未取得',budget=copy.deepcopy(budget)) for i in range(n)])

    def plan(self,**kwargs):return ledger.make_plan(self.store,self.s,self.spec(**kwargs))
    def reserve(self,index=0):
        r=ledger.active(self.s);return ledger.reserve(self.store,self.s,r['queries'][index]['query_id'])['reservation']
    def found(self,token):return ledger.search_result(self.store,self.s,token,dict(status='completed',result_count=1))
    def item(self,claim='synthetic fixture result',sid=None):
        return dict(source_id=sid or self.sid,claim=claim,claim_type='test_presented',support='low',reason='fixture',conditions='synthetic',
                    limitations='不支持真實產品',product_version='fixture',verification='synthetic original content',artifact_key=self.key,start=1,end=2,excerpt='fixture')
    def add(self,token,claim='synthetic fixture result',sid=None):return va.add_evidence(self.store,self.s,self.item(claim,sid),token)
    def review(self,eid,**kwargs):
        review=dict(evidence_id=eid,gap_id=ledger.gaps(self.s)[0]['gap_id'],basis='source_content_review',addresses_gap=True,
                    relevance_reason='synthetic original test matches synthetic gap',independence_basis='reviewed_original_content',independence_reason='合成原始內容')
        review.update(kwargs);return dict(reviews=[review])
    def cli(self,*args):
        return subprocess.run([sys.executable,'-B',str(va.ROOT/'scripts/va.py'),'--data',str(self.store.data),'--cache',str(self.store.cache),*args],text=True,capture_output=True)

    def test_plan_round_stored_in_session_and_no_evidence_changes(self):
        before=copy.deepcopy(self.s['evidence']);r=self.plan()
        self.assertEqual(self.store.session(self.s['id'])['research_rounds'][-1],r)
        self.assertEqual(self.s['evidence'],before);self.assertEqual(self.s['gaps'],['缺同裝置、同環境的原始實測'])
        self.assertEqual(r['limits']['auto_sources'],3)

    def test_fifth_query_blocked_and_no_refund_after_reload(self):
        self.plan()
        for i in range(4):
            token=self.reserve(i);self.found(token);eid=self.add(token,'unique '+str(i))
            result=ledger.complete(self.store,self.s,token,self.review(eid));self.assertEqual(result['effective_evidence_delta'],1)
            self.s=self.store.session(self.s['id'])
        with self.assertRaisesRegex(ValueError,'query_budget_exhausted'):self.reserve(4)
        self.assertEqual(ledger.active(self.store.session(self.s['id']))['queries_used'],4)

    def test_zero_value_stops_before_next_search(self):
        self.plan();token=self.reserve();self.found(token)
        self.assertEqual(ledger.complete(self.store,self.s,token,dict(reviews=[]))['stop_reason'],'zero_new_value')
        with self.assertRaisesRegex(ValueError,'zero_new_value'):self.reserve(1)
        with self.assertRaisesRegex(ValueError,'已停止'):self.plan()

    def test_metadata_does_not_immediately_count_as_evidence(self):
        self.plan();token=self.reserve();self.found(token)
        self.assertEqual(ledger.active(self.s)['queries'][0]['status'],'awaiting_evidence')
        with self.assertRaisesRegex(ValueError,'previous_query_requires_review'):self.reserve(1)

    def test_llm_confidence_cannot_promote_new_evidence(self):
        self.plan();token=self.reserve();self.found(token);eid=self.add(token)
        result=ledger.complete(self.store,self.s,token,self.review(eid,basis='llm_confidence',confidence=1.0))
        self.assertEqual(result['effective_evidence_delta'],0)

    def test_unknown_independence_is_not_original(self):
        self.plan();token=self.reserve();self.found(token);eid=self.add(token)
        result=ledger.complete(self.store,self.s,token,self.review(eid,independence_basis='unknown'))
        self.assertEqual(result['effective_evidence_delta'],1);self.assertEqual(result['independent_source_delta'],0)

    def test_repost_is_not_independent_even_when_claimed_original(self):
        root=self.sid;repost='youtube:12345678901'
        self.s['sources'][repost]=dict(id=repost,url='https://youtu.be/12345678901',origin_source_id=root,selected=True,
                                       role='seed',metadata={},artifacts={'transcript':self.key})
        self.store.save(self.s);self.plan();token=self.reserve();self.found(token);eid=self.add(token,sid=repost)
        result=ledger.complete(self.store,self.s,token,self.review(eid))
        self.assertEqual(result['independent_source_delta'],0)

    def test_duplicate_evidence_under_new_id_no_new_value(self):
        va.add_evidence(self.store,self.s,self.item())
        self.plan();token=self.reserve();self.found(token);eid=self.add(token)
        self.assertEqual(ledger.complete(self.store,self.s,token,self.review(eid))['effective_evidence_delta'],0)

    def test_previous_evidence_cannot_be_reviewed_as_new(self):
        old=va.add_evidence(self.store,self.s,self.item());self.plan();token=self.reserve();self.found(token)
        with self.assertRaisesRegex(ValueError,'舊證據'):ledger.complete(self.store,self.s,token,self.review(old))

    def test_mutation_of_old_evidence_detected(self):
        va.add_evidence(self.store,self.s,self.item());self.plan();token=self.reserve();self.found(token)
        self.s['evidence'][0]['claim']='changed'
        with self.assertRaisesRegex(ValueError,'舊 Evidence'):ledger.complete(self.store,self.s,token,dict(reviews=[]))

    def test_wrong_gap_or_unverified_evidence_no_gain(self):
        self.plan();token=self.reserve();self.found(token);eid=self.add(token)
        self.assertEqual(ledger.complete(self.store,self.s,token,self.review(eid,gap_id='other'))['effective_evidence_delta'],0)

    def test_cancel_persists_across_process_and_blocks_late_evidence(self):
        self.plan();token=self.reserve();self.found(token)
        result=self.cli('query-cancel',self.s['id'],token,'--reason','使用者取消')
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaisesRegex(ValueError,'cancelled'):self.add(token)
        self.assertEqual(self.s['evidence'],[])
        with self.assertRaisesRegex(ValueError,'cancelled'):ledger.complete(self.store,self.s,token,dict(reviews=[]))

    def test_cancel_during_discover_bypasses_writer_lock_and_discards_response(self):
        self.plan(provider='yt-dlp YouTube',max_new_candidates=1);token=self.reserve()
        query=ledger.active(self.s)['queries'][0]['query'];owner=self;calls=[]
        class YDL:
            def __init__(self,opts):pass
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def extract_info(self,*a,**k):
                calls.append(1)
                result=owner.cli('query-cancel',owner.s['id'],token,'--reason','cancel during network')
                owner.assertEqual(result.returncode,0,result.stderr)
                return dict(entries=[dict(id='12345678901',title='late fixture')])
        cache_before={str(p):p.read_bytes() for p in self.store.cache.rglob('*') if p.is_file()}
        with (self.store.data/'writer.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch('yt_dlp.YoutubeDL',YDL),self.assertRaisesRegex(ValueError,'cancelled'):
                va.discover(self.store,self.s,[query],1,reservation=token)
        self.assertEqual(calls,[1]);self.assertNotIn('youtube:12345678901',self.s['sources'])
        self.assertEqual(cache_before,{str(p):p.read_bytes() for p in self.store.cache.rglob('*') if p.is_file()})
        self.assertEqual(ledger.active(self.s)['queries_used'],1)

    def test_discover_requires_reservation_before_network(self):
        with patch.dict(sys.modules,{'yt_dlp':None}),self.assertRaisesRegex(ValueError,'query-reserve'):
            va.discover(self.store,self.s,['raw'],1)

    def test_discover_matches_provider_and_exact_single_query(self):
        self.plan();token=self.reserve()
        with patch.dict(sys.modules,{'yt_dlp':None}),self.assertRaisesRegex(ValueError,'單一查詢'):
            va.discover(self.store,self.s,['query1','query2'],1,reservation=token)

    def test_discover_success_goes_to_review_and_preserves_search_cache(self):
        self.plan(provider='yt-dlp YouTube',max_new_candidates=1);token=self.reserve()
        query=ledger.active(self.s)['queries'][0]['query']
        class YDL:
            def __init__(self,opts):pass
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def extract_info(self,*a,**k):return dict(entries=[dict(id='12345678901',title='fixture')])
        with patch('yt_dlp.YoutubeDL',YDL):self.assertEqual(va.discover(self.store,self.s,[query],1,reservation=token),['youtube:12345678901'])
        self.assertEqual(ledger.active(self.s)['queries'][0]['status'],'awaiting_evidence')
        self.assertTrue(self.s['searches'][0]['query']==query)
        self.assertTrue(list(self.store.cache.glob('search/*.json')))

    def test_discover_failure_consumes_budget_no_retry(self):
        self.plan(provider='yt-dlp YouTube');token=self.reserve();query=ledger.active(self.s)['queries'][0]['query']
        with patch('yt_dlp.YoutubeDL',side_effect=TimeoutError('fixture')),self.assertRaises(TimeoutError):
            va.discover(self.store,self.s,[query],1,reservation=token)
        self.assertEqual(ledger.active(self.s)['queries_used'],1)
        self.assertEqual(ledger.active(self.s)['stop_reason'],'provider_failed')

    def test_source_candidate_cache_preflight_exhaustion(self):
        for field,cost,reason in [('max_new_sources',4,'source'),('max_new_candidates',31,'candidate'),('cache_bytes',va.LIMIT,'cache')]:
            with self.subTest(field=field):
                clone=copy.deepcopy(self.s)
                ledger.make_plan(self.store,clone,self.spec(**{field:cost}))
                with self.assertRaisesRegex(ValueError,reason+'_budget_exhausted'):
                    ledger.reserve(self.store,clone,ledger.active(clone)['queries'][0]['query_id'])

    def test_source_gate_enforces_query_cap_before_select(self):
        ids=va.import_candidates(self.store,self.s,[dict(url='https://youtu.be/12345678901')])
        self.plan();self.reserve();
        with self.assertRaisesRegex(ValueError,'來源增量'):va.select(self.store,self.s,ids,False,'fixture','automatic')
        self.assertFalse(self.s['sources'][ids[0]]['selected'])

    def test_candidate_receipt_cannot_exceed_reservation(self):
        self.plan();token=self.reserve()
        with self.assertRaisesRegex(ValueError,'候選增量'):
            va.import_candidates(self.store,self.s,[dict(url='https://youtu.be/12345678901')],token)
        self.assertNotIn('youtube:12345678901',self.s['sources'])

    def test_old_round_four_queries_migrated_without_reset(self):
        old=dict(kind='automatic_gap_followup',provider='web search',queries=['old '+str(i) for i in range(4)],
                 budget=dict(max_new_queries=4,queries_used=4),stop_reason='original unchanged')
        self.s['research_rounds']=[copy.deepcopy(old)];self.store.save(self.s)
        r=self.plan();self.assertEqual(r['queries_used'],4);self.assertEqual(self.s['research_rounds'][0],old)
        with self.assertRaisesRegex(ValueError,'query_budget_exhausted'):self.reserve()

    def test_legacy_searches_and_smaller_limit_migrated(self):
        self.s['searches']=[dict(query='previous',provider='web')]
        spec=self.spec();spec['max_new_queries']=1
        r=ledger.make_plan(self.store,self.s,spec)
        self.assertEqual(r['queries_used'],1)
        with self.assertRaisesRegex(ValueError,'query_budget_exhausted'):self.reserve()

    def test_plan_does_not_reset_and_new_round_requires_user_reason(self):
        self.plan();token=self.reserve()
        with self.assertRaisesRegex(ValueError,'使用者'):ledger.make_plan(self.store,self.s,self.spec(),new_round=True,actor='automatic',reason='self')
        with self.assertRaisesRegex(ValueError,'未完成'):ledger.make_plan(self.store,self.s,self.spec(),new_round=True,actor='user',reason='user request')
        ledger.search_result(self.store,self.s,token,dict(status='failed',reason='fixture'))
        r=ledger.make_plan(self.store,self.s,self.spec(),new_round=True,actor='user',reason='user request')
        self.assertEqual(r['queries_used'],0);self.assertEqual(len(self.s['research_rounds']),2)

    def test_plan_duplicate_fingerprints_and_paid_budget_rejected(self):
        spec=self.spec();spec['queries'][1]['query']=spec['queries'][0]['query']
        with self.assertRaisesRegex(ValueError,'重複'):ledger.make_plan(self.store,self.s,spec)
        with self.assertRaisesRegex(ValueError,'付費'):ledger.make_plan(self.store,self.s,self.spec(paid_api_calls=1))
        spec=self.spec();spec['max_new_queries']=5
        with self.assertRaises(ValueError):ledger.make_plan(self.store,self.s,spec)

    def test_normalization_and_duplicate_resume(self):
        self.assertEqual(ledger.fingerprint('WEB','Ａ  b'),ledger.fingerprint('web','a b'))
        self.assertNotEqual(ledger.fingerprint('web','風噪'),ledger.fingerprint('web','wind noise'))
        self.plan();token=self.reserve();self.found(token);eid=self.add(token)
        ledger.complete(self.store,self.s,token,self.review(eid))
        self.s=self.store.session(self.s['id'])
        with self.assertRaisesRegex(ValueError,'duplicate_query'):self.reserve()

    def test_status_readonly_and_cancel_projection(self):
        self.plan();token=self.reserve();ledger.cancel(self.store,self.s,token,'fixture')
        path=self.store.data/'sessions'/self.s['id']/'session.json';before=path.read_bytes()
        self.assertEqual(ledger.status(self.store,self.s)['round']['stop_reason'],'cancelled')
        self.assertEqual(path.read_bytes(),before)

    def test_new_question_without_gaps_has_virtual_gap(self):
        self.s['gaps']=[]
        self.assertEqual(ledger.gaps(self.s)[0]['text'],self.s['question'])
        self.assertIsNone(ledger.gaps(self.s)[0]['original_index']);self.assertEqual(self.s['gaps'],[])

    def test_interactive_legacy_no_mode_migration(self):
        self.s.pop('research_policy')
        with self.assertRaisesRegex(ValueError,'互動'):self.plan()

    def test_cli_external_lifecycle_across_processes(self):
        spec=self.root/'plan.json';va.write(spec,self.spec())
        planned=self.cli('research-plan',self.s['id'],str(spec));self.assertEqual(planned.returncode,0,planned.stderr)
        r=json.loads(planned.stdout);qid=r['queries'][0]['query_id']
        reserved=self.cli('query-reserve',self.s['id'],qid);self.assertEqual(reserved.returncode,0,reserved.stderr)
        token=json.loads(reserved.stdout)['reservation']
        result=self.root/'result.json';va.write(result,dict(status='completed',result_count=0))
        found=self.cli('query-search-result',self.s['id'],token,str(result));self.assertEqual(found.returncode,0,found.stderr)
        receipt=self.root/'receipt.json';va.write(receipt,dict(reviews=[]))
        done=self.cli('query-complete',self.s['id'],token,str(receipt));self.assertEqual(done.returncode,0,done.stderr)
        self.assertEqual(json.loads(done.stdout)['stop_reason'],'zero_new_value')
        status=self.cli('research-status',self.s['id']);self.assertEqual(status.returncode,0,status.stderr)
        self.assertEqual(json.loads(status.stdout)['round']['queries_used'],1)

    def test_new_round_preserves_smaller_query_cap(self):
        spec=self.spec();spec['max_new_queries']=1
        ledger.make_plan(self.store,self.s,spec);token=self.reserve();self.found(token)
        ledger.complete(self.store,self.s,token,dict(reviews=[]))
        r=ledger.make_plan(self.store,self.s,self.spec(),new_round=True,actor='user',reason='continue within same bounds')
        self.assertEqual(r['limits']['query_groups'],1)

    def test_changed_gap_requires_review_before_completion(self):
        self.plan();token=self.reserve();self.found(token);self.s['gaps']=['changed']
        with self.assertRaisesRegex(ValueError,'缺口已變更'):ledger.complete(self.store,self.s,token,dict(reviews=[]))

    def test_completed_query_cannot_be_cancelled(self):
        self.plan();token=self.reserve();self.found(token)
        ledger.complete(self.store,self.s,token,dict(reviews=[]))
        result=self.cli('query-cancel',self.s['id'],token,'--reason','too late')
        self.assertEqual(result.returncode,2)

    def test_cli_evidence_receipt_with_real_token(self):
        self.plan();token=self.reserve();self.found(token)
        item_file=self.root/'evidence.json';va.write(item_file,self.item())
        added=self.cli('evidence',self.s['id'],str(item_file),'--reservation',token)
        self.assertEqual(added.returncode,0,added.stderr);eid=json.loads(added.stdout)
        receipt=self.root/'review.json';va.write(receipt,self.review(eid))
        done=self.cli('query-complete',self.s['id'],token,str(receipt))
        self.assertEqual(done.returncode,0,done.stderr)
        self.assertEqual(json.loads(done.stdout)['effective_evidence_delta'],1)
        saved=self.store.session(self.s['id'])
        self.assertEqual(saved['evidence'][0]['query_reservation'],token)

    def test_keyboard_interrupt_stops_without_refund(self):
        self.plan(provider='yt-dlp YouTube');token=self.reserve();query=ledger.active(self.s)['queries'][0]['query']
        with patch('yt_dlp.YoutubeDL',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):
            va.discover(self.store,self.s,[query],1,reservation=token)
        self.assertEqual(ledger.active(self.s)['stop_reason'],'interrupted_requires_review')
        self.assertEqual(ledger.active(self.s)['queries_used'],1)

    def test_plan_extension_cannot_modify_or_reset_reserved_query(self):
        self.plan();token=self.reserve();self.found(token);eid=self.add(token)
        ledger.complete(self.store,self.s,token,self.review(eid))
        spec=self.spec();spec['queries'][0]['purpose']='changed'
        with self.assertRaisesRegex(ValueError,'不可原地修改'):ledger.make_plan(self.store,self.s,spec)
        ledger.make_plan(self.store,self.s,self.spec())
        self.assertEqual(ledger.active(self.s)['queries_used'],1)

    def test_later_summary_does_not_hide_exhausted_legacy_round(self):
        self.s['research_rounds']=[dict(queries=['q'+str(i) for i in range(4)],provider='web',budget=dict(queries_used=4)),dict(kind='summary',notes='no new searches')]
        r=self.plan();self.assertEqual(r['queries_used'],4)
        self.assertEqual(r['migration']['legacy_index'],0)

    def test_external_paid_usage_cannot_be_reported_as_zero(self):
        self.plan();token=self.reserve()
        with self.assertRaisesRegex(ValueError,'付費'):
            ledger.search_result(self.store,self.s,token,dict(status='completed',result_count=1,paid_api_calls=1))


if __name__=='__main__':unittest.main()
