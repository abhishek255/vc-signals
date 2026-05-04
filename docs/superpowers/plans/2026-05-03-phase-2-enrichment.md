# Plan: Phase 2 — Company Enrichment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the Phase-2-reserved null slots (`stage`, `raised`, `headcount`, `founders`, `founding_year`, plus the new `founder_github_activity`) on each company in the radar, cached for re-use across weekly scans.

**Strategy:** Two-tier retrieval mirroring the Phase 1 pattern: **last30days `--deep-research` when available, WebSearch as zero-config fallback.** Python provides cache CRUD + schema validation. Claude (via SKILL.md) drives the actual research and field extraction.

| Layer | Responsibility |
|---|---|
| `scripts/enrichment.py` | Cache load/save, TTL check, per-company update, merge cached fields into radar companies |
| SKILL.md Step 7.5 | Path-select between last30days (preferred) and WebSearch (fallback); per-company research; calling `enrichment.py update` |
| SKILL.md Step 8 | Radar table template adds Stage / Raised / HC columns |
| SKILL.md Step 9 | Persist updated cache as the final step |

**Why two-tier?** The original WebSearch-only design was missing the better tool. last30days `--deep-research` returns one citation-backed synthesis per company (Perplexity Sonar, 50+ citations) covering funding, team, history. Auto-resolve handles entity discovery (X handles, GitHub profiles, subreddits) so we don't hand-build queries. Cost is ~$0.90/company but the 14-day TTL means weekly scans are mostly cache hits — only NEW or RETURNING companies trigger fresh research, keeping ongoing cost in the $5-10/week range.

