# Phase 5 Discovery Yield Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine whether weekly movement queries can reliably surface Lyzr-like early-stage companies without targeted injection, and identify which query families and grounded providers produce the best credible early-stage lead yield.

**Architecture:** Add an offline-first discovery evaluation layer around the existing controlled company discovery pipeline. The bakeoff generates movement-only query families from an eval set, runs the same query set across configured grounded providers, feeds all results through existing verification/maturity/owner-readiness gates, and writes scored artifacts without changing `weekly-preview.md` or loosening production gates.

**Tech Stack:** Python dataclasses, JSON fixtures, existing `radar_company_discovery.py` verification functions, provider-specific grounded web clients where configured, local JSON caches, pytest.

---

## Scope

Build Phase 5 as an evaluation and recommendation system first. Do not route bakeoff winners into the normal weekly artifact until the metrics show which provider/query families produce credible early-stage companies.

Allowed:
- Grounded/company web provider bakeoff.
- Brave.
- You.com if configured.
- Optional Perplexity Search if configured, explicitly not Sonar/deep-research.
- Existing identity, maturity, owner-readiness, Attio, and source-authority gates.
- Local cache files and generated eval artifacts.
- Movement aliases and synonyms from the eval fixture, capped per target.

Not allowed:
- X.
- LinkedIn scraping.
- Product Hunt.
- Package registries.
- Slack delivery.
- Attio writeback.
- Domain guessing.
- Assign-owner gate loosening.
- Provider result bypassing verification.
- Generated Perplexity answer text as evidence. Only raw result URLs/titles/snippets can be normalized as evidence.
- `weekly-preview.md` behavior changes.

North-star metric:

```text
credible early-stage leads per 100 queries
```

Credible early-stage lead means:
- source-backed official company domain,
- verified company or launch-style identity,
- maturity route is `sourcing_candidate` or `research_deeper`,
- not `category_context`, `monitor_only`, `likely_too_late`, `acquired`, or OSS-only,
- survives existing source authority and identity/maturity gates.

---

## Files

Create:
- `.claude/skills/vc-signals/config/lead_discovery_eval_set.json`
  - Versioned seed targets for discovery-yield evaluation.
- `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
  - Eval target loading, query generation, result matching, metric aggregation, and artifact writing.
- `.claude/skills/vc-signals/scripts/discovery_search_providers.py`
  - Provider-neutral search wrapper for Brave, You.com, and optional Perplexity Search; records provider capability, cost, latency, and cache metadata.
- `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`
  - Eval set, query family, metrics, and guardrail tests.
- `.claude/skills/vc-signals/tests/test_discovery_search_providers.py`
  - Provider normalization, cache, skip, cost/latency, and same-query-set tests.

Modify:
- `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
  - Only if a small reusable query-family helper needs to be extracted. Do not change existing weekly gate behavior.
- `.claude/skills/vc-signals/scripts/radar_models.py`
  - Only if shared dataclasses are truly needed. Prefer local eval dataclasses in `discovery_yield_eval.py` first.
- `.claude/skills/vc-signals/tests/test_radar_company_discovery.py`
  - Add regression tests only if shared query helpers are extracted.

Generated, do not commit real run outputs:
- `docs/radar-runs/current-phase5-discovery-yield-bakeoff/lead-discovery-eval.json`
- `docs/radar-runs/current-phase5-discovery-yield-bakeoff/query-family-bakeoff.json`
- `docs/radar-runs/current-phase5-discovery-yield-bakeoff/provider-bakeoff.json`
- `docs/radar-runs/current-phase5-discovery-yield-bakeoff/discovery-yield-summary.md`
- `docs/radar-runs/current-phase5-discovery-yield-bakeoff/provider-cache/`

---

## Initial Eval Set

The eval set is a seed fixture, not a source of truth. Every target includes a domain, movement aliases, route expectation, and verification timestamp so tests can measure recall, but the bakeoff must still verify the company from provider evidence.

Eval target schema:
- `name`: expected canonical company name.
- `aliases`: company aliases for matching provider results, never for movement-only query generation.
- `domain`: expected official domain for recall matching.
- `expected_movement`: primary movement label.
- `movement_aliases`: query synonyms for the movement, capped during generation; must not include target company names or domains.
- `market_sector`: Marathon sector bucket.
- `maturity_expectation`: expected maturity/routing clue for eval scoring.
- `expected_route`: expected route after verification.
- `last_verified_at`: date the seed target was sanity-checked.
- `verification_notes`: short note about why this target is in the eval set.

Create `.claude/skills/vc-signals/config/lead_discovery_eval_set.json`:

```json
{
  "schema_version": 1,
  "notes": [
    "Movement-only discovery queries must not include target company names or target domains.",
    "Exact-name controls may be run separately for diagnostics but do not count toward the north-star metric."
  ],
  "targets": [
    {
      "name": "Lyzr",
      "aliases": ["Lyzr AI"],
      "domain": "lyzr.ai",
      "expected_movement": "Agent reliability and evals",
      "movement_aliases": ["AI agent reliability", "agent evals", "AI agent production", "agent observability"],
      "market_sector": "AI Infra",
      "maturity_expectation": "seed_to_series_b",
      "expected_route": "sourcing_candidate",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; targeted regression already proves owner-ready path when evidence is present.",
      "notes": "Owner-ready path is already proven when evidence is present; Phase 5 tests whether movement queries surface it without injecting Lyzr."
    },
    {
      "name": "Copperhelm",
      "aliases": [],
      "domain": "copperhelm.com",
      "expected_movement": "AI cloud security",
      "movement_aliases": ["agentic cloud security", "AI security posture", "cloud security automation"],
      "market_sector": "Cybersecurity",
      "maturity_expectation": "early_or_unknown",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful missing-evidence target.",
      "notes": "Useful as a missing-evidence target if founder/customer/stage proof is not surfaced."
    },
    {
      "name": "Entro",
      "aliases": ["Entro Security"],
      "domain": "entro.security",
      "expected_movement": "Non-human identity security",
      "movement_aliases": ["NHI security", "machine identity security", "non human identity", "secrets sprawl", "workload identity security"],
      "market_sector": "Cybersecurity",
      "maturity_expectation": "seed_to_series_b",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful for non-human identity discovery recall.",
      "notes": "Should not become owner-ready unless founder/team, maturity, and Attio gates pass."
    },
    {
      "name": "Straiker",
      "aliases": [],
      "domain": "straiker.ai",
      "expected_movement": "AI agent security",
      "movement_aliases": ["agent security", "runtime security for AI agents", "AI agent protection", "agent threat detection"],
      "market_sector": "Cybersecurity",
      "maturity_expectation": "early_or_unknown",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; good article-to-company extraction target.",
      "notes": "Launch/article-derived company candidate; official-domain verification must be required."
    },
    {
      "name": "Noma Security",
      "aliases": ["Noma"],
      "domain": "noma.security",
      "expected_movement": "AI agent security",
      "movement_aliases": ["AI security posture", "AI agent security", "AI application security", "AI risk management"],
      "market_sector": "Cybersecurity",
      "maturity_expectation": "seed_to_series_b",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful AI security recall target.",
      "notes": "Should be early-stage relevant but not owner-ready without owner evidence and Attio gates."
    },
    {
      "name": "Aim Security",
      "aliases": [],
      "domain": "aim.security",
      "expected_movement": "AI application security",
      "movement_aliases": ["AI security", "AI application security", "LLM security", "GenAI security"],
      "market_sector": "Cybersecurity",
      "maturity_expectation": "acquired_or_late",
      "expected_route": "monitor_only",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official/source pages indicate acquisition context; useful negative control.",
      "notes": "Negative/control target: if surfaced with acquisition evidence, it should not become owner-ready."
    },
    {
      "name": "Clutch Security",
      "aliases": [],
      "domain": "clutch.security",
      "expected_movement": "Non-human identity security",
      "movement_aliases": ["NHI security", "machine identity security", "workload identity security", "service account security"],
      "market_sector": "Cybersecurity",
      "maturity_expectation": "seed_to_series_b",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful non-human identity recall target.",
      "notes": "Should remain research-deeper unless owner-readiness evidence is found."
    },
    {
      "name": "LangWatch",
      "aliases": [],
      "domain": "langwatch.ai",
      "expected_movement": "Agent observability and evals",
      "movement_aliases": ["AI agent observability", "LLM monitoring", "agent evals", "LLM tracing"],
      "market_sector": "AI Infra",
      "maturity_expectation": "early_or_unknown",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful observability/evals recall target.",
      "notes": "Good target for eval/observability movement queries."
    },
    {
      "name": "Parea AI",
      "aliases": ["Parea"],
      "domain": "parea.ai",
      "expected_movement": "LLM evals and observability",
      "movement_aliases": ["AI evals", "LLM evaluation", "LLM observability", "AI reliability"],
      "market_sector": "AI Infra",
      "maturity_expectation": "early_or_unknown",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful AI evals recall target.",
      "notes": "Good target for AI eval query families."
    },
    {
      "name": "Helicone",
      "aliases": [],
      "domain": "helicone.ai",
      "expected_movement": "LLM observability",
      "movement_aliases": ["LLM observability", "LLM monitoring", "AI gateway", "LLM tracing"],
      "market_sector": "AI Infra",
      "maturity_expectation": "early_or_unknown",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful LLM observability recall target.",
      "notes": "Good target for AI gateway and LLM observability query families."
    },
    {
      "name": "Braintrust",
      "aliases": [],
      "domain": "braintrust.dev",
      "expected_movement": "LLM evals and observability",
      "movement_aliases": ["LLM evals", "AI evals", "agent observability", "AI reliability"],
      "market_sector": "AI Infra",
      "maturity_expectation": "likely_too_late_or_consensus",
      "expected_route": "category_context",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful category-anchor control.",
      "notes": "Negative/control target for mature category-anchor routing."
    },
    {
      "name": "Tessl",
      "aliases": [],
      "domain": "tessl.io",
      "expected_movement": "AI-native software development",
      "movement_aliases": ["AI software development", "AI-native development", "AI code generation", "software agents"],
      "market_sector": "Devtools",
      "maturity_expectation": "likely_too_late_or_consensus",
      "expected_route": "category_context",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; useful high-funding category-anchor control.",
      "notes": "Negative/control target for high-funding category-anchor routing."
    },
    {
      "name": "HappyRobot",
      "aliases": ["Happy Robot"],
      "domain": "happyrobot.ai",
      "expected_movement": "Vertical AI logistics operations",
      "movement_aliases": ["AI logistics agents", "freight automation", "AI voice agents logistics", "supply chain AI agents"],
      "market_sector": "Vertical AI",
      "maturity_expectation": "early_or_unknown",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; vertical AI recall target.",
      "notes": "Adds vertical AI representation; should not become owner-ready without founder/customer/stage and Attio gates."
    },
    {
      "name": "Rogo",
      "aliases": ["Rogo AI"],
      "domain": "rogo.ai",
      "expected_movement": "Vertical AI financial services",
      "movement_aliases": ["AI financial analyst", "investment banking AI", "finance AI agents", "private equity AI workflow"],
      "market_sector": "Vertical AI",
      "maturity_expectation": "early_or_unknown",
      "expected_route": "research_deeper",
      "last_verified_at": "2026-05-10",
      "verification_notes": "Official domain sanity-checked; vertical AI recall target.",
      "notes": "Adds vertical AI representation; should route by evidence and maturity rather than target expectation."
    }
  ]
}
```

The exact list can be amended before execution if a target is no longer appropriate. Do not make runtime results depend on this fixture as truth; use it only for recall and expected-routing evaluation.

---

## Query Families

The bakeoff must test these families for each movement in the eval set:

1. `official_company_page`
   - Template: `"{movement}" startup company platform official {market_sector}`
   - Goal: official company pages.

2. `yc_company_pages`
   - Template: `site:ycombinator.com/companies "{movement}"`
   - Goal: clean company/founder/stage-like pages.

3. `seed_funding`
   - Template: `"{movement}" startup raises seed OR "Series A" founder`
   - Goal: launch/funding evidence, not publisher domain as identity.

