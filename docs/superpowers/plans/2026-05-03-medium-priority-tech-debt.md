# Plan: Fix Medium-Priority Tech Debt (Items #11–#16)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the six Medium items from `docs/product-context.md`:
- #11 Curated subreddits never passed alongside `--auto-resolve`
- #12 No "persistent" themes computation in `compute_diff`
- #13 Case-sensitive theme matching in `compute_diff`
- #14 No JSON error handling on `stdin.read()`
- #15 `install.sh` has no git check, no trap for cleanup
- #16 README oversells "interactive diagrams"

**Strategy:** Code changes first (Phase A, TDD), then prose/script polish (Phase B), then end-to-end verification (Phase C). Tasks 1 and 2 both touch `compute_diff` but are independent — do them sequentially to keep commits focused.

**Tech stack:** No new dependencies. Python 3.12+ runtime; tests work on 3.9+.

**Scope decision on #13:** `compute_diff` matching becomes case-insensitive but `update_theme_index` keys are NOT changed. Existing on-disk `theme_index.json` files have user data keyed by raw names; rekeying invalidates them. The diff is a transient computation, so fixing only it is the minimal-impact fix.

---

## File Map

| File | Change |
|------|--------|
| `.claude/skills/vc-signals/scripts/persistence.py` | Add `_normalize_theme_name`; extend `compute_diff` with `persistent_themes` and case-insensitive matching; add `_read_json_stdin` helper; route `json.loads(sys.stdin.read())` callsites through it |
| `.claude/skills/vc-signals/tests/test_persistence.py` | New tests for persistence + case-insensitive matching + malformed-stdin handling |
| `.claude/skills/vc-signals/SKILL.md` | Step 4 (Radar): pass curated `subreddits` from `sectors.json` alongside `--auto-resolve` |
| `install.sh` | Check `git` exists; trap-cleanup `TMP_DIR` |
| `README.md` | Drop the "interactive" claim |

---

## Conventions

- Run pytest from `.claude/skills/vc-signals/`: `python3 -m pytest tests/ -v`.
- Commit after each task. Convention: `feat:`, `fix:`, `refactor:`, `docs(skill):`, `chore(install):`.
- All grep verifications run from repo root.
- Write the failing test FIRST, then implement, then re-run.

---

## Phase A — Code Changes (TDD)

### Task 1: Add `persistent_themes` to `compute_diff` (item #12)

**Files:** `scripts/persistence.py`, `tests/test_persistence.py`.

**Why:** Design spec lists four diff categories: new / fading / accelerating / persistent. Function emits only the first three.

**Design:** Optional `theme_index` parameter (default `{}`). Theme is "persistent" if it appears in `current` AND `theme_index[name].appearances >= PERSISTENT_WEEKS_THRESHOLD`. CLI `diff` loads `theme_index.json` and passes it.

- [ ] **Step 1: Write failing tests** (4 tests — see plan body for exact code)
- [ ] **Step 2: Run, expect 4 failures**
- [ ] **Step 3: Implement** (extend signature; add persistent_themes block; update CLI `diff` branch to load index)
- [ ] **Step 4: Run, expect pass**
- [ ] **Step 5: Full suite ≥83 passed**
- [ ] **Step 6: Commit:** `feat(persistence): add persistent_themes to compute_diff`

---

### Task 2: Case-insensitive theme matching in `compute_diff` (item #13)

**Files:** `scripts/persistence.py`, `tests/test_persistence.py`.

**Why:** Raw `theme["name"]` keys mean `"AI Code Review"` and `"AI code review"` count as different themes — one shows new, one fading.

**Design:** Add `_normalize_theme_name`: lowercase + strip + collapse whitespace runs. Use as match key in `compute_diff` only; preserve raw display values in output.

- [ ] **Step 1: Write 3 failing tests** (normalize_theme_name behavior, case-insensitive match, whitespace-insensitive match)
- [ ] **Step 2: Run, expect failures**
- [ ] **Step 3: Implement** `_normalize_theme_name`; rewrite `compute_diff` to key on normalized form while preserving raw dicts
- [ ] **Step 4: Run, expect pass**
- [ ] **Step 5: Full suite ≥86 passed**
- [ ] **Step 6: Commit:** `fix(persistence): match theme names case- and whitespace-insensitively in compute_diff`

---

### Task 3: JSON error handling on stdin (item #14)

**Files:** `scripts/persistence.py`, `tests/test_persistence.py`.

**Why:** 6 callsites of `json.loads(sys.stdin.read())` raise uncaught `JSONDecodeError`, breaking the structured-error contract used everywhere else.

