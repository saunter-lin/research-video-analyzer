"""Offline web text snapshots; acquisition remains the research agent's responsibility."""
import datetime as dt
import ipaddress
import json
from pathlib import Path
import urllib.parse
import va


def identity(raw):
    p = urllib.parse.urlsplit(raw)
    host = (p.hostname or '').lower()
    if (p.scheme != 'https' or not host or p.username or p.password
            or p.port not in (None, 443) or any(c.isspace() for c in raw)
            or host == 'localhost' or host.endswith(('.localhost', '.local'))):
        raise ValueError('網頁來源需為不含憑證的公開 HTTPS URL')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('不接受內網來源')
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
                'bilibili.com', 'www.bilibili.com', 'm.bilibili.com'):
        raise ValueError('影片平台請使用既有影片來源流程')
    authority = '[' + host + ']' if ':' in host else host
    canonical = urllib.parse.urlunsplit(('https', authority, p.path or '/', p.query, ''))
    return 'web:' + va.digest(canonical)[:24], canonical


def import_snapshot(store, session, manifest_file):
    """Import one pre-selected source. Validate everything before persisting artifacts."""
    manifest_file = Path(manifest_file)
    m = va.read(manifest_file)
    sid, canonical = identity(m['url'])
    source = store.allowed(session, sid)
    for field in ('title', 'retrieved_at', 'capture_method'):
        if not isinstance(m.get(field), str) or not m[field].strip():
            raise ValueError('網頁快照缺少欄位：' + field)
    timestamp = dt.datetime.fromisoformat(m['retrieved_at'].replace('Z', '+00:00'))
    if timestamp.utcoffset() is None:
        raise ValueError('retrieved_at 必須包含時區')
    path = (manifest_file.parent / m['file']).resolve()
    if path.stat().st_size > 5 * 1024**2:
        raise ValueError('網頁文字快照上限 5MiB')
    raw = path.read_bytes()
    if len(raw) > 5 * 1024**2:
        raise ValueError('網頁文字快照上限 5MiB')
    text = raw.decode('utf-8-sig', errors='strict')
    if not text.strip() or '\x00' in text or '\ufffd' in text:
        raise ValueError('快照文字為空或編碼損壞')
    if m.get('format') not in ('text', 'markdown'):
        raise ValueError('只接受已擷取的 text／markdown，不接受原始 HTML 或二進位檔')
    payload = dict(source_id=sid, url=canonical, title=m['title'],
                   retrieved_at=m['retrieved_at'], capture_method=m['capture_method'],
                   publisher=m.get('publisher'), published_at=m.get('published_at'),
                   format=m['format'], raw_sha256=va.sha(path), text=text,
                   untrusted_external_content=True)
    recipe = va.digest(['web-snapshot', payload, 'v1'])
    # Admission includes both raw bytes and parsed JSON before either write.
    estimated = len(raw) + len(json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')) + 512
    if sum(p.stat().st_size for p in store.cache.rglob('*') if p.is_file()) + estimated > va.LIMIT:
        raise ValueError('快取容量不足，停止匯入網頁')
    with va.tempfile.TemporaryDirectory() as directory:
        original = Path(directory) / 'original.txt'
        original.write_bytes(raw)
        raw_recipe = va.digest(['web-raw', payload['raw_sha256'], 'v1'])
        store.put(raw_recipe, 'web_raw', original)
        payload['raw_artifact_key'] = store.resolve(raw_recipe)
        saved = Path(directory) / 'snapshot.json'
        va.write(saved, payload)
        store.put(recipe, 'web_snapshot', saved)
    key = store.resolve(recipe)
    source.setdefault('snapshot_keys', [])
    if key not in source['snapshot_keys']:
        source['snapshot_keys'].append(key)
    store.pin(session, payload['raw_artifact_key'])
    source['metadata'] = dict(title=m['title'], uploader=m.get('publisher'),
                              upload_date=m.get('published_at'), retrieved_at=m['retrieved_at'])
    store.attach(session, source, 'web_snapshot', key)
    return dict(source_id=sid, artifact_key=key, raw_sha256=payload['raw_sha256'])


def validate_evidence(store, session, source, item):
    if 'start' in item or 'end' in item:
        raise ValueError('網頁證據使用行號，不接受影片秒數')
    if item['artifact_key'] not in source.get('snapshot_keys', []):
        raise ValueError('網頁快照不屬於此來源')
    snapshot = va.read(store.artifact(session, item['artifact_key']))
    if snapshot['source_id'] != source['id'] or snapshot['url'] != source['url']:
        raise ValueError('網頁快照來源不一致')
    locator = item.get('locator', {})
    a, b = locator.get('line_start'), locator.get('line_end')
    lines = snapshot['text'].splitlines()
    if type(a) is not int or type(b) is not int or not 1 <= a <= b <= len(lines):
        raise ValueError('網頁證據需要有效的快照行號')
    excerpt = item.get('excerpt')
    if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in '\n'.join(lines[a-1:b]):
        raise ValueError('原文摘錄必須逐字存在於指定快照行號')
    return dict(source_type='web', retrieved_at=snapshot['retrieved_at'],
                snapshot_hash=va.sha(store.artifact(session, item['artifact_key'])),
                source_metadata=dict(title=snapshot['title'], uploader=snapshot['publisher'],
                                     upload_date=snapshot['published_at']))
