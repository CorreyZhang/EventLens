"""v0.3 daily OHLC adapters. No generated prices, no implicit CFD substitution."""
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import httpx
from providers import now

SYMBOLS={'NVDA':'NVIDIA 股票','AAPL':'苹果公司股票','QQQ':'NASDAQ-100 ETF代理（非指数）','SMH':'半导体 ETF代理（非指数）','300033.SZ':'同花顺 A股','300750.SZ':'宁德时代 A股','000300.SH':'沪深300 指数','TSM':'台积电ADR · 业务关系候选'}
CACHE={}

def validate_bars(bars,start,end):
    result={}
    for b in bars:
        d=date.fromisoformat(b['date']).isoformat()
        if not start<=d<=end:continue
        values={k:float(b[k]) for k in ('open','high','low','close')}
        if any(not math.isfinite(v) or v<=0 for v in values.values()): raise ValueError('非有限或非正OHLC')
        if values['high']<max(values.values()) or values['low']>min(values.values()):raise ValueError('OHLC区间不合法')
        volume=b.get('volume')
        if volume is not None:
            volume=float(volume)
            if not math.isfinite(volume) or volume<0:raise ValueError('成交量无效')
        if d in result:raise ValueError('交易日重复，拒绝歧义序列')
        result[d]={'date':d,**values,'volume':volume}
    return [result[d] for d in sorted(result)]

