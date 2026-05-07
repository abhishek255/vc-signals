# Controlled Company Discovery And Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn market movements and unresolved research rows into source-backed company/project leads without broad/vibe-based discovery.

**Architecture:** Add a controlled discovery layer that builds movement-specific queries from current `ThemeSignal`, `FocusItem`, and unresolved candidate rows, runs only configured grounded/company-web retrieval, verifies each returned item against strict company/domain/founder evidence rules, and feeds verified leads back through the existing `Signal -> Candidate -> IdentityResolution -> weekly-focus` pipeline. GitHub-only rows remain project rows unless separate source-backed company proof exists.

**Tech Stack:** Python dataclasses, existing `last30days_adapter.run_query`, existing `radar_models`, `radar_company_discovery.py`, `radar_run.py`, `identity_resolution.py`, pytest.

---

## Product Contract

Phase 3 is **Controlled Company Discovery And Verification**. It is not broad source expansion.

The system must answer:

> For the movements and unresolved rows we already found, are there source-backed companies or projects forming around this movement, and are they strong enough to enter Marathon workflow?

### In Scope

- Start from current market movements, theme signals, `Needs More Evidence`, and filtered/noisy rows.
- Generate movement-specific company discovery queries.
- Use grounded/company web only when configured.
- Allow existing HN launch evidence only as a launch-verification fallback, not as broad discovery.
- Require source-backed company/domain/founder/project proof.
- Feed accepted discovery results into `IdentityResolution`.
- Keep GitHub-only rows as project rows unless company proof exists from non-GitHub evidence.
- Upgrade actions only when identity and Attio-safe gates pass.
- Produce an enriched `company-discovery.json` artifact with queries, accepted leads, rejected leads, and verification basis.
- Keep `weekly-preview.md` unchanged in behavior and path.
- Add tests preventing broad/vibe-based discovery.

### Explicitly Out Of Scope

- X / LinkedIn scraping / Product Hunt / package registries.
- Broad web search not tied to a movement or unresolved row.
- Domain guessing from company names.
- LLM-only company creation.
- Attio writeback.
- Slack delivery.
- Changing `weekly-preview.md` format beyond already-existing company discovery section consuming the same artifact key.

---

## File Structure

### Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
Add two focused models:

```python
@dataclass
class DiscoveryQuery:
    id: str
    movement: str
    market_sector: str
    source_reason: str = ""
    topic: str = ""
    sources: str = "grounding"
    lookback_days: int = 30
    web_backend: str = "auto"
    candidate_eligible: bool = True
    origin_row_ids: list[str] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)
    limited: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "DiscoveryQuery":
        return cls(**_known_payload(cls, payload))


@dataclass
class VerifiedCompanyDiscoveryLead:
    name: str
    movement: str
    market_sector: str
    source_url: str
    source: str = ""
    domain: str = ""
    founder_or_maintainer: str = ""
    candidate_type: str = "launch_style_needs_identity"
    verification_status: str = "rejected"
    verification_basis: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    movement_assignment_basis: list[str] = field(default_factory=list)
    query_id: str = ""
    query_topic: str = ""
    why_on_radar: str = ""
    why_this_may_be_noise: str = ""
    raw_title: str = ""
    raw_snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "VerifiedCompanyDiscoveryLead":
        return cls(**_known_payload(cls, payload))
```

### Modify: `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
Responsibilities after Phase 3:

- Build discovery seeds from `ThemeSignal` plus optional `FocusItem`/`Candidate` unresolved rows.
- Generate movement-specific queries.
- Refuse broad/vibe queries.
- Verify returned items into `VerifiedCompanyDiscoveryLead`.
- Return a rich artifact:

```json
{
  "queries": [],
  "items": [],
  "accepted_leads": [],
  "rejected_leads": [],
  "warnings": [],
  "errors": [],
  "summary": {
    "queries_run": 0,
    "accepted": 0,
    "rejected": 0,
    "grounded_available": false
  }
}
```

For backward compatibility, `items` should contain accepted leads converted to existing evidence item dictionaries so `radar_run.build_signals_from_evidence()` can promote them.

### Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
Responsibilities:

- Build initial signals/theme signals as today.
- Promote and score initial candidates as today.
- Build a provisional focus artifact or focus items from scored candidates so discovery can see `Needs More Evidence` / filtered rows without writing artifacts yet.
- Call `collect_company_discovery(theme_signals, unresolved_candidates=..., focus_items=...)`.
- Add accepted discovery items back into `evidence["company_discovery"]`.
- Rebuild signals and candidates as today.
- Feed final candidates into identity resolution as today.
- Continue writing `company-discovery.json` at the same path.
- Keep `weekly-preview.md` unchanged.

### Modify: `.claude/skills/vc-signals/scripts/identity_resolution.py`
No broad changes. Add tests proving accepted discovery leads are still subject to existing `verified_company`, `launch_style_needs_identity`, `oss_project_watch`, `attio_safe_to_match`, and action gates.

### Modify Tests

- `.claude/skills/vc-signals/tests/test_radar_company_discovery.py`
- `.claude/skills/vc-signals/tests/test_radar_run.py`
- `.claude/skills/vc-signals/tests/test_identity_resolution.py`
- `.claude/skills/vc-signals/tests/test_radar_focus.py`

