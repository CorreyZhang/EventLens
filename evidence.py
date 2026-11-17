"""Citation validation and conservative, auditable event state recomputation."""
import hashlib
from datetime import date
from providers import canonical

KINDS={'FACT','OPINION','SPECULATION','RUMOR'}
STANCES={'supports','reported','disputes','corrects','update'}

def validate_ref(ref, sources):
    if not isinstance(ref,dict): raise ValueError('引用格式错误')
    source=next((s for s in sources if s['id']==ref.get('source_id')),None)
    quote=ref.get('quote')
    if not source: raise ValueError('引用的source_id不存在')
    if not isinstance(quote,str): raise ValueError('引文必须为字符串')
    if len(quote.strip())<8 or len(quote)>500: raise ValueError('引文长度不在8–500字符范围')
    body=source['content']
    if quote not in body:raise ValueError('引文不是来源正文中的连续原文')
    return {'source_id':source['id'],'quote':quote,'offset':body.index(quote),
            'source_version_id':'V'+hashlib.sha256(body.encode()).hexdigest()[:16]}

def validate_report(data,sources):
    if not isinstance(data,dict): raise ValueError('报告格式无效')
    claims=[]
    for c in data.get('claims',[])[:30]:
        if not isinstance(c,dict):raise ValueError('条目不是对象')
        c=dict(c)
        kind_alias={'事实':'FACT','已披露事实':'FACT','观点':'OPINION','媒体观点':'OPINION','推测':'SPECULATION','传闻':'RUMOR'}
        stance_alias={'支持':'supports','报道':'reported','否认':'disputes','反驳':'disputes','更正':'corrects','更新':'update'}
        c['kind']=kind_alias.get(c.get('kind'),c.get('kind'))
        c['stance']=stance_alias.get(c.get('stance'),c.get('stance'))
        ref=validate_ref(c,sources)
        if c.get('kind') not in KINDS or c.get('stance') not in STANCES: raise ValueError('无效证据分类')
        for k in ('statement','subject','action','event_key'):
            if not isinstance(c.get(k),str) or not c[k].strip() or len(c[k])>600: raise ValueError('缺少原子事件字段')
        occurred=c.get('occurred_at')
        if occurred: date.fromisoformat(occurred)
        # Key includes subject/action/date so different atomic events cannot merge on company alone.
        key='|'.join((c['subject'].strip().lower(),c['action'].strip().lower(),occurred or c['event_key']))
        claims.append({**{k:c[k] for k in ('statement','subject','action','kind','stance')},**ref,
                       'occurred_at':occurred,'event_key':key,'id':'C'+hashlib.sha256((key+ref['source_id']+ref['quote']).encode()).hexdigest()[:12]})
    relations=[]
    for edge in data.get('relations',[])[:15]:
        ref=validate_ref(edge,sources)
        if not all(isinstance(edge.get(k),str) and 0<len(edge[k])<=200 for k in ('subject','relation','target')):
            raise ValueError('关系缺少业务依据字段')
        relations.append({**{k:edge[k] for k in ('subject','relation','target')},**ref,'status':'模型提取候选 · 用户待复核'})
    # Never accept model-generated URLs or market numbers into the report.
    return {'claims':claims,'relations':relations}

def validate_report_partial(data, sources):
    """Keep only individually valid evidence; report rejected entries explicitly.

    Strict validation stays available for atomic/manual imports. No fuzzy quote
    matching, source-id substitution or silent correction of model assertions.
    """
    if not isinstance(data, dict):
        raise ValueError('报告必须为对象')
    accepted={'claims':[], 'relations':[]}
    rejected=[]
    for field, limit in (('claims',30),('relations',15)):
        entries=data.get(field,[])
        if not isinstance(entries,list):
            raise ValueError('报告条目必须为列表')
        for index,entry in enumerate(entries[:limit]):
            try:
                valid=validate_report({field:[entry]},sources)
                accepted[field].extend(valid[field])
            except (ValueError,KeyError,TypeError,AttributeError):
                if not isinstance(entry,dict):reason='条目不是对象'
                else:
                    try:validate_ref(entry,sources)
                    except ValueError as error:reason=str(error)
                    except (KeyError,TypeError):reason='来源正文格式无效'
                    else:
                        try:validate_report({field:[entry]},sources)
                        except (ValueError,KeyError,TypeError,AttributeError) as error:reason=str(error)[:180]
                rejected.append({'field':field,'index':index+1,'reason':reason})
        if len(entries)>limit:
            rejected.append({'field':field,'reason':'超过条目上限，剩余条目未处理'})
    accepted['validation_warnings']=rejected
    return accepted


def recompute(claims,sources,as_of):
    from event_model import build_events
    from disclosure import normalized_source
    events=build_events(claims,sources,as_of)
    normalized={s['id']:normalized_source(s) for s in sources}
    for event in events:
        dates=[normalized[x]['disclosed_at'][:10] for x in event['source_ids'] if normalized[x].get('disclosed_at')]
        if dates and (date.fromisoformat(as_of)-date.fromisoformat(max(dates))).days>30:
            # Age is a review prompt, not a universal expiry/falsehood rule.
            event['freshness_flag']='近期时效待复核（最近可核披露已超过30天）'
        else:
            event['freshness_flag']=None
        event['earliest_in_collection']=min(dates) if dates else None
        event['independence_note']='稳定来源身份+原始材料版本；同源分组不是独立证实票数'
    return events
