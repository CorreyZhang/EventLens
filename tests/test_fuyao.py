import json
import pytest
import fuyao_client


class FakeResp:
    def __init__(self, data):self.data=data
    def __enter__(self):return self
    def __exit__(self, exc_type, exc, tb):return False
    def read(self, n):return json.dumps(self.data).encode()


def test_no_key(monkeypatch):
    monkeypatch.delenv("FUYAO_API_KEY", raising=False)
    with pytest.raises(fuyao_client.FuyaoError, match="未配置"):
        fuyao_client.stock_timeline()


def test_invalid_market(monkeypatch):
    monkeypatch.setenv("FUYAO_API_KEY", "placeholder-dont-use")
    with pytest.raises(fuyao_client.FuyaoError, match="仅支持"):
        fuyao_client.stock_timeline("NVDA")


def test_no_permission(monkeypatch):
    monkeypatch.setenv("FUYAO_API_KEY", "placeholder-dont-use")
    monkeypatch.setattr(fuyao_client.request, "urlopen", lambda *a, **k: FakeResp({"code":2003,"message":"forbidden"}))
    with pytest.raises(fuyao_client.FuyaoError, match="无权访问"):
        fuyao_client.stock_timeline()


def test_success(monkeypatch):
    monkeypatch.setenv("FUYAO_API_KEY", "placeholder-dont-use")
    def fake_open(request_obj, timeout=8):
        assert request_obj.full_url.startswith("https://fuyao.aicubes.cn/api/news/stock/timeline-list")
        assert request_obj.get_header("X-api-key") == "placeholder-dont-use"
        return FakeResp({"code":0,"data":{"items":[{"id":"abc","title":"示例标题","source":"示例来源","publish_time_ms":1000,"jump_url":"https://example.com"}]}})
    monkeypatch.setattr(fuyao_client.request, "urlopen", fake_open)
    result=fuyao_client.stock_timeline("300033.SZ")
    assert result["ok"] and result["item_count"] == 1
    assert "jump_url" not in result["preview"][0]
