# Phase 6B.6 HN Enrichment Efficiency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the HN outbound enrichment trial complete useful candidate review within bounded runtime by triaging candidates, reordering enrichment stages, moving Attio later, and improving runtime diagnostics.

**Architecture:** Keep HN as an offline source-lane trial. `last30days` continues to own retrieval, while `vc-signals` owns HN outbound interpretation, evidence enrichment, owner-readiness, and artifact reporting. This phase changes only the HN outbound enrichment orchestration in `hn_outbound_enrichment.py`; it does not change weekly default behavior, YC, source discovery, or gates.

**Tech Stack:** Python scripts under `.claude/skills/vc-signals/scripts`, pytest tests under `.claude/skills/vc-signals/tests`, JSON/Markdown artifacts under `docs/radar-runs/`.

---

## Current Evidence

Phase 6B.5 made the larger HN trial bounded but not operationally useful:

- `10` HN outbound candidates attempted.
- `1` candidate completed.
- `9` candidates partially enriched.
- `9` Attio checks ran even though most rows never completed evidence collection.
- `0` Assign owner rows in the larger trial.
- `0` unsafe promotions.
- `budget_exceeded=true` with reasons `per_candidate_timeout_seconds_exceeded`, `live_query_timeout`, and `max_runtime_seconds_exceeded`.

The code currently applies Attio immediately after identity promotion, before maturity, founder/team, and owner evidence. That spends scarce runtime on candidates that may never become actionable.

## Non-Goals

- Do not enable HN in weekly default.
- Do not add YC.
- Do not add new sources.
- Do not add X, LinkedIn, Product Hunt, package registries, Slack, or Attio writeback.
- Do not loosen identity, maturity, founder/team, customer/commercial, Attio, or owner-readiness gates.
- Do not commit generated artifacts, provider caches, or HN enrichment caches.
- Do not modify `weekly-preview.md`.

## Files

- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
  - Add triage helpers.
  - Reorder enrichment stages.
  - Move Attio to a late gate.
  - Add stage-specific runtime accounting and partial reasons.
  - Extend runtime ledger and markdown summary.
- Modify: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`
  - Add regressions for triage, Attio ordering, warm-cache Veris behavior, partial safety, and blocked product/project rows.
- Generated but uncommitted: `docs/radar-runs/current-phase6b6-hn-efficiency-trial/`
  - `hn-outbound-enrichment.json`
  - `hn-outbound-enrichment.md`
  - `hn-enrichment-runtime-ledger.json`

---

### Task 1: Add HN Candidate Triage and Priority Ordering

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Modify: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`

- [ ] **Step 1: Add failing tests for triage buckets**

Add tests that prove triage is execution prioritization only, not a scoring gate. Low priority rows must not be skipped by default; only `skip_or_context` rows are excluded from company enrichment before budget is spent.

```python
def test_hn_enrichment_triage_routes_hosted_demo_to_context_before_live_budget():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    calls = {"query": 0, "attio": 0}

    def query_runner(topic, **kwargs):
        calls["query"] += 1
        return {"items": []}

    def attio_matcher(candidate):
        calls["attio"] += 1
        return {"attio_status": "no_match"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="ARC AGI Swarm Demo",
                    official_url="https://arc-agi-swarm.vercel.app",
                    outbound_domain="arc-agi-swarm.vercel.app",
                    company_domain="arc-agi-swarm.vercel.app",
                    source_title="Show HN: Launch an AI agent swarm for ARC-AGI-3",
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>ARC AGI Swarm Demo</title></html>",
        query_runner=query_runner,
        attio_matcher=attio_matcher,
        max_live_queries=5,
        max_attio_checks=5,
    )

    row = result["product_context_rows"][0]
    ledger = result["runtime_ledger"]["items"][0]
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner"] is False
    assert ledger["priority"] == "skip_or_context"
    assert ledger["partial_reason"] == "hosted_demo_not_company_identity"
    assert row["recommended_lane"] == "HN Product / Project Context"
    assert "hosted_demo_not_company_identity" in row["missing_evidence"]
    assert result["summary"]["product_context_rows"] == 1
    assert calls["query"] == 0
    assert calls["attio"] == 0
```

