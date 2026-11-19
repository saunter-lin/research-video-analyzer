import sys
import copy
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import va
from external_subtitles import import_subtitles

class ExternalSubtitles(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name)
        self.store=va.Store(self.base/'data',self.base/'cache')
        self.s=self.store.create('test','test',['https://youtu.be/abcdefghijk'])
        self.txt=self.base/'raw.txt'
        self.txt.write_text('YouTube transcript\nVideo ID: abcdefghijk\nLanguage: en\nCaptions: auto-generated\n\n[0:00] one\n[0:00] two\n[0:02] three\n')
        self.item=dict(file='raw.txt',video_id='abcdefghijk',url='https://youtu.be/abcdefghijk',subtitle_source='YouTube auto-generated via Computer Use')
        self.manifest=self.base/'manifest.json'
    def tearDown(self):
        self.store.db.close();self.tmp.cleanup()
    def run_import(self):
        va.write(self.manifest,[self.item]);return import_subtitles(self.store,self.s,self.manifest)
    def test_preservation_dedup_versions_languages(self):
        first=self.run_import();key=first['results'][0]['artifact_key'];rev=self.s['revision']
        self.assertEqual(self.run_import()['results'][0]['status'],'duplicate')
        self.assertEqual(rev,self.s['revision'])
        track=va.transcripts(self.store,self.s,'youtube:abcdefghijk')[0]
        self.assertEqual([s['start'] for s in track['segments']],[0,0,2])
        self.assertTrue(all(s['end'] is None for s in track['segments']))
        self.assertEqual(va.sha(self.store.artifact(self.s,track['raw_artifact_key'])),va.sha(self.txt))
        self.txt.write_text(self.txt.read_text().replace('one','ONE'));self.run_import()
        self.txt.write_text(self.txt.read_text().replace('Language: en','Language: zh'));self.run_import()
        self.assertEqual(len(va.transcripts(self.store,self.s,'youtube:abcdefghijk')),3)
        self.assertTrue(self.store.artifact(self.s,key).exists())
        s2=self.store.create('other','other',['https://youtu.be/abcdefghijk'])
        r=import_subtitles(self.store,s2,self.manifest)
        self.assertEqual(r['results'][0]['artifact_key'],self.run_import()['results'][0]['artifact_key'])
    def test_bad_batch_no_mutation(self):
        original=self.txt.read_bytes()
        for broken in [original.replace(b'[0:02]',b'[-0:02]'), original.replace(b'[0:02]',b'[NaN]'),original.replace(b'three',b''),original.replace(b'[0:02]',b'[0:01]').replace(b'[0:00] two',b'[0:03] two'),original+b'\xff']:
            self.txt.write_bytes(broken);rev=self.s['revision']
            self.assertEqual(self.run_import()['status'],'blocked')
            self.assertEqual(self.s['revision'],rev);self.assertEqual(self.s['sources']['youtube:abcdefghijk']['artifacts'],{})
        self.txt.write_bytes(original);self.item['url']='https://youtu.be/zyxwvutsrqp'
        self.assertEqual(self.run_import()['status'],'blocked')
        self.item['url']='https://youtu.be/abcdefghijk';self.item['subtitle_source']=''
        self.assertEqual(self.run_import()['status'],'blocked')
    def test_duplicate_segments_retained_and_selection_gate(self):
        self.txt.write_text(self.txt.read_text()+'[0:02] three\n')
        r=self.run_import();self.assertEqual(len(r['results'][0]['segments']),4)
        self.assertIn('duplicate_segment',[i['code'] for i in r['results'][0]['issues']])
        self.s['sources']['youtube:abcdefghijk']['selected']=False
        with self.assertRaises(ValueError):self.run_import()


