"""Tests for Phase 6B.3 HN candidate evidence recall audit."""

from __future__ import annotations

import json


def _enrichment_payload(*, rows):
    return {
        "phase": "Phase 6B.2-HN",
        "summary": {"assign_owner_rows": 0, "new_to_marathon_rows": 0},
        "enriched_outbound_candidates": list(rows),
        "product_context_rows": [{"name": "Deepgram CLI"}],
        "project_only_rows": [{"name": "AgentSwift"}],
        "rejected_rows": [],
        "reports": {},
    }


def _enriched_row(**overrides):
    row = {
        "name": "Veris",
        "canonical_name": "Veris",
        "official_domain": "veris.ai",
        "source_title": "Show HN: Veris - Agent sandboxes with simulated external services",
        "source_url": "https://news.ycombinator.com/item?id=48054313",
        "official_url": "https://veris.ai/sandbox",
        "hn_author": "jrm-veris",
        "hn_engagement": {"points": 9, "comments": 0},
        "identity_type": "verified_company",
        "identity_promotion_status": "promoted",
        "maturity_status": "seed_to_series_b",
        "maturity_basis": ["owner_evidence_stage_funding_signal"],
        "founder_team_evidence": [],
        "founders": [],
        "founder_profiles": [],
        "stage_funding_evidence": ["https://veris.ai/blog"],
        "customer_buyer_evidence": ["https://veris.ai"],
        "attio_status": "no_owner",
        "owner_readiness_score": 85,
        "missing_owner_evidence": ["no founder/team evidence"],
        "recommended_action": "Research deeper",
        "next_validation_step": "Find founder/team source",
        "assign_owner": False,
        "new_to_marathon": False,
    }
    row.update(overrides)
    return row


def test_audit_finds_named_founder_from_official_owner_evidence_page(tmp_path):
    from hn_candidate_evidence_audit import run_hn_candidate_evidence_audit

    official_page = (
        "<html><body><h1>Introducing Veris AI</h1>"
        "<p>Mehdi Jamei, Co-Founder and CEO and Andi Partovi, Co-Founder and CTO</p>"
        "<p>We're launching with $8.5M in seed funding.</p></body></html>"
    )
    row = _enriched_row()
    payload = _enrichment_payload(rows=[row])

    result = run_hn_candidate_evidence_audit(
        payload,
        page_fetcher=lambda url: official_page if url == "https://veris.ai/blog" else "<html>Veris</html>",
    )

    candidate = result["candidates"][0]
    assert candidate["canonical_name"] == "Veris"
    assert candidate["accepted_evidence"]["founder_team"][0]["name"] == "Mehdi Jamei"
    assert candidate["accepted_evidence"]["founder_team"][0]["source"] == "https://veris.ai/blog"
    assert "no founder/team evidence" not in candidate["final_missing_evidence"]
    assert candidate["audit_findings"]["official_page_founder_hit"] is True
    assert result["summary"]["founder_evidence_found"] == 1
    assert result["summary"]["assign_owner_rows"] == 0
    assert result["summary"]["new_to_marathon_rows"] == 0


def test_audit_uses_hn_body_text_for_named_founders_but_not_username():
    from hn_candidate_evidence_audit import run_hn_candidate_evidence_audit

    row = _enriched_row(
        name="Twill.ai",
        canonical_name="Twill.ai",
        official_domain="twill.ai",
        source_title="Launch HN: Twill.ai (YC S25) - Delegate to cloud agents, get back PRs",
        source_body="Hey HN, we're Willy Wonka and Dan Developer, co-founders of Twill.ai.",
        hn_author="danoandco",
        maturity_status="early_stage_context",
        maturity_basis=["accelerator_batch_evidence: YC S25"],
        stage_funding_evidence=[],
    )

    result = run_hn_candidate_evidence_audit(_enrichment_payload(rows=[row]))

    candidate = result["candidates"][0]
    names = {item["name"] for item in candidate["accepted_evidence"]["founder_team"]}
    assert names == {"Willy Wonka", "Dan Developer"}
    assert candidate["hn_source_text"]["available_fields"] == ["source_title", "source_body"]
    assert candidate["hn_author"] == "danoandco"
    assert "danoandco" not in names
    assert candidate["audit_findings"]["hn_body_founder_hit"] is True


def test_write_evidence_audit_artifacts_does_not_touch_weekly_preview(tmp_path):
    from hn_candidate_evidence_audit import (
        run_hn_candidate_evidence_audit,
        write_hn_candidate_evidence_audit_artifacts,
    )

    payload = run_hn_candidate_evidence_audit(_enrichment_payload(rows=[_enriched_row()]))
    paths = write_hn_candidate_evidence_audit_artifacts(payload, tmp_path)

    assert tmp_path / "hn-candidate-evidence-audit.json" in paths
    assert tmp_path / "hn-candidate-evidence-audit.md" in paths
    assert not (tmp_path / "weekly-preview.md").exists()
    saved = json.loads((tmp_path / "hn-candidate-evidence-audit.json").read_text())
    assert saved["phase"] == "Phase 6B.3-HN"
    assert saved["scope"].startswith("Audit only")