**Design:** Add `_read_json_stdin()` that combines isatty + read + parse + structured error response. Replace all 6 callsites.

- [ ] **Step 1: Parametrized failing test for all 6 commands**
- [ ] **Step 2: Run, expect 6 failures**
- [ ] **Step 3: Implement helper; replace each callsite**
- [ ] **Step 4: Run, expect pass**
- [ ] **Step 5: Full suite ≥92 passed**
- [ ] **Step 6: Commit:** `fix(persistence): structured error response for malformed stdin JSON`

---

## Phase B — Skill / Script Polish

### Task 4: Pass curated subreddits in Radar mode (item #11)

**No code change** — adapter already supports `--subreddits`. Update SKILL.md Radar Step 4 to read `sectors.json[<sector>].subreddits` and pass as `--subreddits "${SUBREDDITS}"` alongside `--auto-resolve`.

- [ ] **Step 1: Update SKILL.md prose + bash block**
- [ ] **Step 2: Verify** `grep -E '\-\-subreddits' SKILL.md` ≥1 match
- [ ] **Step 3: Commit:** `docs(skill): pass curated subreddits to last30days alongside --auto-resolve`

---

### Task 5: Harden `install.sh` (item #15)

**Why:** Missing `command -v git` check; no trap for `TMP_DIR` cleanup if `set -e` aborts.

- [ ] **Step 1: Add `trap 'rm -rf "$TMP_DIR"' EXIT` after TMP_DIR creation; add git existence check after Python check; remove redundant manual cleanup**
- [ ] **Step 2: `bash -n install.sh` clean**
- [ ] **Step 3: Verify greps** (`command -v git` =1, `trap.*EXIT` =1, manual `rm -rf "$TMP_DIR"` =0)
- [ ] **Step 4: Commit:** `chore(install): add git check and TMP_DIR trap-cleanup`

---

### Task 6: Drop "interactive" from README (item #16)

**Why:** README says "interactive visual guide / explainer / diagrams" — HTML is static, no JS.

- [ ] **Step 1: Replace each "interactive" mention with "visual" or simpler phrasing**
- [ ] **Step 2: Verify** `grep -n 'interactive' README.md` empty
- [ ] **Step 3: Commit:** `docs(readme): drop overstated "interactive" claim from visual guide refs`

---

## Phase C — End-to-End Verification

### Task 7: Smoke-test the new behaviors

- [ ] **Check 1:** `compute_diff` with theme_index → emits `persistent_themes`
- [ ] **Check 2:** Case-insensitive theme matching produces no spurious new/fading
- [ ] **Check 3:** Malformed stdin → exit 1 + `{"error": ...}` + no traceback
- [ ] **Check 4:** SKILL.md mentions `subreddits` (≥2 matches)
- [ ] **Check 5:** `install.sh` syntax-clean + has git check + has trap
- [ ] **Check 6:** No "interactive" in README

### Task 8: Final test gate + docs update

- [ ] **Step 1:** Full pytest suite ≥92 passed
- [ ] **Step 2:** Coverage info: persistence ≥65%
- [ ] **Step 3:** Update `docs/product-context.md` — move #11–#16 to Resolved
- [ ] **Step 4: Commit:** `docs: move resolved medium-priority tech debt to Resolved section`

---

## Verification Summary

| # | Check | Expected |
|---|---|---|
| 1 | Tests green | ≥92 passed |
| 2 | `persistent_themes` emitted | non-empty when index ≥3 |
| 3 | Case-insensitive matching | no spurious entries |
| 4 | Malformed stdin | structured error, no traceback |
| 5 | SKILL.md `--subreddits` | ≥1 |
| 6 | install.sh hardened | git check + trap present |
| 7 | README honest | no "interactive" |
| 8 | Coverage | persistence ≥65% |

---

## Out of scope

- Test-coverage gaps (last30days adapter CLI tests, run_query, fetch_star_timestamps, tautological test) — separate plan.
- High items #8, #9, #10 (HTML "Five Modes" drift, `github_topics` dead field, missing seed-map companies) — content/docs work.
- Rekeying on-disk `theme_index.json` to lowercase — invalidates existing user data; revisit if name drift becomes a real problem.

## Recovery notes

- Each task ends in a commit; `git reset --hard HEAD` reverts only the in-progress task.
- Phase A tasks are functionally independent.
- Phase B tasks are entirely independent and prose/script-only.
- Task 6 (README) is the lowest risk and could be done first as a warm-up.
