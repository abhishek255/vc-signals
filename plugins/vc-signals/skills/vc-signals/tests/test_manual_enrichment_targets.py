from __future__ import annotations

from radar_models import Candidate


def test_linkedin_manual_targets_expose_missing_company_founder_and_headcount_evidence():
    from manual_enrichment_targets import build_manual_enrichment_targets

    candidate = Candidate(
        name="AgentForge",
        domain="agentforge.dev",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=1",
        candidate_type="launch",
        tier="Partner Review",
        investment_interest_score=82,
        evidence_confidence_score=70,
        action="research deeper",
    )

    targets = build_manual_enrichment_targets([candidate], limit=5)

    assert targets["summary"]["targets"] == 1
    assert targets["items"][0]["name"] == "AgentForge"
    assert targets["items"][0]["manual_sources"] == ["LinkedIn", "Crunchbase/Coresignal/PDL/Dealroom/Apollo-Clay"]
    assert "company_linkedin_missing" in targets["items"][0]["missing_evidence"]
    assert "founder_team_missing" in targets["items"][0]["missing_evidence"]
    assert "headcount_missing" in targets["items"][0]["missing_evidence"]
    assert "stage_or_funding_missing" in targets["items"][0]["missing_evidence"]


def test_manual_targets_preserve_existing_linkedin_and_founders():
    from manual_enrichment_targets import build_manual_enrichment_targets

    candidate = Candidate(
        name="AgentForge",
        domain="agentforge.dev",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://x.com/founder/status/1",
        candidate_type="social_launch",
        tier="Partner Review",
        investment_interest_score=82,
        evidence_confidence_score=70,
        company_linkedin="https://www.linkedin.com/company/agentforge",
        founder_profiles=[{"name": "Asha Rao", "linkedin": "https://www.linkedin.com/in/asharao", "x": ""}],
        headcount="12",
        stage="Seed",
    )

    targets = build_manual_enrichment_targets([candidate], limit=5)

    assert targets["summary"]["targets"] == 0
    assert targets["summary"]["excluded_complete_or_low_value"] == 1


def test_manual_targets_rank_only_high_value_rows_with_domains_and_gaps():
    from manual_enrichment_targets import build_manual_enrichment_targets

    high_value = Candidate(
        name="Coval",
        domain="coval.dev",
        sector="AI infra",
        theme="agent evals",
        source="https://www.ycombinator.com/companies/coval",
        candidate_type="company",
        tier="Watchlist",
        action="research deeper",
        owner_readiness_score=75,
        partner_priority_score=80,
        investment_interest_score=85,
        evidence_confidence_score=75,
        company_linkedin="https://www.linkedin.com/company/covaldev",
        founders=["Brooke Hopkins"],
    )
    no_domain = Candidate(
        name="Launch Noise",
        domain="",
        sector="AI infra",
        theme="agent evals",
        source="https://x.com/founder/status/1",
        candidate_type="social_launch",
        tier="Watchlist",
        action="research deeper",
        investment_interest_score=95,
        evidence_confidence_score=40,
    )
    context = Candidate(
        name="Category Anchor",
        domain="anchor.ai",
        sector="AI infra",
        theme="agent evals",
        source="https://anchor.ai",
        candidate_type="company",
        tier="Watchlist",
        action="monitor only",
        category_anchor=True,
        investment_interest_score=95,
        evidence_confidence_score=90,
    )

    targets = build_manual_enrichment_targets([no_domain, context, high_value], limit=5)

    assert targets["summary"]["targets"] == 1
    assert targets["summary"]["excluded_complete_or_low_value"] == 2
    assert targets["items"][0]["name"] == "Coval"
    assert targets["items"][0]["manual_sources"] == ["LinkedIn", "Crunchbase/Coresignal/PDL/Dealroom/Apollo-Clay"]
    assert "stage_or_funding_missing" in targets["items"][0]["missing_evidence"]
    assert "Domain required" in targets["summary"]["selection_policy"]
