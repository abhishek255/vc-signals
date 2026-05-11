import json
import subprocess
import sys
from pathlib import Path

from discovery_maturity_evidence import (
    build_maturity_queries,
    classify_maturity_evidence,
    extract_maturity_targets,
    normalize_domain,
    run_maturity_evidence_bakeoff,
    same_domain_or_subdomain,
    write_maturity_evidence_artifact,
)


def test_extract_maturity_targets_dedupes_verified_domains():
    score_payload = {
        "accepted_leads": [
            {"display_name": "Lyzr", "domain": "lyzr.ai", "query_family": "official_company_page"},
            {"display_name": "Lyzr", "domain": "www.lyzr.ai", "query_family": "movement_platform"},
            {"display_name": "Braintrust", "domain": "braintrust.dev", "query_family": "official_company_page"},
        ]
    }

    targets = extract_maturity_targets(score_payload)

    assert [target["domain"] for target in targets] == ["braintrust.dev", "lyzr.ai"]
    lyzr = next(target for target in targets if target["domain"] == "lyzr.ai")
    assert lyzr["company_name"] == "Lyzr"
    assert lyzr["source_query_families"] == ["movement_platform", "official_company_page"]


def test_extract_maturity_targets_prioritizes_eval_targets_and_strong_families():
    score_payload = {
        "target_results": [
            {"target_name": "Lyzr", "target_domain": "lyzr.ai", "found": True},
            {"target_name": "Braintrust", "expected_domain": "braintrust.dev", "found": True},
        ],
        "accepted_leads": [
            {"display_name": "Wiz", "domain": "wiz.io", "query_family": "official_company_page"},
            {"display_name": "Lyzr", "domain": "lyzr.ai", "query_family": "movement_platform"},
            {"display_name": "Braintrust", "domain": "braintrust.dev", "query_family": "official_company_page"},
        ],
    }

    priority = [
        row.get("target_domain") or row.get("domain") or row.get("expected_domain")
        for row in score_payload["target_results"]
        if row.get("found")
    ]
    targets = extract_maturity_targets(score_payload, priority_domains=priority)

    assert [target["domain"] for target in targets][:2] == ["lyzr.ai", "braintrust.dev"]


def test_normalize_domain_handles_urls_paths_and_subdomains():
    assert normalize_domain("https://www.lyzr.ai/blog/foo") == "lyzr.ai"
    assert normalize_domain("https://blog.lyzr.ai/foo") == "blog.lyzr.ai"
    assert same_domain_or_subdomain("blog.lyzr.ai", "lyzr.ai") is True
    assert same_domain_or_subdomain("fake-lyzr.ai.evil.com", "lyzr.ai") is False


def test_build_maturity_queries_are_exact_company_domain_scoped():
    targets = [{"company_name": "Lyzr", "domain": "lyzr.ai", "source_query_families": ["movement_platform"]}]

    queries = build_maturity_queries(targets)

    assert queries
    assert all("Lyzr" in query["topic"] for query in queries)
    assert all("lyzr.ai" in query["topic"] for query in queries)
    assert {query["query_kind"] for query in queries} == {
        "funding_stage",
        "late_stage_or_valuation",
        "acquisition",
        "founder_stage_context",
    }


def test_build_maturity_queries_do_not_create_broad_market_search():
    queries = build_maturity_queries([{"company_name": "Lyzr", "domain": "lyzr.ai"}])

    forbidden = ["best startups", "companies to watch", "market map", "top startups"]
    assert all(not any(term in query["topic"].lower() for term in forbidden) for query in queries)


def test_run_maturity_evidence_bakeoff_uses_current_provider_wrapper_shape():
    queries = [
        {
            "query_id": "maturity:lyzr.ai:funding_stage",
            "topic": '"Lyzr" "lyzr.ai" funding seed',
            "domain": "lyzr.ai",
            "company_name": "Lyzr",
            "query_kind": "funding_stage",
        }
    ]
    seen = {}

    def runner(provider, query, **_kwargs):
        seen["query_is_dict"] = isinstance(query, dict)
        return {
            "provider": provider,
            "query_id": query["query_id"],
            "query": query["topic"],
            "items": [{"title": "Lyzr raises seed", "url": "https://www.lyzr.ai/", "snippet": "Lyzr raised a seed round."}],
            "skipped": False,
            "cache_status": "hit",
        }

    result = run_maturity_evidence_bakeoff(queries, providers=["brave"], provider_runner=runner)

    assert seen["query_is_dict"] is True
    assert result["summary"]["queries_run"] == 1
    assert result["summary"]["cache_hits"] == 1
    assert result["provider_runs"][0]["items"][0]["title"] == "Lyzr raises seed"


def test_run_maturity_evidence_bakeoff_respects_query_cap():
    queries = [
        {
            "query_id": f"q{i}",
            "topic": f'"Lyzr" "lyzr.ai" funding {i}',
            "domain": "lyzr.ai",
            "company_name": "Lyzr",
            "query_kind": "funding_stage",
        }
        for i in range(3)
    ]

    result = run_maturity_evidence_bakeoff(
        queries,
        providers=["brave"],
        provider_runner=lambda *_args, **_kwargs: {"items": [], "skipped": False},
        max_queries_per_provider=1,
    )

    assert result["summary"]["queries_available"] == 3
    assert result["summary"]["runs"] == 1
    assert result["summary"]["partial_eval"] is True


