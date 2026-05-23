def test_high_interest_low_confidence_becomes_watchlist_not_filtered():
    from radar_models import Candidate
    from radar_scoring import score_and_tier

    candidate = Candidate(
        name="AgentShield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        why_on_radar="AI agent security scanner for MCP servers. +184 stars in 30d.",
        source_count=1,
    )

    scored = score_and_tier(candidate)
    assert scored.investment_interest_score >= 45
    assert scored.tier in {"Watchlist", "Needs More Evidence"}


def test_partner_review_requires_interest_and_evidence():
    from radar_models import Candidate
    from radar_scoring import score_and_tier

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://runcandidate.example",
        candidate_type="company_web",
        domain="beesafe.ai",
        why_on_radar="Company page, HN launch, and GitHub repo all point to voice phishing defense for banks.",
        source_count=3,
        company_linkedin="https://www.linkedin.com/company/beesafe-ai",
    )

    scored = score_and_tier(candidate)
    assert scored.evidence_confidence_score >= 45
    assert scored.tier in {"Partner Review", "Watchlist"}


def test_needs_more_evidence_is_preserved_for_markdown_and_json():
    from radar_models import Candidate
    from radar_scoring import score_and_tier

    candidate = Candidate(
        name="LineageWatch",
        sector="Data Infrastructure",
        theme="Data lineage",
        source="https://reddit.com/r/dataengineering/example",
        candidate_type="theme_probe",
        why_on_radar="Repeated Reddit pain around lineage and schema drift, but no verified company yet.",
        source_count=1,
    )

    scored = score_and_tier(candidate)
    assert scored.tier == "Needs More Evidence"
    assert scored.evidence_confidence in {"Low", "Needs More Evidence"}


def test_low_evidence_candidate_action_is_demoted_from_assign_owner():
    from radar_models import Candidate
    from radar_scoring import score_and_tier

    candidate = Candidate(
        name="Zencoder",
        sector="Devtools",
        theme="Devtools OSS workflow tooling",
        source="https://zencoder.ai/",
        candidate_type="company_web",
        domain="zencoder.ai",
        why_on_radar="Zencoder | The AI Coding Agent",
        source_count=1,
        action="assign owner",
    )

    scored = score_and_tier(candidate)

    assert scored.evidence_confidence == "Low"
    assert scored.tier == "Needs More Evidence"
    assert scored.action == "research deeper"
