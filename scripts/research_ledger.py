"""Gap-bound query reservations in existing Session.research_rounds.

No model, crawler, new cache or Evidence store. CLI holds the existing writer
lock. Cancellation uses an atomic marker so it can interrupt that writer's
network operation without a second Session writer.
"""
import copy
import contextlib
import fcntl
import re
import unicodedata
import uuid


def api():
    import va
    return va


def natural(value):
    if type(value) is not int or value < 0:
        raise ValueError('預算／數量必須為非負整數')
    return value


def fingerprint(provider, query):
    return api().digest([provider.strip().casefold(), ' '.join(unicodedata.normalize('NFKC',query).casefold().split())])


def admitted(s):
    return {e['source_id'] for e in s.get('selection_events',[]) if e.get('actor')=='automatic' and e.get('selected')}


def cache_used(store):
    return sum(p.stat().st_size for p in store.cache.rglob('*') if p.is_file())


def gaps(s):
    values=s.get('gaps') or [s['question']]
    result=[]
    for index,value in enumerate(values):
        text=value if isinstance(value,str) else value.get('description',value.get('text',''))
        if not isinstance(text,str) or not text.strip(): raise ValueError('缺口須有可核對文字')
        result.append(dict(gap_id='gap-'+api().digest([s['id'],index,value])[:12],text=text,
                           original_index=index if s.get('gaps') else None,
                           existing_evidence_ids=[e['id'] for e in s['evidence']]))
    return result


def active(s):
    rounds=s.get('research_rounds',[])
    return next((r for r in reversed(rounds) if r.get('ledger_version')==1),None)


def event(r,status,**fields):
    previous=r['events'][-1]['hash'] if r['events'] else '0'*64
    e=dict(seq=len(r['events'])+1,at=api().now(),status=status,previous_hash=previous,**fields)
    e['hash']=api().digest(e);r['events'].append(e)
    return e


def token_query(r,token):
    q=next((q for q in r['queries'] if q.get('token')==token),None)
    if q is None: raise ValueError('查詢 reservation 不屬於目前研究輪次')
    return q


def marker(store,s,token):
    if not re.fullmatch('[a-f0-9]{32}',token): raise ValueError('無效 reservation')
    return store.data/'sessions'/s['id']/'research-cancellations'/(token+'.json')


@contextlib.contextmanager
def commit_guard(store,s,token):
    if token is None:
        yield
        return
    path=marker(store,s,token).with_suffix('.lock');path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def sync_cancel(store,s):
    r=active(s)
    if not r:return
    changed=False
    for q in r['queries']:
        if q.get('token') and q['status'] in ('reserved','searching','awaiting_evidence') and marker(store,s,q['token']).exists():
            q['status']='cancelled';q['stop_reason']='cancelled';r['stop_reason']='cancelled'
            event(r,'cancelled',query_id=q['query_id'],token=q['token'],stop_reason='cancelled');changed=True
    if changed:api().Store.save(store,s)


def status(store,s):
    # Read-only projection: markers are persisted independently from Session history.
    view=copy.deepcopy(s);r=active(view)
    if r:
        for q in r['queries']:
            if q.get('token') and q['status'] in ('reserved','searching','awaiting_evidence') and marker(store,s,q['token']).exists():
                q['status']='cancelled';q['stop_reason']='cancelled';r['stop_reason']='cancelled'
    return dict(gaps=gaps(s),round=r,source_limit=s.get('research_policy',{}).get('max_auto_sources',3),
                historical_admitted=sorted(admitted(s)),cache_bytes=cache_used(store))


