"""Canonical entry point and reproducibility boundaries."""
from pathlib import Path
import sys,unittest,subprocess,tempfile,json
ROOT=Path(__file__).resolve().parents[1]
class Consolidation(unittest.TestCase):
 def test_entry_from_other_directory(self):
  with tempfile.TemporaryDirectory() as tmp:
   process=subprocess.run([str(ROOT/'video-analyzer'),'--help'],cwd=tmp,text=True,capture_output=True)
  self.assertEqual(process.returncode,0,process.stderr);self.assertIn('audio-analyze',process.stdout)
 def test_production_paths_and_flags(self):
  config=json.loads((ROOT/'runtime.example.json').read_text())
  self.assertIs(config['audio_analysis']['enabled'],False)
  self.assertIs(config['sound_event_analysis']['enabled'],False)
  self.assertEqual(config['sound_event_analysis']['qualification'],'not_qualified')
  for p in [ROOT/'SKILL.md',ROOT/'README.md',ROOT/'runtime.example.json',*(ROOT/'scripts').rglob('*.py')]:
   self.assertNotIn('/mac 2/video-analyzer-round',p.read_text())
 def test_archived_assets_are_excluded(self):
  self.assertFalse((ROOT/'docs/archive').exists())
  self.assertFalse((ROOT/'.models').exists())
if __name__=='__main__':unittest.main()
