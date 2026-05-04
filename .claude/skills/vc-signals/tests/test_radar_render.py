def test_render_weekly_brief_includes_sector_gap_and_full_radar(tmp_path):
    from radar_models import Candidate, RejectedSignal, SectorCoverage
    from radar_render import render_weekly_brief

    candidates = [
        Candidate(
            name="AgentShield",
            sector="OSS",
            theme="AI agent security",
            source="https://github.com/affaan-m/agentshield",
            candidate_type="oss_project",
            tier="Watchlist",
            investment_interest="Medium",
            evidence_confidence="Low",
            attio_status="no_match",
            action="watch",
            why_on_radar="+184 stars in 30d.",
            why_this_may_be_noise="Repo traction may not map to company formation.",
        )
    ]
    coverage = {
        "data-infra": SectorCoverage(
            sector="data-infra",
            raw_signals=3,
            candidates=0,
            rejected=3,
            status="no qualified candidates",
            reason="Only Reddit pain and GitHub issue noise; no company/domain/founder evidence.",
        )
    }
    rejected = [RejectedSignal(sector="data-infra", source="reddit", title="What are people using?", reason="source_not_candidate_eligible")]

    markdown = render_weekly_brief(candidates, coverage, rejected)
    assert "## Partner Review" in markdown
    assert "## Full Radar" in markdown
    assert "## Sector Coverage" in markdown
    assert "data-infra: no qualified candidates" in markdown
    assert "Only Reddit pain and GitHub issue noise" in markdown
