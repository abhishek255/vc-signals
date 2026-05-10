# Phase 5.3 Controlled Weekly Trial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the winning Phase 5 discovery-yield query families inside a weekly-shaped run behind an explicit trial flag, while preserving every identity, maturity, owner-readiness, Attio, source-authority, and canonical-name gate.

**Architecture:** Add a trial profile to controlled company discovery, not a default production change. In trial mode, weekly company discovery uses only the selected Phase 5.2 families (`official_company_page`, `founder_company_pages`, and capped `movement_platform`), tags their queries/leads as `discovery_yield_trial`, records trial metrics in `company-discovery.json`, and surfaces a labeled trial summary in `weekly-focus.json` / `weekly-focus.md`. The existing weekly run remains unchanged unless the flag is passed.

**Tech Stack:** Python, pytest, existing `.claude/skills/vc-signals/scripts/radar_company_discovery.py`, `radar_run.py`, `radar_focus.py`, and existing maturity/owner-readiness gates.

---

## Scope

Allowed:
- Add an explicit trial flag to weekly runs.
- Trial only these families:
  - `official_company_page`
  - `founder_company_pages`
  - `movement_platform`, capped
- Use grounded/company web only through the existing configured query runner.
- Use existing provider query cache and runtime budgets.
- Use existing source authority, maturity routing, identity resolution, owner-readiness, Attio, and canonical identity rules.
- Add labeled trial metrics to generated weekly artifacts.

Not allowed:
- No default weekly behavior change.
- No X, LinkedIn scraping, Product Hunt, package registries, Slack, or Attio writeback.
- No provider-result bypass around verification.
- No loosening `Assign owner`, `New To Marathon`, maturity, or source-authority gates.
- No generated run artifacts or provider cache commits.
- No `weekly-preview.md` behavior change.

---

## Product Rules

1. Phase 5.3 is a trial harness, not query-family graduation.
2. Trial rows must be labeled with `discovery_lane = "discovery_yield_trial"`.
3. Mature/category-context rows can support market movements and category context, but cannot enter Sourcing Candidates, New To Marathon, or Assign Owner.
4. Unknown maturity may enter Research Deeper only.
5. `Assign owner` remains controlled by existing owner-readiness and Attio gates.
6. The weekly artifact must report trial metrics even when no rows promote.
7. Success is quality and routing correctness, not forced row count.
8. Trial metrics must count unique domains, not accepted-lead rows.
9. Trial markdown must explicitly state that trial rows did not bypass identity, maturity, owner-readiness, or Attio gates.

---

## File Structure

