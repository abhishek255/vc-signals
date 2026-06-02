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


def test_structured_provider_trial_can_target_alex_review_companies(tmp_path):
    from structured_provider_trial import build_structured_provider_trial

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "source-yield-validation-report.json",
        {
            "evidence_gap_queue": [
                {
                    "name": "GapOnly",
                    "domain": "gaponly.dev",
                    "source_lane": "Product Hunt",
                    "missing_evidence": ["founder_team_missing"],
                }
            ],
            "alex_review_companies": [
                {
                    "name": "AgentFence",
                    "domain": "agentfence.dev",
                    "source_lane": "Product Hunt",
                    "missing_evidence": ["stage_funding_or_headcount_missing"],
                    "recommended_manual_check": "Check Coresignal or Crunchbase-style metadata.",
                }
            ],
        },
    )

    report = build_structured_provider_trial(
        run_dir,
        env={},
        query_runner=lambda **_kwargs: {"items": []},
        limit=5,
        target_source="alex_review_companies",
    )

    assert report["summary"]["target_source"] == "alex_review_companies"
    assert report["summary"]["targets_considered"] == 1
    assert [item["name"] for item in report["items"]] == ["AgentFence"]
    assert report["items"][0]["recommended_next_step"] == "Check Coresignal or Crunchbase-style metadata."


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


def test_structured_provider_trial_uses_direct_coresignal_adapter_when_key_is_configured(tmp_path):
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
                    "missing_evidence": ["stage_funding_or_headcount_missing"],
                }
            ]
        },
    )

    calls = []

    def fake_direct_provider(provider, target, *, env):
        calls.append((provider, target["name"], env["CORESIGNAL_API_KEY"]))
        return {
            "provider": provider,
            "company_name": "AgentFence",
            "website": "https://agentfence.dev",
            "company_linkedin": "https://www.linkedin.com/company/agentfence",
            "headcount": "11-50",
            "founders": ["Ada Rao"],
            "source_url": "https://api.coresignal.example/company/agentfence",
        }

    report = build_structured_provider_trial(
        run_dir,
        env={"CORESIGNAL_API_KEY": "test-key"},
        query_runner=lambda **_kwargs: {"items": []},
        direct_provider_runner=fake_direct_provider,
        limit=1,
    )

    assert calls == [("Coresignal", "AgentFence", "test-key")]
    assert report["summary"]["direct_provider_access"] == ["Coresignal"]
    assert report["summary"]["direct_provider_targets_enriched"] == 1
    item = report["items"][0]
    assert item["provider_status"] == "direct_provider_key_configured"
    assert item["direct_provider_results"]["Coresignal"]["company_linkedin"] == "https://www.linkedin.com/company/agentfence"
    assert item["structured_hints"]["headcount_candidates"][0]["value"] == "11-50"
    assert item["structured_hints"]["founder_candidates"][0]["value"] == "Ada Rao"


def test_structured_provider_trial_calls_live_coresignal_enrich_when_key_and_domain_exist(tmp_path, monkeypatch):
    import structured_provider_trial
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
                    "missing_evidence": ["stage_funding_or_headcount_missing"],
                }
            ]
        },
    )

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "name": "AgentFence",
                "website": "https://agentfence.dev",
                "linkedin_url": "https://www.linkedin.com/company/agentfence",
                "employees_count": 18,
                "founders": [{"name": "Ada Rao"}],
                "last_funding_round_name": "Seed",
            }

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers, timeout))
        return FakeResponse()

    monkeypatch.setattr(structured_provider_trial.requests, "get", fake_get)

    report = build_structured_provider_trial(
        run_dir,
        env={"CORESIGNAL_API_KEY": "test-key"},
        query_runner=lambda **_kwargs: {"items": []},
        limit=1,
    )

    assert calls == [
        (
            "https://api.coresignal.com/cdapi/v2/company_clean/enrich?website=https%3A%2F%2Fagentfence.dev",
            {"accept": "application/json", "apikey": "test-key"},
            20,
        )
    ]
    result = report["items"][0]["direct_provider_results"]["Coresignal"]
    assert result["company_name"] == "AgentFence"
    assert result["website"] == "https://agentfence.dev"
    assert result["company_linkedin"] == "https://www.linkedin.com/company/agentfence"
    assert result["headcount"] == 18
    assert result["founders"] == ["Ada Rao"]
    assert result["stage"] == "Seed"
    assert report["summary"]["direct_provider_targets_enriched"] == 1


def test_structured_provider_trial_skips_live_coresignal_when_domain_missing(tmp_path):
    from structured_provider_trial import build_structured_provider_trial

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "source-yield-validation-report.json",
        {
            "evidence_gap_queue": [
                {
                    "name": "AgentFence",
                    "domain": "",
                    "source_lane": "Product Hunt",
                    "missing_evidence": ["official_domain_identity_not_confirmed"],
                }
            ]
        },
    )

    report = build_structured_provider_trial(
        run_dir,
        env={"CORESIGNAL_API_KEY": "test-key"},
        query_runner=lambda **_kwargs: {"items": []},
        limit=1,
    )

    result = report["items"][0]["direct_provider_results"]["Coresignal"]
    assert result["skipped"] is True
    assert result["skip_reason"] == "missing_domain_for_coresignal_enrich"
