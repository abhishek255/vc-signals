from __future__ import annotations

import html as html_lib
import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from radar_models import Candidate, DiscoveryQuery, FocusItem, ThemeSignal, VerifiedCompanyDiscoveryLead


COMPANY_INTENT_TERMS = ("startup", "company", "founder", "launch", "seed", "yc", "raises", "website")
BROAD_THEMES = {"ai", "devtools", "cybersecurity", "data", "oss", "automation"}
GENERIC_EXTRACTED_NAMES = {
    "ai",
    "the",
    "new",
    "top",
    "how",
    "what",
    "why",
    "us",
    "ai startups",
    "open source ai",
}
GENERIC_MOVEMENTS = {"emerging technical signal", "unclassified technical tooling", "oss company-formation watchlist"}
IDENTITY_MISSING_TERMS = ("domain", "founder", "company", "identity")
NOISY_OSS_TERMS = ("template", "tutorial", "example", "demo", "boilerplate")
STRONG_MOVEMENT_PHRASES = ("ai agent", "agent security", "mcp", "tool permissions", "runtime security", "agent permissions")
CONTENT_PLATFORM_DOMAINS = {
    "github.com",
    "news.ycombinator.com",
    "medium.com",
    "substack.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "reddit.com",
    "docs.google.com",
    "notion.site",
    "deepwiki.com",
}
PUBLISHER_DOMAINS = {
    "techcrunch.com",
    "morningstar.com",
    "timesofisrael.com",
    "prnewswire.com",
    "businesswire.com",
    "globenewswire.com",
    "einpresswire.com",
    "venturebeat.com",
    "forbes.com",
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    "darkreading.com",
    "securityweek.com",
    "lasvegassun.com",
    "indiatoday.in",
    "moneycontrol.com",
    "goerie.com",
    "economictimes.indiatimes.com",
    "zerohedge.com",
}
DIRECTORY_DOMAINS = {
    "crunchbase.com",
    "cbinsights.com",
    "pitchbook.com",
    "g2.com",
    "capterra.com",
    "vcbacked.co",
    "tracxn.com",
}
PUBLISHER_DOMAIN_HINTS = (
    "news",
    "times",
    "today",
    "sun",
    "week",
    "crunch",
    "morningstar",
    "prnewswire",
    "wire",
    "press",
)
TOO_LATE_TERMS = (
    "acquires",
    "acquired",
    "buys",
    "purchases",
    "series c",
    "series d",
    "series e",
    "unicorn",
    "$1b",
    "$100m",
    "$200m",
)
ARTICLE_FETCH_TIMEOUT_SECONDS = 8
ARTICLE_FETCH_MAX_BYTES = 200_000
ARTICLE_MAX_PARAGRAPHS = 5
ARTICLE_MAX_LINKS = 20
ARTICLE_MAX_TEXT_CHARS = 1_200
ARTICLE_MIN_PARAGRAPH_CHARS = 40


@dataclass
class DiscoveryRunBudget:
    mode: str = "weekly"
    max_runtime_seconds: int | None = None
    max_company_discovery_queries: int | None = None
    max_maturity_queries: int | None = None
    max_article_fetches: int | None = None
    max_results_per_query: int | None = None
    per_movement_query_cap: int | None = None
    query_cache_ttl_seconds: int = 24 * 60 * 60
    allow_stale_cache: bool = True

    @classmethod
    def for_mode(cls, mode: str = "weekly", **overrides) -> "DiscoveryRunBudget":
        defaults = {
            "smoke": {
                "mode": "smoke",
                "max_runtime_seconds": 5 * 60,
                "max_company_discovery_queries": 3,
                "max_maturity_queries": 1,
                "max_article_fetches": 2,
                "max_results_per_query": 5,
                "per_movement_query_cap": 1,
            },
            "weekly": {
                "mode": "weekly",
                "max_runtime_seconds": 30 * 60,
                "max_company_discovery_queries": 12,
                "max_maturity_queries": 6,
                "max_article_fetches": 6,
                "max_results_per_query": 10,
                "per_movement_query_cap": 2,
            },
            "deep_dive": {
                "mode": "deep_dive",
                "max_runtime_seconds": 90 * 60,
                "max_company_discovery_queries": 30,
                "max_maturity_queries": 15,
                "max_article_fetches": 12,
                "max_results_per_query": 20,
                "per_movement_query_cap": 4,
            },
            "unbounded": {
                "mode": "unbounded",
                "max_runtime_seconds": None,
                "max_company_discovery_queries": None,
                "max_maturity_queries": None,
                "max_article_fetches": None,
                "max_results_per_query": None,
                "per_movement_query_cap": None,
            },
        }
        payload = dict(defaults.get(mode, defaults["weekly"]))
        for key, value in overrides.items():
            payload[key] = value
        return cls(**payload)


@dataclass
class RuntimeLedger:
    mode: str
    started_monotonic: float = field(default_factory=time.monotonic)
    attempted_queries: int = 0
    completed_queries: int = 0
    skipped_queries: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    cache_hits: int = 0
    stale_cache_hits: int = 0
    live_calls: int = 0
    budget_exceeded: bool = False
    partial: bool = False
    query_events: list[dict] = field(default_factory=list)

    def elapsed(self) -> float:
        return time.monotonic() - self.started_monotonic

    def remaining_seconds(self, budget: DiscoveryRunBudget) -> int | None:
        if budget.max_runtime_seconds is None:
            return None
        remaining = int(budget.max_runtime_seconds - self.elapsed())
        return max(1, remaining)

    def record_skip(self, query: dict, reason: str) -> None:
        self.skipped_queries += 1
        self.partial = True
        self.budget_exceeded = self.budget_exceeded or "budget" in reason or "runtime" in reason or "cap" in reason
        _increment_count(self.skip_reasons, reason)
        self.query_events.append(
            {
                "query_id": query.get("id", ""),
                "movement": query.get("movement", ""),
                "topic": query.get("topic", ""),
                "status": "skipped",
                "reason": reason,
            }
        )

    def record_attempt(self, query: dict, *, cache_status: str = "miss") -> None:
        self.attempted_queries += 1
        self.query_events.append(
            {
                "query_id": query.get("id", ""),
                "movement": query.get("movement", ""),
                "topic": query.get("topic", ""),
                "status": "attempted",
                "cache_status": cache_status,
            }
        )

    def record_complete(self, query: dict, *, cache_status: str = "miss") -> None:
        self.completed_queries += 1
        self.query_events.append(
            {
                "query_id": query.get("id", ""),
                "movement": query.get("movement", ""),
                "topic": query.get("topic", ""),
                "status": "completed",
                "cache_status": cache_status,
            }
        )

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["duration_seconds"] = round(self.elapsed(), 3)
        payload.pop("started_monotonic", None)
        return payload


