"""Tests for the persistence module."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def test_save_briefing_creates_json(data_dir, sample_themes):
    from persistence import save_briefing

    result = save_briefing(
        sector="devtools",
        themes=sample_themes,
        retrieval_path="websearch",
        date="2026-04-09",
        data_dir=data_dir,
    )
    json_path = data_dir / "briefings" / "2026-04-09-devtools.json"
    assert json_path.exists()
    briefing = json.loads(json_path.read_text())
    assert briefing["date"] == "2026-04-09"
    assert briefing["sector"] == "devtools"
    assert briefing["retrieval_path"] == "websearch"
    assert len(briefing["themes"]) == 2
    assert result["saved"] == str(json_path)


def test_load_briefing_returns_data(data_dir, sample_themes):
    from persistence import load_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_briefing("devtools", "2026-04-09", data_dir)
    assert result is not None
    assert result["sector"] == "devtools"
    assert len(result["themes"]) == 2


def test_load_briefing_missing_returns_none(data_dir):
    from persistence import load_briefing

    result = load_briefing("devtools", "2099-01-01", data_dir)
    assert result is None


def test_load_previous_finds_earlier(data_dir, sample_themes):
    from persistence import load_previous_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-02", data_dir)
    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_previous_briefing("devtools", before_date="2026-04-09", data_dir=data_dir)
    assert result is not None
    assert result["date"] == "2026-04-02"


def test_load_previous_no_earlier_returns_none(data_dir, sample_themes):
    from persistence import load_previous_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_previous_briefing("devtools", before_date="2026-04-01", data_dir=data_dir)
    assert result is None


def test_compute_diff_new_themes(data_dir):
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 6},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 7},
            {"name": "Rust Build Tools", "momentum": 5},
        ],
    }
    diff = compute_diff(current, previous)
    assert diff["previous_date"] == "2026-04-02"
    new_names = [t["name"] for t in diff["new_themes"]]
    assert "Rust Build Tools" in new_names


def test_compute_diff_fading_themes():
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "WebAssembly Runtimes", "momentum": 7},
            {"name": "AI Code Review", "momentum": 6},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 7},
        ],
    }
    diff = compute_diff(current, previous)
    fading_names = [t["name"] for t in diff["fading_themes"]]
    assert "WebAssembly Runtimes" in fading_names


def test_compute_diff_persistent_themes_with_index():
    from persistence import compute_diff
    previous = {"date": "2026-04-23", "sector": "devtools",
                "themes": [{"name": "AI Code Review", "momentum": 7}]}
    current = {"date": "2026-04-30", "sector": "devtools",
               "themes": [
                   {"name": "AI Code Review", "momentum": 7},
                   {"name": "Brand New", "momentum": 6},
               ]}
    theme_index = {
        "AI Code Review": {"appearances": 4, "momentum_history": [6, 6, 7, 7]},
        "Brand New":      {"appearances": 1, "momentum_history": [6]},
    }
    diff = compute_diff(current, previous, theme_index=theme_index)
    persistent_names = [t["name"] for t in diff["persistent_themes"]]
    assert "AI Code Review" in persistent_names
    assert "Brand New" not in persistent_names


def test_compute_diff_persistent_default_empty_without_index():
    """Backward compat: omitting theme_index yields empty persistent_themes."""
    from persistence import compute_diff
    previous = {"date": "2026-04-23", "sector": "x",
                "themes": [{"name": "A", "momentum": 5}]}
    current = {"date": "2026-04-30", "sector": "x",
               "themes": [{"name": "A", "momentum": 5}]}
    diff = compute_diff(current, previous)
    assert diff["persistent_themes"] == []


def test_compute_diff_persistent_excludes_themes_not_in_current():
    """A theme persistent in the index but absent from current must NOT appear."""
    from persistence import compute_diff
    previous = {"date": "2026-04-23", "sector": "x",
                "themes": [{"name": "Old Persistent", "momentum": 7}]}
    current = {"date": "2026-04-30", "sector": "x",
               "themes": [{"name": "Other", "momentum": 6}]}
    theme_index = {
        "Old Persistent": {"appearances": 5, "momentum_history": [6] * 5},
        "Other":          {"appearances": 1, "momentum_history": [6]},
    }
    diff = compute_diff(current, previous, theme_index=theme_index)
    assert diff["persistent_themes"] == []


def test_cli_diff_loads_theme_index_for_persistent(data_dir, sample_themes):
    """CLI `diff` command should load theme_index.json and emit persistent."""
    from persistence import save_briefing, update_theme_index
    save_briefing("devtools", sample_themes, "websearch", "2026-04-23", data_dir)
    save_briefing("devtools", sample_themes, "websearch", "2026-04-30", data_dir)
    for d in ["2026-04-16", "2026-04-23", "2026-04-30"]:
        update_theme_index(sample_themes, "devtools", d, data_dir)

    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), "diff",
         "--sector", "devtools", "--date", "2026-04-30",
         "--data-dir", str(data_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    diff = json.loads(result.stdout)
    persistent_names = [t["name"] for t in diff.get("persistent_themes", [])]
    assert "AI-Powered Code Review" in persistent_names


def test_compute_diff_accelerating_themes():
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 5},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 8},
        ],
    }
    diff = compute_diff(current, previous)
    accel_names = [t["name"] for t in diff["accelerating_themes"]]
    assert "AI Code Review" in accel_names


def test_normalize_theme_name_lowercases_and_collapses_whitespace():
    from persistence import _normalize_theme_name
    assert _normalize_theme_name("AI Code Review") == "ai code review"
    assert _normalize_theme_name("ai code review") == "ai code review"
    assert _normalize_theme_name("  AI   Code  Review  ") == "ai code review"


def test_compute_diff_matches_case_insensitively():
    """Same theme written with different case must match across weeks."""
    from persistence import compute_diff
    previous = {"date": "2026-04-23", "sector": "x",
                "themes": [{"name": "AI Code Review", "momentum": 5}]}
    current = {"date": "2026-04-30", "sector": "x",
               "themes": [{"name": "ai code review", "momentum": 8}]}
    diff = compute_diff(current, previous)
    assert diff["new_themes"] == []
    assert diff["fading_themes"] == []
    assert [t["name"] for t in diff["accelerating_themes"]] == ["ai code review"]


def test_compute_diff_matches_whitespace_insensitively():
    from persistence import compute_diff
    previous = {"date": "2026-04-23", "sector": "x",
                "themes": [{"name": "AI  Code  Review", "momentum": 6}]}
    current = {"date": "2026-04-30", "sector": "x",
               "themes": [{"name": "AI Code Review", "momentum": 6}]}
    diff = compute_diff(current, previous)
    assert diff["new_themes"] == []
    assert diff["fading_themes"] == []


def test_update_theme_index_new_theme(data_dir, sample_themes):
    from persistence import update_theme_index

    index = update_theme_index(sample_themes, "devtools", "2026-04-09", data_dir)
    assert "AI-Powered Code Review" in index
    entry = index["AI-Powered Code Review"]
    assert entry["first_seen"] == "2026-04-09"
    assert entry["last_seen"] == "2026-04-09"
    assert entry["appearances"] == 1
    assert entry["momentum_history"] == [8]
    assert entry["peak_momentum"] == 8


def test_update_theme_index_existing_theme(data_dir, sample_themes):
    from persistence import update_theme_index

    update_theme_index(sample_themes, "devtools", "2026-04-02", data_dir)
    updated_themes = [{"name": "AI-Powered Code Review", "momentum": 9}]
    index = update_theme_index(updated_themes, "devtools", "2026-04-09", data_dir)
    entry = index["AI-Powered Code Review"]
    assert entry["first_seen"] == "2026-04-02"
    assert entry["last_seen"] == "2026-04-09"
    assert entry["appearances"] == 2
    assert entry["momentum_history"] == [8, 9]
    assert entry["peak_momentum"] == 9


def test_save_markdown(data_dir):
    from persistence import save_markdown

    content = "# Test Briefing\n\nSome content here."
    result = save_markdown("themes", "agent-evals", content, "2026-04-09", data_dir)
    md_path = data_dir / "themes" / "2026-04-09-agent-evals.md"
    assert md_path.exists()
    assert md_path.read_text() == content
    assert result["saved"] == str(md_path)


def test_validate_date_accepts_iso_date():
    from persistence import _validate_date
    _validate_date("2026-04-16", "date")  # should not raise


def test_validate_date_rejects_path_traversal():
    from persistence import _validate_date

    with pytest.raises(SystemExit):
        _validate_date("../../etc/passwd", "date")


def test_validate_date_rejects_wrong_format():
    from persistence import _validate_date

    for bad in ["2026/04/16", "20260416", "April 16", ""]:
        with pytest.raises(SystemExit):
            _validate_date(bad, "date")


def test_cli_load_briefing_rejects_traversal_date(data_dir):
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), "load-briefing",
         "--sector", "devtools",
         "--date", "../../etc/passwd",
         "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Invalid date" in result.stdout


def test_normalize_company_name_lowercases():
    from persistence import _normalize_company_name
    assert _normalize_company_name("MintMCP") == "mintmcp"


def test_normalize_company_name_strips_legal_suffix():
    from persistence import _normalize_company_name
    assert _normalize_company_name("Anthropic, Inc.") == "anthropic"
    assert _normalize_company_name("Datadog Inc") == "datadog"
    assert _normalize_company_name("Acme Corp.") == "acme"
    assert _normalize_company_name("Foo LLC") == "foo"


def test_normalize_company_name_strips_parenthetical():
    from persistence import _normalize_company_name
    assert _normalize_company_name("Anysphere (Cursor)") == "anysphere"


def test_normalize_company_name_strips_domain_suffix():
    from persistence import _normalize_company_name
    assert _normalize_company_name("Vercel.com") == "vercel"
    assert _normalize_company_name("baserock.ai") == "baserock"


def test_normalize_company_name_collapses_whitespace():
    from persistence import _normalize_company_name
    assert _normalize_company_name("  Grafana   Labs  ") == "grafana labs"


def test_update_company_index_creates_entry(data_dir, sample_companies):
    from persistence import update_company_index

    index = update_company_index(
        sample_companies, sector="devtools", date="2026-04-16", data_dir=data_dir
    )
    assert "mintmcp" in index
    entry = index["mintmcp"]
    assert entry["display_name"] == "MintMCP"
    assert entry["first_seen"] == "2026-04-16"
    assert entry["last_seen"] == "2026-04-16"
    assert entry["weeks_seen"] == 1
    assert entry["missed_weeks"] == 0
    assert entry["sectors"] == ["devtools"]
    assert entry["themes_history"] == ["MCP Agent Infrastructure"]


def test_update_company_index_increments_on_repeat(data_dir, sample_companies):
    from persistence import update_company_index

    update_company_index(sample_companies, "devtools", "2026-04-09", data_dir)
    index = update_company_index(sample_companies, "devtools", "2026-04-16", data_dir)

    entry = index["mintmcp"]
    assert entry["weeks_seen"] == 2
    assert entry["first_seen"] == "2026-04-09"
    assert entry["last_seen"] == "2026-04-16"
    assert entry["missed_weeks"] == 0


def test_update_company_index_tracks_missed_weeks(data_dir, sample_companies):
    """A company absent from week N+1 should have missed_weeks > 0 in the
    intermediate index, then reset to 0 when it next appears."""
    from persistence import update_company_index

    update_company_index(sample_companies, "devtools", "2026-04-02", data_dir)

    # Week of 2026-04-09 — only sample_companies[1] (CodeRabbit) seen
    intermediate = update_company_index(
        [sample_companies[1]], "devtools", "2026-04-09", data_dir
    )
    # MintMCP missed this week — gap should be visible in the intermediate state
    assert intermediate["mintmcp"]["missed_weeks"] == 1
    assert intermediate["coderabbit"]["missed_weeks"] == 0

    # Week of 2026-04-16 — MintMCP returns
    final = update_company_index(sample_companies, "devtools", "2026-04-16", data_dir)
    # On re-appearance, missed_weeks resets to 0
    assert final["mintmcp"]["missed_weeks"] == 0
    assert final["coderabbit"]["missed_weeks"] == 0


def test_update_company_index_dedupes_by_normalized_name(data_dir):
    from persistence import update_company_index

    companies_a = [{"name": "Anysphere (Cursor)", "primary_theme": "Coding"}]
    companies_b = [{"name": "anysphere", "primary_theme": "Coding"}]

    update_company_index(companies_a, "devtools", "2026-04-09", data_dir)
    index = update_company_index(companies_b, "devtools", "2026-04-16", data_dir)

    assert "anysphere" in index
    assert index["anysphere"]["weeks_seen"] == 2


def test_update_company_index_appends_new_themes_only(data_dir):
    from persistence import update_company_index

    week_one = [{"name": "CodeRabbit", "primary_theme": "AI Code Review"}]
    week_two = [{"name": "CodeRabbit", "primary_theme": "Agentic Coding"}]

    update_company_index(week_one, "devtools", "2026-04-09", data_dir)
    index = update_company_index(week_two, "devtools", "2026-04-16", data_dir)

    assert index["coderabbit"]["themes_history"] == [
        "AI Code Review", "Agentic Coding"
    ]


def test_load_company_index_returns_data(data_dir, sample_companies):
    from persistence import load_company_index, update_company_index

    update_company_index(sample_companies, "devtools", "2026-04-16", data_dir)
    index = load_company_index(data_dir)
    assert "mintmcp" in index
    assert index["mintmcp"]["weeks_seen"] == 1


def test_load_company_index_missing_returns_empty(data_dir):
    from persistence import load_company_index

    assert load_company_index(data_dir) == {}


def test_compute_company_diff_new_companies():
    from persistence import compute_company_diff

    previous = [{"name": "CodeRabbit", "primary_theme": "AI Code Review"}]
    current = [
        {"name": "CodeRabbit", "primary_theme": "AI Code Review"},
        {"name": "MintMCP", "primary_theme": "MCP Infra"},
    ]
    diff = compute_company_diff(current, previous)
    assert [c["name"] for c in diff["new_companies"]] == ["MintMCP"]
    assert diff["faded_companies"] == []


def test_compute_company_diff_faded_companies():
    from persistence import compute_company_diff

    previous = [
        {"name": "CodeRabbit", "primary_theme": "AI Code Review"},
        {"name": "OldCo", "primary_theme": "WebAssembly"},
    ]
    current = [{"name": "CodeRabbit", "primary_theme": "AI Code Review"}]
    diff = compute_company_diff(current, previous)
    assert [c["name"] for c in diff["faded_companies"]] == ["OldCo"]
    assert diff["new_companies"] == []


def test_compute_company_diff_uses_normalization():
    from persistence import compute_company_diff

    previous = [{"name": "Anysphere (Cursor)", "primary_theme": "Coding"}]
    current = [{"name": "anysphere", "primary_theme": "Coding"}]
    diff = compute_company_diff(current, previous)
    assert diff["new_companies"] == []
    assert diff["faded_companies"] == []


def test_compute_company_diff_handles_empty_previous():
    from persistence import compute_company_diff

    current = [{"name": "MintMCP", "primary_theme": "MCP"}]
    diff = compute_company_diff(current, [])
    assert [c["name"] for c in diff["new_companies"]] == ["MintMCP"]
    assert diff["faded_companies"] == []


def test_compute_company_tag_new():
    from persistence import compute_company_tag
    assert compute_company_tag("MintMCP", index={}) == "NEW"


def test_compute_company_tag_persistent():
    from persistence import compute_company_tag
    index = {"coderabbit": {"weeks_seen": 4, "missed_weeks": 0}}
    assert compute_company_tag("CodeRabbit", index) == "PERSISTENT"


def test_compute_company_tag_returning():
    from persistence import compute_company_tag
    index = {"oldco": {"weeks_seen": 2, "missed_weeks": 3}}
    assert compute_company_tag("OldCo", index) == "RETURNING"


def test_compute_company_tag_default_none():
    """Seen this week and once before, no missed weeks → no special tag."""
    from persistence import compute_company_tag
    index = {"foo": {"weeks_seen": 2, "missed_weeks": 0}}
    assert compute_company_tag("Foo", index) is None


def test_compute_company_tag_uses_normalized_lookup():
    from persistence import compute_company_tag
    index = {"anysphere": {"weeks_seen": 5, "missed_weeks": 0}}
    assert compute_company_tag("Anysphere (Cursor)", index) == "PERSISTENT"


def test_compute_company_tag_new_requires_old_snapshot(data_dir, sample_companies):
    """Regression: tags must be computed from the PRE-update index snapshot.

    If we update first and then compute tags, the entry will exist (just
    inserted with weeks_seen=1) and NEW won't fire. This test pins the
    snapshot-then-update ordering required by SKILL.md Step 9.
    """
    from persistence import compute_company_tag, load_company_index, update_company_index

    snapshot = load_company_index(data_dir)
    update_company_index(sample_companies, "devtools", "2026-04-16", data_dir)
    after = load_company_index(data_dir)

    assert compute_company_tag("MintMCP", snapshot) == "NEW"
    assert compute_company_tag("MintMCP", after) is None


def test_compute_theme_tag_new():
    from persistence import compute_theme_tag
    assert compute_theme_tag("MCP Infra", momentum=8, theme_index={}) == "NEW"


def test_compute_theme_tag_accelerating():
    from persistence import compute_theme_tag
    theme_index = {
        "AI Testing": {
            "appearances": 2,
            "momentum_history": [5, 6],
            "peak_momentum": 6,
        }
    }
    # current momentum 8 vs previous 6 → +2 jump
    assert compute_theme_tag("AI Testing", momentum=8, theme_index=theme_index) == "ACCELERATING"


def test_compute_theme_tag_persistent():
    from persistence import compute_theme_tag
    theme_index = {
        "AI Code Review": {
            "appearances": 3,
            "momentum_history": [7, 7, 7],
            "peak_momentum": 7,
        }
    }
    assert compute_theme_tag("AI Code Review", momentum=7, theme_index=theme_index) == "PERSISTENT"


def test_compute_theme_tag_default_none():
    from persistence import compute_theme_tag
    theme_index = {
        "Foo": {
            "appearances": 1,
            "momentum_history": [5],
            "peak_momentum": 5,
        }
    }
    assert compute_theme_tag("Foo", momentum=6, theme_index=theme_index) is None


def test_cli_compute_tags(data_dir):
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    payload = json.dumps({
        "themes": [{"name": "MCP Infra", "momentum": 9}],
        "companies": [{"name": "MintMCP", "primary_theme": "MCP Infra"}],
        "theme_index": {},
        "company_index": {},
    })
    result = subprocess.run(
        ["python3", str(script), "compute-tags",
         "--data-dir", str(data_dir)],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["themes"][0]["tag"] == "NEW"
    assert out["companies"][0]["tag"] == "NEW"


def test_save_briefing_persists_companies(data_dir, sample_themes, sample_companies):
    from persistence import save_briefing, load_briefing

    save_briefing(
        sector="devtools",
        themes=sample_themes,
        retrieval_path="websearch",
        date="2026-04-16",
        data_dir=data_dir,
        companies=sample_companies,
    )
    loaded = load_briefing("devtools", "2026-04-16", data_dir)
    assert "companies" in loaded
    assert len(loaded["companies"]) == 2
    assert loaded["companies"][0]["name"] == "MintMCP"


def test_save_briefing_companies_default_empty(data_dir, sample_themes):
    """Old call sites without companies arg still work; companies defaults to []."""
    from persistence import save_briefing, load_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-16", data_dir)
    loaded = load_briefing("devtools", "2026-04-16", data_dir)
    assert loaded["companies"] == []


def test_cli_save_briefing_accepts_object_payload(data_dir):
    """The CLI should accept {themes:[...], companies:[...]} on stdin."""
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    payload = json.dumps({
        "themes": [{"name": "MCP Infra", "momentum": 9}],
        "companies": [{"name": "MintMCP", "primary_theme": "MCP Infra"}],
    })
    result = subprocess.run(
        ["python3", str(script), "save-briefing",
         "--sector", "devtools",
         "--retrieval-path", "websearch",
         "--date", "2026-04-16",
         "--data-dir", str(data_dir)],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    saved = json.loads((data_dir / "briefings" / "2026-04-16-devtools.json").read_text())
    assert len(saved["themes"]) == 1
    assert len(saved["companies"]) == 1
    assert saved["companies"][0]["name"] == "MintMCP"


def test_cli_save_briefing_still_accepts_bare_list(data_dir):
    """Backward compat: old callers piping a bare list still work."""
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    payload = json.dumps([{"name": "MCP Infra", "momentum": 9}])
    result = subprocess.run(
        ["python3", str(script), "save-briefing",
         "--sector", "devtools",
         "--retrieval-path", "websearch",
         "--date", "2026-04-16",
         "--data-dir", str(data_dir)],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    saved = json.loads((data_dir / "briefings" / "2026-04-16-devtools.json").read_text())
    assert len(saved["themes"]) == 1
    assert saved["companies"] == []


def test_cli_update_company_index(data_dir):
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    payload = json.dumps([
        {"name": "MintMCP", "primary_theme": "MCP Infra"}
    ])
    result = subprocess.run(
        ["python3", str(script), "update-company-index",
         "--sector", "devtools",
         "--date", "2026-04-16",
         "--data-dir", str(data_dir)],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "mintmcp" in out
    assert out["mintmcp"]["weeks_seen"] == 1


def test_cli_load_company_index_empty(data_dir):
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), "load-company-index",
         "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


@pytest.mark.parametrize("command,extra_args", [
    ("save-briefing", ["--sector", "devtools"]),
    ("update-index", ["--sector", "devtools"]),
    ("update-company-index", ["--sector", "devtools"]),
    ("company-diff", []),
    ("compute-tags", []),
    ("save-markdown", ["--subdir", "themes", "--slug", "foo"]),
])
def test_cli_malformed_stdin_returns_structured_error(data_dir, command, extra_args):
    """Every command that reads stdin must respond to malformed JSON with
    {"error": ...} on stdout and exit code 1, not a Python traceback.

    save-markdown reads text (not JSON) on stdin, so it tolerates any input —
    we exclude it from the JSON-error contract and instead assert it does
    NOT crash on arbitrary bytes.
    """
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), command,
         *extra_args, "--data-dir", str(data_dir)],
        input="not json {{{",
        capture_output=True, text=True,
    )
    if command == "save-markdown":
        # save-markdown takes raw text, so non-JSON is fine; just no crash.
        assert "Traceback" not in result.stderr
        return

    assert result.returncode == 1, f"command={command} stderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert "error" in payload
    assert "json" in payload["error"].lower() or "invalid" in payload["error"].lower()
    assert "Traceback" not in result.stderr


def test_cli_company_diff(data_dir):
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    payload = json.dumps({
        "current": [{"name": "MintMCP", "primary_theme": "MCP"}],
        "previous": [{"name": "OldCo", "primary_theme": "Wasm"}],
    })
    result = subprocess.run(
        ["python3", str(script), "company-diff",
         "--data-dir", str(data_dir)],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    diff = json.loads(result.stdout)
    assert [c["name"] for c in diff["new_companies"]] == ["MintMCP"]
    assert [c["name"] for c in diff["faded_companies"]] == ["OldCo"]


# --- _slugify and save-markdown --name ---

def test_slugify_basic_lowercases_and_hyphenates():
    from persistence import _slugify
    assert _slugify("AI Code Review") == "ai-code-review"


def test_slugify_strips_punctuation():
    from persistence import _slugify
    assert _slugify("Anysphere (Cursor)") == "anysphere-cursor"
    assert _slugify("Hello, world!") == "hello-world"


def test_slugify_collapses_runs_of_separators():
    from persistence import _slugify
    assert _slugify("AI -- Code   Review") == "ai-code-review"


def test_slugify_strips_leading_and_trailing_separators():
    from persistence import _slugify
    assert _slugify("--foo--") == "foo"
    assert _slugify("  hello  ") == "hello"


def test_slugify_keeps_digits_and_hyphens():
    from persistence import _slugify
    assert _slugify("GPT-4 Turbo 2024") == "gpt-4-turbo-2024"


def test_slugify_empty_input_returns_empty():
    from persistence import _slugify
    assert _slugify("") == ""
    assert _slugify("!!!") == ""


def test_slugify_output_passes_validate_slug():
    """Slugify output must satisfy the existing path validator."""
    from persistence import _slugify, _validate_slug
    for text in ["Anysphere (Cursor)", "AI / ML Tools", "Foo & Bar, Inc."]:
        slug = _slugify(text)
        if slug:
            _validate_slug(slug, "slug")  # must not raise


def test_cli_save_markdown_accepts_name(data_dir):
    """`--name` should be slugified internally and produce a valid file."""
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), "save-markdown",
         "--subdir", "themes",
         "--name", "Anysphere (Cursor)",
         "--date", "2026-04-16",
         "--data-dir", str(data_dir)],
        input="# content",
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    expected = data_dir / "themes" / "2026-04-16-anysphere-cursor.md"
    assert expected.exists(), f"Expected {expected}"


def test_cli_save_markdown_rejects_both_name_and_slug(data_dir):
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), "save-markdown",
         "--subdir", "themes",
         "--slug", "foo",
         "--name", "Foo",
         "--data-dir", str(data_dir)],
        input="# content",
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "exactly one of --slug or --name" in result.stdout


def test_cli_save_markdown_rejects_name_that_slugifies_to_empty(data_dir):
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), "save-markdown",
         "--subdir", "themes",
         "--name", "!!!",
         "--data-dir", str(data_dir)],
        input="# content",
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "name" in result.stdout.lower() or "slug" in result.stdout.lower()


def test_cli_save_markdown_still_accepts_slug(data_dir):
    """Backward compat: existing --slug callers must still work."""
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), "save-markdown",
         "--subdir", "themes",
         "--slug", "agent-evals",
         "--date", "2026-04-16",
         "--data-dir", str(data_dir)],
        input="# content",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert (data_dir / "themes" / "2026-04-16-agent-evals.md").exists()