---

## Verification Rules

### Discovery Query Rules

A query is allowed only if all are true:

- It is derived from a known movement/theme/unresolved row.
- It contains specific movement/problem terms, not just generic sector words. Query eligibility must require at least two movement terms or one high-specificity movement phrase.
- It contains at least one company-intent term: `startup`, `company`, `founder`, `launch`, `seed`, `YC`, `raises`, `website`.
- It has a `source_reason` explaining whether it came from theme signal, partner focus row, needs-more-evidence row, filtered row, or identity-resolution target.
- It is run only when `grounded_available=True`.

Unresolved-row queries are allowed only when the row is evidence-backed, non-generic, non-noisy, and still missing company/founder/domain proof. Weak names, unclassified movements, monitor-only rows, filtered/noisy rows, and obvious generic OSS/template/tutorial rows must not generate discovery queries.

When `grounded_available=False`, the artifact should record skipped/limited queries and should not run broad HN/social discovery for company rows. The summary must report `queries_run: 0`, `accepted: 0`, `rejected: 0`, and `grounded_available: false`.

### Accepted Lead Rules

A returned item can become an accepted discovery lead only if all are true:

- It has a non-empty `source_url`.
- It has a `name` or `company_name`.
- It has at least one identity proof:
  - source-backed domain from company URL or structured `domain`, or
  - HN launch source with outbound domain already captured, or
  - founder/maintainer evidence from source metadata, or
  - non-GitHub company page/source with company name and domain.
- It has movement assignment proof:
  - title/snippet/domain/source metadata includes at least two movement terms, or
  - title/snippet/source metadata includes one high-specificity phrase such as `AI agent`, `agent security`, `MCP`, `tool permissions`, `runtime security`, or `agent permissions`, or
  - query was movement-specific and returned title/snippet matches required terms.
- It is not GitHub-only unless separate company proof exists outside GitHub.
- It does not use a content/community platform as the verified company domain. Blocked company-domain platforms are `github.com`, `news.ycombinator.com`, `medium.com`, `substack.com`, `youtube.com`, `x.com`, `twitter.com`, `linkedin.com`, `reddit.com`, `docs.google.com`, and `notion.site`. These may be evidence URLs, not verified company domains.

Rejected leads must include `missing_evidence` and `verification_basis` explaining why.

### Action Upgrade Rules

Do not set `Assign owner` or `Refresh Attio` inside discovery. Discovery only creates evidence. Existing identity/focus gates decide actions later.

A row can become `Assign owner` only if later identity resolution says:

- `identity_type == "verified_company"`
- `attio_safe_to_match is True`
- source-backed domain exists
- `attio_status in {"no_match", "not_found", "new", "no_owner"}`
- focus action gates pass

---

## Task 1: Add Discovery Models

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_models.py`

- [ ] **Step 1: Write model round-trip tests**

Add to `.claude/skills/vc-signals/tests/test_radar_models.py`:

```python
def test_discovery_query_roundtrip():
    from radar_models import DiscoveryQuery

    query = DiscoveryQuery(
        id="ai-agent-security-theme-company-search",
        movement="AI agent security",
        market_sector="Cybersecurity",
        source_reason="theme_signal",
        topic="AI agent security startup company founder launch",
        sources="grounding",
        required_terms=["agent", "security"],
        origin_row_ids=["theme:ai-agent-security"],
    )

    assert DiscoveryQuery.from_dict(query.to_dict()) == query


def test_verified_company_discovery_lead_roundtrip():
    from radar_models import VerifiedCompanyDiscoveryLead

    lead = VerifiedCompanyDiscoveryLead(
        name="AgentFence",
        movement="AI agent security",
        market_sector="Cybersecurity",
        source_url="https://agentfence.dev",
        source="grounding",
        domain="agentfence.dev",
        candidate_type="verified_company",
        verification_status="accepted",
        verification_basis=["source_backed_domain", "movement_terms_present"],
        movement_assignment_basis=["title_matches_movement"],
        query_id="ai-agent-security-theme-company-search",
        query_topic="AI agent security startup company founder launch",
    )

    assert VerifiedCompanyDiscoveryLead.from_dict(lead.to_dict()) == lead
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py::test_discovery_query_roundtrip .claude/skills/vc-signals/tests/test_radar_models.py::test_verified_company_discovery_lead_roundtrip -q
```

Expected: fail because the classes do not exist.

- [ ] **Step 3: Implement models**

Add the `DiscoveryQuery` and `VerifiedCompanyDiscoveryLead` dataclasses to `.claude/skills/vc-signals/scripts/radar_models.py` after `ThemeSignal`.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py::test_discovery_query_roundtrip .claude/skills/vc-signals/tests/test_radar_models.py::test_verified_company_discovery_lead_roundtrip -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/tests/test_radar_models.py
git commit -m "Add controlled discovery models"
```

---

