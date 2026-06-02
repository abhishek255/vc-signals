import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from discovery_yield_eval import (
    DISCOVERY_QUERY_FAMILIES,
    LeadDiscoveryEvalTarget,
    build_movement_only_queries,
    provider_bakeoff,
    route_rank,
    score_provider_items_against_targets,
    validate_eval_targets,
    write_discovery_yield_artifacts,
)


def _target(**overrides):
    payload = {
        "name": "Lyzr",
        "aliases": ["Lyzr AI"],
        "domain": "lyzr.ai",
        "expected_movement": "Agent reliability and evals",
        "movement_aliases": [
            "AI agent reliability",
            "agent evals",
            "AI agent production",
        ],
        "market_sector": "AI Infra",
        "maturity_expectation": "seed_to_series_b",
        "expected_route": "sourcing_candidate",
        "last_verified_at": "2026-05-10",
        "verification_notes": "Synthetic test target.",
    }
    payload.update(overrides)
    return LeadDiscoveryEvalTarget.from_dict(payload)


def test_validate_eval_targets_requires_domain():
    target = _target(domain="")

    with pytest.raises(ValueError, match="domain"):
        validate_eval_targets([target])


def test_validate_eval_targets_rejects_alias_target_leakage():
    target = _target(movement_aliases=["Lyzr agent reliability"])

    with pytest.raises(ValueError, match="movement_aliases"):
        validate_eval_targets([target])


def test_build_movement_only_queries_covers_required_families():
    queries = build_movement_only_queries([_target()])

    families = {query["query_family"] for query in queries}
    assert families == set(DISCOVERY_QUERY_FAMILIES)
    assert all(query["target_name"] == "" for query in queries)


def test_movement_only_queries_do_not_inject_target_names_or_domains():
    target = _target()
    queries = build_movement_only_queries([target])

    for query in queries:
        topic = query["topic"].lower()
        assert "lyzr" not in topic
        assert "lyzr.ai" not in topic


def test_query_generation_deduplicates_normalized_topics():
    target = _target(
        movement_aliases=[
            "AI agent reliability",
            "AI agent reliability ",
            "ai agent reliability",
        ]
    )

    queries = build_movement_only_queries([target])
    topics = [query["normalized_topic"] for query in queries]

    assert len(topics) == len(set(topics))


def test_provider_bakeoff_uses_same_queries_for_each_provider():
    queries = build_movement_only_queries([_target()], max_aliases_per_target=0)

    def runner(provider, query, **_kwargs):
        return {
            "provider": provider,
            "query_id": query["query_id"],
            "query": query["topic"],
            "items": [],
            "skipped": False,
            "skip_reason": "",
            "cache_status": "miss",
            "latency_ms": 1,
            "cost_usd": 0.0,
            "capabilities": {"snippet_only": True},
        }

    result = provider_bakeoff(
        queries,
        providers=["brave", "you"],
        provider_runner=runner,
        max_queries_per_provider=999,
    )

    brave_queries = [run["query"] for run in result["provider_runs"] if run["provider"] == "brave"]
    you_queries = [run["query"] for run in result["provider_runs"] if run["provider"] == "you"]
    assert brave_queries == you_queries


def test_provider_bakeoff_records_skipped_provider():
    queries = build_movement_only_queries([_target()], max_aliases_per_target=0)[:1]

    def runner(provider, query, **_kwargs):
        return {
            "provider": provider,
            "query_id": query["query_id"],
            "query": query["topic"],
            "items": [],
            "skipped": True,
            "skip_reason": "missing_api_key",
            "cache_status": "skip",
            "latency_ms": 0,
            "cost_usd": 0.0,
            "capabilities": {"snippet_only": True},
        }

    result = provider_bakeoff(
        queries,
        providers=["brave"],
        provider_runner=runner,
        max_queries_per_provider=1,
    )

    assert result["provider_runs"][0]["skipped"] is True
    assert result["provider_runs"][0]["skip_reason"] == "missing_api_key"
    assert result["summary"]["skipped_runs"] == 1