4. `launch_stealth`
   - Template: `"{movement}" "emerged from stealth" OR launches startup founder`
   - Goal: newly launched companies.

5. `founder_company_pages`
   - Template: `"{movement}" founder company official website`
   - Goal: official pages or source-backed founder/company pages.

6. `movement_startup`
   - Template: `"{movement}" startup`
   - Goal: baseline recall.

7. `movement_platform`
   - Template: `"{movement}" platform`
   - Goal: baseline company/category pages.

Query generation rules:
- Movement-only eval queries must not contain target company names.
- Movement-only eval queries must not contain target domains.
- Query generation uses each target's `expected_movement` plus up to 3 `movement_aliases`.
- Alias queries count toward provider/query budgets and must be labeled with `alias_of`.
- Query generation must dedupe by normalized `topic` after templating, not only by movement term.
- Exact-name controls may be generated only under `control_exact_name=true`, stored separately, and excluded from north-star metrics.
- Every query must include `query_family`, `movement`, `market_sector`, `provider`, and `query_id`.

---

## Metrics

Write these into `lead-discovery-eval.json`, `query-family-bakeoff.json`, and `provider-bakeoff.json`:

```json
{
  "queries_run": 0,
  "provider": "brave",
  "query_family": "seed_funding",
  "verified_domains_found": 0,
  "early_stage_rows_found": 0,
  "owner_ready_rows_found": 0,
  "research_deeper_rows_found": 0,
  "category_anchors_found": 0,
  "monitor_only_rows_found": 0,
  "false_positives": 0,
  "publisher_content_junk_rate": 0.0,
  "credible_early_stage_leads_per_100_queries": 0.0,
  "known_target_recall": 0.0,
  "known_target_precision": 0.0,
  "net_new_verified_domains": 0,
  "net_new_credible_early_stage_leads": 0,
  "net_new_false_positive_rate": 0.0,
  "cost_usd": 0.0,
  "latency_ms_p50": 0,
  "latency_ms_p95": 0,
  "cache_hit_rate": 0.0
}
```

Definitions:
- `verified_domains_found`: accepted leads with source-backed official domain.
- `early_stage_rows_found`: accepted leads with `lead_route in {"sourcing_candidate", "research_deeper"}` and not too-late/category/monitor.
- `owner_ready_rows_found`: rows that become `Assign owner` only after the existing gates.
- `research_deeper_rows_found`: rows accepted or target-matched but missing owner evidence.
- `category_anchors_found`: accepted leads routed to `category_context`.
- `false_positives`: rows accepted as official company identity despite source authority mismatch, wrong domain, content/publisher domain, or expected route violation.
- `publisher_content_junk_rate`: share of raw results classified as publisher/content/listicle/directory/social/platform/non-company.
- `known_target_recall`: percent of eval targets surfaced by movement-only queries.
- `known_target_precision`: share of target-matched leads that map to the correct domain and do not over-promote relative to expected route. Route aggressiveness order is `monitor_only < category_context < research_deeper < sourcing_candidate < assign_owner`; if actual route is more aggressive than expected, count it as a routing false positive.
- `net_new_verified_domains`: accepted verified domains not present in the eval target set.
- `net_new_credible_early_stage_leads`: accepted non-target leads routed to `sourcing_candidate` or `research_deeper`, excluding category anchors, monitor-only rows, late/acquired/incumbent rows, and OSS-only rows.
- `net_new_false_positive_rate`: false positives among non-target accepted leads.
- `credible_early_stage_leads_per_100_queries`: `early_stage_rows_found / queries_run * 100`.

Metric guardrail:
- `evaluation_incomplete` rows cannot inflate `credible_early_stage_leads_per_100_queries` unless source-authority and verified-domain gates passed.
- `evaluation_incomplete` rows can never count toward `owner_ready_rows_found`.

---

## Task 1: Lead Discovery Eval Set Loader

**Files:**
- Create: `.claude/skills/vc-signals/config/lead_discovery_eval_set.json`
- Create: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
- Test: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`

- [ ] **Step 1: Write failing tests for eval target loading**

Add:

```python
def test_load_eval_set_validates_required_fields():
    from discovery_yield_eval import load_eval_set

    targets = load_eval_set(".claude/skills/vc-signals/config/lead_discovery_eval_set.json")

    assert len(targets) >= 8
    assert {target.name for target in targets} >= {"Lyzr", "Copperhelm", "Entro"}
    for target in targets:
        assert target.name
        assert target.domain
        assert target.expected_movement
        assert target.movement_aliases
        assert target.market_sector
        assert target.maturity_expectation
        assert target.last_verified_at
        assert target.verification_notes
        for alias in target.movement_aliases:
            assert target.name.lower() not in alias.lower()
            assert target.domain.split(".")[0].lower() not in alias.lower()
            assert all(company_alias.lower() not in alias.lower() for company_alias in target.aliases)
        assert target.expected_route in {
            "sourcing_candidate",
            "research_deeper",
            "category_context",
            "monitor_only",
        }
```

Add:

```python
def test_eval_set_rejects_missing_domain(tmp_path):
    from discovery_yield_eval import load_eval_set

    path = tmp_path / "bad-eval.json"
    path.write_text('{"targets": [{"name": "NoDomain"}]}')

    try:
        load_eval_set(path)
    except ValueError as exc:
        assert "domain" in str(exc)
    else:
        raise AssertionError("Expected missing domain to fail validation")
```

Add:

```python
def test_eval_set_rejects_alias_target_leakage(tmp_path):
    from discovery_yield_eval import load_eval_set

    path = tmp_path / "bad-eval.json"
    path.write_text(
        '''
        {
          "targets": [
            {
              "name": "Lyzr",
              "aliases": ["Lyzr AI"],
              "domain": "lyzr.ai",
              "expected_movement": "Agent reliability and evals",
              "movement_aliases": ["Lyzr agent evals"],
              "market_sector": "AI Infra",
              "maturity_expectation": "seed_to_series_b",
              "expected_route": "sourcing_candidate",
              "last_verified_at": "2026-05-10",
              "verification_notes": "test"
            }
          ]
        }
        '''
    )

    try:
        load_eval_set(path)
    except ValueError as exc:
        assert "movement_aliases" in str(exc)
        assert "target leakage" in str(exc)
    else:
        raise AssertionError("Expected alias leakage to fail validation")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError: No module named 'discovery_yield_eval'
