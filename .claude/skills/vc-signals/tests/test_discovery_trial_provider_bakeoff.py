import json
from pathlib import Path

from discovery_trial_provider_bakeoff import (
    load_trial_queries_from_weekly_run,
    weekly_trial_provider_bakeoff,
    write_weekly_trial_provider_bakeoff_artifacts,
)


def _write_weekly_run(tmp_path: Path, queries: list[dict]) -> Path:
    run_dir = tmp_path / "weekly-run"
    run_dir.mkdir()
    (run_dir / "company-discovery.json").write_text(json.dumps({"queries": queries}, indent=2))
    return run_dir


def _trial_query(**overrides):
    payload = {
        "id": "agent-evals-trial-platform",
        "topic": "Agent reliability and evals platform company official AI Infra",
        "query_family": "movement_platform",
        "discovery_lane": "discovery_yield_trial",
        "movement": "Agent reliability and evals",
        "market_sector": "AI Infra",
        "required_terms": ["agent", "reliability", "evals"],
        "sources": "grounding",
        "lookback_days": 30,
        "web_backend": "auto",
    }
    payload.update(overrides)
    return payload


def test_load_trial_queries_filters_discovery_yield_lane(tmp_path):
    run_dir = _write_weekly_run(
        tmp_path,
        [
            _trial_query(),
            {
                **_trial_query(id="baseline", discovery_lane="controlled_company_discovery"),
                "query_family": "official_company_page",
            },
        ],
    )

    queries = load_trial_queries_from_weekly_run(run_dir)

    assert len(queries) == 1
    assert queries[0]["id"] == "agent-evals-trial-platform"
    assert queries[0]["discovery_lane"] == "discovery_yield_trial"


def test_weekly_trial_provider_bakeoff_runs_same_queries_for_each_provider(tmp_path):
    queries = [_trial_query(), _trial_query(id="agent-evals-trial-founder", query_family="founder_company_pages")]
    seen = []

    def runner(provider, query, **_kwargs):
        seen.append((provider, query["topic"]))
        return {
            "provider": provider,
            "query_id": query["id"],
            "query": query["topic"],
            "items": [],
            "skipped": False,
            "cache_status": "miss",
            "latency_ms": 10,
            "cost_usd": 0.0,
            "capabilities": {"snippet_only": True},
        }

    result = weekly_trial_provider_bakeoff(
        queries,
        providers=["brave", "you"],
        provider_runner=runner,
        cache_dir=tmp_path / "cache",
    )

    brave_topics = [topic for provider, topic in seen if provider == "brave"]
    you_topics = [topic for provider, topic in seen if provider == "you"]
    assert brave_topics == you_topics
    assert len(brave_topics) == 2
    family_rows = {
        (row["provider"], row["query_family"]): row for row in result["provider_family_summaries"]
    }
    assert family_rows[("brave", "movement_platform")]["queries_planned"] == 1
    assert family_rows[("you", "founder_company_pages")]["queries_planned"] == 1


def test_you_only_verified_domain_improves_research_worthy_without_affecting_brave(tmp_path):
    queries = [_trial_query()]

    def runner(provider, query, **_kwargs):
        topic = query["topic"]
        if provider == "you" and "platform company official" in topic:
            return {
                "provider": provider,
                "query_id": query["id"],
                "query": topic,
                "items": [
                    {
                        "title": "LangWatch - Agent reliability and evals platform",
                        "url": "https://langwatch.ai/",
                        "snippet": "LangWatch helps AI teams improve agent reliability and evals.",
                    }
                ],
                "skipped": False,
                "cache_status": "miss",
                "latency_ms": 25,
                "cost_usd": 0.01,
                "capabilities": {"snippet_only": True},
            }
        return {
            "provider": provider,
            "query_id": query.get("id", ""),
            "query": topic,
            "items": [],
            "skipped": False,
            "cache_status": "miss",
            "latency_ms": 5,
            "cost_usd": 0.0,
            "capabilities": {"snippet_only": True},
        }

    result = weekly_trial_provider_bakeoff(
        queries,
        providers=["brave", "you"],
        provider_runner=runner,
        cache_dir=tmp_path / "cache",
    )

    by_provider = {row["provider"]: row for row in result["provider_summaries"]}
    assert by_provider["brave"]["verified_domains"] == 0
    assert by_provider["you"]["verified_domains"] == 1
    assert by_provider["you"]["verified_domain_list"] == ["langwatch.ai"]
    assert by_provider["you"]["research_worthy_unknown"] == 1
    assert by_provider["you"]["maturity_confirmed_early_stage"] == 0


