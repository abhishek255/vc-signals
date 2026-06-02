"""Tests for the last30days adapter module."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_check_not_installed(tmp_path):
    from last30days_adapter import check_availability

    result = check_availability(vendor_path=tmp_path / "nonexistent", config_path=tmp_path / "no-such-env")
    assert result["installed"] is False
    assert result["configured"] is False


def test_check_installed_not_configured(tmp_path):
    from last30days_adapter import check_availability

    vendor = tmp_path / "last30days-skill"
    (vendor / "scripts" / "lib").mkdir(parents=True)
    (vendor / "scripts" / "last30days.py").write_text("# stub")
    (vendor / "scripts" / "lib" / "__init__.py").write_text("")

    result = check_availability(vendor_path=vendor, config_path=tmp_path / "no-such-env")
    assert result["installed"] is True
    assert result["configured"] is False


def test_check_installed_and_configured(tmp_path):
    from last30days_adapter import check_availability

    vendor = tmp_path / "last30days-skill"
    (vendor / "scripts" / "lib").mkdir(parents=True)
    (vendor / "scripts" / "last30days.py").write_text("# stub")
    (vendor / "scripts" / "lib" / "__init__.py").write_text("")

    config_dir = tmp_path / "config" / "last30days"
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text("SETUP_COMPLETE=true\nOPENAI_API_KEY=sk-fake\n")

    result = check_availability(vendor_path=vendor, config_path=config_dir / ".env")
    assert result["installed"] is True
    assert result["configured"] is True


def test_normalize_report_items():
    from last30days_adapter import normalize_report_items

    mock_items = {
        "reddit": [
            {
                "item_id": "r1",
                "source": "reddit",
                "title": "AI code review is amazing",
                "url": "https://reddit.com/r/programming/123",
                "snippet": "I switched to CodeRabbit and it changed everything",
                "published_at": "2026-04-07T10:00:00Z",
                "engagement": {"upvotes": 350, "comments": 42},
                "container": "r/programming",
            }
        ],
        "hackernews": [
            {
                "item_id": "hn1",
                "source": "hackernews",
                "title": "Show HN: New testing framework",
                "url": "https://news.ycombinator.com/item?id=999",
                "outbound_url": "https://testingframework.dev",
                "domain": "testingframework.dev",
                "snippet": "Built a new testing tool that uses AI",
                "published_at": "2026-04-08T14:00:00Z",
                "engagement": {"points": 200, "comments": 85},
                "container": "hackernews",
            }
        ],
    }

    normalized = normalize_report_items(mock_items)
    assert len(normalized) == 2
    assert normalized[0]["source"] in ("reddit", "hackernews")
    assert "title" in normalized[0]
    assert "engagement" in normalized[0]
    hn_item = next(item for item in normalized if item["source"] == "hackernews")
    assert hn_item["outbound_url"] == "https://testingframework.dev"
    assert hn_item["domain"] == "testingframework.dev"
    assert "outbound_url" in hn_item["_raw_fields_present"]
    assert hn_item["_identity_fields_present_upstream"] == ["outbound_url", "domain"]


def test_normalize_report_items_preserves_native_source_identity_fields():
    from last30days_adapter import normalize_report_items

    mock_items = {
        "hackernews": [
            {
                "title": "Show HN: Burrow",
                "url": "https://news.ycombinator.com/item?id=1",
                "hn_url": "https://news.ycombinator.com/item?id=1",
                "outbound_url": "https://burrow.security",
                "domain": "burrow.security",
                "author": "founder",
                "engagement": {"points": 10, "comments": 2},
            }
        ],
        "grounding": [
            {
                "title": "ShieldAgent | Y Combinator",
                "url": "https://www.ycombinator.com/companies/shieldagent",
                "website": "https://shieldagent.ai",
                "homepage": "https://shieldagent.ai",
                "founders": ["Jane Doe"],
                "batch": "W26",
                "description": "AI agent security company.",
            }
        ],
    }

    normalized = normalize_report_items(mock_items)

    hn_item = next(item for item in normalized if item["source"] == "hackernews")
    assert hn_item["hn_url"] == "https://news.ycombinator.com/item?id=1"
    assert hn_item["author"] == "founder"
    assert "hn_url" in hn_item["_identity_fields_present_upstream"]

    yc_item = next(item for item in normalized if item["source"] == "grounding")
    assert yc_item["website"] == "https://shieldagent.ai"
    assert yc_item["founders"] == ["Jane Doe"]
    assert yc_item["batch"] == "W26"
    assert "website" in yc_item["_identity_fields_present_upstream"]
    assert "founders" in yc_item["_identity_fields_present_upstream"]
    assert "batch" in yc_item["_identity_fields_present_upstream"]


def test_normalize_report_items_promotes_hn_metadata_discussion_url_and_domain():
    from last30days_adapter import normalize_report_items

    normalized = normalize_report_items(
        {
            "hackernews": [
                {
                    "title": "Show HN: AgentEval",
                    "url": "https://agenteval.dev",
                    "metadata": {"hn_url": "https://news.ycombinator.com/item?id=42"},
                    "author": "founder",
                    "engagement": {"points": 10, "comments": 2},
                }
            ]
        }
    )

    item = normalized[0]
    assert item["url"] == "https://agenteval.dev"
    assert item["outbound_url"] == "https://agenteval.dev"
    assert item["domain"] == "agenteval.dev"
    assert item["hn_url"] == "https://news.ycombinator.com/item?id=42"
    assert "hn_url" in item["_identity_fields_present_upstream"]
    assert "outbound_url" in item["_identity_fields_present_upstream"]
    assert "domain" in item["_identity_fields_present_upstream"]


# --- run_query: real subprocess-mocked tests ---

def _make_vendor(tmp_path):
    """Create a minimal vendor layout that passes existence checks."""
    vendor = tmp_path / "last30days-skill"
    (vendor / "scripts" / "lib").mkdir(parents=True)
    (vendor / "scripts" / "last30days.py").write_text("# stub")
    (vendor / "scripts" / "lib" / "__init__.py").write_text("")
    return vendor


def _make_nested_vendor(tmp_path):
    """Create the current upstream last30days skill layout."""
    vendor = tmp_path / "last30days-skill"
    skill_root = vendor / "skills" / "last30days"
    (skill_root / "scripts" / "lib").mkdir(parents=True)
    (skill_root / "scripts" / "last30days.py").write_text("# stub")
    (skill_root / "scripts" / "lib" / "__init__.py").write_text("")
    return vendor


def test_check_installed_with_current_upstream_nested_layout(tmp_path):
    from last30days_adapter import check_availability

    vendor = _make_nested_vendor(tmp_path)

    result = check_availability(vendor_path=vendor, config_path=tmp_path / "no-such-env")
    assert result["installed"] is True
    assert result["script_path"].endswith("skills/last30days/scripts/last30days.py")


def test_check_reports_free_sources_when_installed_without_keys(tmp_path):
    from last30days_adapter import check_availability

    vendor = _make_nested_vendor(tmp_path)

    result = check_availability(vendor_path=vendor, config_path=tmp_path / "no-such-env")
    assert result["free_sources_available"] is True
    assert set(result["source_capabilities"]["free"]) >= {"reddit", "hackernews", "github", "polymarket"}
    assert result["source_capabilities"]["social"] == []


def test_check_does_not_report_grounded_from_openrouter_alone(tmp_path):
    from last30days_adapter import check_availability

    vendor = _make_nested_vendor(tmp_path)
    config = tmp_path / ".env"
    config.write_text("SETUP_COMPLETE=true\nOPENROUTER_API_KEY=sk-or-fake\n")

    result = check_availability(vendor_path=vendor, config_path=config)
    assert result["deep_research_available"] is True
    assert result["source_capabilities"]["grounded"] == []


def test_check_reports_grounded_from_native_web_key(tmp_path):
    from last30days_adapter import check_availability

    vendor = _make_nested_vendor(tmp_path)
    config = tmp_path / ".env"
    config.write_text("SETUP_COMPLETE=true\nBRAVE_API_KEY=brave-fake\n")

    result = check_availability(vendor_path=vendor, config_path=config)
    assert result["source_capabilities"]["grounded"] == ["web"]


@pytest.mark.parametrize("key_name", ["EXA_API_KEY", "SERPER_API_KEY"])
def test_check_reports_grounded_from_all_native_web_keys(tmp_path, key_name):
    from last30days_adapter import check_availability

    vendor = _make_nested_vendor(tmp_path)
    config = tmp_path / ".env"
    config.write_text(f"SETUP_COMPLETE=true\n{key_name}=native-web-fake\n")

    result = check_availability(vendor_path=vendor, config_path=config)
    assert key_name in result["available_keys"]
    assert result["source_capabilities"]["grounded"] == ["web"]


def test_check_ignores_placeholder_key_values(tmp_path):
    from last30days_adapter import check_availability

    vendor = _make_nested_vendor(tmp_path)
    config = tmp_path / ".env"
    config.write_text("SETUP_COMPLETE=true\nBRAVE_API_KEY=...\n")

    result = check_availability(vendor_path=vendor, config_path=config)
    assert "BRAVE_API_KEY" not in result["available_keys"]
    assert result["source_capabilities"]["grounded"] == []


def test_run_query_returns_error_when_vendor_missing(tmp_path):
    from last30days_adapter import run_query

    result = run_query("topic", vendor_path=tmp_path / "nonexistent")
    assert result["error"] == "last30days not installed"
    assert result["items"] == []


def test_run_query_returns_error_when_python_missing(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: None)

    result = run_query("topic", vendor_path=vendor)
    assert "Python 3.12+" in result["error"]
    assert result["items"] == []


def test_find_python_uses_codex_bundled_python_when_available(tmp_path, monkeypatch):
    from last30days_adapter import _find_python

    bundled = tmp_path / "codex-python" / "bin" / "python3"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("# stub")

    def fake_run(cmd, **kwargs):
        if cmd[0] == str(bundled):
            return MagicMock(returncode=0)
        raise FileNotFoundError(cmd[0])

    monkeypatch.setenv("CODEX_BUNDLED_PYTHON", str(bundled))
    monkeypatch.setattr("last30days_adapter.subprocess.run", fake_run)

    assert _find_python() == str(bundled)


def test_run_query_emits_normalized_items(tmp_path, monkeypatch):
    """Happy path: subprocess returns valid JSON; items are normalized."""
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")

    fake_payload = {
        "items_by_source": {
            "reddit": [{
                "title": "x", "url": "https://r/x", "snippet": "s",
                "published_at": "2026-04-30", "engagement": {"upvotes": 50},
                "container": "r/programming",
            }],
        },
        "clusters": [],
        "warnings": [],
    }
    completed = MagicMock(returncode=0, stdout=json.dumps(fake_payload), stderr="")
    monkeypatch.setattr("last30days_adapter._run_last30days_command", lambda *a, **kw: completed)

    result = run_query("AI code review", vendor_path=vendor)
    assert result["topic"] == "AI code review"
    assert len(result["items"]) == 1
    assert result["items"][0]["source"] == "reddit"
    assert result["items"][0]["url"] == "https://r/x"


def test_run_query_preserves_source_errors(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    fake_payload = {
        "items_by_source": {},
        "clusters": [],
        "warnings": ["Some sources failed: grounding"],
        "errors_by_source": {"grounding": "HTTP 402: Payment Required"},
    }
    completed = MagicMock(returncode=0, stdout=json.dumps(fake_payload), stderr="")
    monkeypatch.setattr("last30days_adapter._run_last30days_command", lambda *a, **kw: completed)

    result = run_query("AI agent security", vendor_path=vendor)

    assert result["errors_by_source"] == {"grounding": "HTTP 402: Payment Required"}


def test_run_query_uses_nested_script_path_and_skill_root_cwd(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_nested_vendor(tmp_path)
    skill_root = vendor / "skills" / "last30days"
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")

    fake_payload = {"items_by_source": {}, "clusters": [], "warnings": []}
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return MagicMock(returncode=0, stdout=json.dumps(fake_payload), stderr="")

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    result = run_query("AI memory", vendor_path=vendor)
    assert result["topic"] == "AI memory"
    cmd, kwargs = calls[0]
    assert str(skill_root / "scripts" / "last30days.py") in cmd
    assert kwargs["cwd"] == str(skill_root)
    assert kwargs["timeout"] is None


def test_run_query_accepts_custom_timeout_seconds(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query("AI memory", vendor_path=vendor, timeout_seconds=45)

    assert calls[0][1]["timeout"] == 45


def test_run_query_passes_new_last30days_flags(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query(
        "agent infra",
        vendor_path=vendor,
        deep=True,
        x_related="builderio,vercel",
        tiktok_hashtags="aitools,agents",
        tiktok_creators="examplecreator",
        ig_creators="example.ig",
        polymarket_keywords="AI agents",
        web_backend="sonar",
        save_dir="/tmp/vc-signals-last30days",
    )

    cmd = calls[0]
    assert "--deep" in cmd
    assert "--x-related=builderio,vercel" in cmd
    assert "--tiktok-hashtags=aitools,agents" in cmd
    assert "--tiktok-creators=examplecreator" in cmd
    assert "--ig-creators=example.ig" in cmd
    assert "--polymarket-keywords=AI agents" in cmd
    assert "--web-backend=sonar" in cmd
    assert "--save-dir=/tmp/vc-signals-last30days" in cmd


def test_run_query_avoids_implicit_brave_auto_routing(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query("agent infra", vendor_path=vendor, extra_env={"BRAVE_API_KEY": "brave-test"})

    assert "--web-backend=none" in calls[0]


def test_run_query_prefers_explicit_last30days_web_backend(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query(
        "agent infra",
        vendor_path=vendor,
        extra_env={
            "BRAVE_API_KEY": "brave-test",
            "VC_SIGNALS_LAST30DAYS_WEB_BACKEND": "serper",
        },
    )

    assert "--web-backend=serper" in calls[0]
    assert "--web-backend=none" not in calls[0]


def test_run_query_disables_implicit_web_backend_even_when_exa_available(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query(
        "agent infra",
        vendor_path=vendor,
        extra_env={"BRAVE_API_KEY": "brave-test", "EXA_API_KEY": "exa-test"},
    )

    assert "--web-backend=none" in calls[0]


def test_run_query_prefers_exa_when_last30days_grounding_explicitly_enabled(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query(
        "agent infra",
        vendor_path=vendor,
        extra_env={
            "BRAVE_API_KEY": "brave-test",
            "EXA_API_KEY": "exa-test",
            "VC_SIGNALS_ALLOW_LAST30DAYS_GROUNDING": "1",
        },
    )

    assert "--web-backend=exa" in calls[0]


def test_run_query_allows_implicit_brave_only_when_explicitly_enabled(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query(
        "agent infra",
        vendor_path=vendor,
        extra_env={
            "BRAVE_API_KEY": "brave-test",
            "VC_SIGNALS_ALLOW_BRAVE_AUTO": "1",
            "VC_SIGNALS_ALLOW_LAST30DAYS_GROUNDING": "1",
        },
    )

    assert not any(part.startswith("--web-backend=") for part in calls[0])


def test_run_query_skips_grounding_when_paid_search_budget_exceeded(tmp_path, monkeypatch):
    from last30days_adapter import run_query
    from paid_search_guardrails import configure_paid_search_guard, reset_paid_search_guard

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    configure_paid_search_guard(
        mode="smoke",
        run_id="last30days-budget-test",
        max_usd=0.0,
        ledger_path=tmp_path / "ledger.jsonl",
        allow_last30days_grounding=True,
    )

    def should_not_call(*_args, **_kwargs):
        raise AssertionError("budget guard should skip last30days subprocess")

    monkeypatch.setattr("last30days_adapter._run_last30days_command", should_not_call)

    try:
        result = run_query(
            "agent infra",
            vendor_path=vendor,
            sources="grounding",
            extra_env={"EXA_API_KEY": "exa-test", "VC_SIGNALS_ALLOW_LAST30DAYS_GROUNDING": "1"},
        )
    finally:
        reset_paid_search_guard()

    assert result["error"] == "paid_search_budget_exceeded"
    assert result["items"] == []
    assert result["paid_search"]["provider"] == "last30days_grounding"


def test_run_query_passes_v33_alignment_flags(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query(
        "agent infra",
        vendor_path=vendor,
        competitors=2,
        competitors_list="OpenAI,Anthropic,xAI",
        competitors_plan="/tmp/competitors-plan.json",
        synthesis_file="/tmp/synthesis.md",
    )

    cmd = calls[0]
    assert "--competitors=2" in cmd
    assert "--competitors-list=OpenAI,Anthropic,xAI" in cmd
    assert "--competitors-plan=/tmp/competitors-plan.json" in cmd
    assert "--synthesis-file=/tmp/synthesis.md" in cmd


def test_run_query_sets_source_environment_overrides(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query(
        "agent infra",
        vendor_path=vendor,
        include_sources="reddit,hackernews",
        exclude_sources="tiktok,instagram",
        youtube_ssh_host="homebox",
    )

    env = calls[0][1]["env"]
    assert env["INCLUDE_SOURCES"] == "reddit,hackernews"
    assert env["EXCLUDE_SOURCES"] == "tiktok,instagram"
    assert env["LAST30DAYS_YOUTUBE_SSH_HOST"] == "homebox"


def test_run_query_disables_browser_cookie_lookup_by_default(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query("agent infra", vendor_path=vendor, extra_env={"XAI_API_KEY": "xai-test", "FROM_BROWSER": "safari"})

    env = calls[0][1]["env"]
    assert env["FROM_BROWSER"] == "off"
    assert env["LAST30DAYS_DISABLE_BROWSER_COOKIES"] == "1"
    assert env["BIRD_DISABLE_BROWSER_COOKIES"] == "1"


def test_run_query_allows_explicit_browser_cookie_override(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout=json.dumps({"items_by_source": {}}), stderr="")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return completed

    monkeypatch.setattr("last30days_adapter._run_last30days_command", fake_run)

    run_query(
        "agent infra",
        vendor_path=vendor,
        extra_env={"LAST30DAYS_ALLOW_BROWSER_COOKIES": "true", "FROM_BROWSER": "firefox"},
    )

    env = calls[0][1]["env"]
    assert env["FROM_BROWSER"] == "firefox"
    assert "LAST30DAYS_DISABLE_BROWSER_COOKIES" not in env


def test_run_query_handles_nonzero_exit(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=2, stdout="", stderr="boom")
    monkeypatch.setattr("last30days_adapter._run_last30days_command", lambda *a, **kw: completed)

    result = run_query("topic", vendor_path=vendor)
    assert "exited with code 2" in result["error"]
    assert result["stderr"] == "boom"
    assert result["items"] == []


def test_run_query_handles_timeout(tmp_path, monkeypatch):
    import subprocess
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")

    def raise_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd=a[0] if a else "", timeout=1)
    monkeypatch.setattr("last30days_adapter._run_last30days_command", raise_timeout)

    result = run_query("topic", vendor_path=vendor)
    assert "timed out" in result["error"]
    assert result["items"] == []


def test_run_query_preserves_timeout_stderr_and_stdout(tmp_path, monkeypatch):
    import subprocess
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")

    def raise_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(
            cmd=a[0] if a else "",
            timeout=90,
            output="partial source trace",
            stderr="[RedditPublic] HTTP 429 rate limited\n[ScrapeCreators] HTTP 402 Payment Required",
        )

    monkeypatch.setattr("last30days_adapter._run_last30days_command", raise_timeout)

    result = run_query("topic", vendor_path=vendor, timeout_seconds=90)

    assert result["error"] == "last30days query timed out (90s)"
    assert "HTTP 429" in result["stderr"]
    assert "HTTP 402" in result["stderr"]
    assert result["raw_output"] == "partial source trace"
    assert result["items"] == []


def test_run_last30days_command_kills_process_group_on_timeout(monkeypatch):
    import subprocess
    import last30days_adapter

    calls = {"communicate": 0, "killpg": []}

    class FakeProcess:
        pid = 12345
        returncode = None

        def communicate(self, timeout=None):
            calls["communicate"] += 1
            if calls["communicate"] == 1:
                raise subprocess.TimeoutExpired(cmd=["python3"], timeout=timeout, output="partial", stderr="slow")
            return "partial", "slow"

    def fake_popen(*_args, **kwargs):
        assert kwargs["start_new_session"] is True
        return FakeProcess()

    monkeypatch.setattr(last30days_adapter.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(last30days_adapter.os, "killpg", lambda pid, sig: calls["killpg"].append((pid, sig)))

    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        last30days_adapter._run_last30days_command(
            ["python3", "last30days.py"],
            capture_output=True,
            text=True,
            timeout=1,
            cwd="/tmp",
            env={},
        )

    assert calls["killpg"]
    assert exc_info.value.output == "partial"
    assert exc_info.value.stderr == "slow"


def test_run_query_handles_malformed_json(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout="not json{", stderr="")
    monkeypatch.setattr("last30days_adapter._run_last30days_command", lambda *a, **kw: completed)

    result = run_query("topic", vendor_path=vendor)
    assert "Failed to parse" in result["error"]
    assert result["items"] == []


def test_run_query_emit_text_returns_raw_output(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout="raw markdown report", stderr="")
    monkeypatch.setattr("last30days_adapter._run_last30days_command", lambda *a, **kw: completed)

    result = run_query("topic", vendor_path=vendor, emit="text")
    assert result["raw_output"] == "raw markdown report"
    assert result["items"] == []


# --- CLI tests ---

def test_cli_check_emits_json(tmp_path):
    """`check` command should print parseable JSON regardless of install state."""
    import subprocess as sp
    script = Path(__file__).parent.parent / "scripts" / "last30days_adapter.py"
    result = sp.run(
        ["python3", str(script), "check",
         "--vendor-path", str(tmp_path / "nope"),
         "--config-path", str(tmp_path / "no.env")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["installed"] is False
    assert payload["configured"] is False


def test_cli_unknown_command_returns_error():
    import subprocess as sp
    script = Path(__file__).parent.parent / "scripts" / "last30days_adapter.py"
    result = sp.run(
        ["python3", str(script), "bogus"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "Unknown command" in payload["error"]


def test_cli_query_missing_topic_returns_error():
    import subprocess as sp
    script = Path(__file__).parent.parent / "scripts" / "last30days_adapter.py"
    result = sp.run(
        ["python3", str(script), "query"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "topic" in payload["error"].lower()


def test_cli_query_forwards_alignment_args(monkeypatch, capsys):
    import last30days_adapter

    captured = {}

    def fake_run_query(**kwargs):
        captured.update(kwargs)
        return {"topic": kwargs["topic"], "items": []}

    monkeypatch.setattr(last30days_adapter, "run_query", fake_run_query)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "last30days_adapter.py",
            "query",
            "--topic",
            "agent infra",
            "--emit",
            "html",
            "--competitors",
            "2",
            "--competitors-list",
            "OpenAI,Anthropic,xAI",
            "--competitors-plan",
            "/tmp/competitors-plan.json",
            "--synthesis-file",
            "/tmp/synthesis.md",
            "--include-sources",
            "reddit,hackernews",
            "--exclude-sources",
            "tiktok,instagram",
            "--youtube-ssh-host",
            "homebox",
            "--timeout-seconds",
            "45",
        ],
    )

    last30days_adapter._cli_main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["topic"] == "agent infra"
    assert captured["emit"] == "html"
    assert captured["competitors"] == 2
    assert captured["competitors_list"] == "OpenAI,Anthropic,xAI"
    assert captured["competitors_plan"] == "/tmp/competitors-plan.json"
    assert captured["synthesis_file"] == "/tmp/synthesis.md"
    assert captured["include_sources"] == "reddit,hackernews"
    assert captured["exclude_sources"] == "tiktok,instagram"
    assert captured["youtube_ssh_host"] == "homebox"
    assert captured["timeout_seconds"] == 45


def test_cli_no_command_returns_error():
    import subprocess as sp
    script = Path(__file__).parent.parent / "scripts" / "last30days_adapter.py"
    result = sp.run(
        ["python3", str(script)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "Usage" in payload["error"]
