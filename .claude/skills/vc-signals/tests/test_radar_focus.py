from radar_models import Candidate, FocusItem


def _candidate(**overrides):
    data = {
        "name": "AgentShield",
        "sector": "Cybersecurity",
        "market_sector": "Cybersecurity",
        "theme": "AI agent permission security",
        "source": "https://github.com/affaan-m/agentshield",
        "candidate_type": "oss_project",
        "why_on_radar": "AI agent security scanner with MCP permissions focus.",
        "why_this_may_be_noise": "Commercial intent needs verification.",
        "sources": ["https://github.com/affaan-m/agentshield"],
        "source_count": 1,
        "investment_interest_score": 70,
        "evidence_confidence_score": 50,
        "attio_status": "unknown",
        "weekly_tag": "NEW",
        "maintainer_profiles": [{"name": "affaan-m"}],
        "oss_company_formation_score": 60,
    }
    data.update(overrides)
    return Candidate(**data)


def test_company_identity_score_records_basis_and_missing_evidence():
    from radar_focus import score_company_identity

    score, basis, missing = score_company_identity(_candidate(domain="agentshield.dev"))

    assert score >= 80
    assert "domain_present" in basis
    assert "evidence_urls_present" in basis
    assert "no verified company domain" not in missing


def test_consensus_risk_accepts_numeric_enrichment_fields():
    from radar_focus import score_consensus_risk

    score, basis = score_consensus_risk(
        _candidate(
            stage="Seed",
            raised=4000000,
            headcount=12,
            why_on_radar="Seed-stage AI security product.",
        )
    )

    assert score >= 0
    assert basis


def test_attio_no_match_does_not_create_company_identity_by_itself():
    from radar_focus import score_company_identity

    score, basis, missing = score_company_identity(
        _candidate(
            name="A",
            domain="",
            attio_status="no_match",
            candidate_type="company_web",
            founder_profiles=[],
            founders=[],
            maintainer_profiles=[],
            oss_company_formation_score=0,
        )
    )

    assert score < 60
    assert "attio_status_present" not in basis
    assert "weak_candidate_name" in basis
    assert "weak candidate name" in missing


def test_partner_focus_requires_evidence_url_and_identity_quality():
    from radar_focus import is_partner_focus_eligible

    item = FocusItem(
        id="weak",
        name="Weak Project",
        company_identity_quality_score=40,
        evidence_urls=[],
        noise_risk_score=30,
        recommended_action="Research deeper",
        focus_priority_basis=["focus_formula_v1"],
        project_url="https://github.com/example/weak",
    )

    assert is_partner_focus_eligible(item) is False


def test_partner_focus_accepts_credible_actionable_project():
    from radar_focus import is_partner_focus_eligible

    item = FocusItem(
        id="agentshield",
        name="AgentShield",
        company_identity_quality_score=60,
        evidence_urls=["https://github.com/affaan-m/agentshield"],
        noise_risk_score=45,
        recommended_action="Research deeper",
        focus_priority_basis=["focus_formula_v1"],
        project_url="https://github.com/affaan-m/agentshield",
    )

    assert is_partner_focus_eligible(item) is True


def test_take_meeting_gate_is_strict():
    from radar_focus import ACTION_TAKE_MEETING, can_take_meeting, choose_recommended_action

    candidate = _candidate(domain="agentshield.dev", evidence_confidence_score=74)
    item = FocusItem(
        id="agentshield",
        evidence_confidence_score=74,
        company_identity_quality_score=90,
        actionability_score=90,
        noise_risk_score=20,
        attio_status="unknown",
    )

    assert can_take_meeting(item) is False
    assert choose_recommended_action(candidate, item) != ACTION_TAKE_MEETING


