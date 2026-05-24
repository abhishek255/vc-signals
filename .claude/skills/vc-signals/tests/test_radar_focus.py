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


def test_weekly_focus_renders_discovery_yield_trial_section():
    from radar_focus import build_weekly_focus_artifact, render_weekly_focus_markdown

    artifact = build_weekly_focus_artifact(
        candidates=[],
        category_context_items=[],
        theme_signals=[],
        sector_intelligence=[],
        source_health=[],
        run_id="2026-05-10",
        discovery_yield_trial={
            "enabled": True,
            "label": "Phase 5.3 Discovery Yield Trial",
            "families": ["official_company_page", "founder_company_pages", "movement_platform"],
            "verified_domains": 3,
            "maturity_confirmed_early_stage": 1,
            "research_worthy_unknown": 1,
            "category_anchors": 1,
            "accepted": 3,
            "rejected": 8,
            "verified_domain_list": ["langwatch.ai", "wiz.io", "straiker.ai"],
            "families_run": {
                "official_company_page": {
                    "queries_run": 1,
                    "verified_domains": 1,
                    "early_stage": 0,
                    "research_worthy_unknown": 1,
                    "category_anchors": 0,
                },
                "movement_platform": {
                    "queries_run": 1,
                    "verified_domains": 2,
                    "early_stage": 1,
                    "research_worthy_unknown": 0,
                    "category_anchors": 1,
                },
            },
        },
    )

    markdown = render_weekly_focus_markdown(artifact)

    assert "## Discovery Yield Trial" in markdown
    assert "Trial results are experimental" in markdown
    assert "Verified domains: 3" in markdown
    assert "Early-stage confirmed: 1" in markdown
    assert "official_company_page" in markdown


def test_weekly_focus_renders_hn_launch_trial_section():
    from radar_focus import build_weekly_focus_artifact, render_weekly_focus_markdown

    artifact = build_weekly_focus_artifact(
        candidates=[],
        category_context_items=[],
        theme_signals=[],
        sector_intelligence=[],
        source_health=[],
        run_id="2026-05-10",
        hn_launch_trial={
            "enabled": True,
            "label": "Phase 6C HN Launch Trial",
            "queries_planned": 4,
            "items_seen": 8,
            "outbound_candidates": 2,
            "project_only_rows": 3,
            "product_context_rows": 1,
            "research_deeper_rows": 2,
            "assign_owner_rows": 0,
            "action_blocked_by_attio_rows": 1,
            "unsafe_promotions": 0,
            "review_rows": [
                {
                    "name": "Veris",
                    "domain": "veris.ai",
                    "final_action": "Assign owner",
                    "completion_status": "completed_clean",
                    "evidence_dimensions": ["customer", "founder", "stage"],
                    "attio_status": "no_owner",
                    "missing_evidence": [],
                },
                {
                    "name": "AttioBlocked",
                    "domain": "blocked.ai",
                    "final_action": "Research deeper",
                    "recommended_lane": "Action blocked by Attio",
                    "completion_status": "completed_with_stage_failure",
                    "evidence_dimensions": ["customer", "founder", "stage"],
                    "attio_status": "unknown",
                    "missing_evidence": ["attio_timeout"],
                },
                {
                    "name": "ShouldNotDump",
                    "domain": "dump.ai",
                    "final_action": "Research deeper",
                    "completion_status": "completed_with_stage_failure",
                    "evidence_dimensions": [],
                    "attio_status": "unknown",
                    "missing_evidence": ["maturity_query_timeout"],
                },
            ],
            "partial": False,
            "runtime": {
                "candidates_completed": 2,
                "completed_clean": 1,
                "completed_with_stage_failure": 1,
                "stage_failures": 1,
            },
        },
    )

    markdown = render_weekly_focus_markdown(artifact)

    assert "## HN Launch Trial" in markdown
    assert "Trial results are experimental" in markdown
    assert "Outbound candidates: 2" in markdown
    assert "Assign owner rows: 0" in markdown
    assert "Action blocked by Attio rows: 1" in markdown
    assert "Unsafe promotions: 0" in markdown
    assert "clean 1" in markdown
    assert "stage-failed 1" in markdown
    assert "Top HN review rows" in markdown
    assert "Veris" in markdown
    assert "AttioBlocked" in markdown
    assert "ShouldNotDump" not in markdown


