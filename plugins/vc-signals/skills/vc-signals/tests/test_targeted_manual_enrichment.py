import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_build_target_queries_focuses_linkedin_and_funding_gaps():
    from targeted_manual_enrichment import build_target_queries

    queries = build_target_queries(
        {
            "name": "AgentFence",
            "domain": "agentfence.dev",
            "missing_evidence": ["company_linkedin_missing", "stage_or_funding_missing"],
        },
        queries_per_target=2,
    )

    assert len(queries) == 2
    assert "LinkedIn" in queries[0]["query"]
    assert "Crunchbase" in queries[1]["query"]
    assert '"AgentFence"' in queries[0]["query"]
    assert '"AgentFence" "agentfence.dev"' in queries[1]["query"]


def test_build_target_queries_cover_domain_and_commercial_gaps():
    from targeted_manual_enrichment import build_target_queries

    queries = build_target_queries(
        {
            "name": "AgentFence",
            "domain": "",
            "missing_evidence": [
                "official_domain_missing",
                "commercial_or_customer_signal_missing",
                "pricing_docs_or_careers_missing",
            ],
        },
        queries_per_target=4,
    )

    kinds = [query["kind"] for query in queries]
    assert kinds == [
        "official_domain",
        "linkedin_company_and_founders",
        "commercial_customer_proof",
        "pricing_docs_careers",
    ]
    assert "official website" in queries[0]["query"]
    assert "pricing" in queries[2]["query"]
    assert "careers" in queries[3]["query"]


def test_load_targets_falls_back_to_source_yield_evidence_gap_queue(tmp_path):
    from targeted_manual_enrichment import _load_targets

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "source-yield-validation-report.json").write_text(
        json.dumps(
            {
                "evidence_gap_queue": [
                    {
                        "name": "AgentFence",
                        "domain": "agentfence.dev",
                        "source_lane": "Product Hunt",
                        "missing_evidence": ["founder_team_missing"],
                        "next_step": "Find founder/team evidence.",
                    }
                ]
            }
        )
    )

    targets = _load_targets(run_dir)

    assert targets[0]["name"] == "AgentFence"
    assert targets[0]["recommended_next_step"] == "Find founder/team evidence."


def test_load_targets_can_force_source_yield_gap_queue_when_manual_targets_exist(tmp_path):
    from targeted_manual_enrichment import _load_targets

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manual-enrichment-targets.json").write_text(json.dumps({"items": [{"name": "ManualTarget"}]}))
    (run_dir / "source-yield-validation-report.json").write_text(
        json.dumps({"evidence_gap_queue": [{"name": "GapTarget", "next_step": "Resolve evidence."}]})
    )

    targets = _load_targets(run_dir, target_source="evidence_gap_queue")

    assert targets[0]["name"] == "GapTarget"


def test_load_targets_can_target_partner_review_companies(tmp_path):
    from targeted_manual_enrichment import _load_targets

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "source-yield-validation-report.json").write_text(
        json.dumps(
            {
                "partner_review_companies": [
                    {
                        "name": "AgentFence",
                        "domain": "agentfence.dev",
                        "source_lane": "Product Hunt",
                        "missing_evidence": ["stage_funding_or_headcount_missing"],
                        "recommended_manual_check": "Check stage and headcount.",
                    }
                ]
            }
        )
    )

    targets = _load_targets(run_dir, target_source="partner_review_companies")

    assert targets[0]["name"] == "AgentFence"
    assert targets[0]["domain"] == "agentfence.dev"
    assert targets[0]["recommended_next_step"] == "Check stage and headcount."


