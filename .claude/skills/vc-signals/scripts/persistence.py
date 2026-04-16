#!/usr/bin/env python3
"""Persistence layer for VC Signals — save/load briefings, diffs, theme index."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"

FADING_MOMENTUM_DROP = 3   # theme is fading if momentum dropped by this much or more
ACCELERATING_MOMENTUM_GAIN = 2  # theme is accelerating if momentum gained by this much or more


def save_briefing(
    sector: str,
    themes: list[dict],
    retrieval_path: str,
    date: str | None = None,
    data_dir: Path | None = None,
    companies: list[dict] | None = None,
) -> dict:
    """Save a briefing as JSON. Returns dict with saved path.

    The on-disk schema is:
        {
          "date": "YYYY-MM-DD",
          "sector": "devtools",
          "retrieval_path": "websearch" | "last30days",
          "themes": [...],
          "companies": [...]   # added in radar-flip; defaults to [] when not provided
        }

    Old briefings (pre-radar-flip) loaded back will not have a "companies" key;
    callers that need it should default to [] when missing.
    """
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = data_dir or DEFAULT_DATA_DIR

    briefing = {
        "date": date,
        "sector": sector,
        "retrieval_path": retrieval_path,
        "themes": themes,
        "companies": companies or [],
    }

    briefings_dir = data_dir / "briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)

    json_path = briefings_dir / f"{date}-{sector}.json"
    overwritten = json_path.exists()
    json_path.write_text(json.dumps(briefing, indent=2))

    return {"saved": str(json_path), "date": date, "overwritten": overwritten}


def load_briefing(
    sector: str,
    date: str,
    data_dir: Path | None = None,
) -> dict | None:
    """Load a briefing by sector and date. Returns None if not found."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    json_path = data_dir / "briefings" / f"{date}-{sector}.json"
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text())
    except json.JSONDecodeError:
        print(f"Warning: malformed JSON in {json_path}", file=sys.stderr)
        return None


def load_previous_briefing(
    sector: str,
    before_date: str,
    data_dir: Path | None = None,
) -> dict | None:
    """Load the most recent briefing before a given date."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    briefings_dir = data_dir / "briefings"
    if not briefings_dir.exists():
        return None

    candidates = sorted(briefings_dir.glob(f"*-{sector}.json"), reverse=True)
    for path in candidates:
        file_date = path.name.removesuffix(f"-{sector}.json")
        if file_date < before_date:
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                print(f"Warning: malformed JSON in {path}", file=sys.stderr)
                return None
    return None


def compute_diff(current: dict, previous: dict) -> dict:
    """Compute week-over-week diff between two briefings."""
    current_themes = {t["name"]: t for t in current["themes"]}
    previous_themes = {t["name"]: t for t in previous["themes"]}

    new_themes = [t for name, t in current_themes.items() if name not in previous_themes]

    fading_themes = []
    for name, prev_t in previous_themes.items():
        if name not in current_themes:
            fading_themes.append(prev_t)
        elif current_themes[name].get("momentum", 0) <= prev_t.get("momentum", 0) - FADING_MOMENTUM_DROP:
            fading_themes.append(prev_t)

    accelerating_themes = []
    for name in current_themes:
        if name in previous_themes:
            curr_m = current_themes[name].get("momentum", 0)
            prev_m = previous_themes[name].get("momentum", 0)
            if curr_m >= prev_m + ACCELERATING_MOMENTUM_GAIN:
                accelerating_themes.append(current_themes[name])

    return {
        "previous_date": previous["date"],
        "new_themes": new_themes,
        "fading_themes": fading_themes,
        "accelerating_themes": accelerating_themes,
    }


def compute_company_diff(
    current: list[dict], previous: list[dict]
) -> dict:
    """Compute new vs faded companies between two weekly company lists.

    A company is "new" if its normalized name appears in current but not previous.
    A company is "faded" if its normalized name appeared in previous but not current.
    Names are matched via _normalize_company_name to handle display variations.

    Returns: {"new_companies": [...], "faded_companies": [...]}
    where each list contains the original (non-normalized) company dicts.
    """
    prev_keys = {_normalize_company_name(c["name"]) for c in previous}
    curr_keys = {_normalize_company_name(c["name"]) for c in current}

    new_companies = [
        c for c in current
        if _normalize_company_name(c["name"]) not in prev_keys
    ]
    faded_companies = [
        c for c in previous
        if _normalize_company_name(c["name"]) not in curr_keys
    ]
    return {
        "new_companies": new_companies,
        "faded_companies": faded_companies,
    }


def update_theme_index(
    themes: list[dict],
    sector: str,
    date: str | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Update the running theme index. Returns the full index."""
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = data_dir or DEFAULT_DATA_DIR

    index_path = data_dir / "history" / "theme_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if index_path.exists():
        try:
            index = json.loads(index_path.read_text())
        except json.JSONDecodeError:
            print(f"Warning: malformed JSON in {index_path}, starting with empty index", file=sys.stderr)
            index = {}
    else:
        index = {}

    for theme in themes:
        name = theme["name"]
        momentum = theme.get("momentum", 0)

        if name in index:
            entry = index[name]
            entry["last_seen"] = date
            entry["appearances"] += 1
            entry["momentum_history"].append(momentum)
            if len(entry["momentum_history"]) > 52:
                entry["momentum_history"] = entry["momentum_history"][-52:]
            entry["peak_momentum"] = max(entry["peak_momentum"], momentum)
            if sector not in entry["sectors"]:
                entry["sectors"].append(sector)
        else:
            index[name] = {
                "first_seen": date,
                "last_seen": date,
                "appearances": 1,
                "sectors": [sector],
                "momentum_history": [momentum],
                "peak_momentum": momentum,
            }

    index_path.write_text(json.dumps(index, indent=2))
    return index