```python
def test_hn_enrichment_triage_does_not_skip_low_engagement_strong_company_signal():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Veris",
                    source_title="Show HN: Veris - Agent sandboxes with simulated external services",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                    hn_engagement={"points": 1, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
    )

    ledger = result["runtime_ledger"]["items"][0]
    assert ledger["priority"] in {"high_priority", "normal_priority"}
    assert ledger["partial_reason"] != "budget_skipped_low_priority"
```

```python
def test_hn_enrichment_low_priority_is_enriched_when_budget_remains():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="TinyTool",
                    source_title="Show HN: TinyTool",
                    official_url="",
                    outbound_domain="tinytool",
                    company_domain="tinytool",
                    hn_engagement={"points": 0, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>TinyTool</title><body>TinyTool workflow automation</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        max_candidates=1,
        max_runtime_seconds=30,
    )

    ledger = result["runtime_ledger"]["items"][0]
    assert ledger["priority"] == "low_priority"
    assert ledger["partial_reason"] != "budget_skipped_low_priority"
    assert result["summary"]["candidates_enriched"] == 1
```

```python
def test_hn_enrichment_processes_high_priority_before_low_priority_budget_skip():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="TinyTool",
                    source_title="Show HN: TinyTool",
                    official_url="",
                    outbound_domain="tinytool",
                    company_domain="tinytool",
                    hn_engagement={"points": 0, "comments": 0},
                ),
                _hn_outbound(
                    name="Veris",
                    source_title="Show HN: Veris - Agent sandboxes with simulated external services",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                ),
            ]
        ),
        page_fetcher=lambda url: "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        max_candidates=1,
        max_runtime_seconds=30,
    )

    ledger_items = result["runtime_ledger"]["items"]
    assert ledger_items[0]["name"] == "Veris"
    assert ledger_items[0]["priority"] in {"high_priority", "normal_priority"}
    assert ledger_items[1]["name"] == "TinyTool"
    assert ledger_items[1]["priority"] == "low_priority"
    assert ledger_items[1]["partial_reason"] in {"max_candidates_exceeded", "budget_skipped_low_priority"}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py \
  -k "triage"
```

Expected: fail because priority ordering, context routing, and priority ledger fields are not implemented.

- [ ] **Step 3: Implement triage helper**

Add constants and helper near the top of `hn_outbound_enrichment.py`:

```python
PRIORITY_HIGH = "high_priority"
PRIORITY_NORMAL = "normal_priority"
PRIORITY_LOW = "low_priority"
PRIORITY_SKIP_OR_CONTEXT = "skip_or_context"

HOSTED_DEMO_SUFFIXES = (
    ".vercel.app",
    ".netlify.app",
    ".github.io",
    ".pages.dev",
)

PRODUCT_SUBDOMAIN_PREFIXES = (
    "app.",
    "cli.",
    "docs.",
    "demo.",
    "api.",
)


def _triage_hn_candidate(row: dict, *, cache_dir: Path | None = None) -> dict:
    name = str(row.get("name") or row.get("source_title") or "").strip()
    title = str(row.get("source_title") or name).lower()
    domain = _normalize_domain(row.get("company_domain") or row.get("outbound_domain") or "")
    engagement = row.get("hn_engagement") or {}
    points = int(engagement.get("points") or 0)
    comments = int(engagement.get("comments") or 0)
    reasons: list[str] = []

    if any(domain.endswith(suffix) for suffix in HOSTED_DEMO_SUFFIXES):
        return {
            "priority": PRIORITY_SKIP_OR_CONTEXT,
            "reasons": ["hosted_demo_not_company_identity"],
            "should_enrich": False,
            "context_lane": "HN Product / Project Context",
        }

    if any(domain.startswith(prefix) for prefix in PRODUCT_SUBDOMAIN_PREFIXES):
        return {
            "priority": PRIORITY_SKIP_OR_CONTEXT,
            "reasons": ["product_subdomain_risk"],
            "should_enrich": False,
            "context_lane": "HN Product / Category Context",
        }

    if re.search(r"\((?:YC|Y\s+Combinator)\s+[SWF]\d{2}\)", title, re.IGNORECASE):
        reasons.append("accelerator_hint")

    if row.get("official_url") and domain and domain in _normalize_domain(row.get("official_url", "")):
        reasons.append("official_domain_url")

    if domain and "." in domain and not any(domain.endswith(suffix) for suffix in HOSTED_DEMO_SUFFIXES):
        reasons.append("company_looking_domain")

    if points >= 20 or comments >= 5:
        reasons.append("hn_engagement")

    if cache_dir and _has_hn_candidate_cache(domain, cache_dir):
        reasons.append("cache_available")

    if "accelerator_hint" in reasons or "cache_available" in reasons or "official_domain_url" in reasons:
        priority = PRIORITY_HIGH
    elif "company_looking_domain" in reasons:
        priority = PRIORITY_NORMAL
    else:
        priority = PRIORITY_LOW

    return {"priority": priority, "reasons": reasons or ["weak_source_signal"], "should_enrich": True}
```

