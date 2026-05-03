# Plan: Fix High-Priority Tech Debt (Items #3–#7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the five High-priority items from `docs/product-context.md:217-225`:
- #3 `<LOOKBACK>` literal placeholder in SKILL.md
- #4 Hardcoded `.claude/skills/vc-signals/` paths in SKILL.md
- #5 `--sector all` not handled by `github_trending.py`
- #6 `GITHUB_TOKEN` from `.env` not loaded by `github_trending.py`
- #7 No slugify instruction in SKILL.md

**Strategy:** Code first (Phase A, TDD), then SKILL.md prose updates (Phase B), then end-to-end verification (Phase C). Phase B depends on Phase A because SKILL.md will reference new CLI behavior.

**Tech stack:** No new dependencies. Python 3.12+ runtime; tests work on 3.9+.

---

## File Map

| File | Change |
|------|--------|
| `.claude/skills/vc-signals/scripts/github_trending.py` | Add `all` sector handling; fall back to reading `.env` for `GITHUB_TOKEN` |
| `.claude/skills/vc-signals/scripts/persistence.py` | Add `_slugify` helper; add `--name` to `save-markdown` CLI |
| `.claude/skills/vc-signals/tests/test_github_trending.py` | Tests for `all` sector and `.env` token loading |
| `.claude/skills/vc-signals/tests/test_persistence.py` | Tests for `_slugify` and `--name` CLI flag |
| `.claude/skills/vc-signals/SKILL.md` | Replace `<LOOKBACK>` with shell var; replace hardcoded paths with `<skill_dir>`; switch slug callsites to `--name` |

---

## Conventions

- Run pytest from `.claude/skills/vc-signals/`: `python3 -m pytest tests/ -v`.
- Commit after each task. Use the existing convention: `feat:`, `fix:`, `refactor:`, `docs(skill):`.
- All grep verifications run from repo root.
- "Pin the change" = write the failing test FIRST, then implement, then re-run.

---

## Phase A — Code Changes (TDD)

### Task 1: Handle `--sector all` in `github_trending.py` (item #5)

**Files:**
- Modify: `scripts/github_trending.py`
- Modify: `tests/test_github_trending.py`

**Why:** README and SKILL.md document `all` as a valid sector for `/vc-signals github all`, but `build_search_queries("all", ...)` returns `[]` because `"all"` isn't a key in `sectors.json`. Run currently fails silently with `{"error": "No queries for sector 'all'", "repos": []}`.

**Design:** Inside `build_search_queries`, treat `"all"` as a special token that aggregates queries from every sector in `sectors.json`. Inside `run_trending`, when sector is `"all"` propagate it to the output dict (`{"sector": "all", ...}`) and dedupe `repos` by `full_name` since the same repo could legitimately match queries from multiple sectors.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_github_trending.py`:

```python
def test_build_search_queries_all_sector(sample_config_dir):
    """`all` should aggregate queries across every sector in the config."""
    from github_trending import build_search_queries

    # Add a second sector to the fixture to prove aggregation
    import json
    cfg = json.loads((sample_config_dir / "sectors.json").read_text())
    cfg["cybersecurity"] = {
        "display_name": "Cybersecurity",
        "subcategories": {
            "appsec": {
                "name": "AppSec",
                "aliases": ["SAST", "DAST"],
                "seed_queries": ["application security tools"],
            }
        },
        "discovery_queries": [],
        "negative_terms": [],
    }
    (sample_config_dir / "sectors.json").write_text(json.dumps(cfg))

    queries = build_search_queries("all", sample_config_dir / "sectors.json")
    combined = " ".join(queries).lower()
    # Must include terms from BOTH sectors
    assert "continuous integration" in combined or "github actions" in combined
    assert "sast" in combined or "dast" in combined


