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


def test_company_dossier_includes_source_specific_evidence_completion_plan_for_product_hunt():
    from company_dossier import build_company_dossier

    dossier = build_company_dossier(
        {
            "name": "AgentFence",
            "domain": "agentfence.dev",
            "website": "https://agentfence.dev",
            "source_lane": "Product Hunt",
            "product_hunt_url": "https://www.producthunt.com/products/agentfence",
            "tagline": "Permission firewall for AI agents",
            "maker_profiles": ["https://www.producthunt.com/@ada"],
            "votes_count": 321,
            "comments_count": 42,
            "action": "research deeper",
        }
    )

    assert dossier["source_context"]["role"] == "launch_source"
    assert dossier["source_context"]["product_hunt_url"] == "https://www.producthunt.com/products/agentfence"
    assert dossier["source_context"]["votes_count"] == 321
    assert dossier["manual_review_checklist"]
    plan_by_field = {item["field"]: item for item in dossier["evidence_completion_plan"]}
    assert plan_by_field["founder_team"]["status"] == "present"
    assert plan_by_field["commercial"]["status"] == "missing"
    assert any("Product Hunt maker" in source for source in plan_by_field["founder_team"]["where_to_check"])
    assert "promote_if_found" in plan_by_field["commercial"]
    assert dossier["promote_if_found"]
    assert dossier["discard_if_not_found"]


def test_company_dossier_treats_x_as_launch_radar_not_identity_truth():
    from company_dossier import build_company_dossier

    dossier = build_company_dossier(
        {
            "name": "BuildGraph",
            "source_lane": "X",
            "url": "https://x.com/founder/status/1",
            "company_x": "https://x.com/founder/status/1",
            "snippet": "Just launched BuildGraph for developer teams.",
            "launch_intent_score": 80,
            "launch_intent_basis": ["first_person_launch_language"],
            "action": "watch",
        }
    )

    assert dossier["source_context"]["role"] == "launch_radar"
    assert dossier["official_domain"] == ""
    assert "official_domain_missing" in dossier["missing_evidence"]
    assert any("official website" in check.lower() for check in dossier["manual_review_checklist"])
    assert "X can point to a launch" in dossier["source_context"]["identity_policy"]