def build_company_discovery_queries(
    theme_signals: list[ThemeSignal],
    *,
    focus_items: list[FocusItem] | None = None,
    unresolved_candidates: list[Candidate] | None = None,
    grounded_available: bool,
    social_available: bool,
    lookback_days: int = 30,
    max_queries_per_theme: int = 3,
) -> list[dict]:
    """Build targeted company searches from non-company theme evidence."""
    queries: list[dict] = []
    seen_topics = set()

    for signal in theme_signals:
        theme = signal.theme
        if _is_broad_movement(theme):
            continue
        market_sector = signal.market_sector
        required_terms = _movement_terms(theme)
        query_specs = [
            (
                "theme_company_search",
                signal.suggested_search or f"{theme} startups Seed Series A founder launch",
                "theme_signal",
                [f"theme:{_stable_slug(theme)}"],
            ),
            (
                "theme_founder_search",
                f"{theme} startup founder launch company {market_sector}",
                "theme_signal",
                [f"theme:{_stable_slug(theme)}"],
            ),
            (
                "theme_funding_search",
                f"{theme} startup raises seed Series A funding company",
                "theme_signal",
                [f"theme:{_stable_slug(theme)}"],
            ),
        ]
        for kind, topic, reason, origin_ids in query_specs[:max_queries_per_theme]:
            _append_query(
                queries,
                seen_topics,
                kind=kind,
                topic=topic,
                movement=theme,
                market_sector=market_sector,
                source_reason=reason,
                origin_row_ids=origin_ids,
                required_terms=required_terms,
                grounded_available=grounded_available,
                lookback_days=lookback_days,
            )

    for item in focus_items or []:
        if not _focus_item_can_seed_query(item):
            continue
        movement = item.market_movement
        required_terms = _movement_terms(movement)
        topic = f"{movement} startup company founder launch {item.market_sector}".strip()
        _append_query(
            queries,
            seen_topics,
            kind="focus_identity_search",
            topic=topic,
            movement=movement,
            market_sector=item.market_sector,
            source_reason="needs_more_evidence",
            origin_row_ids=[item.id],
            required_terms=required_terms,
            grounded_available=grounded_available,
            lookback_days=lookback_days,
        )

    for candidate in unresolved_candidates or []:
        if not _candidate_can_seed_query(candidate):
            continue
        movement = candidate.theme
        required_terms = _movement_terms(movement)
        topic = f"{movement} startup company founder launch {candidate.name}".strip()
        _append_query(
            queries,
            seen_topics,
            kind="candidate_identity_search",
            topic=topic,
            movement=movement,
            market_sector=candidate.market_sector or candidate.sector,
            source_reason="identity_resolution_target",
            origin_row_ids=[candidate.stable_key or candidate.name],
            required_terms=required_terms,
            grounded_available=grounded_available,
            lookback_days=lookback_days,
        )

    return prioritize_discovery_queries(queries)


def prioritize_discovery_queries(queries: list[dict]) -> list[dict]:
    prioritized = []
    for query in queries:
        payload = dict(query)
        priority = _query_priority(payload)
        payload["query_priority"] = priority
        payload["priority_score"] = priority["score"]
        prioritized.append(payload)
    return sorted(prioritized, key=lambda item: item.get("priority_score", 0), reverse=True)


def _query_priority(query: dict) -> dict:
    movement = query.get("movement", "")
    source_reason = query.get("source_reason", "")
    evidence_count = int(query.get("evidence_count") or len(query.get("origin_row_ids") or []) or 1)
    movement_heat = min(30, evidence_count * 5)
    source_bonus = {
        "identity_resolution_target": 25,
        "needs_more_evidence": 20,
        "theme_signal": 10,
    }.get(source_reason, 0)
    missing_identity = 0
    missing_text = " ".join(query.get("missing_identity_evidence") or []).lower()
    if any(term in missing_text for term in IDENTITY_MISSING_TERMS) or source_reason in {"identity_resolution_target", "needs_more_evidence"}:
        missing_identity = 20
    attio_gap = 15 if query.get("attio_gap") else 0
    prior_yield = int(query.get("prior_yield") or 0)
    generic_penalty = 30 if _is_broad_movement(movement) or (movement or "").lower() in GENERIC_MOVEMENTS else 0
    score = movement_heat + source_bonus + missing_identity + attio_gap + prior_yield - generic_penalty
    return {
        "movement_heat": movement_heat,
        "source_reason": source_bonus,
        "missing_identity_evidence": missing_identity,
        "attio_gap": attio_gap,
        "prior_yield": prior_yield,
        "generic_penalty": generic_penalty,
        "score": score,
    }


