# Product Hunt And X Domain Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Product Hunt and X weak-source conversion by resolving more official company domains from launch text, embedded URLs, search results, and better X launch queries while keeping unsafe promotions at zero.

**Architecture:** Keep Product Hunt and X as signal lanes, not promotion lanes. Add safer deterministic extraction and verification inside the existing adapters, then validate through targeted tests plus a small live resolver reprobe against the current r5 unresolved set.

**Tech Stack:** Python scripts in `.claude/skills/vc-signals/scripts`, pytest tests in `.claude/skills/vc-signals/tests`, existing `last30days_adapter` query runner, existing `signal_investigator.classify_url_role` safety gate.

---

### Task 1: Product Hunt Resolver Strengthening

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/product_hunt_launches.py`
- Modify: `.claude/skills/vc-signals/tests/test_product_hunt_launches.py`

- [ ] **Step 1: Add tests for bare domains and alias-safe official matches**

Add tests that prove the resolver accepts:
- a bare domain in a search snippet, such as `agentfence.dev`
- a result where the official domain uses the maker/company alias from `Emily by Co-Desk`
- a result where the domain does not exactly match the full Product Hunt name but the title/snippet strongly identify the product

- [ ] **Step 2: Run Product Hunt tests and confirm the new tests fail**

Run:
```bash
/tmp/vc-signals-pytest-venv/bin/python -m pytest -q .claude/skills/vc-signals/tests/test_product_hunt_launches.py
```

Expected: new tests fail because `_urls_from_text` only extracts full `https://` URLs and `_verify_domain_candidate` requires a domain-name match.

- [ ] **Step 3: Implement safer candidate extraction and verification**

Change `product_hunt_launches.py` so it:
- extracts bare domains from text and normalizes them to `https://domain`
- builds product aliases from names with versions, pipes, and `by <maker/company>`
- accepts official domains when either the domain matches an alias or the search title/snippet strongly matches the Product Hunt name/tagline
- keeps rejecting Product Hunt, social, app-directory, article, repo, and marketplace domains through `_domain_allowed` and `classify_url_role`
- expands Product Hunt web resolver query count from 2 to 4 with shorter fallback queries before heavier investigator queries

- [ ] **Step 4: Re-run Product Hunt tests**

Run:
```bash
/tmp/vc-signals-pytest-venv/bin/python -m pytest -q .claude/skills/vc-signals/tests/test_product_hunt_launches.py
```

Expected: all Product Hunt tests pass.

### Task 2: X Query Shaping And Domain Extraction

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/x_launches.py`
- Modify: `.claude/skills/vc-signals/tests/test_x_launches.py`

- [ ] **Step 1: Add tests for richer X discovery**

Add tests that prove:
- `build_x_launch_queries` emits multiple launch-intent query variants per movement
- X snippets can resolve bare domains without `https://`
- X can infer a company name from an embedded official domain when the post has launch intent but no clean `company_name`

- [ ] **Step 2: Run X tests and confirm the new tests fail**

Run:
```bash
/tmp/vc-signals-pytest-venv/bin/python -m pytest -q .claude/skills/vc-signals/tests/test_x_launches.py
```

Expected: new tests fail because current X query shaping emits one query per movement and URL extraction only handles full URLs.

- [ ] **Step 3: Implement X improvements**

Change `x_launches.py` so it:
- emits several focused X launch queries per movement, capped by existing `max_queries`
- extracts bare domains from title/snippet/body text
- rejects shorteners and source/social domains as official company identity
- infers a provisional company name from an embedded official domain only when launch language is present
- keeps low-confidence chatter as `watch`, not `research deeper`

- [ ] **Step 4: Re-run X tests**

Run:
```bash
/tmp/vc-signals-pytest-venv/bin/python -m pytest -q .claude/skills/vc-signals/tests/test_x_launches.py
```

Expected: all X tests pass.

### Task 3: Resolver Validation Artifact

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/source_debug_audit.py`
- Modify: `.claude/skills/vc-signals/tests/test_source_debug_audit.py`
- Generate: `docs/radar-runs/ph-x-resolver-coresignal-validation-2026-06-01-r5/source-debug-audit.json`
- Generate: `docs/radar-runs/ph-x-resolver-coresignal-validation-2026-06-01-r5/source-debug-audit.md`

- [ ] **Step 1: Add a targeted Product Hunt reprobe mode**

Add a CLI option that re-runs the improved Product Hunt web resolver on unresolved PH rows from the run artifact, with a row cap and short timeout.

- [ ] **Step 2: Test the reprobe mode with a fake resolver**

Add a unit test that feeds one unresolved row and proves the audit records `attempted`, `resolved`, `domain`, and `warning`.

- [ ] **Step 3: Run the focused audit**

Run:
```bash
/tmp/vc-signals-pytest-venv/bin/python .claude/skills/vc-signals/scripts/source_debug_audit.py --run-dir docs/radar-runs/ph-x-resolver-coresignal-validation-2026-06-01-r5 --product-hunt-reprobe --product-hunt-reprobe-limit 17 --x-probe --x-probe-movement "AI agent security" --x-probe-timeout-seconds 35 --x-probe-limit 5 --x-probe-max-queries 2
```

Expected: audit records improved PH reprobe yield and a capped X live proof.

### Task 4: Verification

**Files:**
- No new source files beyond Tasks 1-3.

- [ ] **Step 1: Run focused tests**

Run:
```bash
/tmp/vc-signals-pytest-venv/bin/python -m pytest -q .claude/skills/vc-signals/tests/test_product_hunt_launches.py .claude/skills/vc-signals/tests/test_x_launches.py .claude/skills/vc-signals/tests/test_source_debug_audit.py
```

Expected: focused tests pass.

- [ ] **Step 2: Run full vc-signals tests**

Run:
```bash
/tmp/vc-signals-pytest-venv/bin/python -m pytest -q .claude/skills/vc-signals/tests
```

Expected: full suite passes.

- [ ] **Step 3: Summarize actual yield honestly**

Report:
- PH original r5 resolved/unresolved count
- PH reprobe resolved count after resolver changes
- X live probe count and whether official domains resolved
- unsafe promotions remain zero if validation report is unchanged or regenerated
