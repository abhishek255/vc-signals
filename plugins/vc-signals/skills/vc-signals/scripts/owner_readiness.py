from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable

from candidate_quality import apply_candidate_name_quality_failure, candidate_quality_from_candidate
from evidence_quality import split_durable_and_weak_urls
from founder_team_verification import extract_named_founder_profiles_from_text
from radar_focus import (
    ACTION_ASSIGN_OWNER,
    ACTION_MONITOR_ONLY,
    ACTION_REFRESH_ATTIO,
    ACTION_RESEARCH_DEEPER,
    ATTIO_NEW_STATUSES,
    ATTIO_NO_OWNER_STATUSES,
    OWNER_READY_THRESHOLD,
    _blocking_owner_missing,
    score_owner_readiness,
)
from radar_models import Candidate, OwnerReadiness


LATE_OR_CONTEXT_STATUSES = {"likely_too_late", "acquired", "incumbent", "category_leader"}
FOUNDER_TERMS = ("founder", "co-founder", "cofounder", "ceo", "cto", "team")
FUNDING_TERMS = ("pre-seed", "pre seed", "seed", "series a", "series b", "funding", "raised")
CUSTOMER_TERMS = (
    "customer",
    "customers",
    "trusted by",
    "used by",
    "design partner",
    "pilot",
    "pilots",
    "enterprise",
    "security teams",
    "ciso",
)


def _clean_query_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    for separator in (" | ", " - ", " – ", " — ", ": "):
        if separator in cleaned:
            parts = [part.strip() for part in cleaned.split(separator) if part.strip()]
            if parts:
                cleaned = parts[-1] if len(parts[-1]) >= 2 else parts[0]
                break
    return cleaned[:80]


def owner_readiness_query(candidate: Candidate) -> str:
    name = _clean_query_name(candidate.name)
    domain = (candidate.domain or candidate.candidate_domain or "").strip()
    if domain:
        return f'"{name}" "{domain}" founder team seed funding customers'
    return f'"{name}" founder team seed funding customers'


def _owner_cache_path(cache_dir: Path | str, topic: str) -> Path:
    digest = hashlib.sha256((topic or "").encode("utf-8")).hexdigest()[:20]
    return Path(cache_dir) / f"{digest}.json"


