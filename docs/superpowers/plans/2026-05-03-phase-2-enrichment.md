# Plan: Phase 2 — Company Enrichment via WebSearch

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the Phase-2-reserved null slots (`stage`, `raised`, `headcount`, `founders`, `founding_year`) on each company in the radar via targeted WebSearch, cached for re-use across weekly scans.

**Strategy:** Python provides cache CRUD + schema validation. Claude (via SKILL.md) drives WebSearch and field extraction — Python scripts can't call WebSearch directly, that's Claude's tool. The clean architectural split:

| Layer | Responsibility |
|---|---|
| `scripts/enrichment.py` | Cache load/save, TTL check, per-company update, merge cached fields into radar companies |
| SKILL.md Step 7.5 | WebSearch orchestration: query templates, parsing rules, calling `enrichment.py update` |
| SKILL.md Step 8 | Radar table template adds Stage / Raised / HC columns |
| SKILL.md Step 9 | Persist updated cache as the final step |

**Tech stack:** No new dependencies. Python 3.12+ runtime; tests work on 3.9+.

**Schema decisions (locked):**
- Cache key = `_normalize_company_name(name)` (re-uses existing helper from `persistence.py`)
- Single TTL of **14 days** for all fields (funding moves on month timescales; headcount/founders on quarter timescales — 14d is conservative)
- Flat schema per company (no nested `fields` wrapper) — easier to reason about, simpler tests:

```json
{
  "anysphere": {
    "fetched_at": "2026-05-03",
    "stage": "Series D",
    "raised": "$2.3B",
    "headcount": "150-200",
    "founders": ["Michael Truell", "Sualeh Asif"],
    "founding_year": 2022,
    "lead_investor": "Thrive Capital",
    "evidence": {
      "stage": "https://crunchbase.com/...",
      "raised": "https://techcrunch.com/...",
      "headcount": "https://linkedin.com/..."
    }
  }
}
```

- A field absent from the entry means "researched, not found" (so weekly scans don't retry until TTL expires). Field present and null is the same as absent; treat both as "no data."
- `evidence` URLs are optional but preferred.

**Confidence per field is OUT of scope for Phase 2.** Adds complexity without clear product value yet. The company-level `confidence` field (confirmed/likely/inferred) already exists from Phase 1 and is sufficient.

---

## File Map

| File | Type | Change |
|------|------|--------|
| `.claude/skills/vc-signals/scripts/enrichment.py` | Create | Cache CRUD; TTL check; merge helper; CLI |
| `.claude/skills/vc-signals/tests/test_enrichment.py` | Create | Full TDD coverage |
| `.claude/skills/vc-signals/tests/conftest.py` | Modify | Add `enriched_company` fixture |
| `.claude/skills/vc-signals/SKILL.md` | Modify | Add Step 7.5; expand Step 8 table; note Step 9 input |
| `.gitignore` | Modify | Add `enrichment_cache.json` |

---

## Conventions

- Run pytest from `.claude/skills/vc-signals/`: `python3 -m pytest tests/ -v`.
- Commit after each task. Convention: `feat(enrichment):`, `test(enrichment):`, `docs(skill):`, `chore(gitignore):`.
- All grep verifications run from repo root.
- Write the failing test FIRST, then implement, then re-run.

---

## Phase A — Cache Module (TDD)

### Task 1: `enrichment.py` skeleton + `load_enrichment_cache` + `save_enrichment_cache`

**Why:** Pure I/O foundation. Mirrors `load_company_index` from persistence.py.

- [ ] **Step 1:** Add `enriched_company` fixture to `conftest.py`.
- [ ] **Step 2:** Write 4 failing tests (load missing → `{}`, load malformed → `{}` + warning, save+load roundtrip, save creates dir).
- [ ] **Step 3:** Implement skeleton: import `_normalize_company_name` from `persistence`; define `DEFAULT_DATA_DIR`, `DEFAULT_TTL_DAYS=14`, `ENRICHED_FIELDS = ("stage","raised","headcount","founders","founding_year","lead_investor")`; implement `_cache_path`, `load_enrichment_cache`, `save_enrichment_cache`.
- [ ] **Step 4:** Run, expect 4 passes.
- [ ] **Step 5: Commit:** `feat(enrichment): cache load/save scaffolding`.

---

### Task 2: TTL check (`is_cache_fresh`)

- [ ] **Step 1:** 5 failing tests (within TTL, at boundary, beyond, missing fetched_at, malformed date).
- [ ] **Step 2:** Implement using `datetime.strptime("%Y-%m-%d")`. Boundary inclusive (`<= ttl_days`). Missing/malformed → `False`.
- [ ] **Step 3:** Run, expect pass.
- [ ] **Step 4: Commit:** `feat(enrichment): is_cache_fresh TTL check`.

---

### Task 3: `update_enrichment` (merge fields into a cache entry)

- [ ] **Step 1:** 6 failing tests: creates entry with `fetched_at`, merges new fields preserving old, normalized-name dedup, rejects unknown fields with `ValueError`, overwrites field values, supports `evidence` dict.
- [ ] **Step 2:** Implement: validate `fields ⊆ ENRICHED_FIELDS`; key by `_normalize_company_name`; merge into existing entry; refresh `fetched_at`; merge evidence dict if provided.
- [ ] **Step 3:** Run, expect pass.
- [ ] **Step 4: Commit:** `feat(enrichment): update_enrichment with normalized-name dedup and field-schema enforcement`.

---

### Task 4: `merge_into_company` (apply cached fields to a radar company dict)

- [ ] **Step 1:** 5 failing tests: applies cached fields, normalized lookup, doesn't overwrite truthy existing values (Claude's inferences win), no cache entry → keeps nulls, doesn't mutate input.
- [ ] **Step 2:** Implement: copy company dict; lookup via normalized name; for each field in `ENRICHED_FIELDS`, fill from cache only if current value is falsy.
- [ ] **Step 3:** Run, expect pass.
- [ ] **Step 4: Commit:** `feat(enrichment): merge_into_company applies cache without overwriting truthy values`.

