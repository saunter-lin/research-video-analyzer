"""Offline YouTube TXT and Bilibili subtitle-response JSON importer."""
import datetime as dt
import json
import re
import tempfile
from pathlib import Path
import va


def validate_bilibili(item, text, path, raw_hash):
    """The manifest binds an identity-less response to the observed player/part."""
    issues = []
    def issue(code, blocking=True, **details):
        issues.append(dict(code=code, blocking=blocking, **details))
    vid, canonical = va.identity(item['url'])
    if not vid.startswith('bilibili:') or item.get('source_id') != vid:
        issue('video_url_mismatch')
    origin = item.get('subtitle_source')
    if not isinstance(origin, str) or not origin.strip() or origin.strip().lower() in ('unknown', '未確認'):
        issue('missing_source_pending_confirmation')
    # Never persist a signed resource URL, cookies, request headers or a HAR.
    allowed = {'format', 'source_id', 'url', 'subtitle_source', 'file', 'cid',
               'language', 'caption_type', 'captured_at', 'capture_method',
               'coverage', 'video_duration'}
    if set(item) - allowed:
        issue('unsupported_manifest_fields')
    if '?' in item['url'] and set(va.url.parse_qs(va.url.urlparse(item['url']).query)) - {'p'}:
        issue('use_canonical_video_url')
    if not isinstance(item.get('cid'), str) or not re.fullmatch(r'[1-9]\d*', item['cid']):
        issue('missing_or_invalid_cid')
    if item.get('capture_method') != 'browser_network_response':
        issue('unsupported_capture_method')
    if item.get('coverage') not in ('full_response', 'partial', 'unknown'):
        issue('invalid_coverage')
    try:
        captured = dt.datetime.fromisoformat(item.get('captured_at', ''))
        if captured.utcoffset() is None:
            issue('capture_time_requires_timezone')
    except (TypeError, ValueError):
        issue('invalid_capture_time')
    duration = item.get('video_duration')
    if isinstance(duration, bool) or not va.finite(duration) or duration <= 0:
        issue('invalid_video_duration')
        duration = None
    payload = json.loads(text)
    if not isinstance(payload, dict) or set(payload) - {
        'font_size', 'font_color', 'background_alpha', 'background_color',
        'Stroke', 'type', 'lang', 'version', 'body'
    }:
        issue('unsupported_subtitle_payload')
        payload = {}
    language = payload.get('lang')
    if not isinstance(language, str) or not language.strip() or item.get('language') != language:
        issue('language_mismatch')
    caption_type = item.get('caption_type')
    # Only the actually observed native AI response is supported in this format.
    if payload.get('type') != 'AIsubtitle' or caption_type != 'auto-generated':
        issue('caption_provenance_mismatch')
    segments, previous, seen, sids = [], -1, set(), []
    body = payload.get('body')
    if not isinstance(body, list) or not body:
        issue('no_segments')
        body = []
    for index, cue in enumerate(body):
        location = f'$.body[{index}]'
        if not isinstance(cue, dict) or set(cue) - {'from', 'to', 'sid', 'location', 'content', 'music'}:
            issue('invalid_cue', json_path=location)
            continue
        start, end, content = cue.get('from'), cue.get('to'), cue.get('content')
        if any(isinstance(t, bool) or not va.finite(t) for t in (start, end)) or start < 0 or end <= start:
            issue('invalid_cue_time', json_path=location)
            continue
        if not isinstance(content, str) or not content.strip():
            issue('empty_text', json_path=location)
            continue
        if start < previous:
            issue('unordered_timestamp', json_path=location)
        elif start == previous:
            issue('equal_timestamp', False, json_path=location)
        if duration is not None and end > duration:
            issue('cue_exceeds_duration', json_path=location)
        if (start, end, content) in seen:
            issue('duplicate_segment', False, json_path=location)
        seen.add((start, end, content)); previous = start
        sids.append(cue.get('sid'))
        segments.append(dict(start=start, end=end, end_status='provided', text=content,
                             source_json_path=location, sid=cue.get('sid')))
    if sids and sids != list(range(1, len(sids) + 1)):
        issue('non_contiguous_sid', False)
    coverage = dict(declared=item.get('coverage'), video_duration=duration,
                    first_start=min((s['start'] for s in segments), default=None),
                    last_end=max((s['end'] for s in segments), default=None),
                    cue_count=len(segments), semantic_accuracy='unverified',
                    identity_binding='manifest_and_browser_observation')
    # End times affect evidence ranges; they must participate in version identity.
    content_hash = va.digest(dict(format='bilibili-json-v1', language=language,
                                 caption_type=caption_type,
                                 segments=[(s['start'], s['end'], s['text']) for s in segments]))
    provenance = {k: item.get(k) for k in ('cid', 'captured_at', 'capture_method', 'coverage', 'video_duration')}
    return dict(file=str(path), raw_hash=raw_hash, source_id=vid, url=canonical,
                video_id=vid.split(':')[1], origin=origin, language=language,
                caption_type=caption_type, input_format='bilibili-json-v1',
                provenance=provenance, coverage=coverage, content_hash=content_hash,
                segments=segments, issues=issues)


