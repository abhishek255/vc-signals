"""Tests for last30days-native company source audit helpers."""

from __future__ import annotations

import json
from pathlib import Path

from company_native_last30days import (
    build_last30days_native_queries,
    build_query_shape_debug_queries,
    build_native_audit_metrics,
    normalize_last30days_native_item,
    run_last30days_native_audit,
    run_query_shape_debug,
    summarize_last30days_native_audit,
    write_query_shape_debug_artifact,
    write_last30days_native_artifacts,
)


def test_build_last30days_native_queries_uses_last30days_sources():
    movements = [
        {
            "movement": "AI agent security",
            "market_sector": "Cybersecurity",
            "origin_row_ids": ["focus:burrow"],
        }
    ]

    queries = build_last30days_native_queries(movements, lanes=("launch_hn", "yc_company"))

    assert {query["lane"] for query in queries} == {"launch_hn", "yc_company"}
    assert all(query["retrieval_engine"] == "last30days" for query in queries)
    assert any(query["sources"] == "hackernews" for query in queries)
    assert any(query["sources"] == "grounding" for query in queries)
    assert any("Show HN" in query["topic"] for query in queries)
    assert any("Launch HN" in query["topic"] for query in queries)
    assert any("site:ycombinator.com/companies" in query["topic"] for query in queries)