def test_mature_provider_result_routes_category_not_early_stage(tmp_path):
    queries = [
        _trial_query(
            id="cloud-security-trial",
            topic="AI cloud security platform company official Cybersecurity",
            movement="AI cloud security",
            market_sector="Cybersecurity",
            required_terms=["cloud", "security"],
        )
    ]

    def runner(provider, query, **_kwargs):
        topic = query["topic"].lower()
        if "funding valuation acquisition" in topic:
            return {
                "provider": provider,
                "query_id": query.get("id", ""),
                "query": query["topic"],
                "items": [
                    {
                        "title": "Wiz reaches $12B valuation after Series E",
                        "url": "https://www.wiz.io/",
                        "snippet": "Wiz is a category leader in cloud security with a large valuation.",
                    }
                ],
                "skipped": False,
                "cache_status": "miss",
                "latency_ms": 10,
                "cost_usd": 0.0,
                "capabilities": {"snippet_only": True},
            }
        return {
            "provider": provider,
            "query_id": query["id"],
            "query": query["topic"],
            "items": [
                {
                    "title": "Wiz - Cloud Security Platform",
                    "url": "https://www.wiz.io/",
                    "snippet": "Wiz is a cloud security platform for AI-era teams.",
                }
            ],
            "skipped": False,
            "cache_status": "miss",
            "latency_ms": 10,
            "cost_usd": 0.0,
            "capabilities": {"snippet_only": True},
        }

    result = weekly_trial_provider_bakeoff(
        queries,
        providers=["you"],
        provider_runner=runner,
        cache_dir=tmp_path / "cache",
    )

    summary = result["provider_summaries"][0]
    assert summary["verified_domains"] == 1
    assert summary["maturity_confirmed_early_stage"] == 0
    assert summary["category_anchors"] == 1
    assert summary["unsafe_promotions"] == 0


def test_skipped_provider_is_reported_without_failing(tmp_path):
    queries = [_trial_query()]

    def runner(provider, query, **_kwargs):
        return {
            "provider": provider,
            "query_id": query["id"],
            "query": query["topic"],
            "items": [],
            "skipped": True,
            "skip_reason": "missing_api_key",
            "cache_status": "skip",
            "latency_ms": 0,
            "cost_usd": 0.0,
            "capabilities": {"snippet_only": True},
        }

    result = weekly_trial_provider_bakeoff(
        queries,
        providers=["you"],
        provider_runner=runner,
        cache_dir=tmp_path / "cache",
    )

    assert result["provider_summaries"][0]["skipped_queries"] == 1
    assert result["provider_summaries"][0]["skip_reasons"] == {"missing_api_key": 1}
    assert result["provider_family_summaries"][0]["skipped_queries"] == 1
    assert result["provider_family_summaries"][0]["skip_reasons"] == {"missing_api_key": 1}


def test_artifact_writer_does_not_touch_weekly_preview(tmp_path):
    weekly_preview = tmp_path / "weekly-preview.md"
    weekly_preview.write_text("unchanged\n")
    payload = {
        "summary": {"providers": ["brave"], "queries": 0},
        "queries": [],
        "provider_summaries": [],
        "provider_family_summaries": [],
        "accepted_leads": [],
        "rejected_leads": [],
    }

    written = write_weekly_trial_provider_bakeoff_artifacts(payload, tmp_path / "out")

    assert weekly_preview.read_text() == "unchanged\n"
    assert (tmp_path / "out" / "weekly-trial-provider-bakeoff.json") in written
    assert (tmp_path / "out" / "weekly-trial-provider-summary.md") in written
