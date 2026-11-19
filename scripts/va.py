#!/usr/bin/env python3
"""Local video research: budgeted selection, immutable artifacts, incremental sessions."""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import html
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.parse as url
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.4.0'
LIMIT = 20 * 1024**3

def now():
    return dt.datetime.now(ZoneInfo('Asia/Taipei')).isoformat()

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def load_runtime():
    configured = os.environ.get('RESEARCH_RUNTIME')
    path = Path(configured).expanduser().resolve() if configured else ROOT/'runtime.example.json'
    cfg = read(path)
    cfg['whisper_cli'] = str((path.parent / Path(cfg['whisper_cli']).expanduser()).resolve())
    for models in cfg['models'].values():
        for name, value in models.items():
            models[name] = str((path.parent / Path(value).expanduser()).resolve())
    return cfg


def identity(raw):
    p = url.urlparse(raw)
    if p.scheme != 'https' or p.username or p.password:
        raise ValueError('只接受公開 HTTPS YouTube／Bilibili 網址')
    host = (p.hostname or '').lower()
    q = url.parse_qs(p.query)
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'):
        vid = p.path.strip('/') if host == 'youtu.be' else q.get('v', [''])[0]
        if p.path.startswith(('/shorts/', '/live/')):
            vid = p.path.split('/')[2]
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
            raise ValueError('無法識別 YouTube 影片 ID')
        return 'youtube:' + vid, 'https://www.youtube.com/watch?v=' + vid
    if host in ('www.bilibili.com', 'bilibili.com', 'm.bilibili.com'):
        m = re.search(r'/video/(BV[A-Za-z0-9]+|av[0-9]+)', p.path)
        part = q.get('p', ['1'])[0]
        if not m or not part.isdigit() or int(part) < 1:
            raise ValueError('Bilibili 需完整 BV／av 網址與有效分 P')
        vid = m.group(1)
        return f'bilibili:{vid}:p{int(part)}', f'https://www.bilibili.com/video/{vid}?p={int(part)}'
    raise ValueError('不支援的影片平台；短網址請先取得完整影片網址')

def finite(v):
    return isinstance(v, (int, float)) and math.isfinite(v)

def run(args, timeout=600):
    p = subprocess.run([str(x) for x in args], text=True, capture_output=True, timeout=timeout)
    if p.returncode:
        # Do not persist full extractor errors: they can contain signed media URLs.
        raise RuntimeError(f'{Path(str(args[0])).name} 失敗 (exit {p.returncode})；檢查網路／平台存取限制')
    return p.stdout

def ffmpeg():
    if shutil.which('ffmpeg'):
        return shutil.which('ffmpeg')
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def ydl_options():
    opts = dict(quiet=True, no_warnings=True, noplaylist=True, socket_timeout=20,
                retries=1, cachedir=False, ignoreconfig=True)
    node = shutil.which('node')
    if node:
        opts['js_runtimes'] = {'node': {'path': node}}
    return opts