def collect_company_discovery(
    theme_signals: list[ThemeSignal],
    *,
    focus_items: list[FocusItem] | None = None,
    unresolved_candidates: list[Candidate] | None = None,
    query_runner: Callable | None,
    grounded_available: bool,
    social_available: bool,
    lookback_days: int = 30,
    max_queries_per_theme: int = 3,
    article_fetcher: Callable | None = None,
    max_article_fetches: int = 8,
    run_budget: DiscoveryRunBudget | None = None,
    partial_output_path: Path | str | None = None,
    query_cache_dir: Path | str | None = None,
) -> dict:
    """Run theme-driven company searches and annotate returned evidence."""
    run_budget = run_budget or DiscoveryRunBudget.for_mode("unbounded")
    ledger = RuntimeLedger(mode=run_budget.mode)
    partial_output_path = Path(partial_output_path) if partial_output_path else None
    query_cache_dir = Path(query_cache_dir) if query_cache_dir else None
    if run_budget.max_article_fetches is not None:
        max_article_fetches = min(max_article_fetches, run_budget.max_article_fetches)
    queries = build_company_discovery_queries(
        theme_signals,
        focus_items=focus_items,
        unresolved_candidates=unresolved_candidates,
        grounded_available=grounded_available,
        social_available=social_available,
        lookback_days=lookback_days,
        max_queries_per_theme=max_queries_per_theme,
    )
    result = {
        "queries": queries,
        "items": [],
        "accepted_leads": [],
        "rejected_leads": [],
        "warnings": [],
        "errors": [],
        "query_diagnostics": [],
        "summary": {
            "queries_run": 0,
            "verification_queries_run": 0,
            "maturity_queries_run": 0,
            "article_fetches_attempted": 0,
            "provider_items_seen": 0,
            "cache_hits": 0,
            "stale_cache_hits": 0,
            "live_calls": 0,
            "partial": False,
            "budget_exceeded": False,
            "source_type_counts": {},
            "accepted": 0,
            "rejected": 0,
            "grounded_available": grounded_available,
        },
    }
    if queries and not grounded_available:
        result["warnings"].append("Grounded company discovery unavailable; company discovery is artifact-only.")
        result["query_diagnostics"] = [
            _query_diagnostic(query, status="not_executed", skip_reason="grounded_company_discovery_unavailable")
            for query in queries
        ]
        for query in queries:
            ledger.record_skip(query, "grounded_company_discovery_unavailable")
        _attach_runtime_metadata(result, ledger, queries)
        _write_partial_discovery_result(partial_output_path, result, ledger, queries)
        return result
    if not query_runner or not queries:
        if queries and not query_runner:
            result["warnings"].append("Theme company discovery skipped because last30days query runner is unavailable.")
            result["query_diagnostics"] = [
                _query_diagnostic(query, status="not_executed", skip_reason="query_runner_unavailable")
                for query in queries
            ]
            for query in queries:
                ledger.record_skip(query, "query_runner_unavailable")
        _attach_runtime_metadata(result, ledger, queries)
        _write_partial_discovery_result(partial_output_path, result, ledger, queries)
        return result

    items = []
    accepted_leads = []
    rejected_leads = []
    maturity_cache: dict[str, dict] = {}
    movement_attempt_counts: dict[str, int] = {}
    for query in queries:
        movement = query.get("movement", "")
        diagnostic = _query_diagnostic(query)
        result["query_diagnostics"].append(diagnostic)
        if _runtime_budget_exceeded(ledger, run_budget):
            ledger.record_skip(query, "max_runtime_seconds_exceeded")
            diagnostic["status"] = "skipped"
            _increment_count(diagnostic["skip_reason_counts"], "max_runtime_seconds_exceeded")
            _write_partial_discovery_result(partial_output_path, result, ledger, queries)
            continue

        cache_payload, cache_status = _read_query_cache(
            query_cache_dir,
            query["topic"],
            ttl_seconds=run_budget.query_cache_ttl_seconds,
            allow_stale=run_budget.allow_stale_cache,
        )
        ledger.record_attempt(query, cache_status=cache_status)
        if cache_payload is not None:
            payload = cache_payload
            ledger.cache_hits += 1
            result["summary"]["cache_hits"] += 1
            if cache_status == "stale":
                ledger.stale_cache_hits += 1
                result["summary"]["stale_cache_hits"] += 1
                warning = f"Using stale cached company discovery result for: {query['topic']}"
                if warning not in result["warnings"]:
                    result["warnings"].append(warning)
                diagnostic["warnings"].append(warning)
            diagnostic["status"] = "processed_cached"
            diagnostic["cache_status"] = cache_status
            ledger.record_complete(query, cache_status=cache_status)
        else:
            if _query_budget_exceeded(result, run_budget):
                ledger.record_skip(query, "company_discovery_query_budget_exceeded")
                diagnostic["status"] = "skipped"
                _increment_count(diagnostic["skip_reason_counts"], "company_discovery_query_budget_exceeded")
                _write_partial_discovery_result(partial_output_path, result, ledger, queries)
                continue
            if (
                run_budget.per_movement_query_cap is not None
                and movement_attempt_counts.get(movement, 0) >= run_budget.per_movement_query_cap
            ):
                ledger.record_skip(query, "per_movement_query_cap_exceeded")
                diagnostic["status"] = "skipped"
                _increment_count(diagnostic["skip_reason_counts"], "per_movement_query_cap_exceeded")
                _write_partial_discovery_result(partial_output_path, result, ledger, queries)
                continue
            movement_attempt_counts[movement] = movement_attempt_counts.get(movement, 0) + 1
            ledger.live_calls += 1
            result["summary"]["live_calls"] += 1
            query_kwargs = {
                "sources": query["sources"],
                "lookback_days": query["lookback_days"],
                "auto_resolve": True,
                "store": True,
                "web_backend": query.get("web_backend"),
            }
            timeout_seconds = ledger.remaining_seconds(run_budget)
            if timeout_seconds is not None:
                query_kwargs["timeout_seconds"] = timeout_seconds
            try:
                payload = query_runner(query["topic"], **query_kwargs)
                _write_query_cache(query_cache_dir, query["topic"], payload)
                result["summary"]["queries_run"] += 1
                ledger.record_complete(query, cache_status="miss")
            except Exception as exc:  # pragma: no cover - defensive boundary around live tools
                error = f"{query['kind']}: {exc}"
                result["errors"].append(error)
                diagnostic["status"] = "error"
                diagnostic["errors"].append(error)
                _increment_count(diagnostic["skip_reason_counts"], "query_runner_exception")
                _write_partial_discovery_result(partial_output_path, result, ledger, queries)
                continue

        if diagnostic["status"] == "pending":
            diagnostic["status"] = "processed"
        diagnostic["payload_keys"] = sorted(payload.keys())
        for warning in payload.get("warnings", []):
            if warning not in result["warnings"]:
                result["warnings"].append(warning)
            if warning not in diagnostic["warnings"]:
                diagnostic["warnings"].append(warning)
        if payload.get("error"):
            result["errors"].append(payload["error"])
            diagnostic["errors"].append(payload["error"])
        for source_name, source_error in (payload.get("errors_by_source") or {}).items():
            error = f"{source_name}: {source_error}"
            if error not in result["errors"]:
                result["errors"].append(error)
            if error not in diagnostic["errors"]:
                diagnostic["errors"].append(error)
            diagnostic["source_errors"][source_name] = source_error

        payload_items = payload.get("items", [])
        if run_budget.max_results_per_query is not None:
            payload_items = payload_items[: run_budget.max_results_per_query]
        diagnostic["provider_item_count"] = len(payload_items)
        result["summary"]["provider_items_seen"] += len(payload_items)
        if not payload_items:
            diagnostic["status"] = "no_items"
            _increment_count(diagnostic["skip_reason_counts"], "provider_returned_no_items")
            _write_partial_discovery_result(partial_output_path, result, ledger, queries)
            continue

        for item in payload_items:
            _record_query_result_preview(diagnostic, item)
            source_type = classify_discovery_source(item)
            _increment_count(diagnostic["source_type_counts"], source_type)
            _increment_count(result["summary"]["source_type_counts"], source_type)
            enriched = dict(item)
            enriched.setdefault("query_kind", query["kind"])
            enriched.setdefault("query_topic", query["topic"])
            enriched.setdefault("query_theme", query["theme"])
            enriched.setdefault("market_sector", query["market_sector"])
            enriched.setdefault("candidate_eligible", True)
            enriched.setdefault("discovery_lane", "controlled_company_discovery")
            lead = verify_discovery_item(enriched, query)
            if lead.verification_status == "accepted":
                lead = _maybe_verify_lead_maturity(
                    lead,
                    query,
                    query_runner,
                    maturity_cache,
                    result,
                    diagnostic,
                    run_budget,
                    ledger,
                )
                accepted_leads.append(lead.to_dict())
                items.append(_lead_to_item(lead))
                diagnostic["accepted_count"] += 1
            else:
                can_fetch_article = result["summary"]["article_fetches_attempted"] < max_article_fetches
                article_lead, article_warnings, article_errors, verification_queries = _verify_publisher_article_company(
                    enriched,
                    query,
                    query_runner,
                    article_fetcher=article_fetcher,
                    allow_article_fetch=can_fetch_article,
                )
                result["summary"]["verification_queries_run"] += verification_queries
                diagnostic["verification_queries_run"] += verification_queries
                if article_warnings and any(warning.startswith("article-detail: fetched") for warning in article_warnings):
                    result["summary"]["article_fetches_attempted"] += 1
                    diagnostic["article_fetches_attempted"] += 1
                for warning in article_warnings:
                    if warning not in diagnostic["warnings"]:
                        diagnostic["warnings"].append(warning)
                    if not warning.startswith("article-detail: fetched") and warning not in result["warnings"]:
                        result["warnings"].append(warning)
                result["errors"].extend(article_errors)
                diagnostic["errors"].extend(article_errors)
                if article_lead:
                    if article_lead.verification_status == "accepted":
                        article_lead = _maybe_verify_lead_maturity(
                            article_lead,
                            query,
                            query_runner,
                            maturity_cache,
                            result,
                            diagnostic,
                            run_budget,
                            ledger,
                        )
                        accepted_leads.append(article_lead.to_dict())
                        items.append(_lead_to_item(article_lead))
                        diagnostic["accepted_count"] += 1
                    else:
                        rejected_leads.append(article_lead.to_dict())
                        diagnostic["rejected_count"] += 1
                        for reason in article_lead.missing_evidence:
                            _increment_count(diagnostic["skip_reason_counts"], reason)
                else:
                    rejected_leads.append(lead.to_dict())
                    diagnostic["rejected_count"] += 1
                    for reason in lead.missing_evidence:
                        _increment_count(diagnostic["skip_reason_counts"], reason)
        _write_partial_discovery_result(partial_output_path, result, ledger, queries)

    result["items"] = _dedupe_items(items)
    result["accepted_leads"] = _dedupe_leads(accepted_leads)
    result["rejected_leads"] = _dedupe_leads(rejected_leads)
    result["summary"]["accepted"] = len(result["accepted_leads"])
    result["summary"]["rejected"] = len(result["rejected_leads"])
    _attach_runtime_metadata(result, ledger, queries)
    _write_partial_discovery_result(partial_output_path, result, ledger, queries)
    return result


