import time
import json
import threading
from datetime import date
import pytest
from fastapi.testclient import TestClient
import providers
from app import create_app
from evidence import validate_report, recompute

QUOTE='The board announced an independent investigation.'

def source(url='https://nvidianews.nvidia.com/news/test', text=QUOTE):
    return providers.source_record({'url':url,'content':'November 8, 2026\n'+text,'title':'TEST fixture: board statement','date':'2026-11-08'})
def report(s, **override):
    return {'claims':[dict(source_id=s['id'],quote=QUOTE,statement='测试：董事会宣布调查',subject='NVIDIA',action='调查启动',event_key='2026-11',occurred_at=None,kind='FACT',stance='supports',**override)],'relations':[]}

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    monkeypatch.delenv('ALPHAVANTAGE_API_KEY',raising=False)
    return TestClient(create_app(str(tmp_path/'test.sqlite3')))

def wait(client,id):
    for i in range(400):
        r=client.get('/api/research/'+id).json()
        if r['status'] not in ('queued','running'): return r
        time.sleep(.01)
    raise AssertionError('job did not finish')

def mock_live(monkeypatch):
    s=source()
    def model(messages):
        if '拆为' in messages[0]['content']: return {'queries':['NVIDIA board','NVIDIA official'],'symbols':['NVDA'],'start':'2026-11-01','end':date.today().isoformat()}
        if '整理器' in messages[0]['content']: return report(s)
        return {'answers':[{'text':'测试：来源披露调查。','refs':[{'source_id':s['id'],'quote':QUOTE}]}],'unknowns':['价格因果无法证实']}
    monkeypatch.setattr(providers,'model',model)
    monkeypatch.setattr(providers,'search',lambda q:[{'url':s['url'],'title':s['title'],'content':s['content'],'date':'2026-11-08'}])
    return s

def test_live_pipeline_and_multiturn(client,monkeypatch):
    mock_live(monkeypatch)
    id=client.post('/api/research',json={'question':'测试NVIDIA调查'}).json()['id']
    r=wait(client,id)
    assert r['status']=='complete' and len(r['sources'])==1 and len(r['events'])==1
    assert 'content' not in r['sources'][0]
    assert r['market'][0]['status']=='unavailable'
    assert client.post(f'/api/research/{id}/ask',json={'question':'测试证据是什么'}).status_code==200
    assert len(client.get('/api/research/'+id).json()['messages'])==1
    assert client.post(f'/api/research/{id}/ask',json={'question':'继续测试追问'}).status_code==200
    assert len(client.get('/api/research/'+id).json()['messages'])==2

def test_note_survives_refresh_and_app_restart(client,monkeypatch):
    mock_live(monkeypatch)
    id=client.post('/api/research',json={'question':'测试NVIDIA'}).json()['id'];wait(client,id)
    client.put(f'/api/research/{id}/judgment',json={'text':'我的原始判断'})
    client.post(f'/api/research/{id}/refresh',json={});r=wait(client,id)
    assert r['judgment']=={'text':'我的原始判断','needs_review':True}
    again=TestClient(create_app(client.app.state.store.path))
    assert again.get('/api/research/'+id).json()['judgment']['text']=='我的原始判断'

def test_missing_key_is_failure(client):
    id=client.post('/api/research',json={'question':'任意研究问题'}).json()['id']
    r=wait(client,id); assert r['status']=='failed' and 'DEEPSEEK_API_KEY' in r['steps'][-1]['detail'] and not r['claims']

def test_preview_not_ai(client,monkeypatch):
    monkeypatch.setattr(providers,'preview_sources',lambda q:([source()],[]))
    id=client.post('/api/research',json={'question':'测试NVIDIA','mode':'preview'}).json()['id']; r=wait(client,id)
    assert r['status']=='preview' and not r['claims']
    assert client.post(f'/api/research/{id}/ask',json={'question':'问题'}).status_code==409

def test_unrelated_preview_rejected():
    with pytest.raises(providers.ProviderError): providers.preview_sources('某其他公司')

@pytest.mark.parametrize('field,value',[('quote','invented quote'),('quote',''),('source_id','fake'),('kind','TRUTH'),('occurred_at','yesterday')])
def test_invalid_extraction_rejected(field,value):
    s=source(); raw=report(s);raw['claims'][0][field]=value
    with pytest.raises(ValueError): validate_report(raw,[s])