def import_legacy(s):
    rounds=s.get('research_rounds',[])
    # A later narrative/analysis round must not hide an exhausted search round.
    relevant=[(i,r) for i,r in enumerate(rounds) if 'queries' in r or
              any(k in r.get('budget',{}) for k in ('queries_used','max_new_queries'))]
    index,last=relevant[-1] if relevant else (None,None)
    budget=(last or {}).get('budget',{})
    raw=(last or {}).get('queries',s.get('searches',[]))
    if not isinstance(raw,list): raise ValueError('舊搜尋紀錄無法安全遷移；先人工核對')
    prior=[]
    for item in raw:
        if isinstance(item,str):query=item;provider=(last or {}).get('provider','legacy-unknown')
        elif isinstance(item,dict):query=item.get('query');provider=item.get('provider','legacy-unknown')
        else:raise ValueError('舊搜尋紀錄無法安全遷移')
        if not isinstance(query,str) or not query.strip():raise ValueError('舊查詢缺少原文，不能假定額度未使用')
        prior.append(dict(query=query,provider=provider,fingerprint=fingerprint(provider,query)))
    used=max(len(prior),natural(budget.get('queries_used',0)))
    limit=min(4,natural(budget.get('max_new_queries',4)))
    return dict(prior_queries=prior,queries_used=used,max_new_queries=limit,
                legacy_index=index,legacy_hash=api().digest(last) if last else None)


def make_plan(store,s,spec,*,new_round=False,actor=None,reason=None):
    va=api();sync_cancel(store,s)
    policy=s.get('research_policy',{'mode':'interactive'})
    if policy.get('mode')!='automatic':raise ValueError('互動／舊 Session 不自動遷移研究模式')
    if new_round and (actor!='user' or not isinstance(reason,str) or not reason.strip()):
        raise ValueError('新輪次須有真正使用者續作指示、--actor user 與 --reason；不能自行重設額度')
    old=active(s)
    if new_round and old and any(q['status'] in ('reserved','searching','awaiting_evidence') for q in old['queries']):
        raise ValueError('尚有未完成查詢；先完成或取消，不開新輪次')
    limit=natural(spec.get('max_new_queries',4))
    if limit>4:raise ValueError('每輪查詢上限不得自動提高至四組以上')
    gs=gaps(s);known={g['gap_id']:g for g in gs};queries=[];seen=set()
    if not isinstance(spec.get('queries'),list) or not 1<=len(spec['queries'])<=30:raise ValueError('計畫需有 1～30 個查詢候選，不代表可全部執行')
    for item in spec['queries']:
        q=copy.deepcopy(item)
        if q.get('gap_id') not in known:raise ValueError('每個查詢須綁定現有 gap_id；先 research-status')
        for field in ('provider','query','purpose','expected_value'):
            if not isinstance(q.get(field),str) or not q[field].strip():raise ValueError('缺少查詢欄位：'+field)
        b=q.get('budget',{})
        if set(b)!={'query_groups','max_new_sources','max_new_candidates','cache_bytes','paid_api_calls'}:raise ValueError('每個查詢須明列完整預算')
        for v in b.values():natural(v)
        if b['query_groups']!=1 or b['paid_api_calls']!=0:raise ValueError('每個字串算一組查詢；不允許付費 API')
        fp=fingerprint(q['provider'],q['query'])
        if fp in seen:raise ValueError('計畫內有重複 query fingerprint')
        seen.add(fp)
        q.update(query_id='q-'+fp[:16],fingerprint=fp,gap=copy.deepcopy(known[q['gap_id']]),status='planned')
        queries.append(q)
    if old and not new_round:
        if old['stop_reason']:raise ValueError('本輪已停止：'+old['stop_reason'])
        existing={q['query_id']:q for q in old['queries']}
        for q in queries:
            previous=existing.get(q['query_id'])
            if previous and any(previous.get(k)!=q.get(k) for k in ('gap_id','provider','query','purpose','expected_value','budget')):
                raise ValueError('既有查詢不可原地修改；保留原計畫與帳本')
        additions=[q for q in queries if q['query_id'] not in existing]
        if len(old['queries'])+len(additions)>30:raise ValueError('查詢計畫候選上限 30')
        old['queries'].extend(additions);old['limits']['query_groups']=min(old['limits']['query_groups'],limit)
        event(old,'plan_extended',new_queries=len(additions));va.Store.save(store,s);return old
    legacy=import_legacy(s) if not new_round else dict(prior_queries=[],queries_used=0,max_new_queries=4,legacy_index=None,legacy_hash=None)
    inherited_limit=old['limits']['query_groups'] if old else import_legacy(s)['max_new_queries']
    round_limit=min(limit,legacy['max_new_queries'],inherited_limit,natural(policy.get('max_new_queries',4)))
    r=dict(ledger_version=1,id='r-'+uuid.uuid4().hex[:16],kind='gap_query_ledger',created_at=va.now(),
           authorization=dict(actor=actor or 'automatic',reason=reason or '沿用目前輪次及既有查詢額度'),
           migration=legacy,limits=dict(query_groups=round_limit,auto_sources=natural(policy.get('max_auto_sources',3)),
                                       candidates=30,cache_bytes=va.LIMIT,paid_api_calls=0),
           queries_used=legacy['queries_used'],queries=queries,events=[],stop_reason=None)
    if r['queries_used']>=round_limit:r['stop_reason']='query_budget_exhausted'
    event(r,'round_opened',stop_reason=r['stop_reason'])
    s.setdefault('research_rounds',[]).append(r);va.Store.save(store,s);return r


