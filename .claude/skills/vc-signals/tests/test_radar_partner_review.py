from __future__ import annotations


def _candidate(
    name,
    market_sector,
    source_lane,
    score=70,
    evidence=50,
    tier="Watchlist",
    *,
    weekly_tag="",
    action="watch",
    attio_status="unknown",
    attio_action="",
    oss_score=0,
):
    from radar_models import Candidate

    return Candidate(
        name=name,
        sector=market_sector,
        market_sector=market_sector,
        source_lane=source_lane,
        theme="Agent security",
        source=f"https://example.com/{name}",
        candidate_type="oss_project" if source_lane == "OSS" else "company_web",
        investment_interest_score=score,
        evidence_confidence_score=evidence,
        investment_interest="High" if score >= 70 else "Medium",
        evidence_confidence="Medium",
        tier=tier,
        weekly_tag=weekly_tag,
        action=action,
        attio_status=attio_status,
        attio_action=attio_action,
        oss_company_formation_score=oss_score,
    )


def test_partner_review_returns_10_to_15_rows_when_available():
    from radar_partner_review import select_partner_review

    candidates = [_candidate(f"Company {i}", "Cybersecurity", "Grounded web", 80 - i, 60) for i in range(20)]

    partner = select_partner_review(candidates, min_rows=10, max_rows=15)

    assert 10 <= len(partner) <= 15
    assert all(item.partner_priority_score > 0 for item in partner)


def test_partner_review_caps_oss_when_other_sources_exist():
    from radar_partner_review import select_partner_review

    candidates = []
    candidates.extend(_candidate(f"OSS {i}", "Cybersecurity", "OSS", 90 - i, 70, oss_score=80) for i in range(12))
    candidates.extend(_candidate(f"Web {i}", "Devtools", "Grounded web", 70 - i, 60) for i in range(6))

    partner = select_partner_review(candidates, min_rows=10, max_rows=15, max_oss_rows=5)

    assert sum(1 for item in partner if item.source_lane == "OSS") <= 5
    assert any(item.source_lane == "Grounded web" for item in partner)


def test_partner_review_does_not_use_fallback_to_pad_with_oss_when_min_is_met():
    from radar_partner_review import select_partner_review

    candidates = []
    candidates.extend(_candidate(f"OSS {i}", "Cybersecurity", "OSS", 90 - i, 70, oss_score=80) for i in range(12))
    candidates.extend(_candidate(f"Web {i}", "Devtools", "Grounded web", 70 - i, 60) for i in range(6))

    partner = select_partner_review(candidates, min_rows=10, max_rows=15, max_oss_rows=5)

    assert len(partner) >= 10
    assert sum(1 for item in partner if item.source_lane == "OSS") <= 5


def test_partner_review_only_exceeds_oss_cap_enough_to_reach_min_rows():
    from radar_partner_review import select_partner_review

    candidates = []
    candidates.extend(_candidate(f"OSS {i}", "Cybersecurity", "OSS", 90 - i, 70, oss_score=80) for i in range(12))
    candidates.extend(_candidate(f"Web {i}", "Devtools", "Grounded web", 70 - i, 60) for i in range(4))

    partner = select_partner_review(candidates, min_rows=10, max_rows=15, max_oss_rows=5)

    assert len(partner) == 10
    assert sum(1 for item in partner if item.source_lane == "OSS") == 6


def test_partner_review_allows_oss_heavy_when_no_alternative_exists():
    from radar_partner_review import select_partner_review

    candidates = [_candidate(f"OSS {i}", "Cybersecurity", "OSS", 90 - i, 70, oss_score=80) for i in range(12)]

    partner = select_partner_review(candidates, min_rows=10, max_rows=15, max_oss_rows=5)

    assert len(partner) == 12
    assert sum(1 for item in partner if item.source_lane == "OSS") == 12


def test_partner_priority_rewards_review_ready_and_penalizes_late_unclassified():
    from radar_partner_review import compute_partner_priority

    ready = _candidate(
        "ReadyCo",
        "AI Infra",
        "Grounded web",
        72,
        70,
        tier="Partner Review",
        weekly_tag="NEW",
        attio_status="no_owner",
        action="assign owner",
    )
    late_unclassified = _candidate(
        "LateCo",
        "Unclassified",
        "Grounded web",
        72,
        70,
        tier="Partner Review",
        weekly_tag="NEW",
        attio_status="no_owner",
        action="likely too late",
    )

    assert compute_partner_priority(ready) > compute_partner_priority(late_unclassified)
    assert compute_partner_priority(late_unclassified) >= 0


def test_partner_priority_uses_attio_action_even_when_action_is_default():
    from radar_partner_review import compute_partner_priority

    default_action = _candidate("DefaultAction", "AI Infra", "Grounded web", 60, 50, action="watch")
    attio_owner = _candidate(
        "AttioOwner",
        "AI Infra",
        "Grounded web",
        60,
        50,
        action="watch",
        attio_action="assign owner",
    )

    assert compute_partner_priority(attio_owner) > compute_partner_priority(default_action)


def test_partner_review_prefers_sector_diversity_before_filling_remaining_slots():
    from radar_partner_review import select_partner_review

    candidates = [_candidate(f"Cyber {i}", "Cybersecurity", "Grounded web", 95 - i, 70) for i in range(14)]
    candidates.append(_candidate("DataInfra", "Data Infra", "Grounded web", 55, 45))

    partner = select_partner_review(candidates, min_rows=10, max_rows=10)

    assert "Data Infra" in {item.market_sector for item in partner}
