"""iFinD official Skill transport + deterministic OHLC table parser.

No LLM transforms price numbers. Wrong ticker/currency is a hard error.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from finance_runtime import call as runtime_call

def unwrap(result):
    if not result.get('ok'):raise ValueError('iFinD传输未成功')
    payload=result.get('data',{}).get('result',{})
    if payload.get('isError'):raise ValueError('iFinD工具返回错误')
    texts=[c.get('text','') for c in payload.get('content',[]) if c.get('type')=='text']
    for text in texts:
        try:
            envelope=json.loads(text)
            if envelope.get('code')!=1:raise ValueError('iFinD业务未成功')
            if isinstance(envelope.get('data'),dict):return envelope['data']
        except json.JSONDecodeError:continue
    raise ValueError('iFinD未返回结构化业务信封')

def quantity(text):
    text=text.strip().replace(',','')
    if text.endswith('亿'):return float(text[:-1])*100000000
    if text.endswith('万'):return float(text[:-1])*10000
    return float(text)

def parse_ohlc(result,symbol):
    data=unwrap(result);answer=data.get('answer','')
    lines=[line for line in answer.splitlines() if line.strip().startswith('|')]
    if len(lines)<3:raise ValueError('iFinD没有逐日OHLC表格')
    header=[cell.strip() for cell in lines[0].strip().strip('|').split('|')]
    def column(name):
        matches=[i for i,h in enumerate(header) if h.startswith(name)]
        if len(matches)!=1:raise ValueError('iFinD字段缺失或歧义：'+name)
        return matches[0]
    cols={k:column(v) for k,v in {'code':'证券代码','date':'日期','currency':'交易币种','open':'开盘价','high':'最高价','low':'最低价','close':'收盘价','volume':'成交量'}.items()}
    allowed={symbol+'.O',symbol+'.OQ',symbol+'.US',symbol} if symbol!='TSM' else {'TSM.N','TSM.US','TSM'}
    params=data.get('indicators_params',{})
    if not all(params.get(k,{}).get('复权方式')=='不复权' for k in ('开盘价','最高价','最低价')):raise ValueError('iFinD未确认OHLC不复权口径')
    close_params=[v for k,v in params.items() if k.startswith('收盘价')]
    if not close_params or any(v.get('复权方式')!='不复权' for v in close_params):raise ValueError('iFinD收盘复权口径未知')
    bars=[];missing=[]
    for line in lines[2:]:
        cells=[cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(cells)!=len(header):continue
        code=cells[cols['code']]
        if code not in allowed:raise ValueError('iFinD返回了非请求证券，拒绝使用')
        if cells[cols['currency']]!='USD':raise ValueError('iFinD返回非USD币种，拒绝使用')
        day=datetime.strptime(cells[cols['date']],'%Y%m%d').date().isoformat()
        values=[cells[cols[k]] for k in ('open','high','low','close')]
        if any(not v or v in ('--','None','null') for v in values):missing.append(day);continue
        bars.append({'date':day,**{k:float(cells[cols[k]].replace(',','')) for k in ('open','high','low','close')},'volume':quantity(cells[cols['volume']]) if cells[cols['volume']] else None})
    return {'bars':bars,'missing_dates':missing,'provider_code':code if lines[2:] else None,'indicators':params,'volume_precision':'上游万/亿单位文本按其显示精度转换，非补造精确成交量'}

def historical(symbol,start,end):
    ric=symbol+'.O' if symbol!='TSM' else 'TSM.N'
    label='美国纳斯达克证券代码' if symbol!='TSM' else '美国纽约证券交易所台积电ADR代码'
    query=f'仅限{label} {ric}，{start.replace("-","")}-{end.replace("-","")} 逐日不复权开盘价、最高价、最低价、收盘价、成交量，交易币种USD。不要模糊匹配其他证券。'
    result=runtime_call({'op':'ifind_call','server':'global_stock','tool':'global_stock_quotes','params':{'query':query}})
    return parse_ohlc(result,symbol)


def index_history(start,end):
    from disclosure import exchange_schedule
    from datetime import timezone
    result=runtime_call({'op':'ifind_call','server':'index','tool':'index_data','params':{'query':f'美国纳斯达克综合指数（IXIC.GI），{start.replace("-","")}-{end.replace("-","")}，每个交易日原始收盘点位，返回代码、名称、日期、收盘点数；不查询ETF。'}})
    data=unwrap(result);lines=[line for line in data.get('answer','').splitlines() if line.startswith('|')]
    if len(lines)<3:raise ValueError('iFinD未返回美股基准序列')
    headers=lines[0].strip('|').split('|')
    def col(prefix):return next(i for i,h in enumerate(headers) if h.startswith(prefix))
    ci,di,vi=col('证券代码'),col('日期'),col('收盘价')
    closed={s['date'] for s in exchange_schedule(start,end) if datetime.fromisoformat(s['close'])<=datetime.now(timezone.utc)}
    points={};excluded=0
    for line in lines[2:]:
        cells=[s.strip() for s in line.strip('|').split('|')]
        if len(cells)!=len(headers) or cells[ci]!='IXIC.GI':continue
        day=datetime.strptime(cells[di],'%Y%m%d').date().isoformat()
        if day not in closed:excluded+=1;continue
        points[day]={'date':day,'close':float(cells[vi].replace(',',''))}
    if not points:raise ValueError('纳指代码或已完成交易日未匹配')
    return {'symbol':'IXIC','label':'NASDAQ Composite · 真实指数','provider':'iFinD MCP','source_url':'https://mcp.51ifind.com/#/documents/mcp/index','tool':'index_data','timezone':'America/New_York','currency':'指数点（非货币）','basis':'指数原始收盘点位，按XNYS已完成交易会话过滤上游休市填充值','instrument_type':'index','adjustment':'none','status':'available','fetched_at':datetime.now(timezone.utc).isoformat(),'points':[points[d] for d in sorted(points)],'excluded_non_session_or_open_dates':excluded}


def news_sources(question,start,end):
    """Actual entitled news snippets; their index date is NOT source disclosure."""
    from providers import source_record
    results=[];diagnostics=[]
    for tool in ('search_news','search_notice'):
        try:
            raw=runtime_call({'op':'ifind_call','server':'news','tool':tool,'params':{'query':question[:200],'time_start':start,'time_end':end,'size':3}})
            payload=raw.get('data',{}).get('result',{})
            if not raw.get('ok') or payload.get('isError'):raise ValueError('工具失败')
            found=[]
            for block in payload.get('content',[]):
                if block.get('type')!='text':continue
                envelope=json.loads(block.get('text','{}'))
                if envelope.get('code')!=1:raise ValueError('业务失败')
                data=envelope.get('data')
                if isinstance(data,dict) and isinstance(data.get('data'),str):
                    parsed=json.loads(data['data'])
                    if isinstance(parsed,list):found.extend(parsed)
            count=0
            for item in found:
                if not item.get('URL') or not item.get('资讯内容'):continue
                s=source_record({'url':item['URL'],'title':item.get('资讯标题'),'date':item.get('日期'),'content':item['资讯内容']},'iFinD '+tool+' · 授权片段（非全文）')
                s['retrieval_status']='provider_excerpt';s['body_origin']='iFinD授权检索片段';s['provider_tool']=tool
                results.append(s);count+=1
            diagnostics.append({'tool':tool,'status':'success' if count else 'empty','count':count})
        except (ValueError,RuntimeError,OSError,KeyError,TypeError) as error:diagnostics.append({'tool':tool,'status':'failed','count':0,'reason':'上游业务、授权或传输失败','error_type':type(error).__name__})
    return results,diagnostics