Modify:
- `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
  - Add `DiscoveryYieldTrialConfig`.
  - Add trial query generation / filtering.
  - Add trial metrics rollup.
  - Tag trial queries/leads.

- `.claude/skills/vc-signals/scripts/radar_run.py`
  - Add `discovery_yield_trial_config` to `run_weekly_artifacts()`.
  - Parse CLI flags.
  - Pass trial summary into weekly focus.

- `.claude/skills/vc-signals/scripts/radar_focus.py`
  - Add optional `discovery_yield_trial` appendix payload.
  - Render a `Discovery Yield Trial` section.

- `.claude/skills/vc-signals/tests/test_radar_company_discovery.py`
  - Query generation, capping, tagging, and metrics tests.

- `.claude/skills/vc-signals/tests/test_radar_run.py`
  - Weekly integration tests for trial flag, Braintrust/Wiz/LangWatch guardrails, and unchanged default behavior.

- `.claude/skills/vc-signals/tests/test_radar_focus.py`
  - Weekly focus rendering tests for the trial section.

Do not modify:
- `docs/radar-runs/current/weekly-preview.md`.
- Phase 5 eval artifacts except generated local trial outputs during verification.

Generated only:
- `docs/radar-runs/current-phase5-3-controlled-weekly-trial/company-discovery.json`
- `docs/radar-runs/current-phase5-3-controlled-weekly-trial/weekly-focus.json`
- `docs/radar-runs/current-phase5-3-controlled-weekly-trial/weekly-focus.md`
- `docs/radar-runs/current-phase5-3-controlled-weekly-trial/runtime-ledger.json`
- `docs/radar-runs/current-phase5-3-controlled-weekly-trial/coverage-report.json`

---

## Task 1: Trial Config And Query Generation Tests

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_radar_company_discovery.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_company_discovery.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
def test_discovery_yield_trial_generates_only_selected_families():
    from radar_company_discovery import DiscoveryYieldTrialConfig, build_company_discovery_queries
    from radar_models import ThemeSignal

    queries = build_company_discovery_queries(
        [
            ThemeSignal(
                market_sector="AI Infra",
                theme="Agent reliability and evals",
                evidence_count=4,
                confidence="Medium",
            )
        ],
        grounded_available=True,
        social_available=False,
        trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    families = {query["query_family"] for query in queries}
    assert families <= {"official_company_page", "founder_company_pages", "movement_platform"}
    assert {"official_company_page", "founder_company_pages", "movement_platform"} <= families
    assert all(query["discovery_lane"] == "discovery_yield_trial" for query in queries)
    assert all(query["candidate_eligible"] is True for query in queries)


def test_discovery_yield_trial_excludes_unproven_families():
    from radar_company_discovery import DiscoveryYieldTrialConfig, build_company_discovery_queries
    from radar_models import ThemeSignal

    queries = build_company_discovery_queries(
        [
            ThemeSignal(
                market_sector="AI Infra",
                theme="Agent reliability and evals",
                evidence_count=4,
                confidence="Medium",
            )
        ],
        grounded_available=True,
        social_available=False,
        trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    families = {query["query_family"] for query in queries}
    assert "seed_funding" not in families
    assert "launch_stealth" not in families
    assert "yc_company_pages" not in families
    assert "movement_startup" not in families
    assert "company_context" not in families


def test_discovery_yield_trial_caps_movement_platform_per_movement():
    from radar_company_discovery import DiscoveryYieldTrialConfig, build_company_discovery_queries
    from radar_models import ThemeSignal

    queries = build_company_discovery_queries(
        [
            ThemeSignal(market_sector="AI Infra", theme="Agent reliability and evals"),
            ThemeSignal(market_sector="AI Infra", theme="AI agent reliability"),
        ],
        grounded_available=True,
        social_available=False,
        trial_config=DiscoveryYieldTrialConfig(enabled=True, movement_platform_cap_per_movement=1),
    )

    movement_platform_queries = [query for query in queries if query["query_family"] == "movement_platform"]
    counts = {}
    for query in movement_platform_queries:
        counts[query["movement"]] = counts.get(query["movement"], 0) + 1
    assert all(count == 1 for count in counts.values())
```

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py -q
```

Expected: failure because `DiscoveryYieldTrialConfig` and `trial_config` do not exist.

- [ ] **Step 3: Add trial config**

In `.claude/skills/vc-signals/scripts/radar_company_discovery.py`, near `DiscoveryRunBudget`, add:

```python
TRIAL_QUERY_FAMILIES = ("official_company_page", "founder_company_pages", "movement_platform")


@dataclass
class DiscoveryYieldTrialConfig:
    enabled: bool = False
    families: tuple[str, ...] = TRIAL_QUERY_FAMILIES
    movement_platform_cap_per_movement: int = 1
    label: str = "Phase 5.3 Discovery Yield Trial"

    def selected_families(self) -> set[str]:
        return {family for family in self.families if family in TRIAL_QUERY_FAMILIES}
```

- [ ] **Step 4: Add trial query specs**

Change `build_company_discovery_queries()` signature:

```python
def build_company_discovery_queries(
    theme_signals: list[ThemeSignal],
    *,
    focus_items: list[FocusItem] | None = None,
    unresolved_candidates: list[Candidate] | None = None,
    grounded_available: bool,
    social_available: bool,
    lookback_days: int = 30,
    max_queries_per_theme: int = 3,
    trial_config: DiscoveryYieldTrialConfig | None = None,
) -> list[dict]:
```

At the start:

```python
    trial_config = trial_config or DiscoveryYieldTrialConfig(enabled=False)
    trial_enabled = bool(trial_config.enabled)
```

For theme signals, when `trial_enabled` is true, replace the existing `query_specs` with:

```python
        if trial_enabled:
            selected = trial_config.selected_families()
            query_specs = []
            if "official_company_page" in selected:
                query_specs.append(
                    (
                        "trial_official_company_page",
                        "official_company_page",
                        f"{theme} startup platform official {market_sector}",
                        "discovery_yield_trial",
                        [f"theme:{_stable_slug(theme)}"],
                        ["official_company_page"],
                    )
                )
            if "founder_company_pages" in selected:
                query_specs.append(
                    (
                        "trial_founder_company_pages",
                        "founder_company_pages",
                        f"{theme} founder company startup official {market_sector}",
                        "discovery_yield_trial",
                        [f"theme:{_stable_slug(theme)}"],
                        ["official_company_page"],
                    )
                )
            if "movement_platform" in selected:
                query_specs.append(
                    (
                        "trial_movement_platform",
                        "movement_platform",
                        f"{theme} platform company official {market_sector}",
                        "discovery_yield_trial",
                        [f"theme:{_stable_slug(theme)}"],
                        ["official_company_page"],
                    )
                )
        else:
            query_specs = [
                (
                    "theme_company_search",
                    "official_company_page",
                    f"{theme} startup company platform official {market_sector}",
                    "theme_signal",
                    [f"theme:{_stable_slug(theme)}"],
                    ["official_company_page"],
                ),
                (
                    "theme_funding_search",
                    "funding_launch_article",
                    f"{theme} startup raises seed Series A launches funding company",
                    "theme_signal",
                    [f"theme:{_stable_slug(theme)}"],
                    ["publisher_article", "funding_press_release"],
                ),
                (
                    "theme_yc_accelerator_search",
                    "yc_accelerator",
                    f'site:ycombinator.com/companies "{theme}" startup company',
                    "theme_signal",
                    [f"theme:{_stable_slug(theme)}"],
                    ["directory_page", "official_company_page"],
                ),
                (
                    "theme_company_context_search",
                    "company_context",
                    f"{theme} market map companies category context startup",
                    "theme_signal",
                    [f"theme:{_stable_slug(theme)}"],
                    ["publisher_article", "directory_page", "official_company_page"],
                ),
            ]