def test_build_last30days_native_queries_filters_forbidden_lanes():
    queries = build_last30days_native_queries(
        [{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        lanes=("launch_hn", "yc_company", "x", "linkedin", "product_hunt"),
    )

    assert {query["lane"] for query in queries} == {"launch_hn", "yc_company"}
    assert all("linkedin" not in query["topic"].lower() for query in queries)
    assert all("product hunt" not in query["topic"].lower() for query in queries)


def test_phase6a_does_not_import_direct_retrieval_clients():
    script = Path(__file__).resolve().parents[1] / "scripts" / "company_native_last30days.py"
    assert script.exists()
    text = script.read_text()
    forbidden_tokens = [
        "company_native_source_bakeoff",
        "run_launch_hn_lane",
        "run_yc_company_lane",
        "run_provider_query",
        "discovery_search_providers",
        "hn.algolia.com/api",
        "api.search.brave.com",
        "ydc-index.io",
        "requests.get(",
        "requests.post(",
        "urlopen(",
    ]

    assert not [token for token in forbidden_tokens if token in text]


def test_summarize_last30days_native_audit_reports_identity_fields():
    query = {
        "id": "phase6:launch_hn:1",
        "lane": "launch_hn",
        "topic": "Show HN AI agent security",
        "sources": "hackernews",
    }
    payload = {
        "items": [
            {
                "source": "hackernews",
                "title": "Show HN: Burrow - Runtime Security for AI Agents",
                "url": "https://burrow.security",
                "hn_url": "https://news.ycombinator.com/item?id=47761957",
                "author": "saranshrana",
                "engagement": {"points": 123, "comments": 42},
                "_raw_fields_present": ["title", "url", "hn_url", "author", "engagement"],
                "_identity_fields_present_upstream": ["domain"],
                "domain": "burrow.security",
            }
        ],
        "warnings": [],
        "errors_by_source": {},
    }

    audit = summarize_last30days_native_audit([(query, payload)])

    row = audit["rows"][0]
    assert row["lane"] == "launch_hn"
    assert row["items_seen"] == 1
    assert row["identity_useful_fields_present"]["domain"] == 1
    assert row["field_presence"]["hn_url"] == 1
    assert audit["summary"]["items_seen"] == 1


def test_normalize_hn_item_with_outbound_url_becomes_company_candidate():
    query = {"lane": "launch_hn", "movement": "AI agent security", "market_sector": "Cybersecurity"}
    item = {
        "source": "hackernews",
        "title": "Show HN: Burrow - Runtime Security for AI Agents",
        "url": "https://burrow.security",
        "hn_url": "https://news.ycombinator.com/item?id=47761957",
        "outbound_url": "https://burrow.security",
        "domain": "burrow.security",
        "author": "saranshrana",
        "engagement": {"points": 123, "comments": 42},
    }

    lead = normalize_last30days_native_item(item, query)

    assert lead["kind"] == "company_candidate"
    assert lead["name"] == "Burrow"
    assert lead["domain"] == "burrow.security"
    assert lead["source_url"] == "https://news.ycombinator.com/item?id=47761957"
    assert lead["official_url"] == "https://burrow.security"
    assert lead["verification_basis"] == ["hn_launch_outbound_url"]


def test_normalize_hn_item_with_github_outbound_becomes_project_only():
    query = {"lane": "launch_hn", "movement": "AI agent security", "market_sector": "Cybersecurity"}
    item = {
        "source": "hackernews",
        "title": "Launch HN: AgentSec - Open source agent security scanner",
        "url": "https://github.com/example/agentsec",
        "hn_url": "https://news.ycombinator.com/item?id=47761958",
        "outbound_url": "https://github.com/example/agentsec",
        "domain": "github.com",
    }

    lead = normalize_last30days_native_item(item, query)

    assert lead["kind"] == "project_only"
    assert lead["domain"] == ""
    assert "hn_outbound_github_project_only" in lead["missing_evidence"]


def test_normalize_yc_item_without_website_marks_metadata_gap():
    query = {"lane": "yc_company", "movement": "AI agent security", "market_sector": "Cybersecurity"}
    item = {
        "source": "grounding",
        "title": "ShieldAgent | Y Combinator",
        "url": "https://www.ycombinator.com/companies/shieldagent",
        "snippet": "AI agent security company.",
    }

    lead = normalize_last30days_native_item(item, query)

    assert lead["kind"] == "needs_detail_enrichment"
    assert "yc_official_website_missing" in lead["missing_evidence"]


def test_normalize_yc_item_with_website_becomes_company_candidate():
    query = {"lane": "yc_company", "movement": "AI agent security", "market_sector": "Cybersecurity"}
    item = {
        "source": "grounding",
        "title": "ShieldAgent | Y Combinator",
        "url": "https://www.ycombinator.com/companies/shieldagent",
        "website": "https://shieldagent.ai",
        "founders": ["Jane Doe"],
        "batch": "W26",
        "description": "AI agent security company.",
    }

    lead = normalize_last30days_native_item(item, query)

    assert lead["kind"] == "company_candidate"
    assert lead["name"] == "ShieldAgent"
    assert lead["domain"] == "shieldagent.ai"
    assert lead["founders"] == ["Jane Doe"]
    assert lead["batch"] == "W26"
    assert lead["verification_basis"] == ["yc_company_official_website"]


def test_build_native_audit_metrics_counts_normalized_leads_without_quality_claims():
    leads = [
        {"kind": "company_candidate", "lane": "launch_hn", "domain": "burrow.security"},
        {
            "kind": "project_only",
            "lane": "launch_hn",
            "domain": "",
            "missing_evidence": ["hn_outbound_github_project_only"],
        },
        {"kind": "company_candidate", "lane": "yc_company", "domain": "shieldagent.ai"},
        {
            "kind": "needs_detail_enrichment",
            "lane": "yc_company",
            "domain": "",
            "missing_evidence": ["yc_official_website_missing"],
        },
    ]

    metrics = build_native_audit_metrics(leads, items_seen=20)

    assert metrics["company_candidates"] == 2
    assert metrics["unique_candidate_domains"] == 2
    assert metrics["candidate_domain_list"] == ["burrow.security", "shieldagent.ai"]
    assert metrics["project_only_leads"] == 1
    assert metrics["needs_detail_enrichment"] == 1
    assert metrics["candidate_domains_per_100_items"] == 10.0
    assert metrics["baseline_context"]["phase5_4_brave"]["verified_domains"] == 7
    assert "not directly comparable" in metrics["baseline_context"]["comparison_note"]
    assert "maturity_confirmed_early_stage" not in metrics


def test_run_last30days_native_audit_calls_adapter_with_source_specific_queries(tmp_path):
    queries = [
        {
            "id": "phase6:launch_hn:1",
            "lane": "launch_hn",
            "topic": "Show HN AI agent security",
            "sources": "hackernews",
            "movement": "AI agent security",
            "market_sector": "Cybersecurity",
            "lookback_days": 30,
        }
    ]
    calls = []

    def fake_run_query(**kwargs):
        calls.append(kwargs)
        return {
            "items": [
                {
                    "source": "hackernews",
                    "title": "Show HN: Burrow - Runtime Security for AI Agents",
                    "url": "https://burrow.security",
                    "hn_url": "https://news.ycombinator.com/item?id=47761957",
                    "domain": "burrow.security",
                }
            ],
            "warnings": [],
            "errors_by_source": {},
        }

    result = run_last30days_native_audit(queries, run_query_fn=fake_run_query, output_dir=tmp_path)

    assert calls[0]["topic"] == "Show HN AI agent security"
    assert calls[0]["sources"] == "hackernews"
    assert calls[0]["store"] is True
    hn_plan = json.loads(calls[0]["plan"])
    assert hn_plan["subqueries"][0]["search_query"] == "Show HN AI agent security"
    assert hn_plan["subqueries"][0]["sources"] == ["hackernews"]
    assert result["audit"]["summary"]["items_seen"] == 1
    assert result["normalized_leads"]["summary"]["unique_candidate_domains"] == 1
    assert tmp_path.joinpath("raw-last30days", "phase6-launch_hn-1.json").exists()


def test_run_last30days_native_audit_uses_evergreen_plan_for_yc_queries(tmp_path):
    queries = [
        {
            "id": "phase6:yc_company:1",
            "lane": "yc_company",
            "topic": "site:ycombinator.com/companies AI agent security",
            "sources": "grounding",
            "movement": "AI agent security",
            "market_sector": "Cybersecurity",
            "lookback_days": 30,
            "web_backend": "brave",
        }
    ]
    calls = []

    def fake_run_query(**kwargs):
        calls.append(kwargs)
        return {"items": [], "warnings": [], "errors_by_source": {}}

    run_last30days_native_audit(queries, run_query_fn=fake_run_query, output_dir=tmp_path)

    plan = json.loads(calls[0]["plan"])
    assert plan["freshness_mode"] == "evergreen_ok"
    assert plan["subqueries"][0]["search_query"] == "site:ycombinator.com/companies AI agent security"
    assert plan["subqueries"][0]["sources"] == ["grounding"]


def test_write_last30days_native_artifacts_does_not_touch_weekly_preview(tmp_path):
    payload = {
        "audit": {"summary": {"items_seen": 1}, "rows": []},
        "normalized_leads": {
            "summary": {"unique_candidate_domains": 1},
            "company_candidates": [],
            "project_only_leads": [],
        },
    }

    paths = write_last30days_native_artifacts(payload, tmp_path)

    assert tmp_path.joinpath("company-native-source-audit.json") in paths
    assert tmp_path.joinpath("company-native-normalized-leads.json") in paths
    assert tmp_path.joinpath("company-native-source-audit.md") in paths
    assert not tmp_path.joinpath("weekly-preview.md").exists()
    assert "Phase 6A audit only" in tmp_path.joinpath("company-native-source-audit.md").read_text()


def test_cli_loads_movements_from_weekly_focus(tmp_path):
    from company_native_last30days import load_movements_from_weekly_run

    run_dir = tmp_path / "weekly"
    run_dir.mkdir()
    run_dir.joinpath("weekly-focus.json").write_text(
        json.dumps(
            {
                "market_movements": [
                    {
                        "movement": "AI agent security",
                        "market_sector": "Cybersecurity",
                        "origin_row_ids": ["m1"],
                    }
                ],
                "research_deeper": [
                    {"id": "r1", "market_movement": "Agent reliability", "market_sector": "AI Infra"}
                ],
            }
        )
    )

    movements = load_movements_from_weekly_run(run_dir)

    assert [row["movement"] for row in movements] == ["AI agent security", "Agent reliability"]


def test_build_query_shape_debug_queries_includes_broad_and_movement_shapes():
    queries = build_query_shape_debug_queries(["AI agent security"], lookback_days=30)

    topics = [query["topic"] for query in queries]
    assert "Show HN" in topics
    assert "Launch HN" in topics
    assert "Show HN AI" in topics
    assert "Show HN AI agent security" in topics
    assert "Show HN AI agent security startup" in topics
    assert "site:ycombinator.com/companies AI" in topics
    assert 'site:ycombinator.com/companies "AI agent security"' in topics
    assert all(query["retrieval_engine"] == "last30days" for query in queries)
    assert any(query["sources"] == "hackernews" for query in queries)
    assert any(query["sources"] == "grounding" for query in queries)


def test_run_query_shape_debug_records_item_counts_fields_and_top_items(tmp_path):
    queries = [
        {
            "id": "shape:hn:1",
            "lane": "hn_shape",
            "topic": "Show HN AI",
            "sources": "hackernews",
            "lookback_days": 30,
            "retrieval_engine": "last30days",
        },
        {
            "id": "shape:yc:1",
            "lane": "yc_shape",
            "topic": "site:ycombinator.com/companies AI",
            "sources": "grounding",
            "lookback_days": 30,
            "retrieval_engine": "last30days",
        },
    ]
    calls = []

    def fake_run_query(**kwargs):
        calls.append(kwargs)
        if kwargs["sources"] == "hackernews":
            return {
                "items": [
                    {
                        "title": "Show HN: AgentEval",
                        "url": "https://agenteval.dev",
                        "hn_url": "https://news.ycombinator.com/item?id=1",
                        "outbound_url": "https://agenteval.dev",
                        "domain": "agenteval.dev",
                        "author": "founder",
                        "engagement": {"points": 12, "comments": 3},
                    }
                ],
                "warnings": [],
                "errors_by_source": {},
            }
        return {
            "items": [
                {
                    "title": "AgentEval | Y Combinator",
                    "url": "https://www.ycombinator.com/companies/agenteval",
                    "website": "https://agenteval.dev",
                    "founders": ["Jane Doe"],
                    "batch": "W26",
                    "description": "AI evals for agent teams.",
                }
            ],
            "warnings": ["thin"],
            "errors_by_source": {},
        }

    result = run_query_shape_debug(queries, run_query_fn=fake_run_query, output_dir=tmp_path)

    assert calls[0]["topic"] == "Show HN AI"
    assert calls[0]["sources"] == "hackernews"
    assert json.loads(calls[0]["plan"])["subqueries"][0]["search_query"] == "Show HN AI"
    assert calls[1]["sources"] == "grounding"
    assert json.loads(calls[1]["plan"])["freshness_mode"] == "evergreen_ok"
    assert result["summary"]["queries"] == 2
    assert result["summary"]["items_seen"] == 2
    assert result["summary"]["queries_with_items"] == 2
    hn_row = result["rows"][0]
    assert hn_row["items_returned"] == 1
    assert hn_row["field_coverage"]["hn_url"] == 1
    assert hn_row["field_coverage"]["outbound_url"] == 1
    assert hn_row["top_items"][0]["title"] == "Show HN: AgentEval"
    yc_row = result["rows"][1]
    assert yc_row["field_coverage"]["website"] == 1
    assert yc_row["field_coverage"]["founders"] == 1
    assert yc_row["warnings"] == ["thin"]
    assert tmp_path.joinpath("raw-last30days-query-shapes", "shape-hn-1.json").exists()


def test_write_query_shape_debug_artifact(tmp_path):
    payload = {
        "summary": {"queries": 1, "items_seen": 0, "queries_with_items": 0},
        "rows": [],
    }

    path = write_query_shape_debug_artifact(payload, tmp_path)

    assert path == tmp_path / "last30days-query-shape-debug.json"
    assert json.loads(path.read_text())["summary"]["queries"] == 1
