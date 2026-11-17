"""Constructed unit fixtures, NOT live market acceptance records."""
import json
from datetime import datetime,timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import create_app
from providers import source_record
from disclosure import normalized_source,exchange_schedule,session_mapping,timeline_sort
from event_model import build_events,provenance_count
from evidence import validate_report
from marketdata import validate_bars
from ifind_client import parse_ohlc

TEXT='The board accepted the resignation effective immediately.'
def doc(url='https://nvidianews.nvidia.com/news/ceo-transition',content=None):
    return source_record({'url':url,'title':'NVIDIA CEO Transition','date':'2026-11-10T16:00:00Z','content':content or '# NVIDIA CEO Transition\n\nNovember 12, 2026\n\n'+TEXT})
def claim(s,subject='NVIDIA',action='管理层变动',occurred='2026-11-11'):
    return validate_report({'claims':[{'source_id':s['id'],'quote':TEXT,'statement':'构造测试：董事会接受辞任','subject':subject,'action':action,'event_key':'Nov transition','occurred_at':occurred,'kind':'FACT','stance':'supports'}]},[s])['claims'][0]

def test_disclosure_is_document_date_not_discovery_or_occurrence():
    s=normalized_source(doc());assert s['disclosed_at']=='2026-11-12' and s['search_published_at']=='2026-11-10T16:00:00Z'
    assert s['disclosure_precision']=='date' and s['disclosure_timezone'] is None
    assert s['disclosure_quote'] in s['content']

def test_unknown_disclosure_not_filled_from_search_metadata():
    s=normalized_source(doc(content=TEXT));assert s['disclosed_at'] is None and s['search_published_at']

def test_sec_event_and_signature_are_not_disclosure():
    s=normalized_source(doc('https://www.sec.gov/Archives/test.htm','Date of Report: November 11, 2026\nDate: November 12, 2026\n'+TEXT))
    assert s['disclosed_at'] is None

def test_navigation_cannot_promote_claim_to_official_status():
    s=doc('https://nvidianews.nvidia.com/news?c=1')
    assert not build_events([claim(s)],[s],'2026-11-17')

def test_stable_source_identity_and_content_revisions():
    a=normalized_source(doc());b=normalized_source(doc(content=doc()['content']+'\nUpdate.'))
    assert a['id']!=b['id'] and a['source_identity']==b['source_identity']
    assert provenance_count([a,b])==1

def test_tracking_parameters_do_not_make_new_identity():
    a=normalized_source(doc());b=normalized_source(doc('https://nvidianews.nvidia.com/news/ceo-transition?_bhlid=x&utm_source=z'))
    assert a['source_identity']==b['source_identity']

def test_entities_and_ceo_departure_synonyms_merge_but_investigation_stays_separate():
    a=doc();b=doc('https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-CEO-Transition')
    claims=[claim(a),claim(b,'英伟达董事会','接受辞任'),claim(a,'英伟达','调查启动')]
    events=build_events(claims,[a,b],'2026-11-17')
    assert len(events)==2 and sorted(len(e['claims']) for e in events)==[1,2]
    assert all('正式确认' not in e['state'] for e in events)

def test_two_explicit_occurrence_dates_not_merged():
    s=doc();events=build_events([claim(s,occurred='2026-11-11'),claim(s,occurred='2026-11-01')],[s],'2026-11-17')
    assert len(events)==2

def test_date_only_mapping_conservatively_waits_next_session():
    schedule=exchange_schedule('2026-11-06','2026-11-12')
    assert session_mapping('2026-11-08','date',schedule)['date']=='2026-11-09'
    assert session_mapping('2026-11-09','date',schedule)['date']=='2026-11-10'

@pytest.mark.parametrize('stamp,expected',[('2026-11-09T08:00:00-05:00','2026-11-09'),('2026-11-09T15:59:00-05:00','2026-11-09'),('2026-11-09T16:00:00-05:00','2026-11-10'),('2026-11-08T12:00:00-05:00','2026-11-09')])
def test_precise_preopen_intraday_afterclose_weekend(stamp,expected):
    assert session_mapping(stamp,'second',exchange_schedule('2026-11-06','2026-11-12'))['date']==expected

def test_exchange_holiday_and_halfday_close():
    schedule=exchange_schedule('2026-11-25','2026-12-01')
    assert session_mapping('2026-11-26T10:00:00-05:00','second',schedule)['date']=='2026-11-27'
    assert session_mapping('2026-11-27T13:00:00-05:00','second',schedule)['date']=='2026-11-30'

def test_unknown_timezone_not_guessed_and_no_missing_bar_backfill():
    schedule=exchange_schedule('2026-11-10','2026-11-17')
    assert session_mapping('2026-11-12T16:00:00','minute',schedule)['date'] is None
    s=doc();e=build_events([claim(s)],[s],'2026-11-17',schedule,{'2026-11-16'})[0]
    assert e['market_session_date']=='2026-11-13' and e['marker_date'] is None

