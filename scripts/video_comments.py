"""Offline, bounded public video-comment snapshots and exact-text evidence."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import va


def import_comments(store, session, manifest_file):
    manifest_file = Path(manifest_file).resolve()
    m = va.read(manifest_file)
    sid, canonical = va.identity(m['url'])
    source = store.allowed(session, sid)
    if m.get('source_id') != sid or source.get('source_type', 'video') != 'video':
        raise ValueError('評論必須綁定已納入的同一影片與分 P')
    if m['url'] != canonical:
        raise ValueError('評論清單請使用標準影片 URL，不含追蹤／簽名參數')
    if set(m) - {'source_id', 'url', 'file', 'retrieved_at', 'capture_method',
                 'sort_order', 'coverage', 'sampling_scope'}:
        raise ValueError('評論清單含不支援欄位；不要匯入憑證或要求標頭')
    for field in ('capture_method', 'sampling_scope'):
        if not isinstance(m.get(field), str) or not m[field].strip():
            raise ValueError('評論快照缺少欄位：' + field)
    stamp = dt.datetime.fromisoformat(m['retrieved_at'].replace('Z', '+00:00'))
    if stamp.utcoffset() is None:
        raise ValueError('評論取得時間須包含時區')
    if m.get('sort_order') not in ('hot', 'new', 'unknown') or m.get('coverage') not in ('partial', 'unknown'):
        raise ValueError('需記錄評論排序及局部取樣範圍；不宣稱全站評論完整')
    path = (manifest_file.parent / m['file']).resolve()
    if path.stat().st_size > 5 * 1024**2:
        raise ValueError('評論快照上限 5MiB')
    raw = path.read_bytes()
    if len(raw) > 5 * 1024**2:
        raise ValueError('評論快照上限 5MiB')
    text = raw.decode('utf-8-sig', errors='strict')
    comments = json.loads(text)
    if not isinstance(comments, list) or not 1 <= len(comments) <= 1000:
        raise ValueError('評論需為 1～1000 項 JSON 陣列')
    seen = set()
    fields = {'comment_id', 'id_kind', 'author', 'text', 'published_at', 'likes',
              'parent_id', 'author_role', 'permalink'}
    for c in comments:
        if not isinstance(c, dict) or set(c) - fields:
            raise ValueError('評論含不支援欄位')
        for field in ('comment_id', 'author', 'text'):
            if not isinstance(c.get(field), str) or not c[field].strip() or any(x in c[field] for x in ('\x00', '\ufffd')):
                raise ValueError('評論缺少有效原文／身分欄位：' + field)
        if c['comment_id'] in seen:
            raise ValueError('同快照評論 ID 重複')
        seen.add(c['comment_id'])
        if c.get('id_kind') not in ('platform', 'snapshot_local'):
            raise ValueError('需區分平台評論 ID 與快照本地 ID')
        if c.get('published_at') is not None and (not isinstance(c['published_at'], str) or not c['published_at'].strip()):
            raise ValueError('發布時間保留網站原文或 null')
        if c.get('likes') is not None and (type(c['likes']) is not int or c['likes'] < 0):
            raise ValueError('按讚數須為非負整數或 null；縮寫數字未確認時不可猜測')
        if c.get('parent_id') is not None and (not isinstance(c['parent_id'], str) or not c['parent_id'].strip() or c['parent_id'] == c['comment_id']):
            raise ValueError('回覆需有效的其他 parent_id 或 null')
        if c.get('author_role') not in ('video_author', 'unknown'):
            raise ValueError('作者身分僅接受網站已核對的 video_author 或 unknown')
        if c.get('permalink') is not None:
            target = c['permalink']
            if va.identity(target)[0] != sid:
                raise ValueError('評論連結不屬於此影片')
            # Only a video URL and an observed anchor; no tracking or tokens.
            if target.split('#', 1)[0] != canonical:
                raise ValueError('評論連結不可含追蹤或簽名參數')
    payload = dict(source_id=sid, url=canonical, comments=comments,
                   retrieved_at=m['retrieved_at'], capture_method=m['capture_method'],
                   sort_order=m['sort_order'], coverage=m['coverage'],
                   sampling_scope=m['sampling_scope'], comment_count=len(comments),
                   raw_sha256=hashlib.sha256(raw).hexdigest(), untrusted_external_content=True,
                   format='video-comments-v1')
    recipe = va.digest(['video-comments', payload, 'v1'])
    estimate = len(raw) + len(json.dumps(payload, ensure_ascii=False, indent=2).encode()) + 512
    if sum(p.stat().st_size for p in store.cache.rglob('*') if p.is_file()) + estimate > va.LIMIT:
        raise ValueError('快取容量不足，停止匯入評論')
    with va.tempfile.TemporaryDirectory() as directory:
        original = Path(directory)/'comments.raw.json'; original.write_bytes(raw)
        raw_recipe = va.digest(['comments-raw', payload['raw_sha256'], 'v1'])
        store.put(raw_recipe, 'comments_raw', original)
        payload['raw_artifact_key'] = store.resolve(raw_recipe)
        saved = Path(directory)/'comments.json'; va.write(saved, payload)
        store.put(recipe, 'video_comments', saved)
    key = store.resolve(recipe)
    store.pin(session, payload['raw_artifact_key'])
    slot = 'comments:' + recipe
    if source['artifacts'].get(slot) != key:
        store.attach(session, source, slot, recipe)
    else:
        store.artifact(session, key)
    return dict(source_id=sid, artifact_key=key, comment_count=len(comments),
                raw_sha256=payload['raw_sha256'], coverage=m['coverage'])


def snapshots(store, session, sid):
    source = store.allowed(session, sid)
    return [va.read(store.artifact(session, key)) for slot, key in source['artifacts'].items()
            if slot.startswith('comments:')]


def validate_evidence(store, session, source, item):
    if 'start' in item or 'end' in item:
        raise ValueError('評論以 comment_id 定位，不接受影片秒數')
    if item['claim_type'] not in ('reviewer_opinion', 'unverified', 'inference'):
        raise ValueError('評論不能冒充影片實測、官方規格或官方宣傳')
    keys = {key for slot, key in source['artifacts'].items() if slot.startswith('comments:')}
    if item['artifact_key'] not in keys:
        raise ValueError('評論快照不屬於此來源')
    snapshot = va.read(store.artifact(session, item['artifact_key']))
    if snapshot['source_id'] != source['id'] or snapshot['url'] != source['url']:
        raise ValueError('評論快照來源不一致')
    cid = item.get('locator', {}).get('comment_id')
    found = next((c for c in snapshot['comments'] if c['comment_id'] == cid), None)
    excerpt = item.get('excerpt')
    if found is None or not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in found['text']:
        raise ValueError('原文摘錄必須逐字存在於指定評論')
    return dict(source_type='comment', retrieved_at=snapshot['retrieved_at'],
                snapshot_hash=va.sha(store.artifact(session, item['artifact_key'])),
                comment_metadata=found, comment_sampling={k: snapshot[k] for k in
                    ('sort_order', 'coverage', 'sampling_scope', 'comment_count')})
