# Source Yield Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Product Hunt, X, GitHub, and manual web from noisy discovery lanes into measurable source-yield lanes that preserve market chatter, promote strict company rows, expose evidence gaps, and prove repeatability.

**Architecture:** Keep the strict company gate in `source_yield_validation.py`, add explicit yield targets and repeatability summaries there, improve PH/X launch adapters only where they can safely resolve official identity, and deepen `targeted_manual_enrichment.py` so the Evidence Gap Queue becomes operational. Generated artifacts stay under the blessed `docs/radar-runs/current/` surface.

**Tech Stack:** Python scripts, pytest, JSON/Markdown run artifacts, last30days-backed public web search where configured.

---

### Task 1: Add Source-Yield Targets and Repeatability Summary

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/source_yield_validation.py`
- Test: `.claude/skills/vc-signals/tests/test_source_yield_validation.py`

- [ ] Add structured source-yield targets for Assign Owner, Review-Worthy Companies, Review-Worthy Market Signals, Evidence Gap Queue, and unsafe promotions.
- [ ] Add a repeatability validation report that compares multiple run directories using the same packet metrics.
- [ ] Render targets and repeatability status in Markdown so the user can see whether the system is getting closer to the final goal.
- [ ] Verify with focused pytest.

### Task 2: Improve Product Hunt Conversion

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/product_hunt_launches.py`
- Test: `.claude/skills/vc-signals/tests/test_product_hunt_launches.py`

- [ ] Preserve maker profiles and launch metrics as evidence fields.
- [ ] Classify PH rows into resolved, unresolved official-domain gap, and founder/manual-enrichment gap.
- [ ] Prefer official website fields and verified web fallback, while rejecting social, marketplace, app-directory, and third-party profile domains.
- [ ] Verify with focused pytest.

### Task 3: Improve X Launch Detection

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/x_launches.py`
- Test: `.claude/skills/vc-signals/tests/test_x_launches.py`

- [ ] Add launch-intent scoring so X rows keep useful chatter without treating every tweet as a company.
- [ ] Preserve author/profile, social-confidence evidence, and domain-resolution evidence.
- [ ] Keep official-domain promotion conservative and keep source/social domains out of company identity.
- [ ] Verify with focused pytest.

### Task 4: Make Evidence Gap Queue Operational

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/source_yield_validation.py`
- Modify: `.claude/skills/vc-signals/scripts/targeted_manual_enrichment.py`
- Test: `.claude/skills/vc-signals/tests/test_source_yield_validation.py`
- Test: `.claude/skills/vc-signals/tests/test_targeted_manual_enrichment.py`

- [ ] Add explicit gap buckets: official domain, founder/team, stage/funding/headcount, commercial/customer signal, pricing/docs/careers, and LinkedIn/manual check.
- [ ] Add per-row manual enrichment queries based on exact missing gaps.
- [ ] Limit manual enrichment to top Evidence Gap rows, not broad search.
- [ ] Verify with focused pytest.

### Task 5: Run and Bless Validation Artifacts

**Files:**
- Modify generated current artifacts under `docs/radar-runs/current/`
- Possibly add repeatability artifact under `docs/radar-runs/current/`

- [ ] Run two or three repeatability validations from available run artifacts or fresh validation outputs.
- [ ] Run targeted manual enrichment on the top 3-5 Evidence Gap Queue rows.
- [ ] Regenerate source-yield decision packet and bless `docs/radar-runs/current/`.
- [ ] Run full pytest, whitespace checks, and secret scan.
- [ ] Commit the intentional baseline only.
