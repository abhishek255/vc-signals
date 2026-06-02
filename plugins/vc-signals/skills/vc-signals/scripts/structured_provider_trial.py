#!/usr/bin/env python3
"""Focused structured-provider trial for the top Evidence Gap rows.

This does not scrape gated provider pages. When direct provider keys are absent,
it creates public/manual provider-style checks for only the top rows.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlparse

from last30days_adapter import run_query
from source_access import detect_enrichment_provider_access

try:
    import requests

    HAS_REQUESTS = True
except ImportError:  # pragma: no cover - damaged local installs
    requests = None
    HAS_REQUESTS = False


STRUCTURED_PROVIDERS = ("Crunchbase", "Coresignal", "LinkedIn")
DIRECT_PROVIDER_KEYS = {
    "CRUNCHBASE_API_KEY": "",
    "CRUNCHBASE_TOKEN": "",
    "CORESIGNAL_API_KEY": "",
    "LINKEDIN_ACCESS_TOKEN": "",
    "LINKEDIN_API_KEY": "",
}
DEFAULT_OUTPUT_NAME = "structured-provider-trial.json"
CORESIGNAL_CLEAN_COMPANY_ENRICH_URL = "https://api.coresignal.com/cdapi/v2/company_clean/enrich"
CORESIGNAL_TIMEOUT_SECONDS = 20
FOCUSED_SOURCE_PRIORITY = {
    "Product Hunt": 0,
    "X": 1,
    "YC": 2,
    "GitHub": 2,
    "Manual Web": 3,
    "Grounded Web": 3,
}
COMPANY_LIKE_SOURCE_LANES = {"Product Hunt", "X", "YC", "Manual Web", "Grounded Web"}


def _read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return fallback


def _domain_from_url(url: str) -> str:
    domain = (urlparse(url or "").netloc or "").lower().strip()
    return domain[4:] if domain.startswith("www.") else domain


def _target_website_url(target: dict) -> str:
    domain = str(target.get("domain") or target.get("website") or "").strip()
    if not domain:
        return ""
    return domain if "://" in domain else f"https://{domain.lower().removeprefix('www.')}"


def _first_scalar(*values):
    for value in values:
        if isinstance(value, list):
            for item in value:
                scalar = _first_scalar(item)
                if scalar not in ("", None):
                    return scalar
        elif isinstance(value, dict):
            scalar = _first_scalar(
                value.get("url"),
                value.get("name"),
                value.get("value"),
                value.get("title"),
            )
            if scalar not in ("", None):
                return scalar
        elif value not in ("", None, [], {}):
            return value
    return ""


def _extract_payload_object(payload) -> dict:
    if isinstance(payload, list):
        return _extract_payload_object(payload[0]) if payload else {}
    if not isinstance(payload, dict):
        return {}
    for key in ("data", "company", "result", "results"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
        if isinstance(value, list) and value:
            return _extract_payload_object(value[0])
    return payload


def _normalize_founders(value) -> list[str]:
    founders = []
    values = value if isinstance(value, list) else [value]
    for item in values:
        if isinstance(item, dict):
            name = str(_first_scalar(item.get("name"), item.get("full_name"), item.get("title")) or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in founders:
            founders.append(name)
    return founders[:5]


def _first_url_like(*values) -> str:
    value = str(_first_scalar(*values) or "").strip()
    return value


def _normalize_coresignal_payload(payload, *, source_url: str) -> dict:
    company = _extract_payload_object(payload)
    funding_rounds = company.get("funding_rounds") if isinstance(company.get("funding_rounds"), list) else []
    first_round = funding_rounds[0] if funding_rounds and isinstance(funding_rounds[0], dict) else {}
    website = _first_url_like(
        company.get("websites_resolved"),
        company.get("websites_main"),
        company.get("websites_main_original"),
        company.get("website"),
        company.get("website_url"),
        company.get("url"),
    )
    company_linkedin = _first_url_like(
        company.get("websites_professional_network_canonical"),
        company.get("websites_professional_network"),
        company.get("social_professional_network_urls"),
        company.get("linkedin_url"),
        company.get("company_linkedin"),
    )
    headcount = _first_scalar(
        company.get("size_range"),
        company.get("size_employees_count"),
        company.get("size_employees_count_inferred"),
        company.get("employees_count"),
        company.get("employee_count"),
    )
    stage = _first_scalar(
        company.get("last_round_type"),
        company.get("last_funding_round_name"),
        company.get("funding_stage"),
        first_round.get("last_round_type"),
    )
    founders = _normalize_founders(company.get("founders") or company.get("founder_names") or [])
    return {
        "company_name": str(_first_scalar(company.get("name"), company.get("company_name")) or "").strip(),
        "website": website,
        "company_linkedin": company_linkedin,
        "headcount": headcount,
        "stage": stage,
        "founders": founders,
        "source_url": source_url,
        "raw_fields_present": sorted(str(key) for key in company.keys())[:30],
    }


def _run_coresignal_company_enrich(target: dict, *, env: dict[str, str]) -> dict:
    if not HAS_REQUESTS:
        return {"skipped": True, "skip_reason": "requests_unavailable_for_coresignal_enrich"}
    api_key = str(env.get("CORESIGNAL_API_KEY") or "").strip().strip("\"'")
    if not api_key:
        return {"skipped": True, "skip_reason": "coresignal_api_key_missing"}
    website = _target_website_url(target)
    if not website:
        return {"skipped": True, "skip_reason": "missing_domain_for_coresignal_enrich"}
    endpoint = f"{CORESIGNAL_CLEAN_COMPANY_ENRICH_URL}?website={quote(website, safe='')}"
    try:
        response = requests.get(
            endpoint,
            headers={"accept": "application/json", "apikey": api_key},
            timeout=CORESIGNAL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {"error": f"coresignal_enrich_failed: {exc}"}
    normalized = _normalize_coresignal_payload(payload, source_url=endpoint)
    if not any(value for key, value in normalized.items() if key not in {"raw_fields_present", "source_url"}):
        return {"skipped": True, "skip_reason": "coresignal_enrich_returned_no_company_fields", "source_url": endpoint}
    return normalized


def _compact_item(item: dict) -> dict:
    url = item.get("url") or item.get("source_url") or ""
    return {
        "title": item.get("title") or "",
        "url": url,
        "domain": item.get("domain") or _domain_from_url(url),
        "source": item.get("source") or "",
        "snippet": item.get("snippet") or item.get("description") or "",
        "published_at": item.get("published_at") or "",
    }


def _source_priority(row: dict) -> tuple[int, str]:
    source_lane = str(row.get("source_lane") or row.get("source") or "").strip()
    priority = FOCUSED_SOURCE_PRIORITY.get(source_lane, 9)
    return priority, str(row.get("name") or "").lower()


def _company_like_provider_target(row: dict) -> bool:
    source_lane = str(row.get("source_lane") or row.get("source") or "").strip()
    name = str(row.get("name") or row.get("company_name") or "").strip()
    domain = str(row.get("domain") or "").lower().removeprefix("www.").strip()
    if source_lane in COMPANY_LIKE_SOURCE_LANES:
        return True
    if "/" in name and (not domain or domain == "github.com"):
        return False
    return bool(domain and domain not in {"github.com", "x.com", "producthunt.com", "news.ycombinator.com"})


def _load_gap_targets(run_dir: Path) -> list[dict]:
    payload = _read_json(run_dir / "source-yield-validation-report.json", {})
    rows = payload.get("evidence_gap_queue") or []
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("company_name") or "").strip()
        if not name:
            continue
        normalized_row = {
            **row,
            "name": name,
            "domain": str(row.get("domain") or "").strip(),
            "source_lane": str(row.get("source_lane") or row.get("source") or "").strip(),
            "missing_evidence": row.get("missing_evidence") or [],
            "recommended_next_step": row.get("recommended_next_step") or row.get("next_step") or "",
        }
        if _company_like_provider_target(normalized_row):
            normalized.append(normalized_row)
    return sorted(normalized, key=_source_priority)


def _load_partner_review_targets(run_dir: Path) -> list[dict]:
    payload = _read_json(run_dir / "source-yield-validation-report.json", {})
    rows = payload.get("partner_review_companies") or []
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("company_name") or "").strip()
        if not name:
            continue
        normalized_row = {
            **row,
            "name": name,
            "domain": str(row.get("domain") or row.get("official_domain") or "").strip(),
            "source_lane": str(row.get("source_lane") or row.get("source") or "").strip(),
            "missing_evidence": row.get("missing_evidence") or [],
            "recommended_next_step": (
                row.get("recommended_next_step")
                or row.get("recommended_manual_check")
                or row.get("next_step")
                or ""
            ),
        }
        if _company_like_provider_target(normalized_row):
            normalized.append(normalized_row)
    return sorted(normalized, key=_source_priority)


def _load_targets(run_dir: Path, *, target_source: str) -> list[dict]:
    if target_source == "partner_review_companies":
        return _load_partner_review_targets(run_dir)
    return _load_gap_targets(run_dir)


def build_provider_queries(target: dict, *, queries_per_target: int = 3) -> list[dict]:
    name = str(target.get("name") or "").strip()
    domain = str(target.get("domain") or "").strip()
    quoted_name = f'"{name}"' if name else ""
    quoted_domain = f'"{domain}"' if domain else ""
    identity = " ".join(part for part in (quoted_name, quoted_domain) if part).strip()
    if not identity:
        return []
    queries = [
        {
            "provider": "Crunchbase",
            "query": f"{identity} Crunchbase organization founders funding stage investors headcount",
            "fields": ["funding_stage", "founders", "investors", "company_identity"],
        },
        {
            "provider": "Coresignal",
            "query": f"{identity} Coresignal company LinkedIn headcount employees website",
            "fields": ["headcount", "company_linkedin", "official_domain", "company_identity"],
        },
        {
            "provider": "LinkedIn",
            "query": f"{identity} LinkedIn company founders employees headcount",
            "fields": ["company_linkedin", "founders", "headcount"],
        },
    ]
    return queries[: max(1, queries_per_target)]


def _summarize_items(items: list[dict], *, max_items: int = 5) -> list[dict]:
    return [_compact_item(item) for item in items[:max_items] if isinstance(item, dict)]


def _append_unique(bucket: list[dict], item: dict) -> None:
    url = item.get("url") or ""
    if url and any(existing.get("url") == url for existing in bucket):
        return
    bucket.append(item)


def _structured_hints(items: list[dict]) -> dict:
    hints = {
        "funding_stage_candidates": [],
        "official_domain_candidates": [],
        "company_linkedin_candidates": [],
        "headcount_candidates": [],
        "founder_candidates": [],
    }
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        item = _compact_item(raw_item)
        blob = " ".join(
            str(raw_item.get(key) or "")
            for key in ("title", "snippet", "description", "url", "domain")
        ).lower()
        url = str(item.get("url") or "").lower()
        domain = str(item.get("domain") or "")
        if domain and domain not in {"crunchbase.com", "linkedin.com", "coresignal.com"}:
            _append_unique(hints["official_domain_candidates"], item)
        if "crunchbase.com/organization" in url or "dealroom.co" in url or any(term in blob for term in ("seed", "series a", "series b", "funding", "raised", "investors")):
            _append_unique(hints["funding_stage_candidates"], item)
        if "linkedin.com/company" in url:
            _append_unique(hints["company_linkedin_candidates"], item)
        if any(term in blob for term in ("headcount", "employees", "employee", "hiring", "jobs", "careers")):
            _append_unique(hints["headcount_candidates"], item)
        if any(term in blob for term in ("founder", "co-founder", "ceo", "cto")):
            _append_unique(hints["founder_candidates"], item)
    return {key: value[:5] for key, value in hints.items()}


def _hint_value(provider: str, field: str, value: str, *, source_url: str = "") -> dict:
    return {
        "provider": provider,
        "field": field,
        "value": value,
        "url": source_url,
        "source_url": source_url,
    }


def _merge_direct_hints(base_hints: dict, direct_results: dict) -> dict:
    hints = {key: list(value) for key, value in base_hints.items()}
    hints.setdefault("funding_stage_candidates", [])
    hints.setdefault("official_domain_candidates", [])
    hints.setdefault("company_linkedin_candidates", [])
    hints.setdefault("headcount_candidates", [])
    hints.setdefault("founder_candidates", [])
    for provider, result in direct_results.items():
        if not isinstance(result, dict) or result.get("skipped") or result.get("error"):
            continue
        source_url = str(result.get("source_url") or "")
        website = str(result.get("website") or result.get("official_url") or "")
        if website:
            hints["official_domain_candidates"].append(_hint_value(provider, "official_domain", _domain_from_url(website), source_url=website or source_url))
        company_linkedin = str(result.get("company_linkedin") or result.get("linkedin_url") or "")
        if company_linkedin:
            hints["company_linkedin_candidates"].append(_hint_value(provider, "company_linkedin", company_linkedin, source_url=company_linkedin))
        headcount = str(result.get("headcount") or result.get("employee_count") or result.get("employees") or "")
        if headcount:
            hints["headcount_candidates"].append(_hint_value(provider, "headcount", headcount, source_url=source_url))
        stage = str(result.get("stage") or result.get("funding_stage") or result.get("last_funding_round") or "")
        if stage:
            hints["funding_stage_candidates"].append(_hint_value(provider, "funding_stage", stage, source_url=source_url))
        for founder in result.get("founders") or result.get("founder_names") or []:
            value = str(founder or "").strip()
            if value:
                hints["founder_candidates"].append(_hint_value(provider, "founder", value, source_url=source_url))
    return {key: value[:5] for key, value in hints.items()}


def _run_direct_provider(
    provider: str,
    target: dict,
    *,
    env: dict[str, str],
    direct_provider_runner=None,
) -> dict:
    if provider != "Coresignal":
        return {"provider": provider, "skipped": True, "skip_reason": "direct_adapter_not_implemented"}
    if direct_provider_runner is not None:
        try:
            payload = direct_provider_runner(provider, target, env=env)
        except Exception as exc:
            return {"provider": provider, "error": str(exc)}
        if not isinstance(payload, dict):
            return {"provider": provider, "error": "direct_provider_runner_returned_non_dict"}
        return {"provider": provider, **payload}
    return {"provider": provider, **_run_coresignal_company_enrich(target, env=env)}


def _access_summary(env: dict[str, str] | None = None) -> tuple[list[str], list[str], dict]:
    if env is None:
        access = detect_enrichment_provider_access()
    else:
        exact_env = {**DIRECT_PROVIDER_KEYS, **env}
        access = detect_enrichment_provider_access(exact_env)
    summary = access.get("summary") or {}
    configured = [provider for provider in STRUCTURED_PROVIDERS if provider in (summary.get("configured") or [])]
    manual_mode = [provider for provider in STRUCTURED_PROVIDERS if provider in (summary.get("manual_mode") or [])]
    return configured, manual_mode, access


def build_structured_provider_trial(
    run_dir: Path | str,
    *,
    env: dict[str, str] | None = None,
    query_runner=run_query,
    direct_provider_runner=None,
    limit: int = 10,
    queries_per_target: int = 3,
    timeout_seconds: int = 45,
    max_runtime_seconds: int | None = None,
    target_source: str = "evidence_gap_queue",
    generated_at: str | None = None,
) -> dict:
    run_path = Path(run_dir)
    targets = _load_targets(run_path, target_source=target_source)
    selected = targets[:limit]
    direct_access, manual_mode, access = _access_summary(env)
    direct_env = {**DIRECT_PROVIDER_KEYS, **(env or {})}
    provider_status = "direct_provider_key_configured" if direct_access else "manual_mode_no_direct_key"

    rows = []
    queries_run = 0
    items_seen = 0
    errors = 0
    targets_with_hints = 0
    direct_provider_targets_enriched = 0
    stopped_early = False
    started_at = time.monotonic()

    for target in selected:
        if max_runtime_seconds is not None and time.monotonic() - started_at >= max_runtime_seconds:
            stopped_early = True
            break
        query_rows = []
        collected_items = []
        for query in build_provider_queries(target, queries_per_target=queries_per_target):
            if max_runtime_seconds is not None and time.monotonic() - started_at >= max_runtime_seconds:
                stopped_early = True
                break
            queries_run += 1
            try:
                payload = query_runner(
                    topic=query["query"],
                    sources="web",
                    lookback_days=365,
                    auto_resolve=True,
                    store=True,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                payload = {"items": [], "error": str(exc)}
            items = payload.get("items") or []
            if payload.get("error"):
                errors += 1
            items_seen += len(items)
            collected_items.extend(item for item in items if isinstance(item, dict))
            query_rows.append(
                {
                    **query,
                    "items_seen": len(items),
                    "top_items": _summarize_items(items),
                    "error": payload.get("error", ""),
                    "warnings": payload.get("warnings") or [],
                    "errors_by_source": payload.get("errors_by_source") or {},
                }
            )
        direct_results = {}
        for provider_name in direct_access:
            if provider_name not in STRUCTURED_PROVIDERS:
                continue
            result = _run_direct_provider(
                provider_name,
                target,
                env=direct_env,
                direct_provider_runner=direct_provider_runner,
            )
            direct_results[provider_name] = result
        if any(result and not result.get("skipped") and not result.get("error") for result in direct_results.values()):
            direct_provider_targets_enriched += 1
        hints = _merge_direct_hints(_structured_hints(collected_items), direct_results)
        if any(hints.values()):
            targets_with_hints += 1
        rows.append(
            {
                "name": target.get("name") or "",
                "domain": target.get("domain") or "",
                "source_lane": target.get("source_lane") or "",
                "missing_evidence": target.get("missing_evidence") or [],
                "recommended_next_step": target.get("recommended_next_step") or "",
                "provider_status": provider_status,
                "direct_provider_access": direct_access,
                "manual_mode_providers": manual_mode,
                "direct_provider_results": direct_results,
                "queries": query_rows,
                "structured_hints": hints,
                "policy": "Top-gap-only provider trial. Public/manual mode does not equal verified provider data unless a direct provider key is configured and used.",
            }
        )

    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_path),
        "policy": (
            "Run Coresignal/Crunchbase/LinkedIn-style checks only on top Evidence Gap rows. "
            "Use direct provider access when configured; otherwise store public/manual evidence hints and unresolved gaps."
        ),
        "summary": {
            "targets_considered": len(targets),
            "targets_enriched": len(rows),
            "target_source": target_source,
            "queries_run": queries_run,
            "items_seen": items_seen,
            "errors": errors,
            "direct_provider_access": direct_access,
            "manual_mode_providers": manual_mode,
            "direct_provider_targets_enriched": direct_provider_targets_enriched,
            "targets_with_structured_hints": targets_with_hints,
            "limit": limit,
            "queries_per_target": queries_per_target,
            "max_runtime_seconds": max_runtime_seconds,
            "stopped_early": stopped_early,
        },
        "source_access": access.get("summary", {}),
        "items": rows,
    }


def write_structured_provider_trial(
    run_dir: Path | str,
    *,
    output_name: str = DEFAULT_OUTPUT_NAME,
    env: dict[str, str] | None = None,
    query_runner=run_query,
    direct_provider_runner=None,
    limit: int = 10,
    queries_per_target: int = 3,
    timeout_seconds: int = 45,
    max_runtime_seconds: int | None = None,
    target_source: str = "evidence_gap_queue",
) -> dict:
    run_path = Path(run_dir)
    report = build_structured_provider_trial(
        run_path,
        env=env,
        query_runner=query_runner,
        direct_provider_runner=direct_provider_runner,
        limit=limit,
        queries_per_target=queries_per_target,
        timeout_seconds=timeout_seconds,
        max_runtime_seconds=max_runtime_seconds,
        target_source=target_source,
    )
    output_path = run_path / output_name
    output_path.write_text(json.dumps(report, indent=2))
    return {"output": str(output_path), "summary": report["summary"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run focused structured-provider/manual-mode trial on top Evidence Gap rows.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--queries-per-target", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--max-runtime-seconds", type=int, default=None)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--target-source", choices=("evidence_gap_queue", "partner_review_companies"), default="evidence_gap_queue")
    args = parser.parse_args()
    result = write_structured_provider_trial(
        args.run_dir,
        output_name=args.output_name,
        limit=args.limit,
        queries_per_target=args.queries_per_target,
        timeout_seconds=args.timeout_seconds,
        max_runtime_seconds=args.max_runtime_seconds,
        target_source=args.target_source,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