```

- [ ] **Step 3: Implement eval target loader**

Create `discovery_yield_eval.py` with:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ALLOWED_EXPECTED_ROUTES = {
    "sourcing_candidate",
    "research_deeper",
    "category_context",
    "monitor_only",
}


@dataclass(frozen=True)
class LeadDiscoveryEvalTarget:
    name: str
    aliases: list[str]
    domain: str
    expected_movement: str
    movement_aliases: list[str]
    market_sector: str
    maturity_expectation: str
    expected_route: str
    last_verified_at: str
    verification_notes: str
    notes: str = ""


def _require_text(payload: dict, field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ValueError(f"Eval target missing required field: {field}")
    return value


def load_eval_set(path: str | Path) -> list[LeadDiscoveryEvalTarget]:
    payload = json.loads(Path(path).read_text())
    targets = []
    for item in payload.get("targets", []):
        route = _require_text(item, "expected_route")
        if route not in ALLOWED_EXPECTED_ROUTES:
            raise ValueError(f"Unsupported expected_route: {route}")
        targets.append(
            LeadDiscoveryEvalTarget(
                name=_require_text(item, "name"),
                aliases=list(item.get("aliases") or []),
                domain=_require_text(item, "domain"),
                expected_movement=_require_text(item, "expected_movement"),
                movement_aliases=list(item.get("movement_aliases") or []),
                market_sector=_require_text(item, "market_sector"),
                maturity_expectation=_require_text(item, "maturity_expectation"),
                expected_route=route,
                last_verified_at=_require_text(item, "last_verified_at"),
                verification_notes=_require_text(item, "verification_notes"),
                notes=str(item.get("notes") or ""),
            )
        )
        if not targets[-1].movement_aliases:
            raise ValueError("Eval target missing required field: movement_aliases")
        domain_stem = targets[-1].domain.split(".")[0].lower()
        forbidden_terms = [targets[-1].name.lower(), domain_stem] + [alias.lower() for alias in targets[-1].aliases]
        for movement_alias in targets[-1].movement_aliases:
            alias_lower = movement_alias.lower()
            if any(term and term in alias_lower for term in forbidden_terms):
                raise ValueError("movement_aliases contain target leakage")
    if not targets:
        raise ValueError("Eval set must include at least one target")
    return targets
```

- [ ] **Step 4: Add the eval set fixture**

Create `.claude/skills/vc-signals/config/lead_discovery_eval_set.json` using the Initial Eval Set above.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Expected:

```text
2 passed
```

Commit:

```bash
git add .claude/skills/vc-signals/config/lead_discovery_eval_set.json .claude/skills/vc-signals/scripts/discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_yield_eval.py
git commit -m "Add discovery yield eval target set"
```

---

## Task 2: Movement-Only Query Family Generation

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
- Test: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`

- [ ] **Step 1: Write failing tests for query families**

Add:

```python
def test_build_movement_only_queries_covers_required_families():
    from discovery_yield_eval import LeadDiscoveryEvalTarget, build_movement_only_queries

    target = LeadDiscoveryEvalTarget(
        name="Lyzr",
        aliases=["Lyzr AI"],
        domain="lyzr.ai",
        expected_movement="Agent reliability and evals",
        movement_aliases=["agent evals", "AI agent production"],
        market_sector="AI Infra",
        maturity_expectation="seed_to_series_b",
        expected_route="sourcing_candidate",
        last_verified_at="2026-05-10",
        verification_notes="test target",
    )

    queries = build_movement_only_queries([target])

    assert {query["query_family"] for query in queries} == {
        "official_company_page",
        "yc_company_pages",
        "seed_funding",
        "launch_stealth",
        "founder_company_pages",
        "movement_startup",
        "movement_platform",
    }
    assert all(query["movement"] == "Agent reliability and evals" for query in queries)
    assert all(query["market_sector"] == "AI Infra" for query in queries)
    assert any(query.get("alias_of") == "Agent reliability and evals" for query in queries)
```

Add:

```python
def test_movement_only_queries_do_not_inject_target_names_or_domains():
    from discovery_yield_eval import LeadDiscoveryEvalTarget, build_movement_only_queries

    target = LeadDiscoveryEvalTarget(
        name="Lyzr",
        aliases=["Lyzr AI"],
        domain="lyzr.ai",
        expected_movement="Agent reliability and evals",
        movement_aliases=["agent evals", "AI agent production"],
        market_sector="AI Infra",
        maturity_expectation="seed_to_series_b",
        expected_route="sourcing_candidate",
        last_verified_at="2026-05-10",
        verification_notes="test target",
    )

    query_text = " ".join(query["topic"].lower() for query in build_movement_only_queries([target]))

    assert "lyzr" not in query_text
    assert "lyzr.ai" not in query_text
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py::test_build_movement_only_queries_covers_required_families .claude/skills/vc-signals/tests/test_discovery_yield_eval.py::test_movement_only_queries_do_not_inject_target_names_or_domains -q
```

Expected:

```text
FAILED ... cannot import name 'build_movement_only_queries'
```

- [ ] **Step 3: Implement query family generation**

Add to `discovery_yield_eval.py`:

```python
QUERY_FAMILY_TEMPLATES = {
    "official_company_page": '"{movement}" startup company platform official {market_sector}',
    "yc_company_pages": 'site:ycombinator.com/companies "{movement}"',
    "seed_funding": '"{movement}" startup raises seed OR "Series A" founder',
    "launch_stealth": '"{movement}" "emerged from stealth" OR launches startup founder',
    "founder_company_pages": '"{movement}" founder company official website',
    "movement_startup": '"{movement}" startup',
    "movement_platform": '"{movement}" platform',
}


def _query_id(movement: str, family: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in movement).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{slug}-{family}"


def _normalized_topic(topic: str) -> str:
    return " ".join((topic or "").lower().split())