Add a small cache helper:

```python
def _has_hn_candidate_cache(domain: str, cache_dir: Path) -> bool:
    if not domain:
        return False
    needles = [
        cache_dir / "hn-official-pages",
        cache_dir / "official-pages",
        cache_dir / "hn-outbound-queries",
        cache_dir / "queries",
    ]
    return any(path.exists() and any(path.iterdir()) for path in needles)
```

- [ ] **Step 4: Pre-triage rows and process high/normal before low**

Before the main enrichment loop, build an ordered queue:

```python
priority_order = {
    PRIORITY_HIGH: 0,
    PRIORITY_NORMAL: 1,
    PRIORITY_LOW: 2,
    PRIORITY_SKIP_OR_CONTEXT: 3,
}
prepared_rows = []
for original_index, row in enumerate(rows):
    triage = _triage_hn_candidate(row, cache_dir=cache_path)
    prepared_rows.append({"row": row, "triage": triage, "original_index": original_index})
prepared_rows.sort(key=lambda item: (priority_order.get(item["triage"]["priority"], 99), item["original_index"]))
```

Then iterate over `prepared_rows` rather than raw `rows`. Preserve `original_index` in the ledger so the artifact remains traceable.

- [ ] **Step 5: Attach triage to ledger and route context rows before expensive calls**

Inside `run_hn_outbound_enrichment`, after `candidate = _candidate_from_hn_row(row)`, run triage:

```python
ledger["priority"] = triage["priority"]
ledger["priority_reasons"] = list(triage["reasons"])
if not triage["should_enrich"]:
    reason = (triage["reasons"] or ["not_company_identity"])[0]
    row_payload = _context_row(row, reason=reason, lane=triage.get("context_lane", "HN Product / Project Context"), ledger=ledger)
    row_payload["priority"] = triage["priority"]
    row_payload["priority_reasons"] = list(triage["reasons"])
    _finalize_ledger_item(ledger, row_payload, started_at=candidate_started_at, runtime=runtime)
    triage_context_rows.append(row_payload)
    continue
```

Initialize `triage_context_rows: list[dict] = []` before the loop and merge it into product/context output:

```python
passthrough_product = triage_context_rows + list(phase6b_payload.get("product_context_rows", []) or [])
```

Extend `_new_ledger_item` with:

```python
"original_index": index,
"priority": "",
"priority_reasons": [],
```

- [ ] **Step 6: Add context row helper**

Add:

```python
def _context_row(row: dict, *, reason: str, lane: str, ledger: dict) -> dict:
    ledger["status"] = "completed"
    ledger["partial_reason"] = reason
    return {
        "name": row.get("name") or row.get("source_title") or row.get("company_domain") or "",
        "canonical_name": row.get("name") or row.get("company_domain") or "",
        "official_domain": row.get("company_domain") or row.get("outbound_domain") or "",
        "source_title": row.get("source_title", ""),
        "source_url": row.get("source_url", ""),
        "official_url": row.get("official_url", ""),
        "identity_type": "hn_context_candidate",
        "identity_promotion_status": "not_promoted",
        "maturity_status": row.get("maturity_status", "unknown"),
        "lead_route": "research_deeper",
        "owner_readiness_score": 0,
        "owner_readiness_basis": [],
        "missing_owner_evidence": [reason],
        "recommended_action": ACTION_RESEARCH_DEEPER,
        "recommended_lane": lane,
        "next_validation_step": "Use as launch/context evidence only; find official company domain before enrichment",
        "assign_owner": False,
        "new_to_marathon": False,
        "unsafe_promotion": False,
        "partial": False,
        "partial_reason": reason,
        "missing_evidence": [reason],
        "movement": row.get("movement", ""),
        "market_sector": row.get("market_sector", ""),
    }
```

