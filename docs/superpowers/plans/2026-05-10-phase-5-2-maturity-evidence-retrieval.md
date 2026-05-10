# Phase 5.2 Maturity Evidence Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take verified domains from the Phase 5 bakeoff and run exact company/domain-scoped maturity checks so the eval can distinguish maturity-confirmed early-stage leads from category anchors, acquired/mature companies, and research-worthy unknowns.

**Architecture:** Add a post-discovery maturity retrieval layer that consumes existing bakeoff accepted leads, generates exact-name/domain maturity queries, uses the existing provider/cache wrapper, classifies evidence with existing maturity logic, and writes `maturity-evidence-bakeoff.json`. The discovery bakeoff remains offline and does not change weekly production routing.

**Tech Stack:** Python, pytest, existing `discovery_yield_eval.py`, `discovery_search_providers.py`, and `radar_company_discovery.py` maturity helpers.

---

## Scope

Allowed:
- Use verified domains already produced by Phase 5 bakeoff accepted leads.
- Use exact company/domain-scoped maturity queries only.
- Use cached Brave/provider results where available.
- Run live provider calls only when explicitly invoked by CLI and within budget.
- Re-score `lead-discovery-eval.json` after maturity evidence retrieval.

Not allowed:
- No broad discovery.
- No X, LinkedIn scraping, Product Hunt, package registries, Slack, or Attio writeback.
- No query-family graduation into weekly.
- No `weekly-preview.md` changes.
- No generated artifact/provider-cache commits.

---

## Product Rules

1. Maturity retrieval runs per unique verified domain, not per accepted row.
2. Query text must include exact company name and/or domain.
3. Maturity evidence can update eval scoring only if the result matches the same company/domain.
4. `seed`, `pre-seed`, `Series A`, or `Series B` evidence can route to `seed_to_series_b`.
5. `Series C+`, `$100M+`, `$1B+ valuation`, `category leader`, `market leader`, `acquired`, or incumbent ownership evidence routes to `category_context` or `monitor_only`.
6. No evidence keeps the domain in `maturity_unknown_research_deeper`.
7. Eval target expectations are used to score over-promotion, not to override evidence.
8. The artifact should report whether maturity unknown decreased and why.

---

## Required Execution Patches

These patches are mandatory during implementation:

1. Keep `run_maturity_evidence_bakeoff()` aligned with the current provider wrapper. In this repo, `run_provider_query(provider, query, ...)` expects a query dict, so the maturity runner must pass the full query dict and then attach `query_id`, `query_kind`, `domain`, and `company_name` to the returned run.
2. Domain normalization must handle URL paths and subdomains. A target can match an exact domain or subdomain via `item_domain == domain or item_domain.endswith("." + domain)`, but not unrelated suffix tricks.
3. Same-company/domain matching is not enough for maturity classification. Items must also contain explicit maturity terms.
4. Generic `seed` must not count as funding stage evidence. Use safer patterns such as `seed round`, `raised seed`, `raises seed`, `pre-seed`, `Series A`, and `Series B`.
5. CLI priority-domain extraction must tolerate `target_domain`, `domain`, or `expected_domain`.
6. `maturity_evaluation_status` must use only `not_evaluated`, `evaluated_no_maturity_evidence`, or `evaluated_with_evidence`. Store details such as `domains_with_no_maturity_results` in a separate reason field and summary counters.
7. Add a mature-domain regression such as Wiz/Orca/Darktrace proving mature net-new domains do not count as early-stage after evidence is applied.

---

## File Structure

Create:
- `.claude/skills/vc-signals/scripts/discovery_maturity_evidence.py`
  - Extract verified-domain targets from `lead-discovery-eval.json`.
  - Generate exact maturity queries.
  - Run/cache maturity evidence provider calls.
  - Classify maturity evidence and update accepted leads.
  - Write `maturity-evidence-bakeoff.json`.

- `.claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py`
  - Unit tests for target extraction, query generation, provider-result normalization, maturity classification, cache use, and artifact writing.