def update_company_index(
    companies: list[dict],
    sector: str,
    date: str | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Update the running company index with this week's companies.

    Mirrors update_theme_index but for companies. The index is keyed by
    the normalized company name (see _normalize_company_name) and stores:

      - display_name: the most recent display form
      - first_seen / last_seen: ISO dates
      - weeks_seen: count of distinct dates this company appeared on
      - missed_weeks: weeks since last_seen, computed when the company
        is updated; reset to 0 each time the company appears
      - sectors: deduped list of sectors that have featured this company
      - themes_history: append-only list of primary_themes (ordered, deduped
        consecutively but not globally — same theme back-to-back collapses)

    Returns the full index dict.
    """
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = data_dir or DEFAULT_DATA_DIR

    index_path = data_dir / "companies" / "company_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if index_path.exists():
        try:
            index = json.loads(index_path.read_text())
        except json.JSONDecodeError:
            print(
                f"Warning: malformed JSON in {index_path}, starting empty",
                file=sys.stderr,
            )
            index = {}
    else:
        index = {}

    for company in companies:
        key = _normalize_company_name(company["name"])
        primary_theme = company.get("primary_theme")

        if key in index:
            entry = index[key]
            entry["display_name"] = company["name"]  # refresh to latest
            entry["last_seen"] = date
            entry["weeks_seen"] += 1
            entry["missed_weeks"] = 0
            if sector not in entry["sectors"]:
                entry["sectors"].append(sector)
            if primary_theme and (
                not entry["themes_history"]
                or entry["themes_history"][-1] != primary_theme
            ):
                entry["themes_history"].append(primary_theme)
        else:
            index[key] = {
                "display_name": company["name"],
                "first_seen": date,
                "last_seen": date,
                "weeks_seen": 1,
                "missed_weeks": 0,
                "sectors": [sector],
                "themes_history": [primary_theme] if primary_theme else [],
            }

    # Compute missed_weeks for companies NOT in this week's list.
    # We measure in calendar weeks since last_seen.
    current_dt = datetime.strptime(date, "%Y-%m-%d")
    current_keys = {_normalize_company_name(c["name"]) for c in companies}
    for key, entry in index.items():
        if key in current_keys:
            continue
        last_dt = datetime.strptime(entry["last_seen"], "%Y-%m-%d")
        weeks_gap = max(0, (current_dt - last_dt).days // 7)
        entry["missed_weeks"] = weeks_gap

    index_path.write_text(json.dumps(index, indent=2))
    return index


def load_company_index(data_dir: Path | None = None) -> dict:
    """Read the company index file, returning {} if it doesn't exist or is malformed."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    index_path = data_dir / "companies" / "company_index.json"
    if not index_path.exists():
        return {}
    try:
        return json.loads(index_path.read_text())
    except json.JSONDecodeError:
        print(f"Warning: malformed JSON in {index_path}", file=sys.stderr)
        return {}


def save_markdown(
    subdir: str,
    slug: str,
    content: str,
    date: str | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Save markdown content to a dated file in the given subdirectory."""
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = data_dir or DEFAULT_DATA_DIR

    target_dir = data_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    md_path = target_dir / f"{date}-{slug}.md"
    md_path.write_text(content)

    return {"saved": str(md_path), "date": date}


# --- CLI interface for Claude to call via Bash ---

def _require_args(args: dict, *required: str) -> None:
    missing = [k for k in required if k not in args]
    if missing:
        print(json.dumps({"error": f"Missing required arguments: {', '.join('--' + k for k in missing)}"}))
        sys.exit(1)


def _validate_slug(value: str, name: str) -> None:
    """Validate that a value is safe for use in file paths."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        print(json.dumps({"error": f"Invalid {name}: '{value}'. Only letters, numbers, hyphens, and underscores allowed."}))
        sys.exit(1)


def _validate_date(value: str, name: str) -> None:
    """Validate that a value is an ISO date (YYYY-MM-DD).

    Used to prevent path traversal via the --date or --before CLI args,
    which flow directly into filenames like f"{date}-{sector}.json".
    """
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        print(json.dumps({"error": f"Invalid {name}: '{value}'. Expected YYYY-MM-DD."}))
        sys.exit(1)


_LEGAL_SUFFIXES = (", inc.", " inc.", ", inc", " inc",
                   ", llc", " llc", ", corp.", " corp.", " corp")
_DOMAIN_SUFFIXES = (".com", ".io", ".ai", ".dev", ".sh", ".net")


def _normalize_company_name(name: str) -> str:
    """Return a canonical key for company dedup across themes and weeks.

    Lowercases, strips legal suffixes ("Inc.", "LLC", "Corp."),
    strips parenthetical disambiguators ("Anysphere (Cursor)" -> "anysphere"),
    strips common domain suffixes (".com", ".ai"), and collapses whitespace.

    Two display names that normalize to the same key are treated as
    the same company by the index, diff, and dedup logic.
    """
    s = name.strip().lower()
    # Drop parenthetical: "anysphere (cursor)" -> "anysphere"
    s = re.sub(r'\s*\([^)]*\)\s*', '', s)
    # Drop legal suffixes
    for suf in _LEGAL_SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    # Drop trailing domain suffixes
    for suf in _DOMAIN_SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    # Collapse internal whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _cli_main() -> None:
    """CLI entry point. Commands: save-briefing, load-briefing, load-previous, diff, update-index, save-markdown."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: persistence.py <command> [args]"}))
        sys.exit(1)

    command = sys.argv[1]
    args = _parse_cli_args(sys.argv[2:])
    data_dir = Path(args.get("data-dir", str(DEFAULT_DATA_DIR)))

    if command == "save-briefing":
        _require_args(args, "sector")
        _validate_slug(args["sector"], "sector")
        if "date" in args:
            _validate_date(args["date"], "date")
        if sys.stdin.isatty():
            print(json.dumps({"error": "No data piped to stdin. Pipe a JSON list of themes or {themes:[], companies:[]}."}))
            sys.exit(1)

        payload = json.loads(sys.stdin.read())
        if isinstance(payload, list):
            # Legacy form: bare themes list
            themes, companies = payload, None
        elif isinstance(payload, dict):
            themes = payload.get("themes", [])
            companies = payload.get("companies")
        else:
            print(json.dumps({"error": "stdin payload must be a list (themes) or object {themes, companies}"}))
            sys.exit(1)

        result = save_briefing(
            sector=args["sector"],
            themes=themes,
            retrieval_path=args.get("retrieval-path", "websearch"),
            date=args.get("date"),
            data_dir=data_dir,
            companies=companies,
        )
        print(json.dumps(result))

    elif command == "load-briefing":
        _require_args(args, "sector", "date")
        _validate_slug(args["sector"], "sector")
        _validate_date(args["date"], "date")
        result = load_briefing(args["sector"], args["date"], data_dir)
        print(json.dumps(result))

    elif command == "load-previous":
        _require_args(args, "sector", "before")
        _validate_slug(args["sector"], "sector")
        _validate_date(args["before"], "before")
        result = load_previous_briefing(args["sector"], args["before"], data_dir)
        print(json.dumps(result))

    elif command == "diff":
        _require_args(args, "sector", "date")
        _validate_slug(args["sector"], "sector")
        _validate_date(args["date"], "date")
        current = load_briefing(args["sector"], args["date"], data_dir)
        previous = load_previous_briefing(args["sector"], args["date"], data_dir)
        if current and previous:
            print(json.dumps(compute_diff(current, previous)))
        else:
            print(json.dumps({"error": "Missing current or previous briefing", "current_found": current is not None, "previous_found": previous is not None}))

    elif command == "update-index":
        _require_args(args, "sector")
        _validate_slug(args["sector"], "sector")
        if "date" in args:
            _validate_date(args["date"], "date")
        if sys.stdin.isatty():
            print(json.dumps({"error": "No data piped to stdin. Usage: echo '<json>' | persistence.py <command> ..."}))
            sys.exit(1)
        themes = json.loads(sys.stdin.read())
        index = update_theme_index(themes, args["sector"], args.get("date"), data_dir)
        print(json.dumps(index))

    elif command == "save-markdown":
        _require_args(args, "subdir", "slug")
        _validate_slug(args["subdir"], "subdir")
        _validate_slug(args["slug"], "slug")
        if "date" in args:
            _validate_date(args["date"], "date")
        if sys.stdin.isatty():
            print(json.dumps({"error": "No data piped to stdin. Usage: echo '<json>' | persistence.py <command> ..."}))
            sys.exit(1)
        content = sys.stdin.read()
        result = save_markdown(args["subdir"], args["slug"], content, args.get("date"), data_dir)
        print(json.dumps(result))

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


def _parse_cli_args(argv: list[str]) -> dict:
    """Parse --key value pairs from argv into a dict."""
    result = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                result[key] = argv[i + 1]
                i += 2
            else:
                result[key] = "true"
                i += 1
        else:
            i += 1
    return result


if __name__ == "__main__":
    _cli_main()
