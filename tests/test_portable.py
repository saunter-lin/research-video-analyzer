"""Portable state/configuration and executable CLI boundaries; no network."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import va


class Portable(unittest.TestCase):
    def test_environment_state_and_explicit_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            with patch.dict(os.environ,dict(RESEARCH_DATA_DIR=str(root/'data'),RESEARCH_CACHE_DIR=str(root/'cache'))):
                store=va.Store()
                self.assertEqual(store.data,root/'data');self.assertEqual(store.cache,root/'cache');store.db.close()
                store=va.Store(root/'other-data',root/'other-cache')
                self.assertEqual(store.data,root/'other-data');self.assertEqual(store.cache,root/'other-cache');store.db.close()

    def test_runtime_relative_paths_and_disabled_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();config=root/'runtime.json'
            va.write(config,va.read(ROOT/'runtime.example.json'))
            with patch.dict(os.environ,dict(RESEARCH_RUNTIME=str(config))):
                runtime=va.load_runtime()
                self.assertEqual(runtime['whisper_cli'],str(root/'.tools/whisper-cli'))
                self.assertEqual(runtime['models']['whisper.cpp']['base'],str(root/'.models/ggml-base.bin'))
                self.assertIs(runtime['audio_analysis']['enabled'],False)

    def test_missing_config_fails_without_fallback(self):
        with patch.dict(os.environ,dict(RESEARCH_RUNTIME='/nonexistent/research-config.json')):
            with self.assertRaises(FileNotFoundError):va.load_runtime()

    def test_source_launcher_from_other_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([str(ROOT/'video-analyzer'),'--help'],cwd=directory,
                env=os.environ|dict(PYTHON=sys.executable),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('query-reserve',result.stdout)

    def test_doctor_does_not_create_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            result=subprocess.run([sys.executable,str(ROOT/'cli.py'),'doctor'],cwd=directory,
                env=os.environ|dict(RESEARCH_DATA_DIR=str(root/'data'),RESEARCH_CACHE_DIR=str(root/'cache')),
                capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(result.stdout)['ok'])
            self.assertFalse((root/'data').exists());self.assertFalse((root/'cache').exists())

    def test_offline_example_resolves_citations(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,str(ROOT/'examples/offline_research.py'),
                '--cli',str(ROOT/'video-analyzer'),'--output',str(Path(directory)/'result')],
                cwd=directory,env=os.environ|dict(PYTHON=sys.executable),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            output=json.loads(result.stdout);text=Path(output['report']).read_text()
            self.assertIn(output['evidence_id'],text);self.assertIn('https://example.com/',text)


if __name__=='__main__':unittest.main()