def test_hn_assign_owner_rows_enter_main_partner_focus_when_weekly_hn_enabled():
    from radar_focus import ACTION_ASSIGN_OWNER, build_weekly_focus_artifact, render_weekly_focus_markdown

    artifact = build_weekly_focus_artifact(
        candidates=[],
        category_context_items=[],
        theme_signals=[],
        sector_intelligence=[],
        source_health=[],
        run_id="2026-05-24",
        hn_launch_trial={
            "enabled": True,
            "label": "Phase 6C HN Launch Trial",
            "assign_owner_rows": 1,
            "unsafe_promotions": 0,
            "review_rows": [
                {
                    "name": "Voker",
                    "domain": "voker.ai",
                    "final_action": "Assign owner",
                    "completion_status": "completed_clean",
                    "evidence_dimensions": ["customer", "founder", "stage"],
                    "attio_status": "no_match",
                    "missing_evidence": [],
                    "unsafe_promotion": False,
                    "assign_owner_evidence_provenance": {
                        "hn_source": {
                            "url": "https://news.ycombinator.com/item?id=48109962",
                            "title": "Launch HN: Voker (YC S24) - Analytics for AI Agents",
                        },
                        "official_company_source": {"url": "https://voker.ai", "domain": "voker.ai"},
                        "founder_evidence": {
                            "url": "https://www.ycombinator.com/companies/voker",
                            "founders": ["Tyler Postle", "Alex Rudolph"],
                        },
                        "stage_funding_evidence": {
                            "url": "https://www.ycombinator.com/companies/voker",
                            "maturity_status": "seed_to_series_b",
                            "basis": ["accelerator_batch_evidence: YC S24"],
                        },
                        "commercial_customer_evidence": {"url": "https://voker.ai"},
                        "attio_status_evidence": {"status": "no_match", "source": "attio_read", "action_safe": True},
                    },
                },
                {
                    "name": "MissingFounder",
                    "domain": "missing.ai",
                    "final_action": "Research deeper",
                    "completion_status": "completed_with_stage_failure",
                    "evidence_dimensions": ["customer", "stage"],
                    "attio_status": "no_match",
                    "missing_evidence": ["no founder/team evidence"],
                    "unsafe_promotion": False,
                },
            ],
        },
    )

    assert artifact.sourcing_candidates[0].name == "Voker"
    assert artifact.sourcing_candidates[0].recommended_action == ACTION_ASSIGN_OWNER
    assert "hn_launch_weekly_source" in artifact.sourcing_candidates[0].focus_priority_basis
    assert "https://news.ycombinator.com/item?id=48109962" in artifact.sourcing_candidates[0].evidence_urls
    assert all(item.name != "MissingFounder" for item in artifact.partner_focus)

    markdown = render_weekly_focus_markdown(artifact)

    assert "HN launch-sourced Assign Owner" in markdown
    assert "HN opt-in" not in markdown
    assert "Voker" in markdown


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


def test_unknown_maturity_verified_company_routes_to_research_deeper_queue():
    from radar_focus import ACTION_RESEARCH_DEEPER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="Copperhelm",
                stable_key="company:copperhelm.com",
                source="https://copperhelm.com/",
                sources=["https://copperhelm.com/"],
                candidate_type="company_web",
                domain="copperhelm.com",
                identity_type="verified_company",
                attio_status="no_match",
                attio_safe_to_match=True,
                recommended_identity_action="Assign owner",
                evidence_confidence_score=55,
                maintainer_profiles=[],
                founder_profiles=[],
                why_on_radar="Copperhelm is building agentic cloud security.",
                maturity_status="unknown",
                maturity_basis=["maturity_not_verified"],
                lead_route="research_deeper",
            )
        ],
        run_id="2026-05-08",
    )

    assert artifact.sourcing_candidates == []
    assert artifact.research_deeper_queue[0].name == "Copperhelm"
    assert artifact.research_deeper_queue[0].recommended_action == ACTION_RESEARCH_DEEPER
    assert artifact.research_deeper_queue[0].maturity_basis == ["maturity_not_verified"]
    assert "no stage or funding verification" in artifact.research_deeper_queue[0].missing_evidence
    assert "no buyer or customer pull evidence" in artifact.research_deeper_queue[0].missing_evidence


