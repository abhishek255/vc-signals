from __future__ import annotations


def test_company_dossier_grades_partner_review_ready_company_without_stage_metadata():
    from company_dossier import build_company_dossier

    dossier = build_company_dossier(
        {
            "name": "AgentFence",
            "domain": "agentfence.dev",
            "website": "https://agentfence.dev",
            "source_lane": "Product Hunt",
            "weekly_tag": "NEW",
            "action": "research deeper",
            "tagline": "Permission firewall for AI agents",
            "maker_profiles": ["https://www.producthunt.com/@ada"],
            "source_outbound_urls": [
                "https://agentfence.dev",
                "https://agentfence.dev/about",
            ],
            "why_on_radar": "Launched a permission firewall for AI agents.",
        }
    )

    assert dossier["official_domain"] == "agentfence.dev"
    assert dossier["confidence_grade"] == "C"
    assert dossier["partner_review_ready"] is True
    assert dossier["strict_review_worthy_ready"] is False
    assert dossier["evidence_buckets"]["identity"]["status"] == "present"
    assert dossier["evidence_buckets"]["founder_team"]["status"] == "present"
    assert dossier["evidence_buckets"]["product"]["status"] == "present"
    assert dossier["evidence_buckets"]["commercial"]["status"] == "missing"
    assert "stage_funding_or_headcount_missing" in dossier["missing_evidence"]
    assert "commercial_or_customer_signal_missing" in dossier["missing_evidence"]
    assert any("stage" in check.lower() for check in dossier["recommended_manual_checks"])
    assert dossier["promote_if"]
    assert dossier["discard_if"]


def test_company_dossier_keeps_repo_only_rows_as_market_signals_not_companies():
    from company_dossier import build_company_dossier

    dossier = build_company_dossier(
        {
            "name": "builder/agent-ci",
            "domain": "github.com",
            "source_lane": "OSS",
            "source": "https://github.com/builder/agent-ci",
            "sources": ["https://github.com/builder/agent-ci"],
            "theme": "Devtools workflow automation",
            "stars": 900,
            "stars_30d": 120,
            "weekly_tag": "NEW",
            "action": "watch",
            "why_on_radar": "Fast-rising local GitHub Actions runner for AI coding agents.",
        }
    )

    assert dossier["route"] == "market_signal"
    assert dossier["official_domain"] == ""
    assert dossier["partner_review_ready"] is False
    assert dossier["strict_review_worthy_ready"] is False
    assert "official_domain_missing" in dossier["missing_evidence"]
    assert any("companies building around" in check.lower() for check in dossier["recommended_manual_checks"])
