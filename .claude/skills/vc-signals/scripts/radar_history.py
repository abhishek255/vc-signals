from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from radar_models import Candidate

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
PERSISTENT_WEEKS = 2
RETURNING_AFTER_MISSED_WEEKS = 2


@dataclass
class HistoryResult:
    candidates: list[Candidate]
    faded: list[dict]
    history: dict


def _normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.split("/", 1)[0]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def stable_candidate_key(candidate: Candidate) -> str:
    domain = _normalize_domain(candidate.domain)
    if domain:
        return f"company:{domain}"

    parsed = urlparse(candidate.source or "")
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [part for part in parsed.path.split("/") if part]
    if host == "github.com" and len(parts) >= 2:
        return f"repo:{host}/{parts[0]}/{parts[1]}".lower()

    return f"candidate:{_slug(candidate.sector)}:{_slug(candidate.name)}"


def _history_path(data_dir: Path) -> Path:
    return data_dir / "companies" / "candidate_history.json"


def load_candidate_history(data_dir: Path | None = None) -> dict:
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = _history_path(data_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_candidate_history(history: dict, data_dir: Path | None = None) -> None:
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = _history_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2))


def _weeks_between(later: str, earlier: str) -> int:
    later_dt = datetime.strptime(later, "%Y-%m-%d")
    earlier_dt = datetime.strptime(earlier, "%Y-%m-%d")
    return max(0, (later_dt - earlier_dt).days // 7)


def apply_weekly_tags(candidates: list[Candidate], history: dict, *, run_date: str) -> HistoryResult:
    current_keys = set()
    tagged = []

    for candidate in candidates:
        key = stable_candidate_key(candidate)
        current_keys.add(key)
        candidate.stable_key = key
        previous = history.get(key)

        if previous is None:
            candidate.weekly_tag = "NEW"
            weeks_seen = 1
            first_seen = run_date
        elif previous.get("last_seen") == run_date:
            weeks_seen = int(previous.get("weeks_seen") or 1)
            first_seen = previous.get("first_seen", run_date)
            candidate.weekly_tag = previous.get("last_tag") or ("NEW" if first_seen == run_date else "PERSISTENT")
        else:
            missed = _weeks_between(run_date, previous.get("last_seen", run_date)) - 1
            weeks_seen = int(previous.get("weeks_seen") or 0) + 1
            first_seen = previous.get("first_seen", run_date)
            if missed >= RETURNING_AFTER_MISSED_WEEKS:
                candidate.weekly_tag = "RETURNING"
            elif weeks_seen >= PERSISTENT_WEEKS:
                candidate.weekly_tag = "PERSISTENT"
            else:
                candidate.weekly_tag = ""

        history[key] = {
            "display_name": candidate.name,
            "first_seen": first_seen,
            "last_seen": run_date,
            "weeks_seen": weeks_seen,
            "missed_weeks": 0,
            "sectors": sorted(set((previous or {}).get("sectors", []) + [candidate.sector])),
            "themes": sorted(set((previous or {}).get("themes", []) + [candidate.theme])),
            "last_source": candidate.source,
            "last_tag": candidate.weekly_tag,
        }
        tagged.append(candidate)

    faded = []
    for key, entry in history.items():
        if key in current_keys:
            continue
        missed_weeks = _weeks_between(run_date, entry.get("last_seen", run_date))
        entry["missed_weeks"] = missed_weeks
        if missed_weeks == 1:
            faded.append({
                "stable_key": key,
                "name": entry.get("display_name", ""),
                "sector": (entry.get("sectors") or [""])[0],
                "theme": (entry.get("themes") or [""])[0],
                "last_seen": entry.get("last_seen", ""),
                "source": entry.get("last_source", ""),
                "weekly_tag": "FADED",
            })

    return HistoryResult(candidates=tagged, faded=faded, history=history)
