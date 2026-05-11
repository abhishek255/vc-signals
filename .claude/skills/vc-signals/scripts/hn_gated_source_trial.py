#!/usr/bin/env python3
"""Phase 6B-HN gated trial for last30days-native HN launch evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from identity_resolution import apply_identity_to_candidate, resolve_candidate_identity
from radar_company_discovery import _classify_maturity_from_items
from radar_focus import ACTION_ASSIGN_OWNER, ACTION_MONITOR_ONLY, ACTION_RESEARCH_DEEPER, score_owner_readiness
from radar_models import Candidate


PRODUCT_SUBDOMAIN_HINTS = {"api", "app", "blog", "cli", "cloud", "console", "docs", "help", "labs", "platform", "www"}
ACCELERATOR_BATCH_RE = re.compile(r"\b(?:YC|Y\s+Combinator)\s+([SWF]\d{2})\b", re.IGNORECASE)
EXPLICIT_CUSTOMER_TERMS = (
    "customer",
    "customers",
    "trusted by",
    "used by",
    "design partner",
    "pilot",
    "pilots",
    "enterprise",
    "buyer",
    "ciso",
)
EXPLICIT_COMMERCIAL_TERMS = (
    "pricing",
    "demo",
    "waitlist",
    "contact sales",
    "customer",
    "customers",
    "enterprise",
    "seed round",
    "raised seed",
    "pre-seed",
    "pre seed",
    "series a",
    "series b",
    "funding",
    "raised $",
)


def run_hn_gated_source_trial(native_payload: dict) -> dict:
    outbound_rows = [_gate_company_candidate(row) for row in native_payload.get("company_candidates", []) or []]
    product_context_rows = [
        row
        for row in outbound_rows
        if row.get("product_subdomain_guardrail")
        or row.get("lead_route") in {"category_context", "monitor_only"}
        or row.get("recommended_action") == ACTION_MONITOR_ONLY
    ]
    company_rows = [row for row in outbound_rows if row not in product_context_rows]
    project_rows = [_gate_project_only(row) for row in native_payload.get("project_only_leads", []) or []]
    rejected_rows = [_gate_rejected(row) for row in (native_payload.get("needs_detail_enrichment", []) or []) + (native_payload.get("rejected_leads", []) or [])]
    summary = _summary(outbound_rows, company_rows, product_context_rows, project_rows, rejected_rows, native_payload.get("summary", {}))
    return {
        "phase": "Phase 6B-HN",
        "scope": "HN-only gated source trial; YC remains parked until last30days returns YC source items.",
        "summary": summary,
        "company_rows": company_rows,
        "product_context_rows": product_context_rows,
        "project_only_rows": project_rows,
        "rejected_rows": rejected_rows,
    }


def load_native_payload(path: Path | str) -> dict:
    payload = json.loads(Path(path).read_text())
    if "normalized_leads" in payload:
        return payload["normalized_leads"]
    return payload


def write_hn_gated_source_trial_artifacts(payload: dict, output_dir: Path | str) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    json_path = path / "hn-gated-source-trial.json"
    md_path = path / "hn-gated-source-trial.md"
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_markdown(payload))
    return [json_path, md_path]


def _gate_company_candidate(row: dict) -> dict:
    candidate = _candidate_from_hn_company(row)
    resolution = resolve_candidate_identity(candidate, hn_cache={})
    candidate = apply_identity_to_candidate(candidate, resolution)
    maturity = _classify_maturity_from_items([_maturity_item_from_row(row)], company_name=candidate.name, domain=candidate.domain)
    _apply_maturity(candidate, maturity)
    _apply_accelerator_context(candidate, row)

    missing_evidence = list(row.get("missing_evidence") or [])
    product_subdomain = _is_product_subdomain(row)
    outbound_domain = _normalize_domain(row.get("domain") or _domain_from_url(row.get("official_url", "")))
    if product_subdomain:
        candidate.domain = ""
        candidate.identity_type = "launch_style_needs_identity"
        candidate.identity_confidence_score = min(candidate.identity_confidence_score or 0, 45)
        candidate.attio_safe_to_match = False
        candidate.recommended_identity_action = ACTION_MONITOR_ONLY
        candidate.lead_route = "category_context"
        candidate.category_anchor = True
        missing_evidence.append("product_subdomain_not_company_proof")
    else:
        _mark_hn_outbound_identity(candidate)

    owner_score, owner_basis, missing_owner, next_step = _score_hn_owner_readiness(candidate, row)
    action = _trial_action(candidate, owner_score, missing_owner)
    assign_owner = action == ACTION_ASSIGN_OWNER
    new_to_marathon = _new_to_marathon(candidate, action)

    if product_subdomain:
        action = ACTION_MONITOR_ONLY
        assign_owner = False
        new_to_marathon = False

    unsafe = bool(
        assign_owner
        and (
            candidate.maturity_status != "seed_to_series_b"
            or candidate.identity_type != "verified_company"
            or not candidate.attio_safe_to_match
            or _blocking_trial_missing(missing_owner)
        )
    )
    company_domain = candidate.domain if candidate.identity_type in {"verified_company", "hn_outbound_candidate"} and not product_subdomain else ""
    return {
        "name": candidate.display_name or candidate.canonical_name or candidate.name,
        "source_title": row.get("title", ""),
        "source_url": row.get("source_url", ""),
        "official_url": row.get("official_url", ""),
        "outbound_domain": outbound_domain,
        "company_domain": company_domain,
        "hn_author": row.get("author", ""),
        "hn_engagement": {"points": row.get("points", 0), "comments": row.get("comments", 0)},
        "hn_points": row.get("points", 0),
        "hn_comments": row.get("comments", 0),
        "identity_type": candidate.identity_type,
        "identity_confidence_score": candidate.identity_confidence_score,
        "identity_basis": list(candidate.identity_confidence_basis),
        "identity_risk": _identity_risk(candidate, product_subdomain),
        "verified_domain_basis": list(candidate.verified_domain_basis),
        "maturity_status": candidate.maturity_status,
        "maturity_basis": list(candidate.maturity_basis),
        "maturity_evidence_urls": list(candidate.maturity_evidence_urls),
        "category_anchor": candidate.category_anchor,
        "lead_route": candidate.lead_route,
        "recommended_action": action,
        "assign_owner": assign_owner,
        "new_to_marathon": new_to_marathon,
        "owner_readiness_score": owner_score,
        "owner_readiness_basis": owner_basis,
        "missing_owner_evidence": list(dict.fromkeys(missing_owner)),
        "missing_evidence": list(dict.fromkeys(missing_evidence)),
        "next_validation_step": next_step,
        "attio_status": candidate.attio_status,
        "attio_safe_to_match": candidate.attio_safe_to_match,
        "product_subdomain_guardrail": product_subdomain,
        "unsafe_promotion": unsafe,
        "recommended_lane": "HN Product / Category Context" if product_subdomain or candidate.lead_route in {"category_context", "monitor_only"} else "HN Outbound Candidates",
        "movement": row.get("movement", ""),
        "market_sector": row.get("market_sector", ""),
        "raw_source_kind": "hn_outbound_candidate",
        "source_kind": "hn_product_context" if product_subdomain or candidate.lead_route in {"category_context", "monitor_only"} else "hn_outbound_candidate",
    }


def _gate_project_only(row: dict) -> dict:
    return {
        "name": row.get("name") or row.get("title") or "HN project",
        "source_title": row.get("title", ""),
        "source_url": row.get("source_url", ""),
        "project_url": row.get("official_url", ""),
        "hn_author": row.get("author", ""),
        "hn_engagement": {"points": row.get("points", 0), "comments": row.get("comments", 0)},
        "company_domain": "",
        "identity_type": "oss_project_watch",
        "lead_route": "project_watch",
        "recommended_action": ACTION_RESEARCH_DEEPER,
        "assign_owner": False,
        "new_to_marathon": False,
        "missing_evidence": list(row.get("missing_evidence") or ["project_only_not_company_identity"]),
        "why_useful": "HN technical launch signal; can support movement evidence but not company identity.",
        "recommended_lane": "HN Project Watch / Technical Launch Signals",
        "movement": row.get("movement", ""),
        "market_sector": row.get("market_sector", ""),
        "source_kind": "hn_project_only",
    }


def _gate_rejected(row: dict) -> dict:
    return {
        "name": row.get("name") or row.get("title") or "Rejected HN row",
        "source_title": row.get("title", ""),
        "source_url": row.get("source_url", ""),
        "recommended_action": ACTION_RESEARCH_DEEPER,
        "missing_evidence": list(row.get("missing_evidence") or ["rejected_upstream"]),
        "recommended_lane": "HN Rejected / Noisy",
        "source_kind": "hn_rejected",
    }


def _candidate_from_hn_company(row: dict) -> Candidate:
    name = row.get("name") or row.get("title") or "HN company candidate"
    hn_url = row.get("source_url") or ""
    official_url = row.get("official_url") or ""
    domain = _normalize_domain(row.get("domain") or _domain_from_url(official_url))
    title = row.get("title") or name
    snippet = row.get("snippet") or title
    return Candidate(
        name=name,
        canonical_name=name,
        display_name=name,
        source_headline=title,
        sector=row.get("market_sector", ""),
        market_sector=row.get("market_sector", ""),
        theme=row.get("movement", ""),
        source=hn_url,
        sources=[url for url in [hn_url, official_url] if url],
        candidate_type="company_web",
        stable_key=f"hn:{row.get('source_url') or official_url or name}",
        domain=domain,
        why_on_radar=snippet or title,
        why_this_may_be_noise="HN launch evidence needs independent validation before routing.",
        attio_status="unknown",
        investment_interest_score=55,
        evidence_confidence_score=50,
        source_lane="Hacker News",
        evidence_metadata=[
            {
                "source": "hackernews",
                "source_url": hn_url,
                "outbound_url": official_url,
                "domain": domain,
                "title": title,
                "author": row.get("author", ""),
                "engagement": {"points": row.get("points", 0), "comments": row.get("comments", 0)},
            }
        ],
    )


def _maturity_item_from_row(row: dict) -> dict:
    return {
        "title": row.get("title", ""),
        "snippet": row.get("snippet") or row.get("title", ""),
        "url": row.get("official_url") or row.get("source_url", ""),
    }


def _apply_maturity(candidate: Candidate, maturity: dict) -> None:
    candidate.maturity_status = maturity.get("maturity_status", "unknown")
    candidate.maturity_basis = list(maturity.get("maturity_basis") or [])
    candidate.maturity_evidence_urls = list(maturity.get("maturity_evidence_urls") or [])
    candidate.category_anchor = bool(maturity.get("category_anchor"))
    candidate.consensus_risk_reason = maturity.get("consensus_risk_reason", "")
    candidate.lead_route = maturity.get("lead_route", "research_deeper")


def _apply_accelerator_context(candidate: Candidate, row: dict) -> None:
    if candidate.maturity_status != "unknown":
        return
    text = " ".join(str(row.get(key, "")) for key in ("name", "title", "snippet", "batch"))
    match = ACCELERATOR_BATCH_RE.search(text)
    if not match:
        return
    batch = f"YC {match.group(1).upper()}"
    candidate.maturity_status = "early_stage_context"
    candidate.maturity_basis = [f"accelerator_batch_evidence: {batch}"]
    candidate.maturity_evidence_urls = [url for url in [row.get("source_url", ""), row.get("official_url", "")] if url][:1]
    candidate.lead_route = "research_deeper"
    candidate.category_anchor = False
    candidate.consensus_risk_reason = "accelerator batch signal needs official/company corroboration before sourcing promotion"


def _mark_hn_outbound_identity(candidate: Candidate) -> None:
    if candidate.identity_type != "verified_company":
        return
    if "hn_outbound_url_metadata" not in set(candidate.verified_domain_basis):
        return
    candidate.identity_type = "hn_outbound_candidate"
    candidate.identity_confidence_score = min(candidate.identity_confidence_score or 0, 65)
    candidate.identity_confidence = "Medium"
    candidate.identity_confidence_basis = list(
        dict.fromkeys(list(candidate.identity_confidence_basis) + ["hn_outbound_not_independent_company_proof"])
    )
    candidate.attio_safe_to_match = False
    candidate.recommended_identity_action = ACTION_RESEARCH_DEEPER


def _score_hn_owner_readiness(candidate: Candidate, row: dict) -> tuple[int, list[str], list[str], str]:
    score, basis, missing, next_step = score_owner_readiness(candidate)
    basis = list(basis)
    missing = list(missing)
    text = _row_text(row, candidate)
    if "customer_buyer_pull_evidence" in basis and not _has_explicit_customer_pull(text):
        basis.remove("customer_buyer_pull_evidence")
        score -= 15
        missing.append("no customer/buyer pull evidence")
    if "commercial_or_funding_evidence" in basis and not _has_explicit_commercial_or_funding(text, candidate):
        basis.remove("commercial_or_funding_evidence")
        score -= 10
        missing.append("no commercial/funding evidence")
    missing = list(dict.fromkeys(missing))
    basis = list(dict.fromkeys(basis))
    return max(0, min(100, score)), basis, missing, _hn_next_validation_step(missing, next_step)


def _row_text(row: dict, candidate: Candidate) -> str:
    values = [
        row.get("name", ""),
        row.get("title", ""),
        row.get("snippet", ""),
        candidate.why_on_radar,
        candidate.stage,
        candidate.raised,
        candidate.maturity_basis,
        candidate.stage_funding_evidence,
        candidate.customer_buyer_evidence,
    ]
    return " ".join(str(value) for value in values if value).lower()


def _has_explicit_customer_pull(text: str) -> bool:
    return any(term in text for term in EXPLICIT_CUSTOMER_TERMS)


def _has_explicit_commercial_or_funding(text: str, candidate: Candidate) -> bool:
    if candidate.maturity_status == "seed_to_series_b":
        return True
    return any(term in text for term in EXPLICIT_COMMERCIAL_TERMS)


def _hn_next_validation_step(missing: list[str], fallback: str) -> str:
    if any("founder" in item.lower() for item in missing):
        return "Find founder/team source"
    if any("stage" in item.lower() or "funding" in item.lower() for item in missing):
        return "Verify stage/funding source"
    if any("attio" in item.lower() for item in missing):
        return "Check Attio match/status"
    if any("customer" in item.lower() or "buyer" in item.lower() for item in missing):
        return "Find buyer/customer pull evidence"
    return fallback or "Review HN outbound evidence"


def _trial_action(candidate: Candidate, owner_score: int, missing_owner: list[str]) -> str:
    if candidate.category_anchor or candidate.lead_route in {"category_context", "monitor_only"}:
        return ACTION_MONITOR_ONLY
    if (
        candidate.lead_route == "sourcing_candidate"
        and candidate.maturity_status == "seed_to_series_b"
        and candidate.identity_type == "verified_company"
        and candidate.attio_safe_to_match
        and (candidate.attio_status or "").lower() in {"no_match", "not_found", "new", "no_owner"}
        and owner_score >= 80
        and not _blocking_trial_missing(missing_owner)
    ):
        return ACTION_ASSIGN_OWNER
    return ACTION_RESEARCH_DEEPER


def _new_to_marathon(candidate: Candidate, action: str) -> bool:
    return bool(
        action == ACTION_ASSIGN_OWNER
        and candidate.identity_type == "verified_company"
        and candidate.domain
        and candidate.attio_safe_to_match
        and (candidate.attio_status or "").lower() in {"no_match", "not_found", "new"}
        and not candidate.category_anchor
    )


def _blocking_trial_missing(missing: list[str]) -> list[str]:
    non_blocking = {"no customer/buyer pull evidence"}
    return [item for item in missing if item not in non_blocking]


def _is_product_subdomain(row: dict) -> bool:
    domain = _normalize_domain(row.get("domain") or _domain_from_url(row.get("official_url", "")))
    if not domain:
        return False
    labels = [label for label in domain.split(".") if label]
    if len(labels) <= 2:
        return False
    first = labels[0]
    title = f" {row.get('title', '').lower()} "
    if first in PRODUCT_SUBDOMAIN_HINTS:
        return True
    return " releases " in title and first not in {labels[-2]}


def _identity_risk(candidate: Candidate, product_subdomain: bool) -> str:
    if product_subdomain:
        return "product_subdomain_not_company_proof"
    if candidate.identity_type == "hn_outbound_candidate":
        return "hn_outbound_domain_needs_independent_company_verification"
    if candidate.identity_type != "verified_company":
        return "identity_not_verified"
    if not candidate.domain:
        return "missing_company_domain"
    return "verified_outbound_domain_needs_independent_review"


def _summary(
    outbound_rows: list[dict],
    company_rows: list[dict],
    product_context_rows: list[dict],
    project_rows: list[dict],
    rejected_rows: list[dict],
    native_summary: dict,
) -> dict:
    routes = Counter(row.get("lead_route") for row in outbound_rows)
    return {
        "input_items_seen": native_summary.get("items_seen", 0),
        "hn_outbound_candidate_rows": len(company_rows),
        "company_candidate_rows": len(company_rows),
        "product_context_rows": len(product_context_rows),
        "project_only_rows": len(project_rows),
        "rejected_rows": len(rejected_rows),
        "research_deeper_rows": sum(1 for row in company_rows if row.get("recommended_action") == ACTION_RESEARCH_DEEPER),
        "category_context_rows": routes.get("category_context", 0),
        "monitor_only_rows": sum(1 for row in outbound_rows if row.get("recommended_action") == ACTION_MONITOR_ONLY),
        "sourcing_candidate_rows": sum(
            1
            for row in outbound_rows
            if row.get("lead_route") == "sourcing_candidate" and row.get("recommended_action") == ACTION_ASSIGN_OWNER
        ),
        "assign_owner_rows": sum(1 for row in outbound_rows if row.get("assign_owner")),
        "new_to_marathon_rows": sum(1 for row in outbound_rows if row.get("new_to_marathon")),
        "unsafe_promotions": sum(1 for row in outbound_rows if row.get("unsafe_promotion")),
        "product_subdomain_guardrails": sum(1 for row in outbound_rows if row.get("product_subdomain_guardrail")),
        "maturity_unknown_rows": sum(1 for row in outbound_rows if row.get("maturity_status") == "unknown"),
        "early_stage_context_rows": sum(1 for row in outbound_rows if row.get("maturity_status") == "early_stage_context"),
        "maturity_confirmed_early_stage_rows": sum(1 for row in outbound_rows if row.get("maturity_status") == "seed_to_series_b"),
        "category_or_monitor_rows": sum(1 for row in outbound_rows if row.get("lead_route") in {"category_context", "monitor_only"}),
    }


def _markdown(payload: dict) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Phase 6B-HN Gated Source Trial",
        "",
        "HN-only gated trial. YC remains parked because last30days returned no YC source items. Trial rows did not bypass identity, maturity, owner-readiness, or Attio gates.",
        "",
        "## Summary",
        "",
    ]
    for key in (
        "hn_outbound_candidate_rows",
        "product_context_rows",
        "project_only_rows",
        "rejected_rows",
        "research_deeper_rows",
        "category_context_rows",
        "early_stage_context_rows",
        "sourcing_candidate_rows",
        "assign_owner_rows",
        "new_to_marathon_rows",
        "unsafe_promotions",
        "product_subdomain_guardrails",
    ):
        lines.append(f"- {key}: {summary.get(key, 0)}")
    lines.extend(["", "## HN Outbound Candidates", ""])
    if payload.get("company_rows"):
        for row in payload["company_rows"]:
            lines.append(
                f"- {row.get('name')} - {row.get('recommended_action')} - {row.get('lead_route')} - "
                f"{row.get('company_domain') or row.get('outbound_domain') or 'no domain'} - "
                f"maturity: {row.get('maturity_status')} - missing: {', '.join(row.get('missing_owner_evidence') or []) or 'none'}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## HN Product / Category Context", ""])
    if payload.get("product_context_rows"):
        for row in payload["product_context_rows"]:
            lines.append(
                f"- {row.get('name')} - {row.get('recommended_action')} - {row.get('lead_route')} - "
                f"{row.get('outbound_domain') or 'no domain'} - reason: {', '.join(row.get('missing_evidence') or row.get('maturity_basis') or []) or row.get('identity_risk')}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## HN Project Watch / Technical Launch Signals", ""])
    if payload.get("project_only_rows"):
        for row in payload["project_only_rows"]:
            lines.append(f"- {row.get('name')} - project watch - {row.get('source_url')}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith(("http://", "https://")):
        raw = urlparse(raw).netloc
    raw = raw.split("/", 1)[0].lower().strip("/")
    return raw[4:] if raw.startswith("www.") else raw


def _domain_from_url(url: str) -> str:
    return _normalize_domain(urlparse(url or "").netloc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 6B-HN gated source trial.")
    parser.add_argument("--native-leads-json", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    payload = run_hn_gated_source_trial(load_native_payload(args.native_leads_json))
    write_hn_gated_source_trial_artifacts(payload, args.output_dir)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
