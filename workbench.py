"""v0.3 routes installed into the existing FastAPI application and SQLite store."""
from datetime import date,timedelta
from fastapi import HTTPException
from disclosure import normalized_source,timeline_sort,exchange_schedule
from event_model import build_events,safe_source
import marketdata

def view(r,symbol='NONE',start=None,end=None,provider='ifind'):
    end=end or r.get('as_of') or date.today().isoformat()
    start=start or (date.fromisoformat(end)-timedelta(days=45)).isoformat()
    # "NONE" means no verified focus symbol. Return evidence/timeline without
    # fetching an unrelated, visually misleading default NVDA chart.
    no_market = symbol == 'NONE'
    primary = ({
        'symbol':'', 'label':'尚未确定行情标的', 'provider':'', 'bars':[],
        'instrument_type':'unknown','currency':'', 'status':'unavailable',
        'reason':'当前问题未能明确匹配支持的证券；不会展示其他股票的行情',
        'fetched_at':None,'basis':'未检索行情','session_basis':'未确定标的'
    } if no_market else marketdata.daily(symbol,start,end,provider))
    calendar_warning = None
    # Never place an A-share event on a US exchange calendar. When the
    # authorized calendar is unavailable, keep the sourced event timeline;
    # only the price-session marker must be absent.
    schedule = [] if no_market or provider == 'fuyao' else exchange_schedule(
        (date.fromisoformat(start)-timedelta(days=10)).isoformat(),
        (date.fromisoformat(end)+timedelta(days=15)).isoformat()
    )
    if provider == 'fuyao' and not no_market:
        try:
            from finance_runtime import call as finance_call
            from datetime import datetime
            from zoneinfo import ZoneInfo
            days = finance_call({
                'op': 'fuyao', 'path': '/api/a-share/calendar/trading-days',
                'params': {
                    'start_date': start.replace('-', ''),
                    'end_date': (date.fromisoformat(end)+timedelta(days=15)).strftime('%Y%m%d'),
                },
            })
            if not isinstance(days, dict) or days.get('code') != 0:
                raise ValueError('A-share trading calendar unavailable')
            for item in days['data']['item']:
                d = datetime.strptime(item['date'], '%Y%m%d').date()
                schedule.append({
                    'date': d.isoformat(),
                    'open': datetime.combine(
                        d, datetime.strptime('09:30', '%H:%M').time(),
                        tzinfo=ZoneInfo('Asia/Shanghai')).isoformat(),
                    'close': datetime.combine(
                        d, datetime.strptime('15:00', '%H:%M').time(),
                        tzinfo=ZoneInfo('Asia/Shanghai')).isoformat(),
                })
            if not schedule:
                raise ValueError('Empty trading calendar')
        except (RuntimeError, OSError, ValueError, KeyError, TypeError):
            schedule = []
            calendar_warning = (
                '扶摇交易日历不可用；事件证据仍按可核的发生/披露日展示，'
                '不生成未经核实的交易日标记'
            )
    sources=[normalized_source(s) for s in r['sources']]
    events=build_events(r['claims'],sources,r['as_of'],schedule,{b['date'] for b in primary['bars']})
    previous_events={}
    if len(r.get('versions',[]))>1:
        version=r['versions'][-2]
        old_sources=[s for s in sources if s['id'] in version.get('source_ids',[])]
        previous_events={e['id']:e for e in build_events(version.get('claims',[]),old_sources,r['as_of'])}
    for event in events:
        old=previous_events.get(event['id'])
        before=set(old['source_ids']) if old else set()
        event['changes']={'new_event':old is None,'added_source_ids':sorted(set(event['source_ids'])-before),'removed_source_ids':sorted(before-set(event['source_ids'])),'previous_state':old['state'] if old else None}
    buckets={}
    for event in events:
        if event['marker_date']:buckets.setdefault(event['marker_date'],[]).append(event['id'])
    series=[primary]
    if no_market:
        series = [primary]
    elif provider in ('ifind','alphavantage'):
        # Benchmarks are ETF proxies, never mislabeled as actual indices.
        series += [marketdata.daily(s,start,end,provider) for s in ('QQQ','SMH') if s!=symbol]
        if provider=='ifind':
            from ifind_client import index_history
            import time
            cache_key=('IXIC',start,end,provider)
            if cache_key in marketdata.CACHE and time.monotonic()-marketdata.CACHE[cache_key][0]<300:
                series.append(marketdata.CACHE[cache_key][1])
            else:
                try:
                    benchmark=index_history(start,end);marketdata.CACHE[cache_key]=(time.monotonic(),benchmark);series.append(benchmark)
                except (RuntimeError,ValueError,OSError,StopIteration):series.append({'symbol':'IXIC','status':'unavailable','reason':'iFinD基准数据或交易日校验失败','bars':[],'instrument_type':'index'})
    elif provider=='fuyao' and symbol!='000300.SH':series.append(marketdata.daily('000300.SH',start,end,provider))
    previous=r.get('versions',[])
    return {'research_id':r['id'],'question':r['question'],'status':r['status'],'ai_status':r.get('ai_status'),
            'market':primary,'markets':series,'comparison':marketdata.comparison(series),
            'events':events,'markers':[{'id':'DAY:'+d,'time':d,'event_ids':ids,'count':len(ids)} for d,ids in sorted(buckets.items())],
            'sources':[safe_source(s) for s in timeline_sort(sources)],
            'excluded_source_ids':[s['id'] for s in sources if s['is_navigation']],
            'unknown_time_event_ids':[e['id'] for e in events if not e['disclosed_at']],
            'related_business':business_relations(r,sources),
            'versions':[{'number':v.get('number'),'at':v.get('at'),'reason':v.get('reason')} for v in previous],
            'updated_at':previous[-1].get('at') if previous else None,
            'warnings':['引文定位通过不等于概括语义已经核实','仅日期的新闻仅在授权交易日历可用时保守对齐下一交易会话；搜索收录时间不用于节点']+([calendar_warning] if calendar_warning else [])}