def _movement_terms(target: LeadDiscoveryEvalTarget, max_aliases_per_target: int) -> list[tuple[str, str]]:
    terms = [(target.expected_movement, "")]
    for alias in target.movement_aliases[:max_aliases_per_target]:
        terms.append((alias, target.expected_movement))
    return terms


def build_movement_only_queries(targets: list[LeadDiscoveryEvalTarget]) -> list[dict]:
    seen = set()
    seen_topics = set()
    queries = []
    for target in targets:
        for movement_term, alias_of in _movement_terms(target, max_aliases_per_target=3):
            movement_key = (movement_term, target.market_sector)
            if movement_key in seen:
                continue
            seen.add(movement_key)
            for family, template in QUERY_FAMILY_TEMPLATES.items():
                topic = template.format(
                    movement=movement_term,
                    market_sector=target.market_sector,
                )
                normalized_topic = _normalized_topic(topic)
                if normalized_topic in seen_topics:
                    continue
                seen_topics.add(normalized_topic)
                queries.append(
                    {
                        "query_id": _query_id(movement_term, family),
                        "query_family": family,
                        "movement": target.expected_movement,
                        "movement_term": movement_term,
                        "alias_of": alias_of,
                        "market_sector": target.market_sector,
                        "topic": topic,
                        "control_exact_name": False,
                    }
                )
    return queries
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Expected:

```text
4 passed
```

Commit:

```bash
git add .claude/skills/vc-signals/scripts/discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_yield_eval.py
git commit -m "Add movement-only discovery query families"
```

---

## Task 3: Provider Search Wrapper

**Files:**
- Create: `.claude/skills/vc-signals/scripts/discovery_search_providers.py`
- Test: `.claude/skills/vc-signals/tests/test_discovery_search_providers.py`

- [ ] **Step 1: Write failing provider tests**

Add:

```python
def test_provider_normalizes_results_and_tracks_latency():
    from discovery_search_providers import normalize_provider_response

    result = normalize_provider_response(
        provider="brave",
        query="agent evals startup",
        raw_items=[
            {
                "title": "Example AI - agent evals",
                "url": "https://example.ai/",
                "description": "Example AI helps teams evaluate agents.",
            }
        ],
        latency_ms=123,
        cost_usd=0.001,
        cache_status="miss",
    )

    assert result["provider"] == "brave"
    assert result["query"] == "agent evals startup"
    assert result["latency_ms"] == 123
    assert result["cost_usd"] == 0.001
    assert result["cache_status"] == "miss"
    assert result["capabilities"] == {
        "snippet_only": True,
        "page_content_returned": False,
        "livecrawl_available": False,
        "cost_estimated": False,
    }
    assert result["items"] == [
        {
            "source": "grounding",
            "title": "Example AI - agent evals",
            "url": "https://example.ai/",
            "snippet": "Example AI helps teams evaluate agents.",
            "provider": "brave",
        }
    ]
```

Add:

```python
def test_provider_skips_when_key_missing(monkeypatch):
    from discovery_search_providers import provider_available

    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("YOU_API_KEY", raising=False)
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

    assert provider_available("brave") is False
    assert provider_available("you") is False
    assert provider_available("perplexity_search") is False
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_search_providers.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError: No module named 'discovery_search_providers'
```

- [ ] **Step 3: Implement normalized provider shell**

Create `discovery_search_providers.py` with:

```python
from __future__ import annotations

import os
from urllib.parse import urlparse


PROVIDER_ENV_KEYS = {
    "brave": "BRAVE_API_KEY",
    "you": ("YOU_API_KEY", "YDC_API_KEY"),
    "perplexity_search": "PERPLEXITY_API_KEY",
}


def provider_available(provider: str) -> bool:
    keys = PROVIDER_ENV_KEYS.get(provider)
    if isinstance(keys, str):
        keys = (keys,)
    return bool(keys and any(os.environ.get(key) for key in keys))


def _snippet(item: dict) -> str:
    return str(item.get("snippet") or item.get("description") or item.get("text") or "")


def normalize_provider_response(
    *,
    provider: str,
    query: str,
    raw_items: list[dict],
    latency_ms: int,
    cost_usd: float,
    cache_status: str,
    capabilities: dict | None = None,
) -> dict:
    capability_payload = {
        "snippet_only": True,
        "page_content_returned": False,
        "livecrawl_available": False,
        "cost_estimated": False,
    }
    capability_payload.update(capabilities or {})
    items = []
    for item in raw_items:
        url = str(item.get("url") or item.get("link") or "")
        title = str(item.get("title") or "")
        if not url or not title:
            continue
        items.append(
            {
                "source": "grounding",
                "title": title,
                "url": url,
                "snippet": _snippet(item),
                "provider": provider,
            }
        )
    return {
        "provider": provider,
        "query": query,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "cache_status": cache_status,
        "capabilities": capability_payload,
        "items": items,
    }
```

- [ ] **Step 4: Add live provider adapters behind configuration**

Implement functions with tests using monkeypatched HTTP clients, not live calls:

```python
def run_provider_query(provider: str, query: str, *, max_results: int = 10, cache_dir=None, timeout_seconds: int = 20) -> dict:
    ...
```

Behavior:
- If provider is unavailable, return `{"provider": provider, "query": query, "items": [], "skipped": true, "skip_reason": "provider_not_configured"}`.
- Brave uses `BRAVE_API_KEY` and sends the request header `X-Subscription-Token`.
- You.com uses `YOU_API_KEY` or `YDC_API_KEY` and sends the request header `X-API-Key`.
- Perplexity Search uses `PERPLEXITY_API_KEY` only if the configured endpoint/model is search, not Sonar/deep-research.
- Perplexity Search normalization discards synthesized answer text. It can only score raw search result URLs/titles/snippets. If citations are present inside an answer payload, normalize only the citation result objects, not the prose answer.
- Provider responses record capability metadata:
  - `snippet_only`
  - `page_content_returned`
  - `livecrawl_available`
  - `cost_estimated`
