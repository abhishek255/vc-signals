from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


TRUTHY = {"1", "true", "yes", "on"}
DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "vc-signals" / "provider-search-cache"
DEFAULT_LEDGER_PATH = Path.home() / ".cache" / "vc-signals" / "paid-search-ledger.jsonl"
DEFAULT_PROVIDER_COST_PER_1000 = {
    "brave": 5.0,
    "exa": 7.0,
    "serper": 1.0,
    "dataforseo": 2.0,
    "you": 5.0,
    "perplexity_search": 5.0,
}
DEFAULT_LAST30DAYS_GROUNDING_COST_USD = 1.0
LAST30DAYS_GROUNDING_ENV = "VC_SIGNALS_ALLOW_LAST30DAYS_GROUNDING"
RUN_MODE_BUDGETS_USD = {
    "smoke": 0.50,
    "dev": 0.50,
    "manual_enrichment": 2.00,
    "weekly": 8.00,
    "deep_dive": 25.00,
    "deep_validation": 25.00,
    "unbounded": None,
}


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in TRUTHY


def _float_env(name: str, default: float | None) -> float | None:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def provider_cache_dir(namespace: str = "") -> Path:
    root = Path(os.environ.get("VC_SIGNALS_PROVIDER_CACHE_DIR") or DEFAULT_CACHE_ROOT)
    if not namespace:
        return root
    parts = [part for part in str(namespace).replace("\\", "/").split("/") if part]
    return root.joinpath(*parts)


def default_ledger_path() -> Path:
    return Path(os.environ.get("VC_SIGNALS_PAID_SEARCH_LEDGER_PATH") or DEFAULT_LEDGER_PATH)


def provider_cost_usd(provider: str, *, request_units: int = 1) -> float:
    normalized = (provider or "").strip().lower()
    if normalized == "last30days_grounding":
        return _float_env("VC_SIGNALS_LAST30DAYS_GROUNDING_COST_USD", DEFAULT_LAST30DAYS_GROUNDING_COST_USD) or 0.0
    per_1000 = _float_env(
        f"VC_SIGNALS_{normalized.upper()}_COST_PER_1000",
        DEFAULT_PROVIDER_COST_PER_1000.get(normalized, 5.0),
    ) or 0.0
    return round((per_1000 / 1000.0) * max(int(request_units or 1), 1), 6)


def budget_for_mode(mode: str) -> float | None:
    normalized = (mode or "weekly").strip().lower()
    return _float_env("VC_SIGNALS_PAID_SEARCH_MAX_USD", RUN_MODE_BUDGETS_USD.get(normalized, RUN_MODE_BUDGETS_USD["weekly"]))


def last30days_grounding_allowed(value: bool | None = None) -> bool:
    if value is not None:
        return bool(value)
    return _truthy(os.environ.get(LAST30DAYS_GROUNDING_ENV))


