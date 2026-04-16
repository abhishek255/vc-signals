# Phase 1: Radar Output Flip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flip the VC Signals weekly scan from theme-centric to company-centric output, with companies as first-class data and a top-level company radar table as the centerpiece.

**Architecture:** Extend `persistence.py` with a parallel company-tracking layer (index, diff, tags) that mirrors the existing theme-tracking layer. Keep schema changes additive (companies field is new, themes field unchanged) so existing tests and old briefings continue to work. Update `SKILL.md` synthesis steps to dedupe companies across themes, target 30-50 per scan, and emit a new radar-format markdown template. Fix two pre-existing security/hygiene bugs in the same change since we're touching the file.

**Tech Stack:** Python 3.12+, pytest, JSON storage, no new dependencies.

---

## File Map

| File | Type | Responsibility |
|------|------|---------------|
| `.gitignore` | Modify | Stop tracking real data files that slipped past existing rules |
| `.claude/skills/vc-signals/scripts/persistence.py` | Modify | Add company normalization, index, diff, tagging; harden `--date` parsing |
| `.claude/skills/vc-signals/tests/test_persistence.py` | Modify | Add tests for all new helpers |
| `.claude/skills/vc-signals/tests/conftest.py` | Modify | Add `sample_companies` fixture |
| `.claude/skills/vc-signals/data/companies/company_index.json` | Create | Initial empty index file (committed) |
| `.claude/skills/vc-signals/SKILL.md` | Modify | New `radar` mode alias, updated Steps 6-9, new output template |

**Decomposition rationale:** All persistence concerns stay in `persistence.py` for Phase 1. Companies *will* grow their own module in Phase 2 (enrichment fetchers), but extracting now is YAGNI. Section comments and docstrings will keep navigation easy at ~450 lines.

---

## Conventions Used in This Plan

- **Paths are absolute from repo root** (`/Users/abhishekgarg/personalProject/`).
- **Test commands assume CWD is `.claude/skills/vc-signals/`** unless stated otherwise.
- **Run pytest with `python3 -m pytest`** from the skill directory.
- **Commit after every passing test set** — one logical change per commit.
- **Function names are final.** If a later task references `update_company_index`, the earlier task that creates it must also call it `update_company_index`.

---

## Phase A — Data Hygiene & Security Fixes

These are blockers because (1) we're about to write more data files and need clean ignores in place, and (2) we're touching `persistence.py` so this is the cheapest moment to harden it.

### Task 1: Untrack real data files that slipped into git history

**Files:**
- Modify: `.gitignore`
- Untrack (do not delete from disk): `.claude/skills/vc-signals/data/briefings/2026-04-10-devtools.json`
- Untrack (do not delete from disk): `.claude/skills/vc-signals/data/history/theme_index.json`

- [ ] **Step 1: Verify the files are currently tracked**

Run from repo root:
```bash
git ls-files | grep -E "(2026-04-10-devtools.json|theme_index.json)"
```
Expected: both file paths print. If neither prints, skip Task 1 entirely.

- [ ] **Step 2: Remove them from the index without deleting from disk**

```bash
git rm --cached .claude/skills/vc-signals/data/briefings/2026-04-10-devtools.json
git rm --cached .claude/skills/vc-signals/data/history/theme_index.json
```

- [ ] **Step 3: Verify .gitignore already covers them**

The existing `.gitignore` already has rules for `data/briefings/*.json` and `data/history/theme_index.json`. Confirm:
```bash
git check-ignore -v .claude/skills/vc-signals/data/briefings/2026-04-10-devtools.json
git check-ignore -v .claude/skills/vc-signals/data/history/theme_index.json
```
Expected: both lines print a matching rule from `.gitignore`. If they don't, add the missing rule to `.gitignore`.

- [ ] **Step 4: Add company_index.json to .gitignore**

Edit `.gitignore`. Find the line `.claude/skills/vc-signals/data/history/theme_index.json` and add immediately after it:
```
.claude/skills/vc-signals/data/companies/company_index.json
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git add -u .claude/skills/vc-signals/data/
git commit -m "chore: untrack real briefing/index data, ignore company_index"
```

---

### Task 2: Harden `--date` against path traversal in persistence.py

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py:195-199` (add a date validator near `_validate_slug`)
- Modify: `.claude/skills/vc-signals/scripts/persistence.py:212-265` (call validator everywhere `args["date"]` or `args["before"]` is used)
- Test: `.claude/skills/vc-signals/tests/test_persistence.py` (new test cases)

**Why this is here:** `--date` flows directly into `f"{date}-{sector}.json"` filenames. A value like `../../../../etc/passwd` would write outside the data dir. Sector is already validated by `_validate_slug`; date is not.

- [ ] **Step 1: Write the failing test (date validator)**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 2: Run the tests, expect failure**

From `.claude/skills/vc-signals/`:
```bash
python3 -m pytest tests/test_persistence.py::test_validate_date_accepts_iso_date -v
```
Expected: ImportError or AttributeError on `_validate_date` — the function doesn't exist yet.

- [ ] **Step 3: Implement `_validate_date` in persistence.py**

In `persistence.py`, immediately after `_validate_slug` (around line 199), add:
```python
def _validate_date(value: str, name: str) -> None:
    """Validate that a value is an ISO date (YYYY-MM-DD).

    Used to prevent path traversal via the --date or --before CLI args,
    which flow directly into filenames like f"{date}-{sector}.json".
    """
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        print(json.dumps({"error": f"Invalid {name}: '{value}'. Expected YYYY-MM-DD."}))
        sys.exit(1)