def test_provider_result_does_not_count_without_verified_domain():
    target = _target()
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent reliability startup founder launch",
            "query_id": "q1",
            "query_family": "launch_stealth",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "TechCrunch: Lyzr launches AI agent reliability platform",
                    "url": "https://techcrunch.com/2026/05/01/lyzr-ai-agent-reliability/",
                    "snippet": "Lyzr says it is helping teams ship AI agents.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["verified_domains_found"] == 0
    assert result["metrics"]["credible_early_stage_leads"] == 0


def test_official_domain_with_unknown_maturity_counts_as_research_worthy_not_early_stage():
    target = _target(expected_route="research_deeper", maturity_expectation="unknown")
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production startup founder launch",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr - Take your AI agents to production, faster",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr helps teams build, evaluate, and launch production AI agents.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["verified_domains_found"] == 1
    assert result["metrics"]["research_worthy_verified_domains"] == 1
    assert result["metrics"]["maturity_unknown_research_deeper"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 0
    assert result["metrics"]["maturity_adjusted_credible_early_stage_leads_per_100_queries"] == 0
    assert result["target_results"][0]["evaluation_incomplete"] is False
    assert result["target_results"][0]["maturity_evaluation_status"] == "evaluated_no_maturity_evidence"


def test_seed_stage_evidence_counts_as_maturity_confirmed_early_stage():
    target = _target(expected_route="sourcing_candidate", maturity_expectation="seed_to_series_b")
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production seed startup",
            "query_id": "q1",
            "query_family": "seed_funding",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr raises seed round for AI agent production platform",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr is a startup building production AI agent tooling after a seed round.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["verified_domains_found"] == 1
    assert result["metrics"]["maturity_confirmed_early_stage"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 1
    assert result["metrics"]["maturity_adjusted_credible_early_stage_leads_per_100_queries"] == 100
    assert result["target_results"][0]["actual_maturity"] == "seed_to_series_b"
    assert result["target_results"][0]["maturity_evaluation_status"] == "evaluated_with_evidence"


def test_series_c_large_round_does_not_count_as_credible_early_stage():
    target = _target(
        name="Wiz",
        aliases=[],
        domain="wiz.io",
        expected_movement="AI cloud security",
        movement_aliases=["cloud security"],
        maturity_expectation="likely_too_late_or_consensus",
        expected_route="category_context",
    )
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI cloud security startup platform",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": target.expected_movement,
            "market_sector": "Cybersecurity",
            "items": [
                {
                    "title": "Wiz - Cloud Security Platform",
                    "url": "https://www.wiz.io/",
                    "snippet": "Wiz is a category leader that raised a $1B financing round.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["verified_domains_found"] == 1
    assert result["metrics"]["likely_too_late_found"] == 1
    assert result["metrics"]["category_anchors_found"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 0
    assert result["target_results"][0]["over_promoted"] is False


def test_net_new_mature_domain_does_not_count_as_early_stage():
    target = _target()
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI cloud security startup platform",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": "AI cloud security",
            "market_sector": "Cybersecurity",
            "items": [
                {
                    "title": "Darktrace - AI Cybersecurity",
                    "url": "https://www.darktrace.com/",
                    "snippet": "Darktrace is a market leader in AI cloud security with enterprise scale.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["net_new_verified_domains"] == 1
    assert result["metrics"]["net_new_credible_early_stage_leads"] == 0
    assert result["metrics"]["likely_too_late_found"] == 1


def test_known_target_precision_penalizes_over_aggressive_route():
    target = _target(
        name="Braintrust",
        aliases=[],
        domain="braintrust.dev",
        expected_movement="LLM evals and observability",
        movement_aliases=["LLM evals"],
        maturity_expectation="likely_too_late_or_consensus",
        expected_route="category_context",
    )
    provider_runs = [
        {
            "provider": "brave",
            "query": "LLM evals startup founder launch",
            "query_id": "q1",
            "query_family": "movement_startup",
            "movement": target.expected_movement,
            "market_sector": "AI Infra",
            "items": [
                {
                    "title": "Braintrust - LLM evals and observability",
                    "url": "https://www.braintrust.dev/",
                    "snippet": "Braintrust helps teams evaluate AI applications and LLM systems.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["known_target_matches"] == 1
    assert result["target_results"][0]["over_promoted"] is True
    assert result["metrics"]["known_target_precision"] == 0


def test_duplicate_domain_does_not_inflate_credible_leads_metric():
    target = _target(expected_route="research_deeper", maturity_expectation="unknown")
    item = {
        "title": "Lyzr - Take your AI agents to production, faster",
        "url": "https://www.lyzr.ai/",
        "snippet": "Lyzr helps teams build, evaluate, and launch production AI agents.",
    }
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production startup founder launch",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [item, item],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert len(result["accepted_leads"]) == 2
    assert result["metrics"]["verified_domains_found"] == 1
    assert result["metrics"]["research_worthy_verified_domains"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 0
    assert result["metrics"]["credible_early_stage_leads_per_100_queries"] == 0
    assert result["target_results"][0]["provider"] == "brave"
    assert result["target_results"][0]["query_family"] == "official_company_page"


def test_same_run_mature_item_does_not_contaminate_other_company_maturity():
    target = _target()
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent reliability startup founder launch",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr - AI agent platform",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr helps teams build and launch production AI agents.",
                },
                {
                    "title": "Braintrust - AI agent evals platform",
                    "url": "https://www.braintrust.dev/",
                    "snippet": "Braintrust is a category leader for AI agent evals with a $1B valuation signal.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["target_results"][0]["actual_maturity"] == "unknown"
    assert result["target_results"][0]["actual_route"] == "research_deeper"
    assert result["metrics"]["likely_too_late_found"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 0


def test_provider_result_items_shape_is_supported():
    target = _target()
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production seed startup",
            "query_id": "q1",
            "query_family": "seed_funding",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "provider_result": {
                "items": [
                    {
                        "title": "Lyzr raises seed round for AI agent production platform",
                        "url": "https://www.lyzr.ai/",
                        "snippet": "Lyzr raised a seed round for AI agent production.",
                    }
                ]
            },
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["verified_domains_found"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 1


def test_query_family_summary_uses_unique_maturity_adjusted_domains(tmp_path):
    target = _target(expected_route="sourcing_candidate")
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production seed startup",
            "query_id": "q1",
            "query_family": "seed_funding",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr raises seed round",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr raised a seed round for AI agent production.",
                },
                {
                    "title": "Lyzr raises seed round",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr raised a seed round for AI agent production.",
                },
            ],
            "skipped": False,
        },
        {
            "provider": "brave",
            "query": "AI agent production platform",
            "query_id": "q2",
            "query_family": "movement_platform",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Braintrust - AI agent evals platform",
                    "url": "https://www.braintrust.dev/",
                    "snippet": "Braintrust is a category leader for AI agent evals.",
                }
            ],
            "skipped": False,
        },
    ]
    score = score_provider_items_against_targets(provider_runs, [target])
    payload = {"eval_targets": [target.to_dict()], "queries": [], "bakeoff": {"provider_runs": provider_runs}, "score": score}

    write_discovery_yield_artifacts(payload, tmp_path)
    family_payload = json.loads((tmp_path / "query-family-bakeoff.json").read_text())
    rows = {row["query_family"]: row for row in family_payload["families"]}

    assert rows["seed_funding"]["verified_domains"] == 1
    assert rows["seed_funding"]["maturity_confirmed_early_stage_domains"] == 1
    assert rows["movement_platform"]["maturity_confirmed_early_stage_domains"] == 0
    assert rows["movement_platform"]["category_anchor_domains"] == 1


def test_route_rank_handles_unknown_and_empty_routes_explicitly():
    assert route_rank("") == -1
    assert route_rank("unknown") == -1
    assert route_rank("assign_owner") > route_rank("sourcing_candidate")


def test_external_maturity_evidence_updates_score_metrics():
    target = _target(expected_route="sourcing_candidate")
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production platform official",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr - AI agent platform",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr helps teams launch production AI agents.",
                }
            ],
            "skipped": False,
        }
    ]
    maturity_evidence = {
        "domains": {
            "lyzr.ai": {
                "maturity_status": "seed_to_series_b",
                "maturity_evaluation_status": "evaluated_with_evidence",
                "lead_route": "sourcing_candidate",
                "likely_too_late": False,
                "category_anchor": False,
                "maturity_basis": ["seed_or_pre_seed"],
                "maturity_evidence_urls": ["https://www.lyzr.ai/"],
            }
        }
    }

    result = score_provider_items_against_targets(provider_runs, [target], maturity_evidence=maturity_evidence)

    assert result["metrics"]["credible_early_stage_leads"] == 1
    assert result["target_results"][0]["actual_maturity"] == "seed_to_series_b"


def test_external_maturity_evidence_keeps_non_matching_domains_unchanged():
    target = _target(expected_route="research_deeper")
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production platform official",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr - AI agent platform",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr helps teams launch production AI agents.",
                }
            ],
            "skipped": False,
        }
    ]
    maturity_evidence = {
        "domains": {
            "braintrust.dev": {
                "maturity_status": "likely_too_late",
                "maturity_evaluation_status": "evaluated_with_evidence",
                "lead_route": "category_context",
            }
        }
    }

    result = score_provider_items_against_targets(provider_runs, [target], maturity_evidence=maturity_evidence)

    assert result["metrics"]["credible_early_stage_leads"] == 0
    assert result["target_results"][0]["actual_maturity"] == "unknown"


