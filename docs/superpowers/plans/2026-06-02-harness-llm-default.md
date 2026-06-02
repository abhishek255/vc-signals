# Harness LLM Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude Code/Codex harness reasoning the default VC Signals LLM path while keeping direct OpenAI/Gemini/xAI APIs as explicit standalone fallback only.

**Architecture:** External APIs retrieve evidence; the harness LLM reasons over evidence bundles and prompts. Python scripts remain deterministic: they build packets, validate outputs, reconcile sources, and render reports. Direct LLM APIs require `VC_SIGNALS_ALLOW_DIRECT_LLM_API=1`.

**Tech Stack:** Python scripts under `.claude/skills/vc-signals/scripts`, pytest, Markdown/JSON generated radar artifacts.

---

### Task 1: Gate Direct Signal-Investigator LLM Calls

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/signal_investigator.py`
- Test: `.claude/skills/vc-signals/tests/test_signal_investigator.py`

- [x] **Step 1: Write failing tests**

Tests assert that legacy `VC_SIGNALS_INVESTIGATOR_ENABLE_LIVE=1` does not call xAI, and that direct xAI only runs when `VC_SIGNALS_ALLOW_DIRECT_LLM_API=1`.

- [x] **Step 2: Implement gate**

`default_llm_provider()` now returns `None` unless `VC_SIGNALS_ALLOW_DIRECT_LLM_API=1` is set.

- [x] **Step 3: Verify**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_signal_investigator.py -q
```

### Task 2: Add Harness Investigation Contract

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/signal_investigator.py`
- Test: `.claude/skills/vc-signals/tests/test_signal_investigator.py`

- [x] **Step 1: Write failing test**

Test requires `build_harness_investigation_package()` and `render_harness_investigation_prompt()` to produce packet, prompt, output schema, validation contract, and no-direct-API rules.

- [x] **Step 2: Implement package and prompt**

The package includes `signal-investigation-harness-input.json`, `signal-investigation-harness-prompt.md`, expected output `signal-investigation-harness-output.json`, deterministic seed queries, and strict evidence rules.

- [x] **Step 3: Verify**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_signal_investigator.py -q
```

### Task 3: Split Provider Health

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/scripts/source_yield_validation.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_run.py`
- Test: `.claude/skills/vc-signals/tests/test_source_yield_validation.py`

- [x] **Step 1: Write failing tests**

Tests require merged signal-investigation summaries to preserve `harness_llm`, `direct_llm_api`, and `source_health` separately.

- [x] **Step 2: Implement split health**

Weekly reports now separate source query counts from harness reasoning and direct LLM API fallback status.

- [x] **Step 3: Verify**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_merge_signal_investigation_reports_preserves_harness_and_direct_llm_health .claude/skills/vc-signals/tests/test_source_yield_validation.py::test_validation_report_treats_harness_signal_investigation_as_completion_ready -q
```

### Task 4: Make Synthesis Harness-First

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_synthesis.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_synthesis.py`

- [x] **Step 1: Write failing tests**

Tests assert that Gemini/OpenAI keys alone do not trigger direct synthesis, and that Gemini only runs with `VC_SIGNALS_ALLOW_DIRECT_LLM_API=1`.

- [x] **Step 2: Implement harness handoff**

`run_synthesis()` now returns a disabled harness handoff result by default and only uses direct providers when explicitly opted in.

- [x] **Step 3: Verify**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_synthesis.py -q
```

### Task 5: Update Docs And Blessed Artifacts

**Files:**
- Modify: `README.md`
- Modify: `.claude/skills/vc-signals/SKILL.md`
- Modify: `.agents/skills/vc-signals/SKILL.md`
- Modify: `docs/index.html`
- Modify: `docs/vc-signals-explainer.html`
- Modify: `docs/product-context.md`
- Regenerate: `docs/radar-runs/current/*`
- Regenerate: `docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/source-yield-*`

- [x] **Step 1: Update public wording**

Docs now say Claude/Codex harness LLM is the normal reasoning path, external APIs are evidence retrieval, and direct LLM APIs are optional standalone fallback.

- [x] **Step 2: Regenerate source-yield reports**

Run:

```bash
python3 .claude/skills/vc-signals/scripts/source_yield_validation.py --run-dir docs/radar-runs/full-source-dossier-validation-2026-06-01-r1 --target-review-worthy-count 8 --target-partner-review-count 8 --repeatability-run-dir docs/radar-runs/exa-isolated-ph-github-validation-2026-06-01-r8
python3 .claude/skills/vc-signals/scripts/bless_current_run.py --source-run-dir docs/radar-runs/full-source-dossier-validation-2026-06-01-r1 --current-dir docs/radar-runs/current --partner-decision-packet docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/source-yield-decision-packet/partner-decision-packet.json --ledger-action-report docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/source-yield-decision-packet/ledger-action-report.json --source-yield-validation-report docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/source-yield-validation-report.json --source-yield-validation-markdown docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/source-yield-validation-report.md --source-yield-repeatability-report docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/source-yield-repeatability-report.json --source-yield-repeatability-markdown docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/source-yield-repeatability-report.md --targeted-manual-enrichment-report docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/targeted-manual-enrichment.json --structured-provider-trial-report docs/radar-runs/full-source-dossier-validation-2026-06-01-r1/structured-provider-trial.json
```

- [x] **Step 3: Verify**

Run the targeted tests and full vc-signals test suite.