```

- [ ] **Step 4: Run the date-validator tests, expect pass**

```bash
python3 -m pytest tests/test_persistence.py -k validate_date -v
```
Expected: 3 passed.

- [ ] **Step 5: Wire the validator into the CLI handlers**

In `persistence.py`, find each CLI branch in `_cli_main()` that reads a date arg. Add `_validate_date` calls before the date is used.

For `save-briefing` (around line 212), after `_validate_slug(args["sector"], "sector")`:
```python
        if "date" in args:
            _validate_date(args["date"], "date")
```

For `load-briefing` (around line 228), after `_require_args(args, "sector", "date")`:
```python
        _validate_slug(args["sector"], "sector")
        _validate_date(args["date"], "date")
```

For `load-previous` (around line 233), after `_require_args(args, "sector", "before")`:
```python
        _validate_slug(args["sector"], "sector")
        _validate_date(args["before"], "before")
```

For `diff` (around line 238), same pattern as `load-briefing`.

For `update-index` (around line 247), after `_validate_slug(args["sector"], "sector")`:
```python
        if "date" in args:
            _validate_date(args["date"], "date")
```

For `save-markdown` (around line 257), after the existing slug validations:
```python
        if "date" in args:
            _validate_date(args["date"], "date")
```

- [ ] **Step 6: Add an end-to-end CLI test for the traversal case**

Append to `tests/test_persistence.py`:
```python
import subprocess


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
```

- [ ] **Step 7: Run the full persistence test suite, expect green**

```bash
python3 -m pytest tests/test_persistence.py -v
```
Expected: all tests pass, including the new ones.

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "fix: validate --date arg in persistence CLI to prevent path traversal"
```

---

## Phase B — Company-as-First-Class Data Model

### Task 3: Add `_normalize_company_name` helper

**Why:** "Anysphere (Cursor)", "Cursor", "cursor.com" should all key to the same company. Without normalization, the company index will fragment on first contact with reality.

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py` (add helper near `_validate_slug`)
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 2: Run, expect ImportError**

```bash
python3 -m pytest tests/test_persistence.py -k normalize_company_name -v
```
Expected: ImportError — function doesn't exist.

- [ ] **Step 3: Implement `_normalize_company_name`**

In `persistence.py`, after `_validate_date`, add:
```python
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
```

- [ ] **Step 4: Run, expect all 5 tests pass**

```bash
python3 -m pytest tests/test_persistence.py -k normalize_company_name -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add _normalize_company_name helper for cross-theme dedup"
```

---

### Task 4: Add `sample_companies` fixture

**Files:**
- Modify: `.claude/skills/vc-signals/tests/conftest.py`

- [ ] **Step 1: Add the fixture**

In `tests/conftest.py`, after the `sample_themes` fixture, add:
```python
@pytest.fixture
def sample_companies() -> list[dict]:
    """Sample company list (post-flip schema) for testing."""
    return [
        {
            "name": "MintMCP",
            "primary_theme": "MCP Agent Infrastructure",
            "secondary_themes": [],
            "tag": None,
            "why_on_radar": "First SOC2-compliant MCP gateway",
            "evidence_url": "https://example.com/mintmcp",
            "stage": None,
            "raised": None,
            "headcount": None,
            "founders": None,
        },
        {
            "name": "CodeRabbit",
            "primary_theme": "AI-Powered Code Review",
            "secondary_themes": ["Agentic Coding Tools"],
            "tag": None,
            "why_on_radar": "2M repos, 13M PRs reviewed",
            "evidence_url": "https://example.com/coderabbit",
            "stage": None,
            "raised": None,
            "headcount": None,
            "founders": None,
        },
    ]
```

- [ ] **Step 2: Verify pytest still discovers fixtures**

```bash
python3 -m pytest tests/ --collect-only -q
```
Expected: same number of tests as before (no errors).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/vc-signals/tests/conftest.py
git commit -m "test: add sample_companies fixture for radar-format tests"
```

---

### Task 5: Implement `update_company_index`

**Why:** Mirror of `update_theme_index`. Tracks first-seen, last-seen, weeks-seen, themes history, and missed-weeks per company. This is what powers the "NEW This Week" tag and "Faded Off" section.

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py` (add function after `update_theme_index`)
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_persistence.py`:
```python
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
    """A company seen in week N but not in N+1 should have missed_weeks > 0
    when next seen."""
    from persistence import update_company_index

    update_company_index(sample_companies, "devtools", "2026-04-02", data_dir)
    # Week of 2026-04-09 — only sample_companies[1] (CodeRabbit) seen
    update_company_index([sample_companies[1]], "devtools", "2026-04-09", data_dir)
    # Week of 2026-04-16 — MintMCP returns
    index = update_company_index(sample_companies, "devtools", "2026-04-16", data_dir)

    assert index["mintmcp"]["missed_weeks"] == 1
    assert index["coderabbit"]["missed_weeks"] == 0


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
```

- [ ] **Step 2: Run, expect all 5 to fail with ImportError**

```bash
python3 -m pytest tests/test_persistence.py -k update_company_index -v
```
Expected: 5 errors / failures.

- [ ] **Step 3: Implement `update_company_index`**

In `persistence.py`, after `update_theme_index` (around line 163), add:
```python
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
```

- [ ] **Step 4: Run the new tests, expect all pass**

```bash
python3 -m pytest tests/test_persistence.py -k update_company_index -v
```
Expected: 5 passed.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
python3 -m pytest tests/ -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add update_company_index for week-over-week company tracking"
```

---

### Task 6: Implement `load_company_index`

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py`
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_persistence.py`:
```python
def test_load_company_index_returns_data(data_dir, sample_companies):
    from persistence import load_company_index, update_company_index

    update_company_index(sample_companies, "devtools", "2026-04-16", data_dir)
    index = load_company_index(data_dir)
    assert "mintmcp" in index
    assert index["mintmcp"]["weeks_seen"] == 1