## Task 2: Build Movement-Specific Discovery Seeds And Queries

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_company_discovery.py`

- [ ] **Step 1: Add query tests**

Add tests:

```python
def test_build_company_discovery_queries_uses_theme_and_unresolved_rows():
    from radar_company_discovery import build_company_discovery_queries
    from radar_models import Candidate, FocusItem

    theme = _theme_signal()
    focus = FocusItem(
        id="burrow",
        name="Burrow",
        market_movement="AI agent security",
        market_sector="Cybersecurity",
        missing_evidence=["no verified domain", "no founder or maintainer identity"],
        evidence_urls=["https://news.ycombinator.com/item?id=47761957"],
        recommended_action="Research deeper",
    )
    candidate = Candidate(
        name="Burrow",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=47761957",
        candidate_type="company_web",
        stable_key="burrow",
        why_on_radar="Show HN: Burrow - Runtime Security for AI Agents",
        sources=["https://news.ycombinator.com/item?id=47761957"],
        missing_identity_evidence=["no verified domain"],
    )

    queries = build_company_discovery_queries(
        [theme],
        focus_items=[focus],
        unresolved_candidates=[candidate],
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=2,
    )

    assert queries
    assert all(query["sources"] == "grounding" for query in queries)
    assert all(query["source_reason"] in {"theme_signal", "needs_more_evidence", "identity_resolution_target"} for query in queries)
    assert all("AI agent security" in query["movement"] for query in queries)
    assert all(any(term in query["topic"].lower() for term in ["startup", "company", "founder", "launch", "yc", "seed"]) for query in queries)


def test_build_company_discovery_queries_refuses_broad_vibe_queries():
    from radar_company_discovery import build_company_discovery_queries
    from radar_models import ThemeSignal

    broad = ThemeSignal(
        market_sector="AI Infra",
        theme="AI",
        evidence_summary="Generic AI chatter.",
        suggested_search="AI startups",
    )

    queries = build_company_discovery_queries(
        [broad],
        grounded_available=True,
        social_available=False,
    )

    assert queries == []


def test_build_company_discovery_queries_skips_execution_without_grounding():
    from radar_company_discovery import build_company_discovery_queries

    queries = build_company_discovery_queries([_theme_signal()], grounded_available=False, social_available=False)

    assert queries
    assert all(query["limited"] is True for query in queries)
    assert all(query["sources"] == "" for query in queries)
    assert "grounded company discovery unavailable" in queries[0]["reason"].lower()


def test_weak_unclassified_row_does_not_generate_discovery_query():
    from radar_company_discovery import build_company_discovery_queries
    from radar_models import FocusItem

    weak = FocusItem(
        id="bearcove-vixen",
        name="bearcove/vixen",
        market_movement="Unclassified technical tooling",
        market_sector="Unclassified",
        missing_evidence=["no verified domain"],
        evidence_urls=["https://github.com/bearcove/vixen"],
        recommended_action="Research deeper",
        noise_risk_score=75,
    )

    queries = build_company_discovery_queries(
        [],
        focus_items=[weak],
        unresolved_candidates=[],
        grounded_available=True,
        social_available=False,
    )

    assert queries == []
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py -q
```

Expected: fail because `focus_items`, `unresolved_candidates`, `source_reason`, `movement`, strict source selection, and broad-query refusal are not implemented.

- [ ] **Step 3: Implement query construction**

In `.claude/skills/vc-signals/scripts/radar_company_discovery.py`:

- Import `Candidate`, `DiscoveryQuery`, `FocusItem`, `ThemeSignal`.
- Add constants:

```python
COMPANY_INTENT_TERMS = ("startup", "company", "founder", "launch", "seed", "yc", "raises", "website")
BROAD_THEMES = {"ai", "devtools", "cybersecurity", "data", "oss", "automation"}
GENERIC_MOVEMENTS = {"emerging technical signal", "unclassified technical tooling", "oss company-formation watchlist"}
IDENTITY_MISSING_TERMS = ("domain", "founder", "company", "identity")
NOISY_OSS_TERMS = ("template", "tutorial", "example", "demo", "boilerplate")
```

- Add helpers:

```python
def _movement_terms(text: str) -> list[str]:
    normalized = (text or "").lower().replace("/", " ").replace("-", " ")
    stop = {"the", "and", "for", "with", "from", "this", "that", "tooling", "tools", "startup", "company"}
    return [token for token in normalized.split() if len(token) >= 3 and token not in stop]


def _is_broad_movement(movement: str) -> bool:
    terms = _movement_terms(movement)
    return not terms or (len(terms) == 1 and terms[0] in BROAD_THEMES)


def _query_is_specific(topic: str, required_terms: list[str]) -> bool:
    text = (topic or "").lower()
    return _movement_match_strength(text, required_terms)[0] and any(term in text for term in COMPANY_INTENT_TERMS)


def _movement_match_strength(text: str, required_terms: list[str]) -> tuple[bool, list[str]]:
    lowered = (text or "").lower()
    matched = [term for term in required_terms if term in lowered]
    if len(matched) >= 2:
        return True, [f"movement_terms_present:{','.join(matched)}"]
    strong_phrases = ("ai agent", "agent security", "mcp", "tool permissions", "runtime security", "agent permissions")
    strong = [phrase for phrase in strong_phrases if phrase in lowered]
    if strong:
        return True, [f"strong_movement_phrase:{strong[0]}"]
    return False, ["movement_terms_missing"]