def verify_discovery_item(item: dict, query: dict) -> VerifiedCompanyDiscoveryLead:
    source_url = item.get("url") or item.get("source_url") or ""
    source = (item.get("source") or "").lower()
    title = item.get("title") or ""
    snippet = item.get("snippet") or item.get("description") or ""
    name = item.get("company_name") or item.get("name") or title
    domain = _normalize_domain(item.get("domain") or item.get("website") or _domain_from_url(source_url))
    required_terms = query.get("required_terms") or _movement_terms(query.get("movement", ""))
    source_type = classify_discovery_source(item)

    basis = []
    missing = []
    movement_basis = []
    combined_text = f"{title} {snippet} {name} {domain}".lower()

    if not source_url:
        missing.append("no_source_url")
    if not name:
        missing.append("no_company_name")
    if source == "github" or "github.com" in source_url:
        missing.append("github_only_not_company_proof")
    domain_ok, domain_basis, domain_missing = _company_domain_evidence(item, domain, source_url, source)
    basis.extend(domain_basis)
    missing.extend(domain_missing)

    movement_ok, movement_reasons = _movement_match_strength(combined_text, required_terms)
    if movement_ok:
        movement_basis.extend(movement_reasons)
    else:
        missing.extend(movement_reasons)

    accepted = bool(source_url and name and domain_ok and movement_basis and "github_only_not_company_proof" not in missing)
    return VerifiedCompanyDiscoveryLead(
        name=name,
        movement=query.get("movement", ""),
        market_sector=query.get("market_sector", ""),
        source_url=source_url,
        source=item.get("source", ""),
        domain=domain if accepted else "",
        founder_or_maintainer=item.get("founder") or item.get("author") or "",
        candidate_type="verified_company" if accepted and domain else "launch_style_needs_identity",
        verification_status="accepted" if accepted else "rejected",
        verification_basis=basis,
        missing_evidence=list(dict.fromkeys(missing)),
        movement_assignment_basis=movement_basis,
        source_type=source_type,
        query_id=query.get("id", ""),
        query_topic=query.get("topic", ""),
        why_on_radar=snippet or title,
        why_this_may_be_noise="Needs verification across stronger company/founder/customer evidence.",
        raw_title=title,
        raw_snippet=snippet,
    )


def _lead_to_item(lead: VerifiedCompanyDiscoveryLead) -> dict:
    return {
        "source": lead.source or "grounding",
        "title": lead.raw_title or lead.name,
        "url": lead.source_url,
        "snippet": lead.why_on_radar,
        "company_name": lead.name,
        "domain": lead.domain,
        "market_sector": lead.market_sector,
        "query_theme": lead.movement,
        "query_topic": lead.query_topic,
        "query_id": lead.query_id,
        "query_kind": _query_kind_from_id(lead.query_id),
        "candidate_eligible": True,
        "signal_role": "launch",
        "source_lane": "Grounded web",
        "discovery_lane": "controlled_company_discovery",
        "discovery_verification_status": "accepted",
        "discovery_verification_basis": lead.verification_basis,
        "movement_assignment_basis": lead.movement_assignment_basis,
        "why_this_may_be_noise": lead.why_this_may_be_noise,
        "source_type": lead.source_type,
        "extracted_company_name": lead.extracted_company_name,
        "extraction_confidence": lead.extraction_confidence,
        "supporting_evidence_urls": lead.supporting_evidence_urls,
        "official_domain_verification_url": lead.official_domain_verification_url,
        "likely_too_late": lead.likely_too_late,
        "maturity_status": lead.maturity_status,
        "maturity_basis": lead.maturity_basis,
        "maturity_evidence_urls": lead.maturity_evidence_urls,
        "category_anchor": lead.category_anchor,
        "consensus_risk_reason": lead.consensus_risk_reason,
        "lead_route": lead.lead_route,
        "action": "monitor only" if lead.lead_route in {"category_context", "monitor_only"} else "",
    }


def _maybe_verify_lead_maturity(
    lead: VerifiedCompanyDiscoveryLead,
    query: dict,
    query_runner: Callable,
    maturity_cache: dict[str, dict],
    result: dict,
    diagnostic: dict,
    run_budget: DiscoveryRunBudget,
    ledger: RuntimeLedger,
) -> VerifiedCompanyDiscoveryLead:
    if run_budget.max_maturity_queries is not None and result["summary"]["maturity_queries_run"] >= run_budget.max_maturity_queries:
        ledger.record_skip(query, "maturity_query_budget_exceeded")
        _increment_count(diagnostic["skip_reason_counts"], "maturity_query_budget_exceeded")
        return lead
    if _runtime_budget_exceeded(ledger, run_budget):
        ledger.record_skip(query, "max_runtime_seconds_exceeded")
        _increment_count(diagnostic["skip_reason_counts"], "max_runtime_seconds_exceeded")
        return lead

    lead, maturity_warnings, maturity_errors, maturity_queries = _verify_lead_maturity(
        lead,
        query,
        query_runner,
        maturity_cache,
        timeout_seconds=ledger.remaining_seconds(run_budget),
    )
    result["summary"]["maturity_queries_run"] += maturity_queries
    diagnostic["maturity_queries_run"] += maturity_queries
    if maturity_queries:
        ledger.live_calls += maturity_queries
        result["summary"]["live_calls"] += maturity_queries
    for warning in maturity_warnings:
        if warning not in diagnostic["warnings"]:
            diagnostic["warnings"].append(warning)
        if warning not in result["warnings"]:
            result["warnings"].append(warning)
    result["errors"].extend(maturity_errors)
    diagnostic["errors"].extend(maturity_errors)
    return lead


def _runtime_budget_exceeded(ledger: RuntimeLedger, budget: DiscoveryRunBudget) -> bool:
    return budget.max_runtime_seconds is not None and ledger.elapsed() >= budget.max_runtime_seconds


def _query_budget_exceeded(result: dict, budget: DiscoveryRunBudget) -> bool:
    return (
        budget.max_company_discovery_queries is not None
        and result.get("summary", {}).get("queries_run", 0) >= budget.max_company_discovery_queries
    )


def _attach_runtime_metadata(result: dict, ledger: RuntimeLedger, queries: list[dict]) -> None:
    result["runtime_ledger"] = ledger.to_dict()
    result["coverage_report"] = _coverage_report(queries, ledger)
    result["summary"]["partial"] = bool(ledger.partial)
    result["summary"]["budget_exceeded"] = bool(ledger.budget_exceeded)
    result["summary"]["cache_hits"] = ledger.cache_hits
    result["summary"]["stale_cache_hits"] = ledger.stale_cache_hits
    result["summary"]["live_calls"] = ledger.live_calls


def _write_partial_discovery_result(path: Path | None, result: dict, ledger: RuntimeLedger, queries: list[dict]) -> None:
    if not path:
        return
    _attach_runtime_metadata(result, ledger, queries)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))


def _coverage_report(queries: list[dict], ledger: RuntimeLedger) -> dict:
    movement_rows: dict[str, dict] = {}
    for query in queries:
        movement = query.get("movement", "") or "unknown"
        row = movement_rows.setdefault(
            movement,
            {
                "movement": movement,
                "total_queries": 0,
                "completed_queries": 0,
                "skipped_queries": 0,
                "status": "skipped",
            },
        )
        row["total_queries"] += 1
    for event in ledger.query_events:
        movement = event.get("movement", "") or "unknown"
        row = movement_rows.setdefault(
            movement,
            {
                "movement": movement,
                "total_queries": 0,
                "completed_queries": 0,
                "skipped_queries": 0,
                "status": "skipped",
            },
        )
        if event.get("status") == "completed":
            row["completed_queries"] += 1
        elif event.get("status") == "skipped":
            row["skipped_queries"] += 1
    for row in movement_rows.values():
        if row["completed_queries"] >= row["total_queries"] and row["total_queries"]:
            row["status"] = "full"
        elif row["completed_queries"]:
            row["status"] = "partial"
        else:
            row["status"] = "skipped"
    rows = list(movement_rows.values())
    return {
        "movements": rows,
        "recommended_deep_dive": [
            row["movement"]
            for row in rows
            if row["status"] in {"partial", "skipped"} and row["total_queries"]
        ],
    }


def _query_cache_path(cache_dir: Path | str, topic: str) -> Path:
    digest = hashlib.sha256((topic or "").encode("utf-8")).hexdigest()[:20]
    return Path(cache_dir) / f"{digest}.json"