def test_run_trending_all_sector_dedupes(monkeypatch, sample_config_dir):
    """When repos appear in queries across sectors, the final list must dedupe."""
    from github_trending import run_trending

    fake_repo = {
        "full_name": "shared/repo",
        "description": "",
        "stargazers_count": 100,
        "forks_count": 0,
        "language": "Go",
        "created_at": "2025-01-01T00:00:00Z",
        "pushed_at": "2026-04-01T00:00:00Z",
        "html_url": "https://github.com/shared/repo",
        "owner": {"login": "shared", "type": "Organization"},
        "topics": [],
    }

    def fake_search(queries, token=None, limit=30):
        from github_trending import parse_repo_data
        return [parse_repo_data(fake_repo)]

    def fake_timestamps(*a, **kw):
        return []

    monkeypatch.setattr("github_trending.search_repos", fake_search)
    monkeypatch.setattr("github_trending.fetch_star_timestamps", fake_timestamps)

    result = run_trending("all", config_path=sample_config_dir / "sectors.json", token="x", limit=10)
    assert result["sector"] == "all"
    full_names = [r["full_name"] for r in result["repos"]]
    assert full_names.count("shared/repo") == 1
```

- [ ] **Step 2: Run, expect failures**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/test_github_trending.py::test_build_search_queries_all_sector tests/test_github_trending.py::test_run_trending_all_sector_dedupes -v
```

Expect: 2 failed (first returns `[]`, second returns `error`).

- [ ] **Step 3: Implement**

In `scripts/github_trending.py`, modify `build_search_queries`:

```python
def build_search_queries(sector: str, config_path: Path | None = None) -> list[str]:
    config_path = config_path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return []

    sectors = json.loads(config_path.read_text())

    if sector == "all":
        target_sectors = list(sectors.keys())
    elif sector in sectors:
        target_sectors = [sector]
    else:
        return []

    queries = []
    seen = set()
    for s in target_sectors:
        for _key, subcat in sectors[s].get("subcategories", {}).items():
            aliases = subcat.get("aliases", [])
            for i in range(0, len(aliases), 2):
                chunk = aliases[i : i + 2]
                q = " OR ".join(f'"{a}"' for a in chunk)
                if q not in seen:
                    seen.add(q)
                    queries.append(q)
    return queries
```

`search_repos` already dedupes by `full_name`. No further changes needed there.

