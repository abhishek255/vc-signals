# LLM Signal Investigator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an LLM-guided investigation layer that turns Product Hunt, X, OSS/GitHub, HN, and evidence-gap weak signals into structured identity/search/evidence packets before deterministic promotion.

**Architecture:** Keep deterministic gates as the final authority, but insert a bounded `signal_investigator` stage before weak-source identity enrichment and domain fallback. The investigator classifies URL roles, generates smarter search plans, reconciles search evidence into official-domain/founder/stage/commercial hints, and writes a first-class artifact used by source-yield validation.

**Tech Stack:** Python stdlib, injectable provider functions for tests, existing last30days query runner for web search, existing pytest suite under `.claude/skills/vc-signals/tests`.

---

## File Structure

- Create `.claude/skills/vc-signals/scripts/signal_investigator.py`
  - Owns LLM prompt construction, provider calls, deterministic fallback, URL role classification, search-plan generation, evidence reconciliation, and candidate mutation.
- Create `.claude/skills/vc-signals/tests/test_signal_investigator.py`
  - Tests red/green behavior for URL role classification, search-plan generation, LLM provider parsing, evidence reconciliation, and safe candidate application.
- Modify `.claude/skills/vc-signals/scripts/weak_source_identity_enrichment.py`
  - Uses investigator-generated search plans before the old single fixed query.
- Modify `.claude/skills/vc-signals/scripts/product_hunt_launches.py`
  - Uses investigator query planning for web fallback so PH redirect `403` does not mean “one generic query and done.”
- Modify `.claude/skills/vc-signals/scripts/x_launches.py`
  - Classifies URL roles so article/social/directory URLs become evidence, not official domains.
- Modify `.claude/skills/vc-signals/scripts/radar_run.py`
  - Runs `investigate_candidates` after candidate enrichment, writes `signal-investigation.json`, and passes investigated candidates into the existing gates.
- Modify `.claude/skills/vc-signals/scripts/source_yield_validation.py`
  - Reports whether the intelligent investigator ran, how many rows it touched, how many search queries it generated, and whether it improved official-domain/evidence hints without unsafe promotions.

## Task 1: Core Investigator Module

**Files:**
- Create: `.claude/skills/vc-signals/scripts/signal_investigator.py`
- Test: `.claude/skills/vc-signals/tests/test_signal_investigator.py`

- [ ] **Step 1: Write failing tests**

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_signal_investigator.py -q
```

Expected: fail because `signal_investigator` does not exist.

- [ ] **Step 2: Implement minimal module**

Implement:

```python
classify_url_role(url, title="", snippet="")
build_investigation_packet(candidate_or_item)
build_search_plan(packet, provider=None)
reconcile_search_evidence(packet, search_items, provider=None)
apply_investigation_to_candidate(candidate, investigation)
```

Rules:
- URL roles must distinguish `official_site`, `article`, `social`, `directory`, `repo`, `product_hunt`, `docs`, `pricing`, `careers`, and `unknown`.
- Provider output must be JSON-only and schema-sanitized.
- If provider is absent or fails, deterministic fallback must still generate useful queries and mark `mode="heuristic_fallback"`.
- Never set an official domain from pure LLM text. Only set it from evidence URLs that are not blocked and have official-site confidence.

- [ ] **Step 3: Run focused tests**

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_signal_investigator.py -q
```

Expected: pass.

## Task 2: Product Hunt and X Resolver Intelligence

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/product_hunt_launches.py`
- Modify: `.claude/skills/vc-signals/scripts/x_launches.py`
- Test: `.claude/skills/vc-signals/tests/test_product_hunt_launches.py`
- Test: `.claude/skills/vc-signals/tests/test_x_launches.py`

- [ ] **Step 1: Add failing tests**

Add PH test: fallback resolver runs multiple investigator queries and resolves a domain from the second query.

Add X test: publisher/article URL is preserved as evidence but not trusted as official domain.

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_product_hunt_launches.py .claude/skills/vc-signals/tests/test_x_launches.py -q
```

Expected: fail before implementation.

- [ ] **Step 2: Implement resolver integration**

Product Hunt:
- Build an investigation packet from launch name, tagline, PH URL, outbound URL, maker profiles, and launch evidence.
- Run investigator search-plan queries before falling back to the old single query.
- Preserve `domain_resolution_evidence.search_plan_source`.

X:
- Classify direct `website/homepage/outbound_url/domain` URL roles.
- If URL role is `article`, `social`, `directory`, `product_hunt`, or `repo`, store it in evidence and keep `domain=""`.
- Only official-site URLs remove `official_domain_identity_not_confirmed`.

