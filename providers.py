"""Server-only providers; never return upstream error bodies or credentials."""
import os
import re
import hashlib
import math
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from html.parser import HTMLParser
import httpx

class ProviderError(RuntimeError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def canonical(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('来源须为不含凭据的 HTTPS URL')
    return urlunsplit(('https', p.hostname.lower(), p.path.rstrip('/') or '/', urlencode(sorted((k,v) for k,v in parse_qsl(p.query) if not k.startswith('utm_') and k not in ('_bhlid','ftag','fbclid','gclid'))), ''))

def ds_request(path, payload):
    key = os.getenv('DEEPSEEK_API_KEY', '').strip()
    if not key:
        raise ProviderError('未配置 DEEPSEEK_API_KEY；未执行 DeepSeek 请求')
    try:
        r = httpx.post('https://api.deepseek.com' + path, json=payload,
                       headers={'Authorization': 'Bearer ' + key}, timeout=60)
        if r.status_code != 200:
            raise ProviderError('DeepSeek HTTP %s（检查权限、余额或限流）' % r.status_code)
        return r.json()
    except (httpx.HTTPError, ValueError):
        raise ProviderError('DeepSeek 网络超时或响应格式无效') from None

def model(messages):
    import json
    data = ds_request('/chat/completions', {
        'model': os.getenv('DEEPSEEK_MODEL', 'deepseek-flash'),
        'messages': messages, 'response_format': {'type':'json_object'},
        'thinking': {'type':'disabled'}, 'temperature':0, 'max_tokens':6000})
    try:
        return json.loads(data['choices'][0]['message']['content'])
    except (KeyError, IndexError, TypeError, ValueError):
        raise ProviderError('DeepSeek 未返回有效 JSON；未使用预置回答替代') from None

def search(query):
    data = ds_request('/v1/tools/search', {'query':query[:128], 'count':5, 'need_content':True})
    if not isinstance(data.get('results'), list):
        raise ProviderError('DeepSeek Search 响应缺少 results')
    return data['results']

def source_record(item, method='DeepSeek Search'):
    url = canonical(item['url'])
    # Only actual page content is extractable evidence; snippets are discovery aids.
    content = str(item.get('content') or '')[:18000]
    host = urlsplit(url).hostname
    kind = 'regulatory' if host == 'www.sec.gov' else 'official' if host in ('nvidianews.nvidia.com','investor.nvidia.com') else 'unverified'
    return {'id':'S'+hashlib.sha256((url+'\n'+content).encode()).hexdigest()[:14],
            'url':url, 'title':str(item.get('title') or host)[:300], 'publisher':host,
            'published_at':item.get('date') or item.get('published_at'), 'occurred_at':None, 'fetched_at':now(), 'updated_at':now(),
            'content':content, 'discovery_snippet':str(item.get('snippet') or '')[:250],
            'retrieval_status':'page_content' if content else 'metadata_only',
            'kind':kind, 'method':method, 'fingerprint':hashlib.sha256(content.encode()).hexdigest() if content else None}

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())

# A disclosed, limited catalog for a no-key source preview. Never called a web search.
CATALOG = [
 ('https://nvidianews.nvidia.com/news/statement-from-nvidia-board-of-directors','董事会声明','2026-11-08'),
 ('https://nvidianews.nvidia.com/news/statement-from-the-independent-members-of-the-nvidia-board','独立董事声明','2026-11-10'),
 ('https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-CEO-Transition/','管理层变动公告','2026-11-12')]

def preview_sources(question):
    if not any(w in question.lower() for w in ('英伟达','黄仁勋','nvda','nvidia')):
        raise ProviderError('无密钥来源预览仅覆盖 NVIDIA 公告目录；其他问题需要启用 DeepSeek 检索')
    result=[]; errors=[]
    for url,title,day in CATALOG:
        try:
            r=httpx.get(url, timeout=12, follow_redirects=False)
            if r.status_code != 200: raise ProviderError('HTTP '+str(r.status_code))
            p=VisibleText(); p.feed(r.text[:500000])
            text='\n'.join(p.parts)
            # Strip navigation/footer when the known article title can be located.
            markers=('Statement From NVIDIA Board','Statement From the Independent','NVIDIA Announces CEO Transition')
            starts=[text.find(m) for m in markers if text.find(m)>=0]
            if starts: text=text[min(starts):].split('More News')[0].split('About NVIDIA')[0]
            result.append(source_record({'url':url,'title':title,'date':day,'content':text[:18000]}, '官方目录实时重取（非搜索、非模型输出）'))
        except (httpx.HTTPError, ProviderError, ValueError):
            errors.append({'url':url,'status':'获取失败；未填充历史缓存'})
    return result,errors

def market(symbols, start, end):
    key=os.getenv('ALPHAVANTAGE_API_KEY','').strip()
    result=[]
    for symbol in symbols[:4]:
        row={'symbol':symbol,'provider':'Alpha Vantage','source_url':'https://www.alphavantage.co/documentation/#daily',
             'timezone':None,'currency':None,'basis':'未复权日收盘价','points':[], 'status':'unavailable'}
        if not key:
            row['reason']='未配置已授权行情凭据；未生成价格'; result.append(row); continue
        if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',symbol):
            row['reason']='证券代码未通过校验'; result.append(row); continue
        try:
            r=httpx.get('https://www.alphavantage.co/query', params={'function':'TIME_SERIES_DAILY','symbol':symbol,'apikey':key},timeout=15)
            data=r.json() if r.status_code==200 else {}
            series=data.get('Time Series (Daily)',{})
            row['timezone']=data.get('Meta Data',{}).get('5. Time Zone')
            row['points']=[{'date':d,'close':float(v['4. close'])} for d,v in sorted(series.items()) if start<=d<=end]
            if any(not math.isfinite(p['close']) or p['close']<=0 for p in row['points']): raise ValueError('invalid price')
            row['status']='available' if len(row['points'])>=2 else 'unavailable'
            row['reason']='可用；币种需按标的另行确认' if row['status']=='available' else '权限、限流或窗口内交易日不足；未回填'
            if row['points'] and row['points'][0]['close']>0:
                base=row['points'][0]['close']
                for point in row['points']: point['change_pct']=round((point['close']/base-1)*100,4)
        except (httpx.HTTPError,ValueError,KeyError,TypeError):
            row['reason']='行情请求或格式失败'; row['status']='unavailable'; row['points']=[]
        result.append(row)
    available=[r for r in result if r['status']=='available']
    if len(available)>1:
        common=set.intersection(*[{p['date'] for p in r['points']} for r in available])
        for row in available:
            row['points']=[p for p in row['points'] if p['date'] in common]
            if len(row['points'])<2:
                row['status']='unavailable'; row['reason']='共同交易日不足，无法比较'; row['points']=[]
            else:
                base=row['points'][0]['close']
                for point in row['points']:point['change_pct']=round((point['close']/base-1)*100,4)
    return result
