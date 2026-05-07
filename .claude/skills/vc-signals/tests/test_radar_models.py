def test_signal_roundtrip_dict():
    from radar_models import Signal

    signal = Signal(
        source="reddit",
        role="pain",
        title="Teams hate debugging flaky AI agents",
        url="https://reddit.com/r/devops/example",
        sector="devtools",
        theme="Agent reliability",
        text="Repeated complaints about flaky agent runs.",
        can_create_candidate=False,
        evidence_strength=35,
        reason="Reddit pain evidence should support themes, not directly create rows.",
    )

    assert Signal.from_dict(signal.to_dict()) == signal


def test_candidate_serializes_profile_fields():
    from radar_models import Candidate

    candidate = Candidate(
        name="AgentShield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        company_linkedin="",
        company_x="",
        founder_profiles=[{"name": "affaan-m", "github": "https://github.com/affaan-m"}],
    )

    payload = candidate.to_dict()
    assert payload["name"] == "AgentShield"
    assert payload["founder_profiles"][0]["github"] == "https://github.com/affaan-m"


def test_candidate_v3_fields_roundtrip_dict():
    from radar_models import Candidate

    candidate = Candidate(
        name="EvalForge",
        sector="ai-infra",
        theme="Agent evals",
        source="https://example.com/evalforge",
        candidate_type="company",
        market_sector="AI infrastructure",
        source_lane="launch",
        evidence_role="company",
        sector_confidence="High",
        sector_reason="Clear agent evaluation workflow and infra buyer.",
        partner_priority_score=84,
    )

    payload = candidate.to_dict()

    assert payload["market_sector"] == "AI infrastructure"
    assert payload["source_lane"] == "launch"
    assert payload["evidence_role"] == "company"
    assert payload["sector_confidence"] == "High"
    assert payload["sector_reason"] == "Clear agent evaluation workflow and infra buyer."
    assert payload["partner_priority_score"] == 84
    assert Candidate.from_dict(payload) == candidate


def test_evidence_metadata_roundtrip_and_candidate_field():
    from radar_models import Candidate, EvidenceMetadata

    metadata = EvidenceMetadata(
        candidate_key="candidate:cybersecurity:burrow",
        source_url="https://news.ycombinator.com/item?id=47761957",
        source="hackernews",
        title="Show HN: Burrow - Runtime Security for AI Agents",
        author="saranshrana",
        outbound_url="https://burrow.security",
        domain="burrow.security",
        query_kind="theme_company_search",
        query_topic="AI agent security startups Seed Series A founder launch",
    )
    restored = EvidenceMetadata.from_dict({**metadata.to_dict(), "future": "ignored"})

    candidate = Candidate(
        name="Burrow",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=47761957",
        candidate_type="launch",
        evidence_metadata=[restored.to_dict()],
    )

    assert restored.outbound_url == "https://burrow.security"
    assert Candidate.from_dict(candidate.to_dict()).evidence_metadata[0]["domain"] == "burrow.security"


def test_theme_signal_roundtrip_dict():
    from radar_models import ThemeSignal

    signal = ThemeSignal(
        market_sector="Devtools",
        theme="Agent observability",
        source_lanes=["reddit_pain", "hn_discussion"],
        evidence_count=7,
        evidence_summary="Repeated complaints about debugging opaque agent runs.",
        why_it_matters="Agents need production-grade monitoring before broad deployment.",
        why_no_company_yet="The evidence is pain-heavy but not tied to a new company launch.",
        suggested_search="agent observability startup launch",
        confidence="Medium",
    )

    assert ThemeSignal.from_dict(signal.to_dict()) == signal


def test_sector_intelligence_roundtrip_dict():
    from radar_models import SectorIntelligence

    intelligence = SectorIntelligence(
        market_sector="Cybersecurity",
        status="Thin company formation, meaningful pain",
        raw_signals=18,
        candidate_eligible_signals=4,
        promoted_candidates=2,
        rejected_signals=12,
        best_evidence="Multiple teams report credential leakage from AI coding agents.",
        why_no_more_companies="Most evidence came from Reddit pain and generic guidance posts.",
        next_hunt="Search for AI agent permissioning launches and OSS repos.",
        source_errors=["HN timeout"],
    )

    assert SectorIntelligence.from_dict(intelligence.to_dict()) == intelligence


def test_synthesis_result_roundtrip():
    from radar_models import PossibleCompanyLead, SectorDiagnosis, SynthesisResult, ThemeHypothesis

    result = SynthesisResult(
        enabled=True,
        model="fake-synthesis",
        generated_at="2026-05-04T12:00:00Z",
        source_digest={"candidate_count": 50, "source_lanes": {"OSS": 50}},
        sector_diagnoses=[
            SectorDiagnosis(
                market_sector="Vertical AI",
                diagnosis="Source failure / incomplete coverage",
                evidence_urls=[],
                recommended_next_queries=["vertical AI workflow automation startup launch"],
                confidence="High",
            )
        ],
        theme_hypotheses=[
            ThemeHypothesis(
                market_sector="Cybersecurity",
                theme="AI agent permission security",
                evidence_summary="Operators and OSS projects point to MCP/tool permission risk.",
                evidence_urls=["https://github.com/affaan-m/agentshield"],
                why_it_matters="Agent adoption creates new security surfaces.",
                why_this_may_be_noise="Evidence is mostly OSS.",
                confidence="Medium",
            )
        ],
        possible_company_leads=[
            PossibleCompanyLead(
                name="AgentShield",
                market_sector="Cybersecurity",
                source_lane="OSS",
                domain="",
                evidence_urls=["https://github.com/affaan-m/agentshield"],
                why_on_radar="Fast OSS momentum.",
                verification_needed=["Confirm company formation"],
                suggested_action="track company formation",
                confidence="Medium",
            )
        ],
        partner_notes=["This run is OSS-heavy."],
        warnings=[],
    )

    restored = SynthesisResult.from_dict(result.to_dict())

    assert restored.enabled is True
    assert restored.sector_diagnoses[0].market_sector == "Vertical AI"
    assert restored.theme_hypotheses[0].theme == "AI agent permission security"
    assert restored.possible_company_leads[0].name == "AgentShield"
    assert restored.partner_notes == ["This run is OSS-heavy."]


