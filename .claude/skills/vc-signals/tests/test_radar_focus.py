from radar_models import Candidate, FocusItem


def _candidate(**overrides):
    data = {
        "name": "AgentShield",
        "sector": "Cybersecurity",
        "market_sector": "Cybersecurity",
        "theme": "AI agent permission security",
        "source": "https://github.com/affaan-m/agentshield",
        "candidate_type": "oss_project",
        "why_on_radar": "AI agent security scanner with MCP permissions focus.",
        "why_this_may_be_noise": "Commercial intent needs verification.",
        "sources": ["https://github.com/affaan-m/agentshield"],
        "source_count": 1,
        "investment_interest_score": 70,
        "evidence_confidence_score": 50,
        "attio_status": "unknown",
        "weekly_tag": "NEW",
        "maintainer_profiles": [{"name": "affaan-m"}],
        "oss_company_formation_score": 60,
    }
    data.update(overrides)
    return Candidate(**data)


def test_company_identity_score_records_basis_and_missing_evidence():
    from radar_focus import score_company_identity

    score, basis, missing = score_company_identity(_candidate(domain="agentshield.dev"))

    assert score >= 80
    assert "domain_present" in basis
    assert "evidence_urls_present" in basis
    assert "no verified company domain" not in missing


def test_partner_focus_requires_evidence_url_and_identity_quality():
    from radar_focus import is_partner_focus_eligible

    item = FocusItem(
        id="weak",
        name="Weak Project",
        company_identity_quality_score=40,
        evidence_urls=[],
        noise_risk_score=30,
        recommended_action="Research deeper",
        focus_priority_basis=["focus_formula_v1"],
        project_url="https://github.com/example/weak",
    )

    assert is_partner_focus_eligible(item) is False


def test_partner_focus_accepts_credible_actionable_project():
    from radar_focus import is_partner_focus_eligible

    item = FocusItem(
        id="agentshield",
        name="AgentShield",
        company_identity_quality_score=60,
        evidence_urls=["https://github.com/affaan-m/agentshield"],
        noise_risk_score=45,
        recommended_action="Research deeper",
        focus_priority_basis=["focus_formula_v1"],
        project_url="https://github.com/affaan-m/agentshield",
    )

    assert is_partner_focus_eligible(item) is True


def test_take_meeting_gate_is_strict():
    from radar_focus import ACTION_TAKE_MEETING, can_take_meeting, choose_recommended_action

    candidate = _candidate(domain="agentshield.dev", evidence_confidence_score=74)
    item = FocusItem(
        id="agentshield",
        evidence_confidence_score=74,
        company_identity_quality_score=90,
        actionability_score=90,
        noise_risk_score=20,
        attio_status="unknown",
    )

    assert can_take_meeting(item) is False
    assert choose_recommended_action(candidate, item) != ACTION_TAKE_MEETING


def test_take_meeting_blocked_when_attio_unknown_even_when_scores_clear():
    from radar_focus import ACTION_TAKE_MEETING, can_take_meeting, choose_recommended_action

    candidate = _candidate(domain="agentshield.dev", evidence_confidence_score=85)
    item = FocusItem(
        id="agentshield",
        evidence_confidence_score=85,
        company_identity_quality_score=90,
        actionability_score=90,
        noise_risk_score=20,
        attio_status="unknown",
    )

    assert can_take_meeting(item) is False
    assert choose_recommended_action(candidate, item) != ACTION_TAKE_MEETING


def test_take_meeting_allowed_when_all_gates_clear_and_attio_known():
    from radar_focus import ACTION_TAKE_MEETING, can_take_meeting, choose_recommended_action

    candidate = _candidate(
        domain="agentshield.dev",
        attio_status="no_match",
        evidence_confidence_score=85,
    )
    item = FocusItem(
        id="agentshield",
        evidence_confidence_score=85,
        company_identity_quality_score=90,
        actionability_score=90,
        noise_risk_score=20,
        attio_status="no_match",
    )

    assert can_take_meeting(item) is True
    assert choose_recommended_action(candidate, item) == ACTION_TAKE_MEETING


def test_build_focus_item_includes_basis_missing_evidence_and_action():
    from radar_focus import build_focus_item

    item = build_focus_item(_candidate(domain="", attio_status="unknown"))

    assert item.name == "AgentShield"
    assert item.market_movement == "AI agent permission security"
    assert item.company_identity_quality_basis
    assert item.actionability_basis
    assert item.focus_priority_basis == ["focus_formula_v1"]
    assert "no verified company domain" in item.missing_evidence
    assert item.recommended_action in {"Assign owner", "Research deeper", "Refresh Attio", "Monitor only"}


def test_build_focus_item_uses_attio_stale_for_refresh_action():
    from radar_focus import ACTION_REFRESH_ATTIO, build_focus_item

    item = build_focus_item(
        _candidate(
            domain="agentshield.dev",
            attio_status="stale",
            attio_staleness_reason="No interaction in 180 days",
        )
    )

    assert item.recommended_action == ACTION_REFRESH_ATTIO
    assert "attio_stale_with_new_signal" in item.actionability_basis


def test_unknown_attio_status_is_not_new_to_marathon_or_assign_owner():
    from radar_focus import ACTION_ASSIGN_OWNER, ACTION_MONITOR_ONLY, ACTION_RESEARCH_DEEPER, build_focus_item

    item = build_focus_item(
        _candidate(
            domain="",
            sources=["https://github.com/affaan-m/agentshield"],
            attio_status="unknown",
            attio_owner="",
            evidence_confidence_score=50,
            maintainer_profiles=[{"name": "affaan-m"}],
            oss_company_formation_score=60,
        )
    )

    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert item.recommended_action != ACTION_ASSIGN_OWNER
    assert item.recommended_action != ACTION_MONITOR_ONLY
    assert "new_to_attio" not in item.actionability_basis