def test_no_false_atomic_merge():
    s=source(); raw=report(s);raw['claims'].append({**raw['claims'][0],'action':'管理层变动'})
    out=validate_report(raw,[s]);assert len(recompute(out['claims'],[s],'2026-11-17'))==2

@pytest.mark.parametrize('stance,state',[('supports','存在一手事实陈述'),('disputes','存在否认或异议'),('corrects','发现一手更正')])
def test_state_changes(stance,state):
    s=source();raw=report(s);raw['claims'][0]['stance']=stance
    assert state in recompute(validate_report(raw,[s])['claims'],[s],'2026-11-17')[0]['state']

def test_expiry_and_no_future_leak():
    s=source(); c=validate_report(report(s),[s])['claims']
    assert not recompute(c,[s],'2026-11-07')
    event=recompute(c,[s],'2026-12-20')[0]
    # Age prompts a freshness review; it must not overwrite the evidence state.
    assert event['status_code']=='primary_document'
    assert '超过30天' in (event['freshness_flag'] or '')

def test_exact_republication_group():
    a=source();b=source('https://example.org/reprint')
    c=validate_report(report(a),[a])['claims']+validate_report(report(b),[b])['claims']
    assert recompute(c,[a,b],'2026-11-17')[0]['provenance_groups']==1

@pytest.mark.parametrize('url',['http://example.org','https://user:secret@example.org','https://example.org:8000'])
def test_url_rejection(url):
    with pytest.raises(ValueError):providers.canonical(url)

