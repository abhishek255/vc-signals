"""Tests for Phase 6C controlled HN weekly trial orchestration."""

from __future__ import annotations

import json


def test_hn_weekly_trial_default_candidate_cap_covers_rich_movement_smoke():
    from hn_weekly_trial import HNLaunchTrialConfig

    assert HNLaunchTrialConfig(enabled=True).max_candidates == 15


def test_hn_weekly_trial_uses_last30days_hn_only_and_writes_artifacts(tmp_path):
    from hn_weekly_trial import HNLaunchTrialConfig, run_hn_launch_weekly_trial

    calls = {"queries": []}

    def fake_last30days_query(topic, **kwargs):
        calls["queries"].append({"topic": topic, **kwargs})
        assert kwargs["sources"] == "hackernews"
        return {
            "items": [
                {
                    "title": "Show HN: Burrow - Runtime Security for AI Agents",
                    "url": "https://news.ycombinator.com/item?id=1",
                    "hn_url": "https://news.ycombinator.com/item?id=1",
                    "outbound_url": "https://burrow.security",
                    "domain": "burrow.security",
                    "author": "founder",
                    "engagement": {"points": 42, "comments": 9},
                }
            ]
        }

    result = run_hn_launch_weekly_trial(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity", "origin_row_ids": ["m1"]}],
        run_query_fn=fake_last30days_query,
        query_runner=lambda topic, **kwargs: {"items": []},
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        attio_matcher=lambda candidate: {"attio_status": "unknown"},
        output_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        config=HNLaunchTrialConfig(enabled=True, max_candidates=2, max_runtime_seconds=30),
    )

    assert result["enabled"] is True
    assert result["queries_planned"] == 2
    assert result["queries_run"] == 2
    assert result["movement_seeds"] == [
        {"movement": "AI agent security", "market_sector": "Cybersecurity", "origin_row_ids": ["m1"]}
    ]
    assert result["items_seen"] == 2
    assert result["outbound_candidates"] == 1
    assert result["assign_owner_rows"] == 0
    assert result["unsafe_promotions"] == 0
    assert all(call["sources"] == "hackernews" for call in calls["queries"])
    assert (tmp_path / "company-native-source-audit.json").exists()
    assert (tmp_path / "hn-gated-source-trial.json").exists()
    assert (tmp_path / "hn-outbound-enrichment.json").exists()
    assert (tmp_path / "hn-weekly-trial.json").exists()
    assert (tmp_path / "hn-weekly-trial.md").exists()
    assert (tmp_path / "hn-trial-row-review.json").exists()
    assert (tmp_path / "hn-trial-row-review.md").exists()
    assert not (tmp_path / "weekly-preview.md").exists()


def test_hn_weekly_trial_writes_summary_when_no_movements(tmp_path):
    from hn_weekly_trial import HNLaunchTrialConfig, run_hn_launch_weekly_trial

    result = run_hn_launch_weekly_trial(
        movements=[],
        run_query_fn=lambda topic, **kwargs: {"items": []},
        output_dir=tmp_path,
        config=HNLaunchTrialConfig(enabled=True),
    )

    assert result["enabled"] is True
    assert result["queries_planned"] == 0
    assert result["queries_run"] == 0
    assert result["movement_seeds"] == []
    assert result["items_seen"] == 0
    assert result["skipped_no_seed"] is True
    assert result["completion_status"] == "skipped_no_seed"
    assert (tmp_path / "hn-weekly-trial.json").exists()
    markdown = (tmp_path / "hn-weekly-trial.md").read_text()
    assert "No HN launch queries were planned" in markdown
    assert "skipped_no_seed" in markdown
    assert not (tmp_path / "weekly-preview.md").exists()