def _focus_item_can_seed_query(item: FocusItem) -> bool:
    movement = (item.market_movement or "").lower()
    text = f"{item.name} {item.why_focus_this_week} {item.why_this_may_be_noise}".lower()
    missing = " ".join(item.missing_evidence).lower()
    return (
        item.recommended_action == "Research deeper"
        and bool(item.evidence_urls)
        and movement not in GENERIC_MOVEMENTS
        and any(term in missing for term in IDENTITY_MISSING_TERMS)
        and item.noise_risk_score < 70
        and not any(term in text for term in NOISY_OSS_TERMS)
    )


def _candidate_can_seed_query(candidate: Candidate) -> bool:
    name = (candidate.name or "").strip()
    theme = (candidate.theme or "").lower()
    text = f"{candidate.name} {candidate.why_on_radar} {candidate.why_this_may_be_noise}".lower()
    return (
        len(name) > 2
        and theme
        and theme not in GENERIC_MOVEMENTS
        and not _is_broad_movement(theme)
        and any(term in " ".join(candidate.missing_identity_evidence).lower() for term in IDENTITY_MISSING_TERMS)
        and not any(term in text for term in NOISY_OSS_TERMS)
    )
```

- Extend `build_company_discovery_queries` signature:

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
) -> list[dict]:
```

- When `grounded_available=True`, use `sources="grounding"` only. Do not use HN/social as company-discovery sources in Phase 3.
- When `grounded_available=False`, return limited query records with `sources=""`, `limited=True`, and do not execute them.
- Build queries from:
  - each non-broad `ThemeSignal`
  - each `FocusItem` that passes `_focus_item_can_seed_query`
  - each unresolved `Candidate` that passes `_candidate_can_seed_query`
- Deduplicate by normalized topic.
- Return `DiscoveryQuery.to_dict()` objects.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py -q
```

Expected: all company discovery tests pass after updating existing assertions from `grounding,hackernews,youtube` to `grounding` where needed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_company_discovery.py .claude/skills/vc-signals/tests/test_radar_company_discovery.py
git commit -m "Build controlled company discovery queries"
```

---

## Task 3: Verify Discovery Results Before Promotion

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_company_discovery.py`

- [ ] **Step 1: Add verification tests**

Add tests:

```python
def test_verify_discovery_item_accepts_source_backed_company_domain():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "AgentFence launches AI agent permission firewall",
        "url": "https://agentfence.dev",
        "snippet": "AgentFence helps security teams control AI agent tool permissions.",
        "company_name": "AgentFence",
        "domain": "agentfence.dev",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "accepted"
    assert lead.name == "AgentFence"
    assert lead.domain == "agentfence.dev"
    assert lead.candidate_type == "verified_company"
    assert "source_backed_domain" in lead.verification_basis
    assert "movement_terms_present" in lead.movement_assignment_basis


def test_verify_discovery_item_rejects_vibe_match_without_movement_terms():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "New devtools company launches",
        "url": "https://generic.dev",
        "snippet": "A generic developer productivity platform.",
        "company_name": "GenericDev",
        "domain": "generic.dev",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "movement_terms_missing" in lead.missing_evidence


