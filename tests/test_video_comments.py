import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import va
import video_comments as comments


class VideoComments(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name)
        self.store=va.Store(self.base/'data',self.base/'cache')
        self.url='https://www.bilibili.com/video/BV1Wogf6vEPj?p=1'
        self.sid=va.identity(self.url)[0]
        self.s=self.store.create('評論測試','評論與影片分開', [self.url])
        self.raw=self.base/'comments.json'; self.manifest=self.base/'manifest.json'
        self.rows=[dict(comment_id='local:1',id_kind='snapshot_local',author='公開暱稱',
                        text='  使用情境不同，不能據此比較畫質。\n原文保留。',
                        published_at='2026-10-24 12:00',likes=3,parent_id=None,
                        author_role='unknown',permalink=None)]
        self.m=dict(source_id=self.sid,url=self.url,file='comments.json',
                    retrieved_at='2026-10-24T15:00:00+08:00',capture_method='native browser AX',
                    sort_order='hot',coverage='partial',sampling_scope='首批一則，未展開回覆')
    def tearDown(self):
        self.store.db.close();self.tmp.cleanup()
    def load(self):
        va.write(self.raw,self.rows); va.write(self.manifest,self.m)
        return comments.import_comments(self.store,self.s,self.manifest)['artifact_key']
    def evidence(self,key):
        return dict(source_id=self.sid,source_type='comment',artifact_key=key,
                    locator=dict(comment_id='local:1'),excerpt='使用情境不同，不能據此比較畫質。',
                    claim='評論者認為使用情境不同',claim_type='reviewer_opinion',support='low',
                    reason='只支持評論者表達的意見',conditions='身分與條件未確認',
                    limitations='非受控測試，局部熱門樣本',product_version='未確認',
                    verification='瀏覽器原文對照')
    def test_roundtrip_versions_and_dedup(self):
        key=self.load();rev=self.s['revision']
        self.assertEqual(self.load(),key);self.assertEqual(self.s['revision'],rev)
        track=comments.snapshots(self.store,self.s,self.sid)[0]
        self.assertEqual(track['comments'],self.rows)
        self.assertEqual(self.store.artifact(self.s,track['raw_artifact_key']).read_bytes(),self.raw.read_bytes())
        self.rows[0]['text']='新的評論文字'
        self.assertNotEqual(self.load(),key)
        self.assertEqual(len(comments.snapshots(self.store,self.s,self.sid)),2)
        self.assertTrue(self.store.artifact(self.s,key).exists())
    def test_selection_identity_and_no_mutation(self):
        va.write(self.raw,self.rows);va.write(self.manifest,self.m)
        self.s['sources'][self.sid]['selected']=False
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):comments.import_comments(self.store,self.s,self.manifest)
        self.assertEqual(before,self.s)
        self.s['sources'][self.sid]['selected']=True
        self.m['source_id']=self.sid.replace(':p1',':p2')
        with self.assertRaises(ValueError):self.load()
        self.assertEqual(self.s['sources'][self.sid]['artifacts'],{})
    def test_bad_fields_rejected_before_writes(self):
        original=copy.deepcopy(self.rows)
        for k,v in [('text',''),('likes',True),('parent_id','local:1'),
                    ('author_role','official'),('id_kind','invented'),
                    ('permalink','https://www.bilibili.com/video/BV123?p=1'),('cookie','secret')]:
            self.rows=copy.deepcopy(original);self.rows[0][k]=v
            with self.assertRaises(ValueError):self.load()
            self.assertEqual(self.s['sources'][self.sid]['artifacts'],{})
        self.rows=original*2
        with self.assertRaises(ValueError):self.load()
    def test_scope_time_and_secret_fields_rejected(self):
        original=copy.deepcopy(self.m)
        for k,v in [('coverage','complete'),('sort_order','representative'),
                    ('retrieved_at','2026-10-24'),('headers',{})]:
            self.m=copy.deepcopy(original);self.m[k]=v
            with self.assertRaises(ValueError):self.load()
            self.assertEqual(self.s['sources'][self.sid]['artifacts'],{})
    def test_exact_comment_evidence_no_fake_timestamps(self):
        key=self.load();va.add_evidence(self.store,self.s,self.evidence(key))
        e=self.s['evidence'][-1];self.assertEqual(e['source_type'],'comment')
        self.assertNotIn('t=',va.evidence_link(e));self.assertIn('快照本地 ID',va.evidence_link(e))
        for change in [dict(excerpt='編造內容'),dict(locator=dict(comment_id='missing')),
                       dict(start=0,end=3),dict(claim_type='test_presented'),
                       dict(claim_type='official_spec')]:
            item=self.evidence(key);item.update(change)
            with self.assertRaises(ValueError):va.add_evidence(self.store,self.s,item)
        item=self.evidence(key);item.pop('source_type');item.update(start=0,end=3)
        with self.assertRaises(ValueError):va.add_evidence(self.store,self.s,item)
    def test_other_video_cannot_use_snapshot(self):
        key=self.load();other=va.import_candidates(self.store,self.s,[dict(url='https://youtu.be/abcdefghijk')])[0]
        va.select(self.store,self.s,[other],False,'test','automatic')
        item=self.evidence(key);item['source_id']=other
        with self.assertRaises(ValueError):va.add_evidence(self.store,self.s,item)
    def test_quick_deep_legacy_and_json(self):
        key=self.load();eid=va.add_evidence(self.store,self.s,self.evidence(key));ref=f'[E:{eid}]'
        a=dict(summary=ref,topics='使用情境意見',comparison=ref,limitations='局部評論非代表性樣本',
               conclusion='證據不足',evidence_ids=[eid],deep=dict(background='評論驗證',
               cross_validation=ref,scenarios=ref,recommendation=ref))
        path=self.base/'analysis.json';va.write(path,a)
        for mode in ('quick','deep'):
            output=Path(va.report(self.store,self.s,path,mode=mode));text=output.read_text()
            self.assertIn('影片評論',text);self.assertNotIn('&t=',text)
            if mode=='deep':self.assertIn('影片評論／評論者意見',text)
        text=Path(va.report(self.store,self.s,path,layout='legacy')).read_text()
        self.assertIn('影片評論',text);self.assertIn('使用情境不同',text)
    def test_real_cli_import_and_read(self):
        va.write(self.raw,self.rows);va.write(self.manifest,self.m)
        cli=[sys.executable,str(va.ROOT/'scripts/va.py'),'--data',str(self.store.data),
             '--cache',str(self.store.cache)]
        p=subprocess.run(cli+['import-comments',self.s['id'],str(self.manifest)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['comment_count'],1)
        p=subprocess.run(cli+['comments',self.s['id'],self.sid],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)[0]['comments'],self.rows)
    def test_mixed_video_web_comments_keep_distinct_locators(self):
        key=self.load();comment_id=va.add_evidence(self.store,self.s,self.evidence(key))
        fixture=self.base/'video.txt';fixture.write_text('test-only video observation')
        self.store.put('video-fixture','transcript',fixture)
        self.store.attach(self.s,self.s['sources'][self.sid],'transcript','video-fixture')
        item=self.evidence(self.store.resolve('video-fixture'))
        item.pop('source_type');item.pop('locator');item.pop('excerpt');item.update(start=1,end=2)
        video_id=va.add_evidence(self.store,self.s,item)
        web_id=va.import_candidates(self.store,self.s,[dict(source_type='web',url='https://example.com/spec')])[0]
        va.select(self.store,self.s,[web_id],False,'mixed fixture','automatic')
        fixture=self.base/'page.txt';fixture.write_text('test-only web claim')
        manifest=self.base/'web.json';va.write(manifest,dict(url='https://example.com/spec',
            title='fixture',file='page.txt',format='text',capture_method='fixture',
            retrieved_at='2026-10-24T15:00:00+08:00'))
        import web_sources
        web_key=web_sources.import_snapshot(self.store,self.s,manifest)['artifact_key']
        item=self.evidence(web_key);item.update(source_id=web_id,source_type='web',
            locator=dict(line_start=1,line_end=1),excerpt='test-only web claim')
        eid=va.add_evidence(self.store,self.s,item)
        ids=[comment_id,video_id,eid];refs=' '.join(f'[E:{x}]' for x in ids)
        path=self.base/'mixed-analysis.json';va.write(path,dict(summary=refs,topics='fixture',
            comparison=refs,limitations='fixture',conclusion='證據不足',evidence_ids=ids,
            deep=dict(background='fixture',cross_validation=refs,scenarios=refs,recommendation=refs)))
        text=Path(va.report(self.store,self.s,path,mode='deep')).read_text()
        self.assertIn('影片評論',text);self.assertIn('網頁快照第 1–1 行',text)
        self.assertIn('&t=1',text)
        self.assertNotIn('t=',va.evidence_link(self.s['evidence'][0]))
