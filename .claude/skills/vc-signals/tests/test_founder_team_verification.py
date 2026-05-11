from __future__ import annotations

import json


def _candidate(**overrides):
    from radar_models import Candidate

    data = {
        "name": "Copperhelm",
        "sector": "Cybersecurity",
        "market_sector": "Cybersecurity",
        "theme": "Agentic cloud security",
        "source": "https://copperhelm.com/",
        "sources": ["https://copperhelm.com/"],
        "candidate_type": "company_web",
        "domain": "copperhelm.com",
        "identity_type": "verified_company",
        "attio_status": "no_match",
        "attio_safe_to_match": True,
        "attio_match_keys": ["domain:copperhelm.com"],
        "maturity_status": "seed_to_series_b",
        "maturity_basis": ["seed_or_pre_seed"],
        "maturity_evidence_urls": ["https://example.com/copperhelm-seed"],
        "stage_funding_evidence": ["https://example.com/copperhelm-seed"],
        "customer_buyer_evidence": ["https://example.com/copperhelm-pilots"],
        "lead_route": "sourcing_candidate",
        "recommended_identity_action": "Assign owner",
        "why_on_radar": "Copperhelm emerged from stealth with $7M seed funding and design partner pilots.",
        "evidence_confidence_score": 70,
    }
    data.update(overrides)
    return Candidate(**data)


def test_founder_team_query_is_exact_company_and_domain_scoped():
    from founder_team_verification import founder_team_query

    assert founder_team_query(_candidate()) == '"Copperhelm" "copperhelm.com" founder OR co-founder OR CEO OR CTO'


def test_founder_team_query_uses_domain_stem_when_name_is_tagline():
    from founder_team_verification import founder_team_query

    candidate = _candidate(name="Take your AI agents to production, faster.", domain="lyzr.ai")

    assert founder_team_query(candidate) == '"Lyzr" "lyzr.ai" founder OR co-founder OR CEO OR CTO'


def test_named_founder_with_company_match_and_url_counts(tmp_path):
    from founder_team_verification import enrich_founder_team_verification

    def fake_query(topic, **kwargs):
        return {
            "items": [
                {
                    "title": "Copperhelm names founding team",
                    "url": "https://example.com/copperhelm-founders",
                    "snippet": "Jane Doe, founder of Copperhelm, previously led cloud security at Acme.",
                }
            ]
        }

    enriched, report = enrich_founder_team_verification(
        [_candidate(founder_profiles=[], founders=[])],
        query_runner=fake_query,
        cache_dir=tmp_path,
    )

    candidate = enriched[0]
    item = report["items"][0]
    assert candidate.founders == ["Jane Doe"]
    assert candidate.founder_profiles == [
        {
            "name": "Jane Doe",
            "role": "founder",
            "source": "https://example.com/copperhelm-founders",
        }
    ]
    assert candidate.founder_team_evidence == ["https://example.com/copperhelm-founders"]
    assert item["founders_found"] == ["Jane Doe"]
    assert item["evidence_urls"] == ["https://example.com/copperhelm-founders"]
    assert "named_founder_company_match" in item["verification_basis"]


def test_tagline_named_row_can_verify_founder_against_domain_company_name(tmp_path):
    from founder_team_verification import enrich_founder_team_verification

    enriched, report = enrich_founder_team_verification(
        [
            _candidate(
                name="Take your AI agents to production, faster.",
                domain="lyzr.ai",
                founder_profiles=[],
                founders=[],
            )
        ],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Lyzr founder profile",
                    "url": "https://example.com/lyzr-founder",
                    "snippet": "Siva Surendira, founder of Lyzr, is building agent infrastructure for enterprises.",
                }
            ]
        },
        cache_dir=tmp_path,
    )

    assert enriched[0].founders == ["Siva Surendira"]
    assert report["items"][0]["founders_found"] == ["Siva Surendira"]
    assert report["items"][0]["query"] == '"Lyzr" "lyzr.ai" founder OR co-founder OR CEO OR CTO'