def test_load_company_index_missing_returns_empty(data_dir):
    from persistence import load_company_index

    assert load_company_index(data_dir) == {}
```

- [ ] **Step 2: Run, expect ImportError**

```bash
python3 -m pytest tests/test_persistence.py -k load_company_index -v
```

- [ ] **Step 3: Implement `load_company_index`**

In `persistence.py`, after `update_company_index`, add:
```python
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
```

- [ ] **Step 4: Run, expect both tests pass**

```bash
python3 -m pytest tests/test_persistence.py -k load_company_index -v
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add load_company_index"
```

---

### Task 7: Implement `compute_company_diff`

**Why:** Drives the "New To Radar This Week" and "Faded Off Radar" sections. Standalone helper so it's testable without coupling to briefing files.

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py`
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 2: Run, expect 4 failures**

```bash
python3 -m pytest tests/test_persistence.py -k compute_company_diff -v
```

- [ ] **Step 3: Implement `compute_company_diff`**

In `persistence.py`, after `compute_diff` (around line 113), add:
```python
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
```

- [ ] **Step 4: Run, expect 4 passes**

```bash
python3 -m pytest tests/test_persistence.py -k compute_company_diff -v
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add compute_company_diff for week-over-week company changes"
```

---

### Task 8: Extend `save_briefing` (function + CLI) to accept companies

**Why:** Persist the full company list in the briefing JSON so future diffs can use it. The function signature gains an optional `companies` param. The CLI gains the ability to accept a `{"themes": [...], "companies": [...]}` payload alongside the legacy bare-list form, so SKILL.md can do one clean save call.

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py:18-43` (function)
- Modify: `.claude/skills/vc-signals/scripts/persistence.py:212-226` (CLI branch for save-briefing)
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing function-level tests**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 2: Run, expect 2 failures**

```bash
python3 -m pytest tests/test_persistence.py -k save_briefing -v
```
Expected: new tests fail (KeyError on "companies"); existing tests still pass.

- [ ] **Step 3: Update the `save_briefing` function**

Replace the existing `save_briefing` function (lines 18-43) with:
```python
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
```

- [ ] **Step 4: Run, expect function-level tests pass**

```bash
python3 -m pytest tests/test_persistence.py -k save_briefing -v
```
Expected: all green.

- [ ] **Step 5: Write the failing CLI test for the new payload shape**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 6: Run, expect the object-payload test to fail**

```bash
python3 -m pytest tests/test_persistence.py -k cli_save_briefing -v
```
Expected: `test_cli_save_briefing_accepts_object_payload` fails (themes ends up as the dict's keys or similar weirdness); `test_cli_save_briefing_still_accepts_bare_list` may already pass.

- [ ] **Step 7: Update the save-briefing CLI branch**

In `persistence.py`, find the `save-briefing` branch in `_cli_main()` (around line 212). Replace the body:
```python
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
```

- [ ] **Step 8: Run both CLI tests, expect both pass**

```bash
python3 -m pytest tests/test_persistence.py -k cli_save_briefing -v
```

- [ ] **Step 9: Run full test suite**

```bash
python3 -m pytest tests/ -v
```
Expected: all green.

- [ ] **Step 10: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: extend save_briefing (function + CLI) with companies field"
```

---

### Task 9: Add CLI commands for company operations

**Why:** SKILL.md drives everything via Bash; new commands need CLI surface. Three new commands: `update-company-index`, `load-company-index`, and `company-diff`.

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py:202-270` (in `_cli_main`)
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 2: Run, expect failures (Unknown command)**

```bash
python3 -m pytest tests/test_persistence.py -k "cli_update_company_index or cli_load_company_index or cli_company_diff" -v
```

- [ ] **Step 3: Add the three CLI branches**

In `persistence.py`, inside `_cli_main()`, immediately before the final `else` that prints "Unknown command", add:

```python
    elif command == "update-company-index":
        _require_args(args, "sector")
        _validate_slug(args["sector"], "sector")
        if "date" in args:
            _validate_date(args["date"], "date")
        if sys.stdin.isatty():
            print(json.dumps({"error": "No data piped to stdin. Pipe a JSON list of companies."}))
            sys.exit(1)
        companies = json.loads(sys.stdin.read())
        index = update_company_index(companies, args["sector"], args.get("date"), data_dir)
        print(json.dumps(index))

    elif command == "load-company-index":
        index = load_company_index(data_dir)
        print(json.dumps(index))

    elif command == "company-diff":
        if sys.stdin.isatty():
            print(json.dumps({"error": "No data piped to stdin. Pipe {current: [...], previous: [...]}."}))
            sys.exit(1)
        payload = json.loads(sys.stdin.read())
        diff = compute_company_diff(payload.get("current", []), payload.get("previous", []))
        print(json.dumps(diff))
```

- [ ] **Step 4: Run, expect 3 new CLI tests pass**

```bash
python3 -m pytest tests/test_persistence.py -k "cli_update_company_index or cli_load_company_index or cli_company_diff" -v
```

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add update-company-index, load-company-index, company-diff CLI commands"
```

---

## Phase C — Tagging Logic

### Task 10: Implement `compute_company_tag`

**Why:** Synthesis step needs to assign each company a NEW / RETURNING / PERSISTENT tag based on the index. Doing it as a pure helper keeps it testable.

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py`
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 2: Run, expect 5 failures**

```bash
python3 -m pytest tests/test_persistence.py -k compute_company_tag -v
```

- [ ] **Step 3: Implement `compute_company_tag`**

In `persistence.py`, after `compute_company_diff`, add:
```python
PERSISTENT_WEEKS_THRESHOLD = 3
RETURNING_MISSED_WEEKS_THRESHOLD = 2


