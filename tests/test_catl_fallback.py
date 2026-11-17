"""CATL regression fixtures: do not mistake A-share data failure for no event.

The disclosure below is invented for unit testing and is NOT market news.
"""
from evidence import validate_report
from marketdata import SYMBOLS
from providers import source_record
from workbench import view


def test_catl_offline_evidence_survives_missing_fuyao_calendar(monkeypatch):
    quote = "CATL issued a constructed quarterly statement."
    source = source_record({
        "url": "https://example.com/catl/constructed-statement",
        "title": "Constructed, not a real CATL filing",
        "date": "2026-11-12",
        "content": "Published: November 12, 2026\n" + quote,
    })
    report = validate_report({
        "claims": [{
            "source_id": source["id"], "quote": quote,
            "statement": "构造的宁德时代季报声明",
            "subject": "宁德时代新能源科技股份有限公司",
            "action": "披露季度报告",
            "event_key": "example_quarterly_report",
            "occurred_at": "2026-11-12",
            "kind": "FACT", "stance": "reported",
        }],
        "relations": [],
    }, [source])
    research = {
        "id": "c" * 32,
        "question": "宁德时代最新公告",
        "as_of": "2026-11-17",
        "status": "ready",
        "sources": [source],
        "claims": report["claims"],
        "relations": [],
        "versions": [],
    }
    assert SYMBOLS["300750.SZ"] == "宁德时代 A股"

    def missing_calendar(*args, **kwargs):
        raise RuntimeError("Constructed no entitlement: no calendar available")

    def fake_daily(symbol, start, end, provider):
        assert symbol in ("300750.SZ", "000300.SH")
        assert provider == "fuyao"
        return {
            "symbol": symbol, "label": SYMBOLS[symbol],
            "provider": "扶摇", "instrument_type": "equity",
            "bars": [], "status": "unavailable",
            "reason": "constructed no market entitlement",
        }

    def forbid_us_calendar(*args, **kwargs):
        raise AssertionError("A-share must never use the US exchange calendar")

    monkeypatch.setattr("finance_runtime.call", missing_calendar)
    monkeypatch.setattr("workbench.exchange_schedule", forbid_us_calendar)
    monkeypatch.setattr("workbench.marketdata.daily", fake_daily)
    result = view(research, "300750.SZ", provider="fuyao")
    assert result["market"]["status"] == "unavailable"
    assert result["events"]
    assert result["events"][0]["timeline_date"] == "2026-11-12"
    assert result["events"][0]["source_ids"] == [source["id"]]
    assert result["markers"] == []
    assert any("交易日历不可用" in note for note in result["warnings"])


def test_catl_chinese_and_english_claims_merge_one_atomic_event():
    from evidence import recompute
    a_quote = "CATL issued a constructed quarterly report."
    b_quote = "宁德时代发布构造测试季度报告。"
    first = source_record({
        "url": "https://example.com/catl/example-en",
        "date": "2026-11-12",
        "content": "Published: November 12, 2026\n" + a_quote,
    })
    second = source_record({
        "url": "https://example.com/catl/example-zh",
        "date": "2026-11-12",
        "content": "Published: November 12, 2026\n" + b_quote,
    })
    claims = []
    for src, quote, subject in (
        (first, a_quote, "CATL"),
        (second, b_quote, "宁德时代新能源科技股份有限公司"),
    ):
        claims.append({
            "source_id": src["id"], "quote": quote,
            "statement": "构造的财报披露",
            "subject": subject, "action": "披露季度报告",
            "event_key": "constructed_quarterly_statement",
            "occurred_at": "2026-11-12",
            "kind": "FACT", "stance": "reported",
        })
    validated = validate_report({"claims": claims, "relations": []}, [first, second])
    events = recompute(validated["claims"], [first, second], "2026-11-17")
    assert len(events) == 1
    assert events[0]["subject"] == "300750.SZ"
    assert set(events[0]["source_ids"]) == {first["id"], second["id"]}


def test_catl_proxy_exception_returns_unavailable_market_not_http_500(monkeypatch):
    import marketdata

    def failed_proxy(*args, **kwargs):
        raise RuntimeError("constructed runtime unavailable")

    monkeypatch.setattr("fuyao_client.historical", failed_proxy)
    row = marketdata.daily(
        "300750.SZ", "2026-10-01", "2026-10-10",
        provider="fuyao", force=True
    )
    assert row["status"] == "unavailable"
    assert row["bars"] == []
    assert "扶摇" in row["reason"]