def validate(item, base):
    issues = []
    def issue(code, blocking=True, **details):
        issues.append(dict(code=code, blocking=blocking, **details))
    path = (base / item['file']).resolve()
    raw = path.read_bytes()
    raw_hash = va.sha(path)
    try:
        text = raw.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError:
        return dict(file=str(path), raw_hash=raw_hash, issues=[dict(code='invalid_utf8', blocking=True)])
    if '\ufffd' in text or '\x00' in text:
        issue('encoding_damage')
    if item.get('format') == 'bilibili-json-v1':
        result = validate_bilibili(item, text, path, raw_hash)
        result['issues'] = issues + result['issues']
        return result
    if item.get('format') not in (None, 'youtube-txt-v1'):
        issue('unsupported_format')
    try:
        vid, canonical = va.identity(item['url'])
        if vid != 'youtube:' + item.get('video_id', ''):
            issue('video_url_mismatch')
    except (ValueError, KeyError):
        vid, canonical = None, None
        issue('invalid_video_url')
    headers = {}
    segments = []
    previous = -1
    seen = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line == 'YouTube transcript':
            continue
        if not segments and ':' in line and not line.startswith('['):
            name, value = line.split(':', 1)
            if name in ('Video ID', 'Language', 'Captions'):
                headers[name] = value.strip()
                continue
        match = re.fullmatch(r'\[(\d+):([0-5]\d)(?::([0-5]\d))?\] (.*)', line)
        if not match:
            issue('unparsed_line', line=number)
            continue
        a, b, c, body = match.groups()
        start = int(a)*60 + int(b) if c is None else int(a)*3600 + int(b)*60 + int(c)
        if not body.strip():
            issue('empty_text', line=number)
        if start < previous:
            issue('unordered_timestamp', line=number)
        elif start == previous:
            issue('equal_timestamp', False, line=number)
        if (start, body) in seen:
            issue('duplicate_segment', False, line=number)
        seen.add((start, body)); previous = start
        segments.append(dict(start=start, end=None, end_status='unknown', text=body,
                             raw_timestamp=line[1:line.index(']')], source_line=number))
    if headers.get('Video ID') != item.get('video_id'):
        issue('header_video_mismatch')
    source = item.get('subtitle_source')
    if not isinstance(source, str) or not source.strip() or source.strip().lower() in ('unknown', '未確認'):
        issue('missing_source_pending_confirmation')
    if not headers.get('Captions'):
        issue('missing_caption_provenance')
    if not segments:
        issue('no_segments')
    language = headers.get('Language') or None
    content_hash = va.digest(dict(language=language, segments=[(x['start'], x['text']) for x in segments]))
    return dict(file=str(path), raw_hash=raw_hash, source_id=vid, url=canonical,
                video_id=item.get('video_id'), origin=source, language=language,
                caption_type=headers.get('Captions'), content_hash=content_hash,
                segments=segments, issues=issues)


def import_subtitles(store, session, manifest):
    """Validate the whole batch first; selected sources required, never overwrite slots."""
    manifest = Path(manifest).resolve()
    items = va.read(manifest)
    if not isinstance(items, list) or not items:
        raise ValueError('匯入清單須為非空 JSON 陣列')
    results = []
    for item in items:
        try:
            result = validate(item, manifest.parent)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            result = dict(file=item.get('file') if isinstance(item, dict) else None,
                          issues=[dict(code='invalid_input', blocking=True, detail=type(exc).__name__)])
        results.append(result)
    if any(i['blocking'] for r in results for i in r['issues']):
        return dict(status='blocked', results=results)
    for result in results:
        store.allowed(session, result['source_id'])
    for result in results:
        src = session['sources'][result['source_id']]
        identity = [result['source_id'], result['origin'], result['content_hash']]
        if result.get('input_format') == 'bilibili-json-v1':
            # A partial/unknown declaration must not inherit full-track metadata
            # from an otherwise identical export (or vice versa).
            identity.append({k: result['provenance'][k] for k in ('cid', 'coverage', 'video_duration')})
        token = va.digest(identity)
        slot = 'external_subtitles:' + token
        if slot in src['artifacts']:
            store.artifact(session, src['artifacts'][slot])
            result.update(status='duplicate', artifact_key=src['artifacts'][slot])
            continue
        cached = store.get(token)
        if cached:
            store.pin(session, va.read(cached)['raw_artifact_key'])
            store.attach(session, src, slot, token)
            result.update(status='reused', artifact_key=src['artifacts'][slot])
            continue
        with tempfile.TemporaryDirectory() as tmp:
            raw_recipe = va.digest(['external-subtitle-raw-v1', result['raw_hash']])
            store.put(raw_recipe, 'external-subtitle-raw', result['file'])
            raw_key = store.resolve(raw_recipe)
            if va.sha(store.artifact(session, raw_key)) != result['raw_hash']:
                raise ValueError('來源檔案在驗證後變更，停止匯入')
            store.pin(session, raw_key)
            payload = dict(result, format='external-subtitles-v1', imported_at=va.now(),
                           manifest_file=str(manifest), manifest_hash=va.sha(manifest),
                           raw_artifact_key=raw_key)
            path = Path(tmp)/'subtitles.json'; va.write(path, payload)
            store.put(token, 'external-subtitles', path)
            store.attach(session, src, slot, token)
        result.update(status='imported', artifact_key=src['artifacts'][slot])
    return dict(status='ok', results=results)