class BilibiliSubtitles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        self.store = va.Store(self.base/'data', self.base/'cache')
        self.url = 'https://www.bilibili.com/video/BV1Wogf6vEPj?p=2'
        self.sid = 'bilibili:BV1Wogf6vEPj:p2'
        self.s = self.store.create('test', 'test', [self.url])
        self.raw = self.base/'raw.json'; self.manifest = self.base/'manifest.json'
        self.payload = dict(type='AIsubtitle', lang='zh', body=[
            dict(sid=1, **{'from': 0.125, 'to': 2.9, 'content': ' 原文，不改字 '}),
            dict(sid=2, **{'from': 3.0, 'to': 4.25, 'content': '拜拜'})])
        self.item = dict(format='bilibili-json-v1', source_id=self.sid, url=self.url,
                         subtitle_source='Bilibili 中文 AI via Edge Network response',
                         file='raw.json', cid='40346979438', language='zh',
                         caption_type='auto-generated', captured_at='2026-10-24T15:00:00+08:00',
                         capture_method='browser_network_response', coverage='full_response',
                         video_duration=5)
    def tearDown(self):
        self.store.db.close(); self.tmp.cleanup()
    def run_import(self, items=None):
        va.write(self.raw, self.payload)
        va.write(self.manifest, items or [self.item])
        return import_subtitles(self.store, self.s, self.manifest)
    def test_roundtrip_raw_hash_timing_and_dedup(self):
        r = self.run_import(); self.assertEqual(r['status'], 'ok')
        track = va.transcripts(self.store, self.s, self.sid)[0]
        self.assertEqual(track['segments'][0]['text'], ' 原文，不改字 ')
        self.assertEqual(track['segments'][0]['start'], .125)
        self.assertEqual(track['segments'][0]['end'], 2.9)
        self.assertEqual(track['segments'][0]['end_status'], 'provided')
        self.assertEqual(track['segments'][0]['source_json_path'], '$.body[0]')
        self.assertEqual(track['coverage']['last_end'], 4.25)
        self.assertEqual(va.sha(self.store.artifact(self.s, track['raw_artifact_key'])), va.sha(self.raw))
        self.assertEqual(self.run_import()['results'][0]['status'], 'duplicate')
        self.payload['body'][0]['to'] = 2.8
        self.assertEqual(self.run_import()['results'][0]['status'], 'imported')
        self.assertEqual(len(va.transcripts(self.store, self.s, self.sid)), 2)
    def test_cross_session_reuse_keeps_raw_pinned(self):
        key = self.run_import()['results'][0]['artifact_key']
        other = self.store.create('other', 'other', [self.url])
        result = import_subtitles(self.store, other, self.manifest)
        self.assertEqual(result['results'][0]['status'], 'reused')
        self.assertEqual(result['results'][0]['artifact_key'], key)
        track = va.transcripts(self.store, other, self.sid)[0]
        self.assertTrue(self.store.artifact(other, track['raw_artifact_key']).exists())
    def test_part_and_platform_identity_mismatch(self):
        for key, value in [('url', self.url.replace('p=2', 'p=1')),
                           ('source_id', self.sid.replace(':p2', ':p1')),
                           ('url', 'https://youtu.be/abcdefghijk')]:
            original = self.item[key]; self.item[key] = value
            self.assertEqual(self.run_import()['status'], 'blocked')
            self.item[key] = original
        self.assertEqual(self.s['sources'][self.sid]['artifacts'], {})
    def test_bad_cues_block_whole_mixed_batch(self):
        original = copy.deepcopy(self.payload)
        for change in [{'from': -1}, {'to': 0}, {'to': 6}, {'from': True},
                       {'to': float('nan')}, {'content': ''}, {'content': 42}]:
            self.payload = copy.deepcopy(original); self.payload['body'][0].update(change)
            self.assertEqual(self.run_import()['status'], 'blocked')
            self.assertEqual(self.s['sources'][self.sid]['artifacts'], {})
        self.payload = copy.deepcopy(original)
        self.payload['body'][1]['from'] = 0
        self.assertEqual(self.run_import()['status'], 'blocked')
    def test_capture_provenance_and_sensitive_fields_rejected(self):
        for key, value in [('cid', ''), ('captured_at', '2026-10-24'),
                           ('language', 'en'), ('caption_type', 'manual'),
                           ('capture_method', 'screenshot'), ('coverage', 'complete_audio'),
                           ('video_duration', True), ('cookie', 'do-not-store')]:
            original = copy.deepcopy(self.item); self.item[key] = value
            self.assertEqual(self.run_import()['status'], 'blocked')
            self.item = original
        self.payload['headers'] = {'cookie': 'do-not-store'}
        self.assertEqual(self.run_import()['status'], 'blocked')
    def test_selection_gate_and_partial_not_upgraded(self):
        self.item['coverage'] = 'partial'
        r = self.run_import()
        self.assertEqual(r['results'][0]['coverage']['declared'], 'partial')
        self.item['coverage'] = 'full_response'
        self.assertEqual(self.run_import()['results'][0]['status'], 'imported')
        tracks = va.transcripts(self.store, self.s, self.sid)
        self.assertEqual({t['coverage']['declared'] for t in tracks}, {'partial', 'full_response'})
        self.s['sources'][self.sid]['selected'] = False
        with self.assertRaises(ValueError):
            self.run_import()
    def test_invalid_json_and_mixed_batch_no_mutation(self):
        va.write(self.raw, self.payload)
        va.write(self.manifest, [self.item, dict(self.item, file='missing.json')])
        self.assertEqual(import_subtitles(self.store, self.s, self.manifest)['status'], 'blocked')
        self.assertEqual(self.s['sources'][self.sid]['artifacts'], {})
        self.raw.write_text('{"body":')
        va.write(self.manifest, [self.item])
        self.assertEqual(import_subtitles(self.store, self.s, self.manifest)['status'], 'blocked')
        self.raw.write_bytes(b'\xff')
        self.assertEqual(import_subtitles(self.store, self.s, self.manifest)['status'], 'blocked')