def _read_query_cache(
    cache_dir: Path | None,
    topic: str,
    *,
    ttl_seconds: int,
    allow_stale: bool,
) -> tuple[dict | None, str]:
    if not cache_dir:
        return None, "disabled"
    path = _query_cache_path(cache_dir, topic)
    if not path.exists():
        return None, "miss"
    age_seconds = max(0, time.time() - path.stat().st_mtime)
    if age_seconds > ttl_seconds and not allow_stale:
        return None, "expired"
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None, "corrupt"
    return payload, "stale" if age_seconds > ttl_seconds else "fresh"


def _write_query_cache(cache_dir: Path | None, topic: str, payload: dict) -> None:
    if not cache_dir:
        return
    path = _query_cache_path(cache_dir, topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def classify_discovery_source(item: dict) -> str:
    source_url = item.get("url") or item.get("source_url") or ""
    source = (item.get("source") or "").lower()
    domain = _domain_from_url(source_url) or _normalize_domain(item.get("domain") or item.get("website") or "")
    if source == "github" or domain == "github.com" or domain.endswith(".github.com"):
        return "github_repo"
    if _is_content_platform_domain(domain):
        return "content_platform"
    if _is_directory_domain(domain):
        return "directory_page"
    if _is_publisher_domain(domain) or (_looks_like_publisher_domain(domain) and not _is_homepage_like(source_url)):
        return "publisher_article"
    if domain and _is_homepage_like(source_url):
        return "official_company_page"
    return "unknown"


class _PublisherArticleParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.description = ""
        self.metadata_texts: list[str] = []
        self.structured_texts: list[str] = []
        self.paragraphs: list[str] = []
        self.outbound_links: list[dict] = []
        self._tag = ""
        self._buffer: list[str] = []
        self._script_type = ""
        self._href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._tag = "title"
            self._buffer = []
        elif tag == "p":
            self._tag = "p"
            self._buffer = []
        elif tag == "script" and "ld+json" in attr.get("type", "").lower():
            self._tag = "script"
            self._script_type = attr.get("type", "")
            self._buffer = []
        elif tag == "a" and attr.get("href"):
            self._tag = "a"
            self._href = attr["href"]
            self._buffer = []
        elif tag == "meta":
            key = (attr.get("name") or attr.get("property") or "").lower()
            content = _clean_text(attr.get("content", ""))
            if key in {"description", "og:description", "twitter:description"} and content:
                if not self.description:
                    self.description = content[:ARTICLE_MAX_TEXT_CHARS]
                self.metadata_texts.append(content[:ARTICLE_MAX_TEXT_CHARS])
            elif key in {"og:title", "twitter:title"} and content:
                if not self.title:
                    self.title = content[:ARTICLE_MAX_TEXT_CHARS]
                self.metadata_texts.append(content[:ARTICLE_MAX_TEXT_CHARS])

    def handle_data(self, data: str) -> None:
        if self._tag in {"title", "p", "script", "a"}:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._tag:
            return
        text = _clean_text(" ".join(self._buffer))
        if tag == "title" and text:
            self.title = text[:ARTICLE_MAX_TEXT_CHARS]
        elif tag == "p" and _useful_article_paragraph(text) and len(self.paragraphs) < ARTICLE_MAX_PARAGRAPHS:
            self.paragraphs.append(text[:ARTICLE_MAX_TEXT_CHARS])
        elif tag == "script" and self._script_type:
            self.structured_texts.extend(_jsonld_texts(text))
        elif tag == "a" and self._href and text and len(self.outbound_links) < ARTICLE_MAX_LINKS:
            self.outbound_links.append({"url": urljoin(self.base_url, self._href), "text": text[:200]})
        self._tag = ""
        self._script_type = ""
        self._href = ""
        self._buffer = []


def parse_publisher_article_detail(html: str, source_url: str) -> dict:
    """Parse compact identity-useful metadata from a publisher page without storing full article body."""
    parser = _PublisherArticleParser(source_url)
    parser.feed(html or "")
    return {
        "title": parser.title,
        "description": parser.description,
        "metadata_texts": _dedupe_texts(parser.metadata_texts),
        "structured_texts": _dedupe_texts(parser.structured_texts),
        "paragraphs": parser.paragraphs,
        "outbound_links": parser.outbound_links,
    }


def fetch_publisher_article_detail(url: str, article_fetcher: Callable | None = None) -> tuple[dict | None, str]:
    """Fetch a publisher URL with byte/time caps, then return compact parsed metadata only."""
    if not url:
        return None, "article_fetch_missing_url"
    try:
        raw = article_fetcher(url) if article_fetcher else _default_article_fetcher(url)
    except Exception as exc:
        return None, f"article_fetch_failed:{type(exc).__name__}"
    if isinstance(raw, dict):
        return raw, ""
    if isinstance(raw, bytes):
        raw = raw[:ARTICLE_FETCH_MAX_BYTES].decode("utf-8", errors="ignore")
    elif not isinstance(raw, str):
        return None, "article_fetch_invalid_payload"
    detail = parse_publisher_article_detail(raw[:ARTICLE_FETCH_MAX_BYTES], url)
    if not any(detail.get(key) for key in ("title", "description", "structured_texts", "paragraphs", "outbound_links")):
        return None, "article_fetch_no_useful_detail"
    return detail, ""


def extract_company_from_publisher_article(item: dict) -> dict | None:
    title = _without_publisher_suffix(item.get("title") or "")
    snippet = item.get("snippet") or item.get("description") or ""
    detail = item.get("article_detail") or {}
    detail_texts = [
        detail.get("title", ""),
        detail.get("description", ""),
        *(detail.get("metadata_texts") or []),
        *(detail.get("structured_texts") or []),
        *(detail.get("paragraphs") or []),
    ]
    patterns = [
        (r"\b(?:acquires|acquire|buys|purchases)\s+([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,3})\b", "acquisition_pattern", "High"),
        (r"^([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,4})\s+(?:raises|raised|secures|secured|lands|landed|closes|closed)\b", "raises_pattern", "High"),
        (r"^([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,4})\s+(?:launches|unveils|introduces|debuts)\b", "launch_pattern", "High"),
        (r"^([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,4})\s+emerges\s+from\s+stealth\b", "stealth_pattern", "High"),
        (r"\b([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,4}),\s+a\s+(?:startup|company)\b", "startup_apposition_pattern", "Medium"),
    ]
    for text in (title, snippet, *detail_texts):
        for pattern, basis, confidence in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            name = _clean_company_name(match.group(1))
            if _valid_extracted_company_name(name):
                return {
                    "company_name": name,
                    "confidence": confidence,
                    "basis": [basis],
                    "likely_too_late": _is_likely_too_late_text(f"{title} {snippet} {' '.join(detail_texts)}") or basis == "acquisition_pattern",
                }
    return None


def _verify_publisher_article_company(
    item: dict,
    query: dict,
    query_runner: Callable,
    *,
    article_fetcher: Callable | None = None,
    allow_article_fetch: bool = True,
) -> tuple[VerifiedCompanyDiscoveryLead | None, list[str], list[str], int]:
    if classify_discovery_source(item) != "publisher_article":
        return None, [], [], 0
    extracted = extract_company_from_publisher_article(item)
    warnings: list[str] = []
    if not extracted and allow_article_fetch:
        article_detail, detail_error = fetch_publisher_article_detail(item.get("url") or item.get("source_url") or "", article_fetcher)
        warnings.append("article-detail: fetched")
        if detail_error:
            warnings.append(f"article-detail: {detail_error}")
        elif article_detail:
            item = {**item, "article_detail": article_detail}
            extracted = extract_company_from_publisher_article(item)
    if not extracted:
        return None, warnings, [], 0

    errors: list[str] = []
    verification_topic = _official_domain_query(extracted["company_name"], query.get("movement", ""))
    try:
        payload = query_runner(
            verification_topic,
            sources=query.get("sources") or "grounding",
            lookback_days=query.get("lookback_days", 30),
            auto_resolve=True,
            store=True,
            web_backend=query.get("web_backend") or "auto",
        )
    except Exception as exc:  # pragma: no cover - defensive live-provider boundary
        rejected = _publisher_article_rejection(item, query, extracted, ["official_domain_verification_failed"])
        return rejected, warnings, [f"article-domain-verification: {exc}"], 1

    warnings.extend(payload.get("warnings", []))
    if payload.get("error"):
        errors.append(payload["error"])

    for official_item in payload.get("items", []):
        verified = _verify_official_domain_for_extracted_company(official_item, item, query, extracted)
        if verified:
            return verified, warnings, errors, 1

    rejected = _publisher_article_rejection(item, query, extracted, ["official_company_domain_not_verified"])
    return rejected, warnings, errors, 1


def _verify_official_domain_for_extracted_company(
    official_item: dict,
    article_item: dict,
    query: dict,
    extracted: dict,
) -> VerifiedCompanyDiscoveryLead | None:
    company_name = extracted["company_name"]
    source_url = official_item.get("url") or official_item.get("source_url") or ""
    domain = _normalize_domain(official_item.get("domain") or official_item.get("website") or _domain_from_url(source_url))
    if not source_url or not domain:
        return None
    if classify_discovery_source(official_item) in {"publisher_article", "directory_page", "github_repo", "content_platform"}:
        return None
    if _is_publisher_domain(domain) or _is_directory_domain(domain) or _is_content_platform_domain(domain):
        return None
    title = official_item.get("title") or ""
    snippet = official_item.get("snippet") or official_item.get("description") or ""
    if not (_domain_matches_name(domain, company_name) or _text_mentions_company(f"{title} {snippet}", company_name)):
        return None

    required_terms = query.get("required_terms") or _movement_terms(query.get("movement", ""))
    article_text = _article_evidence_text(article_item)
    movement_ok, movement_basis = _movement_match_strength(f"{title} {snippet} {article_text}", required_terms)
    if not movement_ok:
        return None

    article_url = article_item.get("url") or article_item.get("source_url") or ""
    too_late = bool(extracted.get("likely_too_late")) or _is_likely_too_late_text(f"{title} {snippet} {article_text}")
    return VerifiedCompanyDiscoveryLead(
        name=company_name,
        movement=query.get("movement", ""),
        market_sector=query.get("market_sector", ""),
        source_url=source_url,
        source=official_item.get("source", "grounding"),
        domain=domain,
        candidate_type="verified_company",
        verification_status="accepted",
        verification_basis=["publisher_article_company_extracted", "official_domain_verified", *extracted.get("basis", [])],
        movement_assignment_basis=movement_basis,
        source_type="publisher_article",
        extracted_company_name=company_name,
        extraction_confidence=extracted.get("confidence", ""),
        supporting_evidence_urls=[article_url] if article_url else [],
        official_domain_verification_url=source_url,
        likely_too_late=too_late,
        query_id=query.get("id", ""),
        query_topic=query.get("topic", ""),
        why_on_radar=article_item.get("snippet") or article_item.get("title") or title,
        why_this_may_be_noise=(
            "Likely too late: article suggests acquisition, late-stage funding, or consensus attention; monitor only."
            if too_late
            else "Article-derived lead; verify founder, stage, customer pull, and Attio context."
        ),
        raw_title=title,
        raw_snippet=snippet,
    )


def _publisher_article_rejection(
    item: dict,
    query: dict,
    extracted: dict,
    missing_evidence: list[str],
) -> VerifiedCompanyDiscoveryLead:
    article_url = item.get("url") or item.get("source_url") or ""
    title = item.get("title") or ""
    snippet = item.get("snippet") or item.get("description") or ""
    return VerifiedCompanyDiscoveryLead(
        name=extracted["company_name"],
        movement=query.get("movement", ""),
        market_sector=query.get("market_sector", ""),
        source_url=article_url,
        source=item.get("source", ""),
        candidate_type="launch_style_needs_identity",
        verification_status="rejected",
        verification_basis=["publisher_article_company_extracted", *extracted.get("basis", [])],
        missing_evidence=missing_evidence,
        source_type="publisher_article",
        extracted_company_name=extracted["company_name"],
        extraction_confidence=extracted.get("confidence", ""),
        supporting_evidence_urls=[article_url] if article_url else [],
        likely_too_late=bool(extracted.get("likely_too_late")),
        query_id=query.get("id", ""),
        query_topic=query.get("topic", ""),
        why_on_radar=snippet or title,
        why_this_may_be_noise="Publisher article mentioned a company, but official company domain was not verified.",
        raw_title=title,
        raw_snippet=snippet,
    )


def _verify_lead_maturity(
    lead: VerifiedCompanyDiscoveryLead,
    query: dict,
    query_runner: Callable,
    maturity_cache: dict[str, dict] | None = None,
    timeout_seconds: int | None = None,
) -> tuple[VerifiedCompanyDiscoveryLead, list[str], list[str], int]:
    """Run one exact-name maturity lookup for accepted company leads."""
    lookup_name = _maturity_lookup_name(lead)
    topic = _maturity_query(lookup_name)
    cache_key = lookup_name.strip().lower()
    if maturity_cache is not None and cache_key in maturity_cache:
        return _apply_maturity_to_lead(lead, maturity_cache[cache_key]), [], [], 0
    warnings: list[str] = []
    errors: list[str] = []
    try:
        payload = query_runner(
            topic,
            sources=query.get("sources") or "grounding",
            lookback_days=query.get("lookback_days", 30),
            auto_resolve=True,
            store=True,
            web_backend=query.get("web_backend") or "auto",
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - defensive live-provider boundary
        maturity = _unknown_maturity()
        if maturity_cache is not None:
            maturity_cache[cache_key] = maturity
        return _apply_maturity_to_lead(lead, maturity), warnings, [f"maturity-verification: {exc}"], 1

    warnings.extend(payload.get("warnings", []))
    if payload.get("error"):
        errors.append(payload["error"])
    for source_name, source_error in (payload.get("errors_by_source") or {}).items():
        errors.append(f"maturity-{source_name}: {source_error}")

    maturity = _classify_maturity_from_items(payload.get("items", []), fallback_likely_too_late=lead.likely_too_late)
    if maturity_cache is not None:
        maturity_cache[cache_key] = maturity
    return _apply_maturity_to_lead(lead, maturity), warnings, errors, 1


def _maturity_query(company_name: str) -> str:
    return f'"{company_name}" funding valuation acquisition Series C'


def _maturity_lookup_name(lead: VerifiedCompanyDiscoveryLead) -> str:
    """Return the most company-like exact name for maturity verification."""
    for candidate in (lead.extracted_company_name, lead.name):
        cleaned = _clean_maturity_name(candidate or "")
        if cleaned:
            return cleaned
    if lead.domain:
        return lead.domain.split(".")[0]
    return lead.name


def _clean_maturity_name(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    for separator in (" | ", " - ", " – ", " — ", ": "):
        if separator in cleaned:
            parts = [_clean_text(part) for part in cleaned.split(separator) if _clean_text(part)]
            for part in parts:
                lowered = part.lower()
                if lowered in {"home", "homepage", "official site", "website"}:
                    continue
                if len(part) >= 2:
                    return part
    cleaned = re.sub(r"^(home|homepage)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned[:80]


def _unknown_maturity() -> dict:
    return {
        "maturity_status": "unknown",
        "maturity_basis": ["maturity_not_verified"],
        "maturity_evidence_urls": [],
        "category_anchor": False,
        "consensus_risk_reason": "",
        "lead_route": "research_deeper",
        "likely_too_late": False,
    }


def _classify_maturity_from_items(items: list[dict], *, fallback_likely_too_late: bool = False) -> dict:
    evidence_urls: list[str] = []
    basis: list[str] = []
    combined_parts: list[str] = []
    for item in items or []:
        title = item.get("title") or ""
        snippet = item.get("snippet") or item.get("description") or ""
        url = item.get("url") or item.get("source_url") or ""
        if url:
            evidence_urls.append(url)
        combined_parts.append(f"{title} {snippet}")
    text = " ".join(combined_parts).lower()

    if fallback_likely_too_late:
        basis.append("article_likely_too_late")
    if re.search(r"\b(acquires|acquired|acquisition|buys|bought|purchases|purchased)\b", text):
        basis.append("acquisition_or_incumbent_ownership")
    if re.search(r"\bseries\s+[cdefg]\b", text):
        basis.append("series_c_or_later")
    if _has_large_money_signal(text):
        basis.append("large_round_or_valuation")
    if re.search(r"\b(unicorn|category leader|market leader|default platform|incumbent)\b", text):
        basis.append("category_leader_language")
    if any(item in basis for item in ("acquisition_or_incumbent_ownership", "series_c_or_later", "large_round_or_valuation", "category_leader_language", "article_likely_too_late")):
        status = "acquired" if "acquisition_or_incumbent_ownership" in basis else "likely_too_late"
        return {
            "maturity_status": status,
            "maturity_basis": list(dict.fromkeys(basis)),
            "maturity_evidence_urls": list(dict.fromkeys(evidence_urls)),
            "category_anchor": True,
            "consensus_risk_reason": "Late-stage, acquired, high-valuation, or consensus/category-leader evidence.",
            "lead_route": "monitor_only" if status == "acquired" else "category_context",
            "likely_too_late": True,
        }

    early_basis = []
    if re.search(r"\b(pre[- ]?seed|seed)\b", text):
        early_basis.append("seed_or_pre_seed")
    if re.search(r"\bseries\s+[ab]\b", text):
        early_basis.append("series_a_or_b")
    if early_basis:
        return {
            "maturity_status": "seed_to_series_b",
            "maturity_basis": early_basis,
            "maturity_evidence_urls": list(dict.fromkeys(evidence_urls)),
            "category_anchor": False,
            "consensus_risk_reason": "",
            "lead_route": "sourcing_candidate",
            "likely_too_late": False,
        }

    return _unknown_maturity()


def _has_large_money_signal(text: str) -> bool:
    for raw_amount, unit in re.findall(r"\$\s?([0-9]+(?:\.[0-9]+)?)\s?(m|million|b|billion)\b", text):
        amount = float(raw_amount)
        normalized = amount * 1000 if unit.startswith("b") else amount
        if normalized >= 100:
            return True
    return bool(re.search(r"\$[0-9]+(?:\.[0-9]+)?\s?(?:b|billion)\s+valuation", text))


def _apply_maturity_to_lead(lead: VerifiedCompanyDiscoveryLead, maturity: dict) -> VerifiedCompanyDiscoveryLead:
    out = VerifiedCompanyDiscoveryLead.from_dict(lead.to_dict())
    out.maturity_status = maturity.get("maturity_status", "unknown")
    out.maturity_basis = list(maturity.get("maturity_basis") or [])
    out.maturity_evidence_urls = list(maturity.get("maturity_evidence_urls") or [])
    out.category_anchor = bool(maturity.get("category_anchor"))
    out.consensus_risk_reason = maturity.get("consensus_risk_reason", "")
    out.lead_route = maturity.get("lead_route", "research_deeper")
    out.likely_too_late = bool(out.likely_too_late or maturity.get("likely_too_late"))
    if out.lead_route in {"category_context", "monitor_only"}:
        out.why_this_may_be_noise = (
            out.consensus_risk_reason
            or "Mature/consensus company; useful as category context, not an owner-ready sourcing lead."
        )
    return out


def _default_article_fetcher(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "vc-signals/1.0"})
    with urlopen(request, timeout=ARTICLE_FETCH_TIMEOUT_SECONDS) as response:  # nosec B310
        return response.read(ARTICLE_FETCH_MAX_BYTES)


def _clean_text(text: str) -> str:
    cleaned = html_lib.unescape(text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _dedupe_texts(texts: list[str]) -> list[str]:
    seen = set()
    out = []
    for text in texts:
        cleaned = _clean_text(text)[:ARTICLE_MAX_TEXT_CHARS]
        key = cleaned.lower()
        if cleaned and key not in seen:
            out.append(cleaned)
            seen.add(key)
    return out


def _useful_article_paragraph(text: str) -> bool:
    cleaned = _clean_text(text)
    if len(cleaned) < ARTICLE_MIN_PARAGRAPH_CHARS:
        return False
    lowered = cleaned.lower()
    return not any(term in lowered for term in ("advertisement", "subscribe", "sign up", "cookie", "read more"))


def _jsonld_texts(raw: str) -> list[str]:
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    texts: list[str] = []

    def visit(value, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, child_key)
        elif isinstance(value, list):
            for child in value:
                visit(child, key)
        elif isinstance(value, str) and key in {"headline", "name", "description", "about", "mentions"}:
            texts.append(value[:ARTICLE_MAX_TEXT_CHARS])

    visit(payload)
    return _dedupe_texts(texts)


def _article_evidence_text(item: dict) -> str:
    detail = item.get("article_detail") or {}
    parts = [
        item.get("title") or "",
        item.get("snippet") or item.get("description") or "",
        detail.get("title", ""),
        detail.get("description", ""),
        *(detail.get("metadata_texts") or []),
        *(detail.get("structured_texts") or []),
        *(detail.get("paragraphs") or []),
    ]
    return " ".join(str(part) for part in parts if part)


def _sources(*, grounded_available: bool, social_available: bool) -> str:
    return "grounding" if grounded_available else ""


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        raw = urlparse(raw).netloc
    raw = raw.lower().strip("/")
    return raw[4:] if raw.startswith("www.") else raw


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    return _normalize_domain(parsed.netloc)


def _is_content_platform_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in CONTENT_PLATFORM_DOMAINS)


def _is_publisher_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in PUBLISHER_DOMAINS)


def _is_directory_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in DIRECTORY_DOMAINS)


def _company_domain_evidence(item: dict, domain: str, source_url: str, source: str) -> tuple[bool, list[str], list[str]]:
    """Decide whether a grounded result domain is company evidence, not just the article publisher."""
    basis: list[str] = []
    missing: list[str] = []
    normalized = _normalize_domain(domain)
    source_domain = _domain_from_url(source_url)
    source_type = classify_discovery_source(item)
    if not normalized:
        return False, basis, ["no_source_backed_domain"]
    if _is_content_platform_domain(normalized):
        return False, basis, ["content_platform_not_company_domain", "no_source_backed_domain"]
    if source_type == "publisher_article":
        return False, basis, ["source_domain_not_company_proof", "no_source_backed_domain"]
    if source_type == "directory_page":
        return False, basis, ["directory_page_not_company_domain", "no_source_backed_domain"]
    if source == "github" or "github.com" in (source_url or ""):
        return False, basis, ["github_only_not_company_proof", "no_source_backed_domain"]
    if _looks_academic_or_government_domain(normalized):
        return False, basis, ["academic_or_government_domain_not_company_proof", "no_source_backed_domain"]

    declared_name = (item.get("company_name") or item.get("name") or "").strip()
    title = (item.get("title") or "").strip()
    homepage_like = _is_homepage_like(source_url)
    if homepage_like and source_domain == normalized and not _looks_like_publisher_domain(normalized):
        return True, ["official_homepage_domain"], missing

    if declared_name and declared_name != title and _domain_matches_name(normalized, declared_name):
        return True, ["declared_company_name_matches_domain"], missing

    if item.get("domain") and source_domain == normalized and _domain_matches_name(normalized, declared_name or title):
        return True, ["source_backed_domain"], missing

    return False, basis, ["source_domain_not_company_proof", "no_source_backed_domain"]


def _is_homepage_like(url: str) -> bool:
    parsed = urlparse(url or "")
    path = (parsed.path or "").strip("/")
    return not path


def _looks_academic_or_government_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return normalized.endswith(".edu") or ".edu." in normalized or normalized.endswith(".gov") or ".gov." in normalized


def _looks_like_publisher_domain(domain: str) -> bool:
    first_label = _normalize_domain(domain).split(".", 1)[0]
    return any(hint in first_label for hint in PUBLISHER_DOMAIN_HINTS)


def _domain_matches_name(domain: str, name: str) -> bool:
    base = _normalize_domain(domain).split(".", 1)[0]
    name_slug = "".join(char.lower() for char in (name or "") if char.isalnum())
    base_slug = "".join(char.lower() for char in base if char.isalnum())
    return bool(base_slug and name_slug and (base_slug in name_slug or name_slug in base_slug))


def _text_mentions_company(text: str, name: str) -> bool:
    normalized_text = " ".join((text or "").lower().split())
    normalized_name = " ".join((name or "").lower().split())
    return bool(normalized_name and normalized_name in normalized_text)


def _without_publisher_suffix(title: str) -> str:
    cleaned = (title or "").strip()
    for separator in (" | ", " - "):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0].strip()
    return cleaned