def test_classify_maturity_evidence_detects_seed_stage():
    targets = [{"company_name": "Lyzr", "domain": "lyzr.ai"}]
    runs = [
        {
            "domain": "lyzr.ai",
            "company_name": "Lyzr",
            "items": [{"title": "Lyzr raises seed", "url": "https://www.lyzr.ai/", "snippet": "Lyzr raised a seed round."}],
            "skipped": False,
        }
    ]

    result = classify_maturity_evidence(targets, runs)

    assert result["domains"]["lyzr.ai"]["maturity_status"] == "seed_to_series_b"
    assert result["domains"]["lyzr.ai"]["lead_route"] == "sourcing_candidate"
    assert result["domains"]["lyzr.ai"]["maturity_evaluation_status"] == "evaluated_with_evidence"


def test_classify_maturity_evidence_detects_category_anchor():
    targets = [{"company_name": "Wiz", "domain": "wiz.io"}]
    runs = [
        {
            "domain": "wiz.io",
            "company_name": "Wiz",
            "items": [{"title": "Wiz raises $1B", "url": "https://www.wiz.io/", "snippet": "Wiz raised a $1B round and is a category leader."}],
            "skipped": False,
        }
    ]

    result = classify_maturity_evidence(targets, runs)

    assert result["domains"]["wiz.io"]["maturity_status"] == "likely_too_late"
    assert result["domains"]["wiz.io"]["lead_route"] == "category_context"


def test_classify_maturity_evidence_keeps_unknown_when_no_matching_evidence():
    targets = [{"company_name": "Lyzr", "domain": "lyzr.ai"}]
    runs = [
        {
            "domain": "lyzr.ai",
            "company_name": "Lyzr",
            "items": [{"title": "Unrelated company raises seed", "url": "https://example.com/", "snippet": "Example raised seed."}],
            "skipped": False,
        }
    ]

    result = classify_maturity_evidence(targets, runs)

    assert result["domains"]["lyzr.ai"]["maturity_status"] == "unknown"
    assert result["domains"]["lyzr.ai"]["maturity_evaluation_status"] == "evaluated_no_maturity_evidence"
    assert result["domains"]["lyzr.ai"]["maturity_result_reason"] == "domains_with_no_maturity_results"


def test_official_homepage_without_maturity_terms_is_not_maturity_evidence():
    targets = [{"company_name": "Lyzr", "domain": "lyzr.ai"}]
    runs = [
        {
            "domain": "lyzr.ai",
            "company_name": "Lyzr",
            "items": [{"title": "Lyzr - AI agent platform", "url": "https://www.lyzr.ai/", "snippet": "Lyzr helps launch AI agents."}],
            "skipped": False,
        }
    ]

    result = classify_maturity_evidence(targets, runs)

    assert result["domains"]["lyzr.ai"]["maturity_status"] == "unknown"
    assert result["domains"]["lyzr.ai"]["maturity_evaluation_status"] == "evaluated_no_maturity_evidence"
    assert result["domains"]["lyzr.ai"]["maturity_result_reason"] == "domains_with_matching_results_but_no_maturity_terms"


def test_generic_seed_word_does_not_count_as_funding_stage():
    targets = [{"company_name": "Lyzr", "domain": "lyzr.ai"}]
    runs = [
        {
            "domain": "lyzr.ai",
            "company_name": "Lyzr",
            "items": [{"title": "Lyzr seed prompts", "url": "https://www.lyzr.ai/", "snippet": "Seed prompts for AI agents."}],
            "skipped": False,
        }
    ]

    result = classify_maturity_evidence(targets, runs)

    assert result["domains"]["lyzr.ai"]["maturity_status"] == "unknown"


def test_write_maturity_evidence_artifact(tmp_path):
    payload = {
        "targets": [{"company_name": "Lyzr", "domain": "lyzr.ai"}],
        "queries": [{"query_id": "q1"}],
        "bakeoff": {"summary": {"queries_run": 1}},
        "classification": {"domains": {"lyzr.ai": {"maturity_status": "seed_to_series_b"}}},
    }

    path = write_maturity_evidence_artifact(payload, tmp_path)

    assert path.name == "maturity-evidence-bakeoff.json"
    assert path.exists()


def test_cli_writes_artifact_with_empty_provider_list(tmp_path):
    repo_root = Path(__file__).resolve().parents[4]
    lead_eval = tmp_path / "lead-discovery-eval.json"
    lead_eval.write_text(
        json.dumps(
            {
                "score": {
                    "accepted_leads": [{"display_name": "Lyzr", "domain": "lyzr.ai", "query_family": "official_company_page"}],
                    "target_results": [{"target_name": "Lyzr", "target_domain": "lyzr.ai", "found": True}],
                }
            }
        )
    )
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / ".claude" / "skills" / "vc-signals" / "scripts" / "discovery_maturity_evidence.py"),
            "--lead-discovery-eval",
            str(lead_eval),
            "--output-dir",
            str(output_dir),
            "--providers",
            "",
            "--max-targets",
            "2",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "maturity-evidence-bakeoff.json").exists()