def reserve(store,s,query_id):
    va=api();sync_cancel(store,s);r=active(s)
    if not r:raise ValueError('先 research-status 與 research-plan；不能跳過缺口計畫')
    q=next((q for q in r['queries'] if q['query_id']==query_id),None)
    if not q:raise ValueError('計畫中沒有此 query_id')
    reason=r['stop_reason']
    if not reason and s.get('research_policy',{}).get('mode')!='automatic':reason='interactive_requires_user'
    if not reason and q['status']!='planned':reason='duplicate_query'
    if not reason and any(x['status'] in ('reserved','searching','awaiting_evidence') for x in r['queries']):reason='previous_query_requires_review'
    if not reason and q['fingerprint'] in {p['fingerprint'] for p in r['migration']['prior_queries']}:reason='duplicate_query'
    if not reason and r['queries_used']>=r['limits']['query_groups']:reason='query_budget_exhausted'
    cap=min(r['limits']['auto_sources'],s.get('research_policy',{}).get('max_auto_sources',3))
    if not reason and len(admitted(s))+q['budget']['max_new_sources']>cap:reason='source_budget_exhausted'
    if not reason and sum(x.get('role')=='candidate' for x in s['sources'].values())+q['budget']['max_new_candidates']>30:reason='candidate_budget_exhausted'
    used=cache_used(store)
    if not reason and used+q['budget']['cache_bytes']>min(va.LIMIT,r['limits']['cache_bytes']):reason='cache_budget_exhausted'
    if not reason and q['gap_id'] not in {g['gap_id'] for g in gaps(s)}:reason='gap_changed_requires_review'
    if reason:
        if reason.endswith('budget_exhausted'):r['stop_reason']=reason
        event(r,'blocked',query_id=query_id,fingerprint=q['fingerprint'],stop_reason=reason,dispatched=False)
        va.Store.save(store,s);raise ValueError('查詢已攔截：'+reason)
    q.update(status='reserved',token=uuid.uuid4().hex,baseline_evidence={e['id']:va.digest(e) for e in s['evidence']},
             baseline_evidence_keys=[evidence_key(e,s['sources']) for e in s['evidence']],baseline_sources=sorted(s['sources']),
             baseline_admitted=sorted(admitted(s)),baseline_cache_bytes=used,
             baseline_origin_roots=sorted({va.source_origin(s['sources'],e.get('origin_source_id',e['source_id'])) for e in s['evidence']}))
    r['queries_used']+=1
    event(r,'reserved',query_id=query_id,token=q['token'],gap_id=q['gap_id'],fingerprint=q['fingerprint'],
          purpose=q['purpose'],expected_value=q['expected_value'],budget=q['budget'],queries_used=r['queries_used'])
    va.Store.save(store,s)
    return dict(round_id=r['id'],query_id=query_id,reservation=q['token'],provider=q['provider'],query=q['query'],
                gap_id=q['gap_id'],budget=q['budget'],status=q['status'],queries_used=r['queries_used'])


def check(store,s,token,states=('reserved','searching','awaiting_evidence')):
    sync_cancel(store,s);r=active(s)
    if not r:raise ValueError('沒有研究帳本')
    q=token_query(r,token)
    if r['stop_reason'] or q['status'] not in states:raise ValueError('查詢不再有效：'+str(r['stop_reason'] or q['status']))
    return r,q