- [ ] **Step 7: Run triage tests**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py \
  -k "triage"
```

Expected: pass.

---

### Task 2: Move Attio to a Late Gate

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Modify: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`

- [ ] **Step 1: Add failing test proving Attio is not called before evidence threshold**

```python
def test_hn_enrichment_does_not_call_attio_before_meaningful_evidence():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    calls = {"attio": 0}

    def attio_matcher(candidate):
        calls["attio"] += 1
        return {"attio_status": "no_match", "attio_action": "assign owner"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=attio_matcher,
        max_attio_checks=5,
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["identity_type"] == "verified_company"
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner"] is False
    assert calls["attio"] == 0
    assert result["runtime_ledger"]["summary"]["attio_checks"] == 0
```

- [ ] **Step 2: Add failing test proving Attio still runs after evidence exists**

```python
def test_hn_enrichment_calls_attio_after_identity_and_evidence_threshold():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    calls = {"attio": 0}

    def attio_matcher(candidate):
        calls["attio"] += 1
        return {"attio_status": "no_owner"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: (
            "<html><title>Burrow</title><body>Burrow was founded by Jane Doe. "
            "Burrow raised a seed round. Burrow works with security teams.</body></html>"
        ),
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=attio_matcher,
        max_attio_checks=5,
    )

    row = result["enriched_outbound_candidates"][0]
    assert calls["attio"] == 1
    assert row["attio_status"] == "no_owner"
    assert result["runtime_ledger"]["summary"]["attio_checks"] == 1
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py \
  -k "attio"
```

Expected: first new test fails because Attio currently runs immediately after identity promotion.

- [ ] **Step 4: Add evidence-threshold helper**

Add:

```python
def _meaningful_evidence_dimensions(candidate: Candidate) -> set[str]:
    dimensions: set[str] = set()
    if _named_founder_profiles(candidate) or candidate.founders:
        dimensions.add("founder")
    if candidate.maturity_status == "seed_to_series_b" or candidate.stage_funding_evidence or candidate.maturity_evidence_urls:
        dimensions.add("stage")
    if _strong_customer_evidence_types(candidate) or candidate.customer_buyer_evidence:
        dimensions.add("customer")
    if candidate.maturity_status == "early_stage_context":
        dimensions.add("early_stage_context")
    return dimensions


def _eligible_for_attio(candidate: Candidate) -> bool:
    if candidate.identity_type != "verified_company":
        return False
    if candidate.category_anchor or candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return False
    return bool(_meaningful_evidence_dimensions(candidate))
```

- [ ] **Step 5: Reorder the enrichment stages**

Change `run_hn_outbound_enrichment` so Attio happens after maturity, founder/team, and owner evidence:

```python
if promoted.identity_type == "verified_company":
    promoted, maturity_report = _enrich_maturity(...)
    reports["maturity"].append(maturity_report)
else:
    reports["maturity"].append(_skipped_maturity_report(promoted, "identity_not_promoted"))

final_candidate = promoted

if final_candidate.identity_type == "verified_company" and not runtime.candidate_exceeded(candidate_started_at):
    founder_enriched, founder_report = enrich_founder_team_verification(...)
    final_candidate = founder_enriched[0]

if final_candidate.identity_type == "verified_company" and not runtime.candidate_exceeded(candidate_started_at):
    owner_enriched, owner_report = enrich_owner_evidence(...)
    final_candidate = owner_enriched[0]

if final_candidate.identity_type == "verified_company" and not runtime.candidate_exceeded(candidate_started_at):
    if _eligible_for_attio(final_candidate):
        final_candidate = _apply_attio(final_candidate, attio_matcher, runtime=runtime, ledger=ledger)
    else:
        ledger["attio_skipped"] += 1
        ledger["attio_skip_reason"] = "insufficient_evidence_before_attio"
        final_candidate.attio_status = final_candidate.attio_status or "unknown"
```

- [ ] **Step 6: Run Attio tests**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py \
  -k "attio"
```

Expected: pass.

---

### Task 3: Add Stage-Specific Timeout and Budget Reasons

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Modify: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`

- [ ] **Step 1: Add failing tests for stage-specific query timeout reason**