---

### Task 5: CLI commands (`load-cache`, `update`, `merge`)

- [ ] **Step 1:** 7 failing tests: load-cache empty, update creates entry, update with evidence, unknown-field rejection, merge applies fields, malformed stdin → structured error, unknown command → error.
- [ ] **Step 2:** Implement `_read_json_stdin`, `_parse_cli_args`, `_cli_main` with three command branches. Re-use the JSON-error-handling pattern from `persistence.py`.
- [ ] **Step 3:** Run, expect pass. Full suite ≥125 passed.
- [ ] **Step 4: Commit:** `feat(enrichment): CLI for load-cache, update, merge`.

---

### Task 6: Add `enrichment_cache.json` to `.gitignore`

- [ ] **Step 1:** Add line `.claude/skills/vc-signals/data/companies/enrichment_cache.json` next to existing `company_index.json` exclusion.
- [ ] **Step 2:** Verify `grep -c 'enrichment_cache' .gitignore` = 1.
- [ ] **Step 3: Commit:** `chore(gitignore): exclude enrichment_cache.json`.

---

## Phase B — SKILL.md Integration

### Task 7: Add Step 7.5 (Enrich Companies) to Radar mode

**Why:** Companies are mapped (Step 7) but null-slotted; insert enrichment before output formatting.

- [ ] **Step 1:** After Step 7, insert "### Step 7.5: Enrich Companies (Phase 2)" with sub-steps:
  - **a.** `enrichment.py load-cache` to get current cache
  - **b.** Per-company decision: skip if cached and `fetched_at` within 14 days; else research
  - **c.** WebSearch query templates table:
    | Field | Query | Extract |
    |---|---|---|
    | stage + raised + lead_investor | `"<co>" funding round investors site:crunchbase.com OR site:techcrunch.com OR site:pitchbook.com` | stage label, USD amount, investor |
    | headcount | `"<co>" employees linkedin.com` | number/range |
    | founders | `"<co>" founders CEO CTO founding team` | name list |
    | founding_year | `"<co>" founded year history` | YYYY |
  - **d.** `enrichment.py update` per researched company (with optional `evidence` dict)
  - **e.** `enrichment.py merge` to apply cached fields to the radar companies array

- [ ] **Step 2:** Verify `grep -c 'Step 7\.5\|Enrich Companies' SKILL.md` ≥3; `grep -c 'enrichment\.py' SKILL.md` ≥3.
- [ ] **Step 3: Commit:** `docs(skill): add Step 7.5 (Enrich Companies) for Phase 2`.

---

### Task 8: Expand Step 8 radar table — Stage / Raised / HC columns

- [ ] **Step 1:** Replace the 4-column header `| Company | Theme | Tag | Why On Radar |` with the 7-column form `| Company | Theme | Tag | Stage | Raised | HC | Why On Radar |`. Update example rows accordingly. Add a "Cell rules" callout above the table:
  > - `Stage`: short form ("Seed", "Series A"), or `—` if unknown.
  > - `Raised`: total raised with magnitude ("$15M", "$2.3B"), or `—`.
  > - `HC`: integer or range ("12", "150-200"), or `—`.
  > - Empty cells **must** render as `—`, not blank.

