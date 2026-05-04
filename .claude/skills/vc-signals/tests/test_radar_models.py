def test_signal_roundtrip_dict():
    from radar_models import Signal

    signal = Signal(
        source="reddit",
        role="pain",
        title="Teams hate debugging flaky AI agents",
        url="https://reddit.com/r/devops/example",
        sector="devtools",
        theme="Agent reliability",
        text="Repeated complaints about flaky agent runs.",
        can_create_candidate=False,
        evidence_strength=35,
        reason="Reddit pain evidence should support themes, not directly create rows.",
    )

    assert Signal.from_dict(signal.to_dict()) == signal


def test_candidate_serializes_profile_fields():
    from radar_models import Candidate

    candidate = Candidate(
        name="AgentShield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        company_linkedin="",
        company_x="",
        founder_profiles=[{"name": "affaan-m", "github": "https://github.com/affaan-m"}],
    )

    payload = candidate.to_dict()
    assert payload["name"] == "AgentShield"
    assert payload["founder_profiles"][0]["github"] == "https://github.com/affaan-m"


def test_candidate_v3_fields_roundtrip_dict():
    from radar_models import Candidate

    candidate = Candidate(
        name="EvalForge",
        sector="ai-infra",
        theme="Agent evals",
        source="https://example.com/evalforge",
        candidate_type="company",
        market_sector="AI infrastructure",
        source_lane="launch",
        evidence_role="company",
        sector_confidence="High",
        sector_reason="Clear agent evaluation workflow and infra buyer.",
        partner_priority_score=84,
    )

    payload = candidate.to_dict()

    assert payload["market_sector"] == "AI infrastructure"
    assert payload["source_lane"] == "launch"
    assert payload["evidence_role"] == "company"
    assert payload["sector_confidence"] == "High"
    assert payload["sector_reason"] == "Clear agent evaluation workflow and infra buyer."
    assert payload["partner_priority_score"] == 84
    assert Candidate.from_dict(payload) == candidate


def test_theme_signal_roundtrip_dict():
    from radar_models import ThemeSignal

    signal = ThemeSignal(
        market_sector="Devtools",
        theme="Agent observability",
        source_lanes=["reddit_pain", "hn_discussion"],
        evidence_count=7,
        evidence_summary="Repeated complaints about debugging opaque agent runs.",
        why_it_matters="Agents need production-grade monitoring before broad deployment.",
        why_no_company_yet="The evidence is pain-heavy but not tied to a new company launch.",
        suggested_search="agent observability startup launch",
        confidence="Medium",
    )

    assert ThemeSignal.from_dict(signal.to_dict()) == signal


def test_sector_intelligence_roundtrip_dict():
    from radar_models import SectorIntelligence

    intelligence = SectorIntelligence(
        market_sector="Cybersecurity",
        status="Thin company formation, meaningful pain",
        raw_signals=18,
        candidate_eligible_signals=4,
        promoted_candidates=2,
        rejected_signals=12,
        best_evidence="Multiple teams report credential leakage from AI coding agents.",
        why_no_more_companies="Most evidence came from Reddit pain and generic guidance posts.",
        next_hunt="Search for AI agent permissioning launches and OSS repos.",
        source_errors=["HN timeout"],
    )

    assert SectorIntelligence.from_dict(intelligence.to_dict()) == intelligence