Modify:
- `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
  - Add optional CLI arguments to consume `maturity-evidence-bakeoff.json` and re-score accepted leads.
  - Keep existing Phase 5 command shape working.

- `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`
  - Add tests proving maturity evidence updates Phase 5.1 metrics without weakening gates.

Do not modify:
- `weekly-preview.md`.
- Production weekly pipeline files unless a tiny import-safe helper is unavoidable.

Generated only:
- `docs/radar-runs/current-phase5-2-maturity-evidence-check/maturity-evidence-bakeoff.json`
- `docs/radar-runs/current-phase5-2-maturity-evidence-check/provider-cache/*`

---

## Task 1: Maturity Target Extraction Tests

**Files:**
- Create: `.claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
from discovery_maturity_evidence import extract_maturity_targets


def test_extract_maturity_targets_dedupes_verified_domains():
    score_payload = {
        "accepted_leads": [
            {"display_name": "Lyzr", "domain": "lyzr.ai", "query_family": "official_company_page"},
            {"display_name": "Lyzr", "domain": "www.lyzr.ai", "query_family": "movement_platform"},
            {"display_name": "Braintrust", "domain": "braintrust.dev", "query_family": "official_company_page"},
        ]
    }

    targets = extract_maturity_targets(score_payload)

    assert [target["domain"] for target in targets] == ["lyzr.ai", "braintrust.dev"]
    assert targets[0]["company_name"] == "Lyzr"
    assert targets[0]["source_query_families"] == ["movement_platform", "official_company_page"]


def test_extract_maturity_targets_prioritizes_eval_targets_and_strong_families():
    score_payload = {
        "target_results": [
            {"target_name": "Lyzr", "target_domain": "lyzr.ai", "found": True},
            {"target_name": "Braintrust", "target_domain": "braintrust.dev", "found": True},
        ],
        "accepted_leads": [
            {"display_name": "Wiz", "domain": "wiz.io", "query_family": "official_company_page"},
            {"display_name": "Lyzr", "domain": "lyzr.ai", "query_family": "movement_platform"},
            {"display_name": "Braintrust", "domain": "braintrust.dev", "query_family": "official_company_page"},
        ],
    }

    targets = extract_maturity_targets(score_payload, priority_domains=["lyzr.ai", "braintrust.dev"])

    assert [target["domain"] for target in targets][:2] == ["lyzr.ai", "braintrust.dev"]
```

- [ ] **Step 2: Run tests and verify red**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py -q
```

Expected: import failure because `discovery_maturity_evidence.py` does not exist.

---

## Task 2: Implement Target Extraction

**Files:**
- Create: `.claude/skills/vc-signals/scripts/discovery_maturity_evidence.py`

- [ ] **Step 1: Add implementation**

Create:

```python
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from discovery_search_providers import load_provider_env_files, run_provider_query
from discovery_yield_eval import route_rank
from radar_company_discovery import _classify_maturity_from_items


STRONG_DISCOVERY_FAMILIES = {"official_company_page", "founder_company_pages", "movement_platform"}


def normalize_domain(value: str) -> str:
    raw = (value or "").lower().strip().replace("https://", "").replace("http://", "")
    raw = raw.split("/", 1)[0]
    return raw[4:] if raw.startswith("www.") else raw


def extract_maturity_targets(score_payload: dict, *, priority_domains: list[str] | None = None, limit: int | None = None) -> list[dict]:
    priority = [normalize_domain(domain) for domain in priority_domains or []]
    rows_by_domain: dict[str, dict] = {}
    for row in score_payload.get("accepted_leads", []):
        domain = normalize_domain(row.get("domain", ""))
        if not domain:
            continue
        target = rows_by_domain.setdefault(
            domain,
            {
                "company_name": row.get("display_name") or row.get("canonical_name") or row.get("name") or domain.split(".")[0],
                "domain": domain,
                "source_query_families": set(),
                "source_rows": [],
                "priority_reason": "",
            },
        )
        if row.get("query_family"):
            target["source_query_families"].add(row["query_family"])
        target["source_rows"].append(row)

    targets = []
    for domain, target in rows_by_domain.items():
        families = sorted(target["source_query_families"])
        target["source_query_families"] = families
        if domain in priority:
            target["priority_reason"] = "known_eval_target"
        elif any(family in STRONG_DISCOVERY_FAMILIES for family in families):
            target["priority_reason"] = "strong_discovery_family"
        else:
            target["priority_reason"] = "verified_domain"
        targets.append(target)

    priority_index = {domain: index for index, domain in enumerate(priority)}
    targets.sort(key=lambda row: (priority_index.get(row["domain"], 999), row["priority_reason"] != "strong_discovery_family", row["domain"]))
    return targets[:limit] if limit else targets
```

- [ ] **Step 2: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py -q
```

Expected: PASS for extraction tests.

---

## Task 3: Exact Maturity Query Generation

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py`
- Modify: `.claude/skills/vc-signals/scripts/discovery_maturity_evidence.py`

- [ ] **Step 1: Add failing tests**

Add:

```python
from discovery_maturity_evidence import build_maturity_queries


def test_build_maturity_queries_are_exact_company_domain_scoped():
    targets = [{"company_name": "Lyzr", "domain": "lyzr.ai", "source_query_families": ["movement_platform"]}]

    queries = build_maturity_queries(targets)

    assert queries
    assert all("Lyzr" in query["topic"] for query in queries)
    assert all("lyzr.ai" in query["topic"] for query in queries)
    assert {query["query_kind"] for query in queries} == {
        "funding_stage",
        "late_stage_or_valuation",
        "acquisition",
        "founder_stage_context",
    }


def test_build_maturity_queries_do_not_create_broad_market_search():
    queries = build_maturity_queries([{"company_name": "Lyzr", "domain": "lyzr.ai"}])

    forbidden = ["best startups", "companies to watch", "market map", "top startups"]
    assert all(not any(term in query["topic"].lower() for term in forbidden) for query in queries)
```

- [ ] **Step 2: Implement query generation**

Add:

```python
MATURITY_QUERY_KINDS = {
    "funding_stage": '"{company}" "{domain}" funding seed Series A Series B',
    "late_stage_or_valuation": '"{company}" "{domain}" Series C valuation $100M unicorn',
    "acquisition": '"{company}" "{domain}" acquired acquisition buys',
    "founder_stage_context": '"{company}" "{domain}" founders funding startup',
}


def build_maturity_queries(targets: list[dict], *, per_domain_cap: int = 4) -> list[dict]:
    queries = []
    seen = set()
    for target in targets:
        company = target.get("company_name", "").strip()
        domain = normalize_domain(target.get("domain", ""))
        if not company or not domain:
            continue
        for kind, template in list(MATURITY_QUERY_KINDS.items())[:per_domain_cap]:
            topic = template.format(company=company, domain=domain)
            key = topic.lower()
            if key in seen:
                continue
            seen.add(key)
            queries.append(
                {
                    "query_id": f"maturity:{domain}:{kind}",
                    "query_kind": kind,
                    "company_name": company,
                    "domain": domain,
                    "topic": topic,
                }
            )
    return queries
```

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py -q
```

Expected: PASS.

---

## Task 4: Run Maturity Provider Bakeoff

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py`
- Modify: `.claude/skills/vc-signals/scripts/discovery_maturity_evidence.py`

- [ ] **Step 1: Add failing provider tests**

Add:

```python
from discovery_maturity_evidence import run_maturity_evidence_bakeoff


def test_run_maturity_evidence_bakeoff_uses_same_provider_wrapper_shape():
    queries = [
        {"query_id": "maturity:lyzr.ai:funding_stage", "topic": '"Lyzr" "lyzr.ai" funding seed', "domain": "lyzr.ai", "company_name": "Lyzr", "query_kind": "funding_stage"}
    ]

    def runner(provider, query, **_kwargs):
        return {
            "provider": provider,
            "query_id": query["query_id"],
            "query": query["topic"],
            "items": [{"title": "Lyzr raises seed", "url": "https://www.lyzr.ai/", "snippet": "Lyzr raised a seed round."}],
            "skipped": False,
            "cache_status": "hit",
        }

    result = run_maturity_evidence_bakeoff(queries, providers=["brave"], provider_runner=runner)

    assert result["summary"]["queries_run"] == 1
    assert result["summary"]["cache_hits"] == 1
    assert result["provider_runs"][0]["items"][0]["title"] == "Lyzr raises seed"


def test_run_maturity_evidence_bakeoff_respects_query_cap():
    queries = [
        {"query_id": f"q{i}", "topic": f'"Lyzr" "lyzr.ai" funding {i}', "domain": "lyzr.ai", "company_name": "Lyzr", "query_kind": "funding_stage"}
        for i in range(3)
    ]

    result = run_maturity_evidence_bakeoff(queries, providers=["brave"], provider_runner=lambda *_args, **_kwargs: {"items": [], "skipped": False}, max_queries_per_provider=1)

    assert result["summary"]["queries_available"] == 3
    assert result["summary"]["runs"] == 1
    assert result["summary"]["partial_eval"] is True
```

- [ ] **Step 2: Implement provider bakeoff**

Add:

```python
def run_maturity_evidence_bakeoff(
    queries: list[dict],
    *,
    providers: list[str],
    provider_runner=run_provider_query,
    max_queries_per_provider: int = 80,
    max_results_per_query: int = 5,
    max_runtime_seconds: int | None = None,
    cache_dir: Path | str | None = None,
) -> dict:
    started = time.monotonic()
    provider_runs = []
    partial = False
    for provider in [item for item in providers if item]:
        for index, query in enumerate(queries):
            if index >= max_queries_per_provider:
                partial = True
                break
            if max_runtime_seconds is not None and time.monotonic() - started >= max_runtime_seconds:
                partial = True
                break
            run = provider_runner(provider, query, max_results=max_results_per_query, cache_dir=cache_dir)
            run.setdefault("provider", provider)
            run.setdefault("query_id", query.get("query_id", ""))
            run.setdefault("query_kind", query.get("query_kind", ""))
            run.setdefault("domain", query.get("domain", ""))
            run.setdefault("company_name", query.get("company_name", ""))
            run.setdefault("query", query.get("topic", ""))
            provider_runs.append(run)
    return {
        "provider_runs": provider_runs,
        "summary": {
            "queries_available": len(queries),
            "runs": len(provider_runs),
            "queries_run": sum(1 for run in provider_runs if not run.get("skipped")),
            "skipped_runs": sum(1 for run in provider_runs if run.get("skipped")),
            "cache_hits": sum(1 for run in provider_runs if run.get("cache_status") == "hit"),
            "partial_eval": partial,
            "duration_seconds": round(time.monotonic() - started, 3),
        },
    }
```

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py -q
```

Expected: PASS.

---

## Task 5: Maturity Classification From Evidence Runs

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py`
- Modify: `.claude/skills/vc-signals/scripts/discovery_maturity_evidence.py`

- [ ] **Step 1: Add failing classification tests**

Add:

```python
from discovery_maturity_evidence import classify_maturity_evidence


def test_classify_maturity_evidence_detects_seed_stage():
    targets = [{"company_name": "Lyzr", "domain": "lyzr.ai"}]
    runs = [
        {
            "domain": "lyzr.ai",
            "company_name": "Lyzr",
            "items": [{"title": "Lyzr raises seed", "url": "https://www.lyzr.ai/", "snippet": "Lyzr raised a seed round."}],
            "skipped": False,
        }
    ]

    result = classify_maturity_evidence(targets, runs)

    assert result["domains"]["lyzr.ai"]["maturity_status"] == "seed_to_series_b"
    assert result["domains"]["lyzr.ai"]["lead_route"] == "sourcing_candidate"


def test_classify_maturity_evidence_detects_category_anchor():
    targets = [{"company_name": "Wiz", "domain": "wiz.io"}]
    runs = [
        {
            "domain": "wiz.io",
            "company_name": "Wiz",
            "items": [{"title": "Wiz raises $1B", "url": "https://www.wiz.io/", "snippet": "Wiz raised a $1B round and is a category leader."}],
            "skipped": False,
        }
    ]

    result = classify_maturity_evidence(targets, runs)

    assert result["domains"]["wiz.io"]["maturity_status"] == "likely_too_late"
    assert result["domains"]["wiz.io"]["lead_route"] == "category_context"


def test_classify_maturity_evidence_keeps_unknown_when_no_matching_evidence():
    targets = [{"company_name": "Lyzr", "domain": "lyzr.ai"}]
    runs = [
        {
            "domain": "lyzr.ai",
            "company_name": "Lyzr",
            "items": [{"title": "Unrelated company raises seed", "url": "https://example.com/", "snippet": "Example raised seed."}],
            "skipped": False,
        }
    ]

    result = classify_maturity_evidence(targets, runs)

    assert result["domains"]["lyzr.ai"]["maturity_status"] == "unknown"
    assert result["domains"]["lyzr.ai"]["maturity_evaluation_status"] == "evaluated_no_maturity_evidence"
```

- [ ] **Step 2: Implement classifier**

Add:

```python
def _run_items(run: dict) -> list[dict]:
    if "items" in run:
        return list(run.get("items") or [])
    return list((run.get("provider_result") or {}).get("items") or [])


def _item_matches_target(item: dict, target: dict) -> bool:
    domain = normalize_domain(target.get("domain", ""))
    company_key = "".join(ch.lower() for ch in (target.get("company_name") or "") if ch.isalnum())
    text_key = "".join(ch.lower() for ch in f"{item.get('title', '')} {item.get('snippet', '')} {item.get('description', '')} {item.get('url', '')}" if ch.isalnum())
    item_domain = normalize_domain(item.get("url", ""))
    return bool((domain and domain in text_key) or (company_key and len(company_key) >= 3 and company_key in text_key) or item_domain == domain)


def classify_maturity_evidence(targets: list[dict], provider_runs: list[dict]) -> dict:
    by_domain = {normalize_domain(target.get("domain", "")): target for target in targets}
    items_by_domain = {domain: [] for domain in by_domain}
    for run in provider_runs:
        domain = normalize_domain(run.get("domain", ""))
        target = by_domain.get(domain)
        if not target or run.get("skipped"):
            continue
        for item in _run_items(run):
            if _item_matches_target(item, target):
                items_by_domain[domain].append(item)
    rows = {}
    for domain, target in by_domain.items():
        items = items_by_domain.get(domain, [])
        maturity = _classify_maturity_from_items(items, company_name=target.get("company_name", ""), domain=domain)
        basis = list(maturity.get("maturity_basis") or [])
        rows[domain] = {
            "company_name": target.get("company_name", ""),
            "domain": domain,
            "maturity_evaluation_status": "evaluated_with_evidence" if maturity.get("maturity_status") != "unknown" and basis else "evaluated_no_maturity_evidence",
            **maturity,
        }
    return {"domains": rows}
```

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py -q
```

Expected: PASS.

---

## Task 6: Apply Maturity Evidence To Discovery Yield Score

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
- Modify: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`

- [ ] **Step 1: Add failing tests**

Add to `test_discovery_yield_eval.py`:

```python
def test_external_maturity_evidence_updates_score_metrics():
    target = _target(expected_route="sourcing_candidate")
    provider_runs = [
        {
            "provider": "brave",
            "query": "AI agent production platform official",
            "query_id": "q1",
            "query_family": "official_company_page",
            "movement": target.expected_movement,
            "market_sector": target.market_sector,
            "items": [
                {
                    "title": "Lyzr - AI agent platform",
                    "url": "https://www.lyzr.ai/",
                    "snippet": "Lyzr helps teams launch production AI agents.",
                }
            ],
            "skipped": False,
        }
    ]
    maturity_evidence = {
        "domains": {
            "lyzr.ai": {
                "maturity_status": "seed_to_series_b",
                "maturity_evaluation_status": "evaluated_with_evidence",
                "lead_route": "sourcing_candidate",
                "likely_too_late": False,
                "category_anchor": False,
                "maturity_basis": ["seed_or_pre_seed"],
                "maturity_evidence_urls": ["https://www.lyzr.ai/"],
            }
        }
    }

    result = score_provider_items_against_targets(provider_runs, [target], maturity_evidence=maturity_evidence)

    assert result["metrics"]["credible_early_stage_leads"] == 1
    assert result["target_results"][0]["actual_maturity"] == "seed_to_series_b"
```

- [ ] **Step 2: Update function signature**

Change:

```python
def score_provider_items_against_targets(provider_runs, targets):
```

to:

```python
def score_provider_items_against_targets(provider_runs, targets, *, maturity_evidence: dict | None = None):
```

- [ ] **Step 3: Apply external maturity evidence after domain rollup**

Add:

```python
def _apply_external_maturity_evidence(accepted: list[dict], maturity_evidence: dict | None) -> list[dict]:
    if not maturity_evidence:
        return accepted
    domains = maturity_evidence.get("domains", {})
    out = []
    for row in accepted:
        domain = _normalize_domain(row.get("domain", ""))
        evidence = domains.get(domain)
        if not evidence:
            out.append(row)
            continue
        updated = dict(row)
        for key in (
            "maturity_status",
            "maturity_evaluation_status",
            "maturity_basis",
            "maturity_evidence_urls",
            "category_anchor",
            "lead_route",
            "likely_too_late",
            "consensus_risk_reason",
        ):
            if key in evidence:
                updated[key] = evidence[key]
        out.append(updated)
    return out
```

Then after `_apply_domain_maturity_rollups`:

```python
accepted = _apply_external_maturity_evidence(accepted, maturity_evidence)
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py -q
```

Expected: PASS.

---

## Task 7: Artifact Writer And CLI

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_maturity_evidence.py`
- Modify: `.claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py`

- [ ] **Step 1: Add failing artifact/CLI tests**

Add:

```python
from discovery_maturity_evidence import write_maturity_evidence_artifact


def test_write_maturity_evidence_artifact(tmp_path):
    payload = {
        "targets": [{"company_name": "Lyzr", "domain": "lyzr.ai"}],
        "queries": [{"query_id": "q1"}],
        "bakeoff": {"summary": {"queries_run": 1}},
        "classification": {"domains": {"lyzr.ai": {"maturity_status": "seed_to_series_b"}}},
    }

    path = write_maturity_evidence_artifact(payload, tmp_path)

    assert path.name == "maturity-evidence-bakeoff.json"
    assert path.exists()
```

- [ ] **Step 2: Implement writer**

Add:

```python
def write_maturity_evidence_artifact(payload: dict, output_dir: Path | str) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    out = path / "maturity-evidence-bakeoff.json"
    out.write_text(json.dumps(payload, indent=2))
    return out
```

- [ ] **Step 3: Implement CLI**

Add:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run maturity evidence retrieval for Phase 5 verified domains.")
    parser.add_argument("--lead-discovery-eval", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--providers", default="brave")
    parser.add_argument("--max-targets", type=int, default=20)
    parser.add_argument("--max-queries-per-provider", type=int, default=80)
    parser.add_argument("--max-results-per-query", type=int, default=5)
    parser.add_argument("--max-runtime-seconds", type=int, default=300)
    args = parser.parse_args(argv)

    load_provider_env_files()
    lead_eval = json.loads(Path(args.lead_discovery_eval).read_text())
    score_payload = lead_eval.get("score", {})
    priority = [row.get("target_domain", "") for row in score_payload.get("target_results", []) if row.get("found")]
    targets = extract_maturity_targets(score_payload, priority_domains=priority, limit=args.max_targets)
    queries = build_maturity_queries(targets)
    bakeoff = run_maturity_evidence_bakeoff(
        queries,
        providers=[provider.strip() for provider in args.providers.split(",") if provider.strip()],
        max_queries_per_provider=args.max_queries_per_provider,
        max_results_per_query=args.max_results_per_query,
        max_runtime_seconds=args.max_runtime_seconds,
        cache_dir=args.cache_dir or None,
    )
    classification = classify_maturity_evidence(targets, bakeoff["provider_runs"])
    write_maturity_evidence_artifact(
        {"targets": targets, "queries": queries, "bakeoff": bakeoff, "classification": classification},
        args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI smoke against empty provider list**

```bash
python3 .claude/skills/vc-signals/scripts/discovery_maturity_evidence.py \
  --lead-discovery-eval docs/radar-runs/current-phase5-discovery-yield-smoke-v2/lead-discovery-eval.json \
  --output-dir /tmp/vc-signals-phase52-empty \
  --providers "" \
  --max-targets 2
```

Expected: exit `0`, artifact written, no provider calls.

---

## Task 8: Re-score Existing Brave Smoke With Maturity Evidence

**Files:**
- Generated only under `docs/radar-runs/current-phase5-2-maturity-evidence-check/`.

- [ ] **Step 1: Run maturity evidence retrieval from existing Phase 5 smoke**

Use existing provider/cache style. This can make live Brave calls only for exact maturity queries unless cache already has them:

```bash
python3 .claude/skills/vc-signals/scripts/discovery_maturity_evidence.py \
  --lead-discovery-eval docs/radar-runs/current-phase5-discovery-yield-smoke-v2/lead-discovery-eval.json \
  --output-dir docs/radar-runs/current-phase5-2-maturity-evidence-check \
  --cache-dir docs/radar-runs/current-phase5-2-maturity-evidence-check/provider-cache \
  --providers brave \
  --max-targets 20 \
  --max-queries-per-provider 80 \
  --max-results-per-query 5 \
  --max-runtime-seconds 300
```

- [ ] **Step 2: Re-score discovery yield using maturity evidence**

Add a `--maturity-evidence` argument to `discovery_yield_eval.py`:

```bash
python3 .claude/skills/vc-signals/scripts/discovery_yield_eval.py \
  --output-dir docs/radar-runs/current-phase5-discovery-yield-smoke-v2 \
  --cache-dir docs/radar-runs/current-phase5-discovery-yield-smoke-v2/provider-cache \
  --providers brave \
  --eval-mode smoke \
  --max-queries-per-provider 40 \
  --max-results-per-query 5 \
  --max-runtime-seconds 300 \
  --maturity-evidence docs/radar-runs/current-phase5-2-maturity-evidence-check/maturity-evidence-bakeoff.json
```

Expected:
- Existing discovery provider cache should be reused.
- Maturity evidence updates score only for matching domains.
- Generated artifacts remain uncommitted.

- [ ] **Step 3: Report before/after**

Report:
- verified domains found
- maturity-confirmed early-stage
- maturity unknown research-deeper
- category anchors / likely too late
- over-promoted controls
- net-new credible early-stage
- net-new research-worthy verified domains

---

## Task 9: Full Verification And Commit

**Files to commit:**
- `.claude/skills/vc-signals/scripts/discovery_maturity_evidence.py`
- `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
- `.claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py`
- `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`
- `docs/superpowers/plans/2026-05-10-phase-5-2-maturity-evidence-retrieval.md`

- [ ] **Step 1: Run focused tests**

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py \
  .claude/skills/vc-signals/tests/test_discovery_yield_eval.py \
  .claude/skills/vc-signals/tests/test_discovery_search_providers.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full skill suite**

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: PASS, allowing existing LibreSSL warning.

- [ ] **Step 3: Confirm weekly preview unchanged**

```bash
git diff --name-only -- '*weekly-preview.md' 'docs/**/weekly-preview.md' '.claude/**/weekly-preview.md'
```

Expected: no output.

- [ ] **Step 4: Confirm generated artifacts uncommitted**

```bash
git status --short docs/radar-runs/current-phase5-2-maturity-evidence-check docs/radar-runs/current-phase5-discovery-yield-smoke-v2
```

Expected: generated artifact directories only, not staged.

- [ ] **Step 5: Commit code/tests/plan only**

```bash
git add \
  .claude/skills/vc-signals/scripts/discovery_maturity_evidence.py \
  .claude/skills/vc-signals/scripts/discovery_yield_eval.py \
  .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py \
  .claude/skills/vc-signals/tests/test_discovery_yield_eval.py \
  docs/superpowers/plans/2026-05-10-phase-5-2-maturity-evidence-retrieval.md
git commit -m "Add maturity evidence retrieval bakeoff"
```

---

## Definition Of Done

- `maturity-evidence-bakeoff.json` exists for the Phase 5.2 run.
- Maturity queries are exact company/domain scoped.
- Maturity evidence is cached.
- Maturity evidence is applied only to matching company/domain rows.
- Braintrust/Wiz/Orca/Darktrace-style mature rows do not count as early-stage when evidence supports maturity.
- Lyzr/Entro/Straiker remain research-worthy or become early-stage only when evidence supports it.
- `maturity_unknown_research_deeper` decreases, or the artifact clearly shows no maturity evidence was discoverable under exact scoped queries.
- Existing Phase 5 command shape remains compatible.
- No weekly production behavior changes.
- `weekly-preview.md` remains unchanged.
- Generated artifacts/provider cache are not committed.

---

## Self-Review

- Spec coverage: Covers verified-domain input, exact maturity queries, cache, artifact, scoring update, and no weekly production changes.
- Guardrails: No broad source expansion, no forbidden sources, no Attio writeback, no Slack.
- Product stance: Improves quality measurement before adding You.com or graduating query families.
