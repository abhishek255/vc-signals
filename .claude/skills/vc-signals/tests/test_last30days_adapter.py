"""Tests for the last30days adapter module."""

from __future__ import annotations

import json
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


# --- run_query: real subprocess-mocked tests ---

def _make_vendor(tmp_path):
    """Create a minimal vendor layout that passes existence checks."""
    vendor = tmp_path / "last30days-skill"
    (vendor / "scripts" / "lib").mkdir(parents=True)
    (vendor / "scripts" / "last30days.py").write_text("# stub")
    (vendor / "scripts" / "lib" / "__init__.py").write_text("")
    return vendor


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
    monkeypatch.setattr("last30days_adapter.subprocess.run", lambda *a, **kw: completed)

    result = run_query("AI code review", vendor_path=vendor)
    assert result["topic"] == "AI code review"
    assert len(result["items"]) == 1
    assert result["items"][0]["source"] == "reddit"
    assert result["items"][0]["url"] == "https://r/x"


def test_run_query_handles_nonzero_exit(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=2, stdout="", stderr="boom")
    monkeypatch.setattr("last30days_adapter.subprocess.run", lambda *a, **kw: completed)

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
    monkeypatch.setattr("last30days_adapter.subprocess.run", raise_timeout)

    result = run_query("topic", vendor_path=vendor)
    assert "timed out" in result["error"]
    assert result["items"] == []


def test_run_query_handles_malformed_json(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout="not json{", stderr="")
    monkeypatch.setattr("last30days_adapter.subprocess.run", lambda *a, **kw: completed)

    result = run_query("topic", vendor_path=vendor)
    assert "Failed to parse" in result["error"]
    assert result["items"] == []


def test_run_query_emit_text_returns_raw_output(tmp_path, monkeypatch):
    from last30days_adapter import run_query

    vendor = _make_vendor(tmp_path)
    monkeypatch.setattr("last30days_adapter._find_python", lambda: "python3")
    completed = MagicMock(returncode=0, stdout="raw markdown report", stderr="")
    monkeypatch.setattr("last30days_adapter.subprocess.run", lambda *a, **kw: completed)

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