- [ ] **Step 4: Run, expect pass**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/test_github_trending.py -v
```

Expect: all `test_github_trending.py` tests green (10 total).

- [ ] **Step 5: Verifiable checkpoint**

```bash
cd .claude/skills/vc-signals && python3 scripts/github_trending.py --sector all --limit 1 2>&1 | head -3
```

Expect: a JSON object whose top-level `"sector": "all"` and either real repos or a clean rate-limit warning — not `{"error": "No queries for sector 'all'"`.

- [ ] **Step 6: Commit**

```
fix(github_trending): handle --sector all by aggregating across sectors
```

---

### Task 2: Load `GITHUB_TOKEN` from `~/.config/last30days/.env` (item #6)

**Files:**
- Modify: `scripts/github_trending.py`
- Modify: `tests/test_github_trending.py`

**Why:** Setup wizard writes `GITHUB_TOKEN=...` to `~/.config/last30days/.env` (SKILL.md:248-254). But `_get_token` (line 118) only checks `gh auth token` and `os.environ["GITHUB_TOKEN"]`. A user who skipped `gh auth login` and pasted a PAT into setup gets unauthenticated requests (60/hr instead of 5000/hr).

**Design:** Make `_get_token` check three sources in priority order: (1) `gh auth token`, (2) `os.environ["GITHUB_TOKEN"]`, (3) parse `~/.config/last30days/.env` for `GITHUB_TOKEN=...`. Accept an `env_path` parameter so tests can override.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_github_trending.py`:

```python
def test_get_token_falls_back_to_env_file(tmp_path, monkeypatch):
    """When gh CLI and GITHUB_TOKEN env var are both absent, read .env."""
    from github_trending import _get_token

    env_file = tmp_path / ".env"
    env_file.write_text("SETUP_COMPLETE=true\nGITHUB_TOKEN=ghp_fromenvfile\n")

    monkeypatch.setattr("github_trending.subprocess.run",
                       lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh")))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    assert _get_token(env_path=env_file) == "ghp_fromenvfile"


def test_get_token_prefers_env_var_over_env_file(tmp_path, monkeypatch):
    from github_trending import _get_token

    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=ghp_fromfile\n")

    monkeypatch.setattr("github_trending.subprocess.run",
                       lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh")))
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fromenvvar")

    assert _get_token(env_path=env_file) == "ghp_fromenvvar"


def test_get_token_returns_none_when_no_source(tmp_path, monkeypatch):
    from github_trending import _get_token

    monkeypatch.setattr("github_trending.subprocess.run",
                       lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh")))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert _get_token(env_path=tmp_path / "nonexistent") is None


def test_get_token_handles_quoted_value(tmp_path, monkeypatch):
    """Setup wizard may write quoted values; parser must strip quotes."""
    from github_trending import _get_token

    env_file = tmp_path / ".env"
    env_file.write_text('GITHUB_TOKEN="ghp_quoted"\n')
    monkeypatch.setattr("github_trending.subprocess.run",
                       lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh")))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    assert _get_token(env_path=env_file) == "ghp_quoted"
```

- [ ] **Step 2: Run, expect failures**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/test_github_trending.py -k "get_token" -v
```

Expect: 4 failed.

- [ ] **Step 3: Implement**

Replace `_get_token` in `scripts/github_trending.py`:

```python
DEFAULT_ENV_PATH = Path.home() / ".config" / "last30days" / ".env"


def _read_token_from_env_file(env_path: Path) -> str | None:
    if not env_path.exists():
        return None
    try:
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("GITHUB_TOKEN="):
                value = stripped.split("=", 1)[1].strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                return value or None
    except OSError:
        return None
    return None


def _get_token(env_path: Path | None = None) -> str | None:
    """Resolve GitHub token from gh CLI > GITHUB_TOKEN env var > .env file."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token

    return _read_token_from_env_file(env_path or DEFAULT_ENV_PATH)
```

- [ ] **Step 4: Run, expect pass**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/test_github_trending.py -v
```

Expect: all 14 tests green.

- [ ] **Step 5: Run full test suite for regressions**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/ -v
```

Expect: 66 passed (was 62, +4 new).

- [ ] **Step 6: Commit**

```
fix(github_trending): load GITHUB_TOKEN from ~/.config/last30days/.env
```

---

### Task 3: Add `_slugify` + `--name` to `persistence.py save-markdown` (item #7, code side)

**Files:**
- Modify: `scripts/persistence.py`
- Modify: `tests/test_persistence.py`

**Why:** SKILL.md tells Claude to pass `<SLUGIFIED_NAME>` for company/theme markdown, but never specifies the slug rules. `_validate_slug` enforces `[a-zA-Z0-9_-]+`, so `Anysphere (Cursor)` or `MCP Agent Infrastructure` will crash. Pushing slugify into the CLI eliminates the per-call burden and a class of bugs.

**Design:** Add an internal `_slugify(text)` helper. Extend the `save-markdown` CLI to accept either `--slug <validated-slug>` (existing behavior) or `--name <free-text>` (slugified internally). Reject calls that supply both or neither.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_persistence.py`:

```python
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
```

- [ ] **Step 2: Run, expect failures**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/test_persistence.py -k "slugify or save_markdown" -v
```

- [ ] **Step 3: Implement `_slugify`**

Add to `scripts/persistence.py`:

```python
def _slugify(text: str) -> str:
    """Convert free-text to a filesystem-safe slug.

    Rules:
      - lowercase
      - replace anything outside [a-z0-9] with a single hyphen
      - collapse runs of hyphens
      - strip leading/trailing hyphens

    Output is guaranteed to satisfy `_validate_slug`'s regex when non-empty.
    """
    s = text.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')
```

- [ ] **Step 4: Update the `save-markdown` CLI branch**

```python
elif command == "save-markdown":
    _require_args(args, "subdir")
    _validate_slug(args["subdir"], "subdir")

    has_slug = "slug" in args
    has_name = "name" in args
    if has_slug == has_name:  # both or neither
        print(json.dumps({"error": "Provide exactly one of --slug or --name."}))
        sys.exit(1)

    if has_name:
        slug = _slugify(args["name"])
        if not slug:
            print(json.dumps({
                "error": f"--name '{args['name']}' slugifies to empty; supply --slug instead."
            }))
            sys.exit(1)
    else:
        slug = args["slug"]
    _validate_slug(slug, "slug")

    if "date" in args:
        _validate_date(args["date"], "date")
    if sys.stdin.isatty():
        print(json.dumps({"error": "No data piped to stdin."}))
        sys.exit(1)
    content = sys.stdin.read()
    result = save_markdown(args["subdir"], slug, content, args.get("date"), data_dir)
    print(json.dumps(result))
```

- [ ] **Step 5: Run, expect pass**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/test_persistence.py -v
```

- [ ] **Step 6: Run full suite for regressions**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/ -v
```

- [ ] **Step 7: Commit**

```
feat(persistence): add _slugify helper and --name to save-markdown CLI
```

---

## Phase B — SKILL.md Hardening

These tasks change only `SKILL.md` prose. Verification = grep results match exactly.

### Task 4: Replace `<LOOKBACK>` placeholders with shell variable (item #3)

**Why:** `<LOOKBACK>` is a literal string Claude must remember to substitute. A model error leaves `--lookback-days <LOOKBACK>` in the actual command, causing `last30days_adapter.py` to fail with `int(args.get("lookback-days", "30"))` → `ValueError`. A shell variable `${LOOKBACK_DAYS}` makes the substitution mechanical and shell-resolvable.

**Lines affected:** SKILL.md lines 358, 639, 649, 741, 750.

- [ ] **Step 1: Add a "Resolve LOOKBACK" preamble at the top of each retrieval mode**

For Radar Step 4, Theme Step 2, Company Step 2: insert before the first `last30days_adapter.py query`:

```bash
# Set LOOKBACK_DAYS once for this scan. Default per mode below; override
# if the user appended a time window like "7d" / "30d" to the command.
LOOKBACK_DAYS=14   # radar default; use 30 for theme and company modes
```

- [ ] **Step 2: Replace each `<LOOKBACK>` with `${LOOKBACK_DAYS}`**

- [ ] **Step 3: Update prose around time-window override**

After each `LOOKBACK_DAYS=<default>`: "If the user appended a time window (e.g. `7d`, `30d`), set `LOOKBACK_DAYS` to that number's digits before running queries."

- [ ] **Step 4: Verifiable checkpoint**

```bash
grep -n '<LOOKBACK>' .claude/skills/vc-signals/SKILL.md
```

Expect: empty.

```bash
grep -c 'LOOKBACK_DAYS' .claude/skills/vc-signals/SKILL.md
```

Expect: ≥ 8.

- [ ] **Step 5: Commit**

```
docs(skill): replace <LOOKBACK> placeholder with $LOOKBACK_DAYS shell var
```

---

### Task 5: Replace hardcoded `.claude/skills/vc-signals/` paths with `<skill_dir>` (item #4)

**Lines affected:** 160, 267, 300, 305, 311, 326, 387, 656, 767, 820. Lines 89, 93, 110, 111, 114, 115 are documentation about resolution rules — leave them.

- [ ] **Step 1: Substitute each runtime command**

Replace `.claude/skills/vc-signals/` with `<skill_dir>/` in each affected runtime command.

- [ ] **Step 2: Verifiable checkpoint**

```bash
grep -nE 'python3 \.claude/skills/vc-signals|cat \.claude/skills/vc-signals' \
  .claude/skills/vc-signals/SKILL.md
```

Expect: empty.

```bash
grep -c '<skill_dir>' .claude/skills/vc-signals/SKILL.md
```

Expect: ≥ 18.

- [ ] **Step 3: Commit**

```
docs(skill): replace hardcoded .claude/skills paths with <skill_dir>
```

---

### Task 6: Switch slug callsites to use `--name` (item #7, SKILL.md side)

**Lines affected:** 709 (theme), 806 (company). Lines 603 (briefings), 869 (github) keep `--slug` since sectors are pre-validated.

- [ ] **Step 1: Update theme drill-down and company backtrace**

```bash
# theme (line 709)
... save-markdown --subdir themes --name "<topic>" --date $(date +%Y-%m-%d)
# company (line 806)
... save-markdown --subdir companies --name "<company name>" --date $(date +%Y-%m-%d)
```

- [ ] **Step 2: Add note in script-paths section**

Around SKILL.md line 119:

> **For free-text identifiers** like company names or theme topics, pass `--name "Free Text"` to `save-markdown`; it slugifies internally. Use `--slug` only when the value is already a known-safe identifier (sector slug, etc.).

- [ ] **Step 3: Verifiable checkpoint**

```bash
grep -nE 'SLUGIFIED_TOPIC|SLUGIFIED_NAME' .claude/skills/vc-signals/SKILL.md
```

Expect: empty.

```bash
grep -nE '\-\-name "<(topic|company name)>"' .claude/skills/vc-signals/SKILL.md
```

Expect: 2 matches.

- [ ] **Step 4: Commit**

```
docs(skill): use --name for free-text save-markdown calls
```

---

## Phase C — End-to-End Verification

### Task 7: Smoke-test the high-priority paths

- [ ] **Check 1: `--sector all` returns valid response**

```bash
python3 .claude/skills/vc-signals/scripts/github_trending.py --sector all --limit 1 2>&1 | head -20
```

Expect: JSON with `"sector": "all"`.

- [ ] **Check 2: Token resolution from .env file**

(See plan — uses tmp .env and patches `subprocess.run`.)

- [ ] **Check 3: `--name` slugifies a difficult company name**

```bash
TMP=$(mktemp -d) && mkdir -p "$TMP/themes" && \
  echo "# test" | python3 .claude/skills/vc-signals/scripts/persistence.py save-markdown \
    --subdir themes --name "Anysphere (Cursor)" --date 2026-05-03 --data-dir "$TMP" && \
  ls "$TMP/themes/"
```

Expect: `2026-05-03-anysphere-cursor.md`.

- [ ] **Check 4: `--slug` and `--name` together is rejected**

```bash
echo "# test" | python3 .claude/skills/vc-signals/scripts/persistence.py save-markdown \
  --subdir themes --slug foo --name bar --data-dir /tmp 2>&1
```

Expect: exit 1 with `exactly one of --slug or --name`.

- [ ] **Check 5: SKILL.md is internally consistent**

```bash
grep -n '<LOOKBACK>' .claude/skills/vc-signals/SKILL.md
grep -nE 'python3 \.claude/skills/vc-signals|cat \.claude/skills/vc-signals' .claude/skills/vc-signals/SKILL.md
grep -nE 'SLUGIFIED_TOPIC|SLUGIFIED_NAME' .claude/skills/vc-signals/SKILL.md
grep -c '<skill_dir>' .claude/skills/vc-signals/SKILL.md
```

Expect: first three empty, last ≥18.

---

### Task 8: Final test gate

- [ ] **Step 1: Full test suite green**

```bash
cd .claude/skills/vc-signals && python3 -m pytest tests/ -v
```

Expect: ≥76 passed.

- [ ] **Step 2: Coverage check**

```bash
cd .claude/skills/vc-signals && \
  python3 -m pytest tests/ --cov=scripts/persistence --cov=scripts/github_trending --cov-report=term-missing
```

Expect: both ≥85%.

- [ ] **Step 3: Update `docs/product-context.md`**

Move items #3-#7 from "High" to a new "Resolved (2026-05-03)" section.

- [ ] **Step 4: Final commit**

```
docs: move resolved high-priority tech debt to Resolved section
```

---

## Verification Summary

| # | Check | Command | Expected |
|---|-------|---------|----------|
| 1 | Tests green | `python3 -m pytest tests/ -v` | ≥76 passed |
| 2 | No `<LOOKBACK>` literals | `grep '<LOOKBACK>' SKILL.md` | empty |
| 3 | No hardcoded runtime paths | `grep -E 'python3 \.claude/skills\|cat \.claude/skills' SKILL.md` | empty |
| 4 | No slug placeholders | `grep -E 'SLUGIFIED_TOPIC\|SLUGIFIED_NAME' SKILL.md` | empty |
| 5 | `--sector all` works | `github_trending.py --sector all --limit 1` | `"sector": "all"` |
| 6 | `--name` slugifies | smoke test in Task 7 Check 3 | `*-anysphere-cursor.md` exists |
| 7 | `.env` token loads | smoke test in Task 7 Check 2 | dummy token returned |
| 8 | Coverage holds | `pytest --cov` | both ≥85% |

---

## Out of scope

- Medium-priority items (#11-#16) and test-coverage items — separate plan.
- Updating the seed map (#10) — content work.
- HTML explainer drift (#8) — UI/marketing.
- Dead `github_topics` field (#9) — separate cleanup.

## Recovery notes

- Each task ends with a commit, so `git reset --hard HEAD` reverts only the in-progress task.
- Phase A tasks are independent — Tasks 1, 2, 3 can be done in any order.
- Phase B Task 6 depends on Phase A Task 3.
- Phase B Tasks 4 and 5 are pure prose and can ship even if Phase A stalls.
