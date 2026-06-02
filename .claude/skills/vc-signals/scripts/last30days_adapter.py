#!/usr/bin/env python3
"""Adapter for last30days research engine — detect, configure, run queries, normalize output."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def _resolve_skill_root(vendor_path: Path) -> Path:
    """Return the runnable last30days skill root for flat or current nested layouts."""
    nested = vendor_path / "skills" / "last30days"
    if (nested / "scripts" / "last30days.py").exists():
        return nested
    return vendor_path


def _resolve_script_path(vendor_path: Path) -> Path:
    """Return the last30days CLI script path for flat or current nested layouts."""
    return _resolve_skill_root(vendor_path) / "scripts" / "last30days.py"


def _has_engine(vendor_path: Path) -> bool:
    script = _resolve_script_path(vendor_path)
    lib = script.parent / "lib" / "__init__.py"
    return script.exists() and lib.exists()


def _find_vendor_path() -> Path:
    """Find last30days-skill in multiple candidate locations."""
    candidates = [
        Path(__file__).resolve().parents[4] / "vendor" / "last30days-skill",  # project-level
        Path.home() / "vendor" / "last30days-skill",  # home dir
        Path.home() / ".claude" / "vendor" / "last30days-skill",  # claude config dir
    ]
    for candidate in candidates:
        if _resolve_script_path(candidate).exists():
            return candidate
    return candidates[0]  # return first as default even if not found


DEFAULT_VENDOR_PATH = _find_vendor_path()
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "last30days" / ".env"
PLACEHOLDER_VALUES = {"", "...", "TODO", "YOUR_KEY", "YOUR_API_KEY", "<YOUR_API_KEY>"}
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
IDENTITY_USEFUL_FIELDS = (
    "outbound_url",
    "resolved_url",
    "story_url",
    "domain",
    "homepage",
    "website",
    "hn_url",
    "owner_name",
    "owner_type",
    "topics",
    "description",
    "founders",
    "batch",
)


def _configured_value(value: str) -> bool:
    normalized = value.strip().strip("\"'")
    return normalized not in PLACEHOLDER_VALUES


def _truthy_env(value: object) -> bool:
    return str(value or "").strip().lower() in TRUTHY_ENV_VALUES


def _load_env_file(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip().strip("\"'")
    return env


def _disable_browser_cookie_lookup(env: dict[str, str], detection_env: dict[str, str]) -> None:
    if _truthy_env(detection_env.get("LAST30DAYS_ALLOW_BROWSER_COOKIES")):
        return
    env["FROM_BROWSER"] = "off"
    env["LAST30DAYS_DISABLE_BROWSER_COOKIES"] = "1"
    env["BIRD_DISABLE_BROWSER_COOKIES"] = "1"


def _decode_subprocess_stream(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _run_last30days_command(cmd: list[str], *, capture_output: bool, text: bool, timeout: int | None, cwd: str, env: dict[str, str]):
    """Run last30days with process-group timeout protection.

    last30days can spawn helper processes that inherit stdout/stderr pipes. The
    stdlib subprocess.run timeout kills only the direct child, which can leave
    the parent process stuck in communicate() waiting for inherited pipes to
    close. Running the child in a new session lets us kill the whole group.
    """
    if os.name == "nt":  # pragma: no cover - this repo runs on Unix/macOS
        return subprocess.run(
            cmd,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=text,
        cwd=cwd,
        env=env,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:  # pragma: no cover - race with process exit
            pass
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            stdout = _decode_subprocess_stream(getattr(exc, "stdout", None) or getattr(exc, "output", None))
            stderr = _decode_subprocess_stream(getattr(exc, "stderr", None))
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)


def check_availability(
    vendor_path: Path | None = None,
    config_path: Path | None = None,
) -> dict:
    """Check if last30days is installed and configured."""
    vendor_path = vendor_path or DEFAULT_VENDOR_PATH
    config_path = config_path or DEFAULT_CONFIG_PATH

    skill_root = _resolve_skill_root(vendor_path)
    script_path = _resolve_script_path(vendor_path)
    installed = _has_engine(vendor_path)

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
            for key_name in (
                "OPENAI_API_KEY",
                "GEMINI_API_KEY",
                "GOOGLE_API_KEY",
                "XAI_API_KEY",
                "OPENROUTER_API_KEY",
                "SCRAPECREATORS_API_KEY",
                "AUTH_TOKEN",
                "CT0",
                "BRAVE_API_KEY",
                "EXA_API_KEY",
                "SERPER_API_KEY",
                "PARALLEL_API_KEY",
            ):
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith(f"{key_name}=") and _configured_value(stripped.split("=", 1)[1]):
                        available_keys.append(key_name)
            configured = len(available_keys) > 0

    social_sources = []
    if "AUTH_TOKEN" in available_keys or "XAI_API_KEY" in available_keys:
        social_sources.append("x")
    if "SCRAPECREATORS_API_KEY" in available_keys:
        social_sources.extend(["youtube", "tiktok", "instagram", "threads", "pinterest"])
    grounded_sources = []
    if any(key in available_keys for key in ("BRAVE_API_KEY", "EXA_API_KEY", "SERPER_API_KEY", "PARALLEL_API_KEY")):
        grounded_sources.append("web")

    return {
        "installed": installed,
        "configured": configured,
        "vendor_path": str(vendor_path),
        "skill_root": str(skill_root),
        "script_path": str(script_path),
        "config_path": str(config_path),
        "available_keys": available_keys,
        "free_sources_available": installed,
        "source_capabilities": {
            "free": ["reddit", "hackernews", "github", "polymarket"] if installed else [],
            "social": social_sources,
            "grounded": grounded_sources,
        },
        "deep_research_available": "OPENROUTER_API_KEY" in available_keys,
    }


def normalize_report_items(items_by_source: dict) -> list[dict]:
    """Normalize last30days source items into a flat list for Claude to process."""
    normalized = []

    for source, items in items_by_source.items():
        for item in items:
            enriched_item = _enrich_native_identity_fields(source, item)
            normalized_item = {
                "source": source,
                "title": enriched_item.get("title", ""),
                "url": enriched_item.get("url", ""),
                "snippet": enriched_item.get("snippet", enriched_item.get("body", ""))[:500],
                "published_at": enriched_item.get("published_at", ""),
                "engagement": enriched_item.get("engagement", {}),
                "container": enriched_item.get("container", ""),
                "author": enriched_item.get("author", ""),
                "_raw_fields_present": sorted(item.keys()),
                "_identity_fields_present_upstream": [
                    field for field in IDENTITY_USEFUL_FIELDS if enriched_item.get(field) not in ("", None, [], {})
                ],
            }
            for field in IDENTITY_USEFUL_FIELDS:
                if enriched_item.get(field) not in ("", None, [], {}):
                    normalized_item[field] = enriched_item[field]
            normalized.append(normalized_item)

    return normalized


def _enrich_native_identity_fields(source: str, item: dict) -> dict:
    """Promote source-native metadata needed by downstream identity audits."""
    enriched = dict(item)
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    if source == "hackernews":
        if not enriched.get("hn_url") and metadata.get("hn_url"):
            enriched["hn_url"] = metadata["hn_url"]
        url = enriched.get("url") or ""
        if url and "news.ycombinator.com" not in url:
            enriched.setdefault("outbound_url", url)
            domain = urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            if domain:
                enriched.setdefault("domain", domain)
    return enriched


def run_query(
    topic: str,
    vendor_path: Path | None = None,
    sources: str | None = None,
    lookback_days: int = 30,
    emit: str = "json",
    subreddits: str | None = None,
    quick: bool = False,
    deep_research: bool = False,
    auto_resolve: bool = False,
    store: bool = False,
    deep: bool = False,
    github_user: str | None = None,
    github_repo: str | None = None,
    x_handle: str | None = None,
    x_related: str | None = None,
    plan: str | None = None,
    tiktok_hashtags: str | None = None,
    tiktok_creators: str | None = None,
    ig_creators: str | None = None,
    polymarket_keywords: str | None = None,
    web_backend: str | None = None,
    save_dir: str | None = None,
    save_suffix: str | None = None,
    competitors: int | str | bool | None = None,
    competitors_list: str | None = None,
    competitors_plan: str | None = None,
    synthesis_file: str | None = None,
    include_sources: str | None = None,
    exclude_sources: str | None = None,
    youtube_ssh_host: str | None = None,
    extra_env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
) -> dict:
    """Run a query through last30days CLI and return parsed results."""
    vendor_path = vendor_path or DEFAULT_VENDOR_PATH
    skill_root = _resolve_skill_root(vendor_path)
    script_path = _resolve_script_path(vendor_path)

    if not _has_engine(vendor_path):
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
    if deep_research:
        cmd.append("--deep-research")
    if deep:
        cmd.append("--deep")
    if auto_resolve:
        cmd.append("--auto-resolve")
    if store:
        cmd.append("--store")
    if github_user:
        cmd.append(f"--github-user={github_user}")
    if github_repo:
        cmd.append(f"--github-repo={github_repo}")
    if x_handle:
        cmd.append(f"--x-handle={x_handle}")
    if x_related:
        cmd.append(f"--x-related={x_related}")
    if plan:
        cmd.append(f"--plan={plan}")
    if tiktok_hashtags:
        cmd.append(f"--tiktok-hashtags={tiktok_hashtags}")
    if tiktok_creators:
        cmd.append(f"--tiktok-creators={tiktok_creators}")
    if ig_creators:
        cmd.append(f"--ig-creators={ig_creators}")
    if polymarket_keywords:
        cmd.append(f"--polymarket-keywords={polymarket_keywords}")
    if web_backend:
        cmd.append(f"--web-backend={web_backend}")
    if save_dir:
        cmd.append(f"--save-dir={save_dir}")
    if save_suffix:
        cmd.append(f"--save-suffix={save_suffix}")
    if competitors is not None and competitors is not False:
        if competitors is True:
            cmd.append("--competitors")
        else:
            cmd.append(f"--competitors={competitors}")
    if competitors_list:
        cmd.append(f"--competitors-list={competitors_list}")
    if competitors_plan:
        cmd.append(f"--competitors-plan={competitors_plan}")
    if synthesis_file:
        cmd.append(f"--synthesis-file={synthesis_file}")

    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    detection_env = _load_env_file(DEFAULT_CONFIG_PATH)
    detection_env.update(os.environ)
    if extra_env:
        detection_env.update({key: str(value) for key, value in extra_env.items()})
    _disable_browser_cookie_lookup(env, detection_env)
    if include_sources:
        env["INCLUDE_SOURCES"] = include_sources
    if exclude_sources:
        env["EXCLUDE_SOURCES"] = exclude_sources
    if youtube_ssh_host:
        env["LAST30DAYS_YOUTUBE_SSH_HOST"] = youtube_ssh_host

    try:
        result = _run_last30days_command(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(skill_root),
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_result = {"error": f"last30days query timed out ({timeout_seconds}s)", "items": []}
        stderr = _decode_subprocess_stream(getattr(exc, "stderr", None))
        stdout = _decode_subprocess_stream(getattr(exc, "stdout", None) or getattr(exc, "output", None))
        if stderr:
            timeout_result["stderr"] = stderr[:4000]
        if stdout:
            timeout_result["raw_output"] = stdout[:2000]
        return timeout_result
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
                "errors_by_source": report.get("errors_by_source", {}),
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
    candidates = []
    env_candidate = os.environ.get("CODEX_BUNDLED_PYTHON")
    if env_candidate:
        candidates.append(env_candidate)
    candidates.extend([
        str(Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python" / "bin" / "python3"),
        "python3.14",
        "python3.13",
        "python3.12",
        "python3",
    ])
    for candidate in candidates:
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
            emit=args.get("emit", "json"),
            subreddits=args.get("subreddits"),
            quick="quick" in args,
            deep_research="deep-research" in args,
            auto_resolve="auto-resolve" in args,
            store="store" in args,
            deep="deep" in args,
            github_user=args.get("github-user"),
            github_repo=args.get("github-repo"),
            x_handle=args.get("x-handle"),
            x_related=args.get("x-related"),
            plan=args.get("plan"),
            tiktok_hashtags=args.get("tiktok-hashtags"),
            tiktok_creators=args.get("tiktok-creators"),
            ig_creators=args.get("ig-creators"),
            polymarket_keywords=args.get("polymarket-keywords"),
            web_backend=args.get("web-backend"),
            save_dir=args.get("save-dir"),
            save_suffix=args.get("save-suffix"),
            competitors=_parse_optional_int_flag(args.get("competitors")),
            competitors_list=args.get("competitors-list"),
            competitors_plan=args.get("competitors-plan"),
            synthesis_file=args.get("synthesis-file"),
            include_sources=args.get("include-sources"),
            exclude_sources=args.get("exclude-sources"),
            youtube_ssh_host=args.get("youtube-ssh-host"),
            timeout_seconds=_parse_int_arg(args.get("timeout-seconds")),
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


def _parse_int_arg(value: str | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _parse_optional_int_flag(value: str | None) -> int | str | bool | None:
    if value is None:
        return None
    if value == "true":
        return True
    try:
        return int(value)
    except ValueError:
        return value


if __name__ == "__main__":
    _cli_main()