```

When appending trial queries, add:

```python
                discovery_lane="discovery_yield_trial" if trial_enabled else "controlled_company_discovery",
```

to `_append_query()`. Update `_append_query()` to accept and store `discovery_lane`.

- [ ] **Step 5: Enforce movement-platform cap**

Inside the trial branch before `_append_query()`:

```python
            if (
                trial_enabled
                and query_family == "movement_platform"
                and sum(
                    1
                    for existing in queries
                    if existing.get("movement") == theme and existing.get("query_family") == "movement_platform"
                )
                >= trial_config.movement_platform_cap_per_movement
            ):
                continue
```

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py -q
```

Expected: pass.

---

## Task 2: Trial Metrics In Company Discovery

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_radar_company_discovery.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_company_discovery.py`

- [ ] **Step 1: Write failing trial metrics test**

Add:

```python
def test_collect_company_discovery_records_discovery_yield_trial_metrics(monkeypatch):
    from radar_company_discovery import DiscoveryRunBudget, DiscoveryYieldTrialConfig, collect_company_discovery
    from radar_models import ThemeSignal

    def fake_query_runner(topic, **kwargs):
        if "platform company official" in topic:
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "LangWatch - AI evals platform",
                        "url": "https://langwatch.ai/",
                        "snippet": "LangWatch helps AI teams evaluate agents and monitor LLM apps.",
                        "company_name": "LangWatch",
                        "domain": "langwatch.ai",
                    }
                ],
                "warnings": [],
            }
        return {"items": [], "warnings": []}

    result = collect_company_discovery(
        [ThemeSignal(market_sector="AI Infra", theme="Agent reliability and evals", evidence_count=4)],
        query_runner=fake_query_runner,
        grounded_available=True,
        social_available=False,
        run_budget=DiscoveryRunBudget.for_mode(
            "smoke",
            max_company_discovery_queries=3,
            max_maturity_queries=0,
            per_movement_query_cap=3,
        ),
        trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    trial = result["discovery_yield_trial"]
    assert trial["enabled"] is True
    assert trial["families_run"]["movement_platform"]["queries_run"] >= 1
    assert trial["verified_domains"] >= 1
    assert "langwatch.ai" in trial["verified_domain_list"]
    assert result["accepted_leads"][0]["discovery_lane"] == "discovery_yield_trial"
```

- [ ] **Step 2: Verify test fails**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py::test_collect_company_discovery_records_discovery_yield_trial_metrics -q
```

Expected: failure because `collect_company_discovery()` does not accept `trial_config` or write `discovery_yield_trial`.

- [ ] **Step 3: Add `trial_config` to collector**

Update signature:

```python
def collect_company_discovery(
    theme_signals: list[ThemeSignal],
    *,
    focus_items: list[FocusItem] | None = None,
    unresolved_candidates: list[Candidate] | None = None,
    query_runner: Callable | None,
    grounded_available: bool,
    social_available: bool,
    lookback_days: int = 30,
    max_queries_per_theme: int = 3,
    article_fetcher: Callable | None = None,
    max_article_fetches: int = 8,
    run_budget: DiscoveryRunBudget | None = None,
    partial_output_path: Path | str | None = None,
    query_cache_dir: Path | str | None = None,
    trial_config: DiscoveryYieldTrialConfig | None = None,
) -> dict:
```

Pass `trial_config` into `build_company_discovery_queries()`.

- [ ] **Step 4: Tag accepted trial leads**

Where `enriched` is created, replace:

```python
            enriched.setdefault("discovery_lane", "controlled_company_discovery")
```

with:

```python
            enriched.setdefault("discovery_lane", query.get("discovery_lane") or "controlled_company_discovery")
```

Ensure `verify_discovery_item()` copies this onto the lead by adding to the returned dataclass call:

```python
        discovery_lane=item.get("discovery_lane") or query.get("discovery_lane") or "",
```

If `VerifiedCompanyDiscoveryLead` lacks `discovery_lane`, add:

```python
    discovery_lane: str = ""
```

to `.claude/skills/vc-signals/scripts/radar_models.py`, and include it in `_lead_to_item()`.

- [ ] **Step 5: Add trial rollup helper**

Add:

```python
def _trial_summary(result: dict, trial_config: DiscoveryYieldTrialConfig | None) -> dict:
    enabled = bool(trial_config and trial_config.enabled)
    families = list((trial_config or DiscoveryYieldTrialConfig()).selected_families())
    trial_queries = [query for query in result.get("queries", []) if query.get("discovery_lane") == "discovery_yield_trial"]
    trial_leads = [lead for lead in result.get("accepted_leads", []) if lead.get("discovery_lane") == "discovery_yield_trial"]
    rejected = [lead for lead in result.get("rejected_leads", []) if lead.get("discovery_lane") == "discovery_yield_trial"]

    families_run = {}
    for query in trial_queries:
        family = query.get("query_family", "")
        row = families_run.setdefault(
            family,
            {
                "queries_planned": 0,
                "queries_run": 0,
                "verified_domain_set": set(),
                "early_stage_set": set(),
                "research_worthy_unknown_set": set(),
                "category_anchor_set": set(),
            },
        )
        row["queries_planned"] += 1
    for diagnostic in result.get("query_diagnostics", []):
        if diagnostic.get("query_family") not in families:
            continue
        family = diagnostic.get("query_family", "")
        row = families_run.setdefault(
            family,
            {
                "queries_planned": 0,
                "queries_run": 0,
                "verified_domain_set": set(),
                "early_stage_set": set(),
                "research_worthy_unknown_set": set(),
                "category_anchor_set": set(),
            },
        )
        if diagnostic.get("status") in {"processed", "processed_cached", "no_items"}:
            row["queries_run"] += 1

    seen_domains = set()
    for lead in trial_leads:
        domain = lead.get("domain", "")
        if domain:
            seen_domains.add(domain)
        family = _query_family_from_lead(result, lead)
        row = families_run.setdefault(
            family,
            {
                "queries_planned": 0,
                "queries_run": 0,
                "verified_domain_set": set(),
                "early_stage_set": set(),
                "research_worthy_unknown_set": set(),
                "category_anchor_set": set(),
            },
        )
        if domain:
            row["verified_domain_set"].add(domain)
        if lead.get("maturity_status") == "seed_to_series_b":
            row["early_stage_set"].add(domain or lead.get("display_name") or lead.get("name", ""))
        elif lead.get("lead_route") == "research_deeper" and lead.get("maturity_status") == "unknown":
            row["research_worthy_unknown_set"].add(domain or lead.get("display_name") or lead.get("name", ""))
        if lead.get("category_anchor") or lead.get("lead_route") in {"category_context", "monitor_only"}:
            row["category_anchor_set"].add(domain or lead.get("display_name") or lead.get("name", ""))

    serialized_families = {}
    for family, row in families_run.items():
        serialized_families[family] = {
            "queries_planned": row.get("queries_planned", 0),
            "queries_run": row.get("queries_run", 0),
            "verified_domains": len(row.get("verified_domain_set", set())),
            "verified_domain_list": sorted(row.get("verified_domain_set", set())),
            "early_stage": len(row.get("early_stage_set", set())),
            "research_worthy_unknown": len(row.get("research_worthy_unknown_set", set())),
            "category_anchors": len(row.get("category_anchor_set", set())),
        }

    return {
        "enabled": enabled,
        "label": (trial_config.label if trial_config else ""),
        "families": families,
        "queries_planned": len(trial_queries),
        "verified_domains": len(seen_domains),
        "verified_domain_list": sorted(seen_domains),
        "maturity_confirmed_early_stage": sum(1 for lead in trial_leads if lead.get("maturity_status") == "seed_to_series_b"),
        "research_worthy_unknown": sum(1 for lead in trial_leads if lead.get("lead_route") == "research_deeper" and lead.get("maturity_status") == "unknown"),
        "category_anchors": sum(1 for lead in trial_leads if lead.get("category_anchor") or lead.get("lead_route") in {"category_context", "monitor_only"}),
        "accepted": len(trial_leads),
        "rejected": len(rejected),
        "families_run": serialized_families,
    }
```

Add `_query_family_from_lead(result, lead)` by matching `lead["query_id"]` against `result["queries"]` / `result["query_diagnostics"]`.

- [ ] **Step 6: Attach summary before writing**

After deduping accepted/rejected leads:

```python
    result["discovery_yield_trial"] = _trial_summary(result, trial_config)
```

- [ ] **Step 7: Run focused tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py -q
```

Expected: pass.

---

## Task 3: Weekly CLI And Default Behavior

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`

- [ ] **Step 1: Write failing default-behavior test**

Add:

```python
def test_weekly_default_does_not_enable_discovery_yield_trial(tmp_path, monkeypatch):
    import radar_run
    from radar_models import ThemeSignal

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [ThemeSignal(market_sector="AI Infra", theme="Agent reliability and evals")],
    )
    monkeypatch.setattr(radar_run, "run_query", lambda topic, **kwargs: {"items": [], "warnings": []})

    radar_run.run_weekly_artifacts(output_dir=tmp_path, sectors=("ai-infra",), github_limit=0)

    discovery = json.loads((tmp_path / "company-discovery.json").read_text())
    assert discovery["discovery_yield_trial"]["enabled"] is False
    assert all(query.get("discovery_lane") != "discovery_yield_trial" for query in discovery["queries"])
    assert {"official_company_page", "funding_launch_article", "yc_accelerator", "company_context"} & {
        query["query_family"] for query in discovery["queries"]
    }
```

- [ ] **Step 2: Write failing trial-flag integration test**

Add:

```python
def test_weekly_discovery_yield_trial_flag_runs_selected_families(tmp_path, monkeypatch):
    import radar_run
    from radar_company_discovery import DiscoveryRunBudget, DiscoveryYieldTrialConfig
    from radar_models import ThemeSignal

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [ThemeSignal(market_sector="AI Infra", theme="Agent reliability and evals", evidence_count=4)],
    )
    monkeypatch.setattr(radar_run, "run_query", lambda topic, **kwargs: {"items": [], "warnings": []})

    radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("ai-infra",),
        github_limit=0,
        discovery_budget=DiscoveryRunBudget.for_mode("smoke", max_company_discovery_queries=3, max_maturity_queries=0),
        discovery_yield_trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    discovery = json.loads((tmp_path / "company-discovery.json").read_text())
    assert discovery["discovery_yield_trial"]["enabled"] is True
    assert {query["query_family"] for query in discovery["queries"]} <= {
        "official_company_page",
        "founder_company_pages",
        "movement_platform",
    }
```

- [ ] **Step 3: Verify tests fail**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_weekly_default_does_not_enable_discovery_yield_trial .claude/skills/vc-signals/tests/test_radar_run.py::test_weekly_discovery_yield_trial_flag_runs_selected_families -q
```

- [ ] **Step 4: Add weekly function parameter**

In `run_weekly_artifacts()` add:

```python
    discovery_yield_trial_config: DiscoveryYieldTrialConfig | None = None,
```

Import `DiscoveryYieldTrialConfig` from `radar_company_discovery`.

Pass to `collect_company_discovery()`:

```python
        trial_config=discovery_yield_trial_config,
```

- [ ] **Step 5: Add CLI parsing**

Add helper:

```python
def _discovery_yield_trial_config_from_args(args: dict) -> DiscoveryYieldTrialConfig | None:
    if not _get_bool_arg(args, "discovery_yield_trial", "discoveryYieldTrial"):
        return None
    raw_families = args.get("discovery_trial_families", "")
    families = tuple(
        family.strip()
        for family in str(raw_families).split(",")
        if family.strip()
    ) or ("official_company_page", "founder_company_pages", "movement_platform")
    movement_platform_cap = int(args.get("discovery_trial_movement_platform_cap", 1))
    return DiscoveryYieldTrialConfig(
        enabled=True,
        families=families,
        movement_platform_cap_per_movement=movement_platform_cap,
    )
```

In the `weekly` command call:

```python
            discovery_yield_trial_config=_discovery_yield_trial_config_from_args(args),
```

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py -q
```

Expected: pass.

---

## Task 4: Trial Routing Guardrails

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_focus.py`

- [ ] **Step 1: Add Braintrust regression**

```python
def test_discovery_yield_trial_braintrust_unknown_stays_research_deeper(tmp_path, monkeypatch):
    import radar_run
    from radar_company_discovery import DiscoveryRunBudget, DiscoveryYieldTrialConfig
    from radar_models import ThemeSignal

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [ThemeSignal(market_sector="AI Infra", theme="Agent reliability and evals", evidence_count=4)],
    )

    def fake_query(topic, **kwargs):
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Braintrust - AI observability platform",
                    "url": "https://www.braintrust.dev/",
                    "snippet": "Braintrust helps teams build quality AI products with evals and observability.",
                    "company_name": "Braintrust",
                    "domain": "braintrust.dev",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_query)

    radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("ai-infra",),
        github_limit=0,
        discovery_budget=DiscoveryRunBudget.for_mode("smoke", max_company_discovery_queries=3, max_maturity_queries=0),
        discovery_yield_trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    focus = json.loads((tmp_path / "weekly-focus.json").read_text())
    names_by_section = {
        "sourcing": [row["name"] for row in focus["sourcing_candidates"]],
        "new": [row["name"] for row in focus["new_to_marathon"]],
        "research": [row["name"] for row in focus["research_deeper_queue"]],
    }
    assert "Braintrust" not in names_by_section["sourcing"]
    assert "Braintrust" not in names_by_section["new"]
