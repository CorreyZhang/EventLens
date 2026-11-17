"""Document disclosure dates are separate from discovery metadata and occurrence."""
import hashlib
import re
from datetime import date,datetime,timedelta,timezone
from urllib.parse import urlsplit
from providers import canonical

MONTHS={m.lower():i for i,m in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
MONTHS.update({m[:3]:v for m,v in list(MONTHS.items())})

def normalized_source(s):
    s=dict(s)
    if s.get('schema_version')==4:return s
    s['search_published_at']=s.get('search_published_at',s.get('published_at'))
    content=s.get('content','');head=content[:900];path=urlsplit(s['url']).path.lower();host=urlsplit(s['url']).hostname
    navigation=('/news'==path.rstrip('/') or '/governance/' in path or path.rstrip('/')=='/' or ('nvidianews' in host and head.count('###')>1 and not head.lstrip().startswith('# ') and 'announcesceotransiti' not in path))
    s.update(schema_version=4,published_at=None,disclosed_at=None,disclosure_precision='unknown',disclosure_timezone=None,disclosure_quote=None,disclosure_basis='unknown',is_navigation=navigation,body_origin=s.get('body_origin') or s.get('method','旧版检索工具正文'))
    # Only a date line or release dateline in this document, never the earliest
    # event/date-of-report or signature date in a regulatory filing.
    if not navigation:
        match=re.search(r'(?im)^\s*(?:Published\s*:?\s*)?([A-Z][a-z]+)\.?\s+(\d{1,2}),?\s+(20\d{2})\s*$',head)
        if not match:match=re.search(r'(?:Calif\.,?\s*|SANTA CLARA[^\n]{0,30}?)([A-Z][a-z]+)\.?\s+(\d{1,2}),\s*(20\d{2})',head)
        if match and match[1].lower() in MONTHS:
            try:
                d=date(int(match[3]),MONTHS[match[1].lower()],int(match[2])).isoformat()
                s.update(published_at=d,disclosed_at=d,disclosure_precision='date',disclosure_quote=match[0].strip(),disclosure_basis='document_date_line')
            except ValueError:pass
        if not s['disclosed_at']:
            # Publication metadata only: accept publisher|date and date + source
            # labels, never an arbitrary occurrence date embedded in prose.
            m=re.search(r'(?m)^\s*(?:(?:(?:深圳证券交易所|上海证券交易所|北京证券交易所|巨潮资讯网?|[^\n|｜]{1,30}(?:证券报|新闻网|财经|新闻|通讯社))[|｜])|(?:(?:发布时间|发布于|时间|来源)[：:][^\n]{0,60}?))?\s*(20\d{2})[年/.-](\d{1,2})[月/.-](\d{1,2})日?(?:\s+(\d{2}):(\d{2})(?::\d{2})?)?(?:\s*(?:来源[：:][^\n]{1,60}|[|｜][^\n]{1,60}|[\u4e00-\u9fff]{2,12}(?:[，、, ][\u4e00-\u9fff]{2,12}){0,5}))?\s*$',head)
            if m:
                try:
                    # Time without a stated timezone is not an absolute instant.
                    d=date(int(m[1]),int(m[2]),int(m[3])).isoformat()
                    s.update(published_at=d,disclosed_at=d,disclosure_precision='date',disclosure_quote=m[0].strip(),disclosure_basis='document_date_line')
                except ValueError:pass
    stable=canonical(s['url']);s['source_identity']='D'+hashlib.sha256(stable.encode()).hexdigest()[:14]
    s['source_version_id']=s['id'];s['canonical_url']=stable
    s['quality_status']='excluded_navigation' if navigation else 'quote_location_only'
    # A release reproduced in EDGAR is not an independent extra vote.
    if any(x in path for x in ('ceo-transition','announcesceotransiti')):s['underlying_source']='NVDA-CEO-transition-release-'+str(s['disclosed_at'])
    else:s['underlying_source']=s.get('origin_group') or s.get('underlying_source') or s['source_identity']
    return s

def timeline_sort(sources):
    return sorted(sources,key=lambda s:(s.get('disclosed_at') is None,s.get('disclosed_at') or '',s['id']))

def session_mapping(disclosed_at,precision,schedule):
    """Date-only disclosures map strictly after that date (conservative).

    For absolute instants, pre-open/in-session maps to current session;
    at/after close (including half-days) maps to next actual exchange session.
    schedule entries are {date, open, close}, UTC ISO datetimes.
    """
    if not disclosed_at:return {'date':None,'reason':'原文披露日期未知，不按搜索日期放置节点'}
    if precision=='date':
        day=date.fromisoformat(disclosed_at[:10])
        chosen=next((s for s in schedule if s['date']>day.isoformat()),None)
        return {'date':chosen['date'] if chosen else None,'reason':'仅知日期，时区/盘中盘后未知；保守放到该日期后的首个交易会话','conservative':True}
    try:
        instant=datetime.fromisoformat(disclosed_at.replace('Z','+00:00'))
        if not instant.tzinfo:return {'date':None,'reason':'缺少时区，不能确定盘后对齐'}
        chosen=next((s for s in schedule if datetime.fromisoformat(s['close'].replace('Z','+00:00'))>instant),None)
        return {'date':chosen['date'] if chosen else None,'reason':'按带时区的原始披露时刻与交易所收盘边界对齐（休市/盘后顺延）','conservative':False}
    except (ValueError,TypeError):return {'date':None,'reason':'披露时刻格式无效'}

def exchange_schedule(start,end):
    import exchange_calendars as xcals
    cal=xcals.get_calendar('XNYS');rows=cal.schedule.loc[start:end]
    def stamp(v):
        if v.tzinfo is None:v=v.tz_localize('UTC')
        return v.isoformat()
    return [{'date':str(i.date()),'open':stamp(r['open'] if 'open' in r else r['market_open']),'close':stamp(r['close'] if 'close' in r else r['market_close'])} for i,r in rows.iterrows()]
