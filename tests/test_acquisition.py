"""Offline acquire branch and safe CLI failure contracts; all state is temporary."""
import contextlib
import copy
import io
import json
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import va
from yt_dlp.networking import exceptions as network
from yt_dlp.utils import DownloadError, ExtractorError, GeoRestrictedError

URL = 'https://www.youtube.com/watch?v=abcdefghijk'
SOURCE = 'youtube:abcdefghijk'
SECRET = 'https://cdn.example/file?token=PRIVATE_TOKEN&signature=PRIVATE_SIGNATURE Cookie=PRIVATE_COOKIE'
VTT = 'WEBVTT\n\n00:01:02.125 --> 00:01:05.875 align:start\n<c>原文</c> &amp; text\n'


def wrapped(cause):
    inner = ExtractorError('extractor ' + SECRET, cause=cause)
    return DownloadError('download ' + SECRET, exc_info=(type(inner), inner, None))


class Acquisition(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = va.Store(self.root / 'data', self.root / 'cache')
        self.addCleanup(self.store.db.close)
        self.session = self.store.create('字幕', 'test', [URL])
        self.calls = []
        self.phases = []
        owner = self

        class FakeYDL:
            def __init__(self, opts):
                self.opts = dict(opts)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def extract_info(self, link, download):
                owner.calls.append((link, download, self.opts))
                action = owner.phases.pop(0)
                if callable(action):
                    action(self.opts)
                if isinstance(action, Exception):
                    # Simulate yt-dlp logging sensitive context before raising.
                    self.opts['logger'].error(SECRET)
                    Path(self.opts['outtmpl'].replace('%(ext)s', 'vtt.part')).write_text(SECRET)
                    raise action
                for lang, text in action.items():
                    Path(self.opts['outtmpl'].replace('%(ext)s', lang + '.vtt')).write_text(text)
                return {'id': 'abcdefghijk'}

        self.addCleanup(patch.stopall)
        patch('yt_dlp.YoutubeDL', FakeYDL).start()
        patch.object(va.importlib.metadata, 'version', return_value='fixture-version').start()
        # No test is allowed to silently fall through to automatic media/ASR.
        patch.object(va, 'transcribe', side_effect=AssertionError('ASR must be explicit')).start()

    def acquire(self, refresh=False, kind='subtitles'):
        return va.acquire(self.store, self.session, SOURCE, kind, refresh)

    @contextlib.contextmanager
    def cli_output(self, args):
        stdout, stderr, handles = io.StringIO(), io.StringIO(), []
        original_open = Path.open
        def tracked_open(path, *positional, **kwargs):
            handle = original_open(path, *positional, **kwargs)
            if path == self.store.data / 'writer.lock':
                handles.append(handle)
            return handle
        try:
            with patch.object(Path, 'open', tracked_open), \
                 patch.object(sys, 'argv', args), patch.object(va, 'Store', return_value=self.store), \
                 contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                yield stdout, stderr
        finally:
            # A real CLI exits its process; release its lock after each in-process call.
            for handle in handles:
                handle.close()

    def unchanged_snapshot(self):
        return {
            'session': copy.deepcopy(self.session),
            'data': {str(p.relative_to(self.store.data)): p.read_bytes()
                     for p in (self.store.data / 'sessions').rglob('*') if p.is_file()},
            'cache': {str(p.relative_to(self.store.cache)): p.read_bytes()
                      for p in self.store.cache.rglob('*') if p.is_file()},
            'artifacts': self.store.db.execute('SELECT * FROM artifacts').fetchall(),
            'recipes': self.store.db.execute('SELECT * FROM recipes').fetchall(),
            'pins': self.store.db.execute('SELECT * FROM pins').fetchall(),
        }

    def assert_failure(self, code, refresh=False):
        before = self.unchanged_snapshot()
        output = io.StringIO()
        with contextlib.redirect_stderr(output), contextlib.redirect_stdout(output):
            with self.assertRaises(va.AcquisitionError) as caught:
                self.acquire(refresh)
        self.assertEqual(caught.exception.code, code)
        self.assertIsInstance(caught.exception, ValueError)
        self.assertEqual(str(caught.exception), va.AcquisitionError.messages[code])
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('PRIVATE_', str(caught.exception))
        self.assertEqual(self.unchanged_snapshot(), before)
        return caught.exception

    def test_manual_subtitles_only_skip_automatic_and_media(self):
        self.phases = [{'en': VTT}]
        key = self.acquire()
        self.assertEqual(len(self.calls), 1)
        link, download, opts = self.calls[0]
        self.assertEqual(link, URL)
        self.assertTrue(download)
        for name in ('skip_download', 'writesubtitles', 'ignoreconfig'):
            self.assertIs(opts[name], True)
        self.assertIs(opts['writeautomaticsub'], False)
        self.assertEqual(opts['subtitleslangs'], ['zh.*', 'en.*'])
        self.assertEqual(opts['subtitlesformat'], 'vtt')
        self.assertEqual((opts['retries'], opts['socket_timeout']), (1, 20))
        payload = va.read(self.store.artifact(self.session, key))
        self.assertEqual(payload['origin'], 'manual')
        self.assertEqual(payload['tracks'], [dict(language='en', vtt=VTT)])
        self.assertEqual(set(self.session['sources'][SOURCE]['artifacts']), {'subtitles'})

    def test_automatic_only_after_empty_manual_pass(self):
        self.phases = [{}, {'zh-Hant': VTT}]
        key = self.acquire()
        self.assertEqual([x[2]['writeautomaticsub'] for x in self.calls], [False, True])
        self.assertTrue(all(x[2]['skip_download'] for x in self.calls))
        self.assertEqual(va.read(self.store.artifact(self.session, key))['origin'], 'automatic')

    def test_no_subtitles_requires_two_successful_empty_passes(self):
        self.phases = [{}, {}]
        self.assert_failure('no_subtitles')
        self.assertEqual(len(self.calls), 2)

    def test_manual_exception_does_not_trigger_automatic_or_success(self):
        self.phases = [wrapped(TimeoutError(SECRET))]
        self.assert_failure('transient_network')
        self.assertEqual(len(self.calls), 1)

    def test_automatic_exception_is_not_no_subtitles(self):
        self.phases = [{}, wrapped(HTTPError(URL, 403, SECRET, {}, None))]
        self.assert_failure('access_restricted')
        self.assertEqual(len(self.calls), 2)

    def test_unknown_extractor_text_does_not_guess_login_or_no_subtitles(self):
        for message in ('Sign in to confirm', 'HTTP Error 429', 'No subtitles', '403 forbidden', SECRET):
            with self.subTest(message=message):
                self.phases = [DownloadError(message)]
                self.assert_failure('unknown_failure')

    def test_multilingual_tracks_preserve_raw_text_and_millisecond_timestamps(self):
        tracks = {lang: VTT.replace('原文', text) for lang, text in
                  [('zh-Hant', '繁體'), ('zh-Hans', '简体'), ('en', 'English')]}
        self.phases = [tracks]
        key = self.acquire()
        payload = va.read(self.store.artifact(self.session, key))
        self.assertEqual({x['language']: x['vtt'] for x in payload['tracks']}, tracks)
        parsed = va.transcripts(self.store, self.session, SOURCE)
        self.assertEqual({x['language'] for x in parsed}, set(tracks))
        for track in parsed:
            segment = track['segments'][0]
            self.assertEqual((segment['start'], segment['end']), (62.125, 65.875))
            self.assertEqual(track['origin'], 'manual')
        self.assertEqual(len(self.calls), 1)

    def test_cache_reuse_across_sessions_never_calls_extractor(self):
        self.phases = [{'zh': VTT}]
        first = self.acquire()
        original = self.store.artifact(self.session, first).read_bytes()
        other = self.store.create('另一研究', 'test', [URL])
        again = va.acquire(self.store, other, SOURCE, 'subtitles')
        self.assertEqual(again, first)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.store.artifact(other, again).read_bytes(), original)
        self.assertTrue(Path(self.store.pin(other, again)).exists())

    def test_automatic_cache_reuse_does_not_repeat_either_pass(self):
        self.phases = [{}, {'zh': VTT}]
        first = self.acquire()
        self.assertEqual(self.acquire(), first)
        self.assertEqual(len(self.calls), 2)

    def test_refresh_preserves_old_pinned_artifact_and_other_session(self):
        self.phases = [{'zh': VTT}]
        old = self.acquire()
        other = self.store.create('另一研究', 'test', [URL])
        va.acquire(self.store, other, SOURCE, 'subtitles')
        old_bytes = self.store.artifact(other, old).read_bytes()
        other_session = (self.store.data / 'sessions' / other['id'] / 'session.json').read_bytes()
        self.phases = [{'zh': VTT.replace('原文', '新版')}]
        revised = self.acquire(refresh=True)
        self.assertNotEqual(old, revised)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.store.artifact(other, old).read_bytes(), old_bytes)
        self.assertEqual(self.store.artifact(self.session, old).read_bytes(), old_bytes)
        self.assertEqual((self.store.data / 'sessions' / other['id'] / 'session.json').read_bytes(), other_session)
        self.assertIn('新版', self.store.artifact(self.session, revised).read_text())
        self.assertEqual(self.acquire(), revised)
        self.assertEqual(len(self.calls), 2)

    def test_failed_refresh_keeps_existing_artifact_and_session(self):
        self.phases = [{'zh': VTT}]
        old = self.acquire()
        for actions, code in [([{}, {}], 'no_subtitles'),
                              ([wrapped(TimeoutError(SECRET))], 'transient_network')]:
            with self.subTest(code=code):
                self.phases = actions
                self.assert_failure(code, refresh=True)
                self.assertEqual(self.session['sources'][SOURCE]['artifacts']['subtitles'], old)

    def test_retry_after_failure_can_succeed_without_negative_cache(self):
        self.phases = [{}, {}]
        self.assert_failure('no_subtitles')
        self.phases = [{'zh': VTT}]
        key = self.acquire()
        self.assertEqual(va.read(self.store.artifact(self.session, key))['origin'], 'manual')
        self.assertEqual(len(self.calls), 3)

    def test_unselected_source_is_rejected_before_extractor(self):
        self.session['sources'][SOURCE]['selected'] = False
        with self.assertRaisesRegex(ValueError, '未經使用者選取'):
            self.acquire()
        self.assertEqual(self.calls, [])

    def test_capacity_guards_keep_existing_errors_and_do_not_retry(self):
        before = self.unchanged_snapshot()
        with patch.object(va, 'LIMIT', 0):
            with self.assertRaisesRegex(ValueError, '快取容量不足') as caught:
                self.acquire()
        self.assertNotIsInstance(caught.exception, va.AcquisitionError)
        self.assertEqual(self.calls, [])
        def over_capacity(opts):
            opts['progress_hooks'][0]({'downloaded_bytes': va.LIMIT + 1})
        self.phases = [over_capacity]
        with self.assertRaisesRegex(ValueError, '下載超出快取／單檔容量') as caught:
            self.acquire()
        self.assertNotIsInstance(caught.exception, va.AcquisitionError)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.unchanged_snapshot(), before)

    def test_http_status_classification_through_real_ytdlp_wrappers(self):
        for status, code in [(401, 'access_restricted'), (403, 'access_restricted'),
                             (451, 'access_restricted'), (408, 'transient_network'),
                             (429, 'transient_network'), (500, 'transient_network'),
                             (502, 'transient_network'), (503, 'transient_network'),
                             (504, 'transient_network'), (404, 'unknown_failure'),
                             (400, 'unknown_failure'), (501, 'unknown_failure')]:
            with self.subTest(status=status):
                self.phases = [wrapped(HTTPError(SECRET, status, SECRET, {}, None))]
                self.assert_failure(code)
        response = type('Response', (), {'status': 429, 'reason': SECRET})()
        self.phases = [wrapped(network.HTTPError(response))]
        self.assert_failure('transient_network')

    def test_typed_transport_geo_and_ambiguous_failures(self):
        cases = [(URLError(TimeoutError(SECRET)), 'transient_network'),
                 (ConnectionResetError(SECRET), 'transient_network'),
                 (network.TransportError(SECRET), 'transient_network'),
                 (GeoRestrictedError(SECRET), 'access_restricted'),
                 (network.CertificateVerifyError(SECRET), 'unknown_failure'),
                 (network.TransportError(cause=ssl.SSLError(SECRET)), 'unknown_failure'),
                 (network.ProxyError(SECRET), 'unknown_failure'),
                 (URLError(SECRET), 'unknown_failure'),
                 (OSError('disk failure ' + SECRET), 'unknown_failure')]
        for cause, code in cases:
            with self.subTest(cause=type(cause).__name__):
                self.phases = [wrapped(cause)]
                self.assert_failure(code)

    def test_explicit_cause_and_cycles_are_bounded(self):
        error = RuntimeError(SECRET)
        error.__cause__ = TimeoutError(SECRET)
        self.assertEqual(va.acquisition_error_code(error), 'transient_network')
        error.__cause__ = error
        self.assertEqual(va.acquisition_error_code(error), 'unknown_failure')

    def test_media_extractor_failures_share_boundary_without_subtitle_fallback(self):
        for kind in ('audio', 'video'):
            with self.subTest(kind=kind):
                self.phases = [wrapped(TimeoutError(SECRET))]
                before = self.unchanged_snapshot()
                with self.assertRaises(va.AcquisitionError) as caught:
                    self.acquire(kind=kind)
                self.assertEqual(caught.exception.code, 'transient_network')
                self.assertEqual(before, self.unchanged_snapshot())
                self.assertNotIn('writeautomaticsub', self.calls[-1][2])
        self.assertEqual(len(self.calls), 2)

    def test_cli_failure_preserves_blocked_json_exit_and_redacts_raw_errors(self):
        for phases, code in [([{}, {}], 'no_subtitles'),
                             ([wrapped(TimeoutError(SECRET))], 'transient_network'),
                             ([GeoRestrictedError(SECRET)], 'access_restricted'),
                             ([DownloadError(SECRET)], 'unknown_failure')]:
            with self.subTest(code=code):
                self.phases = phases
                args = ['va.py', '--data', str(self.store.data), '--cache', str(self.store.cache),
                        'acquire', self.session['id'], SOURCE]
                with self.cli_output(args) as (stdout, stderr):
                    with self.assertRaises(SystemExit) as exit_result:
                        va.main()
                self.assertEqual(exit_result.exception.code, 2)
                self.assertEqual(stdout.getvalue(), '')
                payload = json.loads(stderr.getvalue())
                self.assertEqual(payload, dict(status='blocked', error=va.AcquisitionError.messages[code], error_code=code))
                self.assertNotIn('PRIVATE_', stderr.getvalue())
                self.assertNotIn('Traceback', stderr.getvalue())
                self.assertEqual(self.session['sources'][SOURCE]['artifacts'], {})

    def test_cli_success_still_returns_only_json_artifact_key(self):
        self.phases = [{'zh': VTT}]
        args = ['va.py', '--data', str(self.store.data), '--cache', str(self.store.cache),
                'acquire', self.session['id'], SOURCE]
        with self.cli_output(args) as (stdout, stderr):
            va.main()
        key = json.loads(stdout.getvalue())
        self.assertRegex(key, '^[a-f0-9]{64}$')
        self.assertEqual(stderr.getvalue(), '')
        self.assertEqual(key, self.store.session(self.session['id'])['sources'][SOURCE]['artifacts']['subtitles'])

    def test_other_cli_errors_keep_original_schema(self):
        args = ['va.py', 'acquire', self.session['id'], SOURCE]
        with self.cli_output(args) as (stdout, stderr), \
             patch.object(va, 'acquire', side_effect=ValueError('既有錯誤')):
            with self.assertRaises(SystemExit) as result:
                va.main()
        self.assertEqual(result.exception.code, 2)
        self.assertEqual(json.loads(stderr.getvalue()), dict(status='blocked', error='既有錯誤'))


if __name__ == '__main__':
    unittest.main()