def install(app,store):
    @app.get('/api/research/{id}/revision')
    def revision(id:str):
        r=store.get(id)
        return {'id':r['id'],'version':len(r.get('versions',[])),'status':r['status']}
    @app.get('/api/research/{id}/workbench')
    def workbench(id:str,symbol:str='NONE',start:str=None,end:str=None,provider:str='ifind'):
        try:return view(store.get(id),symbol,start,end,provider)
        except (ValueError,KeyError) as e:raise HTTPException(422,'标的、日期、提供方或交易日历范围无效') from None
    @app.get('/api/workspace/research/{id}/view')
    def bound_research_view(id:str,start:str=None,end:str=None):
        """The embedded left pane is bound to the active native chat.

        Prevents a stale iframe/ticker from asking the server for all events
        from another Session or from a former subject within this Session.
        This is an isolation guard, not a public multi-user auth mechanism.
        """
        from research_focus import event_in_focus
        import public_access
        if public_access.enabled():
            # The public single-user-per-cookie twin uses the same original
            # evidence renderer. Ownership is enforced at the guest middleware,
            # and no unrelated default ticker may be substituted.
            try:
                return view(store.get(id), 'NONE', start, end, 'ifind')
            except (ValueError, KeyError):
                raise HTTPException(422, '研究日期或交易窗口无效') from None
        bridge=getattr(app.state,'workspace_bridge',None)
        active=bridge.state()['active'] if bridge else None
        if not active or active['research_id']!=id:
            raise HTTPException(409,'当前研究与右侧 Harness 对话不一致')
        focus=active.get('focus')
        symbol=(focus or {}).get('market_symbol') or 'NONE'
        if symbol not in marketdata.SYMBOLS:symbol='NONE'
        provider='fuyao' if symbol.endswith(('.SZ','.SH')) else 'ifind'
        try:result=view(store.get(id),symbol,start,end,provider)
        except (ValueError,KeyError):
            raise HTTPException(422,'研究窗口的日期或提供方无效') from None
        result['events']=[e for e in result['events'] if event_in_focus(e,focus)]
        event_ids={e['id'] for e in result['events']}
        source_ids={sid for e in result['events'] for sid in e['source_ids']}
        result['markers']=[
            {**m,'event_ids':[eid for eid in m['event_ids'] if eid in event_ids],
             'count':sum(eid in event_ids for eid in m['event_ids'])}
            for m in result['markers'] if any(eid in event_ids for eid in m['event_ids'])
        ]
        result['sources']=[source for source in result['sources']
                           if source['id'] in source_ids]
        result['related_business']=[relation for relation in result['related_business']
                                    if relation.get('source_id') in source_ids]
        result['focus']=focus
        return result

    @app.get('/api/market/ohlc')
    def ohlc(symbol:str='NONE',start:str='2026-10-01',end:str='2026-11-17',provider:str='ifind'):
        if symbol=='NONE':return {'symbol':'','status':'unavailable','bars':[],'reason':'没有已验证行情标的；研究证据可继续查看'}
        try:return marketdata.daily(symbol,start,end,provider)
        except ValueError as e:raise HTTPException(422,str(e)) from None


def business_relations(r,sources):
    import re
    from evidence import validate_ref
    result=[]
    for edge in r.get('relations',[]):
        if not re.search(r'代工|供应|客户|合作|制造|foundry|supplier|customer|partner',edge.get('relation',''),re.I):continue
        try:ref=validate_ref(edge,sources)
        except (ValueError,TypeError,KeyError):continue
        source=next(s for s in sources if s['id']==edge['source_id'])
        result.append({**edge,**ref,'source_disclosed_at':source.get('disclosed_at'),'temporal_status':'有原文日期' if source.get('disclosed_at') else '业务关系材料时点未核定，不自动宣称为当前关系','status':'有业务关系引文的候选；尚未人工核准，不推断行情因果'})
    return result