def test_seed_stage_verified_company_can_enter_sourcing_candidates():
    from radar_focus import ACTION_ASSIGN_OWNER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="AgentFence",
                stable_key="company:agentfence.dev",
                source="https://agentfence.dev/",
                sources=["https://agentfence.dev/"],
                candidate_type="company_web",
                domain="agentfence.dev",
                identity_type="verified_company",
                attio_status="no_match",
                attio_safe_to_match=True,
                recommended_identity_action="Assign owner",
                evidence_confidence_score=70,
                maintainer_profiles=[],
                founder_profiles=[{"name": "Ada Founder"}],
                why_on_radar="AgentFence raised seed funding for AI agent security.",
                maturity_status="seed_to_series_b",
                maturity_basis=["seed_or_pre_seed"],
                maturity_evidence_urls=["https://agentfence.dev/seed"],
                lead_route="sourcing_candidate",
                owner_readiness_score=85,
                owner_readiness_basis=["founder_team_evidence", "stage_funding_evidence", "attio_new_or_no_match"],
                missing_owner_evidence=[],
                recommended_owner_action="Assign owner",
            )
        ],
        run_id="2026-05-08",
    )

    assert artifact.sourcing_candidates[0].name == "AgentFence"
    assert artifact.sourcing_candidates[0].recommended_action == ACTION_ASSIGN_OWNER
    assert artifact.research_deeper_queue == []


def test_low_evidence_row_cannot_assign_owner_even_if_owner_ready():
    from radar_focus import ACTION_RESEARCH_DEEPER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="AgentFence",
                stable_key="company:agentfence.dev",
                source="https://agentfence.dev/",
                sources=["https://agentfence.dev/"],
                candidate_type="company_web",
                domain="agentfence.dev",
                identity_type="verified_company",
                attio_status="no_match",
                attio_safe_to_match=True,
                recommended_identity_action="Assign owner",
                investment_interest_score=80,
                evidence_confidence="Low",
                evidence_confidence_score=70,
                tier="Watchlist",
                founder_profiles=[{"name": "Ada Founder"}],
                why_on_radar="AgentFence raised seed funding and has customer pilots for AI agent security.",
                maturity_status="seed_to_series_b",
                maturity_basis=["seed_or_pre_seed"],
                maturity_evidence_urls=["https://agentfence.dev/seed"],
                lead_route="sourcing_candidate",
                owner_readiness_score=95,
                owner_readiness_basis=["founder_team_evidence", "stage_funding_evidence", "attio_new_or_no_match"],
                missing_owner_evidence=[],
                recommended_owner_action="Assign owner",
            )
        ],
        run_id="2026-05-22",
    )

    assert artifact.sourcing_candidates == []
    assert artifact.research_deeper_queue[0].recommended_action == ACTION_RESEARCH_DEEPER