def test_verify_discovery_item_rejects_single_generic_term_match():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["ai", "agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "Security startup launches",
        "url": "https://genericsecurity.dev",
        "snippet": "A security platform for developer teams.",
        "company_name": "GenericSecurity",
        "domain": "genericsecurity.dev",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "movement_terms_missing" in lead.missing_evidence


def test_verify_discovery_item_rejects_content_platform_domain():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "AgentFence discusses AI agent security",
        "url": "https://medium.com/@agentfence/ai-agent-security",
        "snippet": "AgentFence discusses AI agent security and MCP permissions.",
        "company_name": "AgentFence",
        "domain": "medium.com",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "content_platform_not_company_domain" in lead.missing_evidence


def test_verify_discovery_item_rejects_github_only_company_proof():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "needs_more_evidence",
    }
    item = {
        "source": "github",
        "title": "affaan-m/agentshield",
        "url": "https://github.com/affaan-m/agentshield",
        "snippet": "AI agent security scanner for MCP permissions.",
        "company_name": "AgentShield",
        "domain": "cerebralvalley.ai",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "github_only_not_company_proof" in lead.missing_evidence
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py::test_verify_discovery_item_accepts_source_backed_company_domain .claude/skills/vc-signals/tests/test_radar_company_discovery.py::test_verify_discovery_item_rejects_vibe_match_without_movement_terms .claude/skills/vc-signals/tests/test_radar_company_discovery.py::test_verify_discovery_item_rejects_github_only_company_proof -q
```

Expected: fail because `verify_discovery_item` does not exist.

- [ ] **Step 3: Implement verification**

Add to `radar_company_discovery.py`:

```python
CONTENT_PLATFORM_DOMAINS = {
    "github.com",
    "news.ycombinator.com",
    "medium.com",
    "substack.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "reddit.com",
    "docs.google.com",
    "notion.site",
}


def verify_discovery_item(item: dict, query: dict) -> VerifiedCompanyDiscoveryLead:
    source_url = item.get("url") or item.get("source_url") or ""
    source = (item.get("source") or "").lower()
    title = item.get("title") or ""
    snippet = item.get("snippet") or item.get("description") or ""
    name = item.get("company_name") or item.get("name") or title
    domain = _normalize_domain(item.get("domain") or item.get("website") or _domain_from_url(source_url))
    required_terms = query.get("required_terms") or _movement_terms(query.get("movement", ""))

    basis = []
    missing = []
    movement_basis = []
    combined_text = f"{title} {snippet} {name} {domain}".lower()

    if not source_url:
        missing.append("no_source_url")
    if not name:
        missing.append("no_company_name")
    if source == "github" or "github.com" in source_url:
        missing.append("github_only_not_company_proof")
    if domain in CONTENT_PLATFORM_DOMAINS or any(domain.endswith(f".{blocked}") for blocked in CONTENT_PLATFORM_DOMAINS):
        missing.append("content_platform_not_company_domain")
    if domain and source != "github" and "github.com" not in source_url and "content_platform_not_company_domain" not in missing:
        basis.append("source_backed_domain")
    else:
        missing.append("no_source_backed_domain")
    movement_ok, movement_reasons = _movement_match_strength(combined_text, required_terms)
    if movement_ok:
        movement_basis.extend(movement_reasons)
    else:
        missing.extend(movement_reasons)

    accepted = bool(source_url and name and basis and movement_basis and "github_only_not_company_proof" not in missing)
    return VerifiedCompanyDiscoveryLead(
        name=name,
        movement=query.get("movement", ""),
        market_sector=query.get("market_sector", ""),
        source_url=source_url,
        source=item.get("source", ""),
        domain=domain if accepted else "",
        founder_or_maintainer=item.get("founder") or item.get("author") or "",
        candidate_type="verified_company" if accepted and domain else "launch_style_needs_identity",
        verification_status="accepted" if accepted else "rejected",
        verification_basis=basis,
        missing_evidence=list(dict.fromkeys(missing)),
        movement_assignment_basis=movement_basis,
        query_id=query.get("id", ""),
        query_topic=query.get("topic", ""),
        why_on_radar=snippet or title,
        why_this_may_be_noise="Needs verification across stronger company/founder/customer evidence.",
        raw_title=title,
        raw_snippet=snippet,
    )
```

Also add `_normalize_domain` and `_domain_from_url` helpers locally or import equivalent helpers if already public. Prefer local private helpers to avoid coupling to `identity_resolution.py` internals.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_company_discovery.py .claude/skills/vc-signals/tests/test_radar_company_discovery.py
git commit -m "Verify controlled company discovery leads"
```

---

## Task 4: Return Rich `company-discovery.json` Artifact And Backward-Compatible Items

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_company_discovery.py`

- [ ] **Step 1: Add collection artifact test**

Add:

```python
def test_collect_company_discovery_returns_accepted_and_rejected_leads():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev",
                    "snippet": "AgentFence helps security teams control AI agent tool permissions.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                },
                {
                    "source": "grounding",
                    "title": "Generic devtools company launches",
                    "url": "https://generic.dev",
                    "snippet": "A generic developer productivity platform.",
                    "company_name": "GenericDev",
                    "domain": "generic.dev",
                },
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert result["summary"]["accepted"] == 1
    assert result["summary"]["rejected"] == 1
    assert result["accepted_leads"][0]["name"] == "AgentFence"
    assert result["rejected_leads"][0]["name"] == "GenericDev"
    assert result["items"][0]["company_name"] == "AgentFence"
    assert result["items"][0]["domain"] == "agentfence.dev"
    assert result["items"][0]["discovery_verification_status"] == "accepted"
    assert result["items"][0]["signal_role"] == "launch"
    assert result["items"][0]["source_lane"] == "Grounded web"


def test_collect_company_discovery_without_grounding_is_artifact_only():
    from radar_company_discovery import collect_company_discovery

    def fail_query(topic, **kwargs):
        raise AssertionError("query runner should not execute without grounding")

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fail_query,
        grounded_available=False,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert result["queries"]
    assert result["items"] == []
    assert result["accepted_leads"] == []
    assert result["rejected_leads"] == []
    assert result["summary"]["queries_run"] == 0
    assert result["summary"]["accepted"] == 0
    assert result["summary"]["rejected"] == 0
    assert result["summary"]["grounded_available"] is False
    assert any("grounded company discovery unavailable" in warning.lower() for warning in result["warnings"])
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py::test_collect_company_discovery_returns_accepted_and_rejected_leads -q
```

Expected: fail because artifact shape is not implemented.

- [ ] **Step 3: Implement artifact shaping**

Update `collect_company_discovery`:

- Initialize `accepted_leads = []`, `rejected_leads = []`.
- For each returned item, call `verify_discovery_item(item, query)`.
- Add accepted leads to `accepted_leads` and backward-compatible `items`.
- Add rejected leads to `rejected_leads`.
- Convert accepted lead to item with:

```python
{
    "source": lead.source or "grounding",
    "title": lead.raw_title or lead.name,
    "url": lead.source_url,
    "snippet": lead.why_on_radar,
    "company_name": lead.name,
    "domain": lead.domain,
    "market_sector": lead.market_sector,
    "query_theme": lead.movement,
    "query_topic": lead.query_topic,
    "query_id": lead.query_id,
    "candidate_eligible": True,
    "signal_role": "launch",
    "source_lane": "Grounded web",
    "discovery_lane": "controlled_company_discovery",
    "discovery_verification_status": "accepted",
    "discovery_verification_basis": lead.verification_basis,
    "movement_assignment_basis": lead.movement_assignment_basis,
}
```

- Add `summary` counts.
- Preserve existing `queries`, `warnings`, `errors`.
- If `query["limited"] is True`, do not call `query_runner`; add a warning once and keep `summary["queries_run"] == 0`.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_company_discovery.py .claude/skills/vc-signals/tests/test_radar_company_discovery.py
git commit -m "Return verified company discovery artifact"
```

---

## Task 5: Feed Verified Discovery Leads Through Candidate Promotion And Identity Resolution

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Add integration tests**

Add or update tests:

```python
def test_run_weekly_artifacts_feeds_verified_discovery_into_identity_resolution(tmp_path, monkeypatch):
    import json
    import radar_run
    from radar_models import ThemeSignal

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "source": "reddit",
                            "title": "How are teams controlling AI agent permissions?",
                            "url": "https://reddit.com/1",
                            "snippet": "Teams need better controls for MCP permissions and autonomous agent security.",
                        }
                    ],
                    "errors": [],
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [
            ThemeSignal(
                market_sector="Cybersecurity",
                theme="AI agent security",
                evidence_count=2,
                evidence_summary="Teams are asking how to control MCP tool permissions.",
                why_it_matters="Agent tool access creates a new security surface.",
                why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
                suggested_search="AI agent security startups Seed Series A founder launch",
                confidence="Medium",
            )
        ],
    )

    def fake_run_query(topic, **kwargs):
        assert kwargs["sources"] == "grounding"
        assert "AI agent security" in topic
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev",
                    "snippet": "AgentFence helps security teams control AI agent tool permissions.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_run_query)

    result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        github_limit=0,
        candidate_limit=50,
    )

    discovery = json.loads((tmp_path / "company-discovery.json").read_text())
    assert discovery["summary"]["accepted"] == 1
    assert discovery["accepted_leads"][0]["name"] == "AgentFence"

    candidates = json.loads((tmp_path / "candidates.json").read_text())
    agentfence = next(candidate for candidate in candidates if candidate["name"] == "AgentFence")
    assert agentfence["domain"] == "agentfence.dev"
    assert agentfence["identity_type"] == "verified_company"
    assert agentfence["attio_safe_to_match"] is True
    assert result["weekly_focus"].endswith("weekly-focus.md")


def test_run_weekly_artifacts_does_not_promote_vibe_discovery_result(tmp_path, monkeypatch):
    import json
    import radar_run
    from radar_models import ThemeSignal

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "source": "reddit",
                            "title": "How are teams controlling AI agent permissions?",
                            "url": "https://reddit.com/1",
                            "snippet": "Teams need better controls for MCP permissions and autonomous agent security.",
                        }
                    ],
                    "errors": [],
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [
            ThemeSignal(
                market_sector="Cybersecurity",
                theme="AI agent security",
                evidence_count=2,
                evidence_summary="Teams are asking how to control MCP tool permissions.",
                why_it_matters="Agent tool access creates a new security surface.",
                why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
                suggested_search="AI agent security startups Seed Series A founder launch",
                confidence="Medium",
            )
        ],
    )

    def fake_run_query(topic, **kwargs):
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Generic devtools company launches",
                    "url": "https://generic.dev",
                    "snippet": "A generic developer productivity platform.",
                    "company_name": "GenericDev",
                    "domain": "generic.dev",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_run_query)

    radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        github_limit=0,
        candidate_limit=50,
    )

    discovery = json.loads((tmp_path / "company-discovery.json").read_text())
    assert discovery["summary"]["accepted"] == 0
    assert discovery["summary"]["rejected"] >= 1

    candidates = json.loads((tmp_path / "candidates.json").read_text())
    assert all(candidate["name"] != "GenericDev" for candidate in candidates)


def test_promote_signals_merges_discovery_lead_with_existing_candidate_domain():
    from radar_models import Signal
    from radar_run import promote_signals_to_candidates

    original = Signal(
        source="grounding",
        role="launch",
        title="AgentFence launches AI agent permission firewall",
        url="https://agentfence.dev/blog/agent-security",
        sector="cybersecurity",
        theme="AI agent security",
        text="AgentFence helps security teams control AI agent permissions.",
        can_create_candidate=True,
        evidence_strength=70,
        metadata={
            "company_name": "AgentFence",
            "domain": "agentfence.dev",
            "source_lane": "Grounded web",
        },
    )
    discovery = Signal(
        source="grounding",
        role="launch",
        title="AgentFence company page",
        url="https://agentfence.dev",
        sector="cybersecurity",
        theme="AI agent security",
        text="AgentFence helps teams control MCP tool permissions for AI agents.",
        can_create_candidate=True,
        evidence_strength=75,
        metadata={
            "company_name": "AgentFence",
            "domain": "agentfence.dev",
            "source_lane": "Grounded web",
            "discovery_lane": "controlled_company_discovery",
            "discovery_verification_status": "accepted",
        },
    )

    result = promote_signals_to_candidates([original, discovery])

    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate.name == "AgentFence"
    assert candidate.domain == "agentfence.dev"
    assert sorted(candidate.sources) == [
        "https://agentfence.dev",
        "https://agentfence.dev/blog/agent-security",
    ]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_feeds_verified_discovery_into_identity_resolution .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_does_not_promote_vibe_discovery_result .claude/skills/vc-signals/tests/test_radar_run.py::test_promote_signals_merges_discovery_lead_with_existing_candidate_domain -q
```

Expected: fail until artifact and integration behavior are updated.

- [ ] **Step 3: Integrate controlled discovery inputs**

In `run_weekly_artifacts`:

- After first `promotion = promote_signals_to_candidates(...)`, create a provisional scored list:

```python
provisional_candidates = _score_sort_limit_candidates(promotion["candidates"], candidate_limit)
```

- Build provisional focus artifact or focus items:

```python
from radar_focus import build_focus_item
provisional_focus_items = [build_focus_item(candidate) for candidate in provisional_candidates]
```

- Pass unresolved candidates/focus rows into `collect_company_discovery`:

```python
company_discovery = collect_company_discovery(
    theme_signals,
    focus_items=provisional_focus_items,
    unresolved_candidates=provisional_candidates,
    query_runner=run_query,
    grounded_available=_grounded_search_available(),
    social_available=_social_search_available(),
    max_queries_per_theme=3,
)
```

- Keep writing `company-discovery.json` exactly as now.
- Let accepted leads enter `evidence["company_discovery"]` and rebuild signals/candidates as already done.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_feeds_verified_discovery_into_identity_resolution .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_does_not_promote_vibe_discovery_result .claude/skills/vc-signals/tests/test_radar_run.py::test_promote_signals_merges_discovery_lead_with_existing_candidate_domain -q
```

Expected: pass.

- [ ] **Step 5: Run related suites**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_company_discovery.py .claude/skills/vc-signals/tests/test_radar_run.py .claude/skills/vc-signals/tests/test_identity_resolution.py .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Feed verified company discovery into weekly radar"
```

---

## Task 6: Preserve GitHub-Only Project Semantics End-To-End

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_company_discovery.py`
- Modify: `.claude/skills/vc-signals/scripts/identity_resolution.py` only if tests expose a gap
- Test: `.claude/skills/vc-signals/tests/test_identity_resolution.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_focus.py`

- [ ] **Step 1: Add guardrail tests**

Add:

```python
def test_verified_discovery_does_not_turn_github_only_project_into_company():
    from identity_resolution import resolve_candidate_identity
    from radar_models import Candidate

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        domain="",
        sources=["https://github.com/affaan-m/agentshield"],
        evidence_metadata=[
            {
                "source": "github",
                "source_url": "https://github.com/affaan-m/agentshield",
                "owner_name": "affaan-m",
                "owner_type": "User",
                "homepage": "https://cerebralvalley.ai",
                "description": "AI agent security scanner for MCP permissions.",
            }
        ],
        attio_status="no_match",
    )

    result = resolve_candidate_identity(candidate)

    assert result.identity_type in {"oss_project_watch", "oss_with_commercial_intent"}
    assert result.verified_domain == ""
    assert result.attio_safe_to_match is False
    assert result.recommended_identity_action != "Assign owner"