def cancel(store,s,token,reason):
    r=active(s)
    if not r:raise ValueError('沒有研究帳本')
    q=token_query(r,token)
    if q['status'] not in ('reserved','searching','awaiting_evidence','cancelled'):raise ValueError('已結束查詢不能再取消')
    if not isinstance(reason,str) or not reason.strip():raise ValueError('取消需記錄原因')
    with commit_guard(store,s,token):
        latest=store.session(s['id']);current_round=active(latest)
        current_query=token_query(current_round,token) if current_round else None
        if current_query is None or current_query['status'] not in ('reserved','searching','awaiting_evidence','cancelled'):
            raise ValueError('查詢已結束，不能取消已提交結果')
        api().write(marker(store,s,token),dict(at=api().now(),reason=reason,token=token))
    return dict(status='cancelled',reservation=token,stop_reason='cancelled')


def search_result(store,s,token,result):
    with commit_guard(store,s,token):return _search_result(store,s,token,result)


def _search_result(store,s,token,result):
    va=api();r,q=check(store,s,token,('reserved','searching'))
    state=result.get('status');count=natural(result.get('result_count',0))
    if natural(result.get('paid_api_calls',0))!=0:raise ValueError('本研究不允許額外付費 API；不能把付費用量記成零')
    if state not in ('completed','failed','blocked'):raise ValueError('搜尋結果狀態無效')
    q['status']='awaiting_evidence' if state=='completed' else 'failed'
    q['search_result']=dict(status=state,result_count=count,reason=result.get('reason','未提供'))
    if state!='completed':q['stop_reason']='provider_failed';r['stop_reason']='provider_failed'
    event(r,'search_'+state,query_id=q['query_id'],token=token,result_count=count,stop_reason=r['stop_reason'])
    va.Store.save(store,s);return dict(status=q['status'],stop_reason=r['stop_reason'],reservation=token)


def candidate_gate(store,s,token,items):
    va=api();r,q=check(store,s,token)
    new=set()
    for item in items:
        if item.get('source_type','video')=='web':
            from web_sources import identity
        else:identity=va.identity
        new.add(identity(item['url'])[0])
    all_new=(set(s['sources'])|new)-set(q['baseline_sources'])
    if len(all_new)>q['budget']['max_new_candidates']:raise ValueError('本查詢候選增量超過 reservation')


def source_gate(store,s,ids):
    """Keep select's original cumulative cap; add the active reservation cap."""
    sync_cancel(store,s);r=active(s)
    if not r:return
    if r['stop_reason']:raise ValueError('本輪已停止：'+r['stop_reason'])
    pending=[q for q in r['queries'] if q['status'] in ('reserved','searching','awaiting_evidence')]
    if len(pending)!=1:raise ValueError('先保留查詢額度再自動納入新來源')
    q=pending[0]
    additions=(admitted(s)|{sid for sid in ids if sid in s['sources'] and not s['sources'][sid]['selected']})-set(q['baseline_admitted'])
    if len(additions)>q['budget']['max_new_sources']:raise ValueError('本查詢來源增量超過 reservation')


def cache_gate(store,s,token,additional_bytes):
    r,q=check(store,s,token)
    if cache_used(store)+additional_bytes-q['baseline_cache_bytes']>q['budget']['cache_bytes']:
        raise ValueError('本查詢搜尋快取超過 reservation')


def evidence_key(e,sources):
    va=api()
    return va.digest([va.source_origin(sources,e.get('origin_source_id',e['source_id'])),e['artifact_key'],
                      e.get('locator'),e.get('start'),e.get('end'),e.get('excerpt'),e['claim']])


class ReadOnlyStore:
    validation_only=True
    def __init__(self,store):self.store=store
    def allowed(self,s,sid):return self.store.allowed(s,sid)
    def artifact(self,s,key):
        va=api();key=self.store.resolve(key)
        if not re.fullmatch('[a-f0-9]{64}',key):raise ValueError('無效 artifact key')
        row=self.store.db.execute('SELECT hash FROM artifacts WHERE key=?',(key,)).fetchone()
        files=list((self.store.data/'sessions'/s['id']/'artifacts').glob(key+'.*'))
        if row and files and va.sha(files[0])==row[0]:return files[0]
        raise ValueError('證據素材不存在或 hash 不符')
    def pin(self,s,key):return str(self.artifact(s,key))
    def save(self,s):pass