def test_write_discovery_yield_artifacts(tmp_path):
    payload = {
        "eval_targets": [_target().to_dict()],
        "queries": build_movement_only_queries([_target()], max_aliases_per_target=0)[:1],
        "bakeoff": {"provider_runs": [], "summary": {}},
        "score": {"metrics": {"credible_early_stage_leads_per_100_queries": 0}},
    }

    written = write_discovery_yield_artifacts(payload, tmp_path)

    assert (tmp_path / "lead-discovery-eval.json").exists()
    assert (tmp_path / "provider-bakeoff.json").exists()
    assert (tmp_path / "query-family-bakeoff.json").exists()
    assert (tmp_path / "discovery-yield-summary.md").exists()
    assert len(written) == 4


def test_discovery_eval_queries_are_movement_specific_not_broad_market_search():
    queries = build_movement_only_queries([_target()], max_aliases_per_target=0)

    forbidden = ["best startups", "top startups", "companies to watch", "market map"]
    for query in queries:
        topic = query["topic"].lower()
        assert all(term not in topic for term in forbidden)
        assert "agent reliability and evals".lower() in topic or "yc" in topic


def test_discovery_eval_does_not_use_forbidden_sources():
    queries = build_movement_only_queries([_target()], max_aliases_per_target=0)

    forbidden = ["site:linkedin.com", "site:x.com", "site:twitter.com", "site:producthunt.com"]
    for query in queries:
        topic = query["topic"].lower()
        assert all(term not in topic for term in forbidden)


def test_discovery_yield_cli_does_not_write_weekly_preview(tmp_path):
    skill_root = Path(__file__).resolve().parents[1]
    weekly_preview = tmp_path / "weekly-preview.md"
    weekly_preview.write_text("unchanged\n")
    output_dir = tmp_path / "out"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(skill_root / "scripts")
    result = subprocess.run(
        [
            sys.executable,
            str(skill_root / "scripts" / "discovery_yield_eval.py"),
            "--output-dir",
            str(output_dir),
            "--eval-mode",
            "smoke",
            "--providers",
            "",
            "--weekly-preview-path",
            str(weekly_preview),
        ],
        cwd=skill_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert weekly_preview.read_text() == "unchanged\n"
    assert (output_dir / "lead-discovery-eval.json").exists()