def daily(symbol,start,end,provider='alphavantage',force=False):
    if symbol not in SYMBOLS:raise ValueError('仅支持已明确配置的证券代码；不自动用NVDA等其他标的替代')
    begin=date.fromisoformat(start);finish=date.fromisoformat(end)
    if begin>finish or (finish-begin).days>370:raise ValueError('窗口须为顺序排列的一年以内日期')
    if provider not in ('ifind','alphavantage','biquote','fuyao'):raise ValueError('提供方无效')
    key=(symbol,start,end,provider)
    if not force and key in CACHE and time.monotonic()-CACHE[key][0]<300:return CACHE[key][1]
    row={'symbol':symbol,'label':SYMBOLS[symbol],'provider':'Alpha Vantage' if provider=='alphavantage' else 'BiQuote',
         'instrument_type':'ETF' if symbol in ('QQQ','SMH') else ('index' if symbol=='000300.SH' else 'equity'),'exchange':'NYSE' if symbol=='TSM' else 'NASDAQ',
         'timezone':'America/New_York','currency':'USD','start':start,'end':end,'interval':'1d','bars':[],
         'fetched_at':now(),'status':'unavailable','source_url':'https://www.alphavantage.co/documentation/#daily',
         'basis':'未复权日OHLC；日收盘不含盘后','adjustment':'raw','session_basis':'美国股票常规交易会话',
         'license_url':'https://www.alphavantage.co/terms_of_service/','coverage_note':'窗口内无数据不补写；不扩展提供方历史深度'}
    try:
        if provider=='ifind':
            from ifind_client import historical
            row.update(provider='iFinD MCP',source_url='https://mcp.51ifind.com/#/documents/mcp/global-stock',license_url='https://mcp.51ifind.com/',tool='global_stock_quotes',timezone='America/New_York',currency='USD',basis='不复权股票/ETF日OHLC；收盘价（不前推）',adjustment='none')
            try:
                result=historical(symbol,start,end)
                bars=result['bars'];row['missing_dates']=result['missing_dates'];row['volume_precision']=result['volume_precision'];row['provider_code']=result['provider_code']
            except (RuntimeError,ValueError,OSError) as error:
                row['reason']=str(error);return row
        elif provider=='fuyao':
            from fuyao_client import historical,FuyaoError
            row.update(provider='扶摇',instrument_type='index' if symbol=='000300.SH' else 'equity',exchange='SSE' if symbol.endswith('.SH') else 'SZSE',timezone='Asia/Shanghai',currency='指数点（非货币）' if symbol=='000300.SH' else 'CNY',basis='指数原始OHLC' if symbol=='000300.SH' else '不复权日OHLC',source_url='https://fuyao.aicubes.cn/docs/api-reference/prices/',license_url='https://fuyao.aicubes.cn/docs/',adjustment='none',session_basis='沪深交易所交易日')
            try:
                result=historical(symbol,start,end,index=symbol=='000300.SH')
                bars=result['bars'];row['request_id']=result['request_id']
            except FuyaoError as error:
                row['reason']=str(error);return row
            except (RuntimeError, OSError, ValueError):
                row['reason']='扶摇本机代理、网络或数据校验暂不可用；行情保持空状态，不影响新闻事件证据';return row
        elif provider=='alphavantage':
            token=os.getenv('ALPHAVANTAGE_API_KEY','').strip()
            if not token:
                row['reason']='ALPHAVANTAGE_API_KEY 未配置，授权美股OHLC不可用';return row
            response=httpx.get('https://www.alphavantage.co/query',params={'function':'TIME_SERIES_DAILY','symbol':symbol,'outputsize':'compact','apikey':token},timeout=20)
            if response.status_code!=200:
                row['reason']='Alpha Vantage HTTP '+str(response.status_code);return row
            payload=response.json();series=payload.get('Time Series (Daily)')
            if not isinstance(series,dict):
                row['reason']='提供方未返回日OHLC（权限、额度、密钥或接口限制）；未生成替代价格';return row
            row['timezone']=payload.get('Meta Data',{}).get('5. Time Zone','America/New_York')
            bars=[{'date':d,**{k:v[str(i)+'. '+k] for i,k in enumerate(('open','high','low','close','volume'),1)}} for d,v in series.items()]
        else:
            row.update(instrument_type='broker_indicative',exchange=None,timezone='UTC',currency='USD（标的报价货币，接口未单独给出）',basis='真实经纪商指示价 OHLC；不是美股成交OHLC；复权未知',adjustment='unknown',session_basis='提供方UTC日桶；节点对齐NYSE交易日只是观察坐标，不证明与常规交易会话一致',source_url='https://biquote.io/api/'+symbol+'/ohlc',license_url='https://biquote.io/terms.html')
            response=httpx.get(row['source_url'],params={'interval':'1d','limit':1000,'from':start+'T00:00:00Z','to':(finish+timedelta(days=1)).isoformat()+'T00:00:00Z'},timeout=20)
            if response.status_code!=200:
                row['reason']='BiQuote HTTP '+str(response.status_code);return row
            payload=response.json()
            if payload.get('symbol')!=symbol or payload.get('interval')!='1d':raise ValueError('代码或周期不符')
            bars=[{'date':b['openTime'][:10],**{k:b[k] for k in ('open','high','low','close')},'volume':None} for b in payload.get('bars',[]) if not b.get('isOpen',True)]
            row['excluded_open_bars']=sum(bool(b.get('isOpen')) for b in payload.get('bars',[]))
        row['bars']=validate_bars(bars,start,end)
        # Exclude an unfinished current session even if an upstream daily table
        # has already populated O/H/L/C during that trading day.
        from zoneinfo import ZoneInfo
        local=datetime.now(ZoneInfo('Asia/Shanghai' if provider=='fuyao' else 'America/New_York'))
        close_hour=15 if provider=='fuyao' else 16
        if provider!='biquote':
            original_count=len(row['bars'])
            row['bars']=[b for b in row['bars'] if b['date']<local.date().isoformat() or (b['date']==local.date().isoformat() and local.hour>=close_hour)]
            row['excluded_unfinished_sessions']=original_count-len(row['bars'])
        row['status']='available' if row['bars'] else 'unavailable'
        row['reason']='已取得外部真实OHLC' if row['bars'] else '接口未返回窗口内已完成日K；无数据不补写'
        if row['bars']:
            row['actual_start']=row['bars'][0]['date'];row['actual_end']=row['bars'][-1]['date']
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        row['reason']='行情网络、响应格式或OHLC校验失败；未生成替代价格';row['bars']=[]
    CACHE[key]=(time.monotonic(),row)
    return row

def comparison(rows):
    available=[{**r,'bars':r.get('bars') or r.get('points')} for r in rows if (r.get('bars') or r.get('points')) and r['instrument_type']!='broker_indicative']
    if len(available)<2:return {'status':'unavailable','reason':'至少两组同口径授权行情才可比较；不混合经纪商指示价','series':[]}
    common=set.intersection(*[{b['date'] for b in r['bars']} for r in available])
    if len(common)<2:return {'status':'unavailable','reason':'共同交易日不足','series':[]}
    result=[]
    for row in available:
        bars=[b for b in row['bars'] if b['date'] in common];base=bars[0]['close']
        result.append({'symbol':row['symbol'],'label':row['label'],'points':[{'time':b['date'],'value':round((b['close']/base-1)*100,5)} for b in bars]})
    return {'status':'available','series':result,'basis':'共同交易日首个收盘价归零，未复权百分比；非因果解释'}
