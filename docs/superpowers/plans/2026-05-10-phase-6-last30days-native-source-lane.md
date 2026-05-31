# Phase 6A last30days-Native Source Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit whether company-native source lanes, starting with Launch HN / Show HN and YC company pages, return identity-useful fields through last30days. Phase 6A does not decide whether a lead is early-stage or owner-ready; it answers whether last30days gives `vc-signals` enough source-backed metadata to run those gates later.

**Architecture:** Keep the boundary clean: last30days is the retrieval/source engine; `vc-signals` is the Marathon intelligence/workflow layer. Phase 6A audits last30days source-specific output for HN launch and YC company queries, normalizes items into `company_candidate`, `project_only`, `needs_detail_enrichment`, or `rejected`, and reports metadata coverage. Phase 6B, planned only after reviewing the audit, will run accepted candidates through existing source-authority, identity, maturity, owner-readiness, Attio-safe, and canonical-name gates. Direct HN Algolia, generic provider, or YC retrieval code inside `vc-signals` is explicitly out of scope unless the audit proves last30days lacks the capability or metadata.

**Tech Stack:** Python, pytest, existing `.claude/skills/vc-signals/scripts/last30days_adapter.py`, `radar_company_discovery.py`, `identity_resolution.py`, `radar_sources.py`, `owner_readiness.py`, `founder_team_verification.py`, `canonical_identity.py`, and local generated artifacts under `docs/radar-runs/`.

---

## Boundary Decision

`last30days` should own:
- HN / Show HN / Launch HN retrieval through its existing Algolia-backed `hackernews` source.
- Grounded web retrieval for `site:ycombinator.com/companies` or other YC-style queries.
- GitHub, Reddit, YouTube, web provider calls, and source execution.
- Source-level retry/caching/storage when available.
- Raw source metadata and basic normalized evidence items.

`vc-signals` should own:
- Source-role interpretation for Marathon.
- Source authority and identity-useful metadata preservation.
- Company identity resolution.
- Maturity / consensus / too-late routing.
- Founder/team and owner-readiness gates.
- Attio context and action routing.
- Weekly focus artifact and Alex/Marathon review workflow.

This phase must not create a second retrieval engine inside `vc-signals`.

---

## Phase Split

**Phase 6A: last30days-native source audit and normalization**
- Run source-specific HN and YC-style queries through `last30days_adapter.run_query()`.
- Inspect raw and normalized field coverage.
- Preserve HN discussion metadata, outbound URLs, author, engagement, domains, YC URLs, and any upstream company metadata.
- Normalize records into `company_candidate`, `project_only`, `needs_detail_enrichment`, or `rejected`.
- Report only audit and normalization metrics. Do not report credible early-stage leads, sourcing candidates, `Assign owner`, `New To Marathon`, or provider graduation decisions.

**Phase 6B: gated source-native trial, after Phase 6A review**
- Consume Phase 6A `company_candidate` rows only after the audit proves the metadata is strong enough.
- Run the existing source authority, identity, maturity, owner-readiness, Attio-safe, and canonical-name gates.
- Compare quality against the Phase 5.4 Brave baseline only after those gates run.

---

## Scope

Allowed:
- Call `last30days_adapter.run_query()` with narrow source-specific queries.
- Audit raw and normalized last30days output fields.
- Build a `company-native-source-audit.json` artifact.
- Build a `company-native-normalized-leads.json` artifact from last30days output.
- Add lightweight YC detail extraction only if the audit proves last30days returns YC page URLs but not website/founder/batch metadata.
- Preserve HN GitHub outbound URLs as project-only evidence, not verified company identity.
- Include Phase 5.4 Brave metrics as context only, with an explicit note that Phase 6A is not directly comparable until Phase 6B gates run.

Not allowed:
- No direct HN Algolia runner in `vc-signals`.
- No new generic provider wrappers for weekly/source-lane execution.
- No X, LinkedIn scraping, Product Hunt, package registries, Slack, or Attio writeback.
- No broad web search.
- No company-name domain guessing.
- No default weekly behavior change.
- No `weekly-preview.md` behavior change.
- No generated artifact/cache commits.
- No bypass around identity/maturity/owner-readiness/Attio gates.

---

## Product Rules

1. Phase 6A is an offline audit and normalization layer. It does not graduate any source into weekly default.
2. Native-source leads can become `verified_company` only with source-backed official domain proof.
3. `news.ycombinator.com`, `hn.algolia.com`, and `ycombinator.com` are evidence sources, not company domains.
4. HN outbound GitHub/project URLs count as `project_only_leads`, not verified companies.
5. Phase 6A does not assign maturity, lead routes, owner actions, `New To Marathon`, or sourcing-candidate status.
6. Unknown maturity can only be handled in Phase 6B, and then routes to `research_deeper`, not `sourcing_candidate` or `Assign owner`.
7. Category/context/mature/acquired rows can support movements in Phase 6B but cannot become `Assign owner` or `New To Marathon`.
8. Owner-ready actions still require verified identity, maturity, founder/team evidence, commercial/customer/funding evidence, and Attio-safe context in Phase 6B.
9. Metrics must count unique domains per lane, not raw rows.
10. The Phase 6A north-star is metadata readiness: source-backed company candidate domains with enough fields to enter Phase 6B gates per 100 source items.
11. Phase 6A success is clean boundary preservation plus useful audit output, not more rows or action upgrades.

---

## File Structure

Create:
- `.claude/skills/vc-signals/scripts/company_native_last30days.py`
  - Source-specific query builder for HN launch and YC company lanes.
  - last30days audit runner.
  - Field-preservation report builder.
  - Native-source lead normalization from last30days items.
  - Audit metrics, normalized-lead summaries, baseline context, and static boundary guard helpers.

