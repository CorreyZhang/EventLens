"""v0.5 offline fixtures; not real DeepSeek/search acceptance."""
import json
import pytest
from fastapi.testclient import TestClient
from app import create_app
from harness_mcp import call
from providers import source_record

@pytest.fixture
def env(tmp_path):
    app=create_app(tmp_path/'v05.sqlite3')
    return TestClient(app),app.state.store

def begin(c,q,sid='session-fixture',seq=1):
    return c.post('/api/workspace/session-event',json={'kind':'user_message','session_id':sid,'seq':seq,'text':q}).json()['active']['research_id']

def resolve(c,q,names):
    return c.post('/api/workspace/intent',json={'question':q,'entities':[{'name':n,'type':'topic','aliases':[n],'market_candidate':'NVDA'} for n in names]})

def claim(sid,subject='任意主体',kind='FACT'):
    return {'source_id':sid,'quote':'构造测试资料：该主体披露了新增生产计划。','statement':'新增生产计划','subject':subject,'action':'生产计划','event_key':'计划','kind':kind,'stance':'reported','occurred_at':None}

def source(c,rid,url='https://example.org/fixture'):
    body={'url':url,'content':'构造测试资料：该主体披露了新增生产计划。'}
    return body,c.post(f'/api/research/{rid}/source',json=body).json()['source_id']

def test_arbitrary_subject_no_ticker_and_partial_strict_submission(env):
    c,store=env;q='帮我看看任意主体最近的消息';rid=begin(c,q)
    focus=resolve(c,q,['任意主体']).json()['focus']
    assert focus['market_symbol'] is None and focus['verified'] is False
    body,sid=source(c,rid)
    assert call('source_identify',body)['source_id']==sid
    bad=claim('Sdoes-not-exist');unknown=claim(sid,kind='没有依据的事实')
    response=c.post(f'/api/research/{rid}/evidence',json={'sources':[],'report':{'claims':[claim(sid,kind='事实'),bad,unknown]}})
    assert response.status_code==200
    assert response.json()['accepted_claims']==1 and len(response.json()['rejected'])==2
    view=c.get(f'/api/workspace/research/{rid}/view').json()
    assert len(view['events'])==1 and view['market']['status']=='unavailable'
    before=store.get(rid)
    denied=c.post(f'/api/research/{rid}/evidence',json={'sources':[],'report':{'claims':[bad,unknown]}})
    assert denied.status_code==422
    assert len(store.get(rid)['versions'])==len(before['versions'])
    assert len(store.get(rid)['claims'])==1

def test_scope_switch_comparison_pronouns_and_history(env):
    c,store=env;q='看看Atlas Dynamics有什么消息';rid=begin(c,q)
    resolve(c,q,['Atlas Dynamics']);_,sid=source(c,rid)
    def submit(name):
        return c.post(f'/api/research/{rid}/evidence',json={'sources':[],'report':{'claims':[claim(sid,subject=name)]}})
    assert submit('Atlas Dynamics').status_code==200
    q2='这个计划有哪些来源？';begin(c,q2,seq=2);resolve(c,q2,['Atlas Dynamics'])
    assert len(c.get(f'/api/workspace/research/{rid}/view').json()['events'])==1
    q3='现在查一下新监管办法';begin(c,q3,seq=3);resolve(c,q3,['新监管办法'])
    assert c.get(f'/api/workspace/research/{rid}/view').json()['events']==[]
    assert submit('新监管办法').status_code==200
    assert submit('Atlas Dynamics').status_code==422
    q4='比较Atlas Dynamics和新监管办法';begin(c,q4,seq=4);resolve(c,q4,['Atlas Dynamics','新监管办法'])
    assert submit('Atlas Dynamics').status_code==200 and submit('新监管办法').status_code==200
    assert len(c.get(f'/api/workspace/research/{rid}/view').json()['events'])==2
    other=begin(c,'另一个研究',sid='session-other');resolve(c,'另一个研究',['另一个研究'])
    assert c.get(f'/api/workspace/research/{rid}/view').status_code==409
    c.post('/api/workspace/session-event',json={'kind':'session_activated','session_id':'session-fixture'})
    assert len(c.get(f'/api/workspace/research/{rid}/view').json()['events'])==2
    assert len(store.get(rid)['claims'])==4

def test_canonical_sources_dedup_and_content_versions(env):
    c,store=env;rid=begin(c,'没有资料可核对');resolve(c,'没有资料可核对',['某政策'])
    body,sid=source(c,rid)
    assert call('source_identify',{**body,'url':body['url']+'/?utm_source=x#part'})['source_id']==sid
    assert c.post(f'/api/research/{rid}/source',json=body).json()['source_id']==sid
    changed={**body,'content':body['content']+'原文更正。'}
    assert c.post(f'/api/research/{rid}/source',json=changed).json()['source_id']!=sid
    assert len(store.get(rid)['sources'])==2
    assert store.get(rid)['events']==[]
    assert c.post('/api/workspace/intent',json={'question':'wrong turn','entities':[]}).status_code==409
    assert c.post(f'/api/research/{rid}/evidence',content='{bad',headers={'content-type':'application/json'}).status_code==422
    assert c.post(f'/api/research/{rid}/evidence',json={'sources':[],'report':{'claims':[]}}).status_code==422