def compute_company_tag(name: str, index: dict) -> str | None:
    """Return the tag for a company based on its history in the company index.

    Tags:
      - "NEW"        — never seen before (no entry in index)
      - "RETURNING"  — seen before but missed >= RETURNING_MISSED_WEEKS_THRESHOLD weeks
      - "PERSISTENT" — seen >= PERSISTENT_WEEKS_THRESHOLD consecutive weeks
      - None         — none of the above (steady but not yet persistent)

    The lookup is normalized via _normalize_company_name so display variants
    ("Anysphere (Cursor)" vs "anysphere") resolve to the same entry.

    NOTE: This must be called BEFORE update_company_index for the current week,
    because update_company_index increments weeks_seen and resets missed_weeks.
    """
    key = _normalize_company_name(name)
    entry = index.get(key)
    if entry is None:
        return "NEW"
    if entry.get("missed_weeks", 0) >= RETURNING_MISSED_WEEKS_THRESHOLD:
        return "RETURNING"
    if entry.get("weeks_seen", 0) >= PERSISTENT_WEEKS_THRESHOLD - 1:
        # weeks_seen is the count BEFORE this week's update; >= 2 means
        # this will be the 3rd consecutive week.
        return "PERSISTENT"
    return None
```

- [ ] **Step 4: Run, expect 5 passes**

```bash
python3 -m pytest tests/test_persistence.py -k compute_company_tag -v
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add compute_company_tag for NEW/RETURNING/PERSISTENT classification"
```

---

### Task 11: Implement `compute_theme_tag`

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py`
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 2: Run, expect failures**

```bash
python3 -m pytest tests/test_persistence.py -k compute_theme_tag -v
```

- [ ] **Step 3: Implement `compute_theme_tag`**

In `persistence.py`, after `compute_company_tag`, add:
```python
def compute_theme_tag(
    name: str, momentum: int, theme_index: dict
) -> str | None:
    """Return the tag for a theme based on its history in the theme index.

    Tags:
      - "NEW"           — not in index (first appearance ever)
      - "ACCELERATING"  — momentum jumped by ACCELERATING_MOMENTUM_GAIN or more vs last week
      - "PERSISTENT"    — appeared in PERSISTENT_WEEKS_THRESHOLD or more scans
      - None            — none of the above

    Theme index is keyed by exact theme name (themes don't have the
    "Anysphere (Cursor)" problem because they're already canonicalized
    during synthesis). If we hit theme-name-fragmentation in practice,
    revisit and add a normalizer.
    """
    entry = theme_index.get(name)
    if entry is None:
        return "NEW"

    history = entry.get("momentum_history", [])
    if history:
        last_momentum = history[-1]
        if momentum >= last_momentum + ACCELERATING_MOMENTUM_GAIN:
            return "ACCELERATING"

    if entry.get("appearances", 0) >= PERSISTENT_WEEKS_THRESHOLD - 1:
        return "PERSISTENT"

    return None
```

- [ ] **Step 4: Run, expect 4 passes**

```bash
python3 -m pytest tests/test_persistence.py -k compute_theme_tag -v
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add compute_theme_tag for NEW/ACCELERATING/PERSISTENT classification"
```

---

### Task 12: Add CLI command `compute-tags`

**Why:** SKILL.md needs to call tag computation from Bash. One CLI command takes a payload of {themes, companies, theme_index, company_index} and returns tagged copies.

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/persistence.py`
- Test: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_persistence.py`:
```python
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
```

- [ ] **Step 2: Run, expect failure**

```bash
python3 -m pytest tests/test_persistence.py -k cli_compute_tags -v
```

- [ ] **Step 3: Add the CLI branch**

In `persistence.py`, inside `_cli_main()` before the unknown-command else, add:
```python
    elif command == "compute-tags":
        if sys.stdin.isatty():
            print(json.dumps({"error": "No data piped. Pipe {themes, companies, theme_index, company_index}."}))
            sys.exit(1)
        payload = json.loads(sys.stdin.read())
        themes = payload.get("themes", [])
        companies = payload.get("companies", [])
        theme_index = payload.get("theme_index", {})
        company_index = payload.get("company_index", {})

        tagged_themes = [
            {**t, "tag": compute_theme_tag(t["name"], t.get("momentum", 0), theme_index)}
            for t in themes
        ]
        tagged_companies = [
            {**c, "tag": compute_company_tag(c["name"], company_index)}
            for c in companies
        ]
        print(json.dumps({"themes": tagged_themes, "companies": tagged_companies}))
```

- [ ] **Step 4: Run, expect pass**

```bash
python3 -m pytest tests/test_persistence.py -k cli_compute_tags -v
```

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git add .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add compute-tags CLI command"
```

---

## Checkpoint 1: Persistence Layer Complete

**Stop here and verify the entire persistence layer before touching SKILL.md.**

- [ ] **Run the full test suite with verbose output**

```bash
cd /Users/abhishekgarg/personalProject/.claude/skills/vc-signals
python3 -m pytest tests/ -v
```

Expected: every test passes. Count should be the original number plus all new tests added across Tasks 2-12 (roughly 25 new tests added).

- [ ] **Run a manual end-to-end shell sequence to verify CLI commands chain correctly**

```bash
cd /Users/abhishekgarg/personalProject
TMPDIR=$(mktemp -d)
mkdir -p $TMPDIR/{briefings,themes,companies,github,history}
SCRIPT=.claude/skills/vc-signals/scripts/persistence.py

# Save a briefing with companies
echo '[{"name":"MCP Infra","momentum":9}]' | \
  python3 $SCRIPT save-briefing --sector devtools --date 2026-04-16 \
    --retrieval-path websearch --data-dir $TMPDIR

