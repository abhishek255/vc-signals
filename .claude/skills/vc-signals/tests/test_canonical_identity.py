from __future__ import annotations


def _company_candidate(**overrides):
    from radar_models import Candidate

    data = {
        "name": "Take your AI agents to production, faster.",
        "sector": "AI Infra",
        "market_sector": "AI Infra",
        "theme": "Agent reliability and evals",
        "source": "https://www.lyzr.ai/",
        "sources": ["https://www.lyzr.ai/"],
        "candidate_type": "company_web",
        "domain": "lyzr.ai",
        "identity_type": "verified_company",
        "attio_status": "no_match",
        "attio_safe_to_match": True,
        "attio_match_keys": ["domain:lyzr.ai"],
        "maturity_status": "seed_to_series_b",
        "maturity_basis": ["seed_or_pre_seed"],
        "maturity_evidence_urls": ["https://www.lyzr.ai/"],
        "lead_route": "sourcing_candidate",
        "recommended_identity_action": "Assign owner",
        "recommended_owner_action": "Assign owner",
        "owner_readiness_score": 100,
        "owner_readiness_basis": [
            "verified_company_identity",
            "founder_team_evidence",
            "stage_funding_evidence",
            "customer_buyer_pull_evidence",
            "attio_new_or_no_match",
        ],
        "missing_owner_evidence": [],
        "founder_team_evidence": ["https://www.lyzr.ai/founders-corner/"],
        "founder_profiles": [
            {
                "name": "Siva Surendira",
                "role": "founder",
                "source": "https://www.lyzr.ai/founders-corner/",
            }
        ],
        "stage_funding_evidence": ["https://www.lyzr.ai/"],
        "customer_buyer_evidence": ["https://lyzr.ai/customers"],
        "why_on_radar": "Take your AI agents to production, faster.",
        "evidence_confidence_score": 60,
    }
    data.update(overrides)
    return Candidate(**data)


def test_domain_backed_tagline_normalizes_to_company_name():
    from canonical_identity import canonicalize_identity

    result = canonicalize_identity(
        name="Take your AI agents to production, faster.",
        domain="lyzr.ai",
        candidate_type="company_web",
        raw_title="Take your AI agents to production, faster.",
    )

    assert result["canonical_name"] == "Lyzr"
    assert result["display_name"] == "Lyzr"
    assert result["tagline"] == "Take your AI agents to production, faster."
    assert result["source_headline"] == "Take your AI agents to production, faster."


def test_github_repo_name_is_not_normalized_to_domain_stem():
    from canonical_identity import canonicalize_identity

    result = canonicalize_identity(
        name="redwoodjs/agent-ci",
        domain="agent-ci.dev",
        candidate_type="oss_project",
        identity_type="oss_with_commercial_intent",
    )

    assert result["display_name"] == "redwoodjs/agent-ci"
    assert result["canonical_name"] == "redwoodjs/agent-ci"
    assert result["tagline"] == ""


def test_title_with_domain_prefix_normalizes_to_domain_company_name():
    from canonical_identity import canonicalize_identity

    result = canonicalize_identity(
        name="n8n.io - AI workflow automation platform",
        domain="n8n.io",
        candidate_type="company_web",
        raw_title="n8n.io - AI workflow automation platform",
    )

    assert result["display_name"] == "n8n"
    assert result["canonical_name"] == "n8n"


def test_focus_item_displays_canonical_company_name_and_preserves_tagline():
    from radar_focus import ACTION_ASSIGN_OWNER, build_focus_item

    item = build_focus_item(_company_candidate())

    assert item.name == "Lyzr"
    assert item.display_name == "Lyzr"
    assert item.canonical_name == "Lyzr"
    assert item.tagline == "Take your AI agents to production, faster."
    assert item.source_headline == "Take your AI agents to production, faster."
    assert item.why_focus_this_week == "Take your AI agents to production, faster."
    assert item.recommended_action == ACTION_ASSIGN_OWNER


def test_no_assign_owner_focus_item_displays_tagline_like_name():
    from canonical_identity import is_tagline_like_name
    from radar_focus import ACTION_ASSIGN_OWNER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(candidates=[_company_candidate()], run_id="2026-05-09")

    assert artifact.sourcing_candidates[0].recommended_action == ACTION_ASSIGN_OWNER
    assert artifact.sourcing_candidates[0].name == "Lyzr"
    assert not is_tagline_like_name(artifact.sourcing_candidates[0].name)


def test_discovery_lead_uses_domain_name_when_official_page_title_is_tagline():
    from radar_company_discovery import verify_discovery_item

    lead = verify_discovery_item(
        {
            "source": "grounding",
            "title": "Take your AI agents to production, faster.",
            "url": "https://www.lyzr.ai/",
            "snippet": "Lyzr helps teams get AI agents into production.",
        },
        {
            "movement": "Agent reliability and evals",
            "market_sector": "AI Infra",
            "required_terms": ["ai agent"],
        },
    )

    assert lead.name == "Lyzr"
    assert lead.canonical_name == "Lyzr"
    assert lead.display_name == "Lyzr"
    assert lead.tagline == "Take your AI agents to production, faster."
    assert lead.raw_title == "Take your AI agents to production, faster."
