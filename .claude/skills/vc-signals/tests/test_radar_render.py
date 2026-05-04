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
            weekly_tag="NEW",
            stage="Seed",
            raised="$4M",
            headcount="12",
            founders=["Asha Rao"],
            tier="Watchlist",
            investment_interest="Medium",
            evidence_confidence="Low",
            attio_status="no_match",
            attio_owner="Michael",
            attio_last_interaction="2026-04-10T00:00:00Z",
            attio_record_url="https://app.attio.com/marathon/companies/record/rec_1",
            attio_staleness_reason="No MMP owner in Attio.",
            action="watch",
            oss_company_formation_score=42,
            oss_action_reason="+54 stars in 30d",
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
    assert "| Company / Project | Sector | Theme | Tag | Stage | Raised | Headcount | Founders | Tier | Interest | Evidence | Attio | Attio Owner | Attio Last Touch | Attio URL | Staleness | Action | OSS Score | Action Reason | LinkedIn | X | Why On Radar | Why This May Be Noise | Best Source |" in markdown
    assert "| AgentShield | OSS | AI agent security | NEW | Seed | $4M | 12 | Asha Rao | Watchlist | Medium | Low | no_match | Michael | 2026-04-10T00:00:00Z | https://app.attio.com/marathon/companies/record/rec_1 | No MMP owner in Attio. | watch | 42 | +54 stars in 30d |" in markdown
    assert "## Faded Off Radar" in markdown
    assert "## Sector Coverage" in markdown
    assert "data-infra: no qualified candidates" in markdown
    assert "Only Reddit pain and GitHub issue noise" in markdown


def test_render_weekly_brief_includes_faded_candidates():
    from radar_render import render_weekly_brief

    markdown = render_weekly_brief(
        [],
        {},
        [],
        faded=[
            {
                "name": "OldCo",
                "sector": "ai-infra",
                "theme": "Agent runtime",
                "last_seen": "2026-04-27",
                "source": "https://oldco.ai",
                "weekly_tag": "FADED",
            }
        ],
    )

    assert "| OldCo | ai-infra | Agent runtime | FADED | 2026-04-27 | https://oldco.ai |" in markdown


def test_partner_review_uses_compact_market_sector_source_lane_columns():
    from radar_models import Candidate
    from radar_render import render_weekly_brief

    candidate = Candidate(
        name="AgentShield",
        sector="Cybersecurity",
        market_sector="Cybersecurity",
        source_lane="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        tier="Watchlist",
        investment_interest="High",
        evidence_confidence="Medium",
        attio_status="no_match",
        action="track company formation",
        why_on_radar="Fast OSS momentum.",
        why_this_may_be_noise="Repo may not become a company.",
    )

    markdown = render_weekly_brief([candidate], {}, [], partner_review=[candidate])

    assert "| Company / Project | Market Sector | Source Lane | Theme | Tag | Tier | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise |" in markdown
    assert "| AgentShield | Cybersecurity | OSS | AI agent security |" in markdown
    assert "| Company / Project | Sector | Theme | Tag | Stage | Raised | Headcount | Founders | Tier | Interest | Evidence | Attio |" in markdown


def test_partner_review_renders_oss_heavy_warning():
    from radar_models import Candidate
    from radar_render import render_weekly_brief

    candidates = [
        Candidate(
            name=f"OSS {i}",
            sector="Cybersecurity",
            market_sector="Cybersecurity",
            source_lane="OSS",
            theme="AI agent security",
            source=f"https://github.com/example/{i}",
            candidate_type="oss_project",
            tier="Watchlist",
        )
        for i in range(6)
    ]

    markdown = render_weekly_brief(candidates, {}, [], partner_review=candidates)

    assert "OSS-heavy Partner Review" in markdown