```python
def test_hn_enrichment_founder_query_timeout_has_specific_reason():
    import time
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def slow_query(topic, **kwargs):
        time.sleep(0.05)
        return {"items": []}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        query_runner=slow_query,
        max_runtime_seconds=1,
        per_candidate_timeout_seconds=0.01,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    assert row["assign_owner"] is False
    assert ledger["partial_reason"] in {
        "founder_query_timeout",
        "maturity_query_timeout",
        "owner_query_timeout",
        "per_candidate_timeout_seconds_exceeded",
    }
```

- [ ] **Step 2: Implement query stage labels**

Change `_budgeted_query_runner` signature:

```python
def _budgeted_query_runner(
    query_runner: Callable | None,
    *,
    runtime: _RuntimeBudget,
    ledger: dict,
    default_stage: str = "query",
) -> Callable | None:
```

Add:

```python
def _query_timeout_reason(topic: str, default_stage: str) -> str:
    lowered = topic.lower()
    if "founder" in lowered or "co-founder" in lowered or "team" in lowered:
        return "founder_query_timeout"
    if "funding" in lowered or "seed" in lowered or "series" in lowered or "valuation" in lowered:
        return "maturity_query_timeout"
    if "customer" in lowered or "case study" in lowered or "buyer" in lowered or "waitlist" in lowered:
        return "customer_query_timeout"
    return f"{default_stage}_query_timeout"
```

In `_budgeted_query_runner`, replace `live_query_timeout` with:

```python
reason = _query_timeout_reason(topic, default_stage)
runtime.mark_timeout(reason)
ledger["timeouts"] += 1
ledger["partial_reason"] = ledger["partial_reason"] or reason
return {"items": [], "_timeout": True, "timeout_reason": reason}
```

- [ ] **Step 3: Use stage-specific wrappers at call sites**

Use:

```python
_budgeted_query_runner(query_runner, runtime=runtime, ledger=ledger, default_stage="maturity")
```

for `_enrich_maturity`.

Use:

```python
_budgeted_query_runner(query_runner, runtime=runtime, ledger=ledger, default_stage="founder")
```

for `enrich_founder_team_verification`.

Use:

```python
_budgeted_query_runner(query_runner, runtime=runtime, ledger=ledger, default_stage="owner")
```

for `enrich_owner_evidence`.

- [ ] **Step 4: Add stage counters to ledger**

Extend `_new_ledger_item`:

```python
"maturity_queries": 0,
"founder_queries": 0,
"owner_queries": 0,
"customer_queries": 0,
"maturity_query_timeouts": 0,
"founder_query_timeouts": 0,
"customer_query_timeouts": 0,
"owner_query_timeouts": 0,
```

When running a query, increment based on `_query_timeout_reason(topic, default_stage)` and `default_stage`.

- [ ] **Step 5: Run timeout tests**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py \
  -k "timeout or runtime"
```

Expected: pass.

---

### Task 4: Add Cache-First Accounting, Evidence Labels, and Durable URLs

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Modify: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`

- [ ] **Step 1: Add failing test for warm-cache Veris with low live budget**

Keep the existing Veris warm-cache behavior, but assert explicit stage cache accounting:

```python
def test_veris_warm_page_evidence_assigns_owner_with_zero_live_queries_and_stage_cache_ledger():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def fake_fetcher(url):
        if url.endswith("/blog"):
            return (
                "<html><body><p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Enterprise teams can book demo access for AI agent validation.</p></body></html>"
            )
        return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Veris",
                    source_title="Show HN: Veris - Agent sandboxes with simulated external services",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                )
            ]
        ),
        page_fetcher=fake_fetcher,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live query should not run")),
        attio_matcher=lambda candidate: {"attio_status": "no_owner"},
        max_live_queries=0,
        max_attio_checks=1,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    assert row["assign_owner"] is True
    assert ledger["live_queries"] == 0
    assert ledger["page_fetches"] >= 1
    assert ledger["evidence_dimensions"] == ["customer", "founder", "stage"]
    assert "commercial_intent_evidence" in ledger["customer_evidence_labels"]
```

- [ ] **Step 2: Add ledger field for evidence dimensions**

Add to `_finalize_ledger_item`:

```python
ledger["evidence_dimensions"] = sorted(_row_evidence_dimensions(row))
```

Add helper:

