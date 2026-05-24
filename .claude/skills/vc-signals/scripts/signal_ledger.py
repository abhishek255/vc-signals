#!/usr/bin/env python3
"""Build and update the persistent VC Signals company/signal ledger."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parent.parent.parent
DEFAULT_RUNS_ROOT = REPO_ROOT / "docs" / "radar-runs"
DEFAULT_LEDGER_PATH = SKILL_DIR / "data" / "radar_runs" / "company_signal_ledger.json"
DEFAULT_REPORT_DIR = DEFAULT_RUNS_ROOT / "current-signal-ledger-backfill-2026-05-24"

WEEKLY_FOCUS_SECTIONS = (
    "partner_focus",
    "sourcing_candidates",
    "research_deeper_queue",
    "extended_watchlist",
    "oss_project_watch",
    "new_to_marathon",
)
JSON_ITEM_FILES = (
    "owner-readiness.json",
    "owner-evidence.json",
    "founder-team-verification.json",
    "main-owner-readiness.json",
    "main-owner-evidence.json",
    "main-founder-team.json",
)
HN_ROW_FILES = (
    "hn-launch-trial/hn-trial-row-review.json",
    "hn-completion/hn-trial-row-review.json",
)
ACTION_RANK = {
    "": 0,
    "Rejected": 0,
    "Passed": 0,
    "Monitor only": 1,
    "Watch OSS": 1,
    "Contact maintainer": 1,
    "Research deeper": 2,
    "Assign owner": 3,
}
SOURCE_LANE_ORDER = ("HN", "YC", "web", "OSS", "GitHub", "Attio")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _clean_string(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_domain(value: str) -> str:
    value = _clean_string(value).lower()
    if not value:
        return ""
    if "://" in value:
        parsed = urlparse(value)
        value = parsed.netloc or parsed.path
    value = value.removeprefix("www.")
    value = value.split("/", 1)[0].split("?", 1)[0].strip()
    if value.startswith("company:"):
        value = value.split(":", 1)[1]
    return value


def _url_host(url: str) -> str:
    parsed = urlparse(_clean_string(url))
    return parsed.netloc.lower().removeprefix("www.")


def _github_project_key(url: str) -> str:
    parsed = urlparse(_clean_string(url))
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [part for part in parsed.path.split("/") if part]
    if host == "github.com" and len(parts) >= 2:
        return f"github.com/{parts[0]}/{parts[1]}".lower()
    return ""


def _extract_date(run_id: str) -> str:
    match = re.search(r"20\d{2}-\d{2}-\d{2}", run_id)
    return match.group(0) if match else ""


def _unique(values) -> list[str]:
    seen = set()
    result = []
    for value in values or []:
        text = _clean_string(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _ordered_lanes(values) -> list[str]:
    lanes = set(_unique(values))
    ordered = [lane for lane in SOURCE_LANE_ORDER if lane in lanes]
    ordered.extend(sorted(lanes - set(ordered)))
    return ordered


def _json_items(payload) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _all_urls(value) -> list[str]:
    urls = []
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            urls.append(value)
    elif isinstance(value, dict):
        for key, nested in value.items():
            if key in {"url", "source_url", "homepage", "identity_url", "outbound_url", "linkedin", "x"}:
                urls.extend(_all_urls(nested))
            elif isinstance(nested, (dict, list)):
                urls.extend(_all_urls(nested))
    elif isinstance(value, list):
        for item in value:
            urls.extend(_all_urls(item))
    return urls


def _urls_from_row(row: dict) -> list[str]:
    urls = []
    for key in (
        "evidence_urls",
        "maturity_evidence_urls",
        "source_outbound_urls",
        "new_evidence_this_week",
        "founder_team_evidence",
        "stage_funding_evidence",
        "customer_buyer_evidence",
        "customer_buyer_pull_evidence",
        "source",
        "url",
        "project_url",
        "movement_assignment_evidence_url",
    ):
        urls.extend(_all_urls(row.get(key)))
    for item in row.get("evidence_metadata") or []:
        if isinstance(item, dict):
            urls.extend(_all_urls(item))
    urls.extend(_all_urls(row.get("assign_owner_evidence_provenance")))
    return _unique(urls)


def _domain_from_row(row: dict) -> str:
    for key in ("domain", "company_domain", "candidate_domain"):
        domain = normalize_domain(row.get(key, ""))
        if domain:
            return domain
    for key in ("id", "candidate_key", "stable_key"):
        value = _clean_string(row.get(key))
        if value.startswith("company:"):
            domain = normalize_domain(value)
            if domain:
                return domain
        if "." in value and "/" not in value and ":" not in value:
            domain = normalize_domain(value)
            if domain:
                return domain
    return ""


def _project_key_from_row(row: dict) -> str:
    for key in ("project_url", "source", "url"):
        project = _github_project_key(row.get(key, ""))
        if project:
            return project
    for key in ("id", "candidate_key", "stable_key", "source_candidate_id"):
        value = _clean_string(row.get(key))
        if value.startswith(("repo:", "project:")):
            value = value.split(":", 1)[1]
            return value.lower()
    return ""


def _entity_id(row: dict) -> str:
    domain = _domain_from_row(row)
    if domain:
        return f"company:{domain}"
    project = _project_key_from_row(row)
    if project:
        return f"project:{project}"
    name = _clean_string(row.get("name") or row.get("canonical_name") or row.get("display_name"))
    return f"entity:{_slug(name) or 'unknown'}"


def _name_from_row(row: dict) -> str:
    return _clean_string(row.get("name") or row.get("canonical_name") or row.get("display_name") or row.get("id"))


def _is_market_anchor(row: dict, action: str, route: str) -> bool:
    maturity = _clean_string(row.get("maturity_status")).lower()
    return (
        bool(row.get("category_anchor"))
        or route == "Category Context"
        or action == "Monitor only"
        or maturity in {"likely_too_late", "acquired", "incumbent", "category_leader"}
        or "category_context" in _clean_string(row.get("query_status")).lower()
    )


def _is_project(row: dict) -> bool:
    identity = _clean_string(row.get("identity_type")).lower()
    lane = _clean_string(row.get("source_lane")).lower()
    return (
        identity == "oss_project_watch"
        or "oss" in lane
        or bool(_project_key_from_row(row))
    )


def _entity_type(row: dict, action: str, route: str) -> str:
    if _is_market_anchor(row, action, route):
        return "market anchor"
    if _is_project(row):
        return "project"
    if _domain_from_row(row):
        return "company"
    return "product/context"


def _normal_action(raw: str) -> str:
    value = _clean_string(raw).lower().replace("_", " ")
    if not value:
        return ""
    if "assign owner" in value:
        return "Assign owner"
    if "monitor only" in value or value in {"monitor"}:
        return "Monitor only"
    if "contact maintainer" in value:
        return "Contact maintainer"
    if "oss" in value and "watch" in value:
        return "Watch OSS"
    if "research deeper" in value or "find " in value:
        return "Research deeper"
    if "too late" in value:
        return "Monitor only"
    if "reject" in value:
        return "Rejected"
    if "pass" in value:
        return "Passed"
    return raw[:1].upper() + raw[1:]


def _action_from_row(row: dict) -> str:
    for key in ("final_action", "recommended_action", "recommended_owner_action", "action"):
        action = _normal_action(row.get(key, ""))
        if action:
            return action
    return ""


def _route_from_row(row: dict, action: str) -> str:
    lead_route = _clean_string(row.get("lead_route")).lower()
    query_status = _clean_string(row.get("query_status")).lower()
    identity = _clean_string(row.get("identity_type")).lower()
    if action == "Assign owner":
        return "Assign Owner"
    if _is_market_anchor(row, action, ""):
        return "Category Context"
    if action == "Rejected":
        return "Rejected"
    if action == "Passed":
        return "Passed"
    if "oss" in identity or _is_project(row):
        return "OSS Watch"
    if "category_context" in lead_route or "category_context" in query_status:
        return "Category Context"
    if "research" in lead_route or action == "Research deeper":
        return "Research Deeper"
    if action == "Monitor only":
        return "Category Context"
    return "Research Deeper" if action else "Observed"


def _evidence_dimensions(row: dict) -> dict[str, bool]:
    explicit = {str(item).lower() for item in row.get("evidence_dimensions") or []}
    provenance = row.get("assign_owner_evidence_provenance") or {}
    owner_basis = {str(item).lower() for item in row.get("owner_readiness_basis") or []}
    identity = (
        bool(_domain_from_row(row))
        or _clean_string(row.get("identity_type")).lower() == "verified_company"
        or "verified_company_identity" in owner_basis
    )
    founder = bool(row.get("founder_team_evidence") or row.get("founder_profiles") or row.get("founders_found"))
    founder = founder or "founder" in explicit or bool((provenance.get("founder_evidence") or {}).get("url"))
    stage = bool(row.get("stage_funding_evidence"))
    stage = stage or "stage" in explicit or bool((provenance.get("stage_funding_evidence") or {}).get("url"))
    customer = bool(
        row.get("customer_buyer_evidence")
        or row.get("customer_buyer_pull_evidence")
        or row.get("customer_buyer_evidence_types")
    )
    customer = customer or "customer" in explicit or "commercial" in explicit
    customer = customer or bool((provenance.get("commercial_customer_evidence") or {}).get("url"))
    return {
        "identity": bool(identity),
        "founder": bool(founder),
        "stage": bool(stage),
        "customer_commercial": bool(customer),
    }


def _source_lanes(row: dict, urls: list[str]) -> list[str]:
    lanes = []
    raw_lane = _clean_string(row.get("source_lane"))
    if raw_lane:
        if raw_lane.lower() in {"grounded web", "web", "grounding"}:
            lanes.append("web")
        elif "oss" in raw_lane.lower():
            lanes.append("OSS")
        elif "hn" in raw_lane.lower() or "hacker" in raw_lane.lower():
            lanes.append("HN")
        else:
            lanes.append(raw_lane)
    for url in urls:
        host = _url_host(url)
        if host == "news.ycombinator.com":
            lanes.append("HN")
        elif host == "www.ycombinator.com" or host == "ycombinator.com":
            lanes.append("YC")
        elif host == "github.com":
            lanes.append("OSS")
        elif host:
            lanes.append("web")
    return _ordered_lanes(lanes)


def _missing_from_row(row: dict) -> list[str]:
    for key in (
        "missing_evidence",
        "missing_owner_evidence",
        "missing_founder_evidence",
        "stage_failure_reason",
    ):
        if key in row:
            return _unique(row.get(key))
    return []


def _sighting_from_row(row: dict, *, run_dir: Path, source_file: str, raw_kind: str) -> dict:
    action = _action_from_row(row)
    route = _route_from_row(row, action)
    urls = _urls_from_row(row)
    entity_id = _entity_id(row)
    domain = _domain_from_row(row)
    project = _project_key_from_row(row)
    return {
        "entity_id": entity_id,
        "name": _name_from_row(row),
        "domain": domain,
        "project_key": project,
        "entity_type": _entity_type(row, action, route),
        "run_id": run_dir.name,
        "run_date": _extract_date(run_dir.name),
        "artifact_path": str(run_dir),
        "source_file": source_file,
        "raw_kind": raw_kind,
        "route": route,
        "action": action or "Observed",
        "attio_status": _clean_string(row.get("attio_status")),
        "attio_owner": _clean_string(row.get("attio_owner")),
        "attio_action": _clean_string(row.get("attio_action")),
        "source_lanes": _source_lanes(row, urls),
        "evidence_dimensions": _evidence_dimensions(row),
        "missing_evidence": _missing_from_row(row),
        "evidence_urls": urls,
        "owner_readiness_score": row.get("owner_readiness_score"),
        "completion_status": _clean_string(row.get("completion_status")),
        "unsafe_promotion": bool(row.get("unsafe_promotion", False)),
    }


def _merge_run_sighting(existing: dict, new: dict) -> dict:
    merged = dict(existing)
    for key in ("name", "domain", "project_key", "entity_type", "route", "action", "source_file", "raw_kind"):
        if new.get(key):
            merged[key] = new[key]
    for key in ("attio_status", "attio_owner", "attio_action", "completion_status"):
        if new.get(key):
            merged[key] = new[key]
    if "owner_readiness_score" in new and new.get("owner_readiness_score") is not None:
        merged["owner_readiness_score"] = new.get("owner_readiness_score")
    merged["unsafe_promotion"] = bool(existing.get("unsafe_promotion")) or bool(new.get("unsafe_promotion"))
    merged["source_lanes"] = _ordered_lanes((existing.get("source_lanes") or []) + (new.get("source_lanes") or []))
    merged["evidence_urls"] = _unique((existing.get("evidence_urls") or []) + (new.get("evidence_urls") or []))
    merged["missing_evidence"] = list(new.get("missing_evidence", existing.get("missing_evidence") or []))
    old_dims = existing.get("evidence_dimensions") or {}
    new_dims = new.get("evidence_dimensions") or {}
    merged["evidence_dimensions"] = {
        "identity": bool(old_dims.get("identity") or new_dims.get("identity")),
        "founder": bool(old_dims.get("founder") or new_dims.get("founder")),
        "stage": bool(old_dims.get("stage") or new_dims.get("stage")),
        "customer_commercial": bool(old_dims.get("customer_commercial") or new_dims.get("customer_commercial")),
    }
    return merged


def iter_run_sightings(run_dir: Path) -> list[dict]:
    sightings_by_entity: dict[str, dict] = {}

    def add(row: dict, source_file: str, raw_kind: str) -> None:
        sighting = _sighting_from_row(row, run_dir=run_dir, source_file=source_file, raw_kind=raw_kind)
        entity_id = sighting["entity_id"]
        if entity_id in sightings_by_entity:
            sightings_by_entity[entity_id] = _merge_run_sighting(sightings_by_entity[entity_id], sighting)
        else:
            sightings_by_entity[entity_id] = sighting

    candidates = _read_json(run_dir / "candidates.json")
    for row in _json_items(candidates):
        add(row, "candidates.json", "candidate")

    weekly_focus = _read_json(run_dir / "weekly-focus.json")
    if isinstance(weekly_focus, dict):
        for section in WEEKLY_FOCUS_SECTIONS:
            for row in weekly_focus.get(section) or []:
                if isinstance(row, dict):
                    enriched = dict(row)
                    enriched.setdefault("lead_route", section)
                    add(enriched, "weekly-focus.json", section)

    for filename in JSON_ITEM_FILES:
        payload = _read_json(run_dir / filename)
        for row in _json_items(payload):
            add(row, filename, filename.removesuffix(".json"))

    for filename in HN_ROW_FILES:
        payload = _read_json(run_dir / filename)
        if isinstance(payload, dict):
            for row in payload.get("rows") or []:
                if isinstance(row, dict):
                    add(row, filename, "hn_row_review")

    return list(sightings_by_entity.values())


def _status_movement(history: list[dict]) -> str:
    if not history:
        return "new"
    latest = history[-1]
    if latest.get("route") == "Rejected" or latest.get("action") == "Rejected":
        return "rejected"
    latest_rank = ACTION_RANK.get(latest.get("action", ""), 0)
    prior_ranks = [ACTION_RANK.get(item.get("action", ""), 0) for item in history[:-1]]
    if not prior_ranks:
        return "new"
    best_prior = max(prior_ranks)
    if latest_rank < best_prior:
        return "demoted"
    if latest_rank > min(prior_ranks):
        return "promoted"
    if len(history) > 1:
        return "repeated"
    return "new"


def _entity_from_history(entity_id: str, history: list[dict]) -> dict:
    history = sorted(
        history,
        key=lambda item: (
            item.get("run_date", ""),
            int(item.get("run_sequence", 0) or 0),
            item.get("run_id", ""),
            item.get("source_file", ""),
        ),
    )
    first = history[0]
    latest = history[-1]
    best = max(history, key=lambda item: ACTION_RANK.get(item.get("action", ""), 0))
    attio_history = [
        {
            "run_id": item.get("run_id", ""),
            "run_date": item.get("run_date", ""),
            "status": item.get("attio_status", ""),
            "action": item.get("attio_action", ""),
            "owner": item.get("attio_owner", ""),
        }
        for item in history
        if item.get("attio_status")
    ]
    attio_current = next((item["status"] for item in reversed(attio_history) if item.get("status")), "unknown")
    return {
        "entity_id": entity_id,
        "name": latest.get("name") or first.get("name") or entity_id,
        "domain": latest.get("domain") or first.get("domain") or "",
        "entity_type": latest.get("entity_type") or first.get("entity_type") or "product/context",
        "first_seen_run": first.get("run_id", ""),
        "first_seen_date": first.get("run_date", ""),
        "last_seen_run": latest.get("run_id", ""),
        "last_seen_date": latest.get("run_date", ""),
        "sightings_count": len(history),
        "source_lanes_seen": _ordered_lanes(lane for item in history for lane in item.get("source_lanes", [])),
        "current_route": latest.get("route", "Observed"),
        "current_action": latest.get("action", "Observed"),
        "best_historical_action": best.get("action", "Observed"),
        "attio_status_history": attio_history,
        "attio_status_current": attio_current,
        "evidence_dimensions": latest.get("evidence_dimensions") or {
            "identity": False,
            "founder": False,
            "stage": False,
            "customer_commercial": False,
        },
        "missing_evidence": latest.get("missing_evidence") or [],
        "latest_evidence_urls": latest.get("evidence_urls") or [],
        "status_movement": _status_movement(history),
        "sighting_history": history,
    }


def _ambiguous_merges(entities: list[dict]) -> list[dict]:
    by_name: dict[str, list[dict]] = defaultdict(list)
    for entity in entities:
        key = _slug(entity.get("name", ""))
        if key:
            by_name[key].append(entity)
    ambiguous = []
    for _name_key, matches in by_name.items():
        ids = sorted({match["entity_id"] for match in matches})
        if len(ids) <= 1:
            continue
        ambiguous.append(
            {
                "name": matches[0].get("name", ""),
                "reason": "same_name_different_entity_ids",
                "entity_ids": ids,
            }
        )
    return ambiguous


def _ledger_from_sightings(sightings: list[dict], *, generated_at: str) -> dict:
    deduped: dict[tuple[str, str], dict] = {}
    for sighting in sightings:
        key = (sighting["entity_id"], sighting.get("run_id", ""))
        if key in deduped:
            deduped[key] = _merge_run_sighting(deduped[key], sighting)
        else:
            deduped[key] = sighting
    by_entity: dict[str, list[dict]] = defaultdict(list)
    for sighting in deduped.values():
        by_entity[sighting["entity_id"]].append(sighting)
    entities = [_entity_from_history(entity_id, history) for entity_id, history in sorted(by_entity.items())]
    route_counts = Counter(entity["current_route"] for entity in entities)
    action_counts = Counter(entity["current_action"] for entity in entities)
    runs = {}
    for sighting in deduped.values():
        run_id = sighting.get("run_id", "")
        runs.setdefault(
            run_id,
            {
                "run_id": run_id,
                "run_date": sighting.get("run_date", ""),
                "run_sequence": int(sighting.get("run_sequence", 0) or 0),
                "path": sighting.get("artifact_path", ""),
                "sightings": 0,
            },
        )
        runs[run_id]["sightings"] += 1
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "runs_backfilled": sorted(
            runs.values(),
            key=lambda item: (int(item.get("run_sequence", 0) or 0), item.get("run_date", ""), item.get("run_id", "")),
        ),
        "summary": {
            "entities": len(entities),
            "sightings": len(deduped),
            "current_routes": dict(sorted(route_counts.items())),
            "current_actions": dict(sorted(action_counts.items())),
            "assign_owner_entities": sum(1 for entity in entities if entity["current_action"] == "Assign owner"),
            "unsafe_promotions": sum(
                1
                for entity in entities
                for item in entity.get("sighting_history", [])
                if item.get("unsafe_promotion")
            ),
        },
        "entities": entities,
        "ambiguous_merges": _ambiguous_merges(entities),
    }


def build_company_signal_ledger(run_dirs: list[Path], *, generated_at: str | None = None) -> dict:
    sightings = []
    for index, run_dir in enumerate(run_dirs):
        for sighting in iter_run_sightings(Path(run_dir)):
            sighting["run_sequence"] = index
            sightings.append(sighting)
    return _ledger_from_sightings(sightings, generated_at=generated_at or _now_iso())


def _sightings_from_existing_ledger(ledger: dict) -> list[dict]:
    sightings = []
    for entity in ledger.get("entities", []):
        for index, item in enumerate(entity.get("sighting_history", [])):
            sighting = dict(item)
            sighting.setdefault("run_sequence", index)
            sighting.setdefault("entity_id", entity.get("entity_id", ""))
            sighting.setdefault("name", entity.get("name", ""))
            sighting.setdefault("domain", entity.get("domain", ""))
            sighting.setdefault("entity_type", entity.get("entity_type", ""))
            if sighting.get("entity_id"):
                sightings.append(sighting)
    return sightings


def update_signal_ledger_from_run(
    *,
    run_dir: Path,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    generated_at: str | None = None,
) -> dict:
    existing = _read_json(ledger_path) if Path(ledger_path).exists() else None
    sightings = _sightings_from_existing_ledger(existing or {})
    next_sequence = len({item.get("run_id") for item in sightings})
    for sighting in iter_run_sightings(Path(run_dir)):
        sighting["run_sequence"] = next_sequence
        sightings.append(sighting)
    ledger = _ledger_from_sightings(sightings, generated_at=generated_at or _now_iso())
    write_ledger(ledger, Path(ledger_path))
    return {
        "ledger": str(ledger_path),
        "entities": ledger["summary"]["entities"],
        "sightings": ledger["summary"]["sightings"],
    }


def write_ledger(ledger: dict, path: Path = DEFAULT_LEDGER_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True))
    return path


def _has_usable_outputs(run_dir: Path) -> bool:
    files = [
        "candidates.json",
        "weekly-focus.json",
        "owner-readiness.json",
        "main-owner-readiness.json",
        "hn-launch-trial/hn-trial-row-review.json",
        "hn-completion/hn-trial-row-review.json",
    ]
    return any((run_dir / file).exists() for file in files)


def _artifact_priority(name: str) -> int:
    if name.startswith("current-weekly-hn-default-runtime-patch"):
        return 95
    if name.startswith("current-weekly-hn-default-timeout90"):
        return 90
    if name.startswith("current-weekly-hn-default-validation"):
        return 85
    if name.startswith("current-weekly-hn-default-partner-review"):
        return 80
    if name.startswith("current-weekly-post-last30days-alignment"):
        return 75
    if name.startswith("current-weekly"):
        return 70
    if name.startswith("current-founder-stage"):
        return 60
    if name.startswith("current-owner-maturity"):
        return 55
    if name.startswith("current-all-sector-clean"):
        return 50
    if "validation" in name:
        return 40
    return 10


def _sort_latest(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: (_extract_date(path.name), _artifact_priority(path.name), path.name), reverse=True)


def discover_backfill_artifacts(runs_root: Path = DEFAULT_RUNS_ROOT, *, limit: int = 10) -> list[Path]:
    runs_root = Path(runs_root)
    candidates = [path for path in runs_root.iterdir() if path.is_dir() and path.name.startswith("current-") and _has_usable_outputs(path)]
    selected: list[Path] = []

    def add(paths: list[Path], cap: int) -> None:
        for path in _sort_latest(paths):
            if path not in selected and len([item for item in selected if item in paths]) < cap:
                selected.append(path)

    add([path for path in candidates if path.name.startswith("current-weekly")], 5)
    add([path for path in candidates if path.name.startswith("current-founder-stage")], 1)
    add([path for path in candidates if path.name.startswith("current-owner-maturity")], 2)
    add([path for path in candidates if path.name.startswith("current-all-sector-clean")], 2)
    for path in _sort_latest([path for path in candidates if path not in selected and "validation" in path.name]):
        if len(selected) >= limit:
            break
        selected.append(path)

    selected = selected[:limit]
    return sorted(selected, key=lambda path: (_extract_date(path.name), _artifact_priority(path.name), path.name))


def write_backfill_report(ledger: dict, report_dir: Path = DEFAULT_REPORT_DIR) -> Path:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "README.md"
    assign_owner = [entity for entity in ledger["entities"] if entity["current_action"] == "Assign owner"]
    research_deeper = [entity for entity in ledger["entities"] if entity["current_route"] == "Research Deeper"]
    category_context = [entity for entity in ledger["entities"] if entity["current_route"] == "Category Context"]
    lines = [
        "# Signal Ledger Backfill",
        "",
        f"Generated: {ledger.get('generated_at', '')}",
        "",
        "## Summary",
        "",
        f"- Entities: {ledger['summary']['entities']}",
        f"- Sightings: {ledger['summary']['sightings']}",
        f"- Assign Owner entities: {ledger['summary']['assign_owner_entities']}",
        f"- Unsafe promotions: {ledger['summary']['unsafe_promotions']}",
        "",
        "## Artifacts Processed",
        "",
    ]
    for run in ledger.get("runs_backfilled", []):
        lines.append(f"- {run['run_id']} ({run.get('sightings', 0)} sightings)")
    lines.extend(["", "## Current Assign Owner", ""])
    if assign_owner:
        for entity in assign_owner:
            lines.append(f"- {entity['name']} ({entity['entity_id']})")
    else:
        lines.append("- None")
    lines.extend(["", "## Research Deeper Missing Evidence", ""])
    for entity in research_deeper[:25]:
        missing = ", ".join(entity.get("missing_evidence") or ["none listed"])
        lines.append(f"- {entity['name']}: {missing}")
    if not research_deeper:
        lines.append("- None")
    lines.extend(["", "## Category Context / Too Late", ""])
    for entity in category_context[:25]:
        lines.append(f"- {entity['name']} ({entity['entity_id']}): {entity['current_action']}")
    if not category_context:
        lines.append("- None")
    lines.extend(["", "## Ambiguous Non-Merges", ""])
    if ledger.get("ambiguous_merges"):
        for item in ledger["ambiguous_merges"]:
            lines.append(f"- {item['name']}: {', '.join(item['entity_ids'])} ({item['reason']})")
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n")
    return path


def backfill_recent_artifacts(
    *,
    runs_root: Path = DEFAULT_RUNS_ROOT,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    report_dir: Path = DEFAULT_REPORT_DIR,
    limit: int = 10,
    generated_at: str | None = None,
) -> dict:
    artifacts = discover_backfill_artifacts(runs_root, limit=limit)
    ledger = build_company_signal_ledger(artifacts, generated_at=generated_at)
    ledger_out = write_ledger(ledger, ledger_path)
    report_out = write_backfill_report(ledger, report_dir)
    return {
        "ledger": str(ledger_out),
        "report": str(report_out),
        "artifacts": [str(path) for path in artifacts],
        "entities": ledger["summary"]["entities"],
        "sightings": ledger["summary"]["sightings"],
    }


def _parse_args(argv: list[str]) -> dict:
    args = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:].replace("-", "_")
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                args[key] = argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            args.setdefault("_positional", []).append(argv[i])
            i += 1
    return args


def _cli_main() -> None:
    args = _parse_args(sys.argv[1:])
    command = (args.get("_positional") or ["backfill"])[0]
    if command != "backfill":
        print(json.dumps({"error": f"Unknown command: {command}"}))
        return
    result = backfill_recent_artifacts(
        runs_root=Path(args.get("runs_root", DEFAULT_RUNS_ROOT)),
        ledger_path=Path(args.get("ledger_path", DEFAULT_LEDGER_PATH)),
        report_dir=Path(args.get("report_dir", DEFAULT_REPORT_DIR)),
        limit=int(args.get("limit", 10)),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli_main()