```

- [ ] **Step 2: Add mature-company regression**

```python
def test_discovery_yield_trial_mature_company_routes_to_category_context(tmp_path, monkeypatch):
    import radar_run
    from radar_company_discovery import DiscoveryRunBudget, DiscoveryYieldTrialConfig
    from radar_models import ThemeSignal

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [ThemeSignal(market_sector="Cybersecurity", theme="Cloud security posture", evidence_count=4)],
    )

    def fake_query(topic, **kwargs):
        lowered = topic.lower()
        if any(term in lowered for term in ["series c", "valuation", "funding", "acquired", "acquisition"]):
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "Wiz announces $1 billion funding round at $12 billion valuation",
                        "url": "https://www.wiz.io/blog/funding",
                        "snippet": "Wiz announced a $1 billion funding round at a $12 billion valuation.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Wiz Cloud Security",
                    "url": "https://www.wiz.io/",
                    "snippet": "Wiz is a cloud security platform.",
                    "company_name": "Wiz",
                    "domain": "wiz.io",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_query)

    radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        github_limit=0,
        discovery_budget=DiscoveryRunBudget.for_mode("smoke", max_company_discovery_queries=3, max_maturity_queries=3),
        discovery_yield_trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    focus = json.loads((tmp_path / "weekly-focus.json").read_text())
    assert "Wiz" not in [row["name"] for row in focus["sourcing_candidates"]]
    assert "Wiz" not in [row["name"] for row in focus["new_to_marathon"]]
    assert "Wiz" in [row["name"] for row in focus["appendix"]["category_context"]]