def test_hn_weekly_trial_surfaces_attio_blocked_owner_ready_rows(tmp_path):
    import time

    from hn_weekly_trial import HNLaunchTrialConfig, run_hn_launch_weekly_trial

    def fake_last30days_query(topic, **kwargs):
        return {
            "items": [
                {
                    "title": "Show HN: Veris - Agent sandboxes with simulated external services",
                    "url": "https://news.ycombinator.com/item?id=2",
                    "hn_url": "https://news.ycombinator.com/item?id=2",
                    "outbound_url": "https://veris.ai/sandbox",
                    "domain": "veris.ai",
                    "author": "founder",
                    "engagement": {"points": 42, "comments": 9},
                }
            ]
        }

    def fake_page_fetcher(url):
        if url.endswith("/blog"):
            return (
                "<html><body><p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Enterprise teams can book demo access for AI agent validation.</p></body></html>"
            )
        return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"

    def slow_attio(_candidate):
        time.sleep(0.05)
        return {"attio_status": "no_owner"}

    result = run_hn_launch_weekly_trial(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity", "origin_row_ids": ["m1"]}],
        run_query_fn=fake_last30days_query,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live query should not run")),
        page_fetcher=fake_page_fetcher,
        attio_matcher=slow_attio,
        output_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        config=HNLaunchTrialConfig(
            enabled=True,
            max_candidates=2,
            max_runtime_seconds=30,
            max_live_queries=0,
            max_attio_checks=2,
            per_candidate_timeout_seconds=0.01,
        ),
    )

    assert result["assign_owner_rows"] == 0
    assert result["action_blocked_by_attio_rows"] == 1
    assert result["runtime"]["attio_timeouts"] == 1
    markdown = (tmp_path / "hn-weekly-trial.md").read_text()
    assert "Action blocked by Attio rows: 1" in markdown
    assert not (tmp_path / "weekly-preview.md").exists()


def test_hn_weekly_trial_markdown_shows_ranked_review_rows_without_dump():
    from hn_weekly_trial import _markdown

    review_rows = [
        {
            "name": "Veris",
            "domain": "veris.ai",
            "final_action": "Assign owner",
            "recommended_lane": "HN Enriched Outbound Candidates",
            "completion_status": "completed_clean",
            "evidence_dimensions": ["customer", "founder", "stage"],
            "missing_evidence": [],
            "attio_status": "no_owner",
        }
    ]
    review_rows.extend(
        {
            "name": f"Research {index}",
            "domain": f"research{index}.ai",
            "final_action": "Research deeper",
            "recommended_lane": "HN Enriched Outbound Candidates",
            "completion_status": "completed_with_stage_failure",
            "evidence_dimensions": ["stage"] if index == 1 else [],
            "missing_evidence": ["maturity_query_timeout"],
            "attio_status": "unknown",
        }
        for index in range(1, 7)
    )
    payload = {
        "queries_planned": 12,
        "queries_run": 12,
        "completion_status": "completed_with_stage_failure",
        "items_seen": 64,
        "outbound_candidates": 14,
        "project_only_rows": 13,
        "product_context_rows": 1,
        "research_deeper_rows": 13,
        "assign_owner_rows": 1,
        "action_blocked_by_attio_rows": 0,
        "unsafe_promotions": 0,
        "runtime": {"candidates_completed": 14, "stage_failures": 11},
        "review_rows": review_rows,
    }

    markdown = _markdown(payload)

    assert "## Top HN Review Rows" in markdown
    assert "Veris" in markdown
    assert "Research 4" in markdown
    assert "Research 5" not in markdown
    assert "13 project-only rows summarized separately" in markdown


def test_hn_weekly_trial_writes_row_review_package_with_priorities(tmp_path):
    from hn_weekly_trial import _write_summary_artifacts

    payload = {
        "queries_planned": 12,
        "queries_run": 12,
        "completion_status": "completed_with_stage_failure",
        "items_seen": 64,
        "outbound_candidates": 2,
        "project_only_rows": 13,
        "product_context_rows": 1,
        "research_deeper_rows": 1,
        "assign_owner_rows": 1,
        "action_blocked_by_attio_rows": 0,
        "unsafe_promotions": 0,
        "runtime": {"high_priority_candidates": 1, "normal_priority_candidates": 1},
        "review_rows": [
            {
                "name": "Veris",
                "domain": "veris.ai",
                "priority": "normal_priority",
                "priority_reasons": ["company_looking_domain"],
                "completion_status": "completed_clean",
                "stage_failure_reason": [],
                "final_action": "Assign owner",
                "recommended_lane": "HN Enriched Outbound Candidates",
                "evidence_dimensions": ["customer", "founder", "stage"],
                "missing_evidence": [],
                "attio_status": "no_owner",
                "unsafe_promotion": False,
            },
            {
                "name": "LoudCo",
                "domain": "loudco.ai",
                "priority": "high_priority",
                "priority_reasons": ["official_domain_url", "hn_engagement"],
                "completion_status": "completed_with_stage_failure",
                "stage_failure_reason": ["maturity_query_timeout"],
                "final_action": "Research deeper",
                "recommended_lane": "HN Enriched Outbound Candidates",
                "evidence_dimensions": ["customer"],
                "missing_evidence": ["maturity_query_timeout", "no founder/team evidence"],
                "attio_status": "unknown",
                "unsafe_promotion": False,
            },
        ],
    }

    result = _write_summary_artifacts(payload, tmp_path)

    assert str(tmp_path / "hn-trial-row-review.json") in result["artifacts"]
    assert str(tmp_path / "hn-trial-row-review.md") in result["artifacts"]
    review_json = json.loads((tmp_path / "hn-trial-row-review.json").read_text())
    assert review_json["summary"]["priority_split"] == {"high_priority": 1, "normal_priority": 1}
    review_md = (tmp_path / "hn-trial-row-review.md").read_text()
    assert "Priority: normal_priority" in review_md
    assert "Priority: high_priority" in review_md
    assert "maturity_query_timeout" in review_md
    assert "weekly-preview.md" not in review_md