def test_take_meeting_blocked_when_attio_unknown_even_when_scores_clear():
    from radar_focus import ACTION_TAKE_MEETING, can_take_meeting, choose_recommended_action

    candidate = _candidate(domain="agentshield.dev", evidence_confidence_score=85)
    item = FocusItem(
        id="agentshield",
        evidence_confidence_score=85,
        company_identity_quality_score=90,
        actionability_score=90,
        noise_risk_score=20,
        attio_status="unknown",
    )

    assert can_take_meeting(item) is False
    assert choose_recommended_action(candidate, item) != ACTION_TAKE_MEETING


def test_take_meeting_allowed_when_all_gates_clear_and_attio_known():
    from radar_focus import ACTION_TAKE_MEETING, can_take_meeting, choose_recommended_action

    candidate = _candidate(
        domain="agentshield.dev",
        attio_status="no_match",
        evidence_confidence_score=85,
    )
    item = FocusItem(
        id="agentshield",
        evidence_confidence_score=85,
        company_identity_quality_score=90,
        actionability_score=90,
        noise_risk_score=20,
        attio_status="no_match",
    )

    assert can_take_meeting(item) is True
    assert choose_recommended_action(candidate, item) == ACTION_TAKE_MEETING


def test_build_focus_item_includes_basis_missing_evidence_and_action():
    from radar_focus import build_focus_item

    item = build_focus_item(_candidate(domain="", attio_status="unknown"))

    assert item.name == "AgentShield"
    assert item.market_movement == "AI agent permission security"
    assert item.company_identity_quality_basis
    assert item.actionability_basis
    assert item.focus_priority_basis == ["focus_formula_v1"]
    assert "no verified company domain" in item.missing_evidence
    assert item.recommended_action in {"Assign owner", "Research deeper", "Refresh Attio", "Monitor only"}


def test_build_focus_item_uses_concrete_fallback_instead_of_emerging_technical_signal():
    from radar_focus import build_focus_item

    item = build_focus_item(
        _candidate(
            sector="Devtools",
            market_sector="Devtools",
            theme="Emerging technical signal",
            why_on_radar="Agent-CI is local GitHub Actions for your agents.",
        )
    )

    assert item.market_movement == "Devtools workflow automation"


def test_build_focus_item_requires_agent_evidence_for_ai_agent_security_assignment():
    from radar_focus import build_focus_item

    item = build_focus_item(
        _candidate(
            name="slowql/slowql",
            sector="Devtools",
            market_sector="Devtools",
            theme="AI agent security",
            why_on_radar="SQL static analyzer for performance, security, compliance and cost. 272 rules. Completely offline.",
            sources=["https://github.com/slowql/slowql"],
        )
    )

    assert item.market_movement == "Devtools security/compliance tooling"
    assert item.market_movement != "AI agent security"


def test_build_focus_item_uses_attio_stale_for_refresh_action():
    from radar_focus import ACTION_REFRESH_ATTIO, build_focus_item

    item = build_focus_item(
        _candidate(
            domain="agentshield.dev",
            attio_status="stale",
            attio_staleness_reason="No interaction in 180 days",
        )
    )

    assert item.recommended_action == ACTION_REFRESH_ATTIO
    assert "attio_stale_with_new_signal" in item.actionability_basis


def test_unknown_attio_status_is_not_new_to_marathon_or_assign_owner():
    from radar_focus import ACTION_ASSIGN_OWNER, ACTION_MONITOR_ONLY, ACTION_RESEARCH_DEEPER, build_focus_item

    item = build_focus_item(
        _candidate(
            domain="",
            sources=["https://github.com/affaan-m/agentshield"],
            attio_status="unknown",
            attio_owner="",
            evidence_confidence_score=50,
            maintainer_profiles=[{"name": "affaan-m"}],
            oss_company_formation_score=60,
        )
    )

    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert item.recommended_action != ACTION_ASSIGN_OWNER
    assert item.recommended_action != ACTION_MONITOR_ONLY
    assert "new_to_attio" not in item.actionability_basis