```

Add focus test:

```python
def test_focus_does_not_assign_owner_to_github_only_project_after_discovery():
    from radar_focus import ACTION_ASSIGN_OWNER, ACTION_RESEARCH_DEEPER, build_focus_item
    from radar_models import Candidate

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        domain="",
        why_on_radar="AI agent security scanner for MCP permissions.",
        sources=["https://github.com/affaan-m/agentshield"],
        attio_status="no_match",
        identity_type="oss_project_watch",
        identity_confidence_score=45,
        recommended_identity_action="Research deeper",
        missing_identity_evidence=["no verified domain"],
        evidence_confidence_score=50,
    )

    item = build_focus_item(candidate)

    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert item.recommended_action != ACTION_ASSIGN_OWNER
    assert item.identity_type == "oss_project_watch"
```

- [ ] **Step 2: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected: pass. If fail, tighten only the minimal identity/focus rules that over-promote GitHub-only rows.

- [ ] **Step 3: Commit if code changed**

If only tests were added and pass:

```bash
git add .claude/skills/vc-signals/tests/test_identity_resolution.py .claude/skills/vc-signals/tests/test_radar_focus.py
git commit -m "Guard GitHub-only rows in discovery flow"
```

If code changed, include relevant script files in `git add`.

---

## Task 7: Product Acceptance Run And Artifact Review

**Files:**
- Generated only: `docs/radar-runs/current-phase3-check/`
- Do not commit generated run artifacts.

- [ ] **Step 1: Run full test suite**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: all tests pass. Existing warning about LibreSSL is acceptable.

- [ ] **Step 2: Run real weekly command**

Run:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/current-phase3-check --limit 50
```

