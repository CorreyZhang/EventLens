"""Safety regression: changing research topic must never show another issuer's news.

Tests intentionally use local fixtures only. They do NOT demonstrate that
external BYD/TSLA news has been retrieved.
"""
from research_focus import focus_from_text, event_in_focus


def event(subject, action="公告"):
    return {"subject": subject, "action": action,
            "claims": [{"subject": subject, "statement": action}]}


def test_byd_question_cannot_show_nvidia_news():
    focus = focus_from_text("我搜比亚迪，最近有哪些值得关注的事件？")
    assert focus["subject"] == "比亚迪"
    assert focus["market_symbol"] is None
    assert event_in_focus(event("比亚迪股份有限公司"), focus)
    assert not event_in_focus(event("NVDA", "英伟达董事会调查"), focus)
    assert not event_in_focus(event("英伟达"), focus)


def test_new_topic_switch_replaces_focus_while_pronoun_followup_keeps_it():
    a = focus_from_text("最近英伟达的董事会发生什么？")
    b = focus_from_text("查一下比亚迪的新闻", a)
    c = focus_from_text("这条新闻有没有原始公告？", b)
    assert a["subject"] == "英伟达"
    assert b["subject"] == "比亚迪"
    assert c == b
    assert not event_in_focus(event("英伟达"), c)


def test_unknown_topic_fails_closed_instead_of_showing_all():
    focus = focus_from_text("最近氢能产业有什么新消息？")
    assert focus["market_symbol"] is None
    assert not event_in_focus(event("NVDA"), focus)


def test_cross_company_comparison_does_not_mislabel_old_news():
    focus = focus_from_text("苹果和英伟达的管理层变动有何不同？")
    assert focus["kind"] == "comparison"
    assert not event_in_focus(event("NVDA"), focus)


def test_quoted_passage_followup_keeps_issuer_not_deictic_phrase():
    focus=focus_from_text('同花顺三季报')
    assert focus_from_text('这段话里的68.86%是哪段时间的？',focus)==focus
    assert focus_from_text('你刚才引用的这个数字呢？',focus)==focus
    assert focus_from_text('那段原文有提到单季吗？',focus)==focus
    assert focus_from_text('这段话和比亚迪的公告有什么不同？',focus)['subject']=='比亚迪'


def test_catl_subject_variants_and_prior_study_isolation():
    for question in (
        "宁德时代",
        "我想了解一下宁德时代最近的公告",
        "查一下CATL的最新消息",
        "300750.SZ三季报有什么变化？",
    ):
        focus = focus_from_text(question)
        assert focus["subject"] == "宁德时代"
        assert focus["market_symbol"] == "300750.SZ"
        assert event_in_focus(event("宁德时代新能源科技股份有限公司"), focus)
        assert event_in_focus(event("300750.SZ"), focus)
        assert not event_in_focus(event("NVDA", "英伟达公告"), focus)
        assert not event_in_focus(event("同花顺"), focus)
    previous = focus_from_text("最近英伟达有什么公告？")
    current = focus_from_text("帮我搜索宁德时代最新消息", previous)
    assert current["subject"] == "宁德时代"
    assert focus_from_text("这条消息来自哪个原始来源？", current) == current