- Cache key includes provider + query + max results.
- Cache hits return normalized payload with `cache_status="hit"`.
- Never call providers in unit tests.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_search_providers.py -q
```

Expected:

```text
all provider tests pass
```

Commit:

```bash
git add .claude/skills/vc-signals/scripts/discovery_search_providers.py .claude/skills/vc-signals/tests/test_discovery_search_providers.py
git commit -m "Add discovery provider search wrapper"
```

---

## Task 4: Same Query Set Provider Bakeoff

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
- Test: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`

- [ ] **Step 1: Write failing tests for same-query provider execution**

Add:

```python
def test_provider_bakeoff_uses_same_queries_for_each_provider():
    from discovery_yield_eval import run_provider_bakeoff

    queries = [
        {"query_id": "agent-evals-official", "query_family": "official_company_page", "movement": "Agent reliability and evals", "market_sector": "AI Infra", "topic": "agent evals startup official"}
    ]
    calls = []

    def fake_runner(provider, query, **kwargs):
        calls.append((provider, query))
        return {"provider": provider, "query": query, "items": [], "latency_ms": 10, "cost_usd": 0.0, "cache_status": "miss"}

    run_provider_bakeoff(queries, providers=["brave", "you"], provider_runner=fake_runner)

    assert calls == [
        ("brave", "agent evals startup official"),
        ("you", "agent evals startup official"),
    ]
```

- [ ] **Step 2: Implement bakeoff runner**

Add:

```python
def run_provider_bakeoff(
    queries: list[dict],
    *,
    providers: list[str],
    provider_runner,
    max_results: int = 10,
    cache_dir=None,
) -> dict:
    runs = []
    for query in queries:
        for provider in providers:
            result = provider_runner(
                provider,
                query["topic"],
                max_results=max_results,
                cache_dir=cache_dir,
            )
            runs.append(
                {
                    "query_id": query["query_id"],
                    "query_family": query["query_family"],
                    "movement": query["movement"],
                    "market_sector": query["market_sector"],
                    "provider": provider,
                    "provider_result": result,
                }
            )
    return {"runs": runs}
```

- [ ] **Step 3: Add configured-provider skip accounting**

Test:

```python
def test_provider_bakeoff_records_skipped_provider():
    from discovery_yield_eval import run_provider_bakeoff

    def fake_runner(provider, query, **kwargs):
        return {"provider": provider, "query": query, "items": [], "skipped": True, "skip_reason": "provider_not_configured"}

    result = run_provider_bakeoff(
        [{"query_id": "q1", "query_family": "movement_startup", "movement": "Agent security", "market_sector": "Cybersecurity", "topic": "agent security startup"}],
        providers=["you"],
        provider_runner=fake_runner,
    )

    assert result["runs"][0]["provider_result"]["skipped"] is True
    assert result["runs"][0]["provider_result"]["skip_reason"] == "provider_not_configured"
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Commit:

```bash
git add .claude/skills/vc-signals/scripts/discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_yield_eval.py
git commit -m "Add same-query provider bakeoff"
```

---

## Task 5: Verification Pipeline Scoring

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
- Test: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`

- [ ] **Step 1: Write failing tests proving provider results cannot bypass verification**

Add:

```python
def test_provider_result_does_not_count_without_verified_domain():
    from discovery_yield_eval import score_provider_items_against_targets

    result = score_provider_items_against_targets(
        provider_runs=[
            {
                "query_id": "q1",
                "query_family": "seed_funding",
                "movement": "AI agent security",
                "market_sector": "Cybersecurity",
                "provider": "brave",
                "provider_result": {
                    "items": [
                        {
                            "source": "grounding",
                            "title": "TechCrunch covers ExampleCo",
                            "url": "https://techcrunch.com/exampleco",
                            "snippet": "ExampleCo is building AI agent security.",
                            "provider": "brave",
                        }
                    ],
                    "latency_ms": 100,
                    "cost_usd": 0.001,
                    "cache_status": "miss",
                },
            }
        ],
        targets=[],
    )

    assert result["metrics"]["verified_domains_found"] == 0
    assert result["metrics"]["credible_early_stage_leads_per_100_queries"] == 0
    assert result["metrics"]["publisher_content_junk_rate"] > 0
```

Add:

```python
def test_official_domain_research_deeper_counts_as_credible_early_stage_lead():
    from discovery_yield_eval import LeadDiscoveryEvalTarget, score_provider_items_against_targets

    target = LeadDiscoveryEvalTarget(
        name="Lyzr",
        aliases=[],
        domain="lyzr.ai",
        expected_movement="Agent reliability and evals",
        movement_aliases=["agent evals", "AI agent production"],
        market_sector="AI Infra",
        maturity_expectation="seed_to_series_b",
        expected_route="sourcing_candidate",
        last_verified_at="2026-05-10",
        verification_notes="test target",
    )

    score = score_provider_items_against_targets(
        provider_runs=[
            {
                "query_id": "q1",
                "query_family": "official_company_page",
                "movement": "Agent reliability and evals",
                "market_sector": "AI Infra",
                "provider": "brave",
                "provider_result": {
                    "items": [
                        {
                            "source": "grounding",
                            "title": "Take your AI agents to production, faster.",
                            "url": "https://www.lyzr.ai/",
                            "snippet": "Lyzr helps teams deploy AI agents into production.",
                            "provider": "brave",
                        }
                    ],
                    "latency_ms": 100,
                    "cost_usd": 0.001,
                    "cache_status": "miss",
                },
            }
        ],
        targets=[target],
    )

    assert score["metrics"]["verified_domains_found"] == 1
    assert score["metrics"]["early_stage_rows_found"] == 1
    assert score["target_results"][0]["found"] is True
    assert score["target_results"][0]["evaluation_incomplete"] is False
```

- [ ] **Step 2: Implement scoring through existing verification**

Use existing functions:
- `radar_company_discovery.verify_discovery_item`
- `radar_company_discovery.classify_discovery_source`
- the same maturity routing used by `collect_company_discovery`
- the same owner-readiness gating used by the weekly pipeline, if enough evidence is available

Mandatory scoring rule:
- Every accepted provider result must run through verification and maturity routing before it counts as a credible lead.
- Owner-readiness must run before a row can count as owner-ready.
- If maturity or owner-readiness cannot run because required provider evidence is unavailable, mark the row with `evaluation_incomplete=true` and `evaluation_incomplete_reason`.
- `evaluation_incomplete` rows can count as `research_deeper` only when identity and source-authority verification passed.
- `evaluation_incomplete` rows cannot count as `owner_ready_rows_found`.

