def test_render_weekly_brief_includes_sector_gap_and_full_radar(tmp_path):
    from radar_models import Candidate, RejectedSignal, SectorCoverage
    from radar_render import render_weekly_brief

    candidates = [
        Candidate(
            name="AgentShield",
            sector="OSS",
            market_sector="Cybersecurity",
            source_lane="OSS",
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
    assert "## Run Summary" in markdown
    assert "## Partner Review" in markdown
    assert "## Full Radar" in markdown
    assert "| Company / Project | Market Sector | Source Lane | Theme | Tag | Stage | Raised | Headcount | Founders | Tier | Interest | Evidence | Attio | Attio Owner | Attio Last Touch | Attio URL | Staleness | Action | OSS Score | Action Reason | LinkedIn | X | Why On Radar | Why This May Be Noise | Best Source |" in markdown
    assert "| AgentShield | Cybersecurity | OSS | AI agent security | NEW | Seed | $4M | 12 | Asha Rao | Watchlist | Medium | Low | no_match | Michael | 2026-04-10T00:00:00Z | https://app.attio.com/marathon/companies/record/rec_1 | No MMP owner in Attio. | watch | 42 | +54 stars in 30d |" in markdown
    assert "## Faded Off Radar" in markdown
    assert "## Sector Intelligence" in markdown
    assert "## Themes With No Company Yet" in markdown
    assert "### data-infra" in markdown
    assert "Status: no qualified candidates" in markdown
    assert "## Sector Coverage" in markdown
    assert "_Compatibility view; see Sector Intelligence for the V3 market map._" in markdown
    assert "**data-infra: no qualified candidates**" in markdown
    assert "Only Reddit pain and GitHub issue noise" in markdown
    assert "## Weak Evidence / Rejected Summary" in markdown
    assert "- source_not_candidate_eligible: 1" in markdown


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
    assert "| Company / Project | Market Sector | Source Lane | Theme | Tag | Stage | Raised | Headcount | Founders | Tier | Interest | Evidence | Attio |" in markdown


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

    assert "OSS-heavy Partner Review" not in markdown
    assert "Warning: this run is OSS-heavy; non-OSS company discovery did not produce qualified rows." in markdown


def test_render_weekly_brief_falls_back_source_lane_for_legacy_rows():
    from radar_models import Candidate
    from radar_render import render_weekly_brief

    oss_candidate = Candidate(
        name="LegacyRepo",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/example/legacyrepo",
        candidate_type="oss_project",
        tier="Watchlist",
    )
    unknown_candidate = Candidate(
        name="LegacyCo",
        sector="Cybersecurity",
        market_sector="Cybersecurity",
        theme="MCP permissions",
        source="https://legacyco.example",
        candidate_type="company",
        tier="Watchlist",
    )

    markdown = render_weekly_brief([oss_candidate, unknown_candidate], {}, [])

    assert "| LegacyRepo | OSS | OSS | AI agent security |" in markdown
    assert "| LegacyCo | Cybersecurity | Unknown | MCP permissions |" in markdown


def test_run_summary_counts_rows_sectors_source_mix_and_warning_behavior():
    from radar_models import Candidate
    from radar_render import render_weekly_brief

    mixed_candidates = [
        Candidate(
            name="AgentShield",
            sector="OSS",
            market_sector="Cybersecurity",
            source_lane="OSS",
            theme="AI agent security",
            source="https://github.com/affaan-m/agentshield",
            candidate_type="oss_project",
            tier="Watchlist",
        ),
        Candidate(
            name="BuildGraph",
            sector="OSS",
            market_sector="Devtools",
            source_lane="OSS",
            theme="Build observability",
            source="https://github.com/example/buildgraph",
            candidate_type="oss_project",
            tier="Watchlist",
        ),
        Candidate(
            name="DataPilot",
            sector="Data Infra",
            market_sector="Data Infra",
            source_lane="Grounded Web",
            theme="Data lineage",
            source="https://datapilot.example",
            candidate_type="company",
            tier="Watchlist",
        ),
    ]

    mixed_markdown = render_weekly_brief(mixed_candidates, {}, [])

    assert "## Run Summary" in mixed_markdown
    assert "This run produced 3 qualified rows across 3 market sectors." in mixed_markdown
    assert "Source mix: 1 Grounded Web, 2 OSS." in mixed_markdown
    assert "Warning: this run is OSS-heavy; non-OSS company discovery did not produce qualified rows." not in mixed_markdown

    oss_markdown = render_weekly_brief(mixed_candidates[:2], {}, [])

    assert "This run produced 2 qualified rows across 2 market sectors." in oss_markdown
    assert "Source mix: 2 OSS." in oss_markdown
    assert "Warning: this run is OSS-heavy; non-OSS company discovery did not produce qualified rows." in oss_markdown


def test_render_weekly_brief_preserves_rejected_summary_and_needs_more_evidence():
    from radar_models import Candidate, RejectedSignal
    from radar_render import render_weekly_brief

    needs_more = Candidate(
        name="QuietCo",
        sector="AI Infra",
        market_sector="AI Infra",
        source_lane="HN/Launch",
        theme="Agent runtime",
        source="https://news.ycombinator.com/item?id=1",
        candidate_type="company",
        tier="Needs More Evidence",
        why_on_radar="Launch signal exists, but company evidence is thin.",
    )
    rejected = [
        RejectedSignal(sector="ai-infra", source="reddit", title="Pain 1", reason="source_not_candidate_eligible"),
        RejectedSignal(sector="ai-infra", source="github", title="Issue 1", reason="source_not_candidate_eligible"),
        RejectedSignal(sector="devtools", source="news", title="Digest", reason="generic_digest"),
    ]

    markdown = render_weekly_brief([needs_more], {}, rejected)

    assert "## Weak Evidence / Rejected Summary" in markdown
    assert "- generic_digest: 1" in markdown
    assert "- source_not_candidate_eligible: 2" in markdown
    assert "### Needs More Evidence" in markdown
    assert "- **QuietCo** (AI Infra): Launch signal exists, but company evidence is thin." in markdown


def test_render_weekly_brief_explains_sector_intelligence_and_themes():
    from radar_models import Candidate, SectorIntelligence, ThemeSignal
    from radar_render import render_weekly_brief

    candidate = Candidate(
        name="AgentShield",
        sector="OSS",
        market_sector="Cybersecurity",
        source_lane="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        weekly_tag="NEW",
        tier="Partner Review",
        investment_interest="High",
        evidence_confidence="Medium",
        attio_status="no_match",
        action="track company formation",
        why_on_radar="Fast OSS momentum.",
        why_this_may_be_noise="Repo may not become a company.",
    )
    intelligence = [
        SectorIntelligence(
            market_sector="Cybersecurity",
            status="OSS/project candidates found",
            raw_signals=12,
            candidate_eligible_signals=4,
            promoted_candidates=1,
            rejected_signals=8,
            best_evidence="1 promoted row from OSS.",
            why_no_more_companies="No verified company pages qualified.",
            next_hunt="AI agent security startups",
            source_errors=["Grounded web timed out."],
        )
    ]
    themes = [
        ThemeSignal(
            market_sector="Data Infra",
            theme="Data lineage",
            source_lanes=["Reddit"],
            evidence_count=2,
            evidence_summary="Teams complain about lineage gaps.",
            why_it_matters="Operator pain is recurring.",
            why_no_company_yet="No verified company/domain evidence.",
            suggested_search="data lineage AI startups",
            confidence="Medium",
        )
    ]

    markdown = render_weekly_brief(
        [candidate],
        {},
        [],
        partner_review=[candidate],
        sector_intelligence=intelligence,
        theme_signals=themes,
    )

    assert "## Run Summary" in markdown
    assert "## Sector Intelligence" in markdown
    assert "### Cybersecurity" in markdown
    assert "Status: OSS/project candidates found" in markdown
    assert "Signals: 12 raw, 4 candidate-eligible, 1 promoted, 8 rejected." in markdown
    assert "Best evidence: 1 promoted row from OSS." in markdown
    assert "Why no more companies: No verified company pages qualified." in markdown
    assert "Next hunt: AI agent security startups" in markdown
    assert "Source errors: Grounded web timed out." in markdown
    assert "## Themes With No Company Yet" in markdown
    assert "| Data Infra | Data lineage | Teams complain about lineage gaps. | Operator pain is recurring. | No verified company/domain evidence. | data lineage AI startups |" in markdown


def test_render_weekly_brief_has_clear_empty_theme_state():
    from radar_render import render_weekly_brief

    markdown = render_weekly_brief([], {}, [], theme_signals=[])

    assert "## Themes With No Company Yet" in markdown
    assert "- No meaningful non-company themes met the evidence bar." in markdown
