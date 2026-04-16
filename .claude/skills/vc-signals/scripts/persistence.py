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
) -> dict:
    """Save a briefing as JSON. Returns dict with saved path."""
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = data_dir or DEFAULT_DATA_DIR

    briefing = {
        "date": date,
        "sector": sector,
        "retrieval_path": retrieval_path,
        "themes": themes,
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
            print(json.dumps({"error": "No data piped to stdin. Usage: echo '<json>' | persistence.py <command> ..."}))
            sys.exit(1)
        themes = json.loads(sys.stdin.read())
        result = save_briefing(
            sector=args["sector"],
            themes=themes,
            retrieval_path=args.get("retrieval-path", "websearch"),
            date=args.get("date"),
            data_dir=data_dir,
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