def _clean_company_name(name: str) -> str:
    cleaned = (name or "").strip(" \t\n\r-:|,.'\"")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _valid_extracted_company_name(name: str) -> bool:
    normalized = (name or "").strip().lower()
    if not normalized or normalized in GENERIC_EXTRACTED_NAMES or normalized in BROAD_THEMES:
        return False
    if normalized in {"the", "new", "top", "how", "what", "why", "us", "ai startups"}:
        return False
    return len(normalized) > 2 and any(char.isalpha() for char in normalized)


def _is_likely_too_late_text(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in TOO_LATE_TERMS)


def _official_domain_query(company_name: str, movement: str) -> str:
    return f'"{company_name}" "{movement}" official'


def _append_query(
    queries: list[dict],
    seen_topics: set[str],
    *,
    kind: str,
    topic: str,
    movement: str,
    market_sector: str,
    source_reason: str,
    origin_row_ids: list[str],
    required_terms: list[str],
    grounded_available: bool,
    lookback_days: int,
) -> None:
    if not _query_is_specific(topic, required_terms):
        return
    normalized_topic = " ".join(topic.lower().split())
    if normalized_topic in seen_topics:
        return
    seen_topics.add(normalized_topic)
    query = DiscoveryQuery(
        id=f"{_stable_slug(movement)}-{kind}",
        movement=movement,
        market_sector=market_sector,
        source_reason=source_reason,
        topic=topic,
        sources=_sources(grounded_available=grounded_available, social_available=False),
        lookback_days=lookback_days,
        web_backend="auto" if grounded_available else "",
        candidate_eligible=True,
        origin_row_ids=origin_row_ids,
        required_terms=required_terms,
        limited=not grounded_available,
        reason="" if grounded_available else "Grounded company discovery unavailable; company discovery is artifact-only.",
    ).to_dict()
    query["kind"] = kind
    query["theme"] = movement
    queries.append(query)


