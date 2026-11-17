"""Transparent evidence-weight explanations and conservative event status.

This is an auditable evidence *display rule*, not an AI truth oracle.
The type of a webpage and exact quoted string cannot independently verify the
semantics of a claim. A single syndicated story is never multiple votes.
"""
from datetime import date
from disclosure import normalized_source


def partition_sources(sources):
    """Group source versions and reprints by connected, nonempty identities.

    Same URL across revisions and identical text across mirrors each imply
    one underlying origin. Missing identity fields never merge two sources.
    This is deduplication, NOT verification that the origins are independent.
    """
    docs = {s["id"]: normalized_source(s) for s in sources}
    parent = {sid: sid for sid in docs}
    seen = {}

    def root(sid):
        while parent[sid] != sid:
            parent[sid] = parent[parent[sid]]
            sid = parent[sid]
        return sid

    for sid in sorted(docs):
        source = docs[sid]
        for kind, value in (
            ("declared", source.get("origin_group")),
            ("underlying", source.get("underlying_source")),
            ("content", source.get("fingerprint")),
            ("url", source.get("source_identity")),
        ):
            if not value:
                continue
            token = (kind, str(value))
            if token in seen:
                parent[root(sid)] = root(seen[token])
            else:
                seen[token] = sid

    groups = {}
    for sid in sorted(docs):
        groups.setdefault(root(sid), []).append(sid)
    return sorted(groups.values(), key=lambda group: group[0])


def assess(event, sources, as_of):
    docs = {s["id"]: normalized_source(s) for s in sources}
    claims = event.get("claims", [])
    grouped = {}
    used_sources = [docs[c["source_id"]] for c in claims
                    if c.get("source_id") in docs]
    for source_ids in partition_sources(used_sources):
        members = [docs[sid] for sid in source_ids]
        explicit = sorted(s["origin_group"] for s in members if s.get("origin_group"))
        underlying = sorted(s["underlying_source"] for s in members
                            if s.get("underlying_source"))
        fingerprints = sorted(s["fingerprint"] for s in members
                              if s.get("fingerprint"))
        group = (explicit[0] if explicit else
                 underlying[0] if underlying else
                 "sha256:" + fingerprints[0] if fingerprints else source_ids[0])
        tiers = [
            "regulatory" if s.get("kind") == "regulatory" else
            "official" if s.get("kind") == "official" else "secondary"
            for s in members
        ]
        tier = max(tiers, key={"secondary": 0, "official": 1, "regulatory": 2}.get)
        items = [c for c in claims if c.get("source_id") in source_ids]
        grouped[group] = {
            "origin_group": group, "tier": tier,
            "source_ids": set(source_ids),
            "claim_kinds": {c.get("kind") for c in items},
            "stances": {c.get("stance") for c in items},
        }
    counts = {"regulatory": 0, "official": 0, "secondary": 0}
    detail = []
    for group, item in sorted(grouped.items()):
        counts[item["tier"]] += 1
        detail.append({
            "origin_group": group,
            "source_ids": sorted(item["source_ids"]),
            "tier": item["tier"],
            "tier_label": {
                "regulatory": "监管来源标记（原文语义待核）",
                "official": "一手来源标记（原文语义待核）",
                "secondary": "二手或身份未核来源",
            }[item["tier"]],
            "kind_labels": sorted(str(k) for k in item["claim_kinds"] if k),
            "stances": sorted(str(v) for v in item["stances"] if v),
            "independent_verified": False,
        })
    official_fact = any(
        (docs.get(c.get("source_id"), {}).get("kind") in ("official", "regulatory") and
         c.get("kind") == "FACT" and c.get("stance") in ("reported", "supports", "update"))
        for c in claims
    )
    official_correction = any(
        docs.get(c.get("source_id"), {}).get("kind") in ("official", "regulatory") and
        c.get("kind") == "FACT" and c.get("stance") == "corrects"
        for c in claims
    )
    has_correction = any(c.get("stance") == "corrects" for c in claims)
    has_dispute = any(c.get("stance") == "disputes" for c in claims)
    has_fact = any(c.get("kind") == "FACT" for c in claims)
    only_opinion_or_rumor = bool(claims) and all(
        c.get("kind") in ("OPINION", "SPECULATION", "RUMOR") for c in claims
    )
    date_conflict = bool(event.get("date_conflicts") or event.get("timeline_conflict"))
    if date_conflict:
        code, label, reason = (
            "date_conflict", "时间说法冲突 · 待核实",
            "同一事件存在不同发生日说法，应核对首次公告与独立资料"
        )
    elif official_correction:
        code, label, reason = (
            "correction_needs_review", "发现一手更正 · 旧结论需复核",
            "存在带原文引文的一手更正候选；仍需人工确认更正所针对的陈述"
        )
    elif has_correction:
        code, label, reason = (
            "correction_unverified", "出现更正说法 · 待核实",
            "已出现更正候选，但来源身份或更正对象尚未核实，不能视为已撤销原结论"
        )
    elif has_dispute:
        code, label, reason = (
            "disputed", "存在否认或异议 · 结论待定",
            "相关否认与异议已记录，但相互作用的对象和语义尚未完全核对"
        )
    elif official_fact:
        code, label, reason = (
            "primary_document", "存在一手事实陈述 · 需复核语义",
            "已定位一手来源的连续原文，不代表模型概括或全部事实已被证实"
        )
    elif only_opinion_or_rumor:
        code, label, reason = (
            "opinion_or_rumor", "仅有观点、推测或传闻",
            "没有通过当前分类获得的可独立核实的事实结论"
        )
    elif has_fact:
        code, label, reason = (
            "secondary_facts", "存在事实说法 · 需要一手核实",
            "当前只有二手或来源身份未验证的事实陈述"
        )
    else:
        code, label, reason = ("no_evidence", "尚无可核验证据", "没有可用于事件判断的原文")
    newest = max((docs[sid].get("disclosed_at")[:10] for sid in event.get("source_ids", [])
                  if docs.get(sid) and docs[sid].get("disclosed_at")), default=None)
    age_days = None
    if newest:
        try:
            age_days = (date.fromisoformat(as_of) - date.fromisoformat(newest)).days
        except (ValueError, TypeError):
            pass
    return {
        "status_code": code, "status_label": label, "reason": reason,
        "weight_rule": "来源层级 + 底层来源去重 + 逐字引文定位；不赋予虚构概率或机械多数票",
        "source_tiers": counts, "origin_groups": detail,
        "origin_count": len(grouped), "claim_count": len(claims),
        "latest_disclosure": newest, "disclosure_age_days": age_days,
        "freshness_note": ("距最新可核披露超过30天；若问题强调“最近”，需重新检索。" 
                           if age_days is not None and age_days > 30 else
                           "时效需按事件性质判断，不能以天数直接判真伪。"),
        "semantic_verified": False,
    }