def test_needs_more_evidence_row_cannot_assign_owner_even_if_owner_ready():
    from radar_focus import ACTION_RESEARCH_DEEPER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="AgentFence",
                stable_key="company:agentfence.dev",
                source="https://agentfence.dev/",
                sources=["https://agentfence.dev/"],
                candidate_type="company_web",
                domain="agentfence.dev",
                identity_type="verified_company",
                attio_status="no_match",
                attio_safe_to_match=True,
                recommended_identity_action="Assign owner",
                investment_interest_score=80,
                evidence_confidence="High",
                evidence_confidence_score=80,
                tier="Needs More Evidence",
                founder_profiles=[{"name": "Ada Founder"}],
                why_on_radar="AgentFence raised seed funding and has customer pilots for AI agent security.",
                maturity_status="seed_to_series_b",
                maturity_basis=["seed_or_pre_seed"],
                maturity_evidence_urls=["https://agentfence.dev/seed"],
                lead_route="sourcing_candidate",
                owner_readiness_score=95,
                owner_readiness_basis=["founder_team_evidence", "stage_funding_evidence", "attio_new_or_no_match"],
                missing_owner_evidence=[],
                recommended_owner_action="Assign owner",
            )
        ],
        run_id="2026-05-22",
    )

    assert artifact.sourcing_candidates == []
    assert artifact.research_deeper_queue[0].recommended_action == ACTION_RESEARCH_DEEPER


def test_seed_stage_verified_company_without_founder_stays_research_deeper():
    from radar_focus import ACTION_RESEARCH_DEEPER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="Copperhelm",
                stable_key="company:copperhelm.com",
                source="https://copperhelm.com/",
                sources=["https://copperhelm.com/"],
                candidate_type="company_web",
                domain="copperhelm.com",
                identity_type="verified_company",
                attio_status="no_match",
                attio_safe_to_match=True,
                recommended_identity_action="Assign owner",
                evidence_confidence_score=70,
                maintainer_profiles=[],
                founder_profiles=[],
                why_on_radar="Copperhelm emerged from stealth with $7M seed funding.",
                maturity_status="seed_to_series_b",
                maturity_basis=["seed_or_pre_seed"],
                maturity_evidence_urls=["https://example.com/copperhelm-seed"],
                lead_route="sourcing_candidate",
            )
        ],
        run_id="2026-05-08",
    )

    item = artifact.research_deeper_queue[0]
    assert artifact.sourcing_candidates == []
    assert item.name == "Copperhelm"
    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert item.owner_readiness_score < 80
    assert "no founder/team evidence" in item.missing_owner_evidence
    assert item.recommended_next_validation_step == "Find founder/team source"


def test_owner_evidence_clears_stale_missing_identity_text():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="Arize",
                stable_key="company:arize.com",
                source="https://arize.com/",
                sources=["https://arize.com/"],
                candidate_type="company_web",
                domain="arize.com",
                identity_type="verified_company",
                attio_status="no_owner",
                attio_safe_to_match=True,
                evidence_confidence_score=70,
                missing_identity_evidence=["no founder identity", "no stage or funding verification"],
                founder_team_evidence=["https://arize.com/team"],
                founder_profiles=[{"name": "source-backed founder/team evidence", "source": "https://arize.com/team"}],
                maturity_status="unknown",
                lead_route="research_deeper",
            )
        ],
        run_id="2026-05-08",
    )

    item = artifact.research_deeper_queue[0]
    assert "no founder identity" not in item.missing_evidence
    assert "no stage or funding verification" in item.missing_evidence


def test_unknown_attio_blocks_owner_ready_assign_owner():
    from radar_focus import ACTION_RESEARCH_DEEPER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="AgentFence",
                stable_key="company:agentfence.dev",
                source="https://agentfence.dev/",
                sources=["https://agentfence.dev/"],
                candidate_type="company_web",
                domain="agentfence.dev",
                identity_type="verified_company",
                attio_status="unknown",
                attio_safe_to_match=True,
                recommended_identity_action="Assign owner",
                evidence_confidence_score=80,
                founder_profiles=[{"name": "Ada Founder"}],
                why_on_radar="AgentFence raised seed funding and has customer pilots for AI agent security.",
                maturity_status="seed_to_series_b",
                maturity_basis=["seed_or_pre_seed"],
                maturity_evidence_urls=["https://agentfence.dev/seed"],
                lead_route="sourcing_candidate",
            )
        ],
        run_id="2026-05-08",
    )

    item = artifact.research_deeper_queue[0]
    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert "Attio status unknown" in item.missing_owner_evidence
    assert item.recommended_next_validation_step == "Check Attio match/status"