```

- [ ] **Step 3: Add LangWatch owner gate regression**

```python
def test_discovery_yield_trial_langwatch_cannot_assign_owner_without_owner_readiness(tmp_path, monkeypatch):
    import radar_run
    from radar_company_discovery import DiscoveryRunBudget, DiscoveryYieldTrialConfig
    from radar_models import ThemeSignal

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(radar_run, "_attio_client_from_env", lambda: None)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [ThemeSignal(market_sector="AI Infra", theme="Agent reliability and evals", evidence_count=4)],
    )

    def fake_query(topic, **kwargs):
        lowered = topic.lower()
        if any(term in lowered for term in ["series c", "valuation", "funding", "acquired", "acquisition"]):
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "LangWatch announces $1M funding round",
                        "url": "https://langwatch.ai/blog/langwatch-ai-announcing-1m-funding-round-to-bring-the-power-of-evaluations-to-ai-teams",
                        "snippet": "LangWatch announced a $1M seed funding round.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "LangWatch AI evals platform",
                    "url": "https://langwatch.ai/",
                    "snippet": "LangWatch helps AI teams evaluate and monitor LLM applications.",
                    "company_name": "LangWatch",
                    "domain": "langwatch.ai",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_query)

    radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("ai-infra",),
        github_limit=0,
        discovery_budget=DiscoveryRunBudget.for_mode("smoke", max_company_discovery_queries=3, max_maturity_queries=3),
        discovery_yield_trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    focus = json.loads((tmp_path / "weekly-focus.json").read_text())
    all_rows = focus["sourcing_candidates"] + focus["research_deeper_queue"] + focus["partner_focus"]
    langwatch = next(row for row in all_rows if row["name"] == "LangWatch")
    assert langwatch["recommended_action"] != "Assign owner"
    assert "Attio status unknown" in langwatch.get("missing_owner_evidence", []) or langwatch["recommended_action"] == "Research deeper"
