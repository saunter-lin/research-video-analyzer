"""Dependency-free regression slice. All test state is temporary."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tests'))
suite = unittest.defaultTestLoader.loadTestsFromNames([
    'test_research_ledger','test_web_sources','test_video_comments','test_external_subtitles','test_portable'])
# Four provider-mocking tests patch yt_dlp's public class and require that optional package.
import importlib.util
if importlib.util.find_spec('yt_dlp') is None:
    import test_research_ledger
    for name in ('test_cancel_during_discover_bypasses_writer_lock_and_discards_response',
                 'test_discover_failure_consumes_budget_no_retry',
                 'test_discover_success_goes_to_review_and_preserves_search_cache',
                 'test_keyboard_interrupt_stops_without_refund'):
        cls = test_research_ledger.ResearchLedger
        setattr(cls, name, unittest.skip('optional yt-dlp required; included in full regression')(getattr(cls,name)))
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
