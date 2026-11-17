"""v0.4.2 time-axis contract: event day != disclosure day != market day.

Pure source fixtures. Never contact a market provider or external API.
"""
from evidence import validate_report
from event_model import build_events
from providers import source_record


def sample(day, slug, action, occurred):
    text = (
        f"Published: November {day}, 2026\n"
        f"Apple Inc. announced: {action}; this is a source quote for testing."
    )
    doc = source_record({
        "url": f"https://example.com/press/{slug}",
        "title": action,
        "date": f"2026-11-{day:02d}",
        "content": text,
    })
    claim = {
        "source_id": doc["id"],
        "quote": f"Apple Inc. announced: {action}",
        "statement": action,
        "subject": "Apple Inc.",
        "action": action,
        "event_key": slug,
        "occurred_at": occurred,
        "kind": "FACT",
        "stance": "reported",
    }
    return doc, claim


def test_timeline_sorts_occurrence_then_labelled_disclosure_fallback():
    # Deliberately input in the WRONG order and make disclosure dates
    # contradict occurrence ordering.
    specs = [
        (13, "later-occurrence", "Management changes", "2026-11-12"),
        (14, "earlier-occurrence", "Product announcement", "2026-11-10"),
        (11, "no-occurrence", "Financial update", None),
    ]
    items = [sample(*s) for s in specs]
    sources = [doc for doc, _ in items]
    claims = validate_report({"claims": [claim for _, claim in items], "relations": []}, sources)["claims"]
    timeline = build_events(claims, sources, "2026-11-17", [], set())
    assert len(timeline) == 3
    assert [e["timeline_date"] for e in timeline] == [
        "2026-11-10", "2026-11-11", "2026-11-12"
    ]
    assert [e["timeline_basis"] for e in timeline] == [
        "发生时间", "披露时间（发生日待核）", "发生时间"
    ]
    # Market-session marker is independent and must not become the timeline day.
    assert all(e["marker_date"] is None for e in timeline)
    assert [e["timeline_disclosed_at"][:10] for e in timeline] == [
        "2026-11-14", "2026-11-11", "2026-11-13"
    ]


def test_unknown_dates_sort_last_without_inventing_occurrence():
    known_doc, known_claim = sample(15, "known", "Published update", None)
    unknown_doc, unknown_claim = sample(12, "undated", "Unverified update", None)
    # Remove its date line, leaving only a quote and discovery date metadata.
    unknown_doc["content"] = "Apple Inc. announced: Unverified update"
    docs = [unknown_doc, known_doc]
    claims = validate_report({"claims": [unknown_claim, known_claim], "relations": []}, docs)["claims"]
    result = build_events(claims, docs, "2026-11-17", [], set())
    assert [e["timeline_date"] for e in result] == ["2026-11-15", None]
    assert result[-1]["timeline_basis"] == "时间待核"


def test_chat_focus_is_inferred_without_manual_symbol_selector():
    from harness_web import explicit_focus

    assert explicit_focus("最近苹果有什么重要新闻？") == "AAPL"
    assert explicit_focus("AAPL 的财报呢") == "AAPL"
    assert explicit_focus("昨天英伟达有公告吗") == "NVDA"
    assert explicit_focus("苹果和英伟达有什么联系") == "MULTI"
    assert explicit_focus("这条新闻有多少可靠证据？") is None


def test_unknown_ticker_does_not_fetch_unrelated_market_data(monkeypatch):
    import marketdata
    from workbench import view

    def should_not_fetch(*args, **kwargs):
        raise AssertionError("unknown ticker must not call a stock provider")

    monkeypatch.setattr(marketdata, "daily", should_not_fetch)
    research = {
        "id": "a" * 32, "question": "现在有什么重要事件？",
        "as_of": "2026-11-17", "sources": [], "claims": [],
        "relations": [], "versions": [], "status": "awaiting_evidence",
    }
    rendered = view(research, symbol="NONE", start="2026-10-01",
                    end="2026-11-17", provider="ifind")
    assert rendered["market"]["status"] == "unavailable"
    assert rendered["market"]["symbol"] == ""
    assert rendered["events"] == []
    assert rendered["comparison"]["status"] == "unavailable"