def _stable_slug(text: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in text or "").strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "unknown"


def _movement_terms(text: str) -> list[str]:
    normalized = (text or "").lower().replace("/", " ").replace("-", " ")
    stop = {"the", "and", "for", "with", "from", "this", "that", "tooling", "tools", "startup", "company"}
    return [token for token in normalized.split() if len(token) >= 3 and token not in stop]


def _is_broad_movement(movement: str) -> bool:
    terms = _movement_terms(movement)
    return not terms or (len(terms) == 1 and terms[0] in BROAD_THEMES) or (movement or "").lower() in GENERIC_MOVEMENTS


def _movement_match_strength(text: str, required_terms: list[str]) -> tuple[bool, list[str]]:
    lowered = (text or "").lower()
    matched = [term for term in required_terms if term in lowered]
    if len(matched) >= 2:
        return True, [f"movement_terms_present:{','.join(matched)}"]
    strong = [phrase for phrase in STRONG_MOVEMENT_PHRASES if phrase in lowered]
    if strong:
        return True, [f"strong_movement_phrase:{strong[0]}"]
    return False, ["movement_terms_missing"]


def _query_is_specific(topic: str, required_terms: list[str]) -> bool:
    text = (topic or "").lower()
    return _movement_match_strength(text, required_terms)[0] and any(term in text for term in COMPANY_INTENT_TERMS)


