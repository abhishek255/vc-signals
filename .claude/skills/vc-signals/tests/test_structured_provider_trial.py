from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def test_structured_provider_trial_reports_no_direct_access_and_builds_queries(tmp_path):
    from structured_provider_trial import build_structured_provider_trial

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "source-yield-validation-report.json",
        {
            "evidence_gap_queue": [
                {
                    "name": "AgentFence",
                    "domain": "agentfence.dev",
                    "source_lane": "Product Hunt",
                    "missing_evidence": [
                        "founder_team_missing",
                        "stage_funding_or_headcount_missing",
                    ],
                }
            ]
        },
    )

    report = build_structured_provider_trial(
        run_dir,
        env={},
        query_runner=lambda **_kwargs: {"items": []},
        limit=1,
    )

    assert report["summary"]["targets_considered"] == 1
    assert report["summary"]["direct_provider_access"] == []
    assert report["summary"]["manual_mode_providers"] == ["Crunchbase", "Coresignal", "LinkedIn"]
    assert report["items"][0]["provider_status"] == "manual_mode_no_direct_key"
    assert [query["provider"] for query in report["items"][0]["queries"]] == ["Crunchbase", "Coresignal", "LinkedIn"]


def test_structured_provider_trial_extracts_public_structured_hints(tmp_path):
    from structured_provider_trial import build_structured_provider_trial

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "source-yield-validation-report.json",
        {
            "evidence_gap_queue": [
                {
                    "name": "AgentFence",
                    "domain": "agentfence.dev",
                    "source_lane": "Product Hunt",
                    "missing_evidence": ["founder_team_missing"],
                }
            ]
        },
    )

    def fake_query_runner(**kwargs):
        if kwargs["topic"].startswith('"AgentFence" "agentfence.dev" Crunchbase'):
            return {
                "items": [
                    {
                        "title": "AgentFence - Funding, Financials, Valuation & Investors",
                        "url": "https://www.crunchbase.com/organization/agentfence",
                        "domain": "crunchbase.com",
                        "snippet": "AgentFence is a Seed company founded by Ada Rao with 14 employees.",
                    }
                ]
            }
        if kwargs["topic"].startswith('"AgentFence" "agentfence.dev" LinkedIn'):
            return {
                "items": [
                    {
                        "title": "AgentFence | LinkedIn",
                        "url": "https://www.linkedin.com/company/agentfence",
                        "domain": "linkedin.com",
                        "snippet": "AgentFence has 11-50 employees.",
                    }
                ]
            }
        return {"items": []}

    report = build_structured_provider_trial(
        run_dir,
        env={},
        query_runner=fake_query_runner,
        limit=1,
    )

    hints = report["items"][0]["structured_hints"]
    assert hints["funding_stage_candidates"][0]["url"] == "https://www.crunchbase.com/organization/agentfence"
    assert hints["company_linkedin_candidates"][0]["url"] == "https://www.linkedin.com/company/agentfence"
    assert report["summary"]["items_seen"] == 2
    assert report["summary"]["targets_with_structured_hints"] == 1


def test_structured_provider_trial_skips_repo_only_oss_market_signals(tmp_path):
    from structured_provider_trial import build_structured_provider_trial

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "source-yield-validation-report.json",
        {
            "evidence_gap_queue": [
                {
                    "name": "builder/example-open-source-list",
                    "domain": "github.com",
                    "source_lane": "GitHub",
                    "missing_evidence": ["official_domain_identity_not_confirmed"],
                },
                {
                    "name": "AgentFence",
                    "domain": "agentfence.dev",
                    "source_lane": "Product Hunt",
                    "missing_evidence": ["founder_team_missing"],
                },
            ]
        },
    )

    report = build_structured_provider_trial(
        run_dir,
        env={},
        query_runner=lambda **_kwargs: {"items": []},
        limit=15,
    )

    assert report["summary"]["targets_considered"] == 1
    assert [item["name"] for item in report["items"]] == ["AgentFence"]