def test_hn_row_review_markdown_renders_assign_owner_evidence_provenance():
    from hn_weekly_trial import _row_review_markdown

    exact_url = "https://veris.ai/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"
    payload = {
        "summary": {
            "rows": 1,
            "priority_split": {"normal_priority": 1},
            "completion_split": {"completed_clean": 1},
            "action_split": {"Assign owner": 1},
        },
        "rows": [
            {
                "name": "Veris",
                "domain": "veris.ai",
                "priority": "normal_priority",
                "priority_reasons": ["official_domain_url"],
                "completion_status": "completed_clean",
                "stage_failure_reason": [],
                "final_action": "Assign owner",
                "evidence_dimensions": ["customer", "founder", "stage"],
                "attio_status": "no_owner",
                "missing_evidence": [],
                "unsafe_promotion": False,
                "assign_owner_evidence_provenance": {
                    "hn_source": {"url": "https://news.ycombinator.com/item?id=48054313"},
                    "official_company_source": {"url": "https://veris.ai/sandbox"},
                    "founder_evidence": {"url": exact_url},
                    "stage_funding_evidence": {"url": exact_url},
                    "commercial_customer_evidence": {"url": exact_url},
                    "attio_status_evidence": {
                        "status": "no_owner",
                        "source": "attio_read",
                        "action_safe": True,
                    },
                },
            }
        ],
    }

    markdown = _row_review_markdown(payload)

    assert "HN source: https://news.ycombinator.com/item?id=48054313" in markdown
    assert "Official/company source: https://veris.ai/sandbox" in markdown
    assert f"Founder evidence: {exact_url}" in markdown
    assert f"Stage/funding evidence: {exact_url}" in markdown
    assert f"Commercial/customer evidence: {exact_url}" in markdown
    assert "Attio status evidence: no_owner via attio_read" in markdown


def test_hn_weekly_trial_warm_attio_cache_supports_assign_owner(tmp_path):
    from hn_outbound_enrichment import _attio_cache_path
    from hn_weekly_trial import HNLaunchTrialConfig, run_hn_launch_weekly_trial

    cache_dir = tmp_path / "cache"
    path = _attio_cache_path(cache_dir, "Veris", "veris.ai")
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"fetched_at": "2026-05-10", "payload": {"attio_status": "no_owner"}, '
        '"match_key": {"name": "Veris", "domain": "veris.ai"}}'
    )

    def fake_last30days_query(topic, **kwargs):
        return {
            "items": [
                {
                    "title": "Show HN: Veris - Agent sandboxes with simulated external services",
                    "url": "https://news.ycombinator.com/item?id=2",
                    "hn_url": "https://news.ycombinator.com/item?id=2",
                    "outbound_url": "https://veris.ai/sandbox",
                    "domain": "veris.ai",
                    "author": "founder",
                    "engagement": {"points": 42, "comments": 9},
                }
            ]
        }

    def fake_page_fetcher(url):
        if url.endswith("/blog"):
            return (
                "<html><body><p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Enterprise teams can book demo access for AI agent validation.</p></body></html>"
            )
        return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"

    result = run_hn_launch_weekly_trial(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity", "origin_row_ids": ["m1"]}],
        run_query_fn=fake_last30days_query,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live query should not run")),
        page_fetcher=fake_page_fetcher,
        attio_matcher=lambda candidate: (_ for _ in ()).throw(AssertionError("fresh cache should avoid live Attio")),
        output_dir=tmp_path,
        cache_dir=cache_dir,
        config=HNLaunchTrialConfig(enabled=True, max_candidates=2, max_runtime_seconds=30, max_live_queries=0),
    )

    assert result["assign_owner_rows"] == 1
    assert result["runtime"]["attio_cache_fresh_hits"] == 1
    assert result["runtime"]["attio_checks"] == 0
    assert result["review_rows"][0]["name"] == "Veris"