def test_build_weekly_focus_artifact_splits_focus_watchlist_and_limits_rows():
    from radar_focus import build_weekly_focus_artifact

    candidates = [
        _candidate(
            name=f"Company {i}",
            stable_key=f"company-{i}",
            domain=f"company{i}.com",
            sources=[f"https://company{i}.com"],
            evidence_confidence_score=70,
            investment_interest_score=70 - i,
        )
        for i in range(20)
    ]

    artifact = build_weekly_focus_artifact(candidates=candidates, run_id="2026-05-11")

    assert len(artifact.partner_focus) <= 15
    assert len(artifact.extended_watchlist) <= 15
    assert artifact.run_id == "2026-05-11"
    assert artifact.executive_snapshot.top_movement


def test_weekly_focus_snapshot_counts_and_research_queue_note():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="RepoOnly",
                stable_key="repo-only",
                domain="",
                sources=["https://github.com/example/repo-only"],
                evidence_confidence_score=50,
                investment_interest_score=50,
                attio_status="unknown",
            ),
            _candidate(
                name="LaunchCo",
                stable_key="launch-co",
                domain="",
                source="https://launch.example/launchco",
                sources=["https://launch.example/launchco"],
                candidate_type="company_web",
                founder_profiles=[],
                founders=[],
                maintainer_profiles=[],
                evidence_confidence_score=30,
                investment_interest_score=80,
                attio_status="no_match",
            ),
        ],
        run_id="2026-05-11",
    )

    assert artifact.executive_snapshot.partner_focus_rows == len(artifact.partner_focus)
    assert artifact.executive_snapshot.oss_project_only_rows == 1
    assert artifact.executive_snapshot.company_or_launch_style_rows == 1
    assert artifact.executive_snapshot.readiness_note == "This run produced a research queue, not owner-ready leads."
    assert artifact.executive_snapshot.top_identity_resolution_target == "LaunchCo"


def test_build_weekly_focus_artifact_caps_project_only_rows():
    from radar_focus import build_weekly_focus_artifact

    candidates = [
        _candidate(
            name=f"Repo {i}",
            stable_key=f"repo-{i}",
            domain="",
            sources=[f"https://github.com/example/repo-{i}"],
            maintainer_profiles=[{"name": f"maintainer-{i}"}],
            oss_company_formation_score=65,
            evidence_confidence_score=60,
            investment_interest_score=80 - i,
        )
        for i in range(10)
    ]

    artifact = build_weekly_focus_artifact(candidates=candidates, run_id="2026-05-11")
    project_only = [item for item in artifact.partner_focus if item.project_url and not item.company_domain]

    assert len(project_only) <= 5


def test_new_to_marathon_and_workflow_view_use_attio_context():
    from radar_focus import ACTION_REFRESH_ATTIO, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="NewCo",
                stable_key="newco",
                domain="new.co",
                sources=["https://new.co"],
                attio_status="no_match",
                evidence_confidence_score=75,
            ),
            _candidate(
                name="KnownCo",
                stable_key="knownco",
                domain="known.co",
                sources=["https://known.co"],
                attio_status="stale",
                attio_staleness_reason="No interaction in 180 days",
                evidence_confidence_score=75,
            ),
        ],
        run_id="2026-05-11",
    )

    assert artifact.new_to_marathon[0].name == "NewCo"
    assert ACTION_REFRESH_ATTIO in artifact.workflow_view


def test_unknown_attio_does_not_populate_new_to_marathon():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="UnknownAttioCo",
                stable_key="unknown-attio-co",
                domain="unknownattio.co",
                sources=["https://unknownattio.co"],
                attio_status="unknown",
                evidence_confidence_score=70,
            )
        ],
        run_id="2026-05-11",
    )

    assert all(item.attio_status != "unknown" for item in artifact.new_to_marathon)


def test_extended_watchlist_excludes_noisy_leftovers():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="GoodCo",
                stable_key="goodco",
                domain="good.co",
                sources=["https://good.co"],
                evidence_confidence_score=75,
            ),
            _candidate(
                name="NoisyCo",
                stable_key="noisyco",
                domain="",
                source="",
                sources=[],
                evidence_confidence_score=20,
                why_this_may_be_noise="No company identity and no source evidence.",
            ),
        ],
        run_id="2026-05-11",
    )

    assert all(item.name != "NoisyCo" for item in artifact.extended_watchlist)
    assert any(row["name"] == "NoisyCo" for row in artifact.appendix["filtered_or_noisy"])


