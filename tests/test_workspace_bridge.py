"""v0.4 conversation/research and quoted-evidence regression tests (no live keys)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

import providers
from app import create_app
from evidence import validate_report
from event_model import build_events


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = create_app(str(tmp_path / "eventlens.sqlite3"))
    return TestClient(app), app.state.store


def event(client, sid, kind, seq=0, text=""):
    r = client.post("/api/workspace/session-event", json={
        "session_id": sid, "kind": kind, "seq": seq, "text": text
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_new_harness_chat_makes_its_own_draft_research(env):
    client, store = env
    a = event(client, "session-a", "session_created")
    assert a["active"]["status"] == "draft"
    first_id = a["active"]["research_id"]
    a = event(client, "session-a", "user_message", 4, "英伟达最近有什么新闻？")
    assert a["active"]["research_id"] == first_id
    assert store.get(first_id)["question"] == "英伟达最近有什么新闻？"
    event(client, "session-a", "user_message", 9, "这份公告有依据吗？")
    assert store.get(first_id)["question"] == "英伟达最近有什么新闻？"
    b = event(client, "session-b", "session_created")
    assert b["active"]["status"] == "draft"
    assert b["active"]["research_id"] != first_id
    updated = event(client, "session-b", "user_message", 2, "同花顺三季报")
    assert updated["active"]["research_id"] == b["active"]["research_id"]
    assert store.get(b["active"]["research_id"])["question"] == "同花顺三季报"
    assert store.get(first_id)["question"] == "英伟达最近有什么新闻？"


def test_replayed_turn_does_not_replace_topic(env):
    client, store = env
    original = event(client, "session-repeat", "user_message", 3, "第一次研究内容")
    research_id = original["active"]["research_id"]
    event(client, "session-repeat", "user_message", 3, "重放错误文本")
    assert store.get(research_id)["question"] == "第一次研究内容"


def quoted_fixture(env):
    client, store = env
    response = event(client, "session-quote", "user_message", 1, "帮我调查英伟达这份公告")
    rid = response["active"]["research_id"]
    quote = "The board announced an independent investigation."
    source = providers.source_record({
        "url": "https://example.com/press/statement",
        "title": "Press statement",
        "date": date.today().isoformat(),
        "content": quote,
    })
    item = {
        "source_id": source["id"], "quote": quote,
        "statement": "董事会宣布独立调查", "subject": "NVIDIA",
        "action": "调查", "event_key": "statement", "occurred_at": None,
        "kind": "FACT", "stance": "reported"
    }
    claims = validate_report({"claims": [item], "relations": []}, [source])["claims"]
    study = store.get(rid)
    study.pop("judgment", None)
    study["sources"] = [source]
    study["claims"] = claims
    study["versions"].append({"number": 1, "reason": "test"})
    store.save(study)
    selected = build_events(claims, [source], study["as_of"])[0]
    return client, store, rid, source, quote, selected["id"]


def test_reference_is_verified_and_not_an_automatic_chat_message(env):
    client, store, rid, source, quote, eid = quoted_fixture(env)
    before = store.get(rid)["messages"]
    payload = {"research_id": rid, "event_id": eid,
               "source_id": source["id"], "quote": quote}
    reply = client.post("/api/workspace/reference", json=payload)
    assert reply.status_code == 200, reply.text
    assert len(reply.json()["references"]) == 1
    assert store.get(rid)["messages"] == before
    again = client.post("/api/workspace/reference", json=payload)
    assert len(again.json()["references"]) == 1
    bridge = client.app.state.workspace_bridge
    assert bridge.for_model_request({"messages": [
        {"role": "user", "content": "另一个会话的不相干问题"}
    ]}) is None
    context = bridge.for_model_request({
        "messages": [{"role": "user", "content": "帮我调查英伟达这份公告"}]
    })
    assert context["context"]["references"][0]["source_id"] == source["id"]
    bridge.mark_sent(context)
    assert client.get("/api/workspace/state").json()["references"] == []


def test_cross_research_reference_is_rejected(env):
    client, store, rid, source, quote, eid = quoted_fixture(env)
    event(client, "session-other", "session_created")
    response = client.post("/api/workspace/reference", json={
        "research_id": rid, "event_id": eid,
        "source_id": source["id"], "quote": quote
    })
    assert response.status_code == 409
    assert not client.get("/api/workspace/state").json()["references"]


def test_invalid_original_quote_is_rejected(env):
    client, store, rid, source, quote, eid = quoted_fixture(env)
    response = client.post("/api/workspace/reference", json={
        "research_id": rid, "event_id": eid,
        "source_id": source["id"], "quote": "This fake quote is not in the original."
    })
    assert response.status_code == 422
    assert not client.get("/api/workspace/state").json()["references"]


def test_old_selection_not_injected_into_new_chat(env):
    client, store, rid, source, quote, eid = quoted_fixture(env)
    r = client.post("/api/harness/selection", json={
        "research_id": rid, "event_id": eid, "source_ids": [source["id"]],
        "market_window": {"symbol": "NVDA", "provider": "ifind",
                          "start": "2026-11-01", "end": "2026-11-17"}
    })
    assert r.status_code == 200, r.text
    event(client, "session-new", "session_created")
    selected = client.get("/api/harness/selection").json()
    assert selected["status"] == "no_selection"


def test_switching_subject_within_chat_invalidates_old_source_and_selection(env):
    client, store, rid, source, quote, eid = quoted_fixture(env)
    first = client.post("/api/harness/selection", json={
        "research_id": rid, "event_id": eid, "source_ids": [source["id"]],
        "market_window": {"symbol": "NVDA", "provider": "ifind",
                          "start": "2026-11-01", "end": "2026-11-17"},
    })
    assert first.status_code == 200, first.text
    # Same study, different subject: old NVDA evidence must disappear.
    switched = event(client, "session-quote", "user_message", 2,
                     "查一下比亚迪最近有哪些重要事件？")
    assert switched["active"]["research_id"] == rid
    assert switched["active"]["focus"]["subject"] == "比亚迪"
    assert client.get("/api/harness/selection").json()["status"] == "no_selection"
    forbidden = client.post("/api/workspace/reference", json={
        "research_id": rid, "event_id": eid,
        "source_id": source["id"], "quote": quote
    })
    assert forbidden.status_code == 409
    scoped = client.get(
        "/api/workspace/research/{}/view?start=2026-11-01&end=2026-11-17".format(rid)
    )
    assert scoped.status_code == 200, scoped.text
    assert scoped.json()["events"] == []
    assert scoped.json()["sources"] == []
    assert scoped.json()["market"]["symbol"] == ""


def test_known_session_reactivation_restores_binding_without_new_research(env):
    client, store = env
    a = event(client, "switch-a", "user_message", 1, "英伟达发生了什么？")
    rid_a = a["active"]["research_id"]
    b = event(client, "switch-b", "user_message", 1, "比亚迪最近发生了什么？")
    rid_b = b["active"]["research_id"]
    restored = event(client, "switch-a", "session_activated")
    assert restored["active"]["research_id"] == rid_a
    assert restored["active"]["focus"]["subject"] == "英伟达"
    assert rid_a != rid_b
    assert store.get(rid_a)["question"] == "英伟达发生了什么？"


def test_unknown_history_session_activation_clears_stale_active_pane(env):
    client, store = env
    event(client, "has-research", "user_message", 1, "英伟达新闻")
    unbound = event(client, "historical-not-bound", "session_activated")
    assert unbound["active"] is None
    assert unbound["reason"] == "unbound_history_session"
    assert client.get("/api/workspace/state").json()["active"] is None


def test_navigation_clear_and_silent_restore_preserve_two_studies(env):
    client, store = env
    a = event(client, 'history-a', 'user_message', 1, '同花顺三季报')
    b = event(client, 'history-b', 'user_message', 1, '比亚迪最近有什么消息？')
    event(client, 'none', 'session_deactivated')
    assert client.get('/api/workspace/state').json()['active'] is None
    restored = event(client, 'history-a', 'session_activated')
    assert restored['active']['research_id'] == a['active']['research_id']
    assert restored['active']['last_prompt'] == '同花顺三季报'
    restored = event(client, 'history-b', 'session_activated')
    assert restored['active']['research_id'] == b['active']['research_id']
    assert store.get(a['active']['research_id'])['question'] == '同花顺三季报'


def test_ui_assets_revalidate_and_private_workspace_state_is_not_cached(env):
    client, _ = env
    assert client.get('/static/workbench.js').headers['cache-control'] == 'no-cache'
    assert client.get('/workstation').headers['cache-control'] == 'no-cache'
    assert client.get('/api/workspace/state').headers['cache-control'] == 'no-store'


def test_native_identity_handles_runtime_text_after_human_prompt(env):
    client, _, rid, source, quote, eid = quoted_fixture(env)
    client.post('/api/workspace/reference',json={'research_id':rid,'event_id':eid,'source_id':source['id'],'quote':quote})
    bridge=client.app.state.workspace_bridge
    payload={'eventlens_context':{'session_id':'session-quote','user_seq':1},
             'messages':[{'role':'user','content':'帮我调查英伟达这份公告'},
                         {'role':'user','content':'Injected runtime context after human prompt'}]}
    used=bridge.for_model_request(payload)
    assert used is not None
    bridge.mark_sent(used)
    assert client.get('/api/workspace/state').json()['references']==[]
    assert bridge.for_model_request(payload) is not None  # another tool step
    event(client,'session-quote','user_message',2,'还有别的证据吗？')
    payload['eventlens_context']['user_seq']=2
    assert bridge.for_model_request(payload) is None


def test_wrong_native_session_cannot_borrow_identical_prompt(env):
    client, _, rid, source, quote, eid = quoted_fixture(env)
    client.post('/api/workspace/reference',json={'research_id':rid,'event_id':eid,'source_id':source['id'],'quote':quote})
    payload={'eventlens_context':{'session_id':'another-session','user_seq':1},
             'messages':[{'role':'user','content':'帮我调查英伟达这份公告'}]}
    assert client.app.state.workspace_bridge.for_model_request(payload) is None
