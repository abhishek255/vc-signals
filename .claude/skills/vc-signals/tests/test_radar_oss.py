from __future__ import annotations


def _candidate():
    from radar_models import Candidate

    return Candidate(
        name="affaan-m/agentshield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )


def test_oss_enrichment_uses_approved_action_vocabulary():
    from radar_oss import OSS_ACTIONS, enrich_oss_candidate

    candidate = enrich_oss_candidate(
        _candidate(),
        {
            "full_name": "affaan-m/agentshield",
            "url": "https://github.com/affaan-m/agentshield",
            "description": "AI agent security scanner for MCP servers",
            "stars": 1200,
            "velocity": {"stars_last_30d": 187},
            "license": "Apache-2.0",
            "topics": ["ai-agent", "security", "mcp"],
        },
    )

    assert candidate.action in OSS_ACTIONS
    assert candidate.action == "track company formation"
    assert candidate.oss_company_formation_score >= 70
    assert "+187 stars in 30d" in candidate.oss_action_reason


def test_oss_enrichment_preserves_repo_metadata_and_maintainer_profile():
    from radar_oss import enrich_oss_candidate

    candidate = enrich_oss_candidate(
        _candidate(),
        {
            "full_name": "affaan-m/agentshield",
            "url": "https://github.com/affaan-m/agentshield",
            "description": "AI agent security scanner",
            "stars": 320,
            "stars_30d": 54,
            "license": "MIT",
            "created_at": "2026-04-01T00:00:00Z",
        },
    )

    assert candidate.stars == 320
    assert candidate.stars_30d == 54
    assert candidate.license == "MIT"
    assert candidate.repo_age_days >= 0
    assert candidate.maintainer_profiles == [{"name": "affaan-m", "github": "https://github.com/affaan-m"}]


def test_oss_low_signal_maps_ecosystem_or_ignores():
    from radar_oss import enrich_oss_candidate

    candidate = enrich_oss_candidate(
        _candidate(),
        {
            "full_name": "unknown/tool",
            "url": "https://github.com/unknown/tool",
            "description": "Small helper script",
            "stars": 3,
            "stars_30d": 0,
        },
    )

    assert candidate.action in {"map ecosystem", "ignore"}
    assert candidate.oss_action_reason