Add:

```python
def score_provider_items_against_targets(provider_runs: list[dict], targets: list[LeadDiscoveryEvalTarget]) -> dict:
    ...
```

Rules:
- Each provider item becomes a candidate discovery item only after `verify_discovery_item`.
- Rejected publisher/content/listicle/directory/social rows increase junk/false-positive diagnostics but not credible leads.
- Target hit if accepted lead domain equals target domain, or normalized name/alias matches and official domain evidence matches target domain.
- Expected-route mismatch increments `false_positives` only when the system promotes beyond the expected route, for example target expected `monitor_only` but route becomes `sourcing_candidate`.
- Known-target metrics and net-new metrics must be reported separately.

- [ ] **Step 3: Add query-family and provider aggregate metrics**

Add:

```python
def aggregate_bakeoff_metrics(scored_runs: dict) -> dict:
    ...
```

Outputs:
- overall metrics,
- per provider metrics,
- per query family metrics,
- per target recall,
- top false-positive reasons,
- top junk source types.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py -q
```

Commit:

```bash
git add .claude/skills/vc-signals/scripts/discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_yield_eval.py
git commit -m "Score discovery yield through verification gates"
```

---

## Task 6: CLI And Artifacts

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/discovery_yield_eval.py`
- Test: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`

- [ ] **Step 1: Write failing artifact test**

Add:

```python
def test_write_discovery_yield_artifacts(tmp_path):
    from discovery_yield_eval import write_discovery_yield_artifacts

    payload = {
        "summary": {
            "credible_early_stage_leads_per_100_queries": 12.5,
            "partial_eval": False,
            "budget_exceeded": False
        },
        "provider_bakeoff": [{"provider": "brave", "credible_early_stage_leads_per_100_queries": 10.0}],
        "query_family_bakeoff": [{"query_family": "seed_funding", "verified_domains_found": 2}],
        "target_results": [{"name": "Lyzr", "found": True}],
    }

    written = write_discovery_yield_artifacts(payload, tmp_path)

    assert (tmp_path / "lead-discovery-eval.json").exists()
    assert (tmp_path / "provider-bakeoff.json").exists()
    assert (tmp_path / "query-family-bakeoff.json").exists()
    assert (tmp_path / "discovery-yield-summary.md").exists()
    assert written["lead_discovery_eval"].endswith("lead-discovery-eval.json")
```

- [ ] **Step 2: Implement artifact writer**

Add:

```python
def write_discovery_yield_artifacts(payload: dict, output_dir: str | Path) -> dict:
    ...
```

Markdown summary must include:
- providers tested,
- query families tested,
- north-star metric,
- known-target recall,
- net-new credible early-stage lead count,
- best provider by credible early-stage leads per 100 queries,
- best query family by credible early-stage leads per 100 queries,
- false positives,
- junk rate,
- total cost,
- latency p50/p95,
- cache hit rate,
- partial/budget status,
- whether current providers/queries found any eval companies without targeted injection.

- [ ] **Step 3: Add CLI**

CLI:

```bash
python3 .claude/skills/vc-signals/scripts/discovery_yield_eval.py run \
  --eval-set .claude/skills/vc-signals/config/lead_discovery_eval_set.json \
  --providers brave,you,perplexity_search \
  --output-dir docs/radar-runs/current-phase5-discovery-yield-bakeoff \
  --max-results 10 \
  --eval-mode full \
  --max-queries-per-provider 400 \
  --max-total-cost-usd 25 \
  --max-runtime-seconds 1800
```

Behavior:
- Missing providers are skipped and reported.
- Configured providers run the exact same movement-only query set.
- Results are cached.
- No exact-name controls run unless `--include-exact-name-controls true`.
- Exact-name controls write `exact-name-control-results.json` and are excluded from north-star metrics.
- Runtime and cost ceilings are enforced:
  - `--eval-mode smoke|standard|full`
  - `--max-queries-per-provider`
  - `--max-results`
  - `--max-total-cost-usd`
  - `--max-runtime-seconds`
- If a ceiling is exceeded, write artifacts with `partial_eval=true` and `budget_exceeded=true` rather than failing silently.

Default eval-mode budgets:
- `smoke`: 40 queries/provider.
- `standard`: 120 queries/provider.
- `full`: all generated movement-only queries/provider, capped by `--max-queries-per-provider` default 400.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_search_providers.py -q
```

Commit:

```bash
git add .claude/skills/vc-signals/scripts/discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_yield_eval.py
git commit -m "Write discovery yield bakeoff artifacts"
```

---

## Task 7: Guardrail Regression Tests

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_discovery_yield_eval.py`
- Modify: `.claude/skills/vc-signals/tests/test_discovery_search_providers.py`
- Modify only if needed: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Add broad/vibe query guardrail tests**

Add:

```python
def test_discovery_eval_queries_are_movement_specific_not_broad_market_search():
    from discovery_yield_eval import load_eval_set, build_movement_only_queries

    queries = build_movement_only_queries(load_eval_set(".claude/skills/vc-signals/config/lead_discovery_eval_set.json"))
    forbidden = [
        "best startups",
        "top startups",
        "trending startups",
        "hot companies",
        "startup list",
        "companies to watch",
    ]

    for query in queries:
        text = query["topic"].lower()
        assert all(term not in text for term in forbidden)
        assert query["movement_term"].lower().split()[0] in text
```

- [ ] **Step 2: Add no-forbidden-source tests**

Add:

```python
def test_discovery_eval_does_not_use_forbidden_sources():
    from discovery_yield_eval import allowed_providers

    assert set(allowed_providers(["brave", "you", "perplexity_search"])) <= {
        "brave",
        "you",
        "perplexity_search",
    }
    assert "x" not in allowed_providers(["x", "linkedin", "product_hunt"])
    assert "linkedin" not in allowed_providers(["x", "linkedin", "product_hunt"])
    assert "product_hunt" not in allowed_providers(["x", "linkedin", "product_hunt"])