def complete(store,s,token,receipt):
    with commit_guard(store,s,token):return _complete(store,s,token,receipt)


def _complete(store,s,token,receipt):
    va=api();r,q=check(store,s,token,('awaiting_evidence',))
    if q['gap_id'] not in {g['gap_id'] for g in gaps(s)}:raise ValueError('缺口已變更；保留原紀錄待人工核對')
    if len(admitted(s)-set(q['baseline_admitted']))>q['budget']['max_new_sources']:
        raise ValueError('本查詢來源增量超過 reservation，不能登記完成')
    if len(set(s['sources'])-set(q['baseline_sources']))>q['budget']['max_new_candidates']:
        raise ValueError('本查詢候選增量超過 reservation，不能登記完成')
    current={e['id']:e for e in s['evidence']}
    if len(current)!=len(s['evidence']) or any(k not in current or va.digest(current[k])!=h for k,h in q['baseline_evidence'].items()):
        raise ValueError('舊 Evidence 被改動；保留帳本並停止人工核對')
    reviews=receipt.get('reviews',[])
    if not isinstance(reviews,list):raise ValueError('reviews 必須為陣列')
    if any(not isinstance(x,dict) or x.get('evidence_id') not in current for x in reviews):raise ValueError('review 必須引用存在的 Evidence')
    review_map={x['evidence_id']:x for x in reviews}
    if len(review_map)!=len(reviews):raise ValueError('Evidence review 重複')
    delta=[e for e in s['evidence'] if e['id'] not in q['baseline_evidence'] and e.get('query_reservation')==token]
    if set(review_map)-{e['id'] for e in delta}:raise ValueError('不可將舊證據或其他查詢證據計為本次增量')
    keys=set(q['baseline_evidence_keys']);effective=[];roots=set();decisions=[]
    for e in delta:
        va.add_evidence(ReadOnlyStore(store),copy.deepcopy(s),copy.deepcopy(e))
        review=review_map.get(e['id'],{});key=evidence_key(e,s['sources'])
        root=va.source_origin(s['sources'],e.get('origin_source_id',e['source_id']))
        eligible=(key not in keys and review.get('gap_id')==q['gap_id'] and review.get('basis')=='source_content_review'
                  and review.get('addresses_gap') is True and isinstance(review.get('relevance_reason'),str)
                  and bool(review['relevance_reason'].strip()) and e['claim_type'] not in ('unverified','inference')
                  and e['support']!='undetermined')
        keys.add(key)
        if eligible:
            effective.append(e['id'])
            if root==e['source_id'] and review.get('independence_basis')=='reviewed_original_content' and isinstance(review.get('independence_reason'),str) and review['independence_reason'].strip():roots.add(root)
        decisions.append(dict(evidence_id=e['id'],effective=eligible,origin_root_id=root,review=review))
    independent=roots-set(q['baseline_origin_roots'])
    q.update(status='completed',effective_evidence_delta=len(effective),observed_evidence_delta=len(delta),
             independent_source_delta=len(independent),new_evidence_ids=effective,independent_roots=sorted(independent),decisions=decisions,
             stop_reason='zero_new_value' if not effective else None,
             usage=dict(query_groups=1,source_admission_delta=len(admitted(s)-set(q['baseline_admitted'])),
                        cache_bytes_delta=max(0,cache_used(store)-q['baseline_cache_bytes']),paid_api_calls=0))
    r['stop_reason']=q['stop_reason']
    event(r,'completed',query_id=q['query_id'],token=token,gap_id=q['gap_id'],fingerprint=q['fingerprint'],
          effective_evidence_delta=len(effective),independent_source_delta=len(independent),stop_reason=r['stop_reason'])
    va.Store.save(store,s)
    return dict(status=q['status'],effective_evidence_delta=len(effective),independent_source_delta=len(independent),
                stop_reason=r['stop_reason'],gap_status='open',usage=q['usage'])