def test_synthesis_result_ignores_unknown_payload_fields():
    from radar_models import SynthesisResult

    restored = SynthesisResult.from_dict(
        {
            "enabled": False,
            "model": "",
            "unknown_future_field": "ok",
            "sector_diagnoses": [{"market_sector": "AI Infra", "extra": "ignored"}],
        }
    )

    assert restored.enabled is False
    assert restored.sector_diagnoses[0].market_sector == "AI Infra"


def test_synthesis_result_to_dict_copies_source_digest():
    from radar_models import SynthesisResult

    result = SynthesisResult(source_digest={"source_lanes": {"OSS": 50}})
    payload = result.to_dict()
    payload["source_digest"]["source_lanes"]["OSS"] = 0

    assert result.source_digest["source_lanes"]["OSS"] == 50


def test_focus_item_roundtrips_and_ignores_extra_fields():
    from radar_models import FocusItem

    item = FocusItem(
        id="agentshield",
        name="AgentShield",
        market_movement="AI agent permission security",
        evidence_urls=["https://github.com/affaan-m/agentshield"],
        company_identity_quality_score=60,
        company_identity_quality_basis=["oss_project_with_company_formation_signal"],
        actionability_basis=["attio_unknown_not_new"],
        missing_evidence=["no verified company domain"],
        recommended_action="Research deeper",
    )

    payload = item.to_dict()
    payload["future_field"] = "ignored"
    restored = FocusItem.from_dict(payload)

    assert restored == item
    assert restored.company_identity_quality_basis == ["oss_project_with_company_formation_signal"]
    assert restored.missing_evidence == ["no verified company domain"]


def test_weekly_focus_artifact_roundtrips_nested_models():
    from radar_models import ExecutiveSnapshot, FocusItem, MarketMovement, WeeklyFocusArtifact

    artifact = WeeklyFocusArtifact(
        run_id="2026-05-11",
        executive_snapshot=ExecutiveSnapshot(
            top_movement="AI agent permission security",
            top_new_to_marathon="AgentShield",
            rows_needing_owner=1,
            rows_needing_attio_refresh=0,
            biggest_source_gap="No X/Product Hunt/package-registry adapters in Phase 1A/1B.",
            top_actions=["Research deeper: 1"],
        ),
        partner_focus=[
            FocusItem(
                id="agentshield",
                name="AgentShield",
                evidence_urls=["https://github.com/affaan-m/agentshield"],
                recommended_action="Research deeper",
            )
        ],
        market_movements=[
            MarketMovement(
                id="cybersecurity-ai-agent-permission-security",
                name="AI agent permission security",
                market_sector="Cybersecurity",
                what_is_moving="Security teams are paying attention to MCP/tool permissions.",
                companies_or_projects=["AgentShield"],
                evidence_urls=["https://github.com/affaan-m/agentshield"],
            )
        ],
        appendix={"source_gaps": ["No X/Product Hunt/package-registry adapters in Phase 1A/1B."]},
        source_gaps=["No X/Product Hunt/package-registry adapters in Phase 1A/1B."],
    )

    restored = WeeklyFocusArtifact.from_dict(artifact.to_dict())

    assert restored == artifact
    assert isinstance(restored.partner_focus[0], FocusItem)
    assert isinstance(restored.market_movements[0], MarketMovement)
    assert restored.executive_snapshot.top_movement == "AI agent permission security"


def test_identity_resolution_roundtrip_ignores_unknown_fields():
    from radar_models import IdentityResolution

    payload = {
        "candidate_key": "launch:burrow",
        "original_name": "Burrow",
        "resolved_name": "Burrow",
        "identity_type": "launch_style_needs_identity",
        "candidate_domain": "burrow.example",
        "verified_domain": "burrow.example",
        "domain_confidence": "Medium",
        "verified_domain_basis": ["candidate_domain_present"],
        "founders": ["Jane Founder"],
        "commercial_intent_score": 65,
        "commercial_intent_basis": ["launch_source_present"],
        "identity_confidence_score": 75,
        "identity_confidence": "Medium",
        "identity_confidence_basis": ["verified_domain_present"],
        "attio_match_keys": ["burrow.example", "Burrow"],
        "attio_safe_to_match": True,
        "recommended_identity_action": "Assign owner",
        "missing_identity_evidence": ["no company linkedin"],
        "evidence_urls": ["https://news.ycombinator.com/item?id=123"],
        "source_outbound_urls": ["https://burrow.example"],
        "source_titles": ["Show HN: Burrow"],
        "fetch_warnings": [],
        "resolved_from": ["candidate_domain"],
        "extra_future_field": "ignored",
    }

    result = IdentityResolution.from_dict(payload)

    assert result.candidate_key == "launch:burrow"
    assert result.verified_domain == "burrow.example"
    assert result.domain_confidence == "Medium"
    assert result.source_titles == ["Show HN: Burrow"]
    assert result.attio_safe_to_match is True
    assert "extra_future_field" not in result.to_dict()
