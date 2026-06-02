# Hard Evidence Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert weak Product Hunt, X, HN, and OSS signals into structured hard-evidence dossiers using fast public/provider search before slow fallback paths, without relaxing unsafe-promotion gates.

**Architecture:** Add a focused hard-evidence resolver that uses the existing `discovery_search_providers.py` provider wrapper, `signal_investigator.py` URL-role classification, and deterministic evidence reconciliation. Wire it before signal promotion so Product Hunt/X rows carry official-domain, founder, stage, and commercial evidence into candidates and source-yield validation.

**Tech Stack:** Python scripts under `.claude/skills/vc-signals/scripts`, pytest tests under `.claude/skills/vc-signals/tests`, Brave/direct provider search through `discovery_search_providers.py`, existing LLM planner in `signal_investigator.py`.

---

### Task 1: Hard Evidence Resolver

**Files:**
- Create: `.claude/skills/vc-signals/scripts/hard_evidence_resolver.py`
- Test: `.claude/skills/vc-signals/tests/test_hard_evidence_resolver.py`

- [ ] **Step 1: Write failing tests**

Add tests proving:
- direct provider search resolves an official domain from a Product Hunt-style row;
- social/Product Hunt/GitHub URLs are retained as evidence but blocked as official domains;
- commercial evidence from pricing/docs/careers/customers snippets is captured;
- the resolver applies a dossier to source rows without inventing founder/stage values.

- [ ] **Step 2: Verify tests fail**

Run:
```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hard_evidence_resolver.py -q
```

Expected: import failure for `hard_evidence_resolver`.

- [ ] **Step 3: Implement resolver**

Implement:
- `build_hard_evidence_dossier(row, source_lane="", search_runner=None, provider="brave", cache_dir=None, max_queries=2, max_results=8, timeout_seconds=10)`
- `apply_dossier_to_source_row(row, dossier)`
- `enrich_source_rows_with_hard_evidence(rows, source_lane="", ...)`

Use `signal_investigator.build_investigation_packet`, `build_search_plan`, and `reconcile_search_evidence`. Use direct provider search through `discovery_search_providers.run_provider_query`.

- [ ] **Step 4: Verify tests pass**

Run:
```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hard_evidence_resolver.py -q
```

Expected: all pass.

### Task 2: Product Hunt And X Wiring

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Write failing tests**

Extend weekly artifact tests so a Product Hunt row with no redirect domain gets enriched by hard evidence before signal promotion. Assert:
- raw evidence row has `domain`;
- `hard-evidence-dossiers.json` exists;
- source health still reports PH separately;
- no source/directory URL is accepted as official.

- [ ] **Step 2: Verify tests fail**

Run:
```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_applies_hard_evidence_to_product_hunt_rows -q
```

Expected: test missing or artifact missing.

- [ ] **Step 3: Wire resolver before signal promotion**

In `run_weekly_artifacts`, after `collect_live_evidence` and before `build_signals_from_evidence`, call `enrich_source_rows_with_hard_evidence` for `product_hunt` and `x_launches`. Write `hard-evidence-dossiers.json` into the run directory and include the path in the returned result.

- [ ] **Step 4: Verify tests pass**

Run:
```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_applies_hard_evidence_to_product_hunt_rows -q
```

Expected: pass.

### Task 3: Review-Worthy Commercial Proof Gate

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/source_yield_validation.py`
- Modify: `.claude/skills/vc-signals/tests/test_source_yield_validation.py`

- [ ] **Step 1: Write failing tests**

Add a source-yield test where a NEW Product Hunt row has:
- official domain;
- founder profile/maker profile;
- pricing/docs/customer/careers commercial evidence;
- no funding/headcount.

Expected: Review-Worthy Company passes because hard commercial proof substitutes for stage/size evidence.

- [ ] **Step 2: Verify tests fail**

Run:
```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_source_yield_validation.py::test_review_worthy_accepts_hard_commercial_proof_for_launch_rows -q
```

Expected: fail because current rule requires `stage`, `raised`, or `headcount`.

- [ ] **Step 3: Implement rule**

Add `_has_hard_commercial_evidence(row)` and update `is_net_new_review_worthy_candidate` to require either stage/size evidence or hard commercial evidence. Do not count generic descriptions; only count evidence URL lists such as `customer_buyer_evidence`, `pricing_evidence`, `docs_evidence`, `careers_evidence`, or `hard_evidence_dossier.commercial_hints`.

- [ ] **Step 4: Verify tests pass**

Run:
```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_source_yield_validation.py::test_review_worthy_accepts_hard_commercial_proof_for_launch_rows -q
```

Expected: pass.

### Task 4: Full Verification

**Files:**
- Generated: `docs/radar-runs/current-hard-evidence-validation-2026-06-01-r1/`
- Update blessed current: `docs/radar-runs/current/`

- [ ] **Step 1: Run full tests**

Run:
```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run fresh deep validation**

Run weekly deep-dive with:
- 30 company-discovery queries;
- 15 maturity queries;
- 12 article fetches;
- 90 minute runtime cap;
- Product Hunt, X, GitHub, YC, HN, manual web active.

- [ ] **Step 3: Validate and bless**

Run source-yield validation, targeted manual enrichment, structured-provider trial, rerun validation, then bless the run into `docs/radar-runs/current`.

- [ ] **Step 4: Completion read**

Complete the goal only if:
- tests pass;
- hard evidence dossier artifact exists;
- Product Hunt/X domain resolution improves versus r5 or reports a clear provider ceiling;
- unsafe promotions remain 0;
- source-yield report shows whether Review-Worthy Companies reach 8/15.

---

## Fresh-Eyes Review

This plan does not loosen Assign Owner. It improves evidence conversion before promotion and updates Review-Worthy Company only to accept hard commercial proof as a substitute for stage/size evidence. That matches the product goal: public sources should become useful when they provide official domain, founder/operator, and commercial proof, while weak rows remain in Evidence Gap.
