"""Conservative topic focus for locally bound Harness research.

Focus is a research subject, NOT a verified tradable security identifier.
Do not let a missing market ticker expose events from an earlier company.
"""
import re
import hashlib

ALIAS_HINTS = (
    ("比亚迪", ("比亚迪", "BYD"), "company", None),
    ("特斯拉", ("特斯拉", "Tesla", "TSLA"), "company", None),
    ("苹果", ("苹果公司", "苹果", "Apple", "AAPL"), "company", "AAPL"),
    ("英伟达", ("英伟达", "NVIDIA", "NVDA", "黄仁勋"), "company", "NVDA"),
    ("同花顺", ("同花顺", "300033"), "company", "300033.SZ"),
    ("宁德时代", ("宁德时代新能源科技股份有限公司", "宁德时代", "CATL", "300750.SZ", "300750"), "company", "300750.SZ"),
    ("台积电", ("台积电", "TSMC", "TSM", "Taiwan Semiconductor"), "company", "TSM"),
    ("微软", ("微软", "Microsoft", "MSFT"), "company", None),
    ("美联储", ("美联储", "Federal Reserve", "FOMC"), "policy", None),
)
FOLLOWUP = re.compile(r"^(?:这条|这份|这个|这些|这段|那段|本段|这句话|那句话|这项|这则|这张|刚才|你刚才|引用的|上述|它|那条|继续|为什么|有证据吗|你说的|还有哪些|进一步|具体).*")
GENERIC = (
    re.compile(r"(?:我(?:想)?(?:查|搜|看)|帮我(?:查|搜|看)|查(?:一下)?|搜(?:一下)?|关于|研究|分析|了解|看看|关注)\s*([\u4e00-\u9fff]{2,12})(?=最近|近期|的|有|是|，|,|？|\?|\s|$)"),
    re.compile(r"^(?:最近|近期|今天|昨天|这周)?\s*([\u4e00-\u9fff]{2,12})(?=最近|近期|的|有|是|，|,|？|\?|\s|$)"),
)
BLOCKED = {"有什么", "怎么样", "什么事", "市场", "最近", "新闻", "看看", "股票", "事件", "消息", "分析", "这个", "来源", "证据", "最新"}


def matched(text, alias):
    if alias.isascii():
        return re.search(r"(?<![A-Za-z0-9])" + re.escape(alias) +
                         r"(?![A-Za-z0-9])", text, flags=re.I) is not None
    if alias == "苹果":
        return bool(re.search(r"苹果(?!汁|醋|派|树)", text))
    return alias in text


def _focus_from_text(message, previous=None):
    text = (message or "").strip()
    if not text:
        return previous
    hits = []
    for name, aliases, kind, market in ALIAS_HINTS:
        if any(matched(text, alias) for alias in aliases):
            hits.append((name, aliases, kind, market))
    if len(hits) > 1:
        return {
            "subject": "多对象比较", "aliases": [], "kind": "comparison",
            "market_symbol": None, "subjects": [row[0] for row in hits],
            "status": "needs_separate_evidence"
        }
    if len(hits) == 1:
        name, aliases, kind, market = hits[0]
        return {
            "subject": name, "aliases": list(aliases), "kind": kind,
            "market_symbol": market, "subjects": [name],
            "status": "subject_identified_market_unverified"
        }
    if FOLLOWUP.match(text):
        return previous
    for pattern in GENERIC:
        m = pattern.search(text)
        if m:
            subject = m[1].strip()
            if subject not in BLOCKED and not any(subject.startswith(x) for x in ("什么", "怎么", "还有")):
                return {
                    "subject": subject, "aliases": [subject], "kind": "topic",
                    "market_symbol": None, "subjects": [subject],
                    "status": "extracted_unverified_subject"
                }
    # Fail closed: an unrecognized new topic is not an invitation to show
    # every stored event or to continue showing NVDA.
    return {
        "subject": text[:80], "aliases": [], "kind": "unknown",
        "market_symbol": None, "subjects": [],
        "status": "awaiting_research_intent"
    }