# Update company index
echo '[{"name":"MintMCP","primary_theme":"MCP Infra"}]' | \
  python3 $SCRIPT update-company-index --sector devtools --date 2026-04-16 \
    --data-dir $TMPDIR

# Read the index back
python3 $SCRIPT load-company-index --data-dir $TMPDIR

# Compute tags
echo '{"themes":[{"name":"MCP Infra","momentum":9}],"companies":[{"name":"MintMCP","primary_theme":"MCP Infra"}],"theme_index":{},"company_index":{}}' | \
  python3 $SCRIPT compute-tags --data-dir $TMPDIR

rm -rf $TMPDIR
```

Expected output: each command prints valid JSON. The compute-tags output shows both items tagged "NEW".

- [ ] **Verify path traversal is blocked**

```bash
python3 .claude/skills/vc-signals/scripts/persistence.py load-briefing \
  --sector devtools --date "../../etc/passwd" --data-dir /tmp
```
Expected: prints `{"error": "Invalid date: '../../etc/passwd'. Expected YYYY-MM-DD."}` and exits with code 1.

If anything in this checkpoint fails, **stop and fix before proceeding**. SKILL.md changes assume the CLI works.

---

## Phase D — SKILL.md: Synthesis & Output Changes

These tasks edit prose, not code. There are no unit tests for SKILL.md — verification is manual (run the skill, eyeball the output). Each task makes one focused change so a reviewer can read the diff.

### Task 13: Add `radar` mode trigger as alias for `weekly`

**Files:**
- Modify: `.claude/skills/vc-signals/SKILL.md:16-23` (Argument Parsing section)
- Modify: `.claude/skills/vc-signals/SKILL.md:4` (argument-hint frontmatter)

- [ ] **Step 1: Update the argument-hint frontmatter**

In `SKILL.md`, replace line 4:
```yaml
argument-hint: 'vc-signals weekly devtools, vc-signals theme "agent evals", vc-signals company "Confluent", vc-signals github ai-infra, vc-signals setup'
```
with:
```yaml
argument-hint: 'vc-signals radar devtools, vc-signals theme "agent evals", vc-signals company "Confluent", vc-signals github ai-infra, vc-signals setup'
```

- [ ] **Step 2: Add `radar` to the argument parsing list**

In `SKILL.md` Argument Parsing section, replace the bullet list (lines 19-25) with:
```markdown
- `/vc-signals setup` → Setup wizard mode
- `/vc-signals radar <sector> [time]` → Company-first weekly radar (sectors: `devtools`, `cybersecurity`, `ai-infra`)
- `/vc-signals weekly <sector> [time]` → Alias for `radar` (kept for backward compatibility)
- `/vc-signals theme "<topic>" [time]` → Theme drill-down
- `/vc-signals company "<name>" [time]` → Company backtrace
- `/vc-signals github <sector>` → GitHub trending repos (sectors: `devtools`, `cybersecurity`, `ai-infra`, `all`)
- `/vc-signals add-sector <name>` → Add a new sector (guided)
- `/vc-signals compare "<company1>" "<company2>"` → Head-to-head comparison (stretch)
```

- [ ] **Step 3: Rename the section header**

Find the heading `## Mode: Weekly Sector Scan` (around line 287). Replace with:
```markdown
## Mode: Radar (Weekly Sector Scan)

**Triggers:** `/vc-signals radar <sector>` or `/vc-signals weekly <sector>` (alias)
```
And remove the duplicate `**Trigger:**` line beneath it.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/vc-signals/SKILL.md
git commit -m "feat(skill): add radar mode as alias for weekly"
```

---

### Task 14: Update Step 6 (Synthesize Themes) — drop low-yield themes

**Files:**
- Modify: `.claude/skills/vc-signals/SKILL.md` (Step 6 section, around lines 392-441)

- [ ] **Step 1: Add the company-yield filter as a new sub-step**

In Step 6, immediately after the **Cluster and deduplicate** sub-section (around line 406), insert a new sub-section:

```markdown
**Filter low-yield themes (Phase 1 radar requirement):**

After clustering, drop any theme that produces fewer than 3 mappable companies in Step 7. A theme without investable companies is signal noise — better to surface 6 themes × 8 companies than 12 themes × 2 companies.

Operationally: do a quick first pass through Step 7's company mapping for each candidate theme. If a theme yields fewer than 3 companies (across seed map, evidence, and GitHub data combined), drop it from the radar before scoring momentum. Note the dropped themes in the persistence record so future scans can detect when a previously-dropped theme starts producing companies.
```

- [ ] **Step 2: Update theme tag instruction**

At the end of Step 6 (right before "### Step 7: Map Companies"), insert:

```markdown
**Compute theme tag (NEW / ACCELERATING / PERSISTENT):**

Load the theme index and use the persistence helper to assign each kept theme a tag:

```bash
echo '{"themes": <THEMES_JSON>, "companies": [], "theme_index": <INDEX_JSON>, "company_index": {}}' | \
  python3 <skill_dir>/scripts/persistence.py compute-tags
```

The returned themes will each have a `tag` field set to "NEW", "ACCELERATING", "PERSISTENT", or null. Use this tag in the output template (Step 8).
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/vc-signals/SKILL.md
git commit -m "docs(skill): drop themes with <3 companies, add tag computation"
```

---

### Task 15: Update Step 7 (Map Companies) — dedup, target counts, why_on_radar

**Files:**
- Modify: `.claude/skills/vc-signals/SKILL.md` (Step 7 section, around lines 442-467)

- [ ] **Step 1: Replace the count target**

Find the existing Step 7 prose. Replace the entire body (between `### Step 7: Map Companies` and `### Step 8: Format Output`) with:

