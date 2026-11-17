"""Public free-tier entrypoint: explicit browser isolation and no unlimited API calls."""
import app as eventlens
from fastapi.testclient import TestClient


class IdlePool:
    def submit(self, *args, **kwargs):
        # Prevent background AI/network calls in this isolated boundary test.
        return None


def clients(monkeypatch, tmp_path, **env):
    monkeypatch.setenv("EVENTLENS_PUBLIC_DEMO", "1")
    monkeypatch.setenv("EVENTLENS_IFIND_NEWS", "0")
    for key, val in env.items():
        monkeypatch.setenv(key, str(val))
    monkeypatch.setattr(eventlens, "POOL", IdlePool())
    app = eventlens.create_app(tmp_path / "public.db")
    return app, TestClient(app), TestClient(app)


def test_guest_cookie_and_no_cross_visitor_leak(monkeypatch, tmp_path):
    app, alice, bob = clients(monkeypatch, tmp_path)
    assert alice.get("/").status_code == 200
    assert bob.get("/").status_code == 200
    a = alice.cookies.get("eventlens_guest")
    b = bob.cookies.get("eventlens_guest")
    assert a != b and len(a) > 50 and len(b) > 50

    res = alice.post("/api/research", json={"question": "检查示例事件", "mode": "live"})
    assert res.status_code == 202
    rid = res.json()["id"]
    assert alice.get(f"/api/research/{rid}").status_code == 200
    assert [x["id"] for x in alice.get("/api/research").json()] == [rid]
    assert bob.get("/api/research").json() == []
    assert bob.get(f"/api/research/{rid}").status_code == 404
    assert bob.put(f"/api/research/{rid}/judgment", json={"text": "偷写"}).status_code == 404
    assert app.state.store.get(rid)["judgment"]["text"] == ""


def test_public_harness_and_evidence_ingestion_disallowed(monkeypatch, tmp_path):
    _, alice, _ = clients(monkeypatch, tmp_path)
    rid = alice.post("/api/research", json={"question": "测试事件范围", "mode": "live"}).json()["id"]
    for path in ("/workstation", "/harness/open", "/api/workspace/state",
                 "/api/market/ohlc", "/api/harness/research"):
        assert alice.get(path).status_code == 404
    assert alice.post(f"/api/research/{rid}/source", json={"url": "https://example.org"}).status_code == 403
    assert alice.post(f"/api/research/{rid}/evidence", json={}).status_code == 403
    assert alice.post(f"/api/research/{rid}/refresh", json={}).status_code == 403
    assert alice.post(f"/api/research/{rid}/ask",
                      json={"question": "再次联网", "refresh": True}).status_code == 403
    assert alice.put(f"/api/research/{rid}/judgment", json={"text": "跨站"},
                     headers={"Origin": "https://malicious.example"}).status_code == 403
    assert alice.put(f"/api/research/{rid}/judgment",
                     data="text=malicious", headers={"Content-Type": "text/plain"}).status_code == 415


def test_public_global_research_budget_cannot_be_bypassed_with_new_browser(monkeypatch, tmp_path):
    _, alice, bob = clients(monkeypatch, tmp_path, EVENTLENS_DEMO_MAX_RESEARCH=1)
    assert alice.post("/api/research", json={"question": "首先研究这个", "mode": "live"}).status_code == 202
    assert bob.post("/api/research", json={"question": "新的访客研究", "mode": "live"}).status_code == 429
    assert alice.post("/api/research", json={"question": "再试一遍", "mode": "live"}).status_code == 429
    assert bob.get("/api/research").json() == []


def test_invalid_guest_signature_does_not_grant_existing_study(monkeypatch, tmp_path):
    app, alice, bob = clients(monkeypatch, tmp_path)
    rid = alice.post("/api/research", json={"question": "研究个人资料", "mode": "preview"}).json()["id"]
    raw = alice.cookies.get("eventlens_guest")
    bob.cookies.set("eventlens_guest", raw[:-1] + ("0" if raw[-1] != "0" else "1"))
    assert bob.get(f"/api/research/{rid}").status_code == 404
    assert bob.get("/api/research").json() == []


def test_public_home_loads_research_interface_not_local_harness(monkeypatch, tmp_path):
    _, guest, _ = clients(monkeypatch, tmp_path)
    result = guest.get("/")
    assert result.status_code == 200
    assert "public-ui.js" in result.text
    assert '<script src="/static/workbench.js' not in result.text
    assert 'id="researchForm"' in result.text
    assert guest.get("/static/public-ui.js").status_code == 200


def test_public_frontend_reveals_actual_result_cards(monkeypatch, tmp_path):
    _, guest, _ = clients(monkeypatch, tmp_path)
    script = guest.get("/static/public-ui.js")
    assert script.status_code == 200
    # The standalone FastAPI UI must unhide the existing evidence+versions
    # panels when native Harness is disabled.
    assert "classList.add('show-legacy')" in script.text
    assert "#workspace:not([hidden]) .tabs" in script.text
    assert "#workspace:not([hidden]) .columns" in script.text
    assert "min-height: 100vh" in script.text


def test_cloud_twin_preserves_original_workbench_without_native_harness(monkeypatch, tmp_path):
    app, alice, bob = clients(monkeypatch, tmp_path)
    response = alice.get("/cloud-workstation")
    assert response.status_code == 200
    assert 'id="research"' in response.text
    assert 'src="/static/cloud-chat.html"' in response.text
    assert 'id="eventTrack"' not in response.text  # original left is in the iframe
    assert response.headers.get("x-frame-options") == "SAMEORIGIN"
    embedded = alice.get("/?embedded=1&cloud=1")
    assert embedded.status_code == 200
    assert "/static/workbench.js?v=0.5.0" in embedded.text
    assert "public-ui.js" not in embedded.text
    assert embedded.headers["x-frame-options"] == "SAMEORIGIN"
    chat = alice.get("/static/cloud-chat.html")
    assert chat.status_code == 200
    assert "cloud-chat.js" in chat.text
    assert chat.headers["x-frame-options"] == "SAMEORIGIN"
    assert alice.get("/static/cloud-workstation.js").status_code == 200
    assert alice.get("/static/cloud-chat.js").status_code == 200

    new = alice.post("/api/research", json={
        "question": "同花顺季度报告有哪些可验证的公告？", "mode": "live"
    })
    assert new.status_code == 202
    rid = new.json()["id"]
    visible = alice.get(f"/api/workspace/research/{rid}/view")
    assert visible.status_code == 200
    result = visible.json()
    assert result["research_id"] == rid
    assert result["market"]["status"] == "unavailable"
    assert bob.get(f"/api/workspace/research/{rid}/view").status_code == 404
    assert alice.post(f"/api/workspace/research/{rid}/view", json={}).status_code == 404
    assert alice.get("/api/workspace/state").status_code == 404
