import sys
import subprocess
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import va

URL='https://www.youtube.com/watch?v=abcdefghijk'
OTHER='https://www.youtube.com/watch?v=zyxwvutsrqp'

class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=Path(self.temp.name)
        self.store=va.Store(self.base/'data',self.base/'cache')
        self.s=self.store.create('耳機','戶外通話',[URL])

    def tearDown(self):
        self.store.db.close();self.temp.cleanup()

    def artifact(self,text='原始證據'):
        p=self.base/'input.json';va.write(p,dict(text=text))
        key=va.digest(['fixture'])
        self.store.put(key,'transcript',p)
        src=self.s['sources']['youtube:abcdefghijk']
        self.store.attach(self.s,src,'transcript',key)
        return src['artifacts']['transcript']

    def evidence(self,key):
        return dict(source_id='youtube:abcdefghijk',claim='作者認為通話清楚',claim_type='reviewer_opinion',
                    support='low',reason='只有講評',conditions='室內',limitations='無戶外原音',
                    product_version='未確認',verification='字幕核對',artifact_key=key,start=1,end=3)

    def test_identity_and_parts(self):
        self.assertEqual(va.identity(URL+'&t=30')[0],va.identity(URL)[0])
        self.assertNotEqual(va.identity('https://www.bilibili.com/video/BV123456?p=1')[0],
                            va.identity('https://www.bilibili.com/video/BV123456?p=2')[0])
        for bad in ['http://youtube.com/watch?v=abcdefghijk','https://youtube.com.evil/watch?v=abcdefghijk','https://user:pass@youtube.com/watch?v=abcdefghijk']:
            with self.assertRaises(ValueError):va.identity(bad)

    def test_unselected_gate_precedes_network(self):
        ids=va.import_candidates(self.store,self.s,[dict(url=OTHER)])
        with patch.dict(sys.modules,{'yt_dlp':None}):
            with self.assertRaisesRegex(ValueError,'未經使用者選取'):
                va.acquire(self.store,self.s,ids[0],'audio')
        va.select(self.store,self.s,ids,False,'使用者選擇第二支')
        self.assertTrue(self.store.allowed(self.s,ids[0]))
        va.import_candidates(self.store,self.s,[dict(url=OTHER+'&t=5')])
        self.assertTrue(self.store.allowed(self.s,ids[0]))
        va.select(self.store,self.s,ids,True,'使用者排除')
        with self.assertRaises(ValueError):self.store.allowed(self.s,ids[0])

    def test_automatic_selection_budget_and_audit(self):
        self.assertEqual(self.s['research_policy']['mode'], 'automatic')
        ids=va.import_candidates(self.store,self.s,[dict(url=OTHER)])
        va.configure_research(self.store,self.s,'automatic',1)
        va.select(self.store,self.s,ids,False,'新增同場通話實測','automatic')
        self.assertTrue(self.store.allowed(self.s,ids[0]))
        self.assertEqual(self.s['selection_events'][-1]['actor'],'automatic')
        va.select(self.store,self.s,ids,True,'無新增證據','automatic')
        other=va.import_candidates(self.store,self.s,[dict(url='https://youtu.be/12345678901')])
        with self.assertRaisesRegex(ValueError,'預算不足'):
            va.select(self.store,self.s,other,False,'另一測試','automatic')
        self.assertFalse(self.s['sources'][other[0]]['selected'])
        self.assertTrue(self.s['sources']['youtube:abcdefghijk']['selected'])

    def test_interactive_and_legacy_require_user(self):
        ids=va.import_candidates(self.store,self.s,[dict(url=OTHER)])
        for legacy in (False,True):
            va.configure_research(self.store,self.s,'interactive')
            if legacy:self.s.pop('research_policy')
            with self.assertRaisesRegex(ValueError,'等待使用者'):
                va.select(self.store,self.s,ids,False,'模型推薦','automatic')
        va.select(self.store,self.s,ids,False,'使用者選擇')
        self.assertTrue(self.store.allowed(self.s,ids[0]))

    def test_mode_switch_preserves_budget_and_materials(self):
        key=self.artifact();ids=va.import_candidates(self.store,self.s,[dict(url=OTHER)])
        va.configure_research(self.store,self.s,'automatic',1)
        va.select(self.store,self.s,ids,False,'新增測項','automatic')
        va.configure_research(self.store,self.s,'interactive')
        va.configure_research(self.store,self.s,'automatic')
        self.assertEqual(self.s['research_policy']['max_auto_sources'],1)
        self.assertTrue(self.store.artifact(self.s,key).exists())
        self.assertEqual(len([e for e in self.s['selection_events'] if e.get('actor')=='automatic']),1)

    def test_research_policy_cli(self):
        result=subprocess.run([sys.executable,str(va.ROOT/'scripts/va.py'),
            '--data',str(self.base/'data'),'--cache',str(self.base/'cache'),
            'research-policy',self.s['id'],'--mode','interactive'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['mode'],'interactive')
        self.assertEqual(self.store.session(self.s['id'])['research_policy']['mode'],'interactive')

    def test_candidate_batch_atomic(self):
        before=len(self.s['sources'])
        with self.assertRaises(ValueError):
            va.import_candidates(self.store,self.s,[dict(url=OTHER),dict(url='https://evil.test')])
        self.assertEqual(before,len(self.s['sources']))

    def test_incremental_cross_session_and_refresh(self):
        old=self.artifact()
        original=self.store.artifact(self.s,old).read_bytes()
        s2=self.store.create('其他研究','同產品其他問題',[URL])
        self.assertIsNotNone(self.store.get(old))
        new=self.artifact('更新後證據')
        self.assertNotEqual(new,old)
        self.assertEqual(self.store.artifact(self.s,old).read_bytes(),original)
        self.assertEqual(s2['evidence'],[])
        self.assertGreaterEqual(len(list((self.store.data/'sessions'/self.s['id']/'history').glob('*.json'))),3)

    def test_integrity_and_pinned_survival(self):
        key=self.artifact()
        cached=self.store.get(key)
        cached.unlink()
        self.assertIsNone(self.store.get(key))
        self.assertTrue(self.store.artifact(self.s,key).is_file())
        self.assertTrue(Path(self.store.pin(self.s,key)).is_file())
        self.store.artifact(self.s,key).write_text('corrupted')
        with self.assertRaises(ValueError):self.store.artifact(self.s,key)

    def test_evidence_closure_report_versions(self):
        key=self.artifact();item=self.evidence(key)
        eid=va.add_evidence(self.store,self.s,item)
        analysis=dict(summary=f'目前僅有作者講評 [E:{eid}]',topics='戶外證據不足',comparison='無法比較',
                      limitations='缺少原音',conclusion='證據不足',evidence_ids=[eid])
        p=self.base/'analysis.json';va.write(p,analysis)
        first=Path(va.report(self.store,self.s,p))
        content=first.read_bytes()
        self.s['question']='加入 JBL 比較';self.store.save(self.s)
        second=Path(va.report(self.store,self.s,p))
        self.assertNotEqual(first,second);self.assertEqual(first.read_bytes(),content)
        analysis['evidence_ids']=[];va.write(p,analysis)
        with self.assertRaises(ValueError):va.report(self.store,self.s,p)

    def test_timestamp_and_vtt(self):
        vtt='WEBVTT\n\n00:01:02.500 --> 00:01:05.000 align:start\n<c>戶外</c> &amp; 通話\n'
        self.assertEqual(va.parse_vtt(vtt),[dict(start=62.5,end=65.0,text='戶外 & 通話')])

    def test_dual_report_snapshot_and_legacy_survival(self):
        key=self.artifact();eid=va.add_evidence(self.store,self.s,self.evidence(key))
        analysis=dict(summary=f'作者講評 [E:{eid}]',topics='沒有本次聆聽',comparison='無法排序',
                      limitations='手機未知',conclusion='保留現有設備',evidence_ids=[eid],
                      decision=dict(recommendation=f'先保留設備 [E:{eid}]',comparison='沒有同場比較',
                        confidence='低',key_limitations=['沒有原音'],next_step='先核對片段'))
        self.s['context']={'phone':'iPhone 15 Pro（待再次確認）','budget':'CNY 200–500（待確認）'}
        p=self.base/'analysis.json';va.write(p,analysis)
        before=va.sha(self.store.artifact(self.s,key))
        primary=Path(va.report(self.store,self.s,p))
        self.assertTrue(primary.name.endswith('.decision.md'))
        base=primary.with_name(primary.name.replace('.decision.md','.md'))
        appendix=base.with_name(base.stem+'.appendix.md')
        snap=va.read(base.with_suffix('.json'))
        for f in (primary,appendix):
            self.assertIn(snap['analysis_key'],f.read_text())
            self.assertIn('iPhone 15 Pro（待再次確認）',f.read_text())
        self.assertIn('## 7.',base.read_text())
        self.assertEqual(snap['context'],self.s['context'])
        self.assertEqual(before,va.sha(self.store.artifact(self.s,key)))
        legacy=Path(va.report(self.store,self.s,p,'legacy'))
        self.assertNotIn('.decision.',legacy.name)
        self.assertIn('## 7.',legacy.read_text())
        old=primary.read_bytes();old_key=snap['analysis_key']
        self.s['context']['budget']='CNY 300';self.store.save(self.s)
        new=Path(va.report(self.store,self.s,p))
        self.assertEqual(primary.read_bytes(),old)
        newbase=new.with_name(new.name.replace('.decision.md','.json'))
        self.assertNotEqual(va.read(newbase)['analysis_key'],old_key)

    def test_decision_unknown_evidence_refused_before_output(self):
        key=self.artifact();eid=va.add_evidence(self.store,self.s,self.evidence(key))
        a=dict(summary=f'作者講評 [E:{eid}]',topics='未知',comparison='未知',limitations='缺原音',
               conclusion='證據不足',evidence_ids=[eid],decision=dict(recommendation='更好 [E:000000000000]',
               comparison='無',confidence='低',key_limitations=['無原音'],next_step='確認'))
        p=self.base/'analysis.json';va.write(p,a)
        with self.assertRaisesRegex(ValueError,'決策摘要引用未選用'):
            va.report(self.store,self.s,p)
        self.assertFalse((self.store.data/'sessions'/self.s['id']/'reports').exists())

    def test_report_depth_routing_and_override(self):
        for question in ('至少五支同型號影片', '至少12支影片', '至少十部影片', 'at least 12 videos', '交叉驗證', '完整研究', 'at least five videos'):
            self.s['question']=question
            self.assertEqual(va.report_mode(self.s,{}),'deep')
            self.assertEqual(va.report_mode(self.s,{},'quick'),'quick')
        self.assertEqual(va.report_mode(self.s,{'research_mode':'quick'}),'quick')
        self.s['context']['research_mode']='quick'
        self.assertEqual(va.report_mode(self.s,{}),'quick')
        self.assertEqual(va.report_mode(self.s,{'research_mode':'deep'}),'deep')
        with self.assertRaises(ValueError):va.report_mode(self.s,{},'invalid')

    def test_deep_self_contained_and_quick_legacy_survive(self):
        key=self.artifact();eid=va.add_evidence(self.store,self.s,self.evidence(key))
        ref=f'[E:{eid}]'
        a=dict(summary='目前僅有講評 '+ref,topics='無戶外實測',comparison='條件不可比',
               limitations='未驗證實際音訊',conclusion='證據不足',evidence_ids=[eid],
               deep=dict(background='研究戶外通話',cross_validation='沒有第二組獨立實測 '+ref,
                         scenarios='不外推戶外 '+ref,recommendation='暫緩決策 '+ref))
        self.s['question']='完整研究'
        p=self.base/'analysis.json';va.write(p,a)
        primary=Path(va.report(self.store,self.s,p))
        self.assertTrue(primary.name.endswith('.full.md'))
        text=primary.read_text()
        for value in ('交叉驗證','使用情境','觀察結果','測試方法','證據限制','最終建議','&t=1','00:01–00:03'):
            self.assertIn(value,text)
        snap=va.read(primary.with_name(primary.name.replace('.full.md','.json')))
        self.assertEqual(snap['research_mode'],'deep')
        self.assertNotIn('analysis_key',text)
        self.assertIn(snap['analysis_key'],primary.with_name(primary.name.replace('.full.md','.appendix.md')).read_text())
        old=primary.read_bytes()
        self.assertTrue(Path(va.report(self.store,self.s,p,mode='quick')).name.endswith('.decision.md'))
        self.assertEqual(primary.read_bytes(),old)
        self.assertIn('## 7.',Path(va.report(self.store,self.s,p,'legacy')).read_text())

    def test_report_context_quotes_and_topic_relevance(self):
        self.s['title']='掃地機器人'
        self.s['question']='延續RV30Plus換機評估，台灣使用NT15000，長頭髮與寵物毛'
        self.s['context']={'phone':'iPhone 15','computer_use_checkpoint':{'status':'pending'}}
        a={'report_context':{'current_device':dict(value='RV30Plus',question_quote='延續RV30Plus換機評估'),
                             'budget':dict(value='NT15000',question_quote='台灣使用NT15000')}}
        text=va.report_context(self.s,a)
        self.assertIn('RV30Plus',text);self.assertIn('NT15000',text)
        for item in ('iPhone','手機','checkpoint','未確認','{}'):self.assertNotIn(item,text)
        self.assertNotIn('current_device',self.s['context'])
        self.s['context']['budget']='NT20000（待確認）'
        self.assertIn('尚待釐清差異',va.report_context(self.s,a))
        a['report_context']['budget']['value']='NT30000'
        with self.assertRaisesRegex(ValueError,'原文依據'):va.report_context(self.s,a)
        self.assertEqual(va.reader_limitations('英語字幕未覆核；end是分析窗口非字幕cue終點'), '英語字幕未覆核')
        self.assertEqual(va.reader_limitations('字幕未覆核。非同場對照。end是分析窗口非字幕cue終點'), '字幕未覆核。非同場對照。')
        self.assertEqual(va.reader_limitations('資料未確認；未直接檢查'), '資料未確認；未直接檢查')

    def test_deep_rejects_summary_only_and_unknown_citations(self):
        key=self.artifact();eid=va.add_evidence(self.store,self.s,self.evidence(key))
        a=dict(summary=f'講評 [E:{eid}]',topics='無',comparison='無',limitations='未知',
               conclusion='證據不足',evidence_ids=[eid])
        p=self.base/'analysis.json';va.write(p,a)
        with self.assertRaisesRegex(ValueError,'Deep 完整分析缺少欄位'):
            va.report(self.store,self.s,p,mode='deep')
        a['deep']=dict(background='背景',cross_validation='[E:000000000000]',
                       scenarios=f'[E:{eid}]',recommendation=f'[E:{eid}]')
        va.write(p,a)
        with self.assertRaisesRegex(ValueError,'Deep 引用未選用'):
            va.report(self.store,self.s,p,mode='deep')
        self.assertFalse((self.store.data/'sessions'/self.s['id']/'reports').exists())

    def test_budget_refuses_no_deletion(self):
        key=self.artifact();old=self.store.artifact(self.s,key)
        p=self.base/'new.txt';p.write_text('test')
        with patch.object(va,'LIMIT',0):
            with self.assertRaises(ValueError):self.store.put('new','test',p)
        self.assertTrue(old.exists())

    def test_bad_times_and_unknown_artifacts(self):
        key=self.artifact();item=self.evidence(key)
        item['end']=float('nan')
        with self.assertRaises(ValueError):va.add_evidence(self.store,self.s,item)
        item['end']=4;item['artifact_key']='0'*64
        with self.assertRaises(ValueError):va.add_evidence(self.store,self.s,item)

    def test_acquisition_cache_cross_session_and_refresh(self):
        calls=[]
        payload=['WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n原始字幕\n']
        class FakeYDL:
            def __init__(self,opts):self.opts=opts
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def extract_info(self,link,download):
                calls.append((link,download))
                Path(self.opts['outtmpl'].replace('%(ext)s','zh.vtt')).write_text(payload[0])
                return {'id':'abcdefghijk'}
        with patch.dict(sys.modules,{'yt_dlp':SimpleNamespace(YoutubeDL=FakeYDL)}),patch.object(va.importlib.metadata,'version',return_value='fixture-version'):
            old=va.acquire(self.store,self.s,'youtube:abcdefghijk','subtitles')
            s2=self.store.create('第二個研究','別的研究問題',[URL])
            reused=va.acquire(self.store,s2,'youtube:abcdefghijk','subtitles')
            self.assertEqual(old,reused);self.assertEqual(len(calls),1)
            payload[0]=payload[0].replace('原始字幕','修訂字幕')
            revised=va.acquire(self.store,self.s,'youtube:abcdefghijk','subtitles',True)
            self.assertNotEqual(old,revised);self.assertEqual(len(calls),2)
            self.assertIn('原始字幕',self.store.artifact(s2,old).read_text())
            self.assertIn('修訂字幕',self.store.artifact(self.s,revised).read_text())

if __name__=='__main__':unittest.main()
