#!/usr/bin/env python3
"""Adapter for last30days research engine — detect, configure, run queries, normalize output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

def _find_vendor_path() -> Path:
    """Find last30days-skill in multiple candidate locations."""
    candidates = [
        Path(__file__).resolve().parents[4] / "vendor" / "last30days-skill",  # project-level
        Path.home() / "vendor" / "last30days-skill",  # home dir
        Path.home() / ".claude" / "vendor" / "last30days-skill",  # claude config dir
    ]
    for candidate in candidates:
        if (candidate / "scripts" / "last30days.py").exists():
            return candidate
    return candidates[0]  # return first as default even if not found

DEFAULT_VENDOR_PATH = _find_vendor_path()
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "last30days" / ".env"


def check_availability(
    vendor_path: Path | None = None,
    config_path: Path | None = None,
) -> dict:
    """Check if last30days is installed and configured."""
    vendor_path = vendor_path or DEFAULT_VENDOR_PATH
    config_path = config_path or DEFAULT_CONFIG_PATH

    installed = (
        (vendor_path / "scripts" / "last30days.py").exists()
        and (vendor_path / "scripts" / "lib" / "__init__.py").exists()
    )

    configured = False
    available_keys = []

    if config_path.exists():
        # Warn if config file is world-readable
        try:
            mode = config_path.stat().st_mode
            if mode & 0o077:  # group or other have read access
                print(json.dumps({"warning": f"Config file {config_path} is world-readable. Run: chmod 600 {config_path}"}), file=sys.stderr)
        except OSError:
            pass
        content = config_path.read_text()
        if "SETUP_COMPLETE=true" in content:
            for key_name in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY"):
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith(f"{key_name}=") and len(stripped.split("=", 1)[1]) > 0:
                        available_keys.append(key_name)
            configured = len(available_keys) > 0

    return {
        "installed": installed,
        "configured": configured,
        "vendor_path": str(vendor_path),
        "config_path": str(config_path),
        "available_keys": available_keys,
    }


def normalize_report_items(items_by_source: dict) -> list[dict]:
    """Normalize last30days source items into a flat list for Claude to process."""
    normalized = []

    for source, items in items_by_source.items():
        for item in items:
            normalized.append({
                "source": source,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", item.get("body", ""))[:500],
                "published_at": item.get("published_at", ""),
                "engagement": item.get("engagement", {}),
                "container": item.get("container", ""),
                "author": item.get("author", ""),
            })

    return normalized


def run_query(
    topic: str,
    vendor_path: Path | None = None,
    sources: str | None = None,
    lookback_days: int = 30,
    emit: str = "json",
    subreddits: str | None = None,
    quick: bool = False,
) -> dict:
    """Run a query through last30days CLI and return parsed results."""
    vendor_path = vendor_path or DEFAULT_VENDOR_PATH
    script_path = vendor_path / "scripts" / "last30days.py"

    if not script_path.exists():
        return {"error": "last30days not installed", "items": []}

    python_cmd = _find_python()
    if not python_cmd:
        return {"error": "Python 3.12+ required for last30days", "items": []}

    cmd = [python_cmd, str(script_path), topic, f"--emit={emit}", f"--lookback-days={lookback_days}"]
    if sources:
        cmd.append(f"--search={sources}")
    if subreddits:
        cmd.append(f"--subreddits={subreddits}")
    if quick:
        cmd.append("--quick")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(vendor_path),
        )
    except subprocess.TimeoutExpired:
        return {"error": "last30days query timed out (120s)", "items": []}
    except FileNotFoundError:
        return {"error": f"Python not found: {python_cmd}", "items": []}

    if result.returncode != 0:
        return {
            "error": f"last30days exited with code {result.returncode}",
            "stderr": result.stderr[:500] if result.stderr else "",
            "items": [],
        }

    if emit == "json":
        try:
            report = json.loads(result.stdout)
            items = normalize_report_items(report.get("items_by_source", {}))
            return {
                "topic": topic,
                "items": items,
                "clusters": report.get("clusters", []),
                "warnings": report.get("warnings", []),
            }
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse last30days JSON output",
                "raw_output": result.stdout[:1000],
                "items": [],
            }
    else:
        return {"topic": topic, "raw_output": result.stdout, "items": []}


def _find_python() -> str | None:
    """Find Python 3.12+ interpreter."""
    for candidate in ("python3.14", "python3.13", "python3.12", "python3"):
        try:
            result = subprocess.run(
                [candidate, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def _cli_main() -> None:
    """CLI entry point. Commands: check, query."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: last30days_adapter.py <check|query> [args]"}))
        sys.exit(1)

    command = sys.argv[1]
    args = _parse_cli_args(sys.argv[2:])

    if command == "check":
        vendor = Path(args["vendor-path"]) if "vendor-path" in args else None
        config = Path(args["config-path"]) if "config-path" in args else None
        result = check_availability(vendor, config)
        print(json.dumps(result, indent=2))

    elif command == "query":
        topic = args.get("topic", "")
        if not topic:
            print(json.dumps({"error": "--topic is required"}))
            sys.exit(1)
        vendor = Path(args["vendor-path"]) if "vendor-path" in args else None
        result = run_query(
            topic=topic,
            vendor_path=vendor,
            sources=args.get("sources"),
            lookback_days=int(args.get("lookback-days", "30")),
            subreddits=args.get("subreddits"),
            quick="quick" in args,
        )
        print(json.dumps(result, indent=2))

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


def _parse_cli_args(argv: list[str]) -> dict:
    """Parse --key value pairs."""
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