def test_market_guess_cannot_enable_unrelated_instrument(env):
    c,_=env;q='调查任意主体近期事件';rid=begin(c,q)
    response=c.post('/api/workspace/intent',json={'question':q,'entities':[{'name':'任意主体','type':'company','aliases':['NVDA'],'market_candidate':'NVDA'}]})
    assert response.json()['focus']['market_symbol'] is None
    assert c.get('/api/market/ohlc').json()['status']=='unavailable'

def test_read_retry_is_bounded_and_write_never_replayed(monkeypatch,tmp_path):
    import urllib.error
    import harness_mcp
    monkeypatch.setattr(harness_mcp,'FAILURE_LOG',tmp_path/'fixture-failures.jsonl')
    calls=[]
    def unavailable(*args,**kwargs):
        calls.append(1);raise urllib.error.URLError('fixture unavailable')
    monkeypatch.setattr(harness_mcp.urllib.request,'urlopen',unavailable)
    with pytest.raises(ValueError):harness_mcp.request_json('http://127.0.0.1:8765/api/workspace/state')
    assert len(calls)==2
    calls.clear()
    req=harness_mcp.urllib.request.Request('http://127.0.0.1:8765/api/fixture',data=b'{}')
    with pytest.raises(ValueError):harness_mcp.request_json(req)
    assert len(calls)==1

def test_background_cannot_submit_to_inactive_native_research(env):
    c,store=env;rid=begin(c,'任意主体研究');resolve(c,'任意主体研究',['任意主体']);body,sid=source(c,rid)
    begin(c,'另一个主体研究',sid='session-second')
    denied=c.post(f'/api/research/{rid}/evidence',json={'sources':[],'report':{'claims':[claim(sid)]}})
    assert denied.status_code==409 and store.get(rid)['claims']==[]
    assert c.post(f'/api/research/{rid}/source',json=body).status_code==409


def test_pre_v05_focus_migrates_without_losing_scope_identity():
    from research_focus import focus_from_text,resolve_focus
    old={'subject':'同花顺','subjects':['同花顺'],'aliases':['同花顺'],'kind':'company'}
    current=focus_from_text('同花顺那份报告呢？',old)
    resolved=resolve_focus(current,[{'name':'同花顺','type':'company','aliases':['同花顺']}])
    assert resolved['scope_id']==current['scope_id']

@pytest.mark.parametrize('name,kind',[('Aster Labs','company'),('林某','person'),('动力电池行业','industry'),('某监管机构','organization'),('一项新规','policy'),('跨境并购','event'),('ABCD.X','company')])
def test_generic_entity_types_are_not_market_whitelisted(name,kind):
    from research_focus import focus_from_text,resolve_focus,event_in_focus
    focus=resolve_focus(focus_from_text('帮我研究'+name),[{'name':name,'type':kind,'aliases':[name],'market_candidate':'NVDA'}])
    assert focus['market_symbol'] is None and focus['verified'] is False
    assert event_in_focus({'claims':[{'research_scope_id':focus['scope_id'],'subject':name}]},focus)

def test_no_symbol_does_not_call_any_calendar(env,monkeypatch):
    import workbench
    c,_=env;q='看看不上市机构的政策';rid=begin(c,q);resolve(c,q,['不上市机构政策'])
    def forbidden(*a,**kw):raise RuntimeError('fixture calendar unavailable')
    monkeypatch.setattr(workbench,'exchange_schedule',forbidden)
    assert c.get(f'/api/workspace/research/{rid}/view').status_code==200

def test_named_document_needs_direct_name_in_source_not_nearby_topic(env):
    c,store=env;q='《某不存在的命名文件》是真的吗？';rid=begin(c,q)
    resolve(c,q,['某不存在的命名文件','某机构'])
    body,sid=source(c,rid)
    accepted=c.post(f'/api/research/{rid}/evidence',json={'sources':[],'report':{'claims':[claim(sid,subject='某不存在的命名文件')]}})
    assert accepted.status_code==422
    assert store.get(rid)['claims']==[]
    assert c.get(f'/api/workspace/research/{rid}/view').json()['events']==[]
    assert c.get(f'/api/research/{rid}?focus=current').json()['claims']==[]
    body={'url':'https://example.org/named','content':'某不存在的命名文件是一条明确点名的构造来源，不能推断真实存在。'}
    sid=c.post(f'/api/research/{rid}/source',json=body).json()['source_id']
    item={**claim(sid,subject='某不存在的命名文件'),'quote':body['content'],'statement':'仅构造原文定位测试'}
    assert c.post(f'/api/research/{rid}/evidence',json={'sources':[],'report':{'claims':[item]}}).status_code==200
    assert len(c.get(f'/api/workspace/research/{rid}/view').json()['events'])==1

def test_invalid_submission_budget_and_same_payload_not_retried(env):
    c,store=env;q='任意主体消息';rid=begin(c,q);resolve(c,q,['任意主体']);_,sid=source(c,rid)
    bad=claim('Snonexistent')
    url=f'/api/research/{rid}/evidence'
    assert c.post(url,json={'sources':[],'report':{'claims':[bad]}}).status_code==422
    assert c.post(url,json={'sources':[],'report':{'claims':[bad]}}).status_code==409
    assert c.post(url,json={'sources':[],'report':{'claims':[{**bad,'statement':'另一个无效输入'}]}}).status_code==422
    assert c.post(url,json={'sources':[],'report':{'claims':[claim(sid)]}}).status_code==429
    begin(c,'这个来源再试一次',seq=2)
    assert c.post(url,json={'sources':[],'report':{'claims':[claim(sid)]}}).status_code==200