```markdown
For each surviving theme (after Step 6 filtering), identify 8-12 relevant companies using three sources:

1. **Seed map:** Check `company_aliases.json` — does any known company map to this theme?
2. **Evidence:** Were any companies/projects mentioned in the search results for this theme?
3. **GitHub data:** Do any trending repos from Step 5 relate to this theme?

**Target: 30-50 total companies across the radar.** This is the centerpiece of the output, not an accessory.

**Deduplicate across themes:**

A company that appears in evidence for multiple themes (e.g., CodeRabbit in both "AI Code Review" and "Agentic Coding") must appear in the company list ONCE, not twice. Pick the strongest theme as `primary_theme`, list the others in `secondary_themes`. The output table shows only `primary_theme`.

To pick `primary_theme`:
- Prefer the theme with the most direct evidence
- If tied, prefer the theme where the company is `direct_solver` over `beneficiary`
- If still tied, pick the theme with higher momentum

**For each company, capture:**

| Field | Source | Notes |
|-------|--------|-------|
| `name` | Display form | "MintMCP", "Anysphere (Cursor)" |
| `primary_theme` | Picked above | The theme this company most clearly rides |
| `secondary_themes` | Other themes the company touches | List of theme names |
| `why_on_radar` | One sentence | The single most concrete reason this is investable. Specific signal, not generic. |
| `evidence_url` | Best source | URL of the strongest piece of evidence |
| `role` | direct_solver / beneficiary / adjacent / unclear | Same taxonomy as before |
| `confidence` | confirmed / likely / inferred / speculative | Same as before |
| `stage` | null | Phase 2 fills this; leave null for now |
| `raised` | null | Phase 2 fills this |
| `headcount` | null | Phase 2 fills this |
| `founders` | null | Phase 2 fills this |

**The `why_on_radar` field is critical.** It's what Alex reads in the radar table. Bad: "AI testing company". Good: "AI-native test gen, launched 3 weeks ago, ex-Datadog founders". One sentence, specific signal.

**Compute company tags:**

Load the company index and use the persistence helper to assign each company a tag:

```bash
echo '{"themes": [], "companies": <COMPANIES_JSON>, "theme_index": {}, "company_index": <COMPANY_INDEX_JSON>}' | \
  python3 <skill_dir>/scripts/persistence.py compute-tags
```

Each company will receive a `tag` field set to "NEW", "RETURNING", "PERSISTENT", or null. Use this in the output table.

**Do NOT:**
- Pretend to know things you don't (especially funding amounts — leave null until Phase 2)
- Map a company to a theme just because the names sound related
- Duplicate companies across themes — pick one primary
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/vc-signals/SKILL.md
git commit -m "docs(skill): rewrite Step 7 — dedup companies, target 30-50, why_on_radar"
```

---

### Task 16: Replace Step 8 (Format Output) — new radar template

**Files:**
- Modify: `.claude/skills/vc-signals/SKILL.md` (Step 8 section, around lines 468-518)

- [ ] **Step 1: Replace the entire Step 8 body**

Find `### Step 8: Format Output` and the text up to `### Step 9: Persist Results`. Replace with:

```markdown
### Step 8: Format Output

Output uses the radar format: themes are short headers, the company table is the centerpiece, week-over-week diff lives at the top.

**Begin with the week-over-week diff (only if a previous briefing exists):**

```bash
python3 <skill_dir>/scripts/persistence.py company-diff <<EOF
{"current": <CURRENT_COMPANIES_JSON>, "previous": <PREV_COMPANIES_JSON>}
EOF
```

The output gives `new_companies` and `faded_companies`. Use these to populate the "New To Radar" and "Faded Off Radar" sections below.

**Output template:**

```markdown
## VC Radar: {Sector Display Name} — Week of {YYYY-MM-DD}

### What's Moving

[For each theme, exactly 3 lines:]
- **{Theme Name}** — {TAG (Nw)}. {one-line why-now in <120 chars}.
  Companies riding this: {N}

