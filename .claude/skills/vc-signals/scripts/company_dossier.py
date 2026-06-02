#!/usr/bin/env python3
"""Build company-review dossiers from noisy source rows."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


SOURCE_OR_DIRECTORY_DOMAINS = {
    "apps.apple.com",
    "github.com",
    "linkedin.com",
    "news.ycombinator.com",
    "producthunt.com",
    "reddit.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe(items: list[Any]) -> list[str]:
    return [item for item in dict.fromkeys(str(value).strip() for value in items) if item]


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = f"https://{url}"
    try:
        host = urlparse(url).netloc.lower().strip().removeprefix("www.")
    except Exception:
        return ""
    return host


def _is_source_or_directory_domain(domain: str) -> bool:
    normalized = (domain or "").lower().strip().removeprefix("www.")
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in SOURCE_OR_DIRECTORY_DOMAINS)


def _row_name(row: dict) -> str:
    return str(row.get("name") or row.get("company_name") or row.get("title") or row.get("display_name") or "").strip()


def _row_domain(row: dict) -> str:
    raw = str(row.get("domain") or row.get("company_domain") or row.get("candidate_domain") or "").strip()
    domain = raw.lower().removeprefix("www.")
    if domain and not _is_source_or_directory_domain(domain):
        return domain
    for key in ("website", "homepage", "resolved_url", "official_url"):
        candidate = _domain_from_url(str(row.get(key) or ""))
        if candidate and not _is_source_or_directory_domain(candidate):
            return candidate
    return ""


def _row_source_bucket(row: dict) -> str:
    text = " ".join(
        str(value or "")
        for value in (
            row.get("source_lane"),
            row.get("candidate_type"),
            row.get("evidence_role"),
            row.get("source"),
            row.get("url"),
        )
    ).lower()
    if "producthunt" in text or "product hunt" in text:
        return "product_hunt"
    if "yc directory" in text or "ycombinator.com/companies" in text or "yc_company" in text:
        return "yc_directory"
    if "news.ycombinator.com" in text or "hackernews" in text or "hacker news" in text:
        return "hn"
    if "github.com" in text or "oss_project" in text or str(row.get("source_lane") or "") == "OSS":
        return "github"
    if "x.com" in text or "twitter.com" in text or str(row.get("source_lane") or "") == "X":
        return "x"
    if "grounded web" in text or "company_discovery" in text or "official_company_page" in text:
        return "manual_web"
    return "other"


def _row_evidence_urls(row: dict) -> list[str]:
    urls = []
    for value in (
        _as_list(row.get("sources"))
        + _as_list(row.get("source_outbound_urls"))
        + _as_list(row.get("evidence_urls"))
        + _as_list(row.get("founder_team_evidence"))
        + _as_list(row.get("stage_funding_evidence"))
        + _as_list(row.get("customer_buyer_evidence"))
        + _as_list(row.get("pricing_evidence"))
        + _as_list(row.get("docs_evidence"))
        + _as_list(row.get("careers_evidence"))
        + [row.get("source"), row.get("url"), row.get("project_url"), row.get("website"), row.get("homepage")]
    ):
        url = str(value or "").strip()
        if url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
    dossier = row.get("hard_evidence_dossier") if isinstance(row.get("hard_evidence_dossier"), dict) else {}
    for value in _as_list(dossier.get("evidence_urls") if isinstance(dossier, dict) else []):
        url = str(value or "").strip()
        if url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
    return urls


def _has_founder_operator(row: dict) -> bool:
    return (
        _has_value(row.get("founders"))
        or _has_value(row.get("founder_profiles"))
        or _has_value(row.get("founder_team_evidence"))
        or _has_value(row.get("maker_profiles"))
        or _has_value(row.get("maker_name"))
        or _has_value(row.get("maintainer_profiles"))
    )


def _has_stage_metadata(row: dict) -> bool:
    return (
        _has_value(row.get("stage"))
        or _has_value(row.get("raised"))
        or _has_value(row.get("raised_amount"))
        or _has_value(row.get("headcount"))
        or _has_value(row.get("stage_funding_evidence"))
    )


def _has_commercial_evidence(row: dict) -> bool:
    dossier = row.get("hard_evidence_dossier") if isinstance(row.get("hard_evidence_dossier"), dict) else {}
    if (
        _has_value(row.get("customer_buyer_evidence"))
        or _has_value(row.get("customer_buyer_evidence_types"))
        or _has_value(row.get("pricing_evidence"))
        or _has_value(row.get("docs_evidence"))
        or _has_value(row.get("careers_evidence"))
        or _has_value(dossier.get("commercial_hints") if isinstance(dossier, dict) else None)
    ):
        return True
    return any(
        term in url.lower()
        for url in _row_evidence_urls(row)
        for term in ("/pricing", "/docs", "/documentation", "/customers", "/case-studies", "/careers", "/jobs")
    )


def _has_product_evidence(row: dict, official_domain: str) -> bool:
    if _has_value(row.get("tagline")) or _has_value(row.get("description")) or _has_value(row.get("why_on_radar")):
        return True
    if official_domain and any(_domain_from_url(url) == official_domain for url in _row_evidence_urls(row)):
        return True
    return _has_value(row.get("product_hunt_url")) or _has_value(row.get("source_headline"))


def _has_social(row: dict) -> bool:
    return _has_value(row.get("company_linkedin")) or _has_value(row.get("company_x"))


def _status(present: bool) -> dict:
    return {"status": "present" if present else "missing"}


def _risk_flags(row: dict) -> list[str]:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("name", "tagline", "description", "why_on_radar", "why_this_may_be_noise")
    ).lower()
    flags = []
    if any(term in text for term in ("daily news", "news brief", "newsletter", "market analysis", "行情")):
        flags.append("content_aggregation_or_news_noise")
    if any(term in text for term in ("free titles", "gaming freebies", "captcha")):
        flags.append("consumer_or_low_fit_noise")
    dossier = row.get("hard_evidence_dossier") if isinstance(row.get("hard_evidence_dossier"), dict) else {}
    identity_risks = _dedupe(_as_list(dossier.get("identity_risk_flags") if isinstance(dossier, dict) else []))
    flags.extend(f"hard_evidence_identity_risk:{risk}" for risk in identity_risks)
    if identity_risks and str(row.get("domain_resolution_source") or "").strip().lower() in {"web_fallback", "hard_evidence"}:
        flags.append("launch_domain_not_confirmed_by_hard_evidence")
    return flags


def _missing_evidence(
    *,
    official_domain: str,
    founder_operator: bool,
    stage_metadata: bool,
    commercial: bool,
    product: bool,
    social: bool,
    row: dict,
) -> list[str]:
    missing = []
    if not official_domain:
        missing.append("official_domain_missing")
    if not founder_operator:
        missing.append("founder_team_missing")
    if not stage_metadata:
        missing.append("stage_funding_or_headcount_missing")
    if not social:
        missing.append("company_linkedin_or_social_missing")
    if not commercial:
        missing.append("commercial_or_customer_signal_missing")
    if not (
        _has_value(row.get("pricing_evidence"))
        or _has_value(row.get("docs_evidence"))
        or _has_value(row.get("careers_evidence"))
        or any(term in url.lower() for url in _row_evidence_urls(row) for term in ("/pricing", "/docs", "/customers", "/careers", "/jobs"))
    ):
        missing.append("pricing_docs_or_careers_missing")
    if not product:
        missing.append("product_proof_missing")
    for gap in (
        _as_list(row.get("missing_owner_evidence"))
        + _as_list(row.get("missing_identity_evidence"))
        + _as_list(row.get("missing_evidence"))
    ):
        normalized = str(gap or "").strip()
        if normalized and normalized not in missing:
            missing.append(normalized)
    return missing


def _manual_checks(missing: list[str], source_bucket: str) -> list[str]:
    checks = []
    gap_set = set(missing)
    if "official_domain_missing" in gap_set:
        checks.append("Resolve official domain from launch text, founder profile, docs, or web search.")
    if "founder_team_missing" in gap_set:
        checks.append("Check founder/team from company site, Product Hunt maker page, GitHub, X, or LinkedIn.")
    if "stage_funding_or_headcount_missing" in gap_set:
        checks.append("Check stage, funding, headcount, jobs, careers, or Crunchbase-style public snippets.")
    if "commercial_or_customer_signal_missing" in gap_set:
        checks.append("Check pricing, docs, customers, case studies, waitlist, or deployment proof.")
    if "company_linkedin_or_social_missing" in gap_set:
        checks.append("Check LinkedIn/company social only for top candidates.")
    if source_bucket == "github":
        checks.append("Search for companies building around this OSS/theme before promoting it as a company.")
    return checks or ["Do one focused official-site check before promotion."]


def _promote_if(missing: list[str]) -> str:
    gap_set = set(missing)
    requirements = []
    if "official_domain_missing" in gap_set:
        requirements.append("official domain")
    if "founder_team_missing" in gap_set:
        requirements.append("founder/team evidence")
    if "stage_funding_or_headcount_missing" in gap_set:
        requirements.append("stage, funding, headcount, or hiring evidence")
    if "commercial_or_customer_signal_missing" in gap_set:
        requirements.append("commercial/customer proof")
    if not requirements:
        return "Promote if the row still matches the thesis after a quick contradiction check."
    return "Promote if manual review confirms " + ", ".join(requirements) + "."


def _discard_if(missing: list[str]) -> str:
    if "official_domain_missing" in missing:
        return "Discard if no official website or durable company identity can be found."
    if "founder_team_missing" in missing:
        return "Discard if no real operator/founder/team evidence appears after focused search."
    return "Discard if evidence remains only launch chatter, social posts, or directories."


def _likely_payoff(missing: list[str], grade: str) -> str:
    if grade in {"A", "B"}:
        return "High: one focused manual check could make this partner-reviewable."
    if "official_domain_missing" in missing or "founder_team_missing" in missing:
        return "Medium: useful if identity resolves cleanly; otherwise keep as watch/noise."
    return "Medium-high: likely useful for partner review if commercial or stage evidence appears."


def build_company_dossier(row: dict) -> dict:
    official_domain = _row_domain(row)
    source_bucket = _row_source_bucket(row)
    founder_operator = _has_founder_operator(row)
    stage_metadata = _has_stage_metadata(row)
    commercial = _has_commercial_evidence(row)
    product = _has_product_evidence(row, official_domain)
    social = _has_social(row)
    risks = _risk_flags(row)
    route = "market_signal" if source_bucket == "github" and not official_domain else "company_candidate" if official_domain else "evidence_gap"

    if official_domain and founder_operator and stage_metadata and commercial:
        grade = "A"
    elif official_domain and founder_operator and commercial:
        grade = "B"
    elif official_domain and founder_operator and product:
        grade = "C"
    else:
        grade = "Gap"

    strict_ready = bool(official_domain and founder_operator and (stage_metadata or commercial) and not risks)
    partner_ready = bool(official_domain and founder_operator and product and source_bucket != "github" and not risks)
    missing = _missing_evidence(
        official_domain=official_domain,
        founder_operator=founder_operator,
        stage_metadata=stage_metadata,
        commercial=commercial,
        product=product,
        social=social,
        row=row,
    )
    checks = _manual_checks(missing, source_bucket)
    evidence_urls = _row_evidence_urls(row)
    return {
        "name": _row_name(row),
        "source_lane": row.get("source_lane", ""),
        "source_bucket": source_bucket,
        "route": route,
        "official_domain": official_domain,
        "official_url": f"https://{official_domain}" if official_domain else "",
        "confidence_grade": grade,
        "partner_review_ready": partner_ready,
        "strict_review_worthy_ready": strict_ready,
        "manual_work_required": bool(missing),
        "evidence_buckets": {
            "identity": _status(bool(official_domain)),
            "founder_team": _status(founder_operator),
            "product": _status(product),
            "commercial": _status(commercial),
            "structured_metadata": _status(stage_metadata),
            "social": _status(social),
        },
        "founder_operator_evidence": _dedupe(
            _as_list(row.get("founders"))
            + _as_list(row.get("founder_profiles"))
            + _as_list(row.get("founder_team_evidence"))
            + _as_list(row.get("maker_profiles"))
            + _as_list(row.get("maintainer_profiles"))
        ),
        "product_evidence": _dedupe(
            _as_list(row.get("product_evidence"))
            + _as_list(row.get("source_outbound_urls"))
            + [row.get("website"), row.get("product_hunt_url"), row.get("url")]
        )[:8],
        "commercial_evidence": _dedupe(
            _as_list(row.get("customer_buyer_evidence"))
            + _as_list(row.get("pricing_evidence"))
            + _as_list(row.get("docs_evidence"))
            + _as_list(row.get("careers_evidence"))
        ),
        "structured_metadata_evidence": _dedupe(
            _as_list(row.get("stage_funding_evidence"))
            + _as_list(row.get("company_linkedin"))
            + _as_list(row.get("headcount"))
            + _as_list(row.get("stage"))
        ),
        "missing_evidence": missing,
        "recommended_manual_checks": checks,
        "recommended_manual_check": checks[0] if checks else "",
        "promote_if": _promote_if(missing),
        "discard_if": _discard_if(missing),
        "likely_payoff": _likely_payoff(missing, grade),
        "why_it_matters": row.get("why_on_radar") or row.get("tagline") or row.get("description") or "",
        "why_this_may_be_noise": row.get("why_this_may_be_noise")
        or ("OSS/theme signal, not a confirmed company." if route == "market_signal" else "Needs manual confirmation before partner action."),
        "risk_flags": risks,
        "evidence_urls": evidence_urls[:8],
    }


def build_partner_review_row(row: dict, dossier: dict | None = None) -> dict:
    dossier = dossier or build_company_dossier(row)
    return {
        "name": dossier["name"],
        "domain": dossier["official_domain"],
        "source_lane": row.get("source_lane", ""),
        "action": row.get("action", ""),
        "tier": row.get("tier", ""),
        "confidence_grade": dossier["confidence_grade"],
        "why_it_matters": dossier["why_it_matters"],
        "official_domain": dossier["official_domain"],
        "founder_team_evidence": dossier["founder_operator_evidence"][:5],
        "product_proof": dossier["product_evidence"][:5],
        "commercial_adoption_proof": dossier["commercial_evidence"][:5],
        "missing_evidence": dossier["missing_evidence"],
        "recommended_manual_check": dossier["recommended_manual_check"],
        "promote_if": dossier["promote_if"],
        "discard_if": dossier["discard_if"],
        "likely_payoff": dossier["likely_payoff"],
        "why_this_may_be_noise": dossier["why_this_may_be_noise"],
        "evidence_urls": dossier["evidence_urls"][:5],
        "dossier": dossier,
    }


def build_manual_evidence_queue_row(row: dict) -> dict:
    dossier = build_company_dossier(row)
    return {
        "name": dossier["name"],
        "domain": dossier["official_domain"],
        "source_lane": row.get("source_lane", ""),
        "market_sector": row.get("market_sector", ""),
        "theme": row.get("theme", ""),
        "action": row.get("action", ""),
        "tier": row.get("tier", ""),
        "confidence_grade": dossier["confidence_grade"],
        "missing_evidence": dossier["missing_evidence"],
        "recommended_manual_check": dossier["recommended_manual_check"],
        "manual_check_sources": dossier["recommended_manual_checks"],
        "promote_if": dossier["promote_if"],
        "discard_if": dossier["discard_if"],
        "likely_payoff": dossier["likely_payoff"],
        "why_it_matters": dossier["why_it_matters"],
        "why_this_may_be_noise": dossier["why_this_may_be_noise"],
        "evidence_urls": dossier["evidence_urls"][:5],
        "dossier": dossier,
    }