@dataclass
class PaidSearchGuard:
    mode: str = "weekly"
    run_id: str = ""
    max_usd: float | None = None
    ledger_path: Path | str | None = None
    dry_run: bool = False
    allow_over_budget: bool = False
    allow_last30days_grounding: bool | None = None
    estimated_spend_usd: float = 0.0
    live_calls: int = 0
    cache_hits: int = 0
    skipped_budget_exceeded: int = 0
    skipped_dry_run: int = 0
    skipped_policy_disabled: int = 0
    records: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_usd is None:
            self.max_usd = budget_for_mode(self.mode)
        self.ledger_path = Path(self.ledger_path) if self.ledger_path else default_ledger_path()
        self.dry_run = bool(self.dry_run or _truthy(os.environ.get("VC_SIGNALS_PAID_SEARCH_DRY_RUN")))
        self.allow_over_budget = bool(
            self.allow_over_budget or _truthy(os.environ.get("VC_SIGNALS_ALLOW_PAID_SEARCH_OVER_BUDGET"))
        )
        self.allow_last30days_grounding = last30days_grounding_allowed(self.allow_last30days_grounding)

    def reserve(
        self,
        *,
        provider: str,
        query: str,
        module: str,
        estimated_cost_usd: float | None = None,
        request_units: int = 1,
    ) -> dict:
        cost = provider_cost_usd(provider, request_units=request_units) if estimated_cost_usd is None else float(estimated_cost_usd)
        allowed = True
        skip_reason = ""
        if provider == "last30days_grounding" and not self.allow_last30days_grounding:
            allowed = False
            skip_reason = "last30days_grounding_disabled"
        elif self.dry_run:
            allowed = False
            skip_reason = "paid_search_dry_run"
        elif self.max_usd is not None and not self.allow_over_budget and self.estimated_spend_usd + cost > float(self.max_usd):
            allowed = False
            skip_reason = "paid_search_budget_exceeded"
        return {
            "allowed": allowed,
            "skip_reason": skip_reason,
            "provider": provider,
            "query": query,
            "module": module,
            "estimated_cost_usd": round(cost, 6),
            "run_id": self.run_id,
            "mode": self.mode,
        }

    def record(self, reservation: dict, *, cache_status: str = "miss", result_count: int = 0) -> dict:
        skipped = not bool(reservation.get("allowed"))
        row = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": self.run_id,
            "mode": self.mode,
            "module": reservation.get("module", ""),
            "provider": reservation.get("provider", ""),
            "query": reservation.get("query", ""),
            "estimated_cost_usd": float(reservation.get("estimated_cost_usd") or 0.0),
            "cache_status": cache_status,
            "result_count": int(result_count or 0),
            "skipped": skipped,
            "skip_reason": reservation.get("skip_reason", ""),
        }
        if cache_status == "hit":
            self.cache_hits += 1
        elif skipped and row["skip_reason"] == "paid_search_budget_exceeded":
            self.skipped_budget_exceeded += 1
        elif skipped and row["skip_reason"] == "paid_search_dry_run":
            self.skipped_dry_run += 1
        elif skipped and row["skip_reason"] == "last30days_grounding_disabled":
            self.skipped_policy_disabled += 1
        elif not skipped:
            self.live_calls += 1
            if cache_status != "hit":
                self.estimated_spend_usd = round(self.estimated_spend_usd + row["estimated_cost_usd"], 6)
        self.records.append(row)
        self._append_ledger(row)
        return row

    def record_cache_hit(self, *, provider: str, query: str, module: str) -> dict:
        reservation = {
            "allowed": True,
            "provider": provider,
            "query": query,
            "module": module,
            "estimated_cost_usd": 0.0,
            "run_id": self.run_id,
            "mode": self.mode,
        }
        return self.record(reservation, cache_status="hit", result_count=0)

    def summary(self) -> dict:
        return {
            "enabled": True,
            "mode": self.mode,
            "run_id": self.run_id,
            "budget_max_usd": self.max_usd,
            "estimated_spend_usd": round(self.estimated_spend_usd, 6),
            "live_calls": self.live_calls,
            "cache_hits": self.cache_hits,
            "skipped_budget_exceeded": self.skipped_budget_exceeded,
            "skipped_dry_run": self.skipped_dry_run,
            "skipped_policy_disabled": self.skipped_policy_disabled,
            "last30days_grounding_allowed": bool(self.allow_last30days_grounding),
            "ledger_path": str(self.ledger_path),
        }

    def _append_ledger(self, row: dict) -> None:
        if _truthy(os.environ.get("VC_SIGNALS_PAID_SEARCH_DISABLE_LEDGER")):
            return
        path = Path(self.ledger_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


_CURRENT_GUARD: PaidSearchGuard | None = None


def configure_paid_search_guard(
    *,
    mode: str = "weekly",
    run_id: str = "",
    max_usd: float | None = None,
    ledger_path: Path | str | None = None,
    dry_run: bool = False,
    allow_last30days_grounding: bool | None = None,
) -> PaidSearchGuard:
    global _CURRENT_GUARD
    _CURRENT_GUARD = PaidSearchGuard(
        mode=mode,
        run_id=run_id,
        max_usd=max_usd,
        ledger_path=ledger_path,
        dry_run=dry_run,
        allow_last30days_grounding=allow_last30days_grounding,
    )
    return _CURRENT_GUARD


def current_paid_search_guard() -> PaidSearchGuard | None:
    return _CURRENT_GUARD


def reset_paid_search_guard() -> None:
    global _CURRENT_GUARD
    _CURRENT_GUARD = None


def paid_search_summary() -> dict:
    if not _CURRENT_GUARD:
        return {"enabled": False, "reason": "paid_search_guard_not_configured"}
    return _CURRENT_GUARD.summary()


def build_weekly_paid_search_preview(
    *,
    run_mode: str,
    sectors: tuple[str, ...],
    max_queries_per_sector: int,
    product_hunt_limit: int,
    x_launch_limit: int,
    company_discovery_queries: int,
    signal_investigation_limit: int,
    hard_evidence_live: bool,
    last30days_grounding_enabled: bool | None = None,
    max_usd: float | None = None,
) -> dict:
    planned = []

    def add(module: str, provider: str, calls: int, cost_per_call: float) -> None:
        if calls <= 0:
            return
        planned.append(
            {
                "module": module,
                "provider": provider,
                "planned_calls": int(calls),
                "estimated_cost_usd": round(float(calls) * float(cost_per_call), 6),
            }
        )

    last30days_enabled = last30days_grounding_allowed(last30days_grounding_enabled)
    if last30days_enabled:
        add(
            "last30days_sector_collection",
            "last30days_grounding",
            len(tuple(sectors or ())) * max(int(max_queries_per_sector or 0), 0),
            provider_cost_usd("last30days_grounding"),
        )
    if hard_evidence_live:
        add("hard_evidence_resolver", "exa", (int(product_hunt_limit or 0) + int(x_launch_limit or 0)) * 2, provider_cost_usd("exa"))
    if last30days_enabled:
        add("company_discovery", "last30days_grounding", int(company_discovery_queries or 0), provider_cost_usd("last30days_grounding"))
        add("signal_investigation", "last30days_grounding", int(signal_investigation_limit or 0), provider_cost_usd("last30days_grounding"))

    estimated = round(sum(row["estimated_cost_usd"] for row in planned), 6)
    max_usd = budget_for_mode(run_mode) if max_usd is None else float(max_usd)
    return {
        "mode": run_mode,
        "budget": {
            "max_usd": max_usd,
            "over_budget": bool(max_usd is not None and estimated > float(max_usd)),
        },
        "planned_paid_search": planned,
        "estimated_cost_usd": estimated,
        "policy": {
            "last30days_grounding_allowed": last30days_enabled,
            "last30days_grounding_env": LAST30DAYS_GROUNDING_ENV,
            "last30days_grounding_note": (
                "Broad last30days paid grounding is disabled by default; use the env flag or CLI opt-in only for intentional deep runs."
            ),
        },
        "cache_dir": str(provider_cache_dir()),
        "ledger_path": str(default_ledger_path()),
    }