def _focus_item_can_seed_query(item: FocusItem) -> bool:
    movement = (item.market_movement or "").lower()
    text = f"{item.name} {item.why_focus_this_week} {item.why_this_may_be_noise}".lower()
    missing = " ".join(item.missing_evidence).lower()
    return (
        item.recommended_action == "Research deeper"
        and bool(item.evidence_urls)
        and movement not in GENERIC_MOVEMENTS
        and any(term in missing for term in IDENTITY_MISSING_TERMS)
        and item.noise_risk_score < 70
        and not any(term in text for term in NOISY_OSS_TERMS)
    )


def _candidate_can_seed_query(candidate: Candidate) -> bool:
    name = (candidate.name or "").strip()
    theme = (candidate.theme or "").lower()
    text = f"{candidate.name} {candidate.why_on_radar} {candidate.why_this_may_be_noise}".lower()
    return (
        len(name) > 2
        and theme
        and theme not in GENERIC_MOVEMENTS
        and not _is_broad_movement(theme)
        and any(term in " ".join(candidate.missing_identity_evidence).lower() for term in IDENTITY_MISSING_TERMS)
        and not any(term in text for term in NOISY_OSS_TERMS)
    )


def _query_diagnostic(query: dict, *, status: str = "pending", skip_reason: str = "") -> dict:
    diagnostic = {
        "query_id": query.get("id", ""),
        "kind": query.get("kind", ""),
        "topic": query.get("topic", ""),
        "movement": query.get("movement", ""),
        "market_sector": query.get("market_sector", ""),
        "source_reason": query.get("source_reason", ""),
        "origin_row_ids": query.get("origin_row_ids", []),
        "sources": query.get("sources", ""),
        "web_backend": query.get("web_backend", ""),
        "status": status,
        "payload_keys": [],
        "provider_item_count": 0,
        "accepted_count": 0,
        "rejected_count": 0,
        "verification_queries_run": 0,
        "maturity_queries_run": 0,
        "article_fetches_attempted": 0,
        "source_type_counts": {},
        "source_errors": {},
        "top_result_urls": [],
        "top_result_domains": [],
        "skip_reason_counts": {},
        "warnings": [],
        "errors": [],
    }
    if skip_reason:
        _increment_count(diagnostic["skip_reason_counts"], skip_reason)
    return diagnostic


def _record_query_result_preview(diagnostic: dict, item: dict) -> None:
    url = item.get("url") or item.get("source_url") or ""
    domain = _domain_from_url(url) or _normalize_domain(item.get("domain") or item.get("website") or "")
    if url and url not in diagnostic["top_result_urls"] and len(diagnostic["top_result_urls"]) < 5:
        diagnostic["top_result_urls"].append(url)
    if domain and domain not in diagnostic["top_result_domains"] and len(diagnostic["top_result_domains"]) < 5:
        diagnostic["top_result_domains"].append(domain)


def _increment_count(counts: dict, key: str) -> None:
    if not key:
        return
    counts[key] = counts.get(key, 0) + 1


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = (item.get("domain") or item.get("url") or item.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_leads(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = (item.get("domain") or item.get("source_url") or item.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _query_kind_from_id(query_id: str) -> str:
    for suffix in ("theme_company_search", "theme_founder_search", "theme_funding_search", "focus_identity_search", "candidate_identity_search"):
        if (query_id or "").endswith(suffix):
            return suffix
    return ""