- `.claude/skills/vc-signals/tests/test_company_native_last30days.py`
  - Tests for query generation, metadata audit, no-direct-retrieval boundary, HN company/project split, YC metadata gap handling, and audit summaries.

Modify:
- `.claude/skills/vc-signals/scripts/last30days_adapter.py`
  - Only if the audit test proves identity-useful fields from last30days are still being dropped.

- `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
  - Only if a small reusable verification helper needs to be exposed. Do not move retrieval code here.

Do not modify:
- `docs/radar-runs/current/weekly-preview.md`
- Default weekly run behavior in `radar_run.py`
- Phase 5.4 provider bakeoff defaults
- last30days vendor code in `vendor/last30days-skill/`

Generated only:
- `docs/radar-runs/current-phase6-last30days-native-audit/company-native-source-audit.json`
- `docs/radar-runs/current-phase6-last30days-native-audit/company-native-normalized-leads.json`
- `docs/radar-runs/current-phase6-last30days-native-audit/company-native-source-audit.md`
- `docs/radar-runs/current-phase6-last30days-native-audit/raw-last30days/`

---

## Task 1: Source-Specific Query Builder And Audit Schema

**Files:**
- Create: `.claude/skills/vc-signals/scripts/company_native_last30days.py`
- Create: `.claude/skills/vc-signals/tests/test_company_native_last30days.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
from company_native_last30days import build_last30days_native_queries, summarize_last30days_native_audit


def test_build_last30days_native_queries_uses_last30days_sources():
    movements = [
        {
            "movement": "AI agent security",
            "market_sector": "Cybersecurity",
            "origin_row_ids": ["focus:burrow"],
        }
    ]

    queries = build_last30days_native_queries(movements, lanes=("launch_hn", "yc_company"))

    assert {query["lane"] for query in queries} == {"launch_hn", "yc_company"}
    assert all(query["retrieval_engine"] == "last30days" for query in queries)
    assert any(query["sources"] == "hackernews" for query in queries)
    assert any(query["sources"] == "grounding" for query in queries)
    assert any("Show HN" in query["topic"] for query in queries)
    assert any("Launch HN" in query["topic"] for query in queries)
    assert any("site:ycombinator.com/companies" in query["topic"] for query in queries)