def test_consumer_gaming_automation_does_not_enter_partner_focus():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="Ronchy2000/epic-freebies-helper",
                stable_key="epic-freebies-helper",
                domain="",
                sources=["https://github.com/Ronchy2000/epic-freebies-helper"],
                why_on_radar="Automatically claim Epic Games weekly free titles with GitHub Actions and GLM-powered captcha solving.",
                evidence_confidence_score=40,
                investment_interest_score=50,
            )
        ],
        run_id="2026-05-11",
    )

    assert all(item.name != "Ronchy2000/epic-freebies-helper" for item in artifact.partner_focus)
    assert any(row["name"] == "Ronchy2000/epic-freebies-helper" for row in artifact.appendix["filtered_or_noisy"])


def test_render_weekly_focus_markdown_has_executive_snapshot_and_compact_basis():
    from radar_focus import build_weekly_focus_artifact, render_weekly_focus_markdown

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                domain="agentshield.dev",
                sources=["https://agentshield.dev"],
                evidence_confidence_score=70,
                attio_status="no_match",
            )
        ],
        run_id="2026-05-11",
    )
    markdown = render_weekly_focus_markdown(artifact)

    assert markdown.startswith("# Marathon Signal Radar: Weekly Focus")
    assert "## Executive Snapshot" in markdown
    assert "Partner Focus rows:" in markdown
    assert "OSS/project-only rows:" in markdown
    assert "Company/launch-style rows:" in markdown
    assert "Readiness note:" in markdown
    assert "Top identity-resolution target:" in markdown
    assert "## Partner Focus" in markdown
    assert "### Focus Evidence Links" in markdown
    assert "https://agentshield.dev" in markdown
    assert "company_identity_quality_basis" not in markdown
    assert "Missing Evidence" in markdown


def test_render_weekly_focus_markdown_qualifies_market_movement_headings():
    from radar_focus import build_weekly_focus_artifact, render_weekly_focus_markdown

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="SecurityRepo",
                stable_key="security-repo",
                market_sector="Cybersecurity",
                sector="Cybersecurity",
                theme="AI agent security",
                sources=["https://github.com/example/security-repo"],
                evidence_confidence_score=70,
            ),
            _candidate(
                name="DevtoolsRepo",
                stable_key="devtools-repo",
                market_sector="Devtools",
                sector="Devtools",
                theme="AI agent security",
                sources=["https://github.com/example/devtools-repo"],
                evidence_confidence_score=70,
            ),
        ],
        run_id="2026-05-11",
    )
    markdown = render_weekly_focus_markdown(artifact)

    assert "### AI agent security (Cybersecurity)" in markdown
    assert "### AI agent security (Devtools)" in markdown


def test_write_weekly_focus_json_and_feedback_scaffold(tmp_path):
    import json
    from radar_focus import build_weekly_focus_artifact, write_feedback_scaffold, write_weekly_focus_json

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                domain="agentshield.dev",
                sources=["https://agentshield.dev"],
                evidence_confidence_score=70,
                attio_status="no_match",
            )
        ],
        run_id="2026-05-11",
    )
    focus_path = write_weekly_focus_json(artifact, tmp_path / "weekly-focus.json")
    feedback_path = write_feedback_scaffold("2026-05-11", artifact.partner_focus, tmp_path / "feedback.json")

    focus_payload = json.loads(focus_path.read_text())
    feedback_payload = json.loads(feedback_path.read_text())

    assert focus_payload["run_id"] == "2026-05-11"
    assert "partner_focus" in focus_payload
    assert feedback_payload["run_id"] == "2026-05-11"
    assert feedback_payload["feedback"][0]["focus_item_id"] == artifact.partner_focus[0].id