- [ ] **Step 3: Run focused tests**

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_product_hunt_launches.py .claude/skills/vc-signals/tests/test_x_launches.py -q
```

Expected: pass.

## Task 3: Pipeline Integration and Artifact

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/scripts/weak_source_identity_enrichment.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_run.py`
- Test: `.claude/skills/vc-signals/tests/test_weak_source_identity_enrichment.py`

- [ ] **Step 1: Add failing tests**

Test that weekly run writes `signal-investigation.json` when enabled by default and includes summary counts.

Test that weak-source enrichment uses investigator query plans ahead of the fixed query.

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_radar_run.py .claude/skills/vc-signals/tests/test_weak_source_identity_enrichment.py -q
```

Expected: fail before integration.

- [ ] **Step 2: Integrate bounded investigation**

Add `signal_investigation_limit` defaulting to the same candidate limit. Run investigation after `apply_candidate_enrichment` and before weak-source identity enrichment.

Write:

```text
<run_dir>/signal-investigation.json
```

with summary:

```json
{
  "enabled": true,
  "provider_mode": "llm|heuristic_fallback|disabled",
  "rows_considered": 0,
  "rows_investigated": 0,
  "search_queries_planned": 0,
  "search_queries_run": 0,
  "official_domains_resolved": 0,
  "url_roles_classified": 0,
  "unsafe_domain_attempts_blocked": 0
}
```

- [ ] **Step 3: Run integration tests**

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_radar_run.py .claude/skills/vc-signals/tests/test_weak_source_identity_enrichment.py -q
```

Expected: pass.

## Task 4: Source-Yield Completion Reporting

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/source_yield_validation.py`
- Test: `.claude/skills/vc-signals/tests/test_source_yield_validation.py`

- [ ] **Step 1: Add failing tests**

Test that validation report includes `llm_signal_investigation_summary` and that completion is not claimed unless:
- investigator ran,
- PH/X/OSS/HN/evidence-gap rows were considered,
- search plans or URL role classifications were produced,
- unsafe promotions stayed at 0.

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_source_yield_validation.py -q
```

Expected: fail before reporting is implemented.

- [ ] **Step 2: Implement report fields**

Add `llm_signal_investigation_summary` to JSON and markdown. Keep it factual. Do not claim the final product goal is reached just because investigator ran.

- [ ] **Step 3: Run reporting tests**

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_source_yield_validation.py -q
```

Expected: pass.

## Task 5: Fresh Verification Run

**Files:**
- Generated artifacts under `docs/radar-runs/current-llm-investigator-validation-2026-06-01`
- Blessed pointer under `docs/radar-runs/current`

- [ ] **Step 1: Run focused test suite**

Run:

```bash
pytest .claude/skills/vc-signals/tests/test_signal_investigator.py \
  .claude/skills/vc-signals/tests/test_product_hunt_launches.py \
  .claude/skills/vc-signals/tests/test_x_launches.py \
  .claude/skills/vc-signals/tests/test_weak_source_identity_enrichment.py \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  .claude/skills/vc-signals/tests/test_source_yield_validation.py -q
```

Expected: pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest .claude/skills/vc-signals/tests -q
```

Expected: pass.

- [ ] **Step 3: Run fresh deep validation**

Run a fresh deep-dive weekly run with:
- 30 company-discovery queries,
- 15 maturity queries,
- 12 article fetches,
- 90 minute runtime cap,
- Product Hunt and X enabled,
- weak-source identity enabled,
- signal investigator enabled,
- targeted enrichment only for top gaps.

- [ ] **Step 4: Generate decision artifacts**

Run source-yield validation, targeted manual enrichment, structured provider trial, repeatability comparison, and bless the fresh run as `docs/radar-runs/current`.

- [ ] **Step 5: Completion gate**

Goal is complete only if fresh artifacts show:
- `signal-investigation.json` exists,
- investigator ran on PH/X/OSS/HN or top gap rows,
- source-yield report includes investigator summary,
- unsafe promotions are 0,
- Product Hunt/X/OSS rows have sharper evidence packets or official-domain outcomes than direct-field-only flow,
- any remaining shortfall is reported honestly.

## Fresh-Eyes Review

- Spec coverage: The plan covers end-to-end LLM use in discovery interpretation, PH/X resolver intelligence, weak-source identity, artifact reporting, and fresh validation. It does not let LLMs assign owners; deterministic gates remain final.
- Risk: Real LLM calls can be flaky/costly. The plan uses injectable providers and deterministic fallback so tests and weekly runs remain repeatable. Completion depends on artifact evidence, not model enthusiasm.
- Risk: LLM could hallucinate domains. The plan explicitly forbids setting official domains unless backed by evidence URLs and allowed URL roles.
- Risk: Too broad for one sprint. The scope is one new module plus narrow integrations, not a rewrite of company discovery, owner readiness, or Attio.
- Placeholder scan: No implementation step depends on undefined future work. Every task has files, commands, and expected verification.