Expected: writes `weekly-focus.md`, `weekly-focus.json`, `company-discovery.json`, `identity-resolution.json`, and other normal artifacts.

- [ ] **Step 3: Inspect product acceptance fields**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
root = Path('docs/radar-runs/current-phase3-check')
focus = json.loads((root / 'weekly-focus.json').read_text())
discovery = json.loads((root / 'company-discovery.json').read_text())
print('Executive Snapshot')
print(json.dumps(focus['executive_snapshot'], indent=2))
print('\nDiscovery Summary')
print(json.dumps(discovery.get('summary', {}), indent=2))
print('\nPartner Focus')
for row in focus['partner_focus']:
    print(row['name'], row.get('identity_type'), row.get('company_domain'), row['attio_status'], row['recommended_action'])
print('\nAccepted Discovery Leads')
for row in discovery.get('accepted_leads', [])[:10]:
    print(row.get('name'), row.get('domain'), row.get('verification_basis'), row.get('movement_assignment_basis'))
print('\nRejected Discovery Leads')
for row in discovery.get('rejected_leads', [])[:10]:
    print(row.get('name'), row.get('missing_evidence'))
PY
```

Acceptance checks:

- `company-discovery.json` includes `queries`, `accepted_leads`, `rejected_leads`, `summary`.
- Accepted leads have source-backed domains or equivalent proof.
- Rejected leads explain missing evidence.
- GitHub-only rows remain `oss_project_watch` or `oss_with_commercial_intent`, not `verified_company`.
- No row becomes `Assign owner` unless `identity_type == verified_company` and `attio_safe_to_match is true`.
- `weekly-focus.md` still clearly separates Partner Focus, New To Marathon, Workflow View, Extended Watchlist, and Appendix.
- `weekly-preview.md` exists and was not structurally changed by this phase.

- [ ] **Step 4: Verify no weekly-preview code diff**

Run:

```bash
git diff -- .claude/skills/vc-signals/scripts/radar_render.py .claude/skills/vc-signals/scripts/radar_run.py | rg 'weekly-preview|_render_weekly_brief|_company_discovery_section' || true
```

Expected: no unintended weekly-preview rendering changes. `radar_run.py` may have integration changes, but preview path and render function should be unchanged.

- [ ] **Step 5: Verify generated artifacts are uncommitted**

Run:

```bash
git status --short
```

Expected: generated `docs/radar-runs/current-phase3-check/` is untracked and not staged.

- [ ] **Step 6: Commit final code if needed**

If Task 7 required code changes:

```bash
git add <changed code/test files only>
git commit -m "Validate controlled company discovery output"
```

Do not add generated run artifacts.

---

## Definition Of Done

Phase 3 is done when all are true:

- Controlled company discovery starts from current market movements plus unresolved/needs-more-evidence rows.
- Query generation is movement-specific and refuses broad/vibe queries.
- Movement assignment requires at least two movement terms or one high-specificity phrase; a single generic term is not enough.
- Company discovery runs only with grounded/company web when configured.
- When grounded discovery is unavailable, discovery is artifact-only and executes zero queries.
- No broad social/source expansion was added.
- Returned discovery items are verified before promotion.
- Accepted leads require source-backed company/domain/founder/project proof and movement assignment proof.
- Content/community platform domains are evidence links only, not verified company domains.
- Rejected leads retain clear missing-evidence reasons.
- Accepted discovery items include `signal_role`, `source_lane`, and `discovery_lane`.
- Accepted leads feed into `Signal -> Candidate -> IdentityResolution`.
- Accepted leads merge with existing candidates by normalized domain/name instead of duplicating rows.
- GitHub-only rows remain project rows unless separate company proof exists.
- Actions upgrade only through existing identity and Attio-safe gates.
- `company-discovery.json` includes query, accepted, rejected, and summary sections.
- `weekly-preview.md` is unchanged in output path and rendering behavior.
- Tests include guardrails against broad/vibe-based discovery.
- Full test suite passes.
- A real weekly artifact is inspected against the Alex five-minute test:
  - top market movements are clear;
  - top companies/projects are source-backed;
  - New To Marathon is not polluted by GitHub-only rows;
  - Attio refresh/owner actions are conservative;
  - weak/noisy rows are disclosed instead of promoted.

---

## Self-Review

### Spec Coverage

- Starts from current market movements and filtered/needs-more-evidence rows: Tasks 2 and 5.
- Generates movement-specific company discovery queries: Task 2.
- Uses grounded/company web only where configured: Tasks 2 and 4.
- Requires source-backed domain/founder/company proof: Task 3.
- Blocks single-term movement/vibe matches and content-platform domains: Task 3.
- Feeds results into IdentityResolution: Task 5.
- Prevents duplicate candidate rows when discovery overlaps existing candidates: Task 5.
- Keeps GitHub-only rows as project rows unless company proof exists: Tasks 3 and 6.
- Upgrades actions only when identity and Attio-safe gates pass: Tasks 5 and 6.
- Produces `company-discovery.json`: Tasks 4 and 7.
- Keeps `weekly-preview.md` unchanged: Tasks 5 and 7.
- Includes tests preventing broad/vibe-based discovery: Tasks 2, 3, 5.

### Placeholder Scan

No task uses TBD/TODO/fill-in placeholders. All tests and commands are concrete.

### Type Consistency

`DiscoveryQuery`, `VerifiedCompanyDiscoveryLead`, `Candidate`, `FocusItem`, `ThemeSignal`, and existing artifact keys are consistently named across tasks.