The WebSearch fallback path stays in the plan verbatim so users without `OPENROUTER_API_KEY` still get enrichment, just shallower.

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
    "founder_github_activity": "Michael Truell: 14 PRs merged in last 30 days across 2 repos",
    "evidence": {
      "stage": "https://crunchbase.com/...",
      "raised": "https://techcrunch.com/...",
      "headcount": "https://linkedin.com/...",
      "founder_github_activity": "https://github.com/mntruell"
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
- [ ] **Step 3:** Implement skeleton: import `_normalize_company_name` from `persistence`; define `DEFAULT_DATA_DIR`, `DEFAULT_TTL_DAYS=14`, `ENRICHED_FIELDS = ("stage","raised","headcount","founders","founding_year","lead_investor","founder_github_activity")`; implement `_cache_path`, `load_enrichment_cache`, `save_enrichment_cache`.
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

**Why:** Companies are mapped (Step 7) but null-slotted; insert enrichment before output formatting. Use the same dual-path pattern as Phase 1 retrieval (Step 3): last30days when configured, WebSearch as the fallback.

- [ ] **Step 1:** After Step 7, insert "### Step 7.5: Enrich Companies (Phase 2)" with the structure below. The whole section reads roughly:

  ````markdown
  ### Step 7.5: Enrich Companies (Phase 2)

  Each radar company gets enriched with funding stage, total raised, headcount, founders, founding year, and (when last30days is available) recent founder GitHub activity. Results cache for 14 days so weekly scans don't re-research the same company.

  **a. Load the enrichment cache:**

  ```bash
  python3 <skill_dir>/scripts/enrichment.py load-cache --data-dir <skill_dir>/data
  ```

  Returns `{}` on first run.

  **b. For each company, decide whether to research:**

  - Cached AND `fetched_at` within 14 days → skip; rely on the cache.
  - Otherwise → research it via the path selected in Step 3 (last30days vs WebSearch).

  **c. Path selection — same check as Step 3:**

  ```bash
  python3 <skill_dir>/scripts/last30days_adapter.py check
  ```

  - `installed=true` AND `configured=true` AND `deep_research_available=true` → **last30days deep-research path** (preferred).
  - Otherwise → **WebSearch fallback path**.

  Tell the user which path Step 7.5 is using so they understand the fidelity:
  - "Enriching companies via last30days deep-research (Perplexity Sonar; ~$0.90/company; first scan only — subsequent scans are cache hits)."
  - "Enriching companies via WebSearch fallback. For citation-backed enrichment, run `/vc-signals setup` and configure OpenRouter."

  **d (last30days path). One deep-research query per cache-miss company:**

  ```bash
  LOOKBACK_DAYS_ENRICH=90  # funding announcements live in 30-90d windows; longer than radar lookback

  python3 <skill_dir>/scripts/last30days_adapter.py query \
    --topic "<company name> funding stage employees founders founding year" \
    --deep-research --auto-resolve --quick \
    --lookback-days ${LOOKBACK_DAYS_ENRICH} --emit json
  ```

  Auto-resolve discovers X handles, GitHub profiles, and subreddits without you spelling them out. The synthesis is a single citation-backed report — extract these fields:

  | Field | Where to look in the synthesis |
  |---|---|
  | `stage` | First "Series X" / "Seed" / "Pre-seed" mention near the most recent funding event |
  | `raised` | Total funding to date in USD with magnitude ("$15M", "$2.3B") |
  | `lead_investor` | Lead investor on the latest round |
  | `headcount` | Employee count or range from LinkedIn citation |
  | `founders` | Named individuals with founder/CEO/CTO titles |
  | `founding_year` | "founded in YYYY" |

  Capture each field's source URL from the citation list and pass it as `evidence`.

  **d.1 (last30days path, optional). Founder GitHub verification:**

  When the deep-research synthesis names a founder AND yields their GitHub username (auto-resolve usually surfaces this), or when the seed map already has known `oss_projects` with traceable owners, run a follow-up:

  ```bash
  python3 <skill_dir>/scripts/last30days_adapter.py query \
    --topic "<founder name> recent activity" \
    --github-user "<github_username>" --quick --emit json
  ```

  Summarize the result as a short string and write it to the cache as `founder_github_activity`. Examples: "Michael Truell: 14 PRs merged in last 30 days across 2 repos", "No public activity in last 90 days", or null if the username couldn't be confirmed.

  **d (WebSearch fallback path). Four targeted searches per cache-miss company:**

  | Field | Query template | Extract |
  |---|---|---|
  | `stage` + `raised` + `lead_investor` | `"<company>" funding round investors site:crunchbase.com OR site:techcrunch.com OR site:pitchbook.com` | stage label, USD amount, investor |
  | `headcount` | `"<company>" employees linkedin.com` | number or range |
  | `founders` | `"<company>" founders CEO CTO founding team` | list of names |
  | `founding_year` | `"<company>" founded year history` | four-digit year |

  Skip `founder_github_activity` on the WebSearch path — it requires last30days `--github-user` person-mode.

  **Extraction rules (both paths):**
  - Prefer the most recent source (a 2026 article beats 2024 for funding info).
  - Don't synthesize — if a field isn't on the page, leave it absent.
  - Use the company's display form (`Anysphere (Cursor)`) for queries; `update` normalizes internally.

  **e. Write each researched company to the cache:**

  ```bash
  echo '{"name": "<COMPANY NAME>", "fields": {"stage": "Seed", "raised": "$4M", "headcount": "12", "founders": ["Jane Doe"], "founding_year": 2024, "founder_github_activity": "Jane Doe: 8 PRs in last 30d"}, "evidence": {"stage": "https://crunchbase.com/...", "founder_github_activity": "https://github.com/janedoe"}}' | \
    python3 <skill_dir>/scripts/enrichment.py update --date $(date +%Y-%m-%d) --data-dir <skill_dir>/data
  ```

  Omit any field you couldn't find. The cache records `fetched_at` regardless, so we don't re-research the same misses every week.

  **f. Apply all cached enrichments to the radar companies:**

  ```bash
  echo '{"companies": <COMPANIES_JSON>}' | \
    python3 <skill_dir>/scripts/enrichment.py merge --data-dir <skill_dir>/data
  ```

  The output `companies` array has the enriched fields populated where the cache had data. Use this enriched array as input to Step 8 and Step 9.

  **Graceful degradation:** If WebSearch is rate-limited or last30days returns nothing for a company, leave that company's enriched fields null. The radar table renders `—` in those cells.
  ````

- [ ] **Step 2:** Verify checkpoints:
  - `grep -c 'Step 7\.5\|Enrich Companies' SKILL.md` ≥3
  - `grep -c 'enrichment\.py' SKILL.md` ≥3
  - `grep -c '\-\-deep-research' SKILL.md` ≥2 (existing theme drill-down + new enrichment usage)
  - `grep -nE 'last30days deep-research|WebSearch fallback' SKILL.md` ≥2 (path-selection prose)
  - `grep -c 'LOOKBACK_DAYS_ENRICH\|founder_github_activity' SKILL.md` ≥2

- [ ] **Step 3: Commit:** `docs(skill): add Step 7.5 with last30days deep-research + WebSearch fallback for Phase 2 enrichment`.

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
| 6 | Both retrieval paths documented | `grep -c '\-\-deep-research\|WebSearch fallback' SKILL.md` | ≥2 last30days, ≥2 fallback |
| 7 | `founder_github_activity` field plumbed | `grep -c 'founder_github_activity' SKILL.md scripts/enrichment.py` | both ≥1 |
| 8 | Radar table expanded | smoke Check 4 | new header present |
| 9 | Cache excluded from git | smoke Check 5 | 1 match in `.gitignore` |
| 10 | Coverage on `enrichment.py` | smoke Check 7 | ≥85% |

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

1. **Cache poisoning via bad parses (either path).** A wrong value persists 14 days. Mitigation: per-field `evidence` URL traces wrong values; future iteration can add a `--force` per-company reset.
2. **Cache key collisions across normalization.** Identical normalized names from different companies (rare but possible: "Stripe" the payments co vs "stripe" the npm package). Mitigation: synthesizer disambiguates at Step 7 via role/sector tagging.
3. **Markdown table width.** 3 added columns may wrap. Mitigation: short column names (`HC` not `Headcount`); enforced `—` for missing data.
4. **WebSearch rate limits (fallback path).** 30 companies × 4 queries = 120 searches per scan. Mitigation: 14-day TTL means most companies are cache hits after first scan; only NEW or RETURNING trigger fresh research.
5. **OpenRouter cost spikes (last30days path).** First scan of a sector with no cache = ~$27 (30 cos × $0.90). Subsequent weekly scans ≈ $5-10 (only new/returning companies). Mitigation: communicate cost in the path-selection prose; users can opt for the WebSearch fallback by skipping `OPENROUTER_API_KEY`.
6. **Founder GitHub username mis-resolution.** Auto-resolve might attach the wrong GitHub user (common name, multiple matches). Mitigation: only run the person-mode follow-up when the deep-research synthesis surfaces the username with high confidence (e.g., linked from the company's official site or a press release); otherwise leave `founder_github_activity` null.