def test_same_session_has_multiple_events_and_timeline_unknown_last():
    s=doc();u=doc('https://example.org/unknown',TEXT)
    e=build_events([claim(s),claim(s,action='任命临时CEO'),claim(u,action='其他事件')],[s,u],'2026-11-17',exchange_schedule('2026-11-10','2026-11-17'),{'2026-11-13'})
    assert len([x for x in e if x['marker_date']=='2026-11-13'])==2
    assert timeline_sort([normalized_source(u),normalized_source(s)])[-1]['disclosed_at'] is None

@pytest.mark.parametrize('bars',[[{'date':'2026-11-12','open':10,'high':9,'low':8,'close':11}],[{'date':'2026-11-12','open':float('nan'),'high':12,'low':8,'close':11}]])
def test_invalid_ohlc_never_drawn(bars):
    with pytest.raises(ValueError):validate_bars(bars,'2026-11-01','2026-11-17')

def table_result(code='NVDA.O',currency='USD'):
    data={'answer':f'|证券代码|证券简称|日期|开盘价|最高价|最低价|收盘价|成交量|交易币种|\n|---|---|---|---|---|---|---|---|---|\n|{code}|test|20261112|10|12|9|11|1.2亿|{currency}|','indicators_params':{k:{'复权方式':'不复权'} for k in ('开盘价','最高价','最低价','收盘价')}}
    return {'ok':True,'data':{'result':{'content':[{'type':'text','text':json.dumps({'code':1,'data':data})}]}}}

def test_ifind_parser_uses_actual_columns_and_volume_units():
    r=parse_ohlc(table_result(),'NVDA');assert r['bars'][0]['volume']==120000000 and r['bars'][0]['close']==11
@pytest.mark.parametrize('code,currency',[('ETF.TV','CAD'),('3347.T','JPY'),('NVDA.O','CNY')])
def test_ifind_success_but_wrong_identity_is_rejected(code,currency):
    with pytest.raises(ValueError):parse_ohlc(table_result(code,currency),'NVDA')

def test_selected_event_scope_and_unrelated_citation_rejected(tmp_path,monkeypatch):
    import providers,marketdata
    client=TestClient(create_app(str(tmp_path/'qa.sqlite3')));store=client.app.state.store
    a=doc();b=doc('https://example.org/other')
    r={'id':'a'*32,'question':'original','as_of':'2026-11-17','status':'complete','mode':'live','sources':[a,b],'claims':[claim(a),claim(b,action='回归讨论')],'events':[],'market':[],'versions':[],'messages':[],'steps':[]}
    store.save(r);event=next(e for e in build_events(r['claims'],r['sources'],r['as_of']) if e['event_type']=='ceo_departure')
    captured=[]
    def model(messages):
        captured.append(json.loads(messages[-1]['content']));return {'answers':[{'text':'构造测试答案','refs':[{'source_id':a['id'],'quote':TEXT}]}],'unknowns':[]}
    monkeypatch.setattr(providers,'model',model);monkeypatch.setattr(marketdata,'daily',lambda *a,**k:{'status':'unavailable','reason':'TEST provider unavailable'})
    payload={'question':'这个事件的依据？','event_id':event['id'],'source_ids':event['source_ids'],'market_window':{'symbol':'NVDA','start':'2026-11-01','end':'2026-11-17','provider':'ifind'}}
    response=client.post('/api/research/'+'a'*32+'/ask',json=payload)
    assert response.status_code==200 and captured[0]['event_id']==event['id']
    assert [s['id'] for s in captured[0]['sources']]==[a['id']]
    payload['source_ids']=[b['id']]
    assert client.post('/api/research/'+'a'*32+'/ask',json=payload).status_code==422

def test_harness_selection_validates_scope(tmp_path):
    app=create_app(tmp_path/'harness.db');client=TestClient(app)
    bound=client.post('/api/workspace/session-event',json={
        'session_id':'harness-scope','kind':'user_message','seq':1,'text':'英伟达公告'}).json()
    r=app.state.store.get(bound['active']['research_id'])
    s=doc();c=claim(s);r['sources']=[s];r['claims']=[c];app.state.store.save(r)
    event=build_events([c],[s],r['as_of'])[0]
    body={'research_id':r['id'],'event_id':event['id'],'source_ids':[s['id']],
          'market_window':{'symbol':'NVDA','provider':'ifind','start':'2026-11-01','end':'2026-11-16'}}
    assert client.get('/api/harness/selection').json()['status']=='no_selection'
    assert client.post('/api/harness/selection',json={**body,'source_ids':['wrong']}).status_code==422
    assert client.post('/api/harness/selection',json=body).status_code==200
    result=client.get('/api/harness/selection').json()
    assert result['event']['id']==event['id'] and result['sources'][0]['id']==s['id']
    assert 'judgment' not in result
    assert client.post('/harness-api/arbitrary-url',json={}).status_code==404