def test_title_prefix_does_not_become_founder_name(tmp_path):
    from founder_team_verification import enrich_founder_team_verification

    enriched, report = enrich_founder_team_verification(
        [
            _candidate(
                name="Take your AI agents to production, faster.",
                domain="lyzr.ai",
                founder_profiles=[],
                founders=[],
            )
        ],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Skott: Marketing Super Agent",
                    "url": "https://www.lyzr.ai/skott/",
                    "snippet": "Siva Surendira, Co-founder, Lyzr AI, explains how teams deploy agents.",
                }
            ]
        },
        cache_dir=tmp_path,
    )

    assert enriched[0].founders == ["Siva Surendira"]
    assert report["items"][0]["founders_found"] == ["Siva Surendira"]


def test_company_context_words_do_not_become_founder_name(tmp_path):
    from founder_team_verification import enrich_founder_team_verification

    enriched, report = enrich_founder_team_verification(
        [
            _candidate(
                name="Take your AI agents to production, faster.",
                domain="lyzr.ai",
                founder_profiles=[],
                founders=[],
            )
        ],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Build the Future of AI. Together.",
                    "url": "https://www.lyzr.ai/partners/",
                    "snippet": "Before Lyzr, our founder Siva scaled his first company Power Up Cloud.",
                }
            ]
        },
        cache_dir=tmp_path,
    )

    assert enriched[0].founders == []
    assert "no source-backed named founder/team evidence" in report["items"][0]["missing_founder_evidence"]


def test_generic_team_language_does_not_count(tmp_path):
    from founder_team_verification import enrich_founder_team_verification

    enriched, report = enrich_founder_team_verification(
        [_candidate(founder_profiles=[], founders=[])],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Copperhelm for security teams",
                    "url": "https://example.com/copperhelm",
                    "snippet": "Our team helps enterprise security teams contact our team for a pilot.",
                }
            ]
        },
        cache_dir=tmp_path,
    )

    assert enriched[0].founders == []
    assert enriched[0].founder_team_evidence == []
    assert "no source-backed named founder/team evidence" in report["items"][0]["missing_founder_evidence"]


def test_company_name_must_match_founder_evidence(tmp_path):
    from founder_team_verification import enrich_founder_team_verification

    enriched, report = enrich_founder_team_verification(
        [_candidate(founder_profiles=[], founders=[])],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "OtherCo founder profile",
                    "url": "https://example.com/otherco-founder",
                    "snippet": "Jane Doe, founder of OtherCo, is building cloud security workflows.",
                }
            ]
        },
        cache_dir=tmp_path,
    )

    assert enriched[0].founders == []
    assert "company_name_missing_from_founder_evidence" in report["items"][0]["rejection_reasons"]


def test_founder_evidence_requires_url(tmp_path):
    from founder_team_verification import enrich_founder_team_verification

    enriched, report = enrich_founder_team_verification(
        [_candidate(founder_profiles=[], founders=[])],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Copperhelm founder",
                    "snippet": "Jane Doe, founder of Copperhelm, leads the team.",
                }
            ]
        },
        cache_dir=tmp_path,
    )

    assert enriched[0].founders == []
    assert "evidence_url_required" in report["items"][0]["rejection_reasons"]


def test_missing_founder_stays_research_deeper_with_clear_next_step(tmp_path):
    from founder_team_verification import enrich_founder_team_verification
    from radar_focus import ACTION_RESEARCH_DEEPER, build_focus_item

    enriched, report = enrich_founder_team_verification(
        [_candidate(founder_profiles=[], founders=[])],
        query_runner=lambda topic, **kwargs: {"items": []},
        cache_dir=tmp_path,
    )

    item = build_focus_item(enriched[0])
    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert "no founder/team evidence" in item.missing_owner_evidence
    assert item.recommended_next_validation_step == "Find founder/team source"
    assert report["items"][0]["missing_founder_evidence"] == ["no source-backed named founder/team evidence"]