```python
def _row_evidence_dimensions(row: dict) -> set[str]:
    dimensions: set[str] = set()
    if row.get("founder_team_evidence") or row.get("founders"):
        dimensions.add("founder")
    if row.get("stage_funding_evidence") or row.get("maturity_status") == "seed_to_series_b":
        dimensions.add("stage")
    if row.get("customer_buyer_evidence") or row.get("customer_buyer_evidence_types"):
        dimensions.add("customer")
    if row.get("maturity_status") == "early_stage_context":
        dimensions.add("early_stage_context")
    return dimensions
```

Also preserve the customer/commercial evidence labels rather than collapsing them into a generic `customer` bucket:

```python
def _row_customer_evidence_labels(row: dict) -> list[str]:
    labels: list[str] = []
    for item in row.get("customer_buyer_evidence_types") or []:
        labels.extend(item.get("evidence_types") or [])
    return sorted(dict.fromkeys(labels))
```

Then in `_finalize_ledger_item`:

```python
ledger["customer_evidence_labels"] = _row_customer_evidence_labels(row)
```

- [ ] **Step 3: Add stage cache counters**

Extend `_new_ledger_item`:

```python
"maturity_query_cache_hits": 0,
"founder_query_cache_hits": 0,
"owner_query_cache_hits": 0,
"customer_query_cache_hits": 0,
"official_page_cache_hits": 0,
"evidence_dimensions": [],
"customer_evidence_labels": [],
```

Update `_run_cached_query` to accept a `stage` argument:

```python
def _run_cached_query(topic: str, *, query_runner: Callable | None, cache_dir: Path | None, ledger: dict | None = None, stage: str = "query") -> tuple[dict, str]:
```

When cache hit occurs:

```python
if ledger is not None:
    ledger["query_cache_hits"] += 1
    stage_key = f"{stage}_query_cache_hits"
    if stage_key in ledger:
        ledger[stage_key] += 1
```

Call maturity with `stage="maturity"`.

- [ ] **Step 4: Preserve durable evidence URLs when exact sources are available**

Do not replace exact evidence URLs with a generic page like `https://veris.ai/blog` when a more durable source is available from official-page links or exact enrichment query results. Add a small URL preference helper:

```python
def _prefer_durable_evidence_urls(urls: list[str]) -> list[str]:
    durable_markers = (
        "/blog-posts/",
        "businesswire.com/",
        "gunder.com/",
        "ycombinator.com/companies/",
    )
    normalized = list(dict.fromkeys(url for url in urls if url))
    durable = [url for url in normalized if any(marker in url.lower() for marker in durable_markers)]
    generic = [url for url in normalized if url not in durable]
    return (durable + generic)[:5]
```

Also add a tiny link extractor for official pages that mention a durable launch/news URL:

```python
def _extract_durable_links_from_html(html: str, *, base_domain: str = "") -> list[str]:
    links = re.findall(r'href=["\\']([^"\\']+)["\\']', html or "", flags=re.IGNORECASE)
    out: list[str] = []
    for link in links:
        lowered = link.lower()
        if any(marker in lowered for marker in ("/blog-posts/", "businesswire.com/", "gunder.com/", "ycombinator.com/companies/")):
            if link.startswith("/") and base_domain:
                out.append(f"https://{base_domain}{link}")
            elif link.startswith("http"):
                out.append(link)
    return list(dict.fromkeys(out))
```

Merge durable links into the relevant evidence URL lists when the same page text produced founder/stage/customer evidence. Apply `_prefer_durable_evidence_urls` before writing `founder_team_evidence`, `stage_funding_evidence`, and `customer_buyer_evidence` in `_row_from_candidate` or `_strict_hn_owner_outputs`.

Add a Veris regression that accepts exact durable URLs when they are present:

```python
def test_veris_evidence_prefers_durable_urls_over_blog_index():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    durable_url = "https://veris.ai/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"

    def fake_fetcher(url):
        if url.endswith("/blog"):
            return (
                f'<html><body><a href="{durable_url}">Introducing Veris AI</a>'
                "<p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Enterprise teams can book demo access for AI agent validation.</p></body></html>"
            )
        return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Veris",
                    source_title="Show HN: Veris - Agent sandboxes with simulated external services",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                )
            ]
        ),
        page_fetcher=fake_fetcher,
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=lambda candidate: {"attio_status": "no_owner"},
        max_live_queries=0,
    )

    row = result["enriched_outbound_candidates"][0]
    assert durable_url in row["founder_team_evidence"] or durable_url in row["stage_funding_evidence"] or durable_url in row["customer_buyer_evidence"]
    assert row["assign_owner"] is True
```

