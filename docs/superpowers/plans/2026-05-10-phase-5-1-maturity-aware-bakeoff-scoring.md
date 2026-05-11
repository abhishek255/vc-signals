# Phase 5.1 Maturity-Aware Bakeoff Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Phase 5 discovery-yield metrics decision-grade by separating verified-domain recall from maturity-confirmed early-stage lead quality.

**Architecture:** Keep Phase 5 as an offline bakeoff/eval layer. Score provider results through the existing company verification and maturity-routing functions, but count a domain as a credible early-stage lead only when maturity evidence confirms seed/pre-seed/Series A/B or an explicitly safe early route. Unknown maturity remains useful as `research_deeper`, but moves to a separate metric so mature companies do not inflate sourcing yield.

**Tech Stack:** Python dataclasses/functions in `.claude/skills/vc-signals/scripts`, pytest, existing `radar_company_discovery.py` verification/maturity helpers, cached provider artifacts under `docs/radar-runs`.

---

## File Structure

- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
  - Add maturity-aware domain rollups.
  - Add stricter metrics.
  - Update target scoring and query-family summary.
  - Keep provider/search execution unchanged.

- Modify: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`
  - Update old optimistic metric tests.
  - Add tests for maturity-confirmed early leads, unknown maturity, mature/category rows, over-promoted controls, and family ranking.

- Do not modify:
  - `.claude/skills/vc-signals/scripts/radar_company_discovery.py` unless a small helper extraction is absolutely required.
  - `.claude/skills/vc-signals/scripts/discovery_search_providers.py`.
  - Any `weekly-preview.md`.

- Generated but not committed:
  - `docs/radar-runs/current-phase5-discovery-yield-smoke-v2/*`
  - Any provider cache under `docs/radar-runs/**/provider-cache/*`

---

## Product Rules

1. `verified_domains_found` remains a raw recall metric.
2. `credible_early_stage_leads` becomes strict and maturity-adjusted.
3. Unknown maturity does not count as credible early-stage.
4. Unknown maturity can still count as `research_worthy_verified_domains`.
5. Category anchors, likely-too-late, acquired, mature/incumbent rows, and monitor-only rows never count as early-stage.
6. Eval labels such as Braintrust expected route are used for scoring false positives, not for overriding production routing.
7. Maturity is evaluated once per unique accepted domain, then applied to all duplicate rows for that domain.
8. Query-family ranking uses maturity-adjusted unique-domain counts, not accepted-row counts.

---

## Required Execution Patches

These patches are mandatory before implementation:

1. Maturity rollups must not include arbitrary maturity-bearing raw items. A raw item can contribute to a domain rollup only when it matches the same domain or the same company/canonical/display name.
2. Provider run item access must support both `run["items"]` and `run["provider_result"]["items"]`; internally use a single helper for this.
3. `maturity_evaluation_status` has exactly three values: `not_evaluated`, `evaluated_no_maturity_evidence`, and `evaluated_with_evidence`.
4. Query-family metrics must use unique domains, not accepted-row counts.
5. Route ordering must go through a public `route_rank()` helper that returns `-1` for unknown or empty routes.
6. CLI commands must keep the existing Phase 5 shape: `discovery_yield_eval.py --output-dir ... --cache-dir ... --providers ... --eval-mode ...`.
7. Net-new mature-domain regressions such as Wiz, Orca, or Darktrace must prove mature domains do not count as early-stage.

---

## Task 1: Add Maturity-Aware Metric Tests

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`

- [ ] **Step 1: Update the optimistic official-domain test**

Rename `test_official_domain_research_deeper_counts_as_credible_early_stage_lead` to:

```python
def test_official_domain_with_unknown_maturity_counts_as_research_worthy_not_early_stage():
```

Change the assertions to:

```python
assert result["metrics"]["verified_domains_found"] == 1
assert result["metrics"]["research_worthy_verified_domains"] == 1
assert result["metrics"]["maturity_unknown_research_deeper"] == 1
assert result["metrics"]["credible_early_stage_leads"] == 0
assert result["metrics"]["maturity_adjusted_credible_early_stage_leads_per_100_queries"] == 0
```

- [ ] **Step 2: Add seed/Series A positive test**

Add:

```python
def test_seed_stage_evidence_counts_as_maturity_confirmed_early_stage():
    target = _target(expected_route="sourcing_candidate", maturity_expectation="seed_to_series_b")
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production seed startup",
            "query_id": "q1",
            "query_family": "seed_funding",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr raises seed round for AI agent production platform",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr is a startup building production AI agent tooling after a seed round.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["verified_domains_found"] == 1
    assert result["metrics"]["maturity_confirmed_early_stage"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 1
    assert result["metrics"]["maturity_adjusted_credible_early_stage_leads_per_100_queries"] == 100
    assert result["target_results"][0]["actual_maturity"] == "seed_to_series_b"
```

- [ ] **Step 3: Add mature company exclusion test**

Add:

```python
def test_series_c_large_round_does_not_count_as_credible_early_stage():
    target = _target(
        name="Wiz",
        aliases=[],
        domain="wiz.io",
        expected_movement="AI cloud security",
        movement_aliases=["cloud security"],
        maturity_expectation="likely_too_late_or_consensus",
        expected_route="category_context",
    )
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI cloud security startup platform",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": target.expected_movement,
            "market_sector": "Cybersecurity",
            "items": [
                {
                    "title": "Wiz - Cloud Security Platform",
                    "url": "https://www.wiz.io/",
                    "snippet": "Wiz is a category leader that raised a $1B financing round.",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["verified_domains_found"] == 1
    assert result["metrics"]["likely_too_late_found"] == 1
    assert result["metrics"]["category_anchors_found"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 0
    assert result["target_results"][0]["over_promoted"] is False
```

- [ ] **Step 4: Add maturity-not-evaluated test**

Add:

```python
def test_maturity_not_evaluated_does_not_inflate_early_stage_metrics():
    target = _target()
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production startup",
            "query_id": "q1",
            "query_family": "movement_platform",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr - AI agent platform",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "",
                }
            ],
            "skipped": False,
        }
    ]

    result = score_provider_items_against_targets(provider_runs, [target])

    assert result["metrics"]["maturity_not_evaluated"] == 1
    assert result["metrics"]["credible_early_stage_leads"] == 0
```

- [ ] **Step 5: Add family-ranking maturity test**

Add:

```python
def test_query_family_summary_uses_maturity_adjusted_counts(tmp_path):
    target = _target(expected_route="sourcing_candidate")
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production seed startup",
            "query_id": "q1",
            "query_family": "seed_funding",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr raises seed round",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr raised a seed round for AI agent production.",
                }
            ],
            "skipped": False,
        },
        {
            "provider": "brave",
            "query": "AI agent production platform",
            "query_id": "q2",
            "query_family": "movement_platform",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Braintrust - AI evals platform",
                    "url": "https://www.braintrust.dev/",
                    "snippet": "Braintrust is a category leader for AI evals.",
                }
            ],
            "skipped": False,
        },
    ]
    score = score_provider_items_against_targets(provider_runs, [target])
    payload = {"eval_targets": [target.to_dict()], "queries": [], "bakeoff": {"provider_runs": provider_runs}, "score": score}

    write_discovery_yield_artifacts(payload, tmp_path)
    family_payload = json.loads((tmp_path / "query-family-bakeoff.json").read_text())
    rows = {row["query_family"]: row for row in family_payload["families"]}

    assert rows["seed_funding"]["maturity_confirmed_early_stage_domains"] == 1
    assert rows["movement_platform"]["maturity_confirmed_early_stage_domains"] == 0
```

- [ ] **Step 6: Run tests to verify they fail**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Expected: FAIL on missing metrics and old optimistic assertions.

---

## Task 2: Add Maturity Domain Rollup

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`

- [ ] **Step 1: Add maturity constants**

Add near `ROUTE_AGGRESSIVENESS`:

```python
EARLY_MATURITY_STATUSES = {"seed_to_series_b"}
MATURE_MATURITY_STATUSES = {"likely_too_late", "acquired"}
NON_EARLY_ROUTES = {"category_context", "monitor_only"}
MATURITY_SIGNAL_TERMS = (
    "seed",
    "pre-seed",
    "series a",
    "series b",
    "series c",
    "series d",
    "series e",
    "$100m",
    "$1b",
    "valuation",
    "acquired",
    "acquisition",
    "category leader",
    "market leader",
)
```

- [ ] **Step 2: Add helper to identify maturity evidence**

Add after `_movement_terms`:

```python
def _has_maturity_signal(item: dict) -> bool:
    text = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('description', '')}".lower()
    return any(term in text for term in MATURITY_SIGNAL_TERMS)
```

- [ ] **Step 3: Add domain rollup helper**

Add:

```python
def _maturity_rollup_for_domain(domain: str, rows: list[dict], raw_items: list[dict]) -> dict:
    maturity_items = [item for item in raw_items if _normalize_domain_from_url(item.get("url", "")) == domain or _has_maturity_signal(item)]
    if not maturity_items:
        return {
            "domain": domain,
            "maturity_evaluation_status": "not_evaluated",
            "maturity_status": "unknown",
            "lead_route": "research_deeper",
            "likely_too_late": False,
            "category_anchor": False,
            "maturity_basis": [],
            "maturity_evidence_urls": [],
        }
    seed = rows[0]
    maturity = _classify_maturity_from_items(
        maturity_items,
        company_name=seed.get("display_name") or seed.get("canonical_name") or seed.get("name", ""),
        domain=domain,
    )
    status = maturity.get("maturity_status", "unknown")
    return {
        "domain": domain,
        "maturity_evaluation_status": "evaluated_with_evidence" if maturity.get("maturity_basis") else "evaluated_no_maturity_evidence",
        **maturity,
    }
```

- [ ] **Step 4: Add URL-domain helper**

Add:

```python
def _normalize_domain_from_url(url: str) -> str:
    if not url:
        return ""
    raw = url.lower().replace("https://", "").replace("http://", "").split("/", 1)[0]
    return raw[4:] if raw.startswith("www.") else raw
```

- [ ] **Step 5: Apply rollup to accepted rows**

Refactor `score_provider_items_against_targets`:

1. Build `accepted` rows as today.
2. Store raw item provenance per domain:

```python
accepted_items_by_domain.setdefault(_normalize_domain(lead.domain), []).append(item)
```

3. After all rows are accepted, call a new helper:

```python
accepted = _apply_domain_maturity_rollups(accepted, accepted_items_by_domain)
```

4. Then call `_mark_target_if_matched` using the matured row values. If easier, rebuild target results after maturity rollup using a helper:

```python
target_results = _build_target_results(targets, accepted)
```

- [ ] **Step 6: Implement `_apply_domain_maturity_rollups`**

Add:

```python
def _apply_domain_maturity_rollups(accepted: list[dict], accepted_items_by_domain: dict[str, list[dict]]) -> list[dict]:
    rows_by_domain: dict[str, list[dict]] = {}
    for row in accepted:
        domain = _normalize_domain(row.get("domain", ""))
        if domain:
            rows_by_domain.setdefault(domain, []).append(row)
    rollups = {
        domain: _maturity_rollup_for_domain(domain, rows, accepted_items_by_domain.get(domain, []))
        for domain, rows in rows_by_domain.items()
    }
    out = []
    for row in accepted:
        domain = _normalize_domain(row.get("domain", ""))
        rollup = rollups.get(domain, {})
        updated = dict(row)
        updated["maturity_evaluation_status"] = rollup.get("maturity_evaluation_status", "not_evaluated")
        updated["maturity_status"] = rollup.get("maturity_status", updated.get("maturity_status", "unknown"))
        updated["maturity_basis"] = rollup.get("maturity_basis", updated.get("maturity_basis", []))
        updated["maturity_evidence_urls"] = rollup.get("maturity_evidence_urls", updated.get("maturity_evidence_urls", []))
        updated["category_anchor"] = rollup.get("category_anchor", updated.get("category_anchor", False))
        updated["lead_route"] = rollup.get("lead_route", updated.get("lead_route", "research_deeper"))
        updated["likely_too_late"] = rollup.get("likely_too_late", updated.get("likely_too_late", False))
        out.append(updated)
    return out
```

- [ ] **Step 7: Run targeted tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Expected: remaining failures are metric computation and target-result rebuilding.

---

## Task 3: Recompute Target Results After Maturity Rollup

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`

- [ ] **Step 1: Add target result builder**

Replace incremental `_mark_target_if_matched` usage with:

```python
def _build_target_results(targets: list[LeadDiscoveryEvalTarget], accepted: list[dict]) -> list[dict]:
    rows = [_empty_target_result(target) for target in targets]
    accepted_by_domain: dict[str, dict] = {}
    for row in accepted:
        domain = _normalize_domain(row.get("domain", ""))
        if domain and domain not in accepted_by_domain:
            accepted_by_domain[domain] = row
    for index, target in enumerate(targets):
        match = accepted_by_domain.get(_normalize_domain(target.domain))
        if not match:
            continue
        rows[index].update(
            {
                "found": True,
                "actual_route": match.get("lead_route", ""),
                "actual_maturity": match.get("maturity_status", ""),
                "provider": match.get("provider", ""),
                "query_family": match.get("query_family", ""),
                "evaluation_incomplete": match.get("maturity_evaluation_status") == "not_evaluated",
                "maturity_evaluation_status": match.get("maturity_evaluation_status", ""),
                "over_promoted": _route_rank(match.get("lead_route", "")) > _route_rank(target.expected_route),
            }
        )
    return rows
```

- [ ] **Step 2: Update `score_provider_items_against_targets`**

After maturity rollup:

```python
target_results = _build_target_results(targets, accepted)
metrics = _score_metrics(provider_runs, accepted, target_results, total_items, publisher_or_content_junk, targets)
```

Remove calls to `_mark_target_if_matched` inside the provider loop.

- [ ] **Step 3: Keep `_mark_target_if_matched` only if still used**

If `_mark_target_if_matched` is unused, delete it.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Expected: target-result tests pass; metric tests may still fail until Task 4.

---

## Task 4: Replace Optimistic Metrics With Maturity-Adjusted Metrics

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`

- [ ] **Step 1: Update `_score_metrics` domain sets**

Inside `_score_metrics`, compute unique-domain sets:

```python
verified_domains = {_normalize_domain(row.get("domain", "")) for row in accepted if row.get("domain")}
maturity_evaluated_domains = {
    _normalize_domain(row.get("domain", ""))
    for row in accepted
    if row.get("domain") and row.get("maturity_evaluation_status") != "not_evaluated"
}
maturity_confirmed_early_domains = {
    _normalize_domain(row.get("domain", ""))
    for row in accepted
    if row.get("maturity_status") in EARLY_MATURITY_STATUSES
    and row.get("lead_route") in {"sourcing_candidate", "research_deeper"}
}
maturity_unknown_research_deeper_domains = {
    _normalize_domain(row.get("domain", ""))
    for row in accepted
    if row.get("maturity_status") == "unknown"
    and row.get("lead_route") == "research_deeper"
    and row.get("maturity_evaluation_status") != "not_evaluated"
}
maturity_not_evaluated_domains = {
    _normalize_domain(row.get("domain", ""))
    for row in accepted
    if row.get("domain") and row.get("maturity_evaluation_status") == "not_evaluated"
}
category_anchor_domains = {
    _normalize_domain(row.get("domain", ""))
    for row in accepted
    if row.get("lead_route") == "category_context" or row.get("category_anchor")
}
likely_too_late_domains = {
    _normalize_domain(row.get("domain", ""))
    for row in accepted
    if row.get("likely_too_late") or row.get("maturity_status") in MATURE_MATURITY_STATUSES
}
research_worthy_domains = maturity_confirmed_early_domains | maturity_unknown_research_deeper_domains
```

- [ ] **Step 2: Replace metric values**

Return:

```python
"verified_domains_found": len(verified_domains),
"maturity_evaluated_domains": len(maturity_evaluated_domains),
"maturity_confirmed_early_stage": len(maturity_confirmed_early_domains),
"credible_early_stage_leads": len(maturity_confirmed_early_domains),
"maturity_adjusted_credible_early_stage_leads_per_100_queries": round((len(maturity_confirmed_early_domains) / completed_queries) * 100, 2) if completed_queries else 0,
"research_worthy_verified_domains": len(research_worthy_domains),
"research_worthy_verified_domains_per_100_queries": round((len(research_worthy_domains) / completed_queries) * 100, 2) if completed_queries else 0,
"maturity_unknown_research_deeper": len(maturity_unknown_research_deeper_domains),
"maturity_not_evaluated": len(maturity_not_evaluated_domains),
"category_anchors_found": len(category_anchor_domains),
"likely_too_late_found": len(likely_too_late_domains),
"incumbent_or_mature": len(likely_too_late_domains | category_anchor_domains),
"over_promoted_controls": len(false_positive_rows),
```

Keep old `credible_early_stage_leads_per_100_queries` as an alias to the maturity-adjusted value for backwards compatibility:

```python
"credible_early_stage_leads_per_100_queries": round((len(maturity_confirmed_early_domains) / completed_queries) * 100, 2) if completed_queries else 0,
```

- [ ] **Step 3: Update net-new metrics**

Use strict early-stage domains for `net_new_credible_early_stage_leads`:

```python
net_new_maturity_confirmed_domains = maturity_confirmed_early_domains - target_domains
net_new_research_worthy_domains = research_worthy_domains - target_domains
```

Return:

```python
"net_new_verified_domains": len(verified_domains - target_domains),
"net_new_credible_early_stage_leads": len(net_new_maturity_confirmed_domains),
"net_new_research_worthy_verified_domains": len(net_new_research_worthy_domains),
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Expected: all discovery-yield eval tests pass.

---

## Task 5: Make Query-Family Summary Maturity-Aware

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`

- [ ] **Step 1: Update `_query_family_summary`**

Iterate over `score["accepted_leads"]` as well as provider runs. For each `query_family`, calculate unique domains:

```python
accepted = score.get("accepted_leads", [])
for row in accepted:
    family = row.get("query_family", "") or "unknown"
    target = rows.setdefault(
        family,
        {
            "query_family": family,
            "runs": 0,
            "items": 0,
            "skipped": 0,
            "verified_domains": set(),
            "maturity_confirmed_early_stage_domains": set(),
            "maturity_unknown_research_deeper_domains": set(),
            "category_anchor_domains": set(),
            "likely_too_late_domains": set(),
        },
    )
    domain = _normalize_domain(row.get("domain", ""))
    if not domain:
        continue
    target["verified_domains"].add(domain)
    if row.get("maturity_status") in EARLY_MATURITY_STATUSES:
        target["maturity_confirmed_early_stage_domains"].add(domain)
    elif row.get("lead_route") == "research_deeper" and row.get("maturity_status") == "unknown":
        target["maturity_unknown_research_deeper_domains"].add(domain)
    if row.get("lead_route") == "category_context" or row.get("category_anchor"):
        target["category_anchor_domains"].add(domain)
    if row.get("likely_too_late") or row.get("maturity_status") in MATURE_MATURITY_STATUSES:
        target["likely_too_late_domains"].add(domain)
```

Serialize sets as counts and sorted lists:

```python
serialized = []
for row in rows.values():
    serialized.append(
        {
            "query_family": row["query_family"],
            "runs": row["runs"],
            "items": row["items"],
            "skipped": row["skipped"],
            "verified_domains": len(row["verified_domains"]),
            "verified_domain_list": sorted(row["verified_domains"]),
            "maturity_confirmed_early_stage_domains": len(row["maturity_confirmed_early_stage_domains"]),
            "maturity_unknown_research_deeper_domains": len(row["maturity_unknown_research_deeper_domains"]),
            "category_anchor_domains": len(row["category_anchor_domains"]),
            "likely_too_late_domains": len(row["likely_too_late_domains"]),
        }
    )
```

- [ ] **Step 2: Add recommendation labels**

Add `family_recommendation`:

```python
def _family_recommendation(row: dict) -> str:
    if row["maturity_confirmed_early_stage_domains"] > 0:
        return "candidate_for_weekly_trial"
    if row["maturity_unknown_research_deeper_domains"] > 0 and row["category_anchor_domains"] == 0:
        return "research_queue_candidate"
    if row["category_anchor_domains"] or row["likely_too_late_domains"]:
        return "category_context_only_until_maturity_filter_improves"
    return "do_not_graduate_yet"
```

- [ ] **Step 3: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Expected: PASS.

---

## Task 6: Update Summary Markdown

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`

- [ ] **Step 1: Update `_summary_markdown`**

Replace the single optimistic line with both strict and secondary metrics:

```python
f"- Maturity-confirmed early-stage leads per 100 queries: {metrics.get('maturity_adjusted_credible_early_stage_leads_per_100_queries', 0)}",
f"- Research-worthy verified domains per 100 queries: {metrics.get('research_worthy_verified_domains_per_100_queries', 0)}",
f"- Maturity unknown research-deeper domains: {metrics.get('maturity_unknown_research_deeper', 0)}",
f"- Category anchors / likely too late: {metrics.get('incumbent_or_mature', 0)}",
f"- Over-promoted controls: {metrics.get('over_promoted_controls', 0)}",
```

- [ ] **Step 2: Run CLI smoke with no providers**

Run:

```bash
python3 .claude/skills/vc-signals/scripts/discovery_yield_eval.py \
  --output-dir /tmp/vc-signals-phase51-empty \
  --providers "" \
  --eval-mode smoke
```

Expected:
- Exit code `0`
- `/tmp/vc-signals-phase51-empty/discovery-yield-summary.md` exists
- No `weekly-preview.md` changes

---

## Task 7: Re-score Existing Smoke Cache

**Files:**
- Generated only: `docs/radar-runs/current-phase5-discovery-yield-smoke-v2/*`

- [ ] **Step 1: Re-run using existing cache**

Run:

```bash
python3 .claude/skills/vc-signals/scripts/discovery_yield_eval.py \
  --output-dir docs/radar-runs/current-phase5-discovery-yield-smoke-v2 \
  --cache-dir docs/radar-runs/current-phase5-discovery-yield-smoke-v2/provider-cache \
  --providers brave \
  --eval-mode smoke \
  --max-queries-per-provider 40 \
  --max-results-per-query 5 \
  --max-runtime-seconds 300
```

Expected:
- Provider runs should use cache hits.
- No generated artifacts are staged.
- New metrics appear in `lead-discovery-eval.json`.

- [ ] **Step 2: Extract before/after review numbers**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
base = Path("docs/radar-runs/current-phase5-discovery-yield-smoke-v2")
lead = json.loads((base / "lead-discovery-eval.json").read_text())
query = json.loads((base / "query-family-bakeoff.json").read_text())
print(json.dumps(lead["score"]["metrics"], indent=2))
print(json.dumps(query["families"], indent=2))
PY
```

Expected:
- `verified_domains_found` should remain raw recall.
- `credible_early_stage_leads` should drop unless maturity evidence confirms early stage.
- `research_worthy_verified_domains` should retain useful unknown-maturity leads.
- Braintrust/Wiz/Orca/Darktrace-style rows should not inflate strict early-stage yield.

---

## Task 8: Full Verification And Commit

**Files:**
- Commit only code/tests/plan if this plan is amended during execution.
- Do not commit `docs/radar-runs/current-phase5-discovery-yield-smoke-v2`.

- [ ] **Step 1: Run focused tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_search_providers.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full skill suite**

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: PASS, allowing the existing LibreSSL warning.

- [ ] **Step 3: Confirm weekly preview unchanged**

```bash
git diff --name-only -- '*weekly-preview.md' 'docs/**/weekly-preview.md' '.claude/**/weekly-preview.md'
```

Expected: no output.

- [ ] **Step 4: Confirm generated artifacts are uncommitted**

```bash
git status --short docs/radar-runs/current-phase5-discovery-yield-smoke-v2
```

Expected: untracked generated artifact directory only.

- [ ] **Step 5: Commit code changes**

```bash
git add .claude/skills/vc-signals/scripts/discovery_yield_eval.py \
  .claude/skills/vc-signals/tests/test_discovery_yield_eval.py \
  docs/superpowers/plans/2026-05-10-phase-5-1-maturity-aware-bakeoff-scoring.md
git commit -m "Add maturity-aware discovery yield scoring"
```

---

## Definition Of Done

- Phase 5 scoring distinguishes:
  - raw verified-domain recall
  - maturity-confirmed early-stage leads
  - research-worthy unknown-maturity domains
  - category anchors / likely-too-late rows
  - not-evaluated maturity rows
  - over-promoted controls
- `credible_early_stage_leads` no longer counts unknown-maturity domains.
- Query-family rankings use maturity-adjusted unique domains.
- Existing smoke cache can be re-scored without new provider calls.
- `weekly-preview.md` remains unchanged.
- Generated smoke artifacts and provider cache remain uncommitted.
- Full test suite passes.

---

## Self-Review

- Spec coverage: Covers maturity-aware scoring, over-promotion controls, mature-company exclusion, query-family ranking, cached smoke re-score, and no weekly production changes.
- Scope: Does not add providers, new source adapters, X, LinkedIn, Product Hunt, package registries, Slack, or Attio writeback.
- Product stance: Keeps recall metrics visible but makes the north-star metric strict enough to avoid rewarding mature companies as sourcing leads.