```

- [ ] **Step 4: Run guardrail tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py -q
```

Expected: pass.

---

## Task 5: Weekly Focus Trial Section

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_radar_focus.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_focus.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`

- [ ] **Step 1: Add rendering test**

Add:

```python
def test_weekly_focus_renders_discovery_yield_trial_section():
    from radar_focus import build_weekly_focus_artifact, render_weekly_focus_markdown

    artifact = build_weekly_focus_artifact(
        candidates=[],
        category_context_items=[],
        theme_signals=[],
        sector_intelligence=[],
        source_health=[],
        run_id="2026-05-10",
        discovery_yield_trial={
            "enabled": True,
            "label": "Phase 5.3 Discovery Yield Trial",
            "families": ["official_company_page", "founder_company_pages", "movement_platform"],
            "verified_domains": 3,
            "maturity_confirmed_early_stage": 1,
            "research_worthy_unknown": 1,
            "category_anchors": 1,
            "accepted": 3,
            "rejected": 8,
            "verified_domain_list": ["langwatch.ai", "wiz.io", "straiker.ai"],
            "families_run": {
                "official_company_page": {"queries_run": 1, "verified_domains": 1, "early_stage": 0, "research_worthy_unknown": 1, "category_anchors": 0},
                "movement_platform": {"queries_run": 1, "verified_domains": 2, "early_stage": 1, "research_worthy_unknown": 0, "category_anchors": 1},
            },
        },
    )

    markdown = render_weekly_focus_markdown(artifact)

    assert "## Discovery Yield Trial" in markdown
    assert "Verified domains: 3" in markdown
    assert "Early-stage confirmed: 1" in markdown
    assert "official_company_page" in markdown