def test_customer_pull_improves_owner_readiness_score():
    from radar_focus import score_owner_readiness

    base = _candidate(
        name="AgentFence",
        candidate_type="company_web",
        domain="agentfence.dev",
        identity_type="verified_company",
        attio_status="no_match",
        attio_safe_to_match=True,
        founder_profiles=[{"name": "Ada Founder"}],
        maturity_status="seed_to_series_b",
        maturity_basis=["seed_or_pre_seed"],
        lead_route="sourcing_candidate",
        why_on_radar="AgentFence raised seed funding for AI agent security.",
    )
    with_customer = _candidate(
        name="AgentFence",
        candidate_type="company_web",
        domain="agentfence.dev",
        identity_type="verified_company",
        attio_status="no_match",
        attio_safe_to_match=True,
        founder_profiles=[{"name": "Ada Founder"}],
        maturity_status="seed_to_series_b",
        maturity_basis=["seed_or_pre_seed"],
        lead_route="sourcing_candidate",
        why_on_radar="AgentFence raised seed funding for AI agent security. Enterprise security teams use it in pilots.",
    )

    base_score, _, base_missing, _ = score_owner_readiness(base)
    customer_score, customer_basis, customer_missing, _ = score_owner_readiness(with_customer)

    assert customer_score > base_score
    assert "customer_buyer_pull_evidence" in customer_basis
    assert "no customer/buyer pull evidence" not in customer_missing


def test_late_or_category_anchor_rows_stay_out_of_partner_focus_and_new_to_marathon():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="n8n.io - AI workflow automation platform",
                stable_key="company:n8n.io",
                sector="Devtools",
                market_sector="Devtools",
                theme="Devtools workflow automation",
                source="https://n8n.io/",
                sources=["https://n8n.io/"],
                candidate_type="company_web",
                domain="n8n.io",
                identity_type="verified_company",
                attio_status="no_match",
                attio_safe_to_match=True,
                recommended_identity_action="Assign owner",
                evidence_confidence_score=70,
                maintainer_profiles=[],
                why_on_radar="n8n validates workflow automation demand.",
                maturity_status="likely_too_late",
                maturity_basis=["series_c_or_later", "large_round_or_valuation"],
                maturity_evidence_urls=["https://blog.n8n.io/series-c/"],
                category_anchor=True,
                lead_route="category_context",
            )
        ],
        run_id="2026-05-08",
    )

    assert artifact.partner_focus == []
    assert artifact.sourcing_candidates == []
    assert artifact.research_deeper_queue == []
    assert artifact.new_to_marathon == []
    assert artifact.appendix["category_context"][0]["name"] == "n8n"


def test_oss_project_watch_is_separate_from_company_focus_lanes():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="redwoodjs/agent-ci",
                stable_key="company:agent-ci.dev",
                sector="Devtools",
                market_sector="Devtools",
                theme="Devtools workflow automation",
                source="https://github.com/redwoodjs/agent-ci",
                sources=["https://github.com/redwoodjs/agent-ci"],
                candidate_type="oss_project",
                domain="agent-ci.dev",
                identity_type="oss_with_commercial_intent",
                attio_status="no_match",
                attio_safe_to_match=True,
                evidence_confidence_score=50,
                why_on_radar="Agent-CI is local GitHub Actions for coding agents.",
                maturity_status="unknown",
                lead_route="research_deeper",
            )
        ],
        run_id="2026-05-08",
    )

    assert artifact.sourcing_candidates == []
    assert artifact.research_deeper_queue == []
    assert artifact.oss_project_watch[0].name == "redwoodjs/agent-ci"
    assert artifact.partner_focus == []


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


