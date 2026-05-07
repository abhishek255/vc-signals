#!/usr/bin/env python3
"""Enrichment cache for VC Signals — funding, headcount, founders, etc.

The cache is keyed by `_normalize_company_name` so display variants
("Anysphere (Cursor)" vs "anysphere") resolve to the same entry. Each
entry has a flat schema with `fetched_at` (ISO date) and the enriched
fields. Field absence = "researched, not found" (or never researched).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Re-use the existing normalizer from persistence
sys.path.insert(0, str(Path(__file__).parent))
from persistence import _normalize_company_name  # noqa: E402

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_TTL_DAYS = 14
ENRICHED_FIELDS = (
    "stage",
    "raised",
    "headcount",
    "founders",
    "founding_year",
    "lead_investor",
    "founder_github_activity",
)


def _cache_path(data_dir: Path) -> Path:
    return data_dir / "companies" / "enrichment_cache.json"


def load_enrichment_cache(data_dir: Path | None = None) -> dict:
    """Load the enrichment cache. Returns {} if missing or malformed."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = _cache_path(data_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        print(f"Warning: malformed JSON in {path}, starting empty", file=sys.stderr)
        return {}


def save_enrichment_cache(cache: dict, data_dir: Path | None = None) -> None:
    """Persist the enrichment cache to disk, creating dirs as needed."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = _cache_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))


def is_cache_fresh(
    entry: dict,
    ttl_days: int = DEFAULT_TTL_DAYS,
    *,
    now: date | None = None,
) -> bool:
    """True iff `entry["fetched_at"]` is within `ttl_days` of `now` (inclusive).

    Missing or malformed `fetched_at` → False (forces re-research).
    """
    raw = entry.get("fetched_at")
    if not raw:
        return False
    try:
        fetched = datetime.strptime(raw, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False
    today = now or datetime.now(timezone.utc).date()
    return (today - fetched).days <= ttl_days


def update_enrichment(
    cache: dict,
    name: str,
    fields: dict,
    *,
    evidence: dict | None = None,
    now: date | None = None,
) -> None:
    """Merge `fields` into the cache entry for `name`, refreshing `fetched_at`.

    - Keys the entry by `_normalize_company_name(name)` so display variants
      ("Anysphere (Cursor)" / "Anysphere") share one entry.
    - Rejects any field outside `ENRICHED_FIELDS` with `ValueError`.
    - `evidence` (if provided) is merged into the entry's evidence dict.
    """
    unknown = set(fields) - set(ENRICHED_FIELDS)
    if unknown:
        raise ValueError(f"unknown enrichment fields: {sorted(unknown)}")

    key = _normalize_company_name(name)
    entry = cache.setdefault(key, {})
    entry.update(fields)
    if evidence:
        entry.setdefault("evidence", {}).update(evidence)
    today = now or datetime.now(timezone.utc).date()
    entry["fetched_at"] = today.strftime("%Y-%m-%d")


def merge_into_company(company: dict, cache: dict) -> dict:
    """Return a copy of `company` with missing enrichment fields filled from cache."""
    out = company.copy()
    name = company.get("name")
    if not name:
        return out

    entry = cache.get(_normalize_company_name(name))
    if not entry:
        return out

    for field in ENRICHED_FIELDS:
        if not out.get(field) and entry.get(field):
            out[field] = entry[field]
    return out


def _read_json_stdin():
    raw = sys.stdin.read()
    if not raw.strip():
        return None, {"error": "No data piped to stdin."}
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, {"error": f"Invalid JSON on stdin: {exc.msg}"}


def _parse_cli_args(argv: list[str]) -> dict:
    args = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:].replace("-", "_")
            if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
                args[key] = True
                i += 1
            else:
                args[key] = argv[i + 1]
                i += 2
        else:
            i += 1
    return args


def _cli_date(args: dict) -> date | None:
    raw = args.get("date")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"Invalid date: '{raw}'. Expected YYYY-MM-DD.")


def _cli_main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: enrichment.py <command> [args]"}))
        return

    command = sys.argv[1]
    args = _parse_cli_args(sys.argv[2:])
    data_dir = Path(args["data_dir"]) if "data_dir" in args else DEFAULT_DATA_DIR

    if command == "load-cache":
        print(json.dumps(load_enrichment_cache(data_dir)))
        return

    if command == "update":
        payload, error = _read_json_stdin()
        if error:
            print(json.dumps(error))
            return
        if not isinstance(payload, dict):
            print(json.dumps({"error": "stdin payload must be an object"}))
            return
        name = payload.get("name")
        fields = payload.get("fields")
        if not name or not isinstance(fields, dict):
            print(json.dumps({"error": "stdin payload must include name and fields object"}))
            return

        cache = load_enrichment_cache(data_dir)
        try:
            update_enrichment(
                cache,
                name,
                fields,
                evidence=payload.get("evidence"),
                now=_cli_date(args),
            )
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            return
        save_enrichment_cache(cache, data_dir)
        key = _normalize_company_name(name)
        print(json.dumps({"updated": key, "entry": cache[key]}))
        return

    if command == "merge":
        payload, error = _read_json_stdin()
        if error:
            print(json.dumps(error))
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("companies"), list):
            print(json.dumps({"error": "stdin payload must be an object with companies list"}))
            return
        cache = load_enrichment_cache(data_dir)
        companies = [merge_into_company(company, cache) for company in payload["companies"]]
        print(json.dumps({"companies": companies}))
        return

    print(json.dumps({"error": f"Unknown command: {command}"}))


if __name__ == "__main__":
    _cli_main()