def test_provider_error_does_not_expose_body(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','TEST_ONLY_DO_NOT_USE')
    class Response: status_code=401; text='secret upstream error'
    monkeypatch.setattr(providers.httpx,'post',lambda *a,**k:Response())
    with pytest.raises(providers.ProviderError,match='HTTP 401') as e:providers.search('test')
    assert 'secret' not in str(e.value)

def test_question_changes_queries(client,monkeypatch):
    queries=[]
    def model(messages):
        if '拆为' in messages[0]['content']:return {'queries':[messages[-1]['content']],'symbols':[],'start':'2026-11-01','end':date.today().isoformat()}
        return {'claims':[],'relations':[]}
    monkeypatch.setattr(providers,'model',model)
    def search(q): queries.append(q);return [{'url':'https://example.org/'+q,'content':QUOTE}]
    monkeypatch.setattr(providers,'search',search)
    for q in ['测试甲公司','测试乙公司']:
        id=client.post('/api/research',json={'question':q}).json()['id'];wait(client,id)
    assert queries==['测试甲公司','测试乙公司']

def test_unsupported_followup_ref_rejected(client,monkeypatch):
    mock_live(monkeypatch);id=client.post('/api/research',json={'question':'测试研究'}).json()['id'];wait(client,id)
    monkeypatch.setattr(providers,'model',lambda m:{'answers':[{'text':'无依据回答','refs':[{'source_id':'fake','quote':QUOTE}]}]})
    assert client.post(f'/api/research/{id}/ask',json={'question':'测试追问'}).status_code==502

def test_cancel_and_note_during_job(client,monkeypatch):
    gate=threading.Event();started=threading.Event()
    def preview(q):started.set();gate.wait(3);return [source()],[]
    monkeypatch.setattr(providers,'preview_sources',preview)
    id=client.post('/api/research',json={'question':'测试NVIDIA','mode':'preview'}).json()['id'];assert started.wait(2)
    client.put(f'/api/research/{id}/judgment',json={'text':'运行中用户判断'})
    client.post(f'/api/research/{id}/cancel',json={});gate.set();r=wait(client,id)
    assert r['status']=='cancelled' and r['judgment']['text']=='运行中用户判断'

def test_provenance_correction_version(client,monkeypatch):
    mock_live(monkeypatch);id=client.post('/api/research',json={'question':'测试研究'}).json()['id'];r=wait(client,id);sid=r['sources'][0]['id']
    assert client.post(f'/api/research/{id}/provenance',json={'source_id':sid,'origin_source_id':sid,'reason':'同源测试依据'}).status_code==200
    assert len(client.get('/api/research/'+id).json()['versions'])==2

def test_health_and_static(client):
    assert client.get('/').status_code==200
    assert client.get('/api/health').json()['deepseek_configured'] is False
    assert client.get('/static/app.js').status_code==200

def test_harness_material_ingest_and_judgment(client):
    s=source();id=client.post('/api/harness/research',json={'question':'测试Harness研究'}).json()['id']
    client.put(f'/api/research/{id}/judgment',json={'text':'用户判断不可修改'})
    payload={'sources':[{'url':s['url'],'title':'测试资料','date':'2026-11-08','content':s['content']}],'report':report(s)}
    r=client.post(f'/api/research/{id}/evidence',json=payload)
    assert r.status_code==200
    state=client.get('/api/research/'+id).json()
    assert len(state['events'])==1 and state['sources'][0]['kind']=='unverified'
    assert state['judgment']['text']=='用户判断不可修改' and state['judgment']['needs_review']
    assert client.post(f'/api/research/{id}/refresh',json={}).status_code==409
    payload['report']['claims'][0]['quote']='hallucinated quote'
    assert client.post(f'/api/research/{id}/evidence',json=payload).status_code==422
    assert len(client.get('/api/research/'+id).json()['versions'])==1

def test_mcp_initialize_and_no_note_write_tool():
    from harness_mcp import dispatch
    assert dispatch({'method':'initialize'})['protocolVersion']=='2024-11-05'
    tools=dispatch({'method':'tools/list'})['tools']
    assert {t['name'] for t in tools}=={'research_create','research_read','source_identify','evidence_submit','selection_read','market_read','ifind_news_search','research_resolve','source_register'}
    result=dispatch({'method':'tools/call','params':{'name':'source_identify','arguments':{'url':source()['url'],'content':source()['content']}}})
    assert json.loads(result['content'][0]['text'])['source_id']==source()['id']

def test_partial_validation_keeps_only_valid_claims_and_relations():
    from evidence import validate_report_partial
    s=source();raw=report(s)
    raw['claims'].append({**raw['claims'][0],'quote':'made up quote that is not present'})
    raw['relations']=[{'source_id':s['id'],'quote':QUOTE,'subject':'NVIDIA','relation':'test relationship','target':'TEST'},{'source_id':'fake','quote':QUOTE,'subject':'X','relation':'fake','target':'Y'}]
    checked=validate_report_partial(raw,[s])
    assert len(checked['claims'])==1 and len(checked['relations'])==1
    assert len(checked['validation_warnings'])==2
    assert all('quote' not in warning for warning in checked['validation_warnings'])

def test_research_bad_item_no_longer_discards_entire_valid_report(client,monkeypatch):
    s=mock_live(monkeypatch);original=providers.model
    def model(messages):
        out=original(messages)
        if '整理器' in messages[0]['content']:
            out['claims'].append({**out['claims'][0],'quote':'fabricated source quotation'})
        return out
    monkeypatch.setattr(providers,'model',model)
    id=client.post('/api/research',json={'question':'测试部分有效报告'}).json()['id']
    state=wait(client,id)
    assert state['status']=='partial' and len(state['claims'])==1
    assert state['validation_warnings'][0]['field']=='claims'
    assert any(s['name']=='证据条目拒绝' for s in state['steps'])

def test_report_all_invalid_keeps_sources_without_fake_report(client,monkeypatch):
    mock_live(monkeypatch);original=providers.model
    def model(messages):
        out=original(messages)
        if '整理器' in messages[0]['content']:out['claims'][0]['quote']='fabricated quote'
        return out
    monkeypatch.setattr(providers,'model',model)
    id=client.post('/api/research',json={'question':'测试全部无效报告'}).json()['id'];state=wait(client,id)
    assert state['status']=='failed' and not state['claims'] and state['sources']
    assert state['validation_warnings'] and not state['versions']

def test_followup_keeps_valid_answer_and_marks_rejected_answer(client,monkeypatch):
    s=mock_live(monkeypatch)
    id=client.post('/api/research',json={'question':'测试混合追问回答'}).json()['id'];wait(client,id)
    monkeypatch.setattr(providers,'model',lambda messages:{'answers':[{'text':'有效测试陈述','refs':[{'source_id':s['id'],'quote':QUOTE}]},{'text':'无依据测试陈述','refs':[{'source_id':'fake','quote':QUOTE}]}],'unknowns':[]})
    response=client.post(f'/api/research/{id}/ask',json={'question':'测试追问'}).json()
    assert len(response['answers'])==1 and len(response['validation_warnings'])==1
    assert response['answers'][0]['text']=='有效测试陈述'