def test_build_last30days_native_queries_filters_forbidden_lanes():
    queries = build_last30days_native_queries(
        [{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        lanes=("launch_hn", "yc_company", "x", "linkedin", "product_hunt"),
    )

    assert {query["lane"] for query in queries} == {"launch_hn", "yc_company"}
    assert all("linkedin" not in query["topic"].lower() for query in queries)
    assert all("product hunt" not in query["topic"].lower() for query in queries)


def test_summarize_last30days_native_audit_reports_identity_fields():
    query = {
        "id": "phase6:launch_hn:1",
        "lane": "launch_hn",
        "topic": "Show HN AI agent security",
        "sources": "hackernews",
    }
    payload = {
        "items": [
            {
                "source": "hackernews",
                "title": "Show HN: Burrow - Runtime Security for AI Agents",
                "url": "https://burrow.security",
                "hn_url": "https://news.ycombinator.com/item?id=47761957",
                "author": "saranshrana",
                "engagement": {"points": 123, "comments": 42},
                "_raw_fields_present": ["title", "url", "hn_url", "author", "engagement"],
                "_identity_fields_present_upstream": ["domain"],
                "domain": "burrow.security",
            }
        ],
        "warnings": [],
        "errors_by_source": {},
    }

    audit = summarize_last30days_native_audit([(query, payload)])

    row = audit["rows"][0]
    assert row["lane"] == "launch_hn"
    assert row["items_seen"] == 1
    assert row["identity_useful_fields_present"]["domain"] == 1
    assert row["field_presence"]["hn_url"] == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py -q
```

Expected: fail because `company_native_last30days.py` does not exist.

- [ ] **Step 3: Implement query builder and audit schema**

Create `.claude/skills/vc-signals/scripts/company_native_last30days.py` with:

```python
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse


NATIVE_LANES = ("launch_hn", "yc_company")
IDENTITY_FIELDS = (
    "outbound_url",
    "resolved_url",
    "story_url",
    "domain",
    "homepage",
    "website",
    "hn_url",
    "author",
    "owner_name",
    "owner_type",
    "topics",
    "description",
)


@dataclass
class Last30daysNativeQuery:
    id: str
    lane: str
    topic: str
    sources: str
    movement: str
    market_sector: str
    retrieval_engine: str = "last30days"
    discovery_lane: str = "last30days_native_source_audit"
    lookback_days: int = 30
    web_backend: str = "auto"
    origin_row_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def build_last30days_native_queries(
    movements: list[dict],
    *,
    lanes: tuple[str, ...] = NATIVE_LANES,
    lookback_days: int = 30,
) -> list[dict]:
    selected_lanes = [lane for lane in lanes if lane in NATIVE_LANES]
    queries: list[dict] = []
    seen = set()
    for row in movements:
        movement = (row.get("movement") or "").strip()
        if not movement:
            continue
        market_sector = row.get("market_sector") or ""
        origin_ids = list(row.get("origin_row_ids") or [])
        specs: list[tuple[str, str, str]] = []
        if "launch_hn" in selected_lanes:
            specs.extend(
                [
                    ("launch_hn", f"Show HN {movement}", "hackernews"),
                    ("launch_hn", f"Launch HN {movement}", "hackernews"),
                    ("launch_hn", f"Show HN {movement} startup", "hackernews"),
                ]
            )
        if "yc_company" in selected_lanes:
            specs.append(("yc_company", f'site:ycombinator.com/companies "{movement}" startup', "grounding"))
        for lane, topic, sources in specs:
            key = (lane, " ".join(topic.lower().split()))
            if key in seen:
                continue
            seen.add(key)
            queries.append(
                Last30daysNativeQuery(
                    id=f"phase6:{lane}:{len(queries) + 1}",
                    lane=lane,
                    topic=topic,
                    sources=sources,
                    movement=movement,
                    market_sector=market_sector,
                    lookback_days=lookback_days,
                    origin_row_ids=origin_ids,
                ).to_dict()
            )
    return queries


def summarize_last30days_native_audit(query_payloads: list[tuple[dict, dict]]) -> dict:
    rows = []
    total_items = 0
    total_identity_fields = Counter()
    for query, payload in query_payloads:
        items = payload.get("items", []) or []
        total_items += len(items)
        field_presence = Counter()
        identity_presence = Counter()
        for item in items:
            for field in item.get("_raw_fields_present") or item.keys():
                field_presence[field] += 1
            for field in IDENTITY_FIELDS:
                if item.get(field) not in ("", None, [], {}):
                    identity_presence[field] += 1
                    total_identity_fields[field] += 1
        rows.append(
            {
                "query_id": query.get("id", ""),
                "lane": query.get("lane", ""),
                "topic": query.get("topic", ""),
                "sources": query.get("sources", ""),
                "items_seen": len(items),
                "field_presence": dict(sorted(field_presence.items())),
                "identity_useful_fields_present": dict(sorted(identity_presence.items())),
                "warnings": payload.get("warnings", []),
                "errors_by_source": payload.get("errors_by_source", {}),
            }
        )
    return {
        "summary": {
            "queries": len(query_payloads),
            "items_seen": total_items,
            "identity_useful_fields_present": dict(sorted(total_identity_fields.items())),
        },
        "rows": rows,
    }
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/company_native_last30days.py .claude/skills/vc-signals/tests/test_company_native_last30days.py
git commit -m "Add last30days-native source audit queries"
```

---

## Task 1.5: No Direct Retrieval Boundary Guard

**Files:**
- Modify: `.claude/skills/vc-signals/tests/test_company_native_last30days.py`

- [ ] **Step 1: Write failing/static regression test**

Add:

```python
from pathlib import Path


def test_phase6a_does_not_import_direct_retrieval_clients():
    script = Path(__file__).resolve().parents[1] / "scripts" / "company_native_last30days.py"
    text = script.read_text() if script.exists() else ""
    forbidden_tokens = [
        "company_native_source_bakeoff",
        "run_launch_hn_lane",
        "run_yc_company_lane",
        "run_provider_query",
        "discovery_search_providers",
        "hn.algolia.com/api",
        "api.search.brave.com",
        "ydc-index.io",
        "requests.get(",
        "requests.post(",
        "urlopen(",
    ]

    assert not [token for token in forbidden_tokens if token in text]
```

- [ ] **Step 2: Run test**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py::test_phase6a_does_not_import_direct_retrieval_clients -q
```

Expected: pass once `company_native_last30days.py` exists and uses only `last30days_adapter.run_query()` for retrieval.

---

## Task 2: Preserve HN Outbound And Discussion Metadata In Adapter

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/last30days_adapter.py`
- Modify: `.claude/skills/vc-signals/tests/test_last30days_adapter.py`

- [ ] **Step 1: Write failing test if missing**

Add or update:

```python
def test_normalize_report_items_preserves_hn_url_and_outbound_url():
    from last30days_adapter import normalize_report_items

    normalized = normalize_report_items(
        {
            "hackernews": [
                {
                    "title": "Show HN: Burrow - Runtime Security for AI Agents",
                    "url": "https://burrow.security",
                    "hn_url": "https://news.ycombinator.com/item?id=47761957",
                    "author": "saranshrana",
                    "engagement": {"points": 123, "comments": 42},
                    "domain": "burrow.security",
                }
            ]
        }
    )

    item = normalized[0]
    assert item["url"] == "https://burrow.security"
    assert item["hn_url"] == "https://news.ycombinator.com/item?id=47761957"
    assert item["outbound_url"] == "https://burrow.security"
    assert item["domain"] == "burrow.security"
    assert "hn_url" in item["_raw_fields_present"]
```

- [ ] **Step 2: Run test**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_last30days_adapter.py::test_normalize_report_items_preserves_hn_url_and_outbound_url -q
```

Expected: fail if `hn_url` or `outbound_url` is not preserved.

- [ ] **Step 3: Patch adapter only if needed**

In `.claude/skills/vc-signals/scripts/last30days_adapter.py`, extend `IDENTITY_USEFUL_FIELDS`:

```python
IDENTITY_USEFUL_FIELDS = (
    "outbound_url",
    "resolved_url",
    "story_url",
    "hn_url",
    "domain",
    "homepage",
    "website",
    "owner_name",
    "owner_type",
    "topics",
    "description",
)
```

In `normalize_report_items()`, after building `normalized_item`, add:

```python
            if source == "hackernews" and item.get("url") and item.get("hn_url"):
                normalized_item.setdefault("outbound_url", item.get("url"))
                normalized_item.setdefault("source_url", item.get("hn_url"))
```

Keep the existing raw-field and identity-field reporting.

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_last30days_adapter.py .claude/skills/vc-signals/tests/test_company_native_last30days.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/last30days_adapter.py .claude/skills/vc-signals/tests/test_last30days_adapter.py
git commit -m "Preserve last30days HN outbound metadata"
```

---

## Task 3: Native Lead Normalization From last30days Items

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/company_native_last30days.py`
- Modify: `.claude/skills/vc-signals/tests/test_company_native_last30days.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
from company_native_last30days import normalize_last30days_native_item


def test_normalize_hn_item_with_outbound_url_becomes_company_lead():
    query = {
        "id": "phase6:launch_hn:1",
        "lane": "launch_hn",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "Show HN AI agent security",
    }
    item = {
        "source": "hackernews",
        "title": "Show HN: Burrow - Runtime Security for AI Agents",
        "url": "https://burrow.security",
        "hn_url": "https://news.ycombinator.com/item?id=47761957",
        "outbound_url": "https://burrow.security",
        "domain": "burrow.security",
        "author": "saranshrana",
        "engagement": {"points": 123, "comments": 42},
        "snippet": "Runtime security for AI agents.",
    }

    lead = normalize_last30days_native_item(item, query)

    assert lead["kind"] == "company_candidate"
    assert lead["name"] == "Burrow"
    assert lead["domain"] == "burrow.security"
    assert lead["source_url"] == "https://news.ycombinator.com/item?id=47761957"
    assert lead["official_url"] == "https://burrow.security"
    assert "hn_launch_outbound_url" in lead["verification_basis"]


def test_normalize_hn_item_with_github_outbound_becomes_project_only():
    query = {
        "id": "phase6:launch_hn:1",
        "lane": "launch_hn",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
    }
    item = {
        "source": "hackernews",
        "title": "Show HN: AgentShield",
        "url": "https://github.com/example/agentshield",
        "hn_url": "https://news.ycombinator.com/item?id=1",
    }

    lead = normalize_last30days_native_item(item, query)

    assert lead["kind"] == "project_only"
    assert lead["domain"] == ""
    assert "hn_outbound_github_project_only" in lead["missing_evidence"]


def test_normalize_yc_item_without_website_marks_metadata_gap():
    query = {
        "id": "phase6:yc_company:1",
        "lane": "yc_company",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
    }
    item = {
        "source": "grounding",
        "title": "ShieldAgent | Y Combinator",
        "url": "https://www.ycombinator.com/companies/shieldagent",
        "snippet": "AI agent security company.",
    }

    lead = normalize_last30days_native_item(item, query)

    assert lead["kind"] == "needs_detail_enrichment"
    assert "yc_official_website_missing" in lead["missing_evidence"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py::test_normalize_hn_item_with_outbound_url_becomes_company_lead .claude/skills/vc-signals/tests/test_company_native_last30days.py::test_normalize_hn_item_with_github_outbound_becomes_project_only .claude/skills/vc-signals/tests/test_company_native_last30days.py::test_normalize_yc_item_without_website_marks_metadata_gap -q
```

Expected: fail because normalization function does not exist.

- [ ] **Step 3: Implement native item normalization**

Add to `company_native_last30days.py`:

```python
BLOCKED_COMPANY_DOMAINS = {
    "github.com",
    "news.ycombinator.com",
    "ycombinator.com",
    "hn.algolia.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "medium.com",
    "substack.com",
    "youtube.com",
    "youtu.be",
}


def normalize_last30days_native_item(item: dict, query: dict) -> dict:
    lane = query.get("lane", "")
    if lane == "launch_hn":
        return _normalize_hn_native_item(item, query)
    if lane == "yc_company":
        return _normalize_yc_native_item(item, query)
    return _rejected_native_item(item, query, ["unsupported_native_lane"])


def _normalize_hn_native_item(item: dict, query: dict) -> dict:
    title = item.get("title") or ""
    outbound_url = item.get("outbound_url") or item.get("resolved_url") or item.get("story_url") or item.get("url") or ""
    hn_url = item.get("hn_url") or item.get("source_url") or ""
    domain = _domain_from_url(outbound_url) or _normalize_domain(item.get("domain", ""))
    name = _name_from_hn_title(title)
    base = _base_native_item(item, query, name=name, source_url=hn_url or item.get("url", ""), official_url=outbound_url, domain=domain)
    if not title.lower().startswith(("show hn:", "launch hn:")):
        return {**base, "kind": "rejected", "verification_status": "rejected", "missing_evidence": ["not_launch_hn"]}
    if not outbound_url or not domain:
        return {**base, "kind": "rejected", "verification_status": "rejected", "missing_evidence": ["hn_outbound_url_missing"]}
    if _is_blocked_company_domain(domain):
        reason = "hn_outbound_github_project_only" if domain == "github.com" or domain.endswith(".github.com") else "hn_outbound_not_company_domain"
        return {**base, "kind": "project_only", "domain": "", "official_url": "", "verification_status": "rejected", "missing_evidence": [reason]}
    return {**base, "kind": "company_candidate", "verification_status": "accepted", "verification_basis": ["hn_launch_outbound_url"]}


def _normalize_yc_native_item(item: dict, query: dict) -> dict:
    source_url = item.get("url") or item.get("source_url") or ""
    website = item.get("website") or item.get("homepage") or item.get("outbound_url") or ""
    domain = _domain_from_url(website) or _normalize_domain(item.get("domain", ""))
    name = item.get("company_name") or _name_from_yc_title(item.get("title") or "")
    base = _base_native_item(item, query, name=name, source_url=source_url, official_url=website, domain=domain)
    if "ycombinator.com/companies" not in source_url:
        return {**base, "kind": "rejected", "verification_status": "rejected", "missing_evidence": ["not_yc_company_page"]}
    if not website or not domain or _is_blocked_company_domain(domain):
        return {**base, "kind": "needs_detail_enrichment", "domain": "", "verification_status": "rejected", "missing_evidence": ["yc_official_website_missing"]}
    return {**base, "kind": "company_candidate", "verification_status": "accepted", "verification_basis": ["yc_company_official_website"]}


def _base_native_item(item: dict, query: dict, *, name: str, source_url: str, official_url: str, domain: str) -> dict:
    engagement = item.get("engagement") or {}
    return {
        "name": name,
        "lane": query.get("lane", ""),
        "movement": query.get("movement", ""),
        "market_sector": query.get("market_sector", ""),
        "source_url": source_url,
        "official_url": official_url,
        "domain": _normalize_domain(domain),
        "title": item.get("title", ""),
        "snippet": item.get("snippet") or item.get("description") or "",
        "author": item.get("author", ""),
        "points": engagement.get("points", 0),
        "comments": engagement.get("comments", 0),
        "founders": item.get("founders") or [],
        "batch": item.get("batch", ""),
        "query_id": query.get("id", ""),
        "query_topic": query.get("topic", ""),
        "verification_basis": [],
        "missing_evidence": [],
        "discovery_lane": "last30days_native_source_audit",
    }


def _rejected_native_item(item: dict, query: dict, missing: list[str]) -> dict:
    return {
        "name": item.get("title", ""),
        "lane": query.get("lane", ""),
        "movement": query.get("movement", ""),
        "market_sector": query.get("market_sector", ""),
        "source_url": item.get("url", ""),
        "domain": "",
        "kind": "rejected",
        "verification_status": "rejected",
        "missing_evidence": missing,
    }


def _domain_from_url(url: str) -> str:
    return _normalize_domain(urlparse(url or "").netloc)


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith(("http://", "https://")):
        raw = urlparse(raw).netloc
    raw = raw.lower().strip("/")
    return raw[4:] if raw.startswith("www.") else raw


def _is_blocked_company_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in BLOCKED_COMPANY_DOMAINS)


def _name_from_hn_title(title: str) -> str:
    cleaned = (title or "").strip()
    for prefix in ("Show HN:", "Launch HN:"):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
    for separator in (" - ", " – ", " — ", ": "):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0].strip()
            break
    return cleaned[:80]


def _name_from_yc_title(title: str) -> str:
    return (title or "").split("|", 1)[0].strip()[:80]
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/company_native_last30days.py .claude/skills/vc-signals/tests/test_company_native_last30days.py
git commit -m "Normalize last30days-native source leads"
```

---

## Task 4: Optional Lightweight YC Detail Parser

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/company_native_last30days.py`
- Modify: `.claude/skills/vc-signals/tests/test_company_native_last30days.py`

Only implement this task if Task 6 audit shows YC last30days output lacks `website`, `homepage`, `outbound_url`, founder, or batch fields.

- [ ] **Step 1: Write failing tests**

Add:

```python
from company_native_last30days import parse_yc_company_detail


def test_parse_yc_company_detail_extracts_website_founders_batch_and_description():
    html = """
    <html>
      <head>
        <title>ShieldAgent | Y Combinator</title>
        <meta name="description" content="AI agent security platform for enterprise tool permissions.">
      </head>
      <body>
        <a href="https://shieldagent.ai">https://shieldagent.ai</a>
        <span>W26</span>
        <div>Founders</div>
        <div>Jane Doe</div>
        <div>Max Roe</div>
      </body>
    </html>
    """

    detail = parse_yc_company_detail(html, "https://www.ycombinator.com/companies/shieldagent")

    assert detail["company_name"] == "ShieldAgent"
    assert detail["website"] == "https://shieldagent.ai"
    assert "Jane Doe" in detail["founders"]
    assert "Max Roe" in detail["founders"]
    assert detail["batch"] == "W26"
    assert "AI agent security" in detail["description"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py::test_parse_yc_company_detail_extracts_website_founders_batch_and_description -q
```

Expected: fail because `parse_yc_company_detail` does not exist.

- [ ] **Step 3: Implement compact parser**

Add a capped parser that extracts only metadata, not full page bodies:

```python
import html as html_lib
import re
from html.parser import HTMLParser


class _YCCompanyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.links: list[str] = []
        self.texts: list[str] = []
        self._tag = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._tag = "title"
            self._buffer = []
        elif tag in {"div", "span", "p", "a"}:
            self._tag = tag
            self._buffer = []
            if tag == "a" and attr.get("href"):
                self.links.append(attr["href"])
        elif tag == "meta":
            key = (attr.get("name") or attr.get("property") or "").lower()
            content = attr.get("content") or ""
            if key in {"description", "og:description"} and content:
                self.description = html_lib.unescape(content).strip()[:500]

    def handle_data(self, data):
        if self._tag:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag != self._tag:
            return
        text = html_lib.unescape(" ".join(self._buffer)).strip()
        if tag == "title" and text:
            self.title = text[:200]
        elif text:
            self.texts.append(text[:200])
        self._tag = ""
        self._buffer = []


def parse_yc_company_detail(html: str, url: str) -> dict:
    parser = _YCCompanyParser()
    parser.feed((html or "")[:200_000])
    company_name = _name_from_yc_title(parser.title) or url.rstrip("/").split("/")[-1].replace("-", " ").title()
    website = ""
    for link in parser.links:
        domain = _domain_from_url(link)
        if domain and not _is_blocked_company_domain(domain):
            website = link
            break
    text_blob = " ".join(parser.texts)
    batch_match = re.search(r"\b([WS]\d{2})\b", text_blob)
    founders = []
    if "Founders" in text_blob:
        after = text_blob.split("Founders", 1)[1]
        for name in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b", after):
            if name not in founders and name not in {"Y Combinator"}:
                founders.append(name)
            if len(founders) >= 4:
                break
    return {
        "company_name": company_name,
        "website": website,
        "founders": founders,
        "batch": batch_match.group(1) if batch_match else "",
        "description": parser.description,
    }
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/company_native_last30days.py .claude/skills/vc-signals/tests/test_company_native_last30days.py
git commit -m "Add lightweight YC company detail parser"
```

---

## Task 5: Audit Metrics And Baseline Context

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/company_native_last30days.py`
- Modify: `.claude/skills/vc-signals/tests/test_company_native_last30days.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
from company_native_last30days import build_native_audit_metrics


def test_build_native_audit_metrics_counts_normalized_leads_without_quality_claims():
    leads = [
        {
            "kind": "company_candidate",
            "lane": "launch_hn",
            "domain": "burrow.security",
        },
        {
            "kind": "project_only",
            "lane": "launch_hn",
            "domain": "",
            "missing_evidence": ["hn_outbound_github_project_only"],
        },
        {
            "kind": "company_candidate",
            "lane": "yc_company",
            "domain": "shieldagent.ai",
        },
        {
            "kind": "needs_detail_enrichment",
            "lane": "yc_company",
            "domain": "",
            "missing_evidence": ["yc_official_website_missing"],
        },
    ]

    metrics = build_native_audit_metrics(leads, items_seen=20)

    assert metrics["company_candidates"] == 2
    assert metrics["unique_candidate_domains"] == 2
    assert metrics["candidate_domain_list"] == ["burrow.security", "shieldagent.ai"]
    assert metrics["project_only_leads"] == 1
    assert metrics["needs_detail_enrichment"] == 1
    assert metrics["candidate_domains_per_100_items"] == 10.0
    assert metrics["baseline_context"]["phase5_4_brave"]["verified_domains"] == 7
    assert "not directly comparable" in metrics["baseline_context"]["comparison_note"]
    assert "maturity_confirmed_early_stage" not in metrics
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py::test_build_native_audit_metrics_counts_normalized_leads_without_quality_claims -q
```

Expected: fail because `build_native_audit_metrics` does not exist.

- [ ] **Step 3: Implement metrics**

Add:

```python
PHASE5_4_BRAVE_BASELINE = {
    "verified_domains": 7,
    "maturity_confirmed_early_stage": 0,
    "research_worthy_unknown": 3,
    "category_or_monitor": 4,
    "assign_owner_rows": 0,
}


def build_native_audit_metrics(leads: list[dict], *, items_seen: int) -> dict:
    company_leads = [lead for lead in leads if lead.get("kind") == "company_candidate" and lead.get("domain")]
    domains = {lead["domain"] for lead in company_leads}
    by_lane = Counter(lead.get("lane", "unknown") for lead in leads)
    candidate_domains_by_lane: dict[str, set[str]] = {}
    for lead in company_leads:
        candidate_domains_by_lane.setdefault(lead.get("lane", "unknown"), set()).add(lead["domain"])
    summary = {
        "items_seen": items_seen,
        "company_candidates": len(company_leads),
        "unique_candidate_domains": len(domains),
        "candidate_domain_list": sorted(domains),
        "project_only_leads": len([lead for lead in leads if lead.get("kind") == "project_only"]),
        "needs_detail_enrichment": len([lead for lead in leads if lead.get("kind") == "needs_detail_enrichment"]),
        "rejected_leads": len([lead for lead in leads if lead.get("kind") == "rejected"]),
        "candidate_domains_per_100_items": round((len(domains) / items_seen) * 100, 2) if items_seen else 0.0,
        "rows_by_lane": dict(sorted(by_lane.items())),
        "candidate_domains_by_lane": {
            lane: sorted(values) for lane, values in sorted(candidate_domains_by_lane.items())
        },
        "baseline_context": {
            "phase5_4_brave": PHASE5_4_BRAVE_BASELINE,
            "comparison_note": "Phase 6A audit metrics are not directly comparable to Phase 5.4 quality metrics until Phase 6B gates run.",
        },
    }
    return summary
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/company_native_last30days.py .claude/skills/vc-signals/tests/test_company_native_last30days.py
git commit -m "Add native source audit metrics"
```

---

## Task 6: Audit Runner And Artifact Writer

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/company_native_last30days.py`
- Modify: `.claude/skills/vc-signals/tests/test_company_native_last30days.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
import json
from pathlib import Path

from company_native_last30days import run_last30days_native_audit, write_last30days_native_artifacts


def test_run_last30days_native_audit_calls_adapter_with_source_specific_queries(tmp_path):
    queries = [
        {
            "id": "phase6:launch_hn:1",
            "lane": "launch_hn",
            "topic": "Show HN AI agent security",
            "sources": "hackernews",
            "movement": "AI agent security",
            "market_sector": "Cybersecurity",
            "lookback_days": 30,
        }
    ]
    calls = []

    def fake_run_query(**kwargs):
        calls.append(kwargs)
        return {
            "items": [
                {
                    "source": "hackernews",
                    "title": "Show HN: Burrow - Runtime Security for AI Agents",
                    "url": "https://burrow.security",
                    "hn_url": "https://news.ycombinator.com/item?id=47761957",
                    "domain": "burrow.security",
                }
            ],
            "warnings": [],
            "errors_by_source": {},
        }

    result = run_last30days_native_audit(queries, run_query_fn=fake_run_query, output_dir=tmp_path)

    assert calls[0]["topic"] == "Show HN AI agent security"
    assert calls[0]["sources"] == "hackernews"
    assert calls[0]["store"] is True
    assert result["audit"]["summary"]["items_seen"] == 1
    assert result["normalized_leads"]["summary"]["unique_candidate_domains"] == 1


def test_write_last30days_native_artifacts_does_not_touch_weekly_preview(tmp_path):
    payload = {
        "audit": {"summary": {"items_seen": 1}, "rows": []},
        "normalized_leads": {
            "summary": {"unique_candidate_domains": 1},
            "company_candidates": [],
            "project_only_leads": [],
        },
    }

    paths = write_last30days_native_artifacts(payload, tmp_path)

    assert tmp_path.joinpath("company-native-source-audit.json") in paths
    assert tmp_path.joinpath("company-native-normalized-leads.json") in paths
    assert tmp_path.joinpath("company-native-source-audit.md") in paths
    assert not tmp_path.joinpath("weekly-preview.md").exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py::test_run_last30days_native_audit_calls_adapter_with_source_specific_queries .claude/skills/vc-signals/tests/test_company_native_last30days.py::test_write_last30days_native_artifacts_does_not_touch_weekly_preview -q
```

Expected: fail because runner/writer functions do not exist.

- [ ] **Step 3: Implement audit runner**

Add:

```python
import json


def run_last30days_native_audit(
    queries: list[dict],
    *,
    run_query_fn,
    output_dir: Path | str | None = None,
    timeout_seconds: int = 120,
) -> dict:
    query_payloads = []
    normalized_leads = []
    raw_dir = Path(output_dir) / "raw-last30days" if output_dir else None
    if raw_dir:
        raw_dir.mkdir(parents=True, exist_ok=True)
    for query in queries:
        payload = run_query_fn(
            topic=query["topic"],
            sources=query["sources"],
            lookback_days=query.get("lookback_days", 30),
            emit="json",
            auto_resolve=True,
            store=True,
            web_backend=query.get("web_backend") or "auto",
            timeout_seconds=timeout_seconds,
        )
        query_payloads.append((query, payload))
        if raw_dir:
            raw_dir.joinpath(f"{query['id'].replace(':', '-')}.json").write_text(json.dumps(payload, indent=2))
        for item in payload.get("items", []) or []:
            normalized_leads.append(normalize_last30days_native_item(item, query))
    audit = summarize_last30days_native_audit(query_payloads)
    audit_summary = build_native_audit_metrics(normalized_leads, items_seen=sum(len(payload.get("items", []) or []) for _query, payload in query_payloads))
    return {
        "audit": audit,
        "normalized_leads": {
            "summary": audit_summary,
            "company_candidates": [lead for lead in normalized_leads if lead.get("kind") == "company_candidate"],
            "project_only_leads": [lead for lead in normalized_leads if lead.get("kind") == "project_only"],
            "needs_detail_enrichment": [lead for lead in normalized_leads if lead.get("kind") == "needs_detail_enrichment"],
            "rejected_leads": [lead for lead in normalized_leads if lead.get("kind") == "rejected"],
        },
    }
```

- [ ] **Step 4: Implement artifact writer**

Add:

```python
def write_last30days_native_artifacts(payload: dict, output_dir: Path | str) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    audit_path = path / "company-native-source-audit.json"
    normalized_path = path / "company-native-normalized-leads.json"
    md_path = path / "company-native-source-audit.md"
    audit_path.write_text(json.dumps(payload.get("audit", {}), indent=2))
    normalized_path.write_text(json.dumps(payload.get("normalized_leads", {}), indent=2))
    md_path.write_text(_native_audit_markdown(payload))
    return [audit_path, normalized_path, md_path]


def _native_audit_markdown(payload: dict) -> str:
    summary = payload.get("normalized_leads", {}).get("summary", {})
    baseline = summary.get("baseline_context", {})
    lines = [
        "# last30days-Native Source Audit",
        "",
        "Phase 6A audit only. Retrieval uses last30days; vc-signals normalizes source-native items but does not run maturity, owner-readiness, Attio, or action gates in this phase.",
        "",
        f"- Items seen: {summary.get('items_seen', 0)}",
        f"- Company candidates: {summary.get('company_candidates', 0)}",
        f"- Unique candidate domains: {summary.get('unique_candidate_domains', 0)}",
        f"- Project-only leads: {summary.get('project_only_leads', 0)}",
        f"- Needs detail enrichment: {summary.get('needs_detail_enrichment', 0)}",
        f"- Rejected leads: {summary.get('rejected_leads', 0)}",
        f"- Candidate domains per 100 items: {summary.get('candidate_domains_per_100_items', 0)}",
        "",
        "## Baseline Context",
        "",
        baseline.get("comparison_note", "Phase 6A audit metrics are not directly comparable to Phase 5.4 quality metrics until Phase 6B gates run."),
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/scripts/company_native_last30days.py .claude/skills/vc-signals/tests/test_company_native_last30days.py
git commit -m "Add last30days-native source audit artifact"
```

---

## Task 7: CLI And Real Audit Run

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/company_native_last30days.py`
- Modify: `.claude/skills/vc-signals/tests/test_company_native_last30days.py`
- Generated only under `docs/radar-runs/current-phase6-last30days-native-audit/`

- [ ] **Step 1: Add CLI**

Append:

```python
import argparse
from last30days_adapter import run_query as last30days_run_query


def _load_movements_from_weekly_run(weekly_run_dir: Path | str) -> list[dict]:
    path = Path(weekly_run_dir) / "weekly-focus.json"
    payload = json.loads(path.read_text())
    movements = []
    for row in payload.get("market_movements", []) or []:
        movement = row.get("movement") or row.get("name") or ""
        if movement:
            movements.append({"movement": movement, "market_sector": row.get("market_sector", ""), "origin_row_ids": row.get("origin_row_ids", [])})
    for row in payload.get("research_deeper", []) or []:
        movement = row.get("market_movement") or ""
        if movement and movement not in {item["movement"] for item in movements}:
            movements.append({"movement": movement, "market_sector": row.get("market_sector", ""), "origin_row_ids": [row.get("id", "")]})
    return movements


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly-run-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--lanes", default="launch_hn,yc_company")
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    movements = _load_movements_from_weekly_run(args.weekly_run_dir)
    queries = build_last30days_native_queries(
        movements,
        lanes=tuple(item.strip() for item in args.lanes.split(",") if item.strip()),
        lookback_days=args.lookback_days,
    )
    payload = run_last30days_native_audit(
        queries,
        run_query_fn=last30days_run_query,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
    )
    write_last30days_native_artifacts(payload, args.output_dir)
    print(json.dumps(payload["normalized_leads"]["summary"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_company_native_last30days.py -q
```

Expected: pass.

- [ ] **Step 3: Run full suite**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: full suite passes.

- [ ] **Step 4: Run real Phase 6 audit**

Use the corrected weekly-trial run as input:

```bash
rm -rf docs/radar-runs/current-phase6-last30days-native-audit
python3 .claude/skills/vc-signals/scripts/company_native_last30days.py \
  --weekly-run-dir docs/radar-runs/current-phase5-3-1-controlled-weekly-trial-full-v2 \
  --output-dir docs/radar-runs/current-phase6-last30days-native-audit \
  --lanes launch_hn,yc_company \
  --lookback-days 30 \
  --timeout-seconds 120
```

Expected:
- `company-native-source-audit.json` exists.
- `company-native-normalized-leads.json` exists.
- `company-native-source-audit.md` exists.
- `weekly-preview.md` remains unchanged.
- Generated artifacts/cache are uncommitted.

- [ ] **Step 5: Inspect review package**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

base = Path("docs/radar-runs/current-phase6-last30days-native-audit")
audit = json.loads((base / "company-native-source-audit.json").read_text())
normalized = json.loads((base / "company-native-normalized-leads.json").read_text())
print("AUDIT")
print(json.dumps(audit["summary"], indent=2))
print("\nNORMALIZED")
print(json.dumps(normalized["summary"], indent=2))
print("\nCOMPANY CANDIDATES")
for row in normalized.get("company_candidates", []):
    print(json.dumps({
        "name": row.get("name"),
        "lane": row.get("lane"),
        "domain": row.get("domain"),
        "source_url": row.get("source_url"),
        "official_url": row.get("official_url"),
        "verification_basis": row.get("verification_basis"),
    }, indent=2))
print("\nPROJECT ONLY")
for row in normalized.get("project_only_leads", []):
    print(json.dumps({
        "name": row.get("name"),
        "lane": row.get("lane"),
        "source_url": row.get("source_url"),
        "missing_evidence": row.get("missing_evidence"),
    }, indent=2))
print("\nNEEDS DETAIL")
for row in normalized.get("needs_detail_enrichment", [])[:20]:
    print(json.dumps({
        "name": row.get("name"),
        "lane": row.get("lane"),
        "source_url": row.get("source_url"),
        "missing_evidence": row.get("missing_evidence"),
    }, indent=2))
print("\nREJECTED")
for row in normalized.get("rejected_leads", [])[:20]:
    print(json.dumps({
        "name": row.get("name"),
        "lane": row.get("lane"),
        "source_url": row.get("source_url"),
        "missing_evidence": row.get("missing_evidence"),
    }, indent=2))
PY
```

- [ ] **Step 6: Check protected outputs**

Run:

```bash
git diff -- docs/radar-runs/current/weekly-preview.md
git status --short --untracked-files=no
```

Expected:
- No diff for `weekly-preview.md`.
- No tracked modified files after commits.
- Generated artifact directories appear only as untracked files when using normal `git status --short`.

---

## Definition Of Done

- Phase 6 plan no longer rebuilds last30days retrieval.
- Source-specific HN and YC queries run through `last30days_adapter.run_query()`.
- Audit artifact reports raw/normalized field presence for:
  - `url`
  - `hn_url`
  - `outbound_url`
  - `domain`
  - `homepage` / `website`
  - `author`
  - `engagement`
  - founder/batch fields when present
- HN outbound company domains become candidate leads only if source-backed and non-blocked.
- HN outbound GitHub/project links become project-only leads.
- YC rows are accepted only if official website/domain is present, or marked as needing detail enrichment.
- Phase 5.4 Brave baseline context is included in JSON and markdown with a warning that Phase 6A is not directly comparable until Phase 6B gates run.
- Phase 6A artifacts do not report credible early-stage leads, sourcing candidates, `Assign owner`, `New To Marathon`, or provider graduation recommendations.
- Full tests pass.
- `weekly-preview.md` unchanged.
- Generated artifacts and raw last30days outputs uncommitted.

---

## Execution Recommendation

Execute in this order:

1. Task 1: create the last30days-native query/audit model.
2. Task 1.5: add the no-direct-retrieval boundary guard.
3. Task 2: patch adapter preservation if needed.
4. Task 3: normalize HN/YC last30days-native items.
5. Task 5: build audit metrics and baseline context.
6. Task 6/7: run a real Phase 6A audit before building YC detail parsing.
7. Only execute Task 4 if the real audit proves YC metadata is missing.
8. Write a Phase 6B plan only after reviewing the audit output.

This avoids rebuilding source retrieval and keeps `vc-signals` focused on Marathon-specific intelligence.