def focus_from_text(message, previous=None):
    focus = _focus_from_text(message, previous)
    if focus is previous or not focus:
        return focus
    text = (message or '').strip()
    if previous:
        focus['previous_focus']={k:v for k,v in previous.items() if k!='previous_focus'}
    title=re.search(r'《([^》]{2,160})》',text)
    if title:focus['literal_title']=title[1]
    focus.update(original_question=text, verified=False,
                 scope_id='R'+hashlib.sha256(text.encode()).hexdigest()[:20])
    return focus


def resolve_focus(current, entities, time_range=None, mode=None):
    """Harness parses arbitrary intent; symbols from the model are candidates only."""
    if not current or not isinstance(entities, list) or not 1 <= len(entities) <= 12:
        raise ValueError('需要当前研究及1至12个结构化主体')
    parsed=[]
    for item in entities:
        if not isinstance(item,dict):raise ValueError('主体必须为对象')
        name=item.get('name')
        kind=item.get('type')
        aliases=item.get('aliases',[])
        if not isinstance(name,str) or not 1<=len(name.strip())<=160:raise ValueError('主体名称无效')
        if kind not in ('company','person','organization','industry','policy','event','topic'):raise ValueError('主体类型无效')
        if not isinstance(aliases,list) or len(aliases)>20 or any(not isinstance(a,str) or not 1<=len(a)<=160 for a in aliases):raise ValueError('别名无效')
        name=name.strip();aliases=list(dict.fromkeys([name]+aliases))
        parsed.append({'id':'N'+hashlib.sha256(name.casefold().encode()).hexdigest()[:16],
                       'name':name,'aliases':aliases,'type':kind,'verified':False,
                       'market_candidate':item.get('market_candidate'), 'market_verified':False})
    if mode not in (None,'single','comparison'):raise ValueError('研究模式无效')
    compare=mode=='comparison' or (mode is None and bool(re.search(r'比较|对比|相比|区别|\bvs\b',current.get('original_question',''),re.I)))
    primary=parsed if compare else parsed[:1]
    names=[e['name'] for e in primary]
    # Only existing locally checked alias hints can enable an adapter. A model
    # guessed ticker is NEVER promoted to a verified security identifier.
    market=None
    if len(primary)==1 and primary[0]['type']=='company':
        hints=[row for row in ALIAS_HINTS if parsed[0]['name'].casefold() in [a.casefold() for a in row[1]]]
        if len(hints)==1:market=hints[0][3]
    previous=current.get('previous_focus') or current
    prior_names=previous.get('aliases',[])
    same_subjects=(len(names)==len(previous.get('subjects',[])) and all(any(a.casefold()==b.casefold() for a in e['aliases'] for b in prior_names) for e in parsed))
    scope=(previous.get('scope_id') or current.get('scope_id')) if same_subjects else current.get('scope_id')
    title=re.search(r'《([^》]{2,160})》',current.get('original_question',''))
    return {**current,'literal_title':current.get('literal_title') or (title[1] if title else None),'scope_id':scope,'subject':'、'.join(names),'subjects':names,'entities':parsed,
            'aliases':list(dict.fromkeys(a for e in parsed for a in e['aliases'])),
            'kind':'comparison' if compare else primary[0]['type'],'related_entities':[] if compare else parsed[1:],
            'market_symbol':market,'status':'model_parsed_unverified','verified':False,
            'time_range':time_range}


def event_in_focus(event, focus):
    if not focus:return False
    scoped=[c for c in event.get('claims',[]) if c.get('research_scope_id')]
    if scoped:
        literal=focus.get('literal_title') or re.search(r'《([^》]{2,160})》',focus.get('original_question',''))
        candidates=[c for c in scoped if c['research_scope_id']==focus.get('scope_id')]
        if literal:
            return any(c.get('literal_subject_located') is True for c in candidates)
        return bool(candidates)
    # Legacy records have no scope identifier. Preserve conservative alias
    # matching; newly submitted evidence is explicitly scoped, including comparisons.
    if focus.get('kind') in ('comparison','unknown'):return False
    names=list(focus.get('aliases') or [])
    subjects=[event.get('subject') or '']+[c.get('subject') or '' for c in event.get('claims') or []]
    return any(matched(value,name) for value in subjects for name in names)