def test_resolved_identity_upgrades_no_match_row_to_assign_owner():
    from radar_focus import ACTION_ASSIGN_OWNER, build_focus_item

    item = build_focus_item(
        _candidate(
            name="Burrow",
            domain="burrow.security",
            attio_status="no_match",
            evidence_confidence_score=50,
            investment_interest_score=65,
            identity_type="verified_company",
            identity_confidence_score=78,
            commercial_intent_score=65,
            attio_safe_to_match=True,
            recommended_identity_action="Assign owner",
            founders=["Jane Founder"],
            founder_profiles=[{"name": "Jane Founder"}],
            sources=["https://news.ycombinator.com/item?id=47761957"],
            maturity_status="seed_to_series_b",
            maturity_basis=["seed_or_pre_seed"],
            lead_route="sourcing_candidate",
        )
    )

    assert item.company_identity_quality_score >= 80
    assert item.recommended_action == ACTION_ASSIGN_OWNER
    assert "identity_resolution_verified_company" in item.company_identity_quality_basis


def test_unverified_github_project_with_no_match_stays_research_deeper():
    from radar_focus import ACTION_ASSIGN_OWNER, ACTION_RESEARCH_DEEPER, build_focus_item

    item = build_focus_item(
        _candidate(
            name="affaan-m/agentshield",
            stable_key="repo:agentshield",
            domain="",
            candidate_type="oss_project",
            attio_status="no_match",
            evidence_confidence_score=50,
            identity_type="oss_project_watch",
            identity_confidence_score=45,
            commercial_intent_score=55,
            attio_safe_to_match=False,
            recommended_identity_action="Research deeper",
            missing_identity_evidence=["no verified domain"],
            sources=["https://github.com/affaan-m/agentshield"],
        )
    )

    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert item.recommended_action != ACTION_ASSIGN_OWNER
    assert item.company_domain == ""
    assert "identity_resolution_weak" in item.company_identity_quality_basis


def test_focus_does_not_assign_owner_to_github_only_project_after_discovery():
    from radar_focus import ACTION_ASSIGN_OWNER, ACTION_RESEARCH_DEEPER, build_focus_item

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        domain="",
        why_on_radar="AI agent security scanner for MCP permissions.",
        sources=["https://github.com/affaan-m/agentshield"],
        attio_status="no_match",
        identity_type="oss_project_watch",
        identity_confidence_score=45,
        recommended_identity_action="Research deeper",
        missing_identity_evidence=["no verified domain"],
        evidence_confidence_score=50,
    )

    item = build_focus_item(candidate)

    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert item.recommended_action != ACTION_ASSIGN_OWNER
    assert item.identity_type == "oss_project_watch"


def test_weak_identity_demotes_unknown_oss_row_to_monitor_only():
    from radar_focus import ACTION_MONITOR_ONLY, build_focus_item

    item = build_focus_item(
        _candidate(
            name="example/weak-demo",
            domain="",
            candidate_type="oss_project",
            attio_status="unknown",
            evidence_confidence_score=45,
            identity_type="oss_project_watch",
            identity_confidence_score=35,
            commercial_intent_score=20,
            recommended_identity_action="Monitor only",
            sources=["https://github.com/example/weak-demo"],
            why_on_radar="Example tutorial repo for a toy workflow.",
        )
    )

    assert item.recommended_action == ACTION_MONITOR_ONLY
    assert item.company_identity_quality_score < 60
    assert "identity_resolution_weak" in item.company_identity_quality_basis


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


def test_new_to_marathon_excludes_weak_extracted_names_and_uses_identity_missing_terms():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="A",
                stable_key="weak-a",
                domain="",
                candidate_type="company_web",
                founder_profiles=[],
                founders=[],
                maintainer_profiles=[],
                attio_status="no_match",
                evidence_confidence_score=45,
                investment_interest_score=70,
            ),
            _candidate(
                name="Burrow",
                stable_key="burrow",
                domain="",
                candidate_type="company_web",
                founder_profiles=[],
                founders=[],
                maintainer_profiles=[],
                attio_status="no_match",
                evidence_confidence_score=45,
                investment_interest_score=70,
                identity_type="launch_style_needs_identity",
                identity_confidence_score=45,
                commercial_intent_score=60,
                recommended_identity_action="Research deeper",
                missing_identity_evidence=["no verified domain", "no founder or maintainer identity"],
                sources=["https://news.ycombinator.com/item?id=47761957"],
            ),
        ],
        run_id="2026-05-11",
    )

    assert artifact.new_to_marathon == []
    assert artifact.executive_snapshot.top_new_to_marathon == ""
    assert artifact.executive_snapshot.top_identity_resolution_target == "Burrow"