- [ ] **Step 2:** Verify `grep -c '| Company | Theme | Tag | Stage' SKILL.md` = 1.
- [ ] **Step 3: Commit:** `docs(skill): expand radar table with Stage/Raised/HC columns`.

---

### Task 9: Note Step 9 consumes enriched companies

- [ ] **Step 1:** Add to Step 9 preamble (after "Order matters."): *"**Note (Phase 2):** The `companies` array passed to Steps 9c–9e is the enriched array from Step 7.5e. Index updates and saved briefings include funding/headcount/founders fields where available."*
- [ ] **Step 2:** Verify `grep -nE 'Step 7\.5e|enriched array' SKILL.md` ≥1.
- [ ] **Step 3: Commit:** `docs(skill): note Step 9 consumes enriched companies from Step 7.5e`.

---

## Phase C — End-to-End Verification

### Task 10: Smoke tests + final test gate + docs update

- [ ] **Check 1:** Full enrichment round-trip via CLI (load-cache → update → load-cache → merge). Expect each step's output matches schema.
- [ ] **Check 2:** Unknown-field rejection returns structured error, exit 1, no traceback.
- [ ] **Check 3:** Malformed stdin returns structured error, exit 1, no traceback.
- [ ] **Check 4:** SKILL.md greps:
  - `grep -c 'Step 7\.5\|Enrich Companies' SKILL.md` ≥3
  - `grep -c 'enrichment\.py' SKILL.md` ≥3
  - `grep -c '| Company | Theme | Tag | Stage' SKILL.md` =1
- [ ] **Check 5:** `grep -c 'enrichment_cache' .gitignore` =1.
- [ ] **Check 6:** Full test suite green: `python3 -m pytest tests/ -v` → ≥125 passed.
- [ ] **Check 7:** Coverage on `enrichment.py` ≥85%.
- [ ] **Step 8:** Update `docs/product-context.md` to mark Phase 2 complete; update README "What's New".
- [ ] **Step 9: Commit:** `docs: mark Phase 2 complete; expand radar with funding/headcount/founders`.

---

## Verification Summary

| # | Check | Command | Expected |
|---|---|---|---|
| 1 | Tests green | `python3 -m pytest tests/` | ≥125 passed |
| 2 | Cache round-trip works | smoke Check 1 | enriched company comes back |
| 3 | Schema enforcement | smoke Check 2 | unknown field rejected |
| 4 | Stdin JSON errors structured | smoke Check 3 | exit 1, JSON error, no traceback |
| 5 | SKILL.md Step 7.5 present | smoke Check 4 | ≥3 mentions |
| 6 | Radar table expanded | smoke Check 4 | new header present |
| 7 | Cache excluded from git | smoke Check 5 | 1 match in `.gitignore` |
| 8 | Coverage on `enrichment.py` | smoke Check 7 | ≥85% |

---

## Out of scope

- **Per-field confidence scoring** — Phase 2.5; company-level `confidence` already exists.
- **Filtering on enriched fields** ("only show pre-Series B") — Phase 3 (NL thesis search).
- **Migration of historical briefings** — old briefings stay as-is; new ones get enrichment.
- **Multiple TTLs per field type** — single 14-day TTL for v1.
- **Re-fetching on cache miss during table render** — radar shows `—` and waits for next run.

## Recovery notes

- Each task ends with a commit; `git reset --hard HEAD` reverts only the in-progress task.
- Phase A tasks 1–4 are sequential; Task 5 (CLI) depends on 1–4; Task 6 (gitignore) is independent.
- Phase B tasks depend on Phase A being complete.
- Tasks 7, 8, 9 within Phase B can be done in any order.

## Risk callouts

1. **Cache poisoning via bad WebSearch parses.** A wrong value persists 14 days. Mitigation: per-field `evidence` URL traces wrong values; future iteration can add a `--force` reset on a per-company basis.
2. **Cache key collisions across normalization.** Identical normalized names from different companies (rare but possible: "Stripe" the payments co vs "stripe" the npm package). Mitigation: synthesizer disambiguates at Step 7 via role/sector tagging.
3. **Markdown table width.** 3 added columns may wrap. Mitigation: short column names (`HC` not `Headcount`); enforced `—` for missing data.
4. **WebSearch rate limits.** 30 companies × 4 queries = 120 searches per scan. Mitigation: 14-day TTL means most companies are cache hits after first scan; only NEW or RETURNING trigger fresh research.
