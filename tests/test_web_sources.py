"""Offline mixed-source contracts; every write is isolated in temporary directories."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import va
import web_sources as web


class WebSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = va.Store(self.root/'data', self.root/'cache')
        self.s = self.store.create('混合研究', '官方規格與影片交叉驗證', [])
        self.sid = va.import_candidates(self.store, self.s, [dict(
            url='https://example.com/spec#section', source_type='web')])[0]
        self.text = self.root/'page.md'
        self.text.write_text('# 規格\n支援追蹤\n限制：指定模式\n')
        self.manifest = self.root/'manifest.json'
        va.write(self.manifest, dict(url='https://example.com/spec', title='規格頁',
            file='page.md', format='markdown', retrieved_at='2026-10-24T10:00:00+08:00',
            capture_method='browser visible text', publisher='Example'))

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def select(self):
        va.select(self.store, self.s, [self.sid], False, '新增官方規格', 'automatic')

    def evidence(self, key):
        return dict(source_id=self.sid, artifact_key=key, claim='官方聲稱支援追蹤',
            claim_type='official_spec', support='medium', reason='原文核對',
            conditions='指定模式', limitations='未驗證實機', product_version='未確認',
            verification='保存頁面核對', locator=dict(line_start=2, line_end=3),
            excerpt='支援追蹤\n限制：指定模式')

    def test_selection_gate_and_dedup(self):
        before = copy.deepcopy(self.s)
        with self.assertRaises(ValueError): web.import_snapshot(self.store,self.s,self.manifest)
        self.assertEqual(before, self.s)
        self.assertEqual(va.import_candidates(self.store,self.s,[dict(
            url='https://example.com/spec#other',source_type='web')]), [])
        self.select()
        self.assertEqual(len(self.s['selection_events']),1)
        with self.assertRaises(ValueError): va.acquire(self.store,self.s,self.sid,'audio')

    def test_snapshot_versions_and_exact_excerpt(self):
        self.select()
        first = web.import_snapshot(self.store,self.s,self.manifest)['artifact_key']
        eid = va.add_evidence(self.store,self.s,self.evidence(first))
        old = self.store.artifact(self.s,first).read_bytes()
        self.text.write_text('# 新版\n不支援追蹤\n')
        second = web.import_snapshot(self.store,self.s,self.manifest)['artifact_key']
        self.assertNotEqual(first,second)
        self.assertEqual(self.store.artifact(self.s,first).read_bytes(),old)
        self.assertEqual(self.s['evidence'][0]['id'],eid)
        va.add_evidence(self.store,self.s,self.evidence(first))
        for change in [dict(excerpt='不存在'),dict(locator=dict(line_start=0,line_end=3)),dict(start=0,end=1)]:
            item=self.evidence(first);item.update(change)
            with self.assertRaises(ValueError):va.add_evidence(self.store,self.s,item)

    def test_invalid_snapshot_does_not_change_session(self):
        self.select()
        before=copy.deepcopy(self.s)
        self.text.write_bytes(b'\xff')
        with self.assertRaises(UnicodeError):web.import_snapshot(self.store,self.s,self.manifest)
        self.assertEqual(before,self.s)

    def test_mixed_quick_deep_and_legacy(self):
        self.select()
        key=web.import_snapshot(self.store,self.s,self.manifest)['artifact_key']
        web_id=va.add_evidence(self.store,self.s,self.evidence(key))
        vid=va.import_candidates(self.store,self.s,[dict(url='https://youtu.be/abcdefghijk')])[0]
        va.select(self.store,self.s,[vid],False,'影片測試','automatic')
        raw=self.root/'video.txt';raw.write_text('fixture video observation')
        self.store.put('fixture','transcript',raw)
        self.store.attach(self.s,self.s['sources'][vid],'transcript','fixture')
        item=self.evidence(self.store.resolve('fixture'))
        item.update(source_id=vid,start=1,end=3,claim_type='reviewer_opinion')
        item.pop('locator');item.pop('excerpt')
        video_id=va.add_evidence(self.store,self.s,item)
        refs=f'[E:{web_id}] [E:{video_id}]'
        analysis=dict(summary=refs,topics='比較條件',comparison=refs,limitations='fixture',
            conclusion='證據不足',evidence_ids=[web_id,video_id],deep=dict(
                background='混合來源',cross_validation=refs,scenarios=refs,recommendation=refs))
        path=self.root/'analysis.json';va.write(path,analysis)
        for mode in ('quick','deep'):
            primary=Path(va.report(self.store,self.s,path,mode=mode))
            text=primary.read_text()
            self.assertIn('網頁快照第 2–3 行',text)
            self.assertIn('t=1',text)
            self.assertNotIn('spec?t=',text)
        legacy=Path(va.report(self.store,self.s,path,layout='legacy'))
        self.assertIn('限制：指定模式',legacy.read_text())

    def test_cli_import(self):
        self.select()
        result=subprocess.run([sys.executable,'-B',str(va.ROOT/'scripts/va.py'),
            '--data',str(self.store.data),'--cache',str(self.store.cache),
            'import-web',self.s['id'],str(self.manifest)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['source_id'],self.sid)

    def test_public_url_validation(self):
        for bad in ['http://example.com','https://user:secret@example.com',
                    'https://127.0.0.1','https://localhost','https://example.local',
                    'https://youtube.com/watch?v=abcdefghijk']:
            with self.assertRaises(ValueError):web.identity(bad)

    def test_original_bytes_and_web_only_report(self):
        self.select()
        raw=b'\xef\xbb\xbf# specs\r\ntracking supported\r\n'
        self.text.write_bytes(raw)
        key=web.import_snapshot(self.store,self.s,self.manifest)['artifact_key']
        snapshot=va.read(self.store.artifact(self.s,key))
        self.assertEqual(self.store.artifact(self.s,snapshot['raw_artifact_key']).read_bytes(),raw)
        item=self.evidence(key)
        item.update(excerpt='tracking supported',locator=dict(line_start=2,line_end=2))
        eid=va.add_evidence(self.store,self.s,item)
        ref=f'[E:{eid}]'
        path=self.root/'analysis.json'
        va.write(path,dict(summary=ref,topics='spec',comparison=ref,limitations='not tested',
            conclusion='一般研究分析',evidence_ids=[eid]))
        report=Path(va.report(self.store,self.s,path,mode='quick'))
        self.assertIn('網頁快照第 2–2 行',report.read_text())

    def test_origin_validation_and_claim_assessment(self):
        origin=va.import_candidates(self.store,self.s,[dict(url='https://youtu.be/abcdefghijk')])[0]
        self.select()
        key=web.import_snapshot(self.store,self.s,self.manifest)['artifact_key']
        item=self.evidence(key)
        item.update(origin_source_id=origin,assessment=dict(
            directness='文字引用影片結果',method='條件未完整公開',independence='與原片同源'))
        va.add_evidence(self.store,self.s,item)
        self.assertEqual(self.s['evidence'][-1]['origin_root_id'],origin)
        item['origin_source_id']='missing'
        with self.assertRaises(ValueError):va.add_evidence(self.store,self.s,item)
        before=copy.deepcopy(self.s)
        with self.assertRaises(ValueError):va.import_candidates(self.store,self.s,[dict(
            url='https://example.com/repost',source_type='web',origin_source_id='missing')])
        self.assertEqual(before,self.s)
        a=web.identity('https://example.com/a')[0]
        b=web.identity('https://example.com/b')[0]
        with self.assertRaises(ValueError):va.import_candidates(self.store,self.s,[
            dict(url='https://example.com/a',source_type='web',origin_source_id=b),
            dict(url='https://example.com/b',source_type='web',origin_source_id=a)])
        self.assertEqual(before,self.s)

    def test_snapshot_cannot_be_used_for_other_source(self):
        self.select()
        key=web.import_snapshot(self.store,self.s,self.manifest)['artifact_key']
        other=va.import_candidates(self.store,self.s,[dict(url='https://example.com/other',source_type='web')])[0]
        va.select(self.store,self.s,[other],False,'other','automatic')
        item=self.evidence(key);item['source_id']=other
        with self.assertRaises(ValueError):va.add_evidence(self.store,self.s,item)


if __name__ == '__main__': unittest.main()