```

- [ ] **Step 2: Verify red**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py::test_weekly_focus_renders_discovery_yield_trial_section -q
```

- [ ] **Step 3: Add artifact parameter**

Update `build_weekly_focus_artifact()` signature:

```python
def build_weekly_focus_artifact(
    *,
    candidates: list[Candidate],
    category_context_items: list[FocusItem] | None = None,
    theme_signals: list[ThemeSignal] | None = None,
    sector_intelligence: list[SectorIntelligence] | None = None,
    source_gap_context: str = "",
    source_health: list[dict] | None = None,
    run_id: str = "",
    discovery_yield_trial: dict | None = None,
) -> WeeklyFocusArtifact:
```

In `appendix`:

```python
        "discovery_yield_trial": discovery_yield_trial or {"enabled": False},
```

In `radar_run.run_weekly_artifacts()`, pass:

```python
        discovery_yield_trial=company_discovery.get("discovery_yield_trial", {"enabled": False}),
```

- [ ] **Step 4: Render section**

In `render_weekly_focus_markdown()`, after Category Context and before New To Marathon, add:

```python
    trial = artifact.appendix.get("discovery_yield_trial", {})
    if trial.get("enabled"):
        lines.extend(["", "## Discovery Yield Trial", ""])
        lines.append(f"Label: {trial.get('label', 'Discovery Yield Trial')}")
        lines.append("Trial results are experimental and did not bypass identity, maturity, owner-readiness, or Attio gates.")
        lines.append(f"- Families: {', '.join(trial.get('families') or [])}")
        lines.append(f"- Verified domains: {trial.get('verified_domains', 0)}")
        lines.append(f"- Early-stage confirmed: {trial.get('maturity_confirmed_early_stage', 0)}")
        lines.append(f"- Research-worthy unknown: {trial.get('research_worthy_unknown', 0)}")
        lines.append(f"- Category anchors / monitor-only: {trial.get('category_anchors', 0)}")
        lines.append(f"- Accepted / rejected: {trial.get('accepted', 0)} / {trial.get('rejected', 0)}")
        families_run = trial.get("families_run") or {}
        if families_run:
            lines.extend(["", "| Family | Queries Run | Verified Domains | Early | Unknown Research | Category Anchors |", "|---|---:|---:|---:|---:|---:|"])
            for family, row in families_run.items():
                lines.append(
                    f"| {_markdown_table_cell(family)} | {row.get('queries_run', 0)} | {row.get('verified_domains', 0)} | {row.get('early_stage', 0)} | {row.get('research_worthy_unknown', 0)} | {row.get('category_anchors', 0)} |"
                )
```

- [ ] **Step 5: Run focus tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected: pass.

---

## Task 6: Bounded Trial Run And Review Package

**Files:**
- Generated only under `docs/radar-runs/current-phase5-3-controlled-weekly-trial/`

- [ ] **Step 1: Run focused tests**

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_company_discovery.py \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  .claude/skills/vc-signals/tests/test_radar_focus.py \
  .claude/skills/vc-signals/tests/test_discovery_yield_eval.py \
  .claude/skills/vc-signals/tests/test_discovery_maturity_evidence.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run full test suite**

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: pass.

- [ ] **Step 3: Run bounded weekly trial**