def test_new_to_marathon_excludes_unverified_github_project_rows():
    from radar_focus import ACTION_RESEARCH_DEEPER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="affaan-m/agentshield",
                stable_key="repo:agentshield",
                domain="",
                candidate_type="oss_project",
                attio_status="no_match",
                evidence_confidence_score=50,
                identity_type="oss_project_watch",
                identity_confidence_score=45,
                commercial_intent_score=55,
                attio_safe_to_match=False,
                recommended_identity_action="Research deeper",
                missing_identity_evidence=["no verified domain"],
                sources=["https://github.com/affaan-m/agentshield"],
            )
        ],
        run_id="2026-05-11",
    )

    assert artifact.new_to_marathon == []
    assert artifact.executive_snapshot.top_new_to_marathon == ""
    assert artifact.executive_snapshot.company_or_launch_style_rows == 0
    assert artifact.workflow_view[ACTION_RESEARCH_DEEPER][0].name == "affaan-m/agentshield"


def test_workflow_view_includes_extended_watchlist_actions_when_focus_empty():
    from radar_focus import ACTION_RESEARCH_DEEPER, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="Burrow",
                stable_key="burrow",
                domain="",
                candidate_type="company_web",
                founder_profiles=[],
                founders=[],
                maintainer_profiles=[],
                attio_status="no_match",
                evidence_confidence_score=45,
                investment_interest_score=70,
                identity_type="launch_style_needs_identity",
                identity_confidence_score=45,
                commercial_intent_score=60,
                recommended_identity_action="Research deeper",
                missing_identity_evidence=["no verified domain", "no founder or maintainer identity"],
                sources=["https://news.ycombinator.com/item?id=47761957"],
            )
        ],
        run_id="2026-05-11",
    )

    assert not artifact.partner_focus
    assert artifact.extended_watchlist
    assert artifact.workflow_view[ACTION_RESEARCH_DEEPER][0].name == "Burrow"


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
                candidate_type="company_web",
                identity_type="verified_company",
                attio_safe_to_match=True,
                attio_status="no_match",
                evidence_confidence_score=75,
            ),
            _candidate(
                name="KnownCo",
                stable_key="knownco",
                domain="known.co",
                sources=["https://known.co"],
                candidate_type="company_web",
                identity_type="verified_company",
                attio_safe_to_match=True,
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


def test_source_gaps_distinguish_bounded_validation_timeouts():
    from radar_focus import build_weekly_focus_artifact
    from radar_models import SectorIntelligence

    artifact = build_weekly_focus_artifact(
        candidates=[],
        sector_intelligence=[
            SectorIntelligence(
                market_sector="Devtools",
                source_errors=["last30days query timed out (75s)"],
            )
        ],
        source_gap_context="bounded_validation",
        run_id="2026-05-11",
    )

    assert "bounded validation profile" in artifact.source_gaps[1]
    assert "true source failure" not in artifact.source_gaps[1]


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
    assert "### Sourcing Candidates" in markdown
    assert "### Research Deeper Queue" in markdown
    assert "### OSS / Project Watch" in markdown
    assert "## Category Context / Market Anchors" in markdown
    assert "### Focus Evidence Links" in markdown
    assert "https://agentshield.dev" in markdown
    assert "company_identity_quality_basis" not in markdown
    assert "Missing Evidence" in markdown


def test_likely_too_late_candidate_cannot_be_assign_owner():
    from radar_focus import ACTION_MONITOR_ONLY, build_focus_item

    item = build_focus_item(
        _candidate(
            name="n8n.io - AI workflow automation platform",
            sector="Devtools",
            market_sector="Devtools",
            theme="Devtools workflow automation",
            source="https://n8n.io/",
            sources=["https://n8n.io/"],
            candidate_type="company_web",
            domain="n8n.io",
            identity_type="verified_company",
            attio_status="no_owner",
            attio_safe_to_match=True,
            recommended_identity_action="Assign owner",
            evidence_confidence_score=70,
            maintainer_profiles=[],
            maturity_status="likely_too_late",
            maturity_basis=["series_c_or_later", "large_round_or_valuation"],
            maturity_evidence_urls=["https://blog.n8n.io/series-c/"],
            category_anchor=True,
            lead_route="category_context",
        )
    )

    assert item.recommended_action == ACTION_MONITOR_ONLY
    assert item.lead_route == "category_context"
    assert item.category_anchor is True


def test_category_context_contributes_market_movement_without_new_to_marathon():
    from radar_focus import build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="n8n.io - AI workflow automation platform",
                sector="Devtools",
                market_sector="Devtools",
                theme="Devtools workflow automation",
                source="https://n8n.io/",
                sources=["https://n8n.io/"],
                candidate_type="company_web",
                domain="n8n.io",
                identity_type="verified_company",
                attio_status="no_match",
                attio_safe_to_match=True,
                recommended_identity_action="Assign owner",
                evidence_confidence_score=70,
                maintainer_profiles=[],
                why_on_radar="n8n validates AI workflow automation demand.",
                maturity_status="likely_too_late",
                maturity_basis=["series_c_or_later", "large_round_or_valuation"],
                maturity_evidence_urls=["https://blog.n8n.io/series-c/"],
                category_anchor=True,
                lead_route="category_context",
            )
        ],
        run_id="2026-05-08",
    )

    assert artifact.new_to_marathon == []
    assert artifact.market_movements
    assert "n8n" in artifact.market_movements[0].companies_or_projects
    assert artifact.appendix["category_context"][0]["name"] == "n8n"