- [ ] **Step 5: Run cache tests**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py \
  -k "cache or Veris or veris"
```

Expected: pass.

---

### Task 5: Update Runtime Ledger and Markdown Review Output

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Modify: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`

- [ ] **Step 1: Add test for ledger summary fields**

```python
def test_hn_enrichment_runtime_ledger_reports_priority_and_stage_counts(tmp_path):
    from hn_outbound_enrichment import run_hn_outbound_enrichment, write_hn_outbound_enrichment_artifacts

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
    )

    paths = write_hn_outbound_enrichment_artifacts(result, tmp_path)
    ledger = json.loads((tmp_path / "hn-enrichment-runtime-ledger.json").read_text())
    item = ledger["items"][0]
    assert "priority" in item
    assert "priority_reasons" in item
    assert "evidence_dimensions" in item
    assert "attio_skip_reason" in item
    assert "maturity_queries" in item
    assert "founder_queries" in item
    assert "owner_queries" in item
    assert tmp_path / "hn-outbound-enrichment.md" in paths
```

- [ ] **Step 2: Extend ledger summary**

In `_runtime_ledger_payload`, add summary fields:

```python
"high_priority_candidates": sum(1 for item in items if item.get("priority") == PRIORITY_HIGH),
"normal_priority_candidates": sum(1 for item in items if item.get("priority") == PRIORITY_NORMAL),
"low_priority_candidates": sum(1 for item in items if item.get("priority") == PRIORITY_LOW),
"skip_or_context_candidates": sum(1 for item in items if item.get("priority") == PRIORITY_SKIP_OR_CONTEXT),
"official_page_cache_hits": sum(int(item.get("official_page_cache_hits", 0)) for item in items),
"maturity_query_cache_hits": sum(int(item.get("maturity_query_cache_hits", 0)) for item in items),
"founder_query_cache_hits": sum(int(item.get("founder_query_cache_hits", 0)) for item in items),
"customer_query_cache_hits": sum(int(item.get("customer_query_cache_hits", 0)) for item in items),
"owner_query_cache_hits": sum(int(item.get("owner_query_cache_hits", 0)) for item in items),
```

- [ ] **Step 3: Update Markdown**

Add a runtime section:

```python
lines.extend(["", "## Runtime Ledger", ""])
ledger = payload.get("runtime_ledger", {}).get("summary", {})
for key in (
    "candidates_completed",
    "candidates_partially_enriched",
    "candidates_skipped",
    "high_priority_candidates",
    "normal_priority_candidates",
    "skip_or_context_candidates",
    "live_queries",
    "attio_checks",
    "page_fetches",
    "timeouts",
):
    lines.append(f"- {key}: {ledger.get(key, 0)}")
```

- [ ] **Step 4: Run artifact test**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py \
  -k "ledger or artifacts"
```

Expected: pass.

---

### Task 6: Full Regression Suite

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Modify: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`

- [ ] **Step 1: Run targeted HN enrichment tests**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py
```

Expected: all tests pass.

- [ ] **Step 2: Run full vc-signals suite**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 -m pytest -q \
  .claude/skills/vc-signals/tests
```

Expected: all tests pass. A urllib3 LibreSSL warning is acceptable if it matches prior runs.

- [ ] **Step 3: Confirm weekly preview is unchanged**

Run:

```bash
git diff -- weekly-preview.md docs/radar-runs/current/weekly-preview.md
```

Expected: no output.

---

### Task 7: Rerun Larger HN-Only Trial

**Files:**
- Read: `docs/radar-runs/current-phase6b5-hn-larger-gated-trial/hn-gated-source-trial.json`
- Write generated artifacts only: `docs/radar-runs/current-phase6b6-hn-efficiency-trial/`

- [ ] **Step 1: Run larger bounded HN enrichment**

Run:

