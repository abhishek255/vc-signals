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


def run_hn_outbound_enrichment(
    phase6b_payload: dict,
    *,
    query_runner: Callable | None = None,
    page_fetcher: Callable | None = None,
    attio_matcher: Callable | None = None,
    cache_dir: Path | str | None = None,
    max_candidates: int = 5,
) -> dict:
    cache_path = Path(cache_dir) if cache_dir else None
    rows = phase6b_payload.get("company_rows", []) or []
    enriched_rows: list[dict] = []
    reports = {
        "identity": [],
        "maturity": [],
        "founder_team": {},
        "owner_evidence": {},
    }

    candidates: list[Candidate] = []
    for row in rows[:max_candidates]:
        candidate = _candidate_from_hn_row(row)
        promoted, identity_report = _promote_identity(
            candidate,
            row,
            page_fetcher=page_fetcher,
            cache_dir=cache_path,
        )
        reports["identity"].append(identity_report)
        if promoted.identity_type == "verified_company":
            promoted = _apply_attio(promoted, attio_matcher)
            promoted, maturity_report = _enrich_maturity(promoted, query_runner=query_runner, cache_dir=cache_path)
            reports["maturity"].append(maturity_report)
        else:
            maturity_report = _skipped_maturity_report(promoted, "identity_not_promoted")
            reports["maturity"].append(maturity_report)
        candidates.append(promoted)

    founder_input = [candidate for candidate in candidates if candidate.identity_type == "verified_company"]
    founder_by_key: dict[str, Candidate] = {}
    if founder_input:
        founder_enriched, founder_report = enrich_founder_team_verification(
            founder_input,
            query_runner=query_runner,
            cache_dir=cache_path,
            max_candidates=max_candidates,
        )
        reports["founder_team"] = founder_report
        founder_by_key = {_candidate_key(candidate): candidate for candidate in founder_enriched}

    after_founder = [founder_by_key.get(_candidate_key(candidate), candidate) for candidate in candidates]
    owner_input = [candidate for candidate in after_founder if candidate.identity_type == "verified_company"]
    owner_by_key: dict[str, Candidate] = {}
    if owner_input:
        owner_enriched, owner_report = enrich_owner_evidence(
            owner_input,
            query_runner=query_runner,
            page_fetcher=page_fetcher,
            cache_dir=cache_path,
            max_candidates=max_candidates,
        )
        reports["owner_evidence"] = owner_report
        owner_by_key = {_candidate_key(candidate): candidate for candidate in owner_enriched}

    for candidate, original_row, identity_report in zip(after_founder, rows[:max_candidates], reports["identity"]):
        final_candidate = owner_by_key.get(_candidate_key(candidate), candidate)
        enriched_rows.append(_row_from_candidate(final_candidate, original_row, identity_report))

    passthrough_product = list(phase6b_payload.get("product_context_rows", []) or [])
    passthrough_projects = list(phase6b_payload.get("project_only_rows", []) or [])
    rejected = list(phase6b_payload.get("rejected_rows", []) or [])
    return {
        "phase": "Phase 6B.2-HN",
        "scope": "HN outbound candidate enrichment; weekly default unchanged; YC remains parked.",
        "summary": _summary(enriched_rows, passthrough_product, passthrough_projects, rejected),
        "enriched_outbound_candidates": enriched_rows,
        "product_context_rows": passthrough_product,
        "project_only_rows": passthrough_projects,
        "rejected_rows": rejected,
        "reports": reports,
    }


def load_phase6b_payload(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def write_hn_outbound_enrichment_artifacts(payload: dict, output_dir: Path | str) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    json_path = path / "hn-outbound-enrichment.json"
    md_path = path / "hn-outbound-enrichment.md"
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_markdown(payload))
    return [json_path, md_path]


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
) -> tuple[Candidate, dict]:
    out = Candidate.from_dict(candidate.to_dict())
    domain = _normalize_domain(out.domain)
    urls = _identity_urls(row, domain)
    checked: list[str] = []
    failed: list[str] = []
    matched_url = ""
    fetch = page_fetcher or _default_page_fetcher
    for url in urls:
        payload = _read_or_fetch_page(url, fetch, cache_dir)
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


def _apply_attio(candidate: Candidate, attio_matcher: Callable | None) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    if not attio_matcher:
        out.attio_status = out.attio_status or "unknown"
        return out
    payload = attio_matcher(out)
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


def _enrich_maturity(candidate: Candidate, *, query_runner: Callable | None, cache_dir: Path | None) -> tuple[Candidate, dict]:
    topic = _maturity_query(candidate)
    payload, query_status = _run_cached_query(topic, query_runner=query_runner, cache_dir=cache_dir)
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
    strict_customer_urls = list(candidate.customer_buyer_evidence)

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
    }


def _named_founder_profiles(candidate: Candidate) -> list[dict]:
    profiles = []
    for profile in candidate.founder_profiles:
        name = str(profile.get("name", "")).strip()
        if name and name.lower() != "source-backed founder/team evidence":
            profiles.append(dict(profile))
    return profiles


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


def _summary(rows: list[dict], product_rows: list[dict], project_rows: list[dict], rejected_rows: list[dict]) -> dict:
    return {
        "hn_outbound_candidates_input": len(rows),
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


def _read_or_fetch_page(url: str, fetcher: Callable, cache_dir: Path | None):
    if not cache_dir:
        return fetcher(url)
    path = cache_dir / "hn-official-pages" / f"{_stable_hash(url)}.json"
    if path.exists():
        try:
            return json.loads(path.read_text()).get("payload", "")
        except json.JSONDecodeError:
            return ""
    payload = fetcher(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "payload": payload}, indent=2))
    return payload


def _run_cached_query(topic: str, *, query_runner: Callable | None, cache_dir: Path | None) -> tuple[dict, str]:
    if not query_runner:
        return {"items": []}, "not_queried"
    if cache_dir:
        path = cache_dir / "hn-outbound-queries" / f"{_stable_hash(topic)}.json"
        if path.exists():
            try:
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
    args = parser.parse_args(argv)
    payload = run_hn_outbound_enrichment(
        load_phase6b_payload(args.phase6b_json),
        query_runner=_default_query_runner if args.live_queries else None,
        page_fetcher=None,
        attio_matcher=_default_attio_matcher if args.attio else None,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )
    write_hn_outbound_enrichment_artifacts(payload, args.output_dir)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