def test_enrich_targets_reports_public_search_hints_without_scraping():
    from targeted_manual_enrichment import enrich_targets

    calls = []

    def fake_query_runner(topic, **kwargs):
        calls.append((topic, kwargs))
        return {
            "items": [
                {
                    "title": "AgentFence company profile",
                    "url": "https://www.linkedin.com/company/agentfence",
                    "domain": "linkedin.com",
                    "snippet": "AgentFence has 12 employees and is hiring.",
                },
                {
                    "title": "AgentFence funding profile",
                    "url": "https://www.crunchbase.com/organization/agentfence",
                    "domain": "crunchbase.com",
                    "snippet": "Seed funding profile.",
                },
            ]
        }

    report = enrich_targets(
        [
            {
                "name": "AgentFence",
                "domain": "agentfence.dev",
                "missing_evidence": ["company_linkedin_missing", "headcount_missing", "stage_or_funding_missing"],
            }
        ],
        limit=1,
        queries_per_target=2,
        timeout_seconds=10,
        query_runner=fake_query_runner,
    )

    assert report["summary"]["queries_run"] == 2
    assert calls[0][1]["sources"] == "web"
    assert calls[0][1]["lookback_days"] == 365
    hints = report["items"][0]["evidence_hints"]
    assert hints["company_linkedin_candidates"][0]["url"] == "https://www.linkedin.com/company/agentfence"
    assert hints["funding_metadata_candidates"][0]["url"] == "https://www.crunchbase.com/organization/agentfence"
    assert report["items"][0]["manual_policy"].startswith("Public web-search assist")
    assert report["items"][0]["manual_workbench"]["exact_checks"]
    assert report["items"][0]["manual_workbench"]["promote_if_found"]
    assert report["items"][0]["manual_workbench"]["discard_if_not_found"]
    assert report["items"][0]["manual_workbench"]["suggested_decision"] == "manual_confirmation_needed"
    assert report["items"][0]["promote_if"]
    assert report["items"][0]["discard_if"]


def test_enrich_targets_marks_unresolved_manual_work_as_still_blocked():
    from targeted_manual_enrichment import enrich_targets

    report = enrich_targets(
        [
            {
                "name": "BuildGraph",
                "domain": "",
                "source_lane": "X",
                "missing_evidence": ["official_domain_missing", "founder_team_missing"],
                "recommended_next_step": "Resolve official domain first.",
            }
        ],
        limit=1,
        queries_per_target=2,
        query_runner=lambda *_args, **_kwargs: {"items": []},
    )

    row = report["items"][0]
    assert row["manual_workbench"]["suggested_decision"] == "still_blocked"
    assert "official_domain_still_missing" in row["unresolved_gaps"]
    assert row["recommended_manual_check"] == "Resolve official domain first."
    assert "official website" in " ".join(row["manual_workbench"]["exact_checks"]).lower()


def test_run_public_search_query_prefers_guarded_direct_provider(tmp_path, monkeypatch):
    import targeted_manual_enrichment

    calls = []

    monkeypatch.setattr(targeted_manual_enrichment, "load_provider_env_files", lambda: {})
    monkeypatch.setattr(targeted_manual_enrichment, "provider_available", lambda provider: provider == "exa")
    monkeypatch.setattr(targeted_manual_enrichment, "provider_cache_dir", lambda namespace: tmp_path / namespace)

    def fake_run_provider_query(provider, query, **kwargs):
        calls.append((provider, query, kwargs))
        return {
            "items": [{"title": "AgentFence", "url": "https://agentfence.dev"}],
            "skipped": False,
            "cost_usd": 0.001,
            "cache_status": "miss",
        }

    monkeypatch.setattr(targeted_manual_enrichment, "run_provider_query", fake_run_provider_query)

    payload = targeted_manual_enrichment.run_public_search_query(
        "AgentFence founder LinkedIn",
        provider_order="exa,brave",
        max_results=3,
        timeout_seconds=9,
    )

    assert payload["provider"] == "exa"
    assert payload["items"][0]["url"] == "https://agentfence.dev"
    assert calls[0][0] == "exa"
    assert calls[0][1]["query_family"] == "targeted_manual_enrichment"
    assert calls[0][2]["max_results"] == 3
    assert calls[0][2]["timeout_seconds"] == 9


def test_run_public_search_query_falls_back_to_last30days_only_without_direct_provider(monkeypatch):
    import targeted_manual_enrichment

    calls = []

    monkeypatch.setattr(targeted_manual_enrichment, "load_provider_env_files", lambda: {})
    monkeypatch.setattr(targeted_manual_enrichment, "provider_available", lambda provider: False)

    def fake_last30days(topic, **kwargs):
        calls.append((topic, kwargs))
        return {"items": [{"title": "Fallback", "url": "https://agentfence.dev"}], "warnings": []}

    monkeypatch.setattr(targeted_manual_enrichment, "run_last30days_query", fake_last30days)

    payload = targeted_manual_enrichment.run_public_search_query(
        "AgentFence founder LinkedIn",
        provider_order="exa,brave",
    )

    assert payload["items"][0]["title"] == "Fallback"
    assert calls[0][0] == "AgentFence founder LinkedIn"
    assert "direct_search_provider_unavailable_last30days_fallback" in payload["warnings"]
