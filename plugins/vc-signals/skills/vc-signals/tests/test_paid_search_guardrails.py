from __future__ import annotations

import json
from pathlib import Path


def test_paid_search_guard_records_ledger_and_blocks_over_budget(tmp_path):
    from paid_search_guardrails import PaidSearchGuard

    ledger_path = tmp_path / "paid-search-ledger.jsonl"
    guard = PaidSearchGuard(mode="smoke", run_id="run-1", max_usd=0.01, ledger_path=ledger_path)

    first = guard.reserve(
        provider="brave",
        query="AI agent security startup",
        module="company_discovery",
        estimated_cost_usd=0.005,
    )
    assert first["allowed"] is True
    guard.record(first, cache_status="miss", result_count=3)

    second = guard.reserve(
        provider="brave",
        query="AI agent security funding",
        module="company_discovery",
        estimated_cost_usd=0.006,
    )
    assert second["allowed"] is False
    assert second["skip_reason"] == "paid_search_budget_exceeded"
    guard.record(second, cache_status="skip", result_count=0)

    rows = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]["estimated_cost_usd"] == 0.005
    assert rows[1]["skipped"] is True
    assert guard.summary()["estimated_spend_usd"] == 0.005
    assert guard.summary()["skipped_budget_exceeded"] == 1


def test_paid_search_guard_blocks_last30days_grounding_by_default(tmp_path):
    from paid_search_guardrails import PaidSearchGuard

    guard = PaidSearchGuard(mode="weekly", run_id="run-1", max_usd=8.0, ledger_path=tmp_path / "ledger.jsonl")

    reservation = guard.reserve(
        provider="last30days_grounding",
        query="broad startup discovery",
        module="last30days_adapter",
    )
    row = guard.record(reservation, cache_status="skip", result_count=0)

    assert reservation["allowed"] is False
    assert reservation["skip_reason"] == "last30days_grounding_disabled"
    assert row["skipped"] is True
    assert guard.summary()["estimated_spend_usd"] == 0
    assert guard.summary()["skipped_policy_disabled"] == 1


def test_global_provider_cache_dir_uses_env_override(monkeypatch, tmp_path):
    from paid_search_guardrails import provider_cache_dir

    monkeypatch.setenv("VC_SIGNALS_PROVIDER_CACHE_DIR", str(tmp_path / "cache"))

    path = provider_cache_dir("hard-evidence/product_hunt")

    assert path == tmp_path / "cache" / "hard-evidence" / "product_hunt"


def test_weekly_paid_search_preview_estimates_costs():
    from paid_search_guardrails import build_weekly_paid_search_preview

    preview = build_weekly_paid_search_preview(
        run_mode="weekly",
        sectors=("devtools", "cybersecurity"),
        max_queries_per_sector=3,
        product_hunt_limit=10,
        x_launch_limit=2,
        company_discovery_queries=12,
        signal_investigation_limit=8,
        hard_evidence_live=True,
        last30days_grounding_enabled=True,
    )

    assert preview["mode"] == "weekly"
    assert preview["estimated_cost_usd"] > 0
    assert preview["budget"]["over_budget"] is True
    modules = {row["module"] for row in preview["planned_paid_search"]}
    assert "last30days_sector_collection" in modules
    assert "hard_evidence_resolver" in modules
    assert "company_discovery" in modules


def test_weekly_paid_search_preview_disables_broad_last30days_by_default():
    from paid_search_guardrails import build_weekly_paid_search_preview

    preview = build_weekly_paid_search_preview(
        run_mode="weekly",
        sectors=("devtools", "cybersecurity"),
        max_queries_per_sector=3,
        product_hunt_limit=10,
        x_launch_limit=2,
        company_discovery_queries=12,
        signal_investigation_limit=8,
        hard_evidence_live=True,
    )

    modules = {row["module"] for row in preview["planned_paid_search"]}
    assert "last30days_sector_collection" not in modules
    assert "company_discovery" not in modules
    assert "signal_investigation" not in modules
    assert "hard_evidence_resolver" in modules
    assert preview["policy"]["last30days_grounding_allowed"] is False


def test_weekly_paid_search_preview_respects_explicit_max_usd():
    from paid_search_guardrails import build_weekly_paid_search_preview

    preview = build_weekly_paid_search_preview(
        run_mode="weekly",
        sectors=("devtools",),
        max_queries_per_sector=3,
        product_hunt_limit=0,
        x_launch_limit=0,
        company_discovery_queries=12,
        signal_investigation_limit=0,
        hard_evidence_live=False,
        last30days_grounding_enabled=True,
        max_usd=2.0,
    )

    assert preview["budget"]["max_usd"] == 2.0
    assert preview["budget"]["over_budget"] is True