```

- [ ] **Step 3: Add weekly-preview unchanged regression**

If a CLI integration test is added, assert it writes only Phase 5 artifacts and does not touch `weekly-preview.md`:

```python
def test_discovery_yield_cli_does_not_write_weekly_preview(tmp_path):
    from discovery_yield_eval import write_discovery_yield_artifacts

    write_discovery_yield_artifacts({"summary": {}, "provider_bakeoff": [], "query_family_bakeoff": [], "target_results": []}, tmp_path)

    assert not (tmp_path / "weekly-preview.md").exists()
```

- [ ] **Step 4: Run focused and full tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_search_providers.py -q
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected:

```text
all tests pass
```

Commit:

```bash
git add .claude/skills/vc-signals/tests/test_discovery_yield_eval.py .claude/skills/vc-signals/tests/test_discovery_search_providers.py
git commit -m "Add discovery yield guardrail regressions"
```

---

## Task 8: Real Bakeoff Run And Product Review Package

**Files:**
- No production edits expected.
- Generated outputs under `docs/radar-runs/current-phase5-discovery-yield-bakeoff/`.

- [ ] **Step 1: Run the bakeoff with configured providers**

Run:

```bash
python3 .claude/skills/vc-signals/scripts/discovery_yield_eval.py run \
  --eval-set .claude/skills/vc-signals/config/lead_discovery_eval_set.json \
  --providers brave,you,perplexity_search \
  --output-dir docs/radar-runs/current-phase5-discovery-yield-bakeoff \
  --max-results 10 \
  --eval-mode full \
  --max-queries-per-provider 400 \
  --max-total-cost-usd 25 \
  --max-runtime-seconds 1800
```

Expected:
- configured providers run,
- missing providers are skipped with reasons,
- same query set is used for each configured provider,
- artifacts are written.

- [ ] **Step 2: Inspect artifacts**

Read:

```bash
python3 - <<'PY'
import json
from pathlib import Path
run = Path("docs/radar-runs/current-phase5-discovery-yield-bakeoff")
for name in ["lead-discovery-eval.json", "provider-bakeoff.json", "query-family-bakeoff.json"]:
    data = json.loads((run / name).read_text())
    print("\\n###", name)
    print(json.dumps(data, indent=2)[:6000])
PY
```

- [ ] **Step 3: Product review report**

Report:
- providers configured,
- providers skipped,
- total queries,
- total cost,
- latency p50/p95,
- cache hit rate,
- verified domains found,
- early-stage rows found,
- owner-ready rows found,
- research-deeper rows found,
- category anchors found,
- false positives,
- junk rate,
- target recall,
- known-target recall,
- known-target precision,
- net-new verified domains,
- net-new credible early-stage leads,
- net-new false-positive rate,
- credible early-stage leads per 100 queries,
- best provider,
- best query family,
- known eval companies found without targeted injection,
- known eval companies not found,
- whether exact-name controls were used, and if yes, that they were excluded from the north-star metric.

- [ ] **Step 4: Confirm generated artifacts are uncommitted**

Run:

```bash
git status --short
git diff -- docs/radar-runs/weekly-preview.md
```

Expected:
- generated bakeoff directory is untracked,
- `weekly-preview.md` diff is empty,
- code/tests only are committed.

---

## Definition Of Done

Phase 5 planning and implementation are done when:

- `lead_discovery_eval_set.json` includes Lyzr, Copperhelm, Entro, and at least 5 additional AI infra/security/devtools/vertical AI eval companies.
- `lead_discovery_eval_set.json` includes `movement_aliases`, `last_verified_at`, and `verification_notes` for every target.
- The eval set includes at least two vertical AI targets.
- Movement-only query families are generated from movement labels plus capped movement aliases, without target company names or target domains.
- The same movement-only query set runs across Brave, You.com, and optional Perplexity Search when configured.
- Missing providers are skipped with explicit reasons.
- Provider results are cached and measured for cost, latency, cache hits, and provider capabilities.
- Perplexity Search uses only raw result URLs/titles/snippets; synthesized answer text is never evidence.
- Every accepted provider result goes through existing verification and maturity gates.
- Owner-readiness gates run before any row can count as owner-ready.
- Rows with incomplete maturity/owner-readiness evaluation are marked `evaluation_incomplete` and cannot count as owner-ready.
- No provider result can bypass source authority or become `Assign owner` directly.
- Metrics include verified domains, early-stage rows, owner-ready rows, research-deeper rows, category anchors, false positives, junk rate, known-target recall/precision, net-new credible early-stage leads, cost, latency, cache hit rate, and credible early-stage leads per 100 queries.
- Cost/runtime ceilings write partial artifacts with `partial_eval=true` and `budget_exceeded=true`.
- The bakeoff can say which query family/provider currently produces the highest-quality early-stage leads.
- If no provider/query combination finds known eval companies without targeted injection, the artifact says that clearly.
- `weekly-preview.md` remains unchanged.
- Generated run artifacts remain uncommitted.

---

## Self-Review

Spec coverage:
- Lead-discovery eval set, movement aliases, verification timestamps, and vertical AI coverage: Task 1.
- Query family bakeoff with capped alias expansion: Task 2 and Task 4.
- Provider bakeoff and provider capability metadata: Task 3 and Task 4.
- Mandatory verification/maturity/owner-readiness scoring and incomplete-eval handling: Task 5.
- Metrics, known-target versus net-new split, cost/runtime ceilings, and north-star: Task 5 and Task 6.
- Perplexity raw-result-only rule, forbidden-source guardrails, and weekly-preview safety: Task 3 and Task 7.
- Definition of done: included above.

Risk:
- Some eval target facts may drift. Treat the fixture as a versioned seed and let provider evidence determine actual routing.
- Provider APIs may differ in response shape and cost metadata. Normalize missing cost to `0.0` with `cost_estimated=false` if the provider does not return cost.
- If You.com or Perplexity Search is not configured, skip rather than block the bakeoff.

Execution recommendation:
- Implement this phase in a separate pass after reviewing the plan.
- Do not wire winning providers/query families into the weekly run until after the bakeoff report shows improved credible early-stage lead yield.
