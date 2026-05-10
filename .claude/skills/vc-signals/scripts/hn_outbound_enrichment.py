#!/usr/bin/env python3
"""Phase 6B.2 enrichment for HN outbound candidates.

This is an offline trial artifact. It does not change weekly default behavior
and does not turn HN outbound links into company leads before official-domain
identity promotion succeeds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import signal
import time
from contextlib import contextmanager
from html import unescape
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from canonical_identity import canonicalize_identity
from founder_team_verification import enrich_founder_team_verification
from owner_evidence import _default_page_fetcher, enrich_owner_evidence
from radar_company_discovery import _classify_maturity_from_items
from radar_focus import ACTION_ASSIGN_OWNER, ACTION_MONITOR_ONLY, ACTION_RESEARCH_DEEPER, score_owner_readiness
from radar_models import Candidate


LATE_OR_CONTEXT_STATUSES = {"likely_too_late", "acquired", "incumbent", "category_leader"}
ACCELERATOR_SUFFIX_RE = re.compile(r"\s*\((?:YC|Y\s+Combinator)\s+[SWF]\d{2}\)\s*", re.IGNORECASE)


class _CallTimeout(Exception):
    pass


class _RuntimeBudget:
    def __init__(
        self,
        *,
        max_runtime_seconds: float | None = None,
        max_attio_checks: int | None = None,
        max_live_queries: int | None = None,
        per_candidate_timeout_seconds: float | None = None,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self.max_runtime_seconds = max_runtime_seconds
        self.max_attio_checks = max_attio_checks
        self.max_live_queries = max_live_queries
        self.per_candidate_timeout_seconds = per_candidate_timeout_seconds
        self.time_fn = time_fn or time.monotonic
        self.started_at = self.time_fn()
        self.live_queries = 0
        self.attio_checks = 0
        self.page_fetches = 0
        self.timeouts = 0
        self.budget_exceeded = False
        self.budget_reasons: list[str] = []

    def elapsed(self) -> float:
        return max(0.0, self.time_fn() - self.started_at)

    def runtime_exceeded(self) -> bool:
        if self.max_runtime_seconds is None:
            return False
        exceeded = self.elapsed() >= self.max_runtime_seconds
        if exceeded:
            self.mark_exceeded("max_runtime_seconds_exceeded")
        return exceeded

    def remaining_runtime_seconds(self) -> float | None:
        if self.max_runtime_seconds is None:
            return None
        return max(0.0, self.max_runtime_seconds - self.elapsed())

    def candidate_exceeded(self, candidate_started_at: float) -> bool:
        if self.per_candidate_timeout_seconds is None:
            return False
        exceeded = max(0.0, self.time_fn() - candidate_started_at) >= self.per_candidate_timeout_seconds
        if exceeded:
            self.mark_exceeded("per_candidate_timeout_seconds_exceeded")
        return exceeded

    def mark_exceeded(self, reason: str) -> None:
        self.budget_exceeded = True
        if reason not in self.budget_reasons:
            self.budget_reasons.append(reason)

    def can_run_live_query(self) -> bool:
        if self.runtime_exceeded():
            return False
        if self.max_live_queries is not None and self.live_queries >= self.max_live_queries:
            return False
        return True

    def mark_live_query(self) -> None:
        self.live_queries += 1

    def can_check_attio(self) -> bool:
        if self.runtime_exceeded():
            return False
        if self.max_attio_checks is not None and self.attio_checks >= self.max_attio_checks:
            self.mark_exceeded("max_attio_checks_exceeded")
            return False
        return True

    def mark_attio_check(self) -> None:
        self.attio_checks += 1

    def mark_page_fetch(self) -> None:
        self.page_fetches += 1

    def mark_timeout(self, reason: str) -> None:
        self.timeouts += 1
        self.mark_exceeded(reason)


@contextmanager
def _timeout(seconds: float | None):
    if not seconds or seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    def _handler(_signum, _frame):
        raise _CallTimeout()

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    signal.signal(signal.SIGALRM, _handler)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def run_hn_outbound_enrichment(
    phase6b_payload: dict,
    *,
    query_runner: Callable | None = None,
    page_fetcher: Callable | None = None,
    attio_matcher: Callable | None = None,
    cache_dir: Path | str | None = None,
    max_candidates: int = 5,
    max_runtime_seconds: float | None = None,
    max_attio_checks: int | None = None,
    max_live_queries: int | None = None,
    per_candidate_timeout_seconds: float | None = None,
    time_fn: Callable[[], float] | None = None,
) -> dict:
    cache_path = Path(cache_dir) if cache_dir else None
    rows = phase6b_payload.get("company_rows", []) or []
    enriched_rows: list[dict] = []
    skipped_rows: list[dict] = []
    runtime = _RuntimeBudget(
        max_runtime_seconds=max_runtime_seconds,
        max_attio_checks=max_attio_checks,
        max_live_queries=max_live_queries,
        per_candidate_timeout_seconds=per_candidate_timeout_seconds,
        time_fn=time_fn,
    )
    ledger_items: list[dict] = []
    reports = {
        "identity": [],
        "maturity": [],
        "founder_team": {"items": [], "summary": {}},
        "owner_evidence": {"items": [], "summary": {}},
    }

    for index, row in enumerate(rows):
        ledger = _new_ledger_item(row, index=index)
        ledger_items.append(ledger)
        candidate_started_at = runtime.time_fn()
        if index >= max_candidates:
            skipped_rows.append(_skipped_row(row, reason="max_candidates_exceeded", ledger=ledger))
            runtime.mark_exceeded("max_candidates_exceeded")
            continue
        if runtime.runtime_exceeded():
            skipped_rows.append(_skipped_row(row, reason="max_runtime_seconds_exceeded", ledger=ledger))
            continue

        candidate = _candidate_from_hn_row(row)
        promoted, identity_report = _promote_identity(
            candidate,
            row,
            page_fetcher=page_fetcher,
            cache_dir=cache_path,
            runtime=runtime,
            ledger=ledger,
        )
        reports["identity"].append(identity_report)
        if promoted.identity_type == "verified_company":
            promoted = _apply_attio(promoted, attio_matcher, runtime=runtime, ledger=ledger)
            promoted, maturity_report = _enrich_maturity(
                promoted,
                query_runner=query_runner,
                cache_dir=cache_path,
                runtime=runtime,
                ledger=ledger,
            )
            reports["maturity"].append(maturity_report)
        else:
            maturity_report = _skipped_maturity_report(promoted, "identity_not_promoted")
            reports["maturity"].append(maturity_report)

        final_candidate = promoted
        if final_candidate.identity_type == "verified_company" and not runtime.candidate_exceeded(candidate_started_at):
            founder_enriched, founder_report = enrich_founder_team_verification(
                [final_candidate],
                query_runner=_budgeted_query_runner(query_runner, runtime=runtime, ledger=ledger),
                cache_dir=cache_path,
                max_candidates=1,
            )
            reports["founder_team"] = _merge_reports(reports["founder_team"], founder_report)
            final_candidate = founder_enriched[0]
            _merge_report_summary_into_ledger(ledger, founder_report, prefix="founder")

        if final_candidate.identity_type == "verified_company" and not runtime.candidate_exceeded(candidate_started_at):
            owner_enriched, owner_report = enrich_owner_evidence(
                [final_candidate],
                query_runner=_budgeted_query_runner(query_runner, runtime=runtime, ledger=ledger),
                page_fetcher=_budgeted_page_fetcher(page_fetcher, runtime=runtime, ledger=ledger),
                cache_dir=cache_path,
                max_candidates=1,
            )
            reports["owner_evidence"] = _merge_reports(reports["owner_evidence"], owner_report)
            final_candidate = owner_enriched[0]
            _merge_report_summary_into_ledger(ledger, owner_report, prefix="owner")

        row_payload = _row_from_candidate(final_candidate, row, identity_report)
        if runtime.candidate_exceeded(candidate_started_at):
            row_payload = _mark_partial_row(row_payload, "per_candidate_timeout_seconds_exceeded")
        if ledger["partial_reason"]:
            row_payload = _mark_partial_row(row_payload, ledger["partial_reason"])
        _finalize_ledger_item(ledger, row_payload, started_at=candidate_started_at, runtime=runtime)
        enriched_rows.append(row_payload)

    passthrough_product = list(phase6b_payload.get("product_context_rows", []) or [])
    passthrough_projects = list(phase6b_payload.get("project_only_rows", []) or [])
    rejected = list(phase6b_payload.get("rejected_rows", []) or [])
    runtime_ledger = _runtime_ledger_payload(ledger_items, runtime=runtime)
    return {
        "phase": "Phase 6B.2-HN",
        "scope": "HN outbound candidate enrichment; weekly default unchanged; YC remains parked.",
        "partial": runtime.budget_exceeded or any(item["status"] in {"partial", "skipped"} for item in ledger_items),
        "budget_exceeded": runtime.budget_exceeded or bool(skipped_rows),
        "budget_reasons": runtime.budget_reasons,
        "summary": _summary(enriched_rows, passthrough_product, passthrough_projects, rejected, skipped_rows, runtime_ledger),
        "enriched_outbound_candidates": enriched_rows,
        "skipped_candidates": skipped_rows,
        "product_context_rows": passthrough_product,
        "project_only_rows": passthrough_projects,
        "rejected_rows": rejected,
        "runtime_ledger": runtime_ledger,
        "reports": reports,
    }


def load_phase6b_payload(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def write_hn_outbound_enrichment_artifacts(payload: dict, output_dir: Path | str) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    json_path = path / "hn-outbound-enrichment.json"
    md_path = path / "hn-outbound-enrichment.md"
    ledger_path = path / "hn-enrichment-runtime-ledger.json"
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_markdown(payload))
    ledger_path.write_text(json.dumps(payload.get("runtime_ledger", {}), indent=2))
    return [json_path, md_path, ledger_path]


def _new_ledger_item(row: dict, *, index: int) -> dict:
    return {
        "index": index,
        "name": row.get("name") or row.get("source_title") or row.get("company_domain") or "",
        "domain": row.get("company_domain") or row.get("outbound_domain") or "",
        "status": "in_progress",
        "partial_reason": "",
        "elapsed_seconds": 0.0,
        "page_fetches": 0,
        "page_cache_hits": 0,
        "live_queries": 0,
        "query_cache_hits": 0,
        "queries_skipped": 0,
        "attio_checks": 0,
        "attio_skipped": 0,
        "timeouts": 0,
        "identity_status": "",
        "maturity_status": "",
        "founder_evidence_found": False,
        "customer_evidence_found": False,
        "final_action": "",
        "unsafe_promotion": False,
        "missing_evidence": [],
    }


def _merge_reports(existing: dict, incoming: dict) -> dict:
    merged = {
        "summary": dict(existing.get("summary") or {}),
        "items": list(existing.get("items") or []),
    }
    for key, value in (incoming.get("summary") or {}).items():
        if isinstance(value, int):
            merged["summary"][key] = int(merged["summary"].get(key, 0)) + value
        else:
            merged["summary"][key] = value
    merged["items"].extend(incoming.get("items") or [])
    return merged


def _merge_report_summary_into_ledger(ledger: dict, report: dict, *, prefix: str) -> None:
    summary = report.get("summary") or {}
    ledger["query_cache_hits"] += int(summary.get("query_cache_hits", 0))
    if prefix == "owner":
        ledger["page_cache_hits"] += int(summary.get("page_cache_hits", 0))
        ledger["page_fetches"] += int(summary.get("page_fetches", 0))


def _budgeted_query_runner(query_runner: Callable | None, *, runtime: _RuntimeBudget, ledger: dict) -> Callable | None:
    if not query_runner:
        return None

    def run(topic: str, **kwargs) -> dict:
        if not runtime.can_run_live_query():
            ledger["queries_skipped"] += 1
            return {"items": [], "_budget_skipped": True, "budget_reason": "max_live_queries_exceeded"}
        runtime.mark_live_query()
        ledger["live_queries"] += 1
        try:
            with _timeout(_query_timeout_seconds(runtime)):
                return query_runner(topic, **kwargs)
        except _CallTimeout:
            runtime.mark_timeout("live_query_timeout")
            ledger["timeouts"] += 1
            ledger["partial_reason"] = ledger["partial_reason"] or "live_query_timeout"
            return {"items": [], "_timeout": True}

    return run


def _budgeted_page_fetcher(page_fetcher: Callable | None, *, runtime: _RuntimeBudget, ledger: dict) -> Callable:
    fetch = page_fetcher or _default_page_fetcher

    def run(url: str):
        if runtime.runtime_exceeded():
            ledger["partial_reason"] = ledger["partial_reason"] or "max_runtime_seconds_exceeded"
            return ""
        runtime.mark_page_fetch()
        ledger["page_fetches"] += 1
        try:
            with _timeout(_page_timeout_seconds(runtime)):
                return fetch(url)
        except _CallTimeout:
            runtime.mark_timeout("page_fetch_timeout")
            ledger["timeouts"] += 1
            ledger["partial_reason"] = ledger["partial_reason"] or "page_fetch_timeout"
            return ""

    return run


def _query_timeout_seconds(runtime: _RuntimeBudget) -> float | None:
    return _bounded_call_timeout(runtime, default_ceiling=75.0)


def _page_timeout_seconds(runtime: _RuntimeBudget) -> float | None:
    return _bounded_call_timeout(runtime, default_ceiling=5.0)


def _attio_timeout_seconds(runtime: _RuntimeBudget) -> float | None:
    return _bounded_call_timeout(runtime, default_ceiling=10.0)


def _bounded_call_timeout(runtime: _RuntimeBudget, *, default_ceiling: float) -> float | None:
    candidates = [default_ceiling]
    if runtime.per_candidate_timeout_seconds:
        candidates.append(runtime.per_candidate_timeout_seconds)
    remaining = runtime.remaining_runtime_seconds()
    if remaining is not None:
        candidates.append(remaining)
    timeout = min(candidates)
    if timeout <= 0:
        return 0.001
    return max(0.001, timeout)


def _skipped_row(row: dict, *, reason: str, ledger: dict) -> dict:
    ledger["status"] = "skipped"
    ledger["partial_reason"] = reason
    return {
        "name": row.get("name") or row.get("source_title") or row.get("company_domain") or "",
        "canonical_name": row.get("name") or row.get("company_domain") or "",
        "official_domain": row.get("company_domain") or row.get("outbound_domain") or "",
        "source_title": row.get("source_title", ""),
        "source_url": row.get("source_url", ""),
        "official_url": row.get("official_url", ""),
        "identity_type": row.get("identity_type", "hn_outbound_candidate"),
        "identity_promotion_status": "skipped",
        "maturity_status": row.get("maturity_status", "unknown"),
        "lead_route": "research_deeper",
        "owner_readiness_score": 0,
        "owner_readiness_basis": [],
        "missing_owner_evidence": [reason],
        "recommended_action": ACTION_RESEARCH_DEEPER,
        "next_validation_step": "Rerun with larger HN enrichment budget",
        "assign_owner": False,
        "new_to_marathon": False,
        "unsafe_promotion": False,
        "partial": True,
        "partial_reason": reason,
        "missing_evidence": [reason],
        "movement": row.get("movement", ""),
        "market_sector": row.get("market_sector", ""),
    }


def _mark_partial_row(row: dict, reason: str) -> dict:
    out = dict(row)
    out["partial"] = True
    out["partial_reason"] = reason
    out["assign_owner"] = False
    out["new_to_marathon"] = False
    out["unsafe_promotion"] = False
    out["recommended_action"] = ACTION_RESEARCH_DEEPER
    out["missing_owner_evidence"] = list(dict.fromkeys(list(out.get("missing_owner_evidence") or []) + [reason]))
    out["missing_evidence"] = list(dict.fromkeys(list(out.get("missing_evidence") or []) + [reason]))
    out["next_validation_step"] = "Rerun with larger HN enrichment budget"
    return out


def _finalize_ledger_item(ledger: dict, row: dict, *, started_at: float, runtime: _RuntimeBudget) -> None:
    if row.get("partial") and not ledger.get("partial_reason"):
        ledger["partial_reason"] = row.get("partial_reason", "")
    if ledger["status"] == "in_progress":
        ledger["status"] = "partial" if row.get("partial") else "completed"
    ledger["elapsed_seconds"] = round(max(0.0, runtime.time_fn() - started_at), 3)
    ledger["identity_status"] = row.get("identity_promotion_status", "")
    ledger["maturity_status"] = row.get("maturity_status", "")
    ledger["founder_evidence_found"] = bool(row.get("founder_team_evidence"))
    ledger["customer_evidence_found"] = bool(row.get("customer_buyer_evidence"))
    ledger["final_action"] = row.get("recommended_action", "")
    ledger["unsafe_promotion"] = bool(row.get("unsafe_promotion"))
    ledger["missing_evidence"] = list(row.get("missing_evidence") or [])


def _runtime_ledger_payload(items: list[dict], *, runtime: _RuntimeBudget) -> dict:
    return {
        "summary": {
            "candidates_seen": len(items),
            "candidates_completed": sum(1 for item in items if item.get("status") == "completed"),
            "candidates_partially_enriched": sum(1 for item in items if item.get("status") == "partial"),
            "candidates_skipped": sum(1 for item in items if item.get("status") == "skipped"),
            "live_queries": runtime.live_queries,
            "attio_checks": runtime.attio_checks,
            "page_fetches": runtime.page_fetches,
            "timeouts": runtime.timeouts,
            "elapsed_seconds": round(runtime.elapsed(), 3),
            "budget_exceeded": runtime.budget_exceeded,
            "budget_reasons": list(runtime.budget_reasons),
        },
        "items": items,
    }


def _candidate_from_hn_row(row: dict) -> Candidate:
    domain = _normalize_domain(row.get("company_domain") or row.get("outbound_domain") or row.get("official_url", ""))
    raw_name = row.get("name") or row.get("source_title") or domain
    clean_name = _clean_company_name(raw_name, domain)
    identity = canonicalize_identity(
        name=clean_name,
        domain=domain,
        candidate_type="company_web",
        identity_type=row.get("identity_type", ""),
        raw_title=row.get("source_title", ""),
        source_headline=row.get("source_title", ""),
    )
    if "." in clean_name and _normalize_domain(clean_name) == domain:
        identity["canonical_name"] = clean_name
        identity["display_name"] = clean_name
    candidate = Candidate(
        name=identity["canonical_name"],
        canonical_name=identity["canonical_name"],
        display_name=identity["display_name"],
        source_headline=identity["source_headline"],
        tagline=identity["tagline"],
        sector=row.get("market_sector", ""),
        market_sector=row.get("market_sector", ""),
        theme=row.get("movement", ""),
        source=row.get("source_url", ""),
        sources=[url for url in [row.get("source_url", ""), row.get("official_url", "")] if url],
        candidate_type="company_web",
        stable_key=f"hn-outbound:{row.get('source_url') or domain or clean_name}",
        domain=domain,
        why_on_radar=row.get("source_title") or row.get("name", ""),
        why_this_may_be_noise="HN outbound evidence requires independent official-domain, maturity, founder, customer, and Attio validation.",
        identity_type=row.get("identity_type", "hn_outbound_candidate"),
        identity_confidence_score=int(row.get("identity_confidence_score") or 0),
        identity_confidence_basis=list(row.get("identity_basis") or []),
        verified_domain_basis=list(row.get("verified_domain_basis") or []),
        maturity_status=row.get("maturity_status", "unknown"),
        maturity_basis=list(row.get("maturity_basis") or []),
        maturity_evidence_urls=list(row.get("maturity_evidence_urls") or []),
        lead_route=row.get("lead_route", "research_deeper"),
        attio_status=row.get("attio_status", "unknown"),
        attio_safe_to_match=False,
        evidence_metadata=[
            {
                "source": "hackernews",
                "source_url": row.get("source_url", ""),
                "outbound_url": row.get("official_url", ""),
                "domain": domain,
                "title": row.get("source_title", ""),
                "author": row.get("hn_author", ""),
                "engagement": row.get("hn_engagement", {}),
            }
        ],
    )
    return candidate


def _promote_identity(
    candidate: Candidate,
    row: dict,
    *,
    page_fetcher: Callable | None,
    cache_dir: Path | None,
    runtime: _RuntimeBudget,
    ledger: dict,
) -> tuple[Candidate, dict]:
    out = Candidate.from_dict(candidate.to_dict())
    domain = _normalize_domain(out.domain)
    urls = _identity_urls(row, domain)
    checked: list[str] = []
    failed: list[str] = []
    matched_url = ""
    fetch = page_fetcher or _default_page_fetcher
    for url in urls:
        payload, cache_status = _read_or_fetch_page(url, fetch, cache_dir, runtime=runtime, ledger=ledger)
        if cache_status == "cache_hit":
            ledger["page_cache_hits"] += 1
        text = _page_text(payload)
        if text:
            checked.append(url)
        else:
            failed.append(url)
        if text and _official_text_confirms_identity(text, out.display_name or out.name, domain):
            matched_url = url
            break
    if matched_url:
        out.identity_type = "verified_company"
        out.identity_confidence_score = max(out.identity_confidence_score, 85)
        out.identity_confidence = "High"
        out.identity_confidence_basis = list(
            dict.fromkeys(list(out.identity_confidence_basis) + ["official_site_confirms_identity"])
        )
        out.verified_domain_basis = list(dict.fromkeys(list(out.verified_domain_basis) + ["official_site_identity_check"]))
        out.attio_safe_to_match = True
        out.missing_identity_evidence = []
        status = "promoted"
    else:
        out.identity_type = "hn_outbound_candidate"
        out.identity_confidence_score = min(out.identity_confidence_score or 65, 65)
        out.identity_confidence = "Medium"
        out.attio_safe_to_match = False
        out.missing_identity_evidence = list(
            dict.fromkeys(list(out.missing_identity_evidence) + ["official_domain_identity_not_confirmed"])
        )
        status = "not_promoted"
    return out, {
        "candidate_key": _candidate_key(out),
        "name": out.display_name or out.name,
        "domain": domain,
        "identity_promotion_status": status,
        "official_identity_url": matched_url,
        "official_site_pages_checked": checked,
        "official_site_pages_failed": failed,
        "missing_identity_evidence": list(out.missing_identity_evidence),
    }


def _apply_attio(candidate: Candidate, attio_matcher: Callable | None, *, runtime: _RuntimeBudget, ledger: dict) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    if not attio_matcher:
        out.attio_status = out.attio_status or "unknown"
        return out
    if not runtime.can_check_attio():
        ledger["attio_skipped"] += 1
        ledger["partial_reason"] = ledger["partial_reason"] or "attio_budget_exceeded"
        out.attio_status = "unknown"
        out.attio_safe_to_match = False
        out.missing_owner_evidence = list(dict.fromkeys(list(out.missing_owner_evidence) + ["attio_budget_exceeded"]))
        return out
    runtime.mark_attio_check()
    ledger["attio_checks"] += 1
    try:
        with _timeout(_attio_timeout_seconds(runtime)):
            payload = attio_matcher(out)
    except _CallTimeout:
        runtime.mark_timeout("attio_timeout")
        ledger["timeouts"] += 1
        ledger["partial_reason"] = ledger["partial_reason"] or "attio_timeout"
        out.attio_status = "unknown"
        out.attio_safe_to_match = False
        out.missing_owner_evidence = list(dict.fromkeys(list(out.missing_owner_evidence) + ["attio_timeout"]))
        return out
    if not isinstance(payload, dict):
        return out
    for key, value in payload.items():
        if hasattr(out, key):
            setattr(out, key, value)
    if out.identity_type == "verified_company" and out.domain:
        out.attio_safe_to_match = True
        if not out.attio_match_keys:
            out.attio_match_keys = [out.domain]
    return out


def _enrich_maturity(candidate: Candidate, *, query_runner: Callable | None, cache_dir: Path | None, runtime: _RuntimeBudget, ledger: dict) -> tuple[Candidate, dict]:
    topic = _maturity_query(candidate)
    payload, query_status = _run_cached_query(
        topic,
        query_runner=_budgeted_query_runner(query_runner, runtime=runtime, ledger=ledger),
        cache_dir=cache_dir,
        ledger=ledger,
    )
    items = list(payload.get("items") or []) if isinstance(payload, dict) else []
    maturity = _classify_maturity_from_items(items, company_name=candidate.name, domain=candidate.domain)
    out = Candidate.from_dict(candidate.to_dict())
    if maturity.get("maturity_status") != "unknown":
        out.maturity_status = maturity.get("maturity_status", "unknown")
        out.maturity_basis = list(maturity.get("maturity_basis") or [])
        out.maturity_evidence_urls = list(maturity.get("maturity_evidence_urls") or [])
        out.category_anchor = bool(maturity.get("category_anchor"))
        out.consensus_risk_reason = maturity.get("consensus_risk_reason", "")
        out.lead_route = maturity.get("lead_route", out.lead_route or "research_deeper")
    elif out.maturity_status in {"", "unknown"}:
        out.maturity_status = "unknown"
        out.maturity_basis = ["maturity_not_verified"]
        out.lead_route = "research_deeper"
    return out, {
        "candidate_key": _candidate_key(out),
        "query": topic,
        "query_status": query_status,
        "items_seen": len(items),
        "maturity_status": out.maturity_status,
        "maturity_basis": list(out.maturity_basis),
        "maturity_evidence_urls": list(out.maturity_evidence_urls),
    }


def _skipped_maturity_report(candidate: Candidate, reason: str) -> dict:
    return {
        "candidate_key": _candidate_key(candidate),
        "query": "",
        "query_status": "not_eligible",
        "skip_reason": reason,
        "items_seen": 0,
        "maturity_status": candidate.maturity_status,
        "maturity_basis": _clean_maturity_basis(candidate),
        "maturity_evidence_urls": list(candidate.maturity_evidence_urls),
    }


def _row_from_candidate(candidate: Candidate, original_row: dict, identity_report: dict) -> dict:
    score, basis, missing, next_step = score_owner_readiness(candidate)
    score, basis, missing, next_step, evidence = _strict_hn_owner_outputs(candidate, score, basis, missing, next_step)
    action = _recommended_action(candidate, score, missing)
    assign_owner = action == ACTION_ASSIGN_OWNER
    unsafe = bool(assign_owner and _unsafe_assign_owner(candidate, missing))
    return {
        "name": candidate.display_name or candidate.canonical_name or candidate.name,
        "canonical_name": candidate.canonical_name or candidate.name,
        "official_domain": candidate.domain,
        "source_title": original_row.get("source_title", ""),
        "source_url": original_row.get("source_url", ""),
        "official_url": original_row.get("official_url", ""),
        "hn_author": original_row.get("hn_author", ""),
        "hn_engagement": original_row.get("hn_engagement", {}),
        "identity_type": candidate.identity_type,
        "identity_promotion_status": identity_report.get("identity_promotion_status", ""),
        "identity_basis": list(candidate.identity_confidence_basis),
        "identity_confidence_score": candidate.identity_confidence_score,
        "missing_identity_evidence": list(candidate.missing_identity_evidence),
        "maturity_status": candidate.maturity_status,
        "maturity_basis": _clean_maturity_basis(candidate),
        "maturity_evidence_urls": list(candidate.maturity_evidence_urls),
        "lead_route": candidate.lead_route,
        "category_anchor": candidate.category_anchor,
        "founder_team_evidence": evidence["founder_team_evidence"],
        "founders": evidence["founders"],
        "founder_profiles": evidence["founder_profiles"],
        "stage_funding_evidence": evidence["stage_funding_evidence"],
        "customer_buyer_evidence": evidence["customer_buyer_evidence"],
        "customer_buyer_evidence_types": evidence["customer_buyer_evidence_types"],
        "attio_status": candidate.attio_status,
        "attio_safe_to_match": candidate.attio_safe_to_match,
        "attio_confidence": candidate.attio_confidence,
        "attio_confidence_basis": list(candidate.attio_confidence_basis),
        "owner_readiness_score": score,
        "owner_readiness_basis": list(basis),
        "missing_owner_evidence": list(missing),
        "recommended_action": action,
        "recommended_lane": "HN Enriched Outbound Candidates",
        "next_validation_step": next_step,
        "assign_owner": assign_owner,
        "new_to_marathon": assign_owner
        and candidate.identity_type == "verified_company"
        and candidate.attio_safe_to_match
        and (candidate.attio_status or "").lower() in {"no_match", "not_found", "new"},
        "unsafe_promotion": unsafe,
        "missing_evidence": list(dict.fromkeys(list(candidate.missing_identity_evidence) + list(missing))),
        "official_site_pages_checked": list(identity_report.get("official_site_pages_checked") or []),
        "official_identity_url": identity_report.get("official_identity_url", ""),
        "movement": original_row.get("movement", ""),
        "market_sector": original_row.get("market_sector", ""),
    }


def _recommended_action(candidate: Candidate, score: int, missing: list[str]) -> str:
    if candidate.category_anchor or candidate.lead_route in {"category_context", "monitor_only"} or candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return ACTION_MONITOR_ONLY
    if (
        candidate.lead_route == "sourcing_candidate"
        and candidate.identity_type == "verified_company"
        and candidate.attio_safe_to_match
        and (candidate.attio_status or "").lower() in {"no_match", "not_found", "new", "no_owner"}
        and score >= 80
        and not missing
    ):
        return ACTION_ASSIGN_OWNER
    return ACTION_RESEARCH_DEEPER


def _clean_maturity_basis(candidate: Candidate) -> list[str]:
    basis = list(candidate.maturity_basis)
    if candidate.maturity_status != "unknown" and len(basis) > 1:
        basis = [item for item in basis if item != "maturity_not_verified"]
    return basis


def _strict_hn_owner_outputs(
    candidate: Candidate,
    score: int,
    basis: list[str],
    missing: list[str],
    next_step: str,
) -> tuple[int, list[str], list[str], str, dict]:
    strict_founder_profiles = _named_founder_profiles(candidate)
    strict_founders = list(dict.fromkeys(list(candidate.founders) + [profile.get("name", "") for profile in strict_founder_profiles if profile.get("name")]))
    strict_founder_urls = list(dict.fromkeys(profile.get("source", "") for profile in strict_founder_profiles if profile.get("source")))
    strict_stage_urls = list(candidate.stage_funding_evidence) if candidate.maturity_status == "seed_to_series_b" else []
    strong_customer_types = _strong_customer_evidence_types(candidate)
    strict_customer_urls = [item["url"] for item in strong_customer_types] if strong_customer_types else list(candidate.customer_buyer_evidence)

    basis = list(basis)
    missing = list(missing)
    if "founder_team_evidence" in basis and not (strict_founders or strict_founder_profiles):
        basis.remove("founder_team_evidence")
        score -= 25
        missing.append("no founder/team evidence")
    if "stage_funding_evidence" in basis and not strict_stage_urls:
        basis.remove("stage_funding_evidence")
        score -= 25
        missing.append("no stage/funding evidence")
    if "customer_buyer_pull_evidence" in basis and not strict_customer_urls:
        basis.remove("customer_buyer_pull_evidence")
        score -= 15
        missing.append("no customer/buyer pull evidence")
    if "commercial_or_funding_evidence" in basis and not (strict_stage_urls or strict_customer_urls):
        basis.remove("commercial_or_funding_evidence")
        score -= 10
        missing.append("no commercial/funding evidence")
    missing = list(dict.fromkeys(missing))
    basis = list(dict.fromkeys(basis))
    return max(0, min(100, score)), basis, missing, _next_validation_step(missing, next_step), {
        "founder_team_evidence": strict_founder_urls,
        "founders": strict_founders,
        "founder_profiles": strict_founder_profiles,
        "stage_funding_evidence": strict_stage_urls,
        "customer_buyer_evidence": strict_customer_urls,
        "customer_buyer_evidence_types": strong_customer_types,
    }


def _named_founder_profiles(candidate: Candidate) -> list[dict]:
    profiles = []
    for profile in candidate.founder_profiles:
        name = str(profile.get("name", "")).strip()
        if name and name.lower() != "source-backed founder/team evidence":
            profiles.append(dict(profile))
    return profiles


def _strong_customer_evidence_types(candidate: Candidate) -> list[dict]:
    strong_types = {
        "named_customer_evidence",
        "early_customer_segment_evidence",
        "buyer_pain_evidence",
        "waitlist_or_demo_evidence",
        "commercial_intent_evidence",
    }
    rows: list[dict] = []
    for item in getattr(candidate, "customer_buyer_evidence_types", []) or []:
        labels = [label for label in item.get("evidence_types", []) if label in strong_types]
        url = item.get("url", "")
        if url and labels:
            rows.append({"url": url, "evidence_types": labels})
    return rows


def _next_validation_step(missing: list[str], fallback: str) -> str:
    if any("founder" in item.lower() for item in missing):
        return "Find founder/team source"
    if any("stage" in item.lower() or "funding" in item.lower() for item in missing):
        return "Verify stage/funding source"
    if any("customer" in item.lower() or "buyer" in item.lower() for item in missing):
        return "Find buyer/customer pull evidence"
    if any("attio" in item.lower() for item in missing):
        return "Check Attio match/status"
    return fallback or "Review enriched HN outbound evidence"


def _unsafe_assign_owner(candidate: Candidate, missing: list[str]) -> bool:
    return bool(
        candidate.identity_type != "verified_company"
        or candidate.maturity_status != "seed_to_series_b"
        or not candidate.attio_safe_to_match
        or (candidate.attio_status or "").lower() not in {"no_match", "not_found", "new", "no_owner"}
        or missing
    )


def _summary(rows: list[dict], product_rows: list[dict], project_rows: list[dict], rejected_rows: list[dict], skipped_rows: list[dict] | None = None, runtime_ledger: dict | None = None) -> dict:
    skipped_rows = skipped_rows or []
    ledger_summary = (runtime_ledger or {}).get("summary", {})
    return {
        "hn_outbound_candidates_input": len(rows) + len(skipped_rows),
        "candidates_enriched": len(rows),
        "candidates_skipped": len(skipped_rows),
        "candidates_partially_enriched": sum(1 for row in rows if row.get("partial")),
        "live_queries": ledger_summary.get("live_queries", 0),
        "attio_checks": ledger_summary.get("attio_checks", 0),
        "page_fetches": ledger_summary.get("page_fetches", 0),
        "timeouts": ledger_summary.get("timeouts", 0),
        "identity_promoted_rows": sum(1 for row in rows if row.get("identity_promotion_status") == "promoted"),
        "identity_not_promoted_rows": sum(1 for row in rows if row.get("identity_promotion_status") != "promoted"),
        "maturity_confirmed_early_stage_rows": sum(1 for row in rows if row.get("maturity_status") == "seed_to_series_b"),
        "early_stage_context_rows": sum(1 for row in rows if row.get("maturity_status") == "early_stage_context"),
        "research_deeper_rows": sum(1 for row in rows if row.get("recommended_action") == ACTION_RESEARCH_DEEPER),
        "category_context_rows": sum(1 for row in rows if row.get("lead_route") in {"category_context", "monitor_only"}),
        "assign_owner_rows": sum(1 for row in rows if row.get("assign_owner")),
        "new_to_marathon_rows": sum(1 for row in rows if row.get("new_to_marathon")),
        "unsafe_promotions": sum(1 for row in rows if row.get("unsafe_promotion")),
        "product_context_rows": len(product_rows),
        "project_only_rows": len(project_rows),
        "rejected_rows": len(rejected_rows),
    }


def _markdown(payload: dict) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Phase 6B.2 HN Outbound Enrichment",
        "",
        "Offline enrichment for HN outbound candidates. Weekly default is unchanged, project/product rows are not promoted, and YC remains parked.",
        "",
        "## Summary",
        "",
    ]
    for key in (
        "hn_outbound_candidates_input",
        "identity_promoted_rows",
        "identity_not_promoted_rows",
        "maturity_confirmed_early_stage_rows",
        "early_stage_context_rows",
        "research_deeper_rows",
        "assign_owner_rows",
        "new_to_marathon_rows",
        "unsafe_promotions",
        "product_context_rows",
        "project_only_rows",
    ):
        lines.append(f"- {key}: {summary.get(key, 0)}")
    lines.extend(["", "## Enriched HN Outbound Candidates", ""])
    for row in payload.get("enriched_outbound_candidates", []) or []:
        lines.append(
            f"- {row.get('name')} - {row.get('recommended_action')} - identity: {row.get('identity_type')} "
            f"({row.get('identity_promotion_status')}) - maturity: {row.get('maturity_status')} - "
            f"missing: {', '.join(row.get('missing_owner_evidence') or []) or 'none'}"
        )
    if not payload.get("enriched_outbound_candidates"):
        lines.append("- None")
    lines.extend(["", "## Product / Category Context Preserved", ""])
    if payload.get("product_context_rows"):
        for row in payload["product_context_rows"]:
            lines.append(f"- {row.get('name')} - {row.get('recommended_lane', 'HN Product / Category Context')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Project Watch Preserved", ""])
    lines.append(f"- {len(payload.get('project_only_rows') or [])} project-only rows preserved.")
    return "\n".join(lines) + "\n"


def _identity_urls(row: dict, domain: str) -> list[str]:
    urls = []
    for value in (row.get("official_url", ""), f"https://{domain}" if domain else ""):
        if value and value not in urls:
            urls.append(value)
    return urls[:2]


def _read_or_fetch_page(url: str, fetcher: Callable, cache_dir: Path | None, *, runtime: _RuntimeBudget, ledger: dict):
    if not cache_dir:
        return _budgeted_page_fetcher(fetcher, runtime=runtime, ledger=ledger)(url), "fetched"
    path = cache_dir / "hn-official-pages" / f"{_stable_hash(url)}.json"
    if path.exists():
        try:
            return json.loads(path.read_text()).get("payload", ""), "cache_hit"
        except json.JSONDecodeError:
            return "", "cache_error"
    payload = _budgeted_page_fetcher(fetcher, runtime=runtime, ledger=ledger)(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "payload": payload}, indent=2))
    return payload, "fetched"


def _run_cached_query(topic: str, *, query_runner: Callable | None, cache_dir: Path | None, ledger: dict | None = None) -> tuple[dict, str]:
    if not query_runner:
        return {"items": []}, "not_queried"
    if cache_dir:
        path = cache_dir / "hn-outbound-queries" / f"{_stable_hash(topic)}.json"
        if path.exists():
            try:
                if ledger is not None:
                    ledger["query_cache_hits"] += 1
                return json.loads(path.read_text()), "cache_hit"
            except json.JSONDecodeError:
                pass
    payload = query_runner(
        topic,
        sources="grounding",
        lookback_days=30,
        auto_resolve=True,
        store=True,
        web_backend="auto",
    )
    if isinstance(payload, dict) and payload.get("_budget_skipped"):
        return payload, "budget_skipped"
    if isinstance(payload, dict) and payload.get("_timeout"):
        return payload, "timeout"
    if cache_dir:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
    return payload, "queried"


def _maturity_query(candidate: Candidate) -> str:
    return f'"{candidate.name}" "{candidate.domain}" funding valuation acquisition Series C seed'


def _official_text_confirms_identity(text: str, name: str, domain: str) -> bool:
    normalized_text = _key(text)
    normalized_name = _key(_clean_company_name(name, domain))
    domain_root = _normalize_domain(domain).split(".")[0]
    return bool(
        normalized_text
        and (
            (normalized_name and normalized_name in normalized_text)
            or (domain_root and _key(domain_root) in normalized_text)
        )
    )


def _clean_company_name(name: str, domain: str = "") -> str:
    cleaned = ACCELERATOR_SUFFIX_RE.sub(" ", name or "")
    cleaned = re.sub(r"^(?:Show|Launch)\s+HN:\s*", "", cleaned, flags=re.IGNORECASE)
    for sep in (" - ", " – ", " — ", " | "):
        if sep in cleaned:
            cleaned = cleaned.split(sep, 1)[0]
            break
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned and domain:
        cleaned = _normalize_domain(domain).split(".")[0].title()
    return cleaned


def _page_text(payload) -> str:
    if isinstance(payload, dict):
        payload = " ".join(str(payload.get(key, "")) for key in ("title", "snippet", "description", "body", "html", "payload"))
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", str(payload or ""))
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith(("http://", "https://")):
        raw = urlparse(raw).netloc
    raw = raw.split("/", 1)[0].lower().strip("/")
    return raw[4:] if raw.startswith("www.") else raw


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _candidate_key(candidate: Candidate) -> str:
    return candidate.stable_key or candidate.domain or candidate.name


def _default_query_runner(topic: str, **kwargs) -> dict:
    from last30days_adapter import run_query

    return run_query(topic, timeout_seconds=75, **kwargs)


def _default_attio_matcher(candidate: Candidate) -> dict:
    try:
        from attio import AttioClient, get_access_token
    except ImportError:
        return {"attio_status": "unknown"}
    token, _source = get_access_token()
    if not token:
        return {"attio_status": "unknown"}
    return AttioClient(token).match_company({"name": candidate.name, "domain": candidate.domain})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 6B.2 HN outbound enrichment.")
    parser.add_argument("--phase6b-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--live-queries", action="store_true")
    parser.add_argument("--attio", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--max-runtime-seconds", type=float, default=None)
    parser.add_argument("--max-attio-checks", type=int, default=None)
    parser.add_argument("--max-live-queries", type=int, default=None)
    parser.add_argument("--per-candidate-timeout-seconds", type=float, default=None)
    args = parser.parse_args(argv)
    payload = run_hn_outbound_enrichment(
        load_phase6b_payload(args.phase6b_json),
        query_runner=_default_query_runner if args.live_queries else None,
        page_fetcher=None,
        attio_matcher=_default_attio_matcher if args.attio else None,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        max_candidates=args.max_candidates,
        max_runtime_seconds=args.max_runtime_seconds,
        max_attio_checks=args.max_attio_checks,
        max_live_queries=args.max_live_queries,
        per_candidate_timeout_seconds=args.per_candidate_timeout_seconds,
    )
    write_hn_outbound_enrichment_artifacts(payload, args.output_dir)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