def test_category_context_items_can_be_added_without_entering_partner_focus():
    from radar_focus import ACTION_MONITOR_ONLY, build_weekly_focus_artifact, render_weekly_focus_markdown
    from radar_models import FocusItem

    category_anchor = FocusItem(
        id="7ai",
        name="7AI",
        company_domain="7ai.com",
        market_movement_id="cybersecurity-ai-agent-security",
        market_movement="AI agent security",
        market_sector="Cybersecurity",
        why_focus_this_week="7AI validates demand for AI SOC agents and agentic security.",
        evidence_snapshot=["AI SOC agents and agentic security platform."],
        evidence_urls=["https://7ai.com/", "https://example.com/7ai-series-c"],
        identity_type="verified_company",
        recommended_action=ACTION_MONITOR_ONLY,
        evidence_confidence_score=70,
        company_identity_quality_score=90,
        maturity_status="likely_too_late",
        maturity_basis=["large_round_or_valuation"],
        maturity_evidence_urls=["https://example.com/7ai-series-c"],
        category_anchor=True,
        consensus_risk_reason="Mature category anchor, not a fresh sourcing lead.",
        lead_route="category_context",
    )

    artifact = build_weekly_focus_artifact(
        candidates=[],
        category_context_items=[category_anchor],
        run_id="2026-05-11",
    )
    markdown = render_weekly_focus_markdown(artifact)

    assert artifact.partner_focus == []
    assert artifact.new_to_marathon == []
    assert artifact.appendix["category_context"][0]["name"] == "7AI"
    assert "7AI" in artifact.market_movements[0].companies_or_projects
    assert "## Category Context / Market Anchors" in markdown
    assert "https://7ai.com/" in markdown


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
                    candidate_type="company_web",
                    identity_type="verified_company",
                    attio_safe_to_match=True,
                    evidence_confidence_score=70,
                    attio_status="no_match",
                    maturity_status="seed_to_series_b",
                    maturity_basis=["seed_or_pre_seed"],
                    lead_route="sourcing_candidate",
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