def _read_cache(cache_dir: Path | None, topic: str) -> dict | None:
    if not cache_dir:
        return None
    path = _owner_cache_path(cache_dir, topic)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _write_cache(cache_dir: Path | None, topic: str, payload: dict) -> None:
    if not cache_dir:
        return
    path = _owner_cache_path(cache_dir, topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _eligible_for_owner_readiness(candidate: Candidate) -> bool:
    if not candidate_quality_from_candidate(candidate).usable:
        return False
    if candidate.category_anchor or candidate.lead_route in {"category_context", "monitor_only"}:
        return False
    if candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return False
    if candidate.identity_type in {"oss_project_watch", "oss_with_commercial_intent"}:
        return False
    if candidate.candidate_type == "oss_project" and candidate.identity_type != "verified_company":
        return False
    return bool(candidate.domain and candidate.identity_type == "verified_company")


def _owner_readiness_skip_reason(candidate: Candidate) -> str:
    name_quality = candidate_quality_from_candidate(candidate)
    if not name_quality.usable:
        return name_quality.rejection_code
    if candidate.category_anchor or candidate.lead_route in {"category_context", "monitor_only"}:
        return "category_context_or_monitor_only"
    if candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return candidate.maturity_status
    if candidate.identity_type in {"oss_project_watch", "oss_with_commercial_intent"}:
        return "oss_project_only"
    if candidate.candidate_type == "oss_project" and candidate.identity_type != "verified_company":
        return "oss_project_only"
    if not candidate.domain or candidate.identity_type != "verified_company":
        return "not_verified_company"
    return ""


def _text_for_items(items: list[dict]) -> str:
    return " ".join(
        " ".join(str(item.get(key, "")) for key in ("title", "snippet", "description", "url"))
        for item in items or []
    ).lower()


def _evidence_urls(items: list[dict]) -> list[str]:
    return list(dict.fromkeys(item.get("url") or item.get("source_url") or "" for item in items or [] if item.get("url") or item.get("source_url")))


def _domain(candidate: Candidate) -> str:
    return (candidate.domain or candidate.candidate_domain or "").strip()


def _company_aliases(candidate: Candidate) -> list[str]:
    aliases: list[str] = []
    for value in (candidate.canonical_name, candidate.display_name, candidate.name, _clean_query_name(candidate.name)):
        value = re.sub(r"\s+", " ", (value or "").strip())
        if value and value.lower() not in {item.lower() for item in aliases}:
            aliases.append(value)
    domain = _domain(candidate)
    root = domain.split(".", 1)[0] if domain else ""
    if root:
        root_title = root[:1].upper() + root[1:]
        if root_title.lower() not in {item.lower() for item in aliases}:
            aliases.append(root_title)
    return aliases[:5]


def _item_text(item: dict) -> str:
    return " ".join(str(item.get(key, "")) for key in ("title", "snippet", "description", "body", "url")).strip()


def _item_url(item: dict) -> str:
    return str(item.get("url") or item.get("source_url") or "").strip()


def _has_stage_funding_text(text: str) -> bool:
    lowered = (text or "").lower()
    if re.search(r"\b(pre[- ]?seed|seed|series\s+[ab])\b", lowered):
        return True
    return bool(re.search(r"\braised\b[^.\n]{0,80}(?:\$|\d|round|financing|funding)", lowered))


def _sanitize_stage_evidence(candidate: Candidate) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    durable, weak = split_durable_and_weak_urls(
        list(dict.fromkeys(list(out.stage_funding_evidence or []) + list(out.maturity_evidence_urls or []))),
        candidate_domain=_domain(out),
    )
    out.stage_funding_evidence = durable[:5]
    out.weak_stage_funding_hints = list(dict.fromkeys(list(out.weak_stage_funding_hints or []) + weak))[:8]
    return out


def _apply_owner_query_evidence(candidate: Candidate, payload: dict) -> tuple[Candidate, dict[str, list[str]]]:
    out = _sanitize_stage_evidence(candidate)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    dimensions = {
        "founder_team_evidence": [],
        "stage_funding_evidence": [],
        "weak_founder_team_hints": list(out.weak_founder_team_hints),
        "weak_stage_funding_hints": list(out.weak_stage_funding_hints),
        "customer_buyer_pull_evidence": [],
        "attio_context_evidence": [],
    }
    customer_urls: list[str] = []
    for item in items:
        item_text = _item_text(item)
        item_url = _item_url(item)
        durable, weak = split_durable_and_weak_urls([item_url], candidate_domain=_domain(out), item=item)
        founder_profiles, _rejected = extract_named_founder_profiles_from_text(
            company_names=_company_aliases(out),
            text=item_text,
            url=item_url,
        )
        if founder_profiles:
            if durable:
                existing_profiles = {(profile.get("name"), profile.get("source")) for profile in out.founder_profiles}
                existing_names = set(out.founders)
                for profile in founder_profiles:
                    name = profile.get("name", "")
                    if name and name not in existing_names:
                        out.founders.append(name)
                        existing_names.add(name)
                    key = (profile.get("name"), profile.get("source"))
                    if key not in existing_profiles:
                        out.founder_profiles.append(dict(profile))
                        existing_profiles.add(key)
                dimensions["founder_team_evidence"].extend(durable)
            else:
                dimensions["weak_founder_team_hints"].extend(weak)
        if _has_stage_funding_text(item_text):
            dimensions["stage_funding_evidence"].extend(durable)
            dimensions["weak_stage_funding_hints"].extend(weak)
        lowered = item_text.lower()
        if any(term in lowered for term in CUSTOMER_TERMS):
            customer_urls.extend(durable or [item_url] if item_url else [])
            out.evidence_metadata.append({"description": item_text[:1200]})
    dimensions["founder_team_evidence"] = list(dict.fromkeys(dimensions["founder_team_evidence"]))[:3]
    dimensions["stage_funding_evidence"] = list(dict.fromkeys(dimensions["stage_funding_evidence"]))[:3]
    dimensions["weak_founder_team_hints"] = list(dict.fromkeys(dimensions["weak_founder_team_hints"]))[:5]
    dimensions["weak_stage_funding_hints"] = list(dict.fromkeys(dimensions["weak_stage_funding_hints"]))[:5]
    dimensions["customer_buyer_pull_evidence"] = list(dict.fromkeys(customer_urls))[:3]
    out.founder_team_evidence = list(dict.fromkeys(list(out.founder_team_evidence) + dimensions["founder_team_evidence"]))[:5]
    out.stage_funding_evidence = list(dict.fromkeys(list(out.stage_funding_evidence) + dimensions["stage_funding_evidence"]))[:5]
    out.weak_founder_team_hints = dimensions["weak_founder_team_hints"]
    out.weak_stage_funding_hints = dimensions["weak_stage_funding_hints"]
    status = (out.attio_status or "unknown").lower()
    if status in ATTIO_NEW_STATUSES or status in ATTIO_NO_OWNER_STATUSES or status in {"stale", "passed"}:
        dimensions["attio_context_evidence"] = [status]
    return out, dimensions


def _recommended_owner_action(candidate: Candidate, score: int, missing: list[str]) -> str:
    if candidate.category_anchor or candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return ACTION_MONITOR_ONLY
    if (candidate.evidence_confidence or "").strip().lower() == "low" or candidate.tier == "Needs More Evidence":
        return ACTION_RESEARCH_DEEPER
    if score < OWNER_READY_THRESHOLD or _blocking_owner_missing(missing):
        return ACTION_RESEARCH_DEEPER
    status = (candidate.attio_status or "unknown").lower()
    if status in {"stale", "passed"}:
        return ACTION_REFRESH_ATTIO
    if status in ATTIO_NEW_STATUSES or status in ATTIO_NO_OWNER_STATUSES:
        return ACTION_ASSIGN_OWNER
    return ACTION_RESEARCH_DEEPER


def _readiness_for_candidate(candidate: Candidate, *, query: str = "", query_status: str = "", payload: dict | None = None) -> tuple[Candidate, OwnerReadiness]:
    scored_candidate = _sanitize_stage_evidence(candidate)
    dimensions = {
        "founder_team_evidence": list(scored_candidate.founder_team_evidence),
        "stage_funding_evidence": list(scored_candidate.stage_funding_evidence),
        "weak_founder_team_hints": list(scored_candidate.weak_founder_team_hints),
        "weak_stage_funding_hints": list(scored_candidate.weak_stage_funding_hints),
        "customer_buyer_pull_evidence": list(scored_candidate.customer_buyer_evidence),
        "attio_context_evidence": [],
    }
    if payload:
        scored_candidate, dimensions = _apply_owner_query_evidence(scored_candidate, payload)
    score, basis, missing, next_step = score_owner_readiness(scored_candidate)
    action = _recommended_owner_action(scored_candidate, score, missing)
    scored_candidate.owner_readiness_score = score
    scored_candidate.owner_readiness_basis = list(basis)
    scored_candidate.missing_owner_evidence = list(missing)
    scored_candidate.recommended_owner_action = action
    scored_candidate.recommended_next_validation_step = next_step
    readiness = OwnerReadiness(
        candidate_key=scored_candidate.stable_key or scored_candidate.domain or scored_candidate.name,
        name=scored_candidate.name,
        domain=scored_candidate.domain,
        eligible=_eligible_for_owner_readiness(scored_candidate),
        owner_readiness_score=score,
        owner_readiness_basis=list(basis),
        missing_owner_evidence=list(missing),
        recommended_owner_action=action,
        recommended_next_validation_step=next_step,
        founder_team_evidence=dimensions["founder_team_evidence"],
        stage_funding_evidence=dimensions["stage_funding_evidence"],
        weak_founder_team_hints=dimensions["weak_founder_team_hints"],
        weak_stage_funding_hints=dimensions["weak_stage_funding_hints"],
        customer_buyer_pull_evidence=dimensions["customer_buyer_pull_evidence"],
        attio_context_evidence=dimensions["attio_context_evidence"],
        evidence_urls=_evidence_urls(payload.get("items", []) if payload else []) or list(scored_candidate.sources[:3]),
        query=query,
        query_status=query_status,
    )
    return scored_candidate, readiness


def enrich_owner_readiness(
    candidates: list[Candidate],
    *,
    query_runner: Callable | None = None,
    cache_dir: Path | str | None = None,
    max_queries: int = 5,
) -> tuple[list[Candidate], dict]:
    cache_path = Path(cache_dir) if cache_dir else None
    enriched: list[Candidate] = []
    readiness_items: list[OwnerReadiness] = []
    summary = {
        "eligible": 0,
        "queries_run": 0,
        "cache_hits": 0,
        "skipped": 0,
    }
    for candidate in candidates:
        skip_reason = _owner_readiness_skip_reason(candidate)
        if skip_reason:
            skipped_candidate = Candidate.from_dict(candidate.to_dict())
            if skip_reason.startswith("candidate_name_quality_failed:"):
                skipped_candidate = apply_candidate_name_quality_failure(skipped_candidate)
            scored, readiness = _readiness_for_candidate(skipped_candidate, query_status=skip_reason)
            enriched.append(scored)
            readiness_items.append(readiness)
            summary["skipped"] += 1
            continue
        summary["eligible"] += 1
        topic = owner_readiness_query(candidate)
        payload = _read_cache(cache_path, topic)
        query_status = "cache_hit" if payload else "not_queried"
        if payload:
            summary["cache_hits"] += 1
        elif query_runner and summary["queries_run"] < max_queries:
            payload = query_runner(
                topic,
                sources="grounding",
                lookback_days=30,
                auto_resolve=True,
                store=True,
                web_backend="auto",
            )
            _write_cache(cache_path, topic, payload)
            summary["queries_run"] += 1
            query_status = "queried"
        elif query_runner:
            query_status = "query_budget_exceeded"
            summary["skipped"] += 1
        elif max_queries <= 0:
            query_status = "live_query_budget_zero"
        else:
            query_status = "live_query_disabled"
        scored, readiness = _readiness_for_candidate(candidate, query=topic, query_status=query_status, payload=payload)
        enriched.append(scored)
        readiness_items.append(readiness)
    report = {
        "summary": summary,
        "items": [item.to_dict() for item in readiness_items],
    }
    return enriched, report


def write_owner_readiness_json(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