[6-8 themes max. TAG is one of NEW, ACCELERATING (#prev → #curr), PERSISTENT (Nw), or omitted if no tag. (Nw) means "N weeks active".]

### Company Radar ({N} companies)

| Company | Theme | Tag | Why On Radar |
|---------|-------|-----|--------------|
| MintMCP | MCP Infra | NEW | First SOC2-compliant MCP gateway, picking up enterprise pilots |
| CodeRabbit | AI Code Review | PERSISTENT | 2M repos, 13M PRs reviewed |
| ... | ... | ... | ... |

[30-50 rows, sorted by primary_theme then alphabetically by company name. Tag column shows NEW / RETURNING / PERSISTENT or empty.]

### New To Radar This Week ({N} companies)

[Bulleted list, max 10. If more than 10 are new, show top 10 by best evidence and note "+N more in the table above".]
- {Company} — {primary_theme}. {why_on_radar}
- ...

### Faded Off Radar ({N} companies)

[Bulleted list, max 10. From company-diff faded_companies.]
- {Company} — last seen {date}, was in {primary_theme}.

### Theme Detail

[For each theme, 2-3 lines max. NOT the long-form analysis from v1. Pointer to deep-dive.]
- **{Theme}** ({company_count} companies) — {2-sentence context}.
  Run `/vc-signals deep "{Theme}"` for full evidence and subthemes.
```

**Sorting rules:**
- Themes in "What's Moving" are sorted by tag (NEW → ACCELERATING → PERSISTENT → no-tag), then by momentum descending.
- Company Radar rows are sorted by primary_theme (matching the order themes appear in "What's Moving"), then alphabetically by company name within each theme.
- New To Radar is sorted by primary_theme matching above.

**Length budget:** the entire radar should fit in roughly 150-250 lines. If it's longer, the per-theme detail is too verbose — tighten it.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/vc-signals/SKILL.md
git commit -m "docs(skill): replace Step 8 with radar output template"
```

---

### Task 17: Update Step 9 (Persist Results) — call new persistence commands

**Files:**
- Modify: `.claude/skills/vc-signals/SKILL.md` (Step 9 section, around lines 520-547)

- [ ] **Step 1: Replace the Step 9 body**

Find `### Step 9: Persist Results` and the text up to `## Mode: Theme Drill-Down`. Replace with:

```markdown
### Step 9: Persist Results

**Order matters:** compute tags BEFORE updating the indices (the tag logic reads pre-update state), then persist.

**Save the briefing (themes + companies in one call):**

```bash
cat <<'BRIEFING_EOF' | python3 <skill_dir>/scripts/persistence.py save-briefing --sector <SECTOR> --retrieval-path <websearch|last30days> --date $(date +%Y-%m-%d)
{"themes": [the themes array], "companies": [the companies array]}
BRIEFING_EOF
```

**Save the markdown output:**

```bash
cat <<'MD_EOF' | python3 <skill_dir>/scripts/persistence.py save-markdown --subdir briefings --slug <SECTOR> --date $(date +%Y-%m-%d)
[the markdown content goes here]
MD_EOF
```

**Update the theme index:**

```bash
cat <<'THEMES_EOF' | python3 <skill_dir>/scripts/persistence.py update-index --sector <SECTOR> --date $(date +%Y-%m-%d)
[the JSON themes array goes here]
THEMES_EOF
```

**Update the company index (NEW in Phase 1):**

```bash
cat <<'COMPANIES_EOF' | python3 <skill_dir>/scripts/persistence.py update-company-index --sector <SECTOR> --date $(date +%Y-%m-%d)
[the JSON companies array goes here]
COMPANIES_EOF
```

If any persistence step fails, warn the user but still display the full briefing inline. Do not crash.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/vc-signals/SKILL.md
git commit -m "docs(skill): update Step 9 to persist companies and company index"
```

---

## Phase E — Verification & Cleanup

### Task 18: Create initial empty company_index.json

**Why:** The first scan post-flip will work fine without this (the load function returns `{}` when the file is missing). But committing an empty `{}` makes the data directory shape obvious to future contributors.

**Files:**
- Create: `.claude/skills/vc-signals/data/companies/company_index.json`

- [ ] **Step 1: Decide whether to create**

Since `.gitignore` (after Task 1) ignores `company_index.json`, creating it does nothing for git. Skip this task — leave the file to be created on first scan.

**Marking this task complete by skipping it intentionally.**

---

### Task 19: Code-simplifier pass on persistence.py

**Why:** After 6 new functions and ~150 added lines, the file deserves a sanity check for duplication and clarity.

- [ ] **Step 1: Dispatch the code-simplifier agent**

Use the Agent tool with `subagent_type: code-simplifier` and prompt:
```
Review .claude/skills/vc-signals/scripts/persistence.py for the changes added in
this session (Phase 1 radar flip). Focus areas:

1. Duplication between update_theme_index and update_company_index — both
   read JSON, mutate dict, write JSON. Is there a clean shared helper without
   over-abstracting?
2. The CLI _cli_main function is now ~110 lines. Is the dispatch table getting
   unwieldy enough to warrant a small refactor (e.g., dict of command -> handler)?
3. Comment quality — are docstrings explaining WHY, or just restating the function
   name? Trim any that are pure restatement.
4. Any obvious dead code or unused imports.

Do NOT change behavior. Do NOT refactor anything that requires changing the public
API (function signatures, CLI commands). Only internal cleanup. Run pytest after
each change to verify nothing breaks.

Skip the change if a simplification would obscure intent or require significant
test rewrites — clarity beats cleverness.
```

- [ ] **Step 2: Review the agent's diff**

Read each change the agent made. For each one ask:
- Does it preserve the public API exactly?
- Are tests still passing after?
- Is the code actually clearer?

If any change is questionable, revert that specific change with `git restore` on the relevant lines.

- [ ] **Step 3: Run the full test suite**

```bash
cd /Users/abhishekgarg/personalProject/.claude/skills/vc-signals
python3 -m pytest tests/ -v
```
Expected: every test passes.

- [ ] **Step 4: Commit (if there were changes)**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py
git commit -m "refactor: code-simplifier pass on persistence.py"
```

If the simplifier made no changes, skip the commit.

---

### Task 20: End-to-end manual test of `/vc-signals radar devtools`

**Why:** Unit tests verify the persistence layer. The SKILL.md changes can only be validated by running the actual skill and inspecting the output.

- [ ] **Step 1: Reset local state for a clean run**

```bash
rm -f .claude/skills/vc-signals/data/companies/company_index.json
ls .claude/skills/vc-signals/data/briefings/
ls .claude/skills/vc-signals/data/history/
```

If old briefings exist locally (from before the flip), keep them — the diff against the old schema should degrade gracefully. Note the existing files for comparison.

- [ ] **Step 2: Run the radar in a fresh Claude Code session**

In a new conversation:
```
/vc-signals radar devtools
```

Wait for completion (3-7 minutes for full scan).

- [ ] **Step 3: Inspect the output against this checklist**

Verify each item:

- [ ] Output starts with `## VC Radar: ... — Week of ...` (not `## Weekly VC Signal Brief`)
- [ ] "What's Moving" section has 6-8 themes
- [ ] Each theme line is 3 lines maximum (name+tag, why-now, company count)
- [ ] At least one theme shows a tag (NEW or PERSISTENT) — first scan post-flip should show NEW for many
- [ ] "Company Radar" table has between 25 and 55 rows
- [ ] No duplicate company names in the table
- [ ] Every row has a non-empty `Why On Radar` cell (not "—" or "TBD")
- [ ] No company shows fake funding/headcount data (those columns aren't in Phase 1 — table has 4 columns only)
- [ ] "New To Radar This Week" section exists; if first scan, every company should be NEW
- [ ] "Faded Off Radar" section exists (may be empty on first run)
- [ ] "Theme Detail" section is brief — 2-3 lines per theme, not 15
- [ ] Total output is between 100 and 300 lines

- [ ] **Step 4: Inspect the persisted data**

```bash
ls .claude/skills/vc-signals/data/briefings/
cat .claude/skills/vc-signals/data/briefings/*-devtools.json | python3 -m json.tool | head -60
cat .claude/skills/vc-signals/data/companies/company_index.json | python3 -m json.tool | head -40
```

Verify:
- [ ] The new briefing JSON has both `themes` and `companies` keys
- [ ] `companies` is a list of dicts with `name`, `primary_theme`, `why_on_radar`, `tag` fields
- [ ] `company_index.json` exists and contains entries with `display_name`, `first_seen`, `weeks_seen` fields

- [ ] **Step 5: Run the radar a second time (in a fresh session) to test week-over-week**

Wait at least one full minute (so timestamps differ), then in a new session:
```
/vc-signals radar devtools
```

Verify:
- [ ] Output includes a "What Changed Since Last Week" or equivalent diff section
- [ ] Companies that appeared in the first run no longer have "NEW" tag
- [ ] At least one company shows up in "New To Radar" only if synthesis surfaces something different (not guaranteed but likely with fresh searches)
- [ ] The `weeks_seen` field in `company_index.json` shows 2 for repeat companies

- [ ] **Step 6: If any check failed, debug**

Common issues:
- Output template not matching → Step 8 prose in SKILL.md needs sharpening
- No tags appearing → tag computation step in Step 6/7 was skipped during synthesis
- Companies duplicated across rows → Step 7 dedup instruction isn't being followed; consider strengthening the prose with explicit "ONE row per company"
- Index file empty → Step 9 is failing silently; check Bash command output

Each fix is a small SKILL.md prose tweak followed by a re-run.

- [ ] **Step 7: Commit any SKILL.md fixes from debugging**

```bash
git add .claude/skills/vc-signals/SKILL.md
git commit -m "fix(skill): tighten radar output instructions based on E2E test"
```

---

### Task 21: Final test suite + coverage gate

- [ ] **Step 1: Run the full test suite one last time**

```bash
cd /Users/abhishekgarg/personalProject/.claude/skills/vc-signals
python3 -m pytest tests/ -v --tb=short
```
Expected: 100% pass.

- [ ] **Step 2: Get a coverage report on persistence.py**

```bash
python3 -m pip install --quiet coverage 2>/dev/null || true
python3 -m coverage run --source=scripts -m pytest tests/
python3 -m coverage report -m
```
Expected: `persistence.py` shows ≥85% coverage. Lines uncovered should be limited to error branches (`json.JSONDecodeError` handlers, `sys.exit(1)` paths inside CLI dispatch where the success path is tested).

- [ ] **Step 3: If coverage is below 85% on a new function, add tests**

For each new function added in Tasks 3-12, the happy path AND at least one edge case should be covered. If a function is below 85% specifically, add the missing test, then re-run coverage.

- [ ] **Step 4: Verify no real data files are tracked in git**

```bash
cd /Users/abhishekgarg/personalProject
git ls-files | grep -E "(briefings|companies|history)/.*\.(json|md)$" | grep -v ".gitkeep"
```
Expected: empty output. If any data files appear, they need to be untracked.

- [ ] **Step 5: Final commit if anything was added**

```bash
git add -A
git status   # confirm nothing unexpected
git commit -m "test: improve coverage on persistence helpers" || true
```

---

## Verification Summary

When all tasks are complete, the following must all be true:

1. **Tests:** `python3 -m pytest tests/` → all green, ≥85% coverage on persistence.py
2. **Security:** `--date` arg rejects path traversal (test_cli_load_briefing_rejects_traversal_date passes)
3. **Data hygiene:** No real briefing or index files tracked in git
4. **Schema:** New briefings have both `themes` and `companies` keys; `companies` are deduped with `primary_theme`/`secondary_themes`
5. **Tagging:** First-week scan tags every company NEW; second scan tags repeats appropriately
6. **Output:** Radar markdown is 100-300 lines, leads with company table (30-50 rows), shows themes as 3-line headers
7. **Backward compat:** `/vc-signals weekly devtools` still works (alias for radar); old test fixtures still pass; old briefings still loadable
8. **Persistence layer:** `update-company-index`, `load-company-index`, `company-diff`, `compute-tags` CLI commands all functional

---

## What's Explicitly Out of Scope for This Plan

- WebSearch enrichment (funding/headcount/founders) — Phase 2
- Slack delivery — Phase 3
- Attio integration — Phase 4
- Theme drill-down depth improvements — Phase 5
- Other tech debt items #3-#16 from the audit — separate cleanup plan

Each `null` field in the company schema (`stage`, `raised`, `headcount`, `founders`) is the seam Phase 2 will fill in. No callers should break when those become non-null.

---

## Recovery Notes

If a task partially completes and breaks the suite:
- Each task ends with a commit, so `git reset --hard HEAD` reverts the in-progress work without losing prior tasks
- If Phase D (SKILL.md) breaks runtime behavior, revert just those commits — the persistence layer (Phase B/C) is independent and can stay merged
- The two security/hygiene fixes in Phase A are independent of everything else; if they ship alone, that's still net-positive
