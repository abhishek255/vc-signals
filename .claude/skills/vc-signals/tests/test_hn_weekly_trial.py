"""Tests for Phase 6C controlled HN weekly trial orchestration."""

from __future__ import annotations


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
