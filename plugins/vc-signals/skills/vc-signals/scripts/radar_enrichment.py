from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from enrichment import DEFAULT_DATA_DIR, DEFAULT_TTL_DAYS, is_cache_fresh, load_enrichment_cache
from persistence import _normalize_company_name
from radar_models import Candidate


ENRICHMENT_FIELDS = ("stage", "raised", "headcount", "founders", "founding_year", "lead_investor")


def candidate_cache_key(candidate: Candidate) -> str:
    return _normalize_company_name(candidate.name)


def load_fresh_enrichment_cache(
    *,
    data_dir: Path | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    now: date | None = None,
) -> dict:
    cache = load_enrichment_cache(data_dir or DEFAULT_DATA_DIR)
    return {
        key: entry
        for key, entry in cache.items()
        if isinstance(entry, dict) and is_cache_fresh(entry, ttl_days=ttl_days, now=now)
    }


def merge_source_enrichment(candidate: Candidate, source_metadata: dict) -> Candidate:
    """Merge structured source fields only when field-level evidence exists."""
    evidence = source_metadata.get("evidence") or source_metadata.get("enrichment_evidence") or {}
    for field in ENRICHMENT_FIELDS:
        value = source_metadata.get(field)
        if not value or not evidence.get(field) or getattr(candidate, field):
            continue
        setattr(candidate, field, value)
        candidate.enrichment_evidence[field] = evidence[field]
    return candidate


def merge_cached_enrichment(candidate: Candidate, cache: dict) -> Candidate:
    entry = cache.get(candidate_cache_key(candidate))
    if not isinstance(entry, dict):
        return candidate
    evidence = entry.get("evidence") or {}
    for field in ENRICHMENT_FIELDS:
        value = entry.get(field)
        if not value or not evidence.get(field) or getattr(candidate, field):
            continue
        setattr(candidate, field, value)
        candidate.enrichment_evidence[field] = evidence[field]
    return candidate


def merge_attio_enrichment(candidate: Candidate, attributes: dict) -> Candidate:
    mappings = {
        "stage": attributes.get("last_round_type"),
        "raised": attributes.get("total_amount_raised"),
        "headcount": attributes.get("headcount") or attributes.get("employee_range"),
    }
    for field, value in mappings.items():
        if value and not getattr(candidate, field):
            setattr(candidate, field, str(value))
            candidate.enrichment_evidence[field] = "attio"
    return candidate


def apply_candidate_enrichment(
    candidates: list[Candidate],
    *,
    cache: dict | None = None,
    data_dir: Path | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    now: date | None = None,
) -> list[Candidate]:
    today = now or datetime.now(timezone.utc).date()
    source_cache = cache if cache is not None else load_enrichment_cache(data_dir or DEFAULT_DATA_DIR)
    fresh_cache = {
        key: entry
        for key, entry in source_cache.items()
        if isinstance(entry, dict) and is_cache_fresh(entry, ttl_days=ttl_days, now=today)
    }
    return [merge_cached_enrichment(candidate, fresh_cache) for candidate in candidates]
