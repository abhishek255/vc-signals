# Phase 4 Owner Evidence Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Enrich only verified, early-stage company leads with source-backed owner evidence so `Assign owner` is allowed only when identity, maturity, founder/team, evidence, and Attio gates all pass.

**Architecture:** Add a narrow `owner_evidence.py` enrichment layer before owner-readiness scoring. It uses exact company/domain-scoped queries and capped official-site page extraction, caches every fetch/query result, writes `owner-evidence.json`, and populates candidate evidence fields consumed by `radar_focus.py`.

**Tech Stack:** Python dataclasses, local JSON cache files, existing `run_query` grounding provider, `urllib` official-site fetch fallback, pytest.

---

### Task 1: Owner Evidence Models

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Test: `.claude/skills/vc-signals/tests/test_owner_evidence.py`

- [x] Add `OwnerEvidence` dataclass with eligibility, official-site checks, evidence dimensions, Attio confidence, missing evidence, and recommended action fields.
- [x] Add compact owner-evidence fields to `Candidate` and `FocusItem`:
  - `founder_team_evidence`
  - `stage_funding_evidence`
  - `customer_buyer_evidence`
  - `attio_confidence`
  - `attio_confidence_basis`
  - `owner_evidence_status`

Verification:
- `python3 -m pytest .claude/skills/vc-signals/tests/test_owner_evidence.py -q`

### Task 2: Owner Evidence Enrichment

**Files:**
- Create: `.claude/skills/vc-signals/scripts/owner_evidence.py`
- Test: `.claude/skills/vc-signals/tests/test_owner_evidence.py`

- [x] Implement eligibility:
  - include verified company leads only
  - exclude category context, likely-too-late, monitor-only, acquired/incumbent/category-leader, and OSS-only rows
- [x] Implement official-site checks for `/`, `/about`, `/team`, `/customers`, `/pricing`, `/contact`, `/blog` with strict caps.
- [x] Implement exact funding/stage and customer/buyer queries:
  - `"<Company>" "<domain>" funding seed series A series B`
  - `"<Company>" "<domain>" customers users case study enterprise`
- [x] Cache all page fetches and query results.
- [x] Extract evidence snippets and URLs, but never store full article/page bodies.
- [x] Compute Attio confidence from `attio_status`, `attio_safe_to_match`, domain, and match keys.

Verification:
- Tests prove official pages extract founder/team evidence.
- Tests prove funding/customer query results enrich dimensions.
- Tests prove category anchors and OSS-only rows are skipped.
- Tests prove unknown/unsafe Attio blocks owner assignment.

### Task 3: Owner-Readiness Integration

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_focus.py`
- Modify: `.claude/skills/vc-signals/scripts/owner_readiness.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_focus.py`

- [x] Make owner-readiness scoring consume explicit owner-evidence dimensions.
- [x] Keep `Assign owner` blocked unless:
  - verified company identity
  - sourcing maturity
  - founder/team evidence
  - stage/funding or commercial evidence
  - Attio confidence is sufficient
- [x] Keep category anchors like n8n, 7AI, and LangChain monitor/category only.

Verification:
- Copperhelm-like company with missing founder/team remains `Research deeper`.
- Company with founder/team, seed evidence, Attio no-match, and safe identity can become `Assign owner`.
- Category anchors cannot become `Assign owner`.

### Task 4: Weekly Run Integration

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [x] Run owner-evidence enrichment after identity resolution and before owner-readiness scoring.
- [x] Write `owner-evidence.json`.
- [x] Keep `weekly-preview.md` rendering unchanged.
- [x] Include `owner_evidence_json` in the weekly result payload.

Verification:
- Weekly run test writes `owner-evidence.json`.
- Weekly focus still writes `weekly-focus.json` and `weekly-focus.md`.
- `weekly-preview.md` still exists and has the original weekly-preview surface.

### Task 5: Weekly-Focus Display

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_focus.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_focus.py`

- [x] Add compact display columns for:
  - founder/team evidence
  - stage/funding evidence
  - customer/buyer evidence
  - missing owner evidence
  - next validation step
- [x] Keep table concise enough for Alex to scan quickly.

Verification:
- Markdown test confirms these headings render.
- Missing owner evidence appears for Research deeper rows.

### Task 6: Full Verification And Real Run

**Files:**
- No production edits expected.

- [x] Run targeted owner evidence/focus/run tests.
- [x] Run full test suite.
- [x] Run a bounded weekly artifact into `docs/radar-runs/current-phase4-owner-evidence-check`.
- [x] Inspect `owner-evidence.json`, `weekly-focus.json`, and `weekly-focus.md`.
- [x] Confirm generated artifacts are not committed.

Verification commands:
- `python3 -m pytest .claude/skills/vc-signals/tests/test_owner_evidence.py .claude/skills/vc-signals/tests/test_owner_readiness.py .claude/skills/vc-signals/tests/test_radar_focus.py .claude/skills/vc-signals/tests/test_radar_run.py -q`
- `python3 -m pytest .claude/skills/vc-signals/tests -q`
- `git diff --check`

Definition of Done:
- `owner-evidence.json` exists and summarizes eligible, skipped, page checks, query checks, and Attio-blocked rows.
- Category anchors and OSS-only rows are skipped by owner evidence enrichment.
- `Assign owner` only appears when identity, maturity, founder/team, evidence, and Attio gates all pass.
- Copperhelm-style rows remain `Research deeper` with explicit missing evidence when founder/team or customer/funding evidence is missing.
- `weekly-preview.md` behavior is unchanged.
- Generated run artifacts remain uncommitted.
