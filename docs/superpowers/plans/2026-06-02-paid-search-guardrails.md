# Paid Search Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make VC Signals paid web search visible, bounded, cached across runs, and safer during validation experiments without reducing production packet quality.

**Architecture:** Add one small guardrail module that owns provider cost estimates, shared cache/ledger paths, run budgets, and dry-run previews. Wire it through `discovery_search_providers.py`, `last30days_adapter.py`, and `radar_run.py` so both direct provider searches and last30days grounding are counted. Keep provider A/B testing as a deterministic CLI scaffold that can run dry by default and live only when explicitly requested.

**Tech Stack:** Python stdlib, pytest, existing VC Signals scripts under `.claude/skills/vc-signals/scripts`.

---

### Task 1: Guardrail Core

**Files:**
- Create: `.claude/skills/vc-signals/scripts/paid_search_guardrails.py`
- Test: `.claude/skills/vc-signals/tests/test_paid_search_guardrails.py`

- [x] **Step 1: Write tests for budget accounting, ledger entries, shared cache path, and dry-run preview.**
- [x] **Step 2: Implement `PaidSearchGuard`, provider cost estimates, mode defaults, global cache path, and preview helpers.**
- [x] **Step 3: Run `test_paid_search_guardrails.py`.**

### Task 2: Direct Provider Search Guarding

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_search_providers.py`
- Modify: `.claude/skills/vc-signals/tests/test_discovery_search_providers.py`

- [x] **Step 1: Add tests that cache hits avoid budget spend and budget exhaustion skips live calls.**
- [x] **Step 2: Add Serper and DataForSEO provider support for future cheaper bulk-search trials.**
- [x] **Step 3: Wire `run_provider_query` through the paid-search guard before live requests and after results.**

### Task 3: last30days Grounding Guarding

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/last30days_adapter.py`
- Modify: `.claude/skills/vc-signals/tests/test_last30days_adapter.py`

- [x] **Step 1: Add tests that implicit Brave auto-routing is avoided and budget blocks a last30days grounding call.**
- [x] **Step 2: Prefer explicit `VC_SIGNALS_LAST30DAYS_WEB_BACKEND`, then Exa/Serper/Parallel, and only use Brave when explicitly allowed.**
- [x] **Step 3: Record estimated last30days grounding spend because one adapter call can fan out into many Brave requests.**

### Task 4: Weekly Run Budget, Ledger Summary, and Dry-Run Cost Preview

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [x] **Step 1: Add tests for weekly paid-search preview and runtime ledger summary.**
- [x] **Step 2: Configure a guard at the start of `run_weekly_artifacts` using run mode and explicit CLI/env caps.**
- [x] **Step 3: Add `--paid-search-dry-run` / `--dry-run-cost` preview path before live collection.**

### Task 5: Provider A/B Test Scaffold and Docs

**Files:**
- Create: `.claude/skills/vc-signals/scripts/provider_ab_test.py`
- Create: `.claude/skills/vc-signals/tests/test_provider_ab_test.py`
- Modify: `README.md`
- Modify: `.claude/skills/vc-signals/SKILL.md`
- Modify: `.agents/skills/vc-signals/SKILL.md`

- [x] **Step 1: Add dry-run-first provider A/B CLI that estimates Brave, Exa, Serper, and DataForSEO cost for real query sets.**
- [x] **Step 2: Document the new budget env vars, cache, ledger, and provider routing recommendation.**

### Self-Review

- Spec coverage: The plan covers immediate Brave safety, spend ledger, hard caps, dry-run preview, global cache, provider routing, and provider A/B scaffold.
- Placeholder scan: No TBD or unbounded implementation placeholders remain.
- Type consistency: Guardrail terms use `provider`, `module`, `estimated_cost_usd`, `cache_status`, `run_id`, and `mode` consistently.