class Store:
    def __init__(self, data=None, cache=None):
        self.data = Path(data or os.environ.get('RESEARCH_DATA_DIR') or Path.home()/'.local/share/research-video-analyzer').expanduser().resolve()
        self.cache = Path(cache or os.environ.get('RESEARCH_CACHE_DIR') or Path.home()/'.cache/research-video-analyzer').expanduser().resolve()
        self.data.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.data/'index.sqlite3', timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS artifacts(key TEXT PRIMARY KEY, kind TEXT, path TEXT,
          hash TEXT, created TEXT, accessed TEXT, hits INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS pins(session TEXT, key TEXT, PRIMARY KEY(session,key));
        CREATE TABLE IF NOT EXISTS recipes(recipe TEXT PRIMARY KEY, artifact TEXT);
        ''')
        self.db.commit()

    def session(self, sid):
        if not re.fullmatch(r'[0-9a-f]{12}', sid):
            raise ValueError('研究 ID 格式錯誤')
        return read(self.data/'sessions'/sid/'session.json')

    def save(self, s):
        s['updated_at'] = now()
        s['revision'] += 1
        base = self.data/'sessions'/s['id']
        write(base/'history'/f'{s["revision"]:06}.json', s)
        write(base/'session.json', s)

    def create(self, title, question, seeds):
        if not title.strip() or not question.strip():
            raise ValueError('研究標題與問題不可空白')
        s = dict(schema_version=1,id=uuid.uuid4().hex[:12], title=title, question=question, revision=0,
                 research_policy=dict(mode="automatic", max_auto_sources=3),
                 created_at=now(), products=[], sources={}, selection_events=[], evidence=[],
                 conflicts=[], gaps=[], context={})
        for raw in seeds:
            vid, canonical = identity(raw)
            s['sources'][vid] = dict(id=vid, url=canonical, role='seed', selected=True,
                                    added_at=now(), metadata={}, artifacts={})
        self.save(s)
        return s

    def allowed(self, s, vid):
        source = s['sources'].get(vid)
        if not source or not source['selected']:
            raise ValueError('影片未經使用者選取或自動研究納入，禁止字幕／影音／ASR／影格處理')
        return source

    def resolve(self, key):
        row=self.db.execute('SELECT artifact FROM recipes WHERE recipe=?',(key,)).fetchone()
        return row[0] if row else key

    def get(self, key, max_age=None):
        key=self.resolve(key)
        row = self.db.execute('SELECT path,hash,created FROM artifacts WHERE key=?', (key,)).fetchone()
        if not row:
            return None
        path = Path(row[0])
        if max_age is not None and (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(row[2])).total_seconds() > max_age:
            return None
        if not path.is_file() or sha(path) != row[1]:
            return None
        self.db.execute('UPDATE artifacts SET accessed=?,hits=hits+1 WHERE key=?', (now(), key))
        self.db.commit()
        return path

    def put(self, key, kind, src):
        recipe=key
        key=digest([recipe,kind,sha(src)])
        existing=self.get(key)
        if existing:
            self.db.execute('INSERT OR REPLACE INTO recipes VALUES(?,?)',(recipe,key))
            self.db.commit()
            return existing
        # Admission refuses over-budget writes; no automatic evidence deletion.
        size = sum(p.stat().st_size for p in self.cache.rglob('*') if p.is_file())
        if size + Path(src).stat().st_size > LIMIT:
            raise ValueError('快取達 20GiB 上限；先檢視 cache-status，保留引用證據')
        ext = Path(src).suffix
        dest = self.cache/kind/(key + ext)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as f:
            temp = Path(f.name)
        try:
            shutil.copyfile(src, temp)
            os.replace(temp, dest)
        finally:
            temp.unlink(missing_ok=True)
        self.db.execute('INSERT OR REPLACE INTO artifacts VALUES(?,?,?,?,?,?,COALESCE((SELECT hits FROM artifacts WHERE key=?),0))',
                        (key, kind, str(dest), sha(dest), now(), now(), key))
        self.db.execute('INSERT OR REPLACE INTO recipes VALUES(?,?)',(recipe,key))
        self.db.commit()
        return dest

    def pin(self, s, key):
        key=self.resolve(key)
        directory = self.data/'sessions'/s['id']/'artifacts'
        existing=list(directory.glob(key+'.*'))
        row=self.db.execute('SELECT hash FROM artifacts WHERE key=?',(key,)).fetchone()
        if existing and row and sha(existing[0])==row[0]:
            return str(existing[0])
        path = self.get(key)
        if path is None:
            raise ValueError('無法保護不存在的證據素材')
        dest = self.data/'sessions'/s['id']/'artifacts'/(key+path.suffix)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copyfile(path, dest)
        if sha(dest) != sha(path):
            raise ValueError('證據副本雜湊不一致')
        self.db.execute('INSERT OR IGNORE INTO pins VALUES(?,?)', (s['id'], key))
        self.db.commit()
        return str(dest)

    def artifact(self, s, key):
        key=self.resolve(key)
        base = self.data/'sessions'/s['id']/'artifacts'
        found = list(base.glob(key+'.*')) if re.fullmatch('[a-f0-9]{64}', key) else []
        path = self.get(key)
        if found:
            row = self.db.execute('SELECT hash FROM artifacts WHERE key=?', (key,)).fetchone()
            if row and sha(found[0]) == row[0]:
                return found[0]
        if path:
            return path
        raise ValueError('素材不存在或完整性檢查失敗，請重新取得')

    def attach(self, s, source, kind, key):
        key=self.resolve(key)
        source['artifacts'][kind] = key
        self.pin(s, key)
        self.save(s)

def metadata(info):
    # Explicit allowlist excludes signed URLs, headers, cookies, download formats.
    fields = ('title','description','uploader','channel_id','upload_date','duration','webpage_url')
    result = {k: info.get(k) for k in fields}
    result['chapters'] = [{k: x.get(k) for k in ('start_time','end_time','title')} for x in info.get('chapters') or []]
    result['retrieved_at'] = now()
    return result

def inspect_source(store, s, vid, refresh=False):
    src = s['sources'][vid]
    if src.get('source_type') == 'web':
        return src['metadata']
    key = digest(['metadata', vid, 'v1'])
    cached = None if refresh else store.get(key, 86400)
    if cached:
        src['metadata'] = read(cached)
    else:
        from yt_dlp import YoutubeDL
        with YoutubeDL(ydl_options()) as y:
            info = y.extract_info(src['url'], download=False)
        if info.get('_type') in ('playlist','multi_video'):
            raise ValueError('取得多影片清單；請明確指定單片／分 P')
        src['metadata'] = metadata(info)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'metadata.json'; write(p, src['metadata']); store.put(key,'metadata',p)
    store.save(s)
    return src['metadata']

def discover(store, s, queries, limit, refresh=False, reservation=None):
    import research_ledger as ledger
    if not 1 <= limit <= 30:
        raise ValueError('候選探索數須介於 1～30')
    if reservation is None:
        if s.get('research_policy',{}).get('mode')=='automatic':
            raise ValueError('自動搜尋須先 research-plan、query-reserve，再傳 --reservation；每個查詢綁 gap_id 與預算')
        return _discover(store,s,queries,limit,refresh)
    r,q=ledger.check(store,s,reservation,('reserved',))
    if queries!=[q['query']] or q['provider']!='yt-dlp YouTube':
        raise ValueError('discover 必須與 reservation 的單一查詢及 yt-dlp YouTube provider 一致')
    q['status']='searching';ledger.event(r,'searching',query_id=q['query_id'],token=reservation);store.save(s)
    try:
        result=_discover(store,s,queries,limit,refresh,reservation)
        ledger.search_result(store,s,reservation,dict(status='completed',result_count=len(result)))
        return result
    except BaseException as error:
        ledger.sync_cancel(store,s)
        if q['status']!='cancelled':
            q['status']='failed'
            r['stop_reason']='interrupted_requires_review' if not isinstance(error,Exception) else 'provider_failed'
            q['stop_reason']=r['stop_reason']
            ledger.event(r,'failed',query_id=q['query_id'],token=reservation,stop_reason=r['stop_reason'])
            store.save(s)
        raise


def _discover(store, s, queries, limit, refresh=False, reservation=None):
    if not 1 <= limit <= 30:
        raise ValueError('候選探索數須介於 1～30')
    from yt_dlp import YoutubeDL
    candidates = {}
    records = []
    for query in queries:
        if reservation:
            import research_ledger as ledger
            ledger.check(store,s,reservation)
        key = digest(['youtube-search',query,limit,'v1'])
        cached = None if refresh else store.get(key,86400)
        if cached:
            results = read(cached)
        else:
            opts = ydl_options(); opts['extract_flat'] = True
            with YoutubeDL(opts) as y:
                info = y.extract_info(f'ytsearch{limit}:{query}',download=False)
            if reservation:ledger.check(store,s,reservation)
            results = []
            for entry in info.get('entries') or []:
                if entry and re.fullmatch('[A-Za-z0-9_-]{11}', str(entry.get('id',''))):
                    results.append(dict(url='https://www.youtube.com/watch?v='+entry['id'],metadata=metadata(entry),
                                        relevance='僅依搜尋 metadata；內容待核對', independence='未確認',
                                        expected_value=query, recommended=False))
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'search.json';write(p,results)
                if reservation:
                    with ledger.commit_guard(store,s,reservation):
                        ledger.cache_gate(store,s,reservation,p.stat().st_size)
                        store.put(key,'search',p)
                else:store.put(key,'search',p)
        for item in results:
            vid,_ = identity(item['url'])
            candidates.setdefault(vid,item)
        records.append(dict(query=query,provider='yt-dlp YouTube',searched_at=now(),cache_reused=bool(cached)))
    added = import_candidates(store,s,list(candidates.values())[:limit],reservation)
    s.setdefault('searches',[]).extend(records)
    s.setdefault('discovery_limits',[]).append('Bilibili 自動搜尋未實作；由 Agent 或人工網頁搜尋後匯入候選，不能宣稱已搜尋 B 站')
    store.save(s)
    return added

def import_candidates(store, s, items, reservation=None):
    if not isinstance(items,list):
        raise ValueError('候選檔案必須是 JSON 陣列')
    # Validate entire batch before mutating state; duplicate URLs keep selection unchanged.
    pending={}
    for item in items:
        if item.get('source_type', 'video') == 'web':
            from web_sources import identity as web_identity
            vid,canonical=web_identity(item['url'])
        elif item.get('source_type', 'video') == 'video':
            vid,canonical=identity(item['url'])
        else:
            raise ValueError('不支援的來源類型')
        if vid in s['sources'] or vid in pending:
            continue
        meta={k:item.get('metadata',{}).get(k) for k in ('title','uploader','upload_date','duration','description')}
        pending[vid]=dict(id=vid,url=canonical,source_type=item.get('source_type','video'),role='candidate',selected=False,added_at=now(),metadata=meta,
                          relevance=item.get('relevance','未確認'),expected_value=item.get('expected_value','未確認'),
                          independence=item.get('independence','未確認'),
                          source_group=item.get('source_group'),product_version=item.get('product_version','未確認'),
                          recommended=bool(item.get('recommended',False)),artifacts={})
        if item.get('origin_source_id') is not None:
            pending[vid]['origin_source_id'] = item['origin_source_id']
    combined = dict(s['sources'], **pending)
    for vid in pending:
        source_origin(combined, vid)
    count=sum(x['role']=='candidate' for x in s['sources'].values())
    if count+len(pending)>30:
        raise ValueError('候選池超過 30 支，請明確建立新研究或縮小探索範圍')
    if sum(x.get('recommended',False) for x in list(s['sources'].values())+list(pending.values()))>10:
        raise ValueError('推薦數不可超過 10 支')
    import research_ledger as ledger
    with ledger.commit_guard(store,s,reservation):
        if reservation:ledger.candidate_gate(store,s,reservation,items)
        s['sources'].update(pending);store.save(s)
    return list(pending)


def source_origin(sources, sid):
    """Known citation lineage only; absence does not establish independence."""
    seen = set()
    while True:
        if sid in seen or sid not in sources:
            raise ValueError('原始來源關聯不存在或形成循環')
        seen.add(sid)
        origin = sources[sid].get('origin_source_id')
        if origin is None:
            return sid
        if not isinstance(origin, str) or not origin:
            raise ValueError('origin_source_id 必須為已登記來源 ID')
        sid = origin

def configure_research(store, s, mode, max_auto_sources=None):
    if mode not in ('automatic', 'interactive'):
        raise ValueError('研究模式須為 automatic 或 interactive')
    policy = dict(s.get('research_policy', {}))
    policy['mode'] = mode
    if max_auto_sources is not None:
        if not isinstance(max_auto_sources, int) or isinstance(max_auto_sources, bool) or max_auto_sources < 0:
            raise ValueError('自動來源預算須為非負整數')
        policy['max_auto_sources'] = max_auto_sources
    policy.setdefault('max_auto_sources', 3)
    s['research_policy'] = policy
    s.setdefault('policy_events', []).append(dict(at=now(), policy=dict(policy)))
    store.save(s)
    return policy


def select(store,s,ids,exclude,reason,actor='user'):
    if actor not in ('user', 'automatic'):
        raise ValueError('選片 actor 無效')
    policy = s.get('research_policy', {'mode': 'interactive'})
    if actor == 'automatic' and policy.get('mode') != 'automatic':
        raise ValueError('互動選片模式須等待使用者選取')
    # Count historical admissions, not only currently selected sources; no reset by exclusion.
    admitted = {e['source_id'] for e in s['selection_events']
                if e.get('actor') == 'automatic' and e['selected']}
    new = {v for v in ids if v in s['sources'] and not s['sources'][v]['selected']} - admitted
    if actor == 'automatic' and not exclude and len(admitted | new) > policy.get('max_auto_sources', 3):
        raise ValueError('自動研究來源預算不足；需使用者同意提高預算')
    if not reason.strip():
        raise ValueError('必須記錄選片／排除依據；自動選片須說明新增證據價值')
    for vid in ids:
        if vid not in s['sources']:
            raise ValueError('選片 ID 不存在')
    import research_ledger as ledger
    token=None
    if actor=='automatic' and not exclude:
        ledger.source_gate(store,s,ids)
        r=ledger.active(s)
        token=next((q['token'] for q in r['queries'] if q['status'] in ('reserved','searching','awaiting_evidence')),None) if r else None
    with ledger.commit_guard(store,s,token):
        if token:ledger.source_gate(store,s,ids)
        for vid in ids:
            src=s['sources'][vid];src['selected']=not exclude
            s['selection_events'].append(dict(source_id=vid,selected=not exclude,at=now(),reason=reason,actor=actor))
        store.save(s)

class AcquisitionError(ValueError):
    """Safe acquire failure; raw extractor messages must not reach CLI output."""
    messages = {
        'no_subtitles': '無可用繁簡英字幕；可使用既有 Browser Use 交接，或明確執行本機 ASR。',
        'transient_network': '取得暫時受網路、限流或伺服器錯誤阻擋；可稍後重試，不代表沒有字幕。',
        'access_restricted': '平台回報存取或地區限制；請以既有 Browser Use 流程確認權限，不代表必須登入。',
        'unknown_failure': '取得失敗，原因未確認；請檢查平台存取與工具狀態，不將此結果視為沒有字幕。',
    }

    def __init__(self, code):
        self.code = code
        super().__init__(self.messages[code])


def acquisition_error_code(error):
    """Classify typed causes only; ambiguous extractor text remains unknown."""
    from ssl import SSLError
    from urllib.error import HTTPError, URLError
    from yt_dlp.networking import exceptions as network
    from yt_dlp.utils import GeoRestrictedError
    pending, seen, codes = [error], set(), set()
    while pending and len(seen) < 20:
        exc = pending.pop()
        if not isinstance(exc, Exception) or id(exc) in seen:
            continue
        seen.add(id(exc))
        if isinstance(exc, (HTTPError, network.HTTPError)):
            status = exc.code if isinstance(exc, HTTPError) else exc.status
            if status in (401, 403, 451):
                codes.add('access_restricted')
            elif status in (408, 429, 500, 502, 503, 504):
                codes.add('transient_network')
        elif isinstance(exc, GeoRestrictedError):
            codes.add('access_restricted')
        elif isinstance(exc, (SSLError, network.SSLError, network.ProxyError)):
            # Certificate/TLS failures are not presumed temporary.
            return 'unknown_failure'
        elif isinstance(exc, (TimeoutError, ConnectionError, network.TransportError)):
            codes.add('transient_network')
        pending.extend((getattr(exc, 'cause', None), exc.__cause__))
        info = getattr(exc, 'exc_info', None)
        if isinstance(info, tuple) and len(info) == 3:
            pending.append(info[1])
        if isinstance(exc, URLError):
            pending.append(exc.reason)
    for code in ('access_restricted', 'transient_network'):
        if code in codes:
            return code
    return 'unknown_failure'


class _AcquisitionLogger:
    # yt-dlp can log signed URLs before raising. Only the safe CLI error is shown.
    def debug(self, message): pass
    info = warning = error = debug


def acquire(store,s,vid,kind,refresh=False):
    src=store.allowed(s,vid)
    if src.get('source_type') == 'web':
        raise ValueError('網頁來源請使用 import-web，不使用 yt-dlp')
    import yt_dlp
    ver=importlib.metadata.version('yt-dlp')
    key=digest(['acquire',vid,kind,ver,'v1'])
    if not refresh and store.get(key):
        store.attach(s,src,kind,key);return store.resolve(key)
    with tempfile.TemporaryDirectory(dir=store.cache) as d:
        opts=ydl_options();opts['outtmpl']=str(Path(d)/'source.%(ext)s')
        opts['logger']=_AcquisitionLogger()
        opts['max_filesize']=min(LIMIT,2*1024**3)
        available=LIMIT-sum(p.stat().st_size for p in store.cache.rglob('*') if p.is_file())
        if available<=0:
            raise ValueError('快取容量不足，停止下載')
        capacity_exceeded=False
        def capacity_hook(progress):
            nonlocal capacity_exceeded
            if progress.get('downloaded_bytes',0)>min(available,2*1024**3):
                capacity_exceeded=True
                raise ValueError('下載超出快取／單檔容量，停止取得')
        opts['progress_hooks']=[capacity_hook]
        if kind=='subtitles':
            opts.update(skip_download=True,writesubtitles=True,writeautomaticsub=False,
                        subtitleslangs=['zh.*','en.*'],subtitlesformat='vtt')
        else:
            opts['format']='bestaudio/best' if kind=='audio' else 'bestvideo[height<=720]/best[height<=720]/worstvideo'
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                info=y.extract_info(src['url'],download=True)
            if kind=='subtitles' and not list(Path(d).glob('*.vtt')):
                opts['writeautomaticsub']=True
                with yt_dlp.YoutubeDL(opts) as y:
                    info=y.extract_info(src['url'],download=True)
        except Exception as exc:
            if capacity_exceeded:
                raise ValueError('下載超出快取／單檔容量，停止取得') from None
            raise AcquisitionError(acquisition_error_code(exc)) from None
        if kind=='subtitles':
            files=sorted(Path(d).glob('*.vtt'))
            if not files:
                raise AcquisitionError('no_subtitles')
            payload=dict(origin='automatic' if opts.get('writeautomaticsub') else 'manual',
                         retrieved_at=now(),tracks=[dict(language=p.name[7:-4],vtt=p.read_text()) for p in files])
            p=Path(d)/'subtitles.json';write(p,payload)
        else:
            files=[p for p in Path(d).iterdir() if p.is_file() and p.suffix not in ('.part','.ytdl','.json')]
            if len(files)!=1:
                raise ValueError('媒體取得未完成或輸出不明確')
            p=files[0]
        store.put(key,kind,p)
    store.attach(s,src,kind,key)
    return store.resolve(key)

def timestamp(text):
    parts=text.strip().replace(',','.').split(':')
    return sum(float(v)*60**i for i,v in enumerate(reversed(parts)))

def parse_vtt(text):
    out=[]
    for block in re.split(r'\n\s*\n',text.replace('\r','')):
        lines=block.splitlines()
        for i,line in enumerate(lines):
            if '-->' in line:
                a,b=line.split('-->',1)
                try:
                    start,end=timestamp(a),timestamp(b.split()[0])
                except ValueError:
                    continue
                body=html.unescape(re.sub('<[^>]+>','', ' '.join(lines[i+1:])))
                if body.strip() and end>start:
                    out.append(dict(start=start,end=end,text=body.strip()))
                break
    return out

def transcripts(store,s,vid):
    src=store.allowed(s,vid)
    external = [read(store.artifact(s, key)) for slot, key in src['artifacts'].items()
                if slot.startswith('external_subtitles:')]
    if 'subtitles' in src['artifacts']:
        payload=read(store.artifact(s,src['artifacts']['subtitles']))
        return [dict(language=t['language'],origin=payload['origin'],segments=parse_vtt(t['vtt'])) for t in payload['tracks']] + external
    if 'transcript' in src['artifacts']:
        return [read(store.artifact(s,src['artifacts']['transcript']))] + external
    if external:
        return external
    raise ValueError('先取得字幕，無字幕時再轉錄')

def transcribe(store,s,vid,backend,model,language):
    src=store.allowed(s,vid)
    if 'audio' not in src['artifacts']:
        acquire(store,s,vid,'audio')
    audio=store.artifact(s,src['artifacts']['audio'])
    config=load_runtime()
    modelpath=Path(config['models'][backend][model])
    if not modelpath.exists():
        raise ValueError('模型尚未準備；不自動下載未知模型')
    modelhash=sha(modelpath) if modelpath.is_file() else digest(sorted((str(p.relative_to(modelpath)),sha(p)) for p in modelpath.rglob('*') if p.is_file()))
    key=digest(['asr',sha(audio),backend,modelhash,config['versions'],language,1,False,'v1'])
    if not store.get(key):
        with tempfile.TemporaryDirectory(dir=store.cache) as d:
            wav=Path(d)/'input.wav';out=Path(d)/'transcript.json'
            run([ffmpeg(),'-nostdin','-v','error','-i',audio,'-ar','16000','-ac','1','-c:a','pcm_s16le',wav])
            run([sys.executable,ROOT/'scripts/asr_worker.py','--backend',backend,'--model',modelpath,
                 '--audio',wav,'--output',out,'--language',language,'--whisper-cli',config['whisper_cli']],timeout=3600)
            store.put(key,'transcript',out)
    store.attach(s,src,'transcript',key)
    return store.resolve(key)

def extract(store,s,vid,kind,start,end,count):
    src=store.allowed(s,vid)
    if not finite(start) or not finite(end) or start<0 or end<=start:
        raise ValueError('時間範圍無效')
    if not 1<=count<=24:
        raise ValueError('每次影格數需介於 1～24')
    media_kind='video' if kind=='frames' else 'audio'
    if media_kind not in src['artifacts']:
        acquire(store,s,vid,media_kind)
    media=store.artifact(s,src['artifacts'][media_kind])
    duration=src.get('metadata',{}).get('duration')
    if duration and end>duration:
        raise ValueError('超出影片長度')
    key=digest(['extract',sha(media),kind,start,end,count,'v1',run([ffmpeg(),'-version']).splitlines()[0]])
    old=src.setdefault('extractions',[])
    if kind=='frames' and not any(x['key']==store.resolve(key) for x in old):
        if sum(x.get('count',0) for x in old if x['kind']=='frames')+count>24:
            raise ValueError('此片已達 24 張影格預算；需先人工確認補取範圍並調整預算')
    with tempfile.TemporaryDirectory(dir=store.cache) as d:
        if kind=='clip':
            p=Path(d)/'clip.wav'
            if not store.get(key):
                run([ffmpeg(),'-nostdin','-v','error','-i',media,'-ss',start,'-t',end-start,'-ar','48000','-ac','1','-c:a','pcm_s16le',p])
                store.put(key,'clip',p)
            store.pin(s,key)
        else:
            keys=[]
            for i in range(count):
                t=start+(end-start)*(i+.5)/count
                fk=digest([key,i]);p=Path(d)/f'{i}.jpg'
                if not store.get(fk):
                    run([ffmpeg(),'-nostdin','-v','error','-ss',t,'-i',media,'-frames:v','1','-q:v','2',p])
                    store.put(fk,'frame',p)
                store.pin(s,fk);keys.append(dict(key=store.resolve(fk),time=t))
            p=Path(d)/'frames.json';write(p,dict(source_id=vid,frames=keys));store.put(key,'frames',p);store.pin(s,key)
    key=store.resolve(key)
    if not any(x['key']==key for x in old):
        old.append(dict(key=key,kind=kind,start=start,end=end,count=count if kind=='frames' else 0,offset=start))
        store.save(s)
    return key

CLAIMS={'test_presented','reviewer_opinion','official_spec','official_marketing','unverified','inference'}

def add_evidence(store,s,item,reservation=None):
    import research_ledger as ledger
    if not getattr(store,'validation_only',False):
        if item.get('query_reservation') and item['query_reservation']!=reservation:
            raise ValueError('Evidence reservation 須以參數明確傳入，不接受偽造來源欄位')
        if reservation:
            _,query=ledger.check(store,s,reservation,('awaiting_evidence',))
            item=dict(item,query_reservation=reservation,query_id=query['query_id'],gap_id=query['gap_id'])
    src=store.allowed(s,item['source_id'])
    for field in ('claim','claim_type','support','reason','conditions','limitations','product_version','verification','artifact_key'):
        if not item.get(field):
            raise ValueError('缺少證據欄位：'+field)
    if item['claim_type'] not in CLAIMS or item['support'] not in ('high','medium','low','undetermined'):
        raise ValueError('無效證據分類或支持程度')
    origin = item.get('origin_source_id', src.get('origin_source_id'))
    if origin is not None:
        if not isinstance(origin, str) or origin == src['id']:
            raise ValueError('證據原始來源須為其他已登記來源')
        source_origin(s['sources'], origin)
    assessment = item.get('assessment')
    if assessment is not None:
        if not isinstance(assessment, dict) or any(
                not isinstance(assessment.get(k), str) or not assessment[k].strip()
                for k in ('directness','method','independence')):
            raise ValueError('assessment 需說明 directness、method、independence')
    if item.get('source_type') == 'comment':
        from video_comments import validate_evidence
        extra = validate_evidence(store,s,src,item)
        item=dict(item);item.update(id=uuid.uuid4().hex[:12],recorded_at=now(),url=src['url'],
                                   source_metadata=src['metadata'],
                                   artifact_path=store.pin(s,item['artifact_key']), **extra)
    elif src.get('source_type') == 'web':
        from web_sources import validate_evidence
        extra = validate_evidence(store,s,src,item)
        item=dict(item);item.update(id=uuid.uuid4().hex[:12],recorded_at=now(),url=src['url'],
                                   artifact_path=store.pin(s,item['artifact_key']), **extra)
    else:
        if item['artifact_key'] in {key for slot,key in src['artifacts'].items() if slot.startswith('comments:')}:
            raise ValueError('評論素材必須使用 source_type=comment 與評論定位')
        a,b=item.get('start'),item.get('end')
        if not finite(a) or not finite(b) or a<0 or b<=a:
            raise ValueError('證據需要有效的原影片起訖秒數')
        keys=set(src['artifacts'].values())|{x['key'] for x in src.get('extractions',[])}
        if item['artifact_key'] not in keys:
            raise ValueError('證據素材不屬於此來源')
        dur=src.get('metadata',{}).get('duration')
        if dur and b>dur:
            raise ValueError('證據時間超出影片長度')
        item=dict(item);item.update(id=uuid.uuid4().hex[:12],recorded_at=now(),url=src['url'],
                                   source_type='video',source_metadata=src['metadata'],artifact_path=store.pin(s,item['artifact_key']))
    if origin is not None:
        item['origin_source_id'] = origin
        item['origin_root_id'] = source_origin(s['sources'], origin)
    with ledger.commit_guard(store,s,reservation):
        if reservation:ledger.check(store,s,reservation,('awaiting_evidence',))
        s['evidence'].append(item);store.save(s)
    return item['id']

def cell(x):
    return str(x if x is not None else '未確認').replace('|','／').replace('\n',' ')

def candidate_table(s):
    lines=['| ID | 標題／連結 | 作者／日期 | 產品版本 | 預期價值 | 獨立性／同源 | 狀態 |',
           '|---|---|---|---|---|---|---|']
    for v in s['sources'].values():
        m=v['metadata']
        lines.append(f"| {v['id']} | [{cell(m.get('title') or '未確認')}]({v['url']}) | {cell(m.get('uploader'))}／{cell(m.get('upload_date'))} | {cell(v.get('product_version','未確認'))} | {cell(v.get('expected_value','使用者種子'))} | {cell(v.get('independence','未確認'))}／{cell(v.get('source_group'))} | {'已納入' if v['selected'] else '待選取'}；內容待核對 |")
    return '\n'.join(lines)

def report_mode(s, a, mode='auto'):
    if mode == 'auto':
        mode = a.get('research_mode', s.get('context', {}).get('research_mode', 'auto'))
    if mode == 'auto':
        request = s['title'] + ' ' + s['question']
        mode = 'deep' if re.search(r'交叉驗證|交叉验证|完整研究|完整報告|完整报告|至少\s*(?:[五六七八九十百]+|[5-9]|[1-9]\d+)\s*(?:支|部)|(?:deep|cross.validation|comprehensive|at least (?:five|six|seven|eight|nine|[5-9]|[1-9]\d+))', request, re.I) else 'quick'
    if mode not in ('quick', 'deep'):
        raise ValueError('研究深度須為 quick 或 deep')
    return mode


def evidence_link(e, short=False):
    if e.get('source_type') == 'comment':
        c=e['comment_metadata']
        link=c.get('permalink') or e['url']
        label='影片評論' if c['id_kind']=='platform' else '影片評論（快照本地 ID）'
        return (f"[{label} {cell(c['comment_id'])}／{cell(c['author'])}]({link})"
                f"（發布：{cell(c.get('published_at'))}；取得：{e['retrieved_at']}；局部取樣）")
    if e.get('source_type') == 'web':
        locator=e['locator']
        title=e.get('source_metadata',{}).get('title') or e['source_id']
        return f"[{cell(title)}]({e['url']})（網頁快照第 {locator['line_start']}–{locator['line_end']} 行；取得：{e['retrieved_at']}）"
    def stamp(t):
        return f'{int(t)//60:02d}:{int(t)%60:02d}'
    link = e['url'] + ('&t=' if '?' in e['url'] else '?t=') + str(int(e['start']))
    metadata=e.get('source_metadata', {})
    title=(metadata.get('uploader') if short else None) or metadata.get('title') or e['source_id']
    return f"[{title} {stamp(e['start'])}–{stamp(e['end'])}]({link})"


CONTEXT_LABELS = {'current_device':'現有設備', 'budget':'需求預算', 'region':'使用地區',
                  'needs':'使用需求／期望', 'phone':'通話手機'}


def report_context(s, a):
    # Explicitly quoted facts supplement presentation only; never mutate the Session.
    facts=a.get('report_context', {})
    if not isinstance(facts, dict) or set(facts)-set(CONTEXT_LABELS):
        raise ValueError('報告情境欄位無效')
    rows=[]
    for key,label in CONTEXT_LABELS.items():
        fact=facts.get(key)
        existing=s['context'].get(key)
        if fact is not None:
            if (not isinstance(fact,dict) or not isinstance(fact.get('value'),str)
                    or not fact['value'].strip() or not isinstance(fact.get('question_quote'),str)
                    or not fact['question_quote'].strip() or fact['question_quote'] not in s['question']
                    or fact['value'] not in fact['question_quote']):
                raise ValueError('報告情境需有研究問題原文依據：'+key)
            value=fact['value']
            basis='研究問題已提供'
            if existing and str(existing)!=value:
                basis+='；結構化記錄另載「'+str(existing)+'」，尚待釐清差異'
        elif existing is not None and existing != '' and isinstance(existing,(str,int,float)):
            value=str(existing);basis='沿用情境記錄，保留原確認狀態'
        else:
            continue
        if key=='phone' and not re.search(r'手機|通話|耳機|phone|iphone|microphone',s['title']+' '+s['question'],re.I):
            continue
        rows.append((label,value,basis))
    if not rows:
        return ''
    return '\n'.join(['| 研究條件 | 內容 | 依據 |','|---|---|---|']+
                     [f'| {cell(k)} | {cell(v)} | {cell(b)} |' for k,v,b in rows])


def reader_limitations(text):
    # Only remove known bookkeeping clauses; the original remains in appendix/JSON.
    return re.sub(r'(^|[；;。])\s*end(?:是|為|为)[^。；;\n]*(?:分析窗口|窗口邊界|窗口边界)[^。；;\n]*(?:cue|終點|终点)[^。；;\n]*',
                  lambda m: '。' if m.group(1)=='。' else '',text,flags=re.I).strip('；; ')


def full_report(s, a, selected):
    sections=a['deep']
    lines=[f'# {s["title"]}：完整研究報告',
           a.get('data_basis','取得與核對方式依逐項證據記錄；未核對事項不視為已完成。'),
           '## 1. 研究背景', sections['background'], report_context(s,a),
           '## 2. 結論摘要', a['summary'],
           '## 3. 產品與測項比較', sections.get('comparison_table',a['comparison']),
           '## 4. 來源清單與逐項證據' if any(x.get('source_type')=='web' for x in s['sources'].values()) else '## 4. 影片清單與逐片證據']
    types={'test_presented':'片中實測','reviewer_opinion':'作者意見','official_spec':'官方規格',
           'official_marketing':'官方宣傳','unverified':'未驗證說法','inference':'推論'}
    levels={'high':'高','medium':'中','low':'低','undetermined':'未定'}
    for sid,src in s['sources'].items():
        if not src['selected']:
            continue
        m=src['metadata']
        lines += [f"### {m.get('title') or '未提供標題'}",
                  f"作者：{m.get('uploader') or '未確認'}；發布日期：{m.get('upload_date') or '未確認'}；[原始來源]({src['url']})"]
        items=[e for e in selected if e['source_id']==sid]
        if not items:
            lines += ['本次未有可引用證據；不計為有效性能驗證，不推測測試方法或結果。']
        for e in items:
            nature = types[e['claim_type']]
            if e.get('source_type') == 'comment':
                nature = '影片評論／' + ('評論者意見' if e['claim_type']=='reviewer_opinion' else nature)
            elif e.get('source_type') == 'web' and e['claim_type']=='test_presented':
                nature = '來源呈現的測試'
            lines += [f"**觀察結果**：[E:{e['id']}] {e['claim']}",
                      f"- 測試方法／條件：{e['conditions']}",
                      f"- 產品／版本：{e['product_version']}",
                      f"- 證據性質：{nature}；支持程度：{levels[e['support']]}",
                      f"- 核對方式：{e['verification']}",
                      f"- 證據限制：{reader_limitations(e['limitations'])}"]
            lines += [f"- 原始來源關聯：{e.get('origin_root_id') or e.get('origin_source_id') or src.get('source_group') or '未確認；不據此視為獨立測試'}"]
            if e.get('assessment'):
                lines += [f"- 證據直接性：{e['assessment']['directness']}；方法：{e['assessment']['method']}；獨立性：{e['assessment']['independence']}"]
            if e.get('source_type') == 'comment':
                sampling=e['comment_sampling']
                lines += [f"- 評論取樣：{sampling['sort_order']}；{sampling['sampling_scope']}；按讚不代表真實性或代表性。"]
    lines += ['## 5. 交叉驗證與結果差異', sections['cross_validation']]
    if not a.get('topics_in_cross_validation',False):
        lines += ['### 補充主題',a['topics']]
    lines += ['## 6. 使用情境與維護取捨',sections['scenarios'],
              '## 7. 研究限制',a['limitations'], '## 8. 最終建議',sections['recommendation']]
    return '\n\n'.join(x for x in lines if x)


def report(store,s,analysis_file,layout='dual',mode='auto',_backend_review=False):
    a=read(analysis_file)
    if not _backend_review:
        from antigravity_backend import guard_report
        guard_report(store,s,a)
    for field in ('summary','topics','comparison','limitations','conclusion','evidence_ids'):
        if field not in a:
            raise ValueError('分析缺少欄位：'+field)
    if a['conclusion'] not in ('建議購買','有條件購買','保留現有設備','不建議購買','證據不足','一般影片分析','一般研究分析'):
        raise ValueError('結論類型無效')
    ev={e['id']:e for e in s['evidence']}
    if any(k not in ev for k in a['evidence_ids']):
        raise ValueError('分析引用不存在的證據')
    if a['conclusion'] not in ('證據不足','一般影片分析','一般研究分析') and not a['evidence_ids']:
        raise ValueError('購買結論必須有證據')
    # Require references to every selected evidence item in prose, and reject unknown tags.
    prose='\n'.join(str(a[k]) for k in ('summary','topics','comparison','limitations'))
    tags=set(re.findall(r'\[E:([a-f0-9]{12})\]',prose))
    if tags!=set(a['evidence_ids']):
        raise ValueError('文字需以 [E:證據ID] 對應 evidence_ids，且不得引用未知證據')
    if layout not in ('dual','legacy'):
        raise ValueError('報告格式無效')
    mode=report_mode(s,a,mode)
    deep=a.get('deep',{})
    if mode=='deep' and layout!='legacy':
        for field in ('background','cross_validation','scenarios','recommendation'):
            if not isinstance(deep.get(field),str) or not deep[field].strip():
                raise ValueError('Deep 完整分析缺少欄位：'+field)
        for field in ('cross_validation','scenarios','recommendation'):
            if not re.search(r'\[E:[a-f0-9]{12}\]',deep[field]):
                raise ValueError('Deep 重要結論需引用證據：'+field)
        deep_tags=set(re.findall(r'\[E:([a-f0-9]{12})\]', '\n'.join(deep.values())))
        if deep_tags-set(a['evidence_ids']):
            raise ValueError('Deep 引用未選用的證據')
    resolved_context=report_context(s,a)
    decision=a.get('decision')
    if decision is not None:
        for field in ('recommendation','comparison','confidence','key_limitations','next_step'):
            if field not in decision:
                raise ValueError('決策摘要缺少欄位：'+field)
        if not isinstance(decision['key_limitations'],list) or not 1<=len(decision['key_limitations'])<=3:
            raise ValueError('決策摘要需有一至三項關鍵限制')
        texts=[decision[k] for k in ('recommendation','comparison','confidence','next_step')]+decision['key_limitations']
        if any(not isinstance(t,str) or not t.strip() for t in texts):
            raise ValueError('決策摘要欄位必須為非空文字')
        decision_text='\n'.join(texts)
        if len(decision_text)>2400:
            raise ValueError('決策摘要過長；完整分析請放附錄')
        decision_tags=set(re.findall(r'\[E:([a-f0-9]{12})\]',decision_text))
        if decision_tags-set(a['evidence_ids']):
            raise ValueError('決策摘要引用未選用的證據')
        if a['conclusion'] not in ('證據不足','一般影片分析','一般研究分析') and not decision_tags:
            raise ValueError('決策摘要的購買結論必須引用證據')
    selected=[ev[k] for k in a['evidence_ids']]
    for e in selected:
        store.allowed(s,e['source_id']);store.artifact(s,e['artifact_key'])
    provenance=dict(rules_version=VERSION,engine=a.get('analysis_engine','Human or Agent analysis; exact model unconfirmed'))
    key=digest([provenance,s['question'],s['context'],s['revision'],a,selected,mode,layout])
    base=store.data/'sessions'/s['id']/'reports'
    base.mkdir(parents=True,exist_ok=True)
    p=base/(now().replace(':','-')+'-'+key[:8]+'.md')
    lines=[f'# {s["title"]}','', '## 1. 基本資訊',
           f'研究 ID：{s["id"]}；版本：{s["revision"]}；產出時間：{now()}',
           f'研究問題：{s["question"]}',candidate_table(s),
           '## 2. 重點摘要',a['summary'],f'結論：{a["conclusion"]}',
           '## 3. 主題分析',a['topics'],'## 4. 實際測試結果與證據']
    for e in selected:
        lines.extend([f"- [E:{e['id']}] {e['claim']}（{e['claim_type']}／{e['support']}）",
                      f"  條件：{e['conditions']}；版本：{e['product_version']}；核對方式：{e['verification']}",
                      f"  理由：{e['reason']}；限制：{e['limitations']}"])
        if e.get('origin_source_id'):
            lines.append(f"  引用／轉載原始來源：{e['origin_source_id']}；共同根來源：{e['origin_root_id']}")
        if e.get('assessment'):
            lines.append('  證據評估：'+json.dumps(e['assessment'],ensure_ascii=False))
    lines.extend(['## 5. 多來源／多產品比較',a['comparison'],'## 6. 可信度、限制、衝突與缺口',
                  a['limitations'],json.dumps(s['conflicts'],ensure_ascii=False),json.dumps(s['gaps'],ensure_ascii=False),
                  '本報告引用歷史快照；來源是否更新需另查核。字幕與 ASR 不足以證明實際收音品質。',
                  '## 7. 原始定位與來源連結'])
    for e in selected:
        if e.get('source_type') == 'comment':
            lines.append(f"- [E:{e['id']}] {evidence_link(e)}；快照 SHA-256：{e['snapshot_hash']}；素材：{e['artifact_path']}；原文：{e['excerpt']}")
            continue
        if e.get('source_type') == 'web':
            lines.append(f"- [E:{e['id']}] {evidence_link(e)}；快照 SHA-256：{e['snapshot_hash']}；素材：{e['artifact_path']}；原文：{e['excerpt']}")
            continue
        link=e['url']+('&t=' if '?' in e['url'] else '?t=')+str(int(e['start']))
        lines.append(f"- [E:{e['id']}] [{e['source_id']} {e['start']}–{e['end']} 秒]({link})；記錄：{e['recorded_at']}；素材：{e['artifact_path']}")
    if a.get('backend_provenance') is not None:
        bp=a['backend_provenance']
        lines.append('Antigravity → Codex 接手：'+('是；原因：'+str(bp.get('reason')) if bp['handoff'] else '否；Codex 已審核並整合後端草稿。'))
    p.write_text('\n\n'.join(lines),encoding='utf-8')
    snapshot=dict(research_mode=mode,layout=layout,analysis=a,evidence=selected,session_revision=s['revision'],context=s['context'],analysis_key=key,provenance=provenance,created_at=now())
    write(p.with_suffix('.json'),snapshot)
    if layout=='legacy':
        return str(p)
    appendix=p.with_name(p.stem+'.appendix.md')
    primary=p.with_name(p.stem+('.full.md' if mode=='deep' else '.decision.md'))
    context=resolved_context
    footer=(f'\n\n---\n\n研究快照：{s["id"]}／revision {s["revision"]}；analysis_key：{key}'
            f'\n\n情境設定（依記錄保留確認狀態）：\n\n{context}'
            f'\n\n[結構化證據與情境快照]({p.with_suffix(".json").name})'
            f'\n\n[主報告]({primary.name})；[七節 Legacy 報告]({p.name})')
    appendix.write_text(p.read_text(encoding='utf-8')+footer+'\n\n## 報告呈現設定與原始情境\n\n```json\n'+json.dumps(dict(context=s['context'],report_context=a.get('report_context',{}),research_question=s['question'],data_basis=a.get('data_basis')),ensure_ascii=False,indent=2)+'\n```',encoding='utf-8')
    # Old analyses remain valid; fallback is extractive and makes no new performance claims.
    decision=decision or dict(recommendation=a['summary'],comparison=a['comparison'],
        confidence='本摘要沿用完整分析；未額外驗證或提高原證據可信度。',
        key_limitations=[a['limitations']],next_step='依附錄列出的證據缺口安排下一步；未知項仍待確認。')
    sections=[f'# {s["title"]}：決策主報告',
        f'研究 {s["id"]}／revision {s["revision"]}；結論：{a["conclusion"]}',
        decision['recommendation'],context,decision['comparison'],
        '可信度：'+decision['confidence'],'關鍵限制：\n\n'+'\n'.join('- '+t for t in decision['key_limitations']),
        '下一步：'+decision['next_step'],
        f'[完整證據附錄]({appendix.name})；[證據快照]({p.with_suffix(".json").name})',
        f'analysis_key：{key}']
    text=(full_report(s,a,selected)+f'\n\n---\n\n[技術附錄與完整證據記錄]({appendix.name})；[證據快照]({p.with_suffix(".json").name})'
          if mode=='deep' else '\n\n'.join(sections))
    # Resolve citations in the primary itself so readers never need the appendix.
    by_id={e['id']:e for e in selected}
    text=re.sub(r'\[E:([a-f0-9]{12})\]',
                lambda m: m.group(0)+' '+evidence_link(by_id[m.group(1)],short=mode=='deep')+' ',text)
    if a.get('backend_provenance') is not None:
        bp=a['backend_provenance']
        note=('Antigravity → Codex 接手：是；原因：'+str(bp.get('reason')) if bp['handoff'] else
              'Antigravity → Codex 接手：否；後端草稿已由目前 Codex 工作階段完成語意審核與整合。')
        text+='\n\n'+note
    primary.write_text(text,encoding='utf-8')
    return str(primary)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data');p.add_argument('--cache')
    sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('create');q.add_argument('--title',required=True);q.add_argument('--question',required=True);q.add_argument('--seed',action='append',default=[])
    sub.add_parser('list')
    q=sub.add_parser('analyze');q.add_argument('session');q.add_argument('--timeout',type=int,default=600)
    q=sub.add_parser('backend-handoff');q.add_argument('session');q.add_argument('--reason',choices=['authorization_denied','authorized_execution_unavailable'],required=True)
    q=sub.add_parser('backend-launch');q.add_argument('session');q.add_argument('--timeout',type=int,default=600)
    q=sub.add_parser('backend-status');q.add_argument('session')
    q=sub.add_parser('backend-finish');q.add_argument('session');q.add_argument('file');q.add_argument('review')
    q.add_argument('--mode',choices=['auto','quick','deep'],default='auto')
    q.add_argument('--layout',choices=['dual','legacy'],default='dual')
    for name in ('show','candidates','inspect','discover','import-candidates','select','acquire','transcript','transcribe','extract','evidence','report','update','research-policy','import-subtitles','import-web','import-comments','comments','research-status','research-plan','query-reserve','query-search-result','query-complete','query-cancel'):
        q=sub.add_parser(name);q.add_argument('session')
        if name in ('inspect','acquire','transcript','transcribe','extract','comments'):
            q.add_argument('source')
        if name in ('inspect','discover','acquire'):
            q.add_argument('--refresh',action='store_true')
        if name=='discover':
            q.add_argument('--query',action='append',required=True);q.add_argument('--limit',type=int,default=15)
        if name in ('discover','import-candidates','evidence'):
            q.add_argument('--reservation')
        if name in ('query-search-result','query-complete','query-cancel'):q.add_argument('reservation')
        if name in ('import-candidates','evidence','report','update','import-subtitles','import-web','import-comments','research-plan','query-search-result','query-complete'):
            q.add_argument('file')
        if name=='research-plan':
            q.add_argument('--new-round',action='store_true');q.add_argument('--actor',choices=['user','automatic'])
            q.add_argument('--reason')
        if name=='query-reserve':q.add_argument('query_id')
        if name=='query-cancel':q.add_argument('--reason',required=True)
        if name=='report':
            q.add_argument('--layout',choices=['dual','legacy'],default='dual')
            q.add_argument('--mode',choices=['auto','quick','deep'],default='auto')
        if name=='research-policy':
            q.add_argument('--mode',choices=['automatic','interactive'],required=True)
            q.add_argument('--max-auto-sources',type=int)
        if name=='select':
            q.add_argument('ids',nargs='+');q.add_argument('--exclude',action='store_true');q.add_argument('--reason',required=True);q.add_argument('--actor',choices=['user','automatic'],default='user')
        if name=='acquire':
            q.add_argument('--kind',choices=['subtitles','audio','video'],default='subtitles')
        if name=='transcribe':
            q.add_argument('--backend',choices=['whisper.cpp','faster-whisper'],required=True);q.add_argument('--model',default='base');q.add_argument('--language',default='zh')
        if name=='extract':
            q.add_argument('--kind',choices=['clip','frames'],required=True);q.add_argument('--start',type=float,required=True);q.add_argument('--end',type=float,required=True);q.add_argument('--count',type=int,default=6)
    q=sub.add_parser('audio-analyze');q.add_argument('session');q.add_argument('source')
    q.add_argument('--artifact-key',required=True);q.add_argument('--source-offset',type=float,required=True)
    q.add_argument('--clip-start',type=float,default=0);q.add_argument('--clip-end',type=float)
    q.add_argument('--enable',action='store_true');q.add_argument('--config')
    sub.add_parser('cache-status')
    args=p.parse_args();store=Store(args.data,args.cache)
    # A cancellation marker must not wait behind the network writer's lock.
    if args.cmd=='query-cancel':
        try:
            from research_ledger import cancel
            out=cancel(store,store.session(args.session),args.reservation,args.reason)
            print(json.dumps(out,ensure_ascii=False,indent=2));return
        except Exception as error:
            print(json.dumps(dict(status='blocked',error=str(error)),ensure_ascii=False),file=sys.stderr);sys.exit(2)
    lock=(store.data/'writer.lock').open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        print('此資料目錄已有作業執行，請待完成後再試',file=sys.stderr);sys.exit(2)
    try:
        if args.cmd=='create': out=store.create(args.title,args.question,args.seed)
        elif args.cmd=='list':
            out=[{k:read(f).get(k) for k in ('id','title','question','updated_at')} for f in sorted((store.data/'sessions').glob('*/session.json'))]
        elif args.cmd=='cache-status':
            out=dict(used_bytes=sum(p.stat().st_size for p in store.cache.rglob('*') if p.is_file()),limit_bytes=LIMIT,
                     artifacts=store.db.execute('SELECT kind,COUNT(*),SUM(hits) FROM artifacts GROUP BY kind').fetchall(),
                     protected=store.db.execute('SELECT COUNT(*) FROM pins').fetchone()[0],automatic_eviction=False)
        else:
            s=store.session(args.session)
            if args.cmd=='audio-analyze':
                from audio_analysis.pipeline import analyze
                config=read(args.config) if args.config else {}
                # Only this explicit one-shot opt-in enables processing; runtime default remains false.
                config['enabled']=args.enable
                out=analyze(store,s,args.source,args.artifact_key,args.source_offset,config,args.clip_start,args.clip_end)
            elif args.cmd=='analyze':
                from antigravity_backend import delegate
                if not 1<=args.timeout<=1800: raise ValueError('timeout must be 1..1800 seconds')
                out=delegate(store,s,args.timeout)
            elif args.cmd=='backend-handoff':
                from antigravity_backend import host_handoff
                out=host_handoff(store,s,args.reason)
            elif args.cmd=='backend-launch':
                from antigravity_backend import launch_request
                out=launch_request(store,s,args.timeout)
            elif args.cmd=='backend-status':
                from antigravity_backend import directory,fingerprint
                path=directory(store,s)/'state.json'
                out=read(path) if path.exists() else dict(status='not_started')
                out['current_session_fingerprint']=fingerprint(s)
            elif args.cmd=='backend-finish':
                from antigravity_backend import finish
                out=finish(store,s,args.file,args.review,args.mode,args.layout)
            elif args.cmd=='show':out=s
            elif args.cmd=='candidates':print(candidate_table(s));return
            elif args.cmd=='inspect':out=inspect_source(store,s,args.source,args.refresh)
            elif args.cmd=='discover':out=discover(store,s,args.query,args.limit,args.refresh,args.reservation)
            elif args.cmd=='research-status':
                from research_ledger import status
                out=status(store,s)
            elif args.cmd=='research-plan':
                from research_ledger import make_plan
                out=make_plan(store,s,read(args.file),new_round=args.new_round,actor=args.actor,reason=args.reason)
            elif args.cmd=='query-reserve':
                from research_ledger import reserve
                out=reserve(store,s,args.query_id)
            elif args.cmd=='query-search-result':
                from research_ledger import search_result
                out=search_result(store,s,args.reservation,read(args.file))
            elif args.cmd=='query-complete':
                from research_ledger import complete
                out=complete(store,s,args.reservation,read(args.file))
            elif args.cmd=='import-web':
                from web_sources import import_snapshot
                out=import_snapshot(store,s,args.file)
            elif args.cmd=='import-comments':
                from video_comments import import_comments
                out=import_comments(store,s,args.file)
            elif args.cmd=='comments':
                from video_comments import snapshots
                out=snapshots(store,s,args.source)
            elif args.cmd=='import-subtitles':
                from external_subtitles import import_subtitles
                out=import_subtitles(store,s,args.file)
                if out['status']=='blocked':
                    print(json.dumps(out,ensure_ascii=False,indent=2));sys.exit(2)
            elif args.cmd=='import-candidates':out=import_candidates(store,s,read(args.file),args.reservation)
            elif args.cmd=='research-policy':out=configure_research(store,s,args.mode,args.max_auto_sources)
            elif args.cmd=='select':select(store,s,args.ids,args.exclude,args.reason,args.actor);out=s['selection_events']
            elif args.cmd=='acquire':out=acquire(store,s,args.source,args.kind,args.refresh)
            elif args.cmd=='transcript':out=transcripts(store,s,args.source)
            elif args.cmd=='transcribe':out=transcribe(store,s,args.source,args.backend,args.model,args.language)
            elif args.cmd=='extract':out=extract(store,s,args.source,args.kind,args.start,args.end,args.count)
            elif args.cmd=='evidence':out=add_evidence(store,s,read(args.file),args.reservation)
            elif args.cmd=='report':out=report(store,s,args.file,args.layout,args.mode)
            elif args.cmd=='update':
                changes=read(args.file)
                if set(changes)-{'question','products','context','conflicts','gaps'}:
                    raise ValueError('只可更新研究問題、產品、情境、衝突與缺口')
                s.update(changes);store.save(s);out=s
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except Exception as e:
        message=str(e) if isinstance(e,(ValueError,RuntimeError,KeyError,FileNotFoundError,subprocess.TimeoutExpired)) else type(e).__name__+'；取得受阻，請檢查平台與網路狀態'
        failure=dict(status='blocked',error=message)
        if isinstance(e,AcquisitionError):
            failure['error_code']=e.code
        print(json.dumps(failure,ensure_ascii=False),file=sys.stderr);sys.exit(2)

if __name__=='__main__':
    main()
