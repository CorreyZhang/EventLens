"""Assignment 08: evidence tiers, duplicate origins, correction/versions, freshness.

All fixtures are constructed; they are not real financial disclosures.
"""
from evidence import validate_report, recompute
from providers import source_record
from disclosure import normalized_source
from event_assessment import partition_sources


def make_source(path, text, kind="official", published="2026-11-10"):
    content = "Published: November 10, 2026\n" + text
    source = source_record({
        "url": "https://example.com/press/" + path,
        "title": "Constructed test disclosure",
        "date": published, "content": content,
    })
    source["kind"] = kind
    return source


def make_claim(source, quote, stance="reported", kind="FACT"):
    return {
        "source_id": source["id"],
        "quote": quote,
        "statement": "构造的调查声明",
        "subject": "Example Company",
        "action": "董事会调查",
        "event_key": "board_investigation",
        "occurred_at": "2026-11-08",
        "kind": kind, "stance": stance,
    }


def test_official_correction_updates_current_status_preserving_version():
    original = "The board announced an investigation."
    amended = "The board corrected its earlier investigation announcement."
    first = make_source("first", original)
    second = make_source("correction", amended)
    version_1 = validate_report({
        "claims": [make_claim(first, original)], "relations": []
    }, [first])["claims"]
    before = recompute(version_1, [first], "2026-11-17")
    assert len(before) == 1
    assert before[0]["status_code"] == "primary_document"
    assert before[0]["assessment"]["source_tiers"]["official"] == 1
    amended_claims = validate_report({
        "claims": [make_claim(first, original),
                   make_claim(second, amended, "corrects")],
        "relations": [],
    }, [first, second])["claims"]
    after = recompute(amended_claims, [first, second], "2026-11-17")
    assert len(after) == 1
    assert after[0]["id"] == before[0]["id"]
    assert after[0]["status_code"] == "correction_needs_review"
    assert after[0]["state"] != before[0]["state"]
    # A new text does not magically prove the semantic meaning or target.
    assert after[0]["assessment"]["semantic_verified"] is False


def test_reposted_identical_content_is_not_two_independent_votes():
    text = "This financial statement is a constructed source quote."
    first = make_source("origin-a", text, "unverified")
    mirror = make_source("mirror-b", text, "unverified")
    claims = validate_report({
        "claims": [make_claim(first, text), make_claim(mirror, text)],
        "relations": [],
    }, [first, mirror])["claims"]
    events = recompute(claims, [first, mirror], "2026-11-17")
    assert len(events) == 1
    assessment = events[0]["assessment"]
    assert assessment["claim_count"] == 2
    assert assessment["origin_count"] == 1
    assert assessment["source_tiers"] == {
        "regulatory": 0, "official": 0, "secondary": 1
    }
    assert events[0]["status_code"] == "secondary_facts"


def test_rumor_does_not_become_verified_fact():
    text = "An unconfirmed rumor about the board is circulating."
    src = make_source("rumor", text, "unverified")
    claims = validate_report({
        "claims": [make_claim(src, text, kind="RUMOR")], "relations": []
    }, [src])["claims"]
    event = recompute(claims, [src], "2026-11-17")[0]
    assert event["status_code"] == "opinion_or_rumor"
    assert event["assessment"]["semantic_verified"] is False


def test_age_alone_does_not_rewrite_evidence_conclusion():
    text = "The board announced an investigation."
    src = make_source("old", text, "official")
    claims = validate_report({
        "claims": [make_claim(src, text)], "relations": []
    }, [src])["claims"]
    event = recompute(claims, [src], "2027-01-31")[0]
    assert event["status_code"] == "primary_document"
    assert event["freshness_flag"]
    assert "超过30天" in event["assessment"]["freshness_note"]


def test_same_url_new_content_is_one_origin_not_independent_confirmation():
    original = "The board published the initial investigation statement."
    revised = "The board published a revised investigation statement."
    first = make_source("same-url", original)
    update = make_source("same-url", revised)
    assert first["id"] != update["id"]
    claims = validate_report({
        "claims": [make_claim(first, original), make_claim(update, revised, "update")],
        "relations": [],
    }, [first, update])["claims"]
    event = recompute(claims, [first, update], "2026-11-17")[0]
    assert event["source_count"] == 2  # Retain both source snapshots.
    assert event["assessment"]["origin_count"] == 1
    assert event["provenance_groups"] == 1
    assert event["assessment"]["origin_groups"][0]["source_ids"] == sorted(
        [first["id"], update["id"]]
    )


def test_mirror_and_revised_mirror_merge_transitively_without_losing_snapshots():
    first_text = "The company announced a constructed board investigation."
    revised_text = "The company revised its constructed board investigation."
    original = make_source("original", first_text, "unverified")
    mirror = make_source("mirror", first_text, "unverified")
    changed_mirror = make_source("mirror", revised_text, "unverified")
    claims = validate_report({
        "claims": [make_claim(original, first_text),
                   make_claim(mirror, first_text),
                   make_claim(changed_mirror, revised_text, "update")],
        "relations": [],
    }, [original, mirror, changed_mirror])["claims"]
    event = recompute(claims, [original, mirror, changed_mirror], "2026-11-17")[0]
    assert event["assessment"]["origin_count"] == 1
    assert event["provenance_groups"] == 1
    assert event["assessment"]["claim_count"] == 3


def test_missing_underlying_source_does_not_merge_unrelated_records():
    one = normalized_source(make_source("one", "A constructed first article."))
    two = normalized_source(make_source("two", "A completely different article."))
    for source in (one, two):
        source["underlying_source"] = None
        source["origin_group"] = None
        source["fingerprint"] = None
    assert len(partition_sources([one, two])) == 2


def test_explicit_shared_origin_survives_normalization():
    original = make_source("edition-a", "The first constructed disclosure.")
    reprint = make_source("edition-b", "The revised constructed disclosure.")
    for source in (original, reprint):
        source["underlying_source"] = "release-2026-11-10"
    assert normalized_source(original)["underlying_source"] == "release-2026-11-10"
    assert normalized_source(reprint)["underlying_source"] == "release-2026-11-10"
    assert len(partition_sources([original, reprint])) == 1