def test_placeholder_founder_profile_does_not_keep_row_owner_ready(tmp_path):
    from founder_team_verification import enrich_founder_team_verification
    from radar_focus import ACTION_RESEARCH_DEEPER, build_focus_item

    enriched, report = enrich_founder_team_verification(
        [
            _candidate(
                founders=[],
                founder_profiles=[
                    {
                        "name": "source-backed founder/team evidence",
                        "source": "https://copperhelm.com/team",
                    }
                ],
                founder_team_evidence=["https://copperhelm.com/team"],
            )
        ],
        query_runner=lambda topic, **kwargs: {"items": []},
        cache_dir=tmp_path,
    )

    item = build_focus_item(enriched[0])
    assert enriched[0].founder_profiles == []
    assert enriched[0].founder_team_evidence == []
    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert "no founder/team evidence" in item.missing_owner_evidence
    assert report["items"][0]["missing_founder_evidence"] == ["no source-backed named founder/team evidence"]


def test_founder_verification_can_clear_assign_owner_when_all_gates_pass(tmp_path):
    from founder_team_verification import enrich_founder_team_verification
    from radar_focus import ACTION_ASSIGN_OWNER, build_focus_item

    enriched, _ = enrich_founder_team_verification(
        [_candidate(founder_profiles=[], founders=[])],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Copperhelm funding",
                    "url": "https://example.com/copperhelm-founder",
                    "snippet": "Jane Doe, CEO and co-founder of Copperhelm, launched the company after enterprise pilots.",
                }
            ]
        },
        cache_dir=tmp_path,
    )

    item = build_focus_item(enriched[0])
    assert item.recommended_action == ACTION_ASSIGN_OWNER
    assert item.owner_readiness_score >= 80
    assert item.missing_owner_evidence == []


def test_founder_verification_clears_stale_identity_research_action(tmp_path):
    from founder_team_verification import enrich_founder_team_verification
    from radar_focus import ACTION_ASSIGN_OWNER, build_focus_item

    enriched, _ = enrich_founder_team_verification(
        [
            _candidate(
                founder_profiles=[],
                founders=[],
                evidence_confidence_score=40,
                recommended_identity_action="Research deeper",
                missing_identity_evidence=["no founder or maintainer identity"],
            )
        ],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Copperhelm founder",
                    "url": "https://example.com/copperhelm-founder",
                    "snippet": "Jane Doe, founder of Copperhelm, leads the company.",
                }
            ]
        },
        cache_dir=tmp_path,
    )

    item = build_focus_item(enriched[0])
    assert "no founder or maintainer identity" not in enriched[0].missing_identity_evidence
    assert enriched[0].recommended_identity_action == ACTION_ASSIGN_OWNER
    assert enriched[0].evidence_confidence_score >= 60
    assert item.recommended_action == ACTION_ASSIGN_OWNER


def test_founder_verification_skips_category_context_and_oss_rows(tmp_path):
    from founder_team_verification import enrich_founder_team_verification

    calls = []

    def fake_query(topic, **kwargs):  # pragma: no cover - should not run
        calls.append(topic)
        return {"items": []}

    enriched, report = enrich_founder_team_verification(
        [
            _candidate(name="n8n", domain="n8n.io", maturity_status="likely_too_late", category_anchor=True, lead_route="category_context"),
            _candidate(name="redwoodjs/agent-ci", candidate_type="oss_project", identity_type="oss_with_commercial_intent", domain="agent-ci.dev"),
        ],
        query_runner=fake_query,
        cache_dir=tmp_path,
    )

    assert calls == []
    assert report["summary"]["eligible"] == 0
    assert report["summary"]["skipped"] == 2
    assert enriched[0].owner_evidence_status == "skipped"
    assert enriched[1].owner_evidence_status == "skipped"


def test_write_founder_team_verification_artifact(tmp_path):
    from founder_team_verification import enrich_founder_team_verification, write_founder_team_verification_json

    _, report = enrich_founder_team_verification(
        [_candidate(founder_profiles=[], founders=[])],
        query_runner=lambda topic, **kwargs: {"items": []},
        cache_dir=tmp_path,
    )
    path = write_founder_team_verification_json(report, tmp_path / "founder-team-verification.json")
    payload = json.loads(path.read_text())

    assert path.name == "founder-team-verification.json"
    assert payload["summary"]["eligible"] == 1
    assert payload["items"][0]["name"] == "Copperhelm"
