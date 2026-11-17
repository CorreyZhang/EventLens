import pytest

@pytest.fixture(autouse=True)
def disable_live_news(monkeypatch):
    monkeypatch.setenv("EVENTLENS_IFIND_NEWS","0")