```bash
PYTHONPATH=.claude/skills/vc-signals/scripts python3 .claude/skills/vc-signals/scripts/hn_outbound_enrichment.py \
  --phase6b-json docs/radar-runs/current-phase6b5-hn-larger-gated-trial/hn-gated-source-trial.json \
  --cache-dir docs/radar-runs/current-phase6b6-hn-efficiency-trial/cache \
  --output-dir docs/radar-runs/current-phase6b6-hn-efficiency-trial \
  --live-queries --attio \
  --max-candidates 10 \
  --max-runtime-seconds 90 \
  --max-attio-checks 10 \
  --max-live-queries 25 \
  --per-candidate-timeout-seconds 8
```

- [ ] **Step 2: Summarize artifacts**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("docs/radar-runs/current-phase6b6-hn-efficiency-trial/hn-outbound-enrichment.json")
data = json.loads(p.read_text())
print(json.dumps({
  "partial": data.get("partial"),
  "budget_exceeded": data.get("budget_exceeded"),
  "budget_reasons": data.get("budget_reasons"),
  "summary": data.get("summary"),
  "ledger_summary": data.get("runtime_ledger", {}).get("summary"),
}, indent=2))
PY
```

Expected: report is complete enough to judge whether high/normal-priority rows completed. It is acceptable for low-priority rows to be skipped. It is not acceptable for partial rows to become Assign owner.

- [ ] **Step 3: Inspect row-level outcomes**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("docs/radar-runs/current-phase6b6-hn-efficiency-trial/hn-enrichment-runtime-ledger.json")
data = json.loads(p.read_text())
for row in data.get("items", []):
    print(json.dumps({
        "name": row.get("name"),
        "domain": row.get("domain"),
        "priority": row.get("priority"),
        "status": row.get("status"),
        "partial_reason": row.get("partial_reason"),
        "evidence_dimensions": row.get("evidence_dimensions"),
        "live_queries": row.get("live_queries"),
        "attio_checks": row.get("attio_checks"),
        "final_action": row.get("final_action"),
        "unsafe_promotion": row.get("unsafe_promotion"),
    }, indent=2))
PY
```

Expected:
- `unsafe_promotion` remains false for every row.
- `attio_checks` are materially lower than the number of identity-promoted rows unless evidence thresholds are met.
- Stage-specific partial reasons explain where budget failed.

---

### Task 8: Commit Code Only

**Files:**
- Stage: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Stage: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`
- Do not stage: `docs/radar-runs/current-phase6b6-hn-efficiency-trial/`
- Do not stage: `.claude/skills/vc-signals/data/companies/hn_enrichment_cache.json`

- [ ] **Step 1: Review status**

Run:

```bash
git status --short
```

Expected: only the two code/test files are staged later; generated artifacts remain untracked.

- [ ] **Step 2: Stage code and tests**

Run:

```bash
git add .claude/skills/vc-signals/scripts/hn_outbound_enrichment.py \
  .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py
```

- [ ] **Step 3: Commit**

Run:

```bash
git commit -m "Prioritize HN outbound enrichment runtime"
```

---

## Acceptance Criteria

- HN remains offline/trial-only.
- YC remains parked.
- No weekly default behavior changes.
- `weekly-preview.md` remains unchanged.
- Partial rows cannot become Assign owner.
- Product/subdomain rows and project-only rows remain blocked from company promotion.
- Hosted demo domains become product/project context evidence, not verified company leads and not dropped rows.
- Attio runs late, only after verified identity plus meaningful evidence.
- Larger HN trial writes complete artifacts even if partial.
- Ledger reports priority, stage-specific timeout reasons, cache hits, live calls, Attio checks, evidence dimensions, and typed customer/commercial evidence labels.
- Veris remains owner-ready under sufficient budget and warm-cache conditions.
- Veris uses exact durable evidence URLs when available rather than only generic pages like `/blog`.
- The larger HN trial shows improved budget allocation: high/normal-priority rows complete or fail with precise stage reasons; low-priority rows may be skipped honestly.
- Low-priority rows are not skipped by default; they are enriched when budget remains after high/normal-priority rows.
- Generated artifacts and provider/cache files remain uncommitted.

## Repo Hygiene Follow-Up

`.git/gc.log` currently says there are too many unreachable loose objects and recommends `git prune`. Treat that as separate housekeeping after the product commit:

```bash
git status --short
cat .git/gc.log
git gc
```

Do not mix git cleanup with the Phase 6B.6 implementation commit.
