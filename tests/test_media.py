"""Exercise real media decoding, range mapping, frame budget, and content reuse."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import va


class Media(unittest.TestCase):
    def test_extract_repeat_offsets_and_metrics(self):
        from audio_metrics import metrics
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);store=va.Store(root/'data',root/'cache')
            s=store.create('測試素材','驗證原片時間',['https://www.youtube.com/watch?v=abcdefghijk'])
            src=s['sources']['youtube:abcdefghijk'];src['metadata']['duration']=4
            video=root/'fixture.mp4'
            va.run([va.ffmpeg(),'-v','error','-f','lavfi','-i','testsrc=size=160x90:rate=10:duration=4',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',video])
            for kind in ('video','audio'):
                recipe=va.digest(['fixture',kind]);store.put(recipe,kind,video);store.attach(s,src,kind,recipe)
            key=va.extract(store,s,src['id'],'frames',1,3,3)
            first=store.artifact(s,key).read_bytes()
            again=va.extract(store,s,src['id'],'frames',1,3,3)
            self.assertEqual(key,again);self.assertEqual(first,store.artifact(s,key).read_bytes())
            self.assertEqual(len(src['extractions']),1)
            manifest=va.read(store.artifact(s,key))
            self.assertEqual(len(manifest['frames']),3)
            self.assertTrue(all(1<x['time']<3 for x in manifest['frames']))
            clip=va.extract(store,s,src['id'],'clip',1,3,1)
            m=metrics(store.artifact(s,clip))
            self.assertAlmostEqual(m['duration_s'],2,places=2)
            self.assertLess(m['peak_dbfs'],0)
            self.assertEqual(src['extractions'][-1]['offset'],1)
            with self.assertRaises(ValueError):va.extract(store,s,src['id'],'frames',0,4,24)
            with self.assertRaises(ValueError):va.extract(store,s,src['id'],'clip',0,9,1)
            store.db.close()

if __name__=='__main__':unittest.main()