Use cached provider data where available, bounded GitHub, and the explicit trial flag:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly \
  --output-dir docs/radar-runs/current-phase5-3-controlled-weekly-trial \
  --sectors ai-infra,cybersecurity,devtools,vertical-ai,data-infra,oss \
  --github-limit 10 \
  --github-timeout 180 \
  --query-timeout 75 \
  --discovery-budget-mode weekly \
  --max-company-discovery-queries 12 \
  --max-maturity-queries 6 \
  --max-results-per-query 10 \
  --per-movement-query-cap 3 \
  --discovery-yield-trial \
  --discovery-trial-families official_company_page,founder_company_pages,movement_platform \
  --discovery-trial-movement-platform-cap 1
```

Expected:
- Command exits successfully.
- `company-discovery.json` has `discovery_yield_trial.enabled = true`.
- `weekly-focus.md` includes `## Discovery Yield Trial`.
- `weekly-preview.md` is produced but the tracked baseline `docs/radar-runs/current/weekly-preview.md` remains unchanged.

- [ ] **Step 4: Produce comparison summary**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
base = Path("docs/radar-runs/current-phase5-3-controlled-weekly-trial")
discovery = json.loads((base / "company-discovery.json").read_text())
focus = json.loads((base / "weekly-focus.json").read_text())
trial = discovery.get("discovery_yield_trial", {})
print("trial", json.dumps(trial, indent=2)[:4000])
print("sourcing", [row["name"] for row in focus.get("sourcing_candidates", [])])
print("research", [row["name"] for row in focus.get("research_deeper_queue", [])])
print("category", [row["name"] for row in focus.get("appendix", {}).get("category_context", [])])
print("new_to_marathon", [row["name"] for row in focus.get("new_to_marathon", [])])
workflow = focus.get("workflow_view", {})
assign_owner = workflow.get("Assign owner") or workflow.get("assign_owner") or []
print("assign_owner", [row["name"] for row in assign_owner])
PY
```

- [ ] **Step 5: Confirm generated artifacts are untracked**

```bash
git status --short
git diff -- docs/radar-runs/current/weekly-preview.md
```

Expected:
- Generated run directory appears untracked.
- No diff for `docs/radar-runs/current/weekly-preview.md`.

---

## Commit Plan

After tests pass and generated artifacts are confirmed untracked:

```bash
git add \
  .claude/skills/vc-signals/scripts/radar_company_discovery.py \
  .claude/skills/vc-signals/scripts/radar_run.py \
  .claude/skills/vc-signals/scripts/radar_focus.py \
  .claude/skills/vc-signals/scripts/radar_models.py \
  .claude/skills/vc-signals/tests/test_radar_company_discovery.py \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  .claude/skills/vc-signals/tests/test_radar_focus.py \
  docs/superpowers/plans/2026-05-10-phase-5-3-controlled-weekly-trial.md
git commit -m "Add controlled weekly discovery yield trial"
```

Do not stage:
- `docs/radar-runs/current-phase5-3-controlled-weekly-trial/`
- provider caches
- `.DS_Store`
- `docs/radar-runs/current/weekly-preview.md`

---

## Final Review Package

After implementation, report:
1. Full test result.
2. Trial runtime / budget / cache status.
3. Discovery Yield Trial summary from `company-discovery.json`.
4. Families run and per-family yield.
5. Verified domains.
6. Early-stage confirmed rows.
7. Research-worthy unknown rows.
8. Category anchors / monitor-only rows.
9. Rows promoted into Sourcing Candidates, Research Deeper, Category Context, New To Marathon, and Assign Owner.
10. Evidence basis for any row that changed lanes.
11. Confirmation Braintrust, Wiz/Orca/Darktrace, and LangWatch regressions pass.
12. Confirmation `weekly-preview.md` unchanged.
13. Confirmation generated artifacts/cache are not committed.

---

## Acceptance Criteria

- Default weekly behavior is unchanged when the trial flag is absent.
- Trial mode runs only `official_company_page`, `founder_company_pages`, and capped `movement_platform`.
- Trial output is labeled in `company-discovery.json`, `weekly-focus.json`, and `weekly-focus.md`.
- Mature/category-anchor rows cannot enter Sourcing Candidates, New To Marathon, or Assign Owner.
- Unknown-maturity rows can enter Research Deeper only.
- No row becomes Assign Owner unless existing owner-readiness and Attio gates pass.
- Runtime remains bounded and observable.
- Generated artifacts and provider cache remain uncommitted.

---

## Self-Review

- Spec coverage: Covers explicit trial flag, selected query families, excluded families, unchanged gates, labeled artifacts, trial metrics, Braintrust/Wiz/LangWatch regressions, bounded run, and generated artifact hygiene.
- Placeholder scan: No `TBD`, broad source expansion, or vague "add tests" instructions remain.
- Type consistency: New `DiscoveryYieldTrialConfig`, `discovery_yield_trial_config`, `discovery_yield_trial`, and `discovery_lane` names are used consistently across planned files.