def test_harness_messages_carry_server_selection_and_hide_key(tmp_path,monkeypatch):
    import harness_web,httpx
    sent=[]
    class Upstream:
        async def aclose(self):pass
        def build_request(self,method,url,**kwargs):return httpx.Request(method,url,**kwargs)
        async def send(self,request,stream=False):
            sent.append(request)
            return httpx.Response(200,content=b'{"content":[]}',headers={'content-type':'application/json'})
    monkeypatch.setenv('DEEPSEEK_API_KEY','unit-test-only-secret')
    monkeypatch.setattr(harness_web.httpx,'AsyncClient',lambda **kwargs:Upstream())
    client=TestClient(create_app(tmp_path/'proxy.db'))
    result=client.post('/harness-api/anthropic/v1/messages',json={'model':'deepseek-flash','system':'Harness system','messages':[],'eventlens_context':{'session_id':'local-test','user_seq':1}})
    assert result.status_code==200
    body=json.loads(sent[0].content)
    assert 'eventlens_context' not in body  # local routing metadata never goes upstream
    assert 'EVENTLENS_CURRENT_SELECTION' in body['system'][-1]['text']
    assert 'no_selection' in body['system'][-1]['text']
    assert 'unit-test-only-secret' not in result.text
    assert 'unit-test-only-secret' not in sent[0].content.decode()
    assert str(sent[0].url)=='https://api.deepseek.com/anthropic/v1/messages'

@pytest.mark.parametrize('line',['深圳证券交易所|2026-10-23 00:00:00','2026-10-23 20:55:04来源：央广网','来源：人民财讯作者：李在山2026-10-23 18:38'])
def test_chinese_publication_metadata_not_search_date(line):
    s=normalized_source(doc(content='# 报告\n\n'+line+'\n\n'+TEXT))
    assert s['disclosed_at']=='2026-10-23'
    assert line in s['disclosure_quote']
    assert s['disclosure_precision']=='date' and s['disclosure_timezone'] is None

def test_report_metrics_merge_by_explicit_quarter_and_keep_date_conflict():
    a=doc(content='# 2026 年第三季度报告\n2026-10-23\n'+TEXT)
    b=doc('https://example.org/report',content='# 2026年第三季度报告\n2026-10-22\n'+TEXT)
    rows=[claim(a,'同花顺','三季报披露','2026-10-23'),claim(a,'同花顺','净利润增长',None),claim(b,'同花顺','三季报披露','2026-10-22')]
    events=build_events(rows,[a,b],'2026-11-17')
    assert len(events)==1 and len(events[0]['claims'])==3
    assert events[0]['date_conflicts']==['2026-10-22','2026-10-23']
    assert events[0]['has_conflict']

def test_distinct_quarterly_reports_do_not_merge():
    a=doc(content='# 2026年第三季度报告\n2026-10-23\n'+TEXT)
    b=doc('https://example.org/q2',content='# 2026年第二季度报告\n2026-10-23\n'+TEXT)
    assert len(build_events([claim(a,'同花顺','净利润增长',None),claim(b,'同花顺','净利润增长',None)],[a,b],'2026-11-17'))==2

def test_report_period_pipe_is_not_publication_metadata():
    s=normalized_source(doc(content='# 报告\n报告期|2026-09-30\n'+TEXT))
    assert s['disclosed_at'] is None

def test_harness_appends_to_live_research_and_revision_without_replacing(tmp_path):
    app=create_app(tmp_path/'append.db');client=TestClient(app)
    rid=client.post('/api/harness/research',json={'question':'构造跨引擎追加测试'}).json()['id']
    a=doc();b=doc('https://example.org/new-report')
    def payload(s):return {'sources':[{'url':s['url'],'title':s['title'],'content':s['content']}],'report':{'claims':[claim(s)]}}
    assert client.post(f'/api/research/{rid}/evidence',json=payload(a)).status_code==200
    r=app.state.store.get(rid);r['mode']='live';r['sources'][0]['kind']='official';app.state.store.save(r)
    client.put(f'/api/research/{rid}/judgment',json={'text':'构造测试：用户手写判断'})
    assert client.post(f'/api/research/{rid}/evidence',json=payload(b)).status_code==200
    # Re-submitting an old source cannot downgrade or erase previous evidence.
    assert client.post(f'/api/research/{rid}/evidence',json=payload(a)).status_code==200
    state=app.state.store.get(rid)
    assert len(state['claims'])==2 and len(state['sources'])==2
    assert next(s for s in state['sources'] if s['id']==a['id'])['kind']=='official'
    assert state['judgment']['text']=='构造测试：用户手写判断' and state['judgment']['needs_review']
    assert client.get(f'/api/research/{rid}/revision').json()['version']==3

def test_empty_plugin_submission_cannot_create_research_version(tmp_path):
    app=create_app(tmp_path/'empty.db');client=TestClient(app)
    rid=client.post('/api/harness/research',json={'question':'构造空材料测试'}).json()['id']
    assert client.post(f'/api/research/{rid}/evidence',json={'sources':[],'report':{}}).status_code==422
    assert client.get(f'/api/research/{rid}/revision').json()['version']==0
