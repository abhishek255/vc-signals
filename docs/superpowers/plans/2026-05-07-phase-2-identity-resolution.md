# Phase 2 Identity Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the actual company/project identity behind launch-style and OSS/project focus rows so VC Signals can upgrade credible rows from `Research deeper` to `Assign owner` or `Refresh Attio`, and demote rows whose identity or commercial intent remains weak.

**Architecture:** Add a deterministic identity-resolution layer between candidate scoring and weekly-focus rendering. Phase 2 consumes existing `Candidate` rows and already-captured evidence URLs only; it does not add broad new source adapters. The resolver normalizes company/project identity, domain, founders/maintainers, commercial intent, Attio-safe match keys, confidence, and post-resolution action, then feeds enriched candidates back into the existing `weekly-focus.json` and `weekly-focus.md` flow.

**Tech Stack:** Python dataclasses, existing `.claude/skills/vc-signals/scripts` modules, pytest, JSON cache/artifacts, optional read-only HTTP fetches for already-present evidence URLs, existing read-only Attio client.

---

## Product Scope

Phase 2 starts from the current top identity-resolution target pattern:

```text
Burrow
- launch-style evidence
- no_match in Attio
- missing domain
- missing founder identity
- action is currently Research deeper
```

The product goal is not to find more broad internet sources yet. The goal is to make the rows already found more actionable.

Phase 2 should answer, for each eligible row:

- What is the actual company/project identity?
- Is there a verified domain?
- Who are the founders or maintainers?
- Is there commercial intent?
- What Attio-safe matching keys should be used?
- What is the identity confidence and why?
- Should the row become `Assign owner`, `Refresh Attio`, stay `Research deeper`, or be demoted to `Monitor only` / Appendix?

## Explicit Non-Goals

Do not build these in Phase 2:

- broad new source adapters
- X/Twitter adapter
- LinkedIn scraping/automation
- Product Hunt adapter
- package registry adapters
- movement time-series
- Slack delivery
- Attio writeback
- live LLM dependency
- changes to `weekly-preview.md`

Allowed in Phase 2:

- Use existing candidate fields.
- Use already-present source URLs from `Candidate.sources` / `Candidate.source`.
- Fetch or parse already-present evidence URLs when network is available.
- Use existing read-only Attio matching after a cleaner domain/name is resolved.
- Cache identity-resolution results.

## Files And Responsibilities

### Create

- `.claude/skills/vc-signals/scripts/identity_resolution.py`
  - Pure identity-resolution logic.
  - Defines deterministic classifiers and helpers.
  - Reads existing candidate evidence URLs only.
  - Does not discover broad new sources.
  - Does not write Attio.

- `.claude/skills/vc-signals/tests/test_identity_resolution.py`
  - Unit tests for model roundtrips, launch-style resolution, OSS/project classification, commercial intent scoring, Attio-safe match keys, action upgrades/demotions, and cache behavior.

### Modify

- `.claude/skills/vc-signals/scripts/radar_models.py`
  - Add `IdentityResolution` dataclass.
  - Add identity-resolution fields to `Candidate`.
  - Keep unknown fields tolerant with `_known_payload`.

- `.claude/skills/vc-signals/scripts/radar_focus.py`
  - Use resolved identity fields in `score_company_identity()`, missing evidence, actionability, and recommended action.
  - Preserve existing Phase 1A/1B behavior when no identity resolution is present.

- `.claude/skills/vc-signals/scripts/radar_run.py`
  - Apply identity resolution after candidate enrichment and before Attio matching/focus artifact generation.
  - Write `identity-resolution.json` beside `weekly-focus.json`.
  - Include identity-resolution summary in run JSON.
  - Do not change `weekly-preview.md` rendering.

- `.claude/skills/vc-signals/tests/test_radar_focus.py`
  - Add tests proving resolved identity changes focus scoring/actions.

- `.claude/skills/vc-signals/tests/test_radar_run.py`
  - Add tests proving weekly runs write `identity-resolution.json` and still leave `weekly-preview.md` content path unchanged.

- `.gitignore`
  - Add generated identity-resolution cache/output files if they are local run state.

### Optional Docs Update After Implementation

- `docs/examples/weekly-focus-example.md`
  - Update only after Phase 2 works, to show one row upgraded by identity resolution.

- `docs/superpowers/specs/2026-05-07-market-movement-intelligence-product-spec.md`
  - Mark Phase 2 as implemented only after tests and real artifact verification pass.

---

## Model Definitions

### Add `IdentityResolution` To `radar_models.py`

```python
@dataclass
class IdentityResolution:
    candidate_key: str
    original_name: str = ""
    resolved_name: str = ""
    identity_type: str = "insufficient_identity"
    candidate_domain: str = ""
    verified_domain: str = ""
    domain_confidence: str = "Low"
    verified_domain_basis: list[str] = field(default_factory=list)
    project_url: str = ""
    company_linkedin: str = ""
    company_x: str = ""
    founders: list[str] = field(default_factory=list)
    founder_profiles: list[dict] = field(default_factory=list)
    maintainers: list[str] = field(default_factory=list)
    maintainer_profiles: list[dict] = field(default_factory=list)
    commercial_intent_score: int = 0
    commercial_intent_basis: list[str] = field(default_factory=list)
    identity_confidence_score: int = 0
    identity_confidence: str = "Low"
    identity_confidence_basis: list[str] = field(default_factory=list)
    attio_match_keys: list[str] = field(default_factory=list)
    attio_safe_to_match: bool = False
    recommended_identity_action: str = "Research deeper"
    missing_identity_evidence: list[str] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    source_outbound_urls: list[str] = field(default_factory=list)
    source_titles: list[str] = field(default_factory=list)
    fetch_warnings: list[str] = field(default_factory=list)
    resolved_from: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "IdentityResolution":
        return cls(**_known_payload(cls, payload))
```

### Add Fields To `Candidate`

Add these optional fields to `Candidate`:

```python
identity_type: str = ""
candidate_domain: str = ""
domain_confidence: str = ""
verified_domain_basis: list[str] = field(default_factory=list)
identity_confidence_score: int = 0
identity_confidence: str = ""
identity_confidence_basis: list[str] = field(default_factory=list)
commercial_intent_score: int = 0
commercial_intent_basis: list[str] = field(default_factory=list)
attio_match_keys: list[str] = field(default_factory=list)
attio_safe_to_match: bool = False
recommended_identity_action: str = ""
missing_identity_evidence: list[str] = field(default_factory=list)
source_outbound_urls: list[str] = field(default_factory=list)
source_titles: list[str] = field(default_factory=list)
fetch_warnings: list[str] = field(default_factory=list)
identity_resolved_from: list[str] = field(default_factory=list)
```

Allowed `identity_type` values:

- `verified_company`
- `launch_style_needs_identity`
- `oss_with_commercial_intent`
- `oss_project_watch`
- `insufficient_identity`

Allowed `recommended_identity_action` values:

- `Assign owner`
- `Refresh Attio`
- `Research deeper`
- `Monitor only`

---

## Scoring Rules

### Identity Confidence

Start at 20.

Add:

- `+35` verified domain from a source URL or trusted candidate domain provenance.
- `+20` founder or maintainer identity present.
- `+15` launch-style evidence present.
- `+15` company/social profile present from existing candidate fields.
- `+10` Attio-safe match key exists.
- `+10` commercial intent score >= 60.

Subtract:

- `-25` no domain and no founder/maintainer identity.
- `-20` inferred name only.
- `-15` consumer/off-thesis project language.

Clamp to 0-100.

Confidence labels:

- `High`: `>= 80`
- `Medium`: `>= 55`
- `Low`: `< 55`

Domain terminology must stay conservative:

- `candidate_domain` means a domain already present on the candidate.
- `verified_domain` means the resolver can explain why the domain is safe to use for Attio matching.
- `domain_confidence="High"` only when the domain came from an already-present company URL, existing Attio enrichment, or an explicitly trusted structured field.
- `domain_confidence="Medium"` when the domain came from `candidate.domain` without provenance.
- `domain_confidence="Low"` when no domain exists.
- Do not call a GitHub repo URL a verified company domain.

Every `verified_domain` must include `verified_domain_basis`, such as:

- `source_url_domain`
- `candidate_domain_present`
- `attio_enrichment_domain`
- `hn_outbound_url_domain`
- `company_url_already_present`

### Commercial Intent

Start at 20.

Add:

- `+25` source text contains pricing, demo, waitlist, customers, enterprise, cloud, hosted, company, startup, or contact sales.
- `+20` verified domain exists and is not only a GitHub repo.
- `+15` founder/company profile exists.
- `+15` launch-style source exists.
- `+10` OSS repo has company/org owner or maintainer identity.

Subtract:

- `-20` personal side project language.
- `-20` no domain and only GitHub evidence.
- `-15` tutorial/demo/example wording.
- `-15` consumer/gaming/freebie/off-thesis wording.

Clamp to 0-100.

### Action After Identity Resolution

Rules:

```python
if attio_status in {"stale", "passed"} and identity_confidence_score >= 60:
    return "Refresh Attio"

if attio_status in {"no_match", "not_found", "new"}:
    has_actionable_identity = bool(verified_domain) or (
        bool(founders or maintainers)
        and "launch_source_present" in identity_confidence_basis
    )
    if (
        identity_confidence_score >= 70
        and commercial_intent_score >= 50
        and attio_safe_to_match
        and has_actionable_identity
    ):
        return "Assign owner"
    return "Research deeper"

if attio_status in {"unknown", ""}:
    if identity_confidence_score >= 70 and commercial_intent_score >= 60:
        return "Research deeper"
    return "Monitor only"

if identity_confidence_score < 45 or commercial_intent_score < 35:
    return "Monitor only"

return "Research deeper"
```

Phase 2 should not produce `Take meeting`. That action remains gated by Phase 1A/1B strict rules and should stay rare.

---

## Task 1: Identity Models

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_models.py`

- [ ] **Step 1: Write failing model roundtrip test**

Add to `.claude/skills/vc-signals/tests/test_radar_models.py`:

```python
def test_identity_resolution_roundtrip_ignores_unknown_fields():
    from radar_models import IdentityResolution

    payload = {
        "candidate_key": "launch:burrow",
        "original_name": "Burrow",
        "resolved_name": "Burrow",
        "identity_type": "launch_style_needs_identity",
        "candidate_domain": "burrow.example",
        "verified_domain": "burrow.example",
        "domain_confidence": "Medium",
        "verified_domain_basis": ["candidate_domain_present"],
        "founders": ["Jane Founder"],
        "commercial_intent_score": 65,
        "commercial_intent_basis": ["launch_source_present"],
        "identity_confidence_score": 75,
        "identity_confidence": "Medium",
        "identity_confidence_basis": ["verified_domain_present"],
        "attio_match_keys": ["burrow.example", "Burrow"],
        "attio_safe_to_match": True,
        "recommended_identity_action": "Assign owner",
        "missing_identity_evidence": ["no company linkedin"],
        "evidence_urls": ["https://news.ycombinator.com/item?id=123"],
        "source_outbound_urls": ["https://burrow.example"],
        "source_titles": ["Show HN: Burrow"],
        "fetch_warnings": [],
        "resolved_from": ["candidate_domain"],
        "extra_future_field": "ignored",
    }

    result = IdentityResolution.from_dict(payload)

    assert result.candidate_key == "launch:burrow"
    assert result.verified_domain == "burrow.example"
    assert result.domain_confidence == "Medium"
    assert result.source_titles == ["Show HN: Burrow"]
    assert result.attio_safe_to_match is True
    assert "extra_future_field" not in result.to_dict()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py::test_identity_resolution_roundtrip_ignores_unknown_fields -q
```

Expected: FAIL because `IdentityResolution` does not exist.

- [ ] **Step 3: Add `IdentityResolution` and Candidate fields**

Implement the model definitions exactly from the "Model Definitions" section.

- [ ] **Step 4: Run model test**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py::test_identity_resolution_roundtrip_ignores_unknown_fields -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/tests/test_radar_models.py
git commit -m "Add identity resolution models"
```

---

## Task 2: Deterministic Identity Resolver

**Files:**
- Create: `.claude/skills/vc-signals/scripts/identity_resolution.py`
- Create: `.claude/skills/vc-signals/tests/test_identity_resolution.py`

- [ ] **Step 1: Write failing tests for Burrow-style launch row**

Create `.claude/skills/vc-signals/tests/test_identity_resolution.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from radar_models import Candidate


def _candidate(**overrides):
    payload = {
        "name": "Burrow",
        "sector": "Cybersecurity",
        "theme": "AI agent security",
        "source": "https://news.ycombinator.com/item?id=47761957",
        "candidate_type": "company_web",
        "stable_key": "hn:47761957",
        "domain": "",
        "why_on_radar": "Show HN: Burrow - Runtime Security for AI Agents",
        "sources": ["https://news.ycombinator.com/item?id=47761957"],
        "attio_status": "no_match",
        "evidence_confidence_score": 30,
    }
    payload.update(overrides)
    return Candidate(**payload)


def test_launch_style_missing_domain_stays_research_deeper():
    from identity_resolution import resolve_candidate_identity

    result = resolve_candidate_identity(_candidate())

    assert result.original_name == "Burrow"
    assert result.identity_type == "launch_style_needs_identity"
    assert result.verified_domain == ""
    assert result.identity_confidence == "Low"
    assert result.recommended_identity_action == "Research deeper"
    assert "no verified domain" in result.missing_identity_evidence
    assert "no founder or maintainer identity" in result.missing_identity_evidence
    assert result.attio_safe_to_match is False


def test_launch_style_with_domain_and_founder_can_assign_owner():
    from identity_resolution import resolve_candidate_identity

    result = resolve_candidate_identity(
        _candidate(
            domain="burrow.security",
            founders=["Jane Founder"],
            founder_profiles=[{"name": "Jane Founder", "source": "launch page"}],
        )
    )

    assert result.identity_type == "verified_company"
    assert result.verified_domain == "burrow.security"
    assert result.identity_confidence_score >= 70
    assert result.commercial_intent_score >= 50
    assert result.attio_safe_to_match is True
    assert "burrow.security" in result.attio_match_keys
    assert result.recommended_identity_action == "Assign owner"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py -q
```

Expected: FAIL because `identity_resolution.py` does not exist.

- [ ] **Step 3: Implement resolver skeleton**

Create `.claude/skills/vc-signals/scripts/identity_resolution.py`:

```python
from __future__ import annotations

import re
from urllib.parse import urlparse

from radar_focus import ACTION_ASSIGN_OWNER, ACTION_MONITOR_ONLY, ACTION_REFRESH_ATTIO, ACTION_RESEARCH_DEEPER
from radar_models import Candidate, IdentityResolution


IDENTITY_VERIFIED_COMPANY = "verified_company"
IDENTITY_LAUNCH_NEEDS_IDENTITY = "launch_style_needs_identity"
IDENTITY_OSS_COMMERCIAL = "oss_with_commercial_intent"
IDENTITY_OSS_WATCH = "oss_project_watch"
IDENTITY_INSUFFICIENT = "insufficient_identity"


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))


def _text_blob(*values: object) -> str:
    return " ".join(str(value) for value in values if value is not None).lower()


def _source_urls(candidate: Candidate) -> list[str]:
    urls = []
    for source in list(candidate.sources or []) + [candidate.source]:
        if source and source.startswith(("http://", "https://")) and source not in urls:
            urls.append(source)
    return urls


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        raw = parsed.netloc
    raw = raw.lower().strip("/")
    if raw.startswith("www."):
        raw = raw[4:]
    return raw


def _is_github_only(candidate: Candidate) -> bool:
    urls = _source_urls(candidate)
    return bool(urls) and all("github.com" in url for url in urls) and not candidate.domain


def _has_launch_evidence(candidate: Candidate) -> bool:
    text = _text_blob(candidate.name, candidate.why_on_radar, candidate.source, candidate.sources)
    return any(term in text for term in ("show hn", "launch", "ycombinator.com", "product launch"))


def _founder_or_maintainer_names(candidate: Candidate) -> tuple[list[str], list[str]]:
    founders = list(candidate.founders or [])
    maintainers = []
    for profile in candidate.founder_profiles or []:
        name = profile.get("name") or profile.get("title") or profile.get("url") or ""
        if name and name not in founders:
            founders.append(name)
    for profile in candidate.maintainer_profiles or []:
        name = profile.get("name") or profile.get("login") or profile.get("url") or ""
        if name and name not in maintainers:
            maintainers.append(name)
    return founders, maintainers


def score_commercial_intent(candidate: Candidate, verified_domain: str, founders: list[str], maintainers: list[str]) -> tuple[int, list[str]]:
    score = 20
    basis = []
    text = _text_blob(candidate.name, candidate.why_on_radar, candidate.why_this_may_be_noise, candidate.source_lane)
    if any(term in text for term in ("pricing", "demo", "waitlist", "customers", "enterprise", "cloud", "hosted", "company", "startup", "contact sales")):
        score += 25
        basis.append("commercial_language_present")
    if verified_domain and "github.com" not in verified_domain:
        score += 20
        basis.append("non_github_domain_present")
    if founders or candidate.company_linkedin or candidate.company_x:
        score += 15
        basis.append("founder_or_company_profile_present")
    if _has_launch_evidence(candidate):
        score += 15
        basis.append("launch_source_present")
    if candidate.candidate_type == "oss_project" and maintainers:
        score += 10
        basis.append("oss_maintainer_identity_present")
    if any(term in text for term in ("side project", "toy", "demo only", "example", "tutorial")):
        score -= 20
        basis.append("side_project_or_demo_language")
    if _is_github_only(candidate):
        score -= 20
        basis.append("github_only_no_domain")
    if any(term in text for term in ("epic games", "freebies", "consumer", "gaming")):
        score -= 15
        basis.append("consumer_or_off_thesis_language")
    return _clamp(score), basis or ["baseline_commercial_intent"]


def score_identity_confidence(
    candidate: Candidate,
    verified_domain: str,
    founders: list[str],
    maintainers: list[str],
    commercial_intent_score: int,
    attio_match_keys: list[str],
) -> tuple[int, str, list[str]]:
    score = 20
    basis = []
    text = _text_blob(candidate.name, candidate.why_on_radar)
    if verified_domain:
        score += 35
        basis.append("verified_domain_present")
    if founders or maintainers:
        score += 20
        basis.append("founder_or_maintainer_identity_present")
    if _has_launch_evidence(candidate):
        score += 15
        basis.append("launch_source_present")
    if candidate.company_linkedin or candidate.company_x:
        score += 15
        basis.append("company_social_profile_present")
    if attio_match_keys:
        score += 10
        basis.append("attio_match_key_present")
    if commercial_intent_score >= 60:
        score += 10
        basis.append("commercial_intent_medium_or_better")
    if not verified_domain and not founders and not maintainers:
        score -= 25
        basis.append("missing_domain_and_people")
    if len((candidate.name or "").strip()) <= 2 and not verified_domain:
        score -= 20
        basis.append("inferred_name_only")
    if any(term in text for term in ("consumer", "gaming", "freebies")):
        score -= 15
        basis.append("off_thesis_language")
    score = _clamp(score)
    if score >= 80:
        label = "High"
    elif score >= 55:
        label = "Medium"
    else:
        label = "Low"
    return score, label, basis or ["baseline_identity_confidence"]


def classify_identity(candidate: Candidate, verified_domain: str, commercial_intent_score: int) -> str:
    if verified_domain and commercial_intent_score >= 50:
        return IDENTITY_VERIFIED_COMPANY
    if _has_launch_evidence(candidate):
        return IDENTITY_LAUNCH_NEEDS_IDENTITY
    if candidate.candidate_type == "oss_project" and commercial_intent_score >= 60:
        return IDENTITY_OSS_COMMERCIAL
    if candidate.candidate_type == "oss_project":
        return IDENTITY_OSS_WATCH
    return IDENTITY_INSUFFICIENT


def choose_identity_action(candidate: Candidate, resolution: IdentityResolution) -> str:
    status = (candidate.attio_status or "unknown").lower()
    if status in {"stale", "passed"} and resolution.identity_confidence_score >= 60:
        return ACTION_REFRESH_ATTIO
    if status in {"no_match", "not_found", "new"}:
        has_actionable_identity = bool(resolution.verified_domain) or (
            bool(resolution.founders or resolution.maintainers)
            and "launch_source_present" in resolution.identity_confidence_basis
        )
        if (
            resolution.identity_confidence_score >= 70
            and resolution.commercial_intent_score >= 50
            and resolution.attio_safe_to_match
            and has_actionable_identity
        ):
            return ACTION_ASSIGN_OWNER
        return ACTION_RESEARCH_DEEPER
    if status in {"unknown", ""}:
        if resolution.identity_confidence_score >= 70 and resolution.commercial_intent_score >= 60:
            return ACTION_RESEARCH_DEEPER
        return ACTION_MONITOR_ONLY
    if resolution.identity_confidence_score < 45 or resolution.commercial_intent_score < 35:
        return ACTION_MONITOR_ONLY
    return ACTION_RESEARCH_DEEPER


def resolve_candidate_identity(candidate: Candidate) -> IdentityResolution:
    urls = _source_urls(candidate)
    candidate_domain = _normalize_domain(candidate.domain)
    verified_domain = candidate_domain
    domain_confidence = "Medium" if candidate_domain else "Low"
    verified_domain_basis = ["candidate_domain_present"] if candidate_domain else []
    founders, maintainers = _founder_or_maintainer_names(candidate)
    attio_match_keys = [key for key in [verified_domain, candidate.name] if key]
    commercial_score, commercial_basis = score_commercial_intent(candidate, verified_domain, founders, maintainers)
    confidence_score, confidence, confidence_basis = score_identity_confidence(
        candidate,
        verified_domain,
        founders,
        maintainers,
        commercial_score,
        attio_match_keys,
    )
    missing = []
    if not verified_domain:
        missing.append("no verified domain")
    if not founders and not maintainers:
        missing.append("no founder or maintainer identity")
    identity_type = classify_identity(candidate, verified_domain, commercial_score)
    resolution = IdentityResolution(
        candidate_key=candidate.stable_key or candidate.name,
        original_name=candidate.name,
        resolved_name=candidate.name,
        identity_type=identity_type,
        candidate_domain=candidate_domain,
        verified_domain=verified_domain,
        domain_confidence=domain_confidence,
        verified_domain_basis=verified_domain_basis,
        project_url=next((url for url in urls if "github.com" in url), ""),
        company_linkedin=candidate.company_linkedin,
        company_x=candidate.company_x,
        founders=founders,
        founder_profiles=list(candidate.founder_profiles or []),
        maintainers=maintainers,
        maintainer_profiles=list(candidate.maintainer_profiles or []),
        commercial_intent_score=commercial_score,
        commercial_intent_basis=commercial_basis,
        identity_confidence_score=confidence_score,
        identity_confidence=confidence,
        identity_confidence_basis=confidence_basis,
        attio_match_keys=attio_match_keys,
        attio_safe_to_match=bool(verified_domain),
        missing_identity_evidence=missing,
        evidence_urls=urls,
        source_outbound_urls=[],
        source_titles=[],
        fetch_warnings=[],
        resolved_from=["candidate_fields"],
    )
    resolution.recommended_identity_action = choose_identity_action(candidate, resolution)
    return resolution
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/identity_resolution.py .claude/skills/vc-signals/tests/test_identity_resolution.py
git commit -m "Add deterministic identity resolver"
```

---

## Task 2.5: Resolve Identity From Existing Evidence URLs

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/identity_resolution.py`
- Modify: `.claude/skills/vc-signals/tests/test_identity_resolution.py`

This task is the difference between identity scoring and identity resolution.

Scope is intentionally narrow:

- Inspect only `candidate.source` and `candidate.sources`.
- Do not run web search.
- Do not query X, Product Hunt, LinkedIn, package registries, or search APIs.
- Parse HN item pages for title and outbound URL.
- Parse GitHub repo URLs for owner/repo and project identity.
- Use company URLs already present as source evidence.
- Cache fetch results.
- Fail closed when fetch/network parsing fails.

- [ ] **Step 1: Add failing tests for existing evidence URL parsing**

Append to `.claude/skills/vc-signals/tests/test_identity_resolution.py`:

```python
def test_parse_hn_item_extracts_title_and_outbound_url():
    from identity_resolution import parse_hn_item

    html = """
    <html>
      <tr class="athing" id="47761957">
        <span class="titleline">
          <a href="https://burrow.security">Show HN: Burrow - Runtime Security for AI Agents</a>
        </span>
      </tr>
    </html>
    """

    result = parse_hn_item(html)

    assert result["title"] == "Show HN: Burrow - Runtime Security for AI Agents"
    assert result["outbound_url"] == "https://burrow.security"


def test_hn_item_with_outbound_url_improves_identity_domain(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    html = """
    <html>
      <span class="titleline">
        <a href="https://burrow.security">Show HN: Burrow - Runtime Security for AI Agents</a>
      </span>
    </html>
    """

    def fake_fetch(url, cache=None, timeout_seconds=8):
        return html

    monkeypatch.setattr("identity_resolution.fetch_existing_url", fake_fetch)

    result = resolve_candidate_identity(_candidate())

    assert result.verified_domain == "burrow.security"
    assert result.domain_confidence == "High"
    assert "hn_outbound_url_domain" in result.verified_domain_basis
    assert "https://burrow.security" in result.source_outbound_urls
    assert result.identity_confidence_score >= 55


def test_hn_fetch_failure_keeps_launch_style_needs_identity(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    def fake_fetch(url, cache=None, timeout_seconds=8):
        raise TimeoutError("network timeout")

    monkeypatch.setattr("identity_resolution.fetch_existing_url", fake_fetch)

    result = resolve_candidate_identity(_candidate())

    assert result.identity_type == "launch_style_needs_identity"
    assert result.verified_domain == ""
    assert result.recommended_identity_action == "Research deeper"
    assert result.fetch_warnings


def test_github_only_row_extracts_project_but_not_company_domain():
    from identity_resolution import parse_github_url, resolve_candidate_identity

    parsed = parse_github_url("https://github.com/slowql/slowql")
    assert parsed["owner"] == "slowql"
    assert parsed["repo"] == "slowql"
    assert parsed["project_url"] == "https://github.com/slowql/slowql"

    result = resolve_candidate_identity(
        _candidate(
            name="slowql/slowql",
            stable_key="repo:slowql",
            candidate_type="oss_project",
            source="https://github.com/slowql/slowql",
            sources=["https://github.com/slowql/slowql"],
            domain="",
            attio_status="unknown",
        )
    )

    assert result.project_url == "https://github.com/slowql/slowql"
    assert result.verified_domain == ""
    assert result.attio_safe_to_match is False
    assert "github_project_identity" in result.identity_confidence_basis
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py::test_parse_hn_item_extracts_title_and_outbound_url .claude/skills/vc-signals/tests/test_identity_resolution.py::test_hn_item_with_outbound_url_improves_identity_domain .claude/skills/vc-signals/tests/test_identity_resolution.py::test_hn_fetch_failure_keeps_launch_style_needs_identity .claude/skills/vc-signals/tests/test_identity_resolution.py::test_github_only_row_extracts_project_but_not_company_domain -q
```

Expected: FAIL because evidence URL parsing functions do not exist.

- [ ] **Step 3: Implement parsing helpers**

Add to `.claude/skills/vc-signals/scripts/identity_resolution.py`:

```python
from html.parser import HTMLParser
from urllib.request import Request, urlopen


class _HNTitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_titleline = False
        self.capture_text = False
        self.title_parts = []
        self.outbound_url = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        class_value = attrs_dict.get("class", "")
        if tag == "span" and "titleline" in class_value:
            self.in_titleline = True
        elif self.in_titleline and tag == "a":
            href = attrs_dict.get("href", "")
            if href and not href.startswith("item?id="):
                self.outbound_url = href
            self.capture_text = True

    def handle_endtag(self, tag):
        if tag == "a":
            self.capture_text = False
        elif tag == "span" and self.in_titleline:
            self.in_titleline = False

    def handle_data(self, data):
        if self.capture_text:
            text = data.strip()
            if text:
                self.title_parts.append(text)


def parse_hn_item(html: str) -> dict:
    parser = _HNTitleParser()
    parser.feed(html or "")
    return {
        "title": " ".join(parser.title_parts).strip(),
        "outbound_url": parser.outbound_url.strip(),
    }


def parse_github_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return {}
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return {}
    owner, repo = parts[0], parts[1]
    return {
        "owner": owner,
        "repo": repo,
        "project_url": f"https://github.com/{owner}/{repo}",
    }


def fetch_existing_url(url: str, cache: dict | None = None, timeout_seconds: int = 8) -> str:
    if cache is not None and url in cache:
        return cache[url]
    request = Request(url, headers={"User-Agent": "vc-signals-identity-resolution/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8", errors="replace")
    if cache is not None:
        cache[url] = body
    return body


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    domain = _normalize_domain(parsed.netloc)
    if domain in {"github.com", "news.ycombinator.com", "www.github.com"}:
        return ""
    return domain


def resolve_from_existing_urls(candidate: Candidate, fetch_cache: dict | None = None) -> dict:
    hints = {
        "verified_domain": "",
        "domain_confidence": "Low",
        "verified_domain_basis": [],
        "project_url": "",
        "source_outbound_urls": [],
        "source_titles": [],
        "fetch_warnings": [],
        "identity_confidence_basis": [],
        "resolved_from": [],
    }

    for url in _source_urls(candidate):
        github = parse_github_url(url)
        if github:
            hints["project_url"] = hints["project_url"] or github["project_url"]
            hints["identity_confidence_basis"].append("github_project_identity")
            hints["resolved_from"].append("github_url")
            continue

        direct_domain = _domain_from_url(url)
        if direct_domain and "news.ycombinator.com" not in url:
            hints["verified_domain"] = hints["verified_domain"] or direct_domain
            hints["domain_confidence"] = "High"
            hints["verified_domain_basis"].append("company_url_already_present")
            hints["resolved_from"].append("source_url")

        if "news.ycombinator.com/item" in url:
            try:
                html = fetch_existing_url(url, cache=fetch_cache)
                parsed = parse_hn_item(html)
            except Exception as exc:
                hints["fetch_warnings"].append(f"{url}: {exc}")
                continue
            if parsed.get("title"):
                hints["source_titles"].append(parsed["title"])
            outbound_url = parsed.get("outbound_url") or ""
            if outbound_url:
                hints["source_outbound_urls"].append(outbound_url)
                outbound_domain = _domain_from_url(outbound_url)
                if outbound_domain:
                    hints["verified_domain"] = hints["verified_domain"] or outbound_domain
                    hints["domain_confidence"] = "High"
                    hints["verified_domain_basis"].append("hn_outbound_url_domain")
                    hints["resolved_from"].append("hn_item_outbound_url")

    hints["verified_domain_basis"] = list(dict.fromkeys(hints["verified_domain_basis"]))
    hints["identity_confidence_basis"] = list(dict.fromkeys(hints["identity_confidence_basis"]))
    hints["resolved_from"] = list(dict.fromkeys(hints["resolved_from"]))
    return hints
```

- [ ] **Step 4: Integrate hints into `resolve_candidate_identity()`**

Update `resolve_candidate_identity()` so it calls:

```python
url_hints = resolve_from_existing_urls(candidate)
candidate_domain = _normalize_domain(candidate.domain)
verified_domain = url_hints.get("verified_domain") or candidate_domain
domain_confidence = url_hints.get("domain_confidence") or ("Medium" if candidate_domain else "Low")
verified_domain_basis = list(url_hints.get("verified_domain_basis") or [])
if candidate_domain and not verified_domain_basis:
    verified_domain_basis.append("candidate_domain_present")
```

Also pass these fields into `IdentityResolution`:

```python
candidate_domain=candidate_domain,
verified_domain=verified_domain,
domain_confidence=domain_confidence,
verified_domain_basis=verified_domain_basis,
project_url=url_hints.get("project_url") or next((url for url in urls if "github.com" in url), ""),
source_outbound_urls=list(url_hints.get("source_outbound_urls") or []),
source_titles=list(url_hints.get("source_titles") or []),
fetch_warnings=list(url_hints.get("fetch_warnings") or []),
resolved_from=list(dict.fromkeys(["candidate_fields"] + list(url_hints.get("resolved_from") or []))),
```

When scoring identity confidence, include `url_hints["identity_confidence_basis"]` in the final basis.

- [ ] **Step 5: Run identity tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/scripts/identity_resolution.py .claude/skills/vc-signals/tests/test_identity_resolution.py
git commit -m "Resolve identity from existing evidence URLs"
```

## Task 3: Apply Identity Resolution To Candidates

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/identity_resolution.py`
- Modify: `.claude/skills/vc-signals/tests/test_identity_resolution.py`

- [ ] **Step 1: Add failing tests for candidate application**

Append:

```python
def test_apply_identity_resolution_updates_candidate_fields():
    from identity_resolution import apply_identity_resolution

    candidates = [
        _candidate(
            domain="burrow.security",
            founders=["Jane Founder"],
            founder_profiles=[{"name": "Jane Founder"}],
        )
    ]

    resolved, resolutions = apply_identity_resolution(candidates)

    assert len(resolutions) == 1
    assert resolved[0].domain == "burrow.security"
    assert resolved[0].identity_type == "verified_company"
    assert resolved[0].identity_confidence_score >= 70
    assert resolved[0].commercial_intent_score >= 50
    assert resolved[0].attio_safe_to_match is True
    assert resolved[0].recommended_identity_action == "Assign owner"


def test_apply_identity_resolution_demotes_weak_unknown_oss_row():
    from identity_resolution import apply_identity_resolution

    candidates = [
        _candidate(
            name="example/weak-demo",
            stable_key="repo:weak-demo",
            candidate_type="oss_project",
            source="https://github.com/example/weak-demo",
            sources=["https://github.com/example/weak-demo"],
            domain="",
            founders=[],
            founder_profiles=[],
            maintainer_profiles=[],
            attio_status="unknown",
            why_on_radar="Example tutorial repo for trying a toy workflow.",
        )
    ]

    resolved, resolutions = apply_identity_resolution(candidates)

    assert resolutions[0].identity_type == "oss_project_watch"
    assert resolutions[0].recommended_identity_action == "Monitor only"
    assert resolved[0].recommended_identity_action == "Monitor only"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py::test_apply_identity_resolution_updates_candidate_fields .claude/skills/vc-signals/tests/test_identity_resolution.py::test_apply_identity_resolution_demotes_weak_unknown_oss_row -q
```

Expected: FAIL because `apply_identity_resolution` does not exist.

- [ ] **Step 3: Implement application function**

Add to `identity_resolution.py`:

```python
def apply_identity_to_candidate(candidate: Candidate, resolution: IdentityResolution) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    if resolution.verified_domain:
        out.domain = resolution.verified_domain
    if resolution.company_linkedin:
        out.company_linkedin = resolution.company_linkedin
    if resolution.company_x:
        out.company_x = resolution.company_x
    if resolution.founders:
        out.founders = list(resolution.founders)
    if resolution.founder_profiles:
        out.founder_profiles = list(resolution.founder_profiles)
    if resolution.maintainer_profiles:
        out.maintainer_profiles = list(resolution.maintainer_profiles)
    out.identity_type = resolution.identity_type
    out.identity_confidence_score = resolution.identity_confidence_score
    out.identity_confidence = resolution.identity_confidence
    out.identity_confidence_basis = list(resolution.identity_confidence_basis)
    out.commercial_intent_score = resolution.commercial_intent_score
    out.commercial_intent_basis = list(resolution.commercial_intent_basis)
    out.attio_match_keys = list(resolution.attio_match_keys)
    out.attio_safe_to_match = resolution.attio_safe_to_match
    out.recommended_identity_action = resolution.recommended_identity_action
    out.missing_identity_evidence = list(resolution.missing_identity_evidence)
    out.identity_resolved_from = list(resolution.resolved_from)
    return out


def apply_identity_resolution(candidates: list[Candidate]) -> tuple[list[Candidate], list[IdentityResolution]]:
    resolved_candidates = []
    resolutions = []
    for candidate in candidates:
        resolution = resolve_candidate_identity(candidate)
        resolutions.append(resolution)
        resolved_candidates.append(apply_identity_to_candidate(candidate, resolution))
    return resolved_candidates, resolutions
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/identity_resolution.py .claude/skills/vc-signals/tests/test_identity_resolution.py
git commit -m "Apply identity resolution to candidates"
```

---

## Task 4: Feed Identity Resolution Into Focus Scoring

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_focus.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_focus.py`

- [ ] **Step 1: Add failing focus tests**

Add to `.claude/skills/vc-signals/tests/test_radar_focus.py`:

```python
def test_resolved_identity_upgrades_no_match_row_to_assign_owner():
    from radar_focus import ACTION_ASSIGN_OWNER, build_focus_item

    item = build_focus_item(
        _candidate(
            name="Burrow",
            domain="burrow.security",
            attio_status="no_match",
            evidence_confidence_score=50,
            investment_interest_score=65,
            identity_type="verified_company",
            identity_confidence_score=78,
            commercial_intent_score=65,
            attio_safe_to_match=True,
            recommended_identity_action="Assign owner",
            founders=["Jane Founder"],
            founder_profiles=[{"name": "Jane Founder"}],
            sources=["https://news.ycombinator.com/item?id=47761957"],
        )
    )

    assert item.company_identity_quality_score >= 80
    assert item.recommended_action == ACTION_ASSIGN_OWNER
    assert "identity_resolution_verified_company" in item.company_identity_quality_basis


def test_weak_identity_demotes_unknown_oss_row_to_monitor_only():
    from radar_focus import ACTION_MONITOR_ONLY, build_focus_item

    item = build_focus_item(
        _candidate(
            name="example/weak-demo",
            domain="",
            candidate_type="oss_project",
            attio_status="unknown",
            evidence_confidence_score=45,
            identity_type="oss_project_watch",
            identity_confidence_score=35,
            commercial_intent_score=20,
            recommended_identity_action="Monitor only",
            sources=["https://github.com/example/weak-demo"],
            why_on_radar="Example tutorial repo for a toy workflow.",
        )
    )

    assert item.recommended_action == ACTION_MONITOR_ONLY
    assert item.company_identity_quality_score < 60
    assert "identity_resolution_weak" in item.company_identity_quality_basis
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py::test_resolved_identity_upgrades_no_match_row_to_assign_owner .claude/skills/vc-signals/tests/test_radar_focus.py::test_weak_identity_demotes_unknown_oss_row_to_monitor_only -q
```

Expected: FAIL because `radar_focus.py` does not use identity-resolution fields yet.

- [ ] **Step 3: Update `score_company_identity()`**

At the beginning of `score_company_identity(candidate)`, add:

```python
    if candidate.identity_confidence_score:
        score = candidate.identity_confidence_score
        basis = [f"identity_resolution_{candidate.identity_type or 'unknown'}"]
        missing = list(candidate.missing_identity_evidence or [])
        if candidate.identity_type == "verified_company" and candidate.domain:
            score = max(score, 85)
            basis.append("resolved_verified_domain")
        elif candidate.identity_type == "oss_with_commercial_intent":
            score = max(score, 65)
            basis.append("resolved_oss_commercial_intent")
        elif candidate.identity_type in {"oss_project_watch", "insufficient_identity"}:
            score = min(score, 45)
            basis.append("identity_resolution_weak")
        return _clamp(score), basis, missing
```

- [ ] **Step 4: Update `choose_recommended_action()`**

Before current Attio status rules, add:

```python
    if candidate.recommended_identity_action in {
        ACTION_ASSIGN_OWNER,
        ACTION_REFRESH_ATTIO,
        ACTION_RESEARCH_DEEPER,
        ACTION_MONITOR_ONLY,
    }:
        if candidate.recommended_identity_action == ACTION_ASSIGN_OWNER:
            if item.company_identity_quality_score >= 70 and item.evidence_confidence_score >= 45:
                return ACTION_ASSIGN_OWNER
        if candidate.recommended_identity_action == ACTION_REFRESH_ATTIO:
            return ACTION_REFRESH_ATTIO
        if candidate.recommended_identity_action == ACTION_MONITOR_ONLY:
            return ACTION_MONITOR_ONLY
```

Do not let identity resolution force `Take meeting`.

- [ ] **Step 5: Run focus tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_focus.py .claude/skills/vc-signals/tests/test_radar_focus.py
git commit -m "Use identity resolution in focus scoring"
```

---

## Task 5: Integrate Into Weekly Run

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

Integration guardrail:

> Prefer minimal integration into the existing weekly path. Only extract `write_weekly_artifacts()` if the extraction is clean, regression-tested, and does not change `weekly-preview.md`. Add the regression test before any refactor.

- [ ] **Step 1: Add failing weekly-run test**

Add to `.claude/skills/vc-signals/tests/test_radar_run.py`:

```python
def test_weekly_run_writes_identity_resolution_artifact(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    import radar_run

    output_dir = tmp_path / "run"
    candidates = [
        radar_run.Candidate(
            name="Burrow",
            sector="Cybersecurity",
            theme="AI agent security",
            source="https://news.ycombinator.com/item?id=47761957",
            candidate_type="company_web",
            stable_key="hn:47761957",
            domain="",
            why_on_radar="Show HN: Burrow - Runtime Security for AI Agents",
            sources=["https://news.ycombinator.com/item?id=47761957"],
            attio_status="no_match",
            evidence_confidence_score=30,
            investment_interest_score=40,
        )
    ]

    written = radar_run.write_weekly_artifacts(
        output_dir=output_dir,
        run_id="2026-05-11",
        candidates=candidates,
        signals=[],
        theme_signals=[],
        sector_intelligence=[],
        raw_evidence=[],
    )

    identity_path = Path(written["identity_resolution_json"])
    assert identity_path.exists()
    payload = json.loads(identity_path.read_text())
    assert payload[0]["original_name"] == "Burrow"
    assert payload[0]["identity_type"] == "launch_style_needs_identity"
    assert Path(written["weekly_focus_json"]).exists()
    assert Path(written["weekly_focus_markdown"]).exists()
```

If `write_weekly_artifacts()` does not exist yet, this task should introduce it as an extraction from the current weekly artifact-writing block. Keep the extraction deterministic and do not change rendered `weekly-preview.md` content.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_weekly_run_writes_identity_resolution_artifact -q
```

Expected: FAIL because `identity_resolution_json` is not written or `write_weekly_artifacts()` is missing.

- [ ] **Step 3: Implement artifact writing**

In `radar_run.py`:

1. Import:

```python
from identity_resolution import apply_identity_resolution
```

2. After candidate enrichment and before Attio matching/focus artifact generation, run:

```python
scored_candidates, identity_resolutions = apply_identity_resolution(scored_candidates)
```

3. Write:

```python
identity_resolution_path = output_dir / "identity-resolution.json"
identity_resolution_path.write_text(
    json.dumps([item.to_dict() for item in identity_resolutions], indent=2, sort_keys=True)
)
```

4. Add the path to the run result:

```python
"identity_resolution_json": str(identity_resolution_path)
```

If current code does not have a helper suitable for tests, extract the existing write block into:

```python
def write_weekly_artifacts(
    *,
    output_dir: Path,
    run_id: str,
    candidates: list[Candidate],
    signals: list[Signal],
    theme_signals: list[ThemeSignal],
    sector_intelligence: list[SectorIntelligence],
    raw_evidence: list[dict],
) -> dict:
    ...
```

The helper must write the same existing artifacts plus `identity-resolution.json`.

- [ ] **Step 4: Run weekly-run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Write identity resolution artifact in weekly run"
```

---

## Task 6: Read-Only Attio Re-Match After Identity Resolution

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Add failing test for Attio-safe re-match**

Add:

```python
def test_identity_resolution_runs_before_attio_matching(monkeypatch):
    import radar_run

    calls = []

    def fake_apply_identity_resolution(candidates):
        for candidate in candidates:
            candidate.domain = "burrow.security"
            candidate.attio_safe_to_match = True
            candidate.attio_match_keys = ["burrow.security", "Burrow"]
        return candidates, []

    def fake_apply_attio(candidates, attio_client=None):
        calls.append([candidate.domain for candidate in candidates])
        return candidates

    monkeypatch.setattr(radar_run, "apply_identity_resolution", fake_apply_identity_resolution)
    monkeypatch.setattr(radar_run, "_apply_attio_to_candidates", fake_apply_attio)

    candidate = radar_run.Candidate(
        name="Burrow",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=47761957",
        candidate_type="company_web",
    )

    radar_run.prepare_candidates_for_weekly_focus([candidate], attio_client=None)

    assert calls == [["burrow.security"]]
```

If `prepare_candidates_for_weekly_focus()` does not exist, add it in this task.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_identity_resolution_runs_before_attio_matching -q
```

Expected: FAIL because the helper/order does not exist.

- [ ] **Step 3: Implement preparation helper**

Add to `radar_run.py`:

```python
def prepare_candidates_for_weekly_focus(candidates: list[Candidate], attio_client=None) -> tuple[list[Candidate], list]:
    resolved_candidates, identity_resolutions = apply_identity_resolution(candidates)
    resolved_candidates = _apply_attio_to_candidates(resolved_candidates, attio_client)
    return resolved_candidates, identity_resolutions
```

Then replace the inline sequence:

```python
scored_candidates = apply_candidate_enrichment(scored_candidates)
scored_candidates = _apply_attio_to_candidates(scored_candidates, _attio_client_from_env())
```

with:

```python
scored_candidates = apply_candidate_enrichment(scored_candidates)
scored_candidates, identity_resolutions = prepare_candidates_for_weekly_focus(
    scored_candidates,
    _attio_client_from_env(),
)
```

Make sure `identity_resolutions` is the list written to `identity-resolution.json`.

- [ ] **Step 4: Run run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Run identity resolution before Attio matching"
```

---

## Task 7: Real Artifact Verification Loop

**Files:**
- Read: `docs/radar-runs/current-focus-check/candidates.json`
- Write local generated artifacts only under `docs/radar-runs/current-focus-check/`
- Do not commit generated artifacts unless explicitly requested.

- [ ] **Step 1: Rebuild current focus check from saved candidates**

Run:

```bash
python3 - <<'PY'
import json
import sys
from pathlib import Path
sys.path.insert(0, '.claude/skills/vc-signals/scripts')
from radar_models import Candidate, SectorIntelligence, ThemeSignal
from identity_resolution import apply_identity_resolution
from radar_focus import build_weekly_focus_artifact, render_weekly_focus_markdown, write_feedback_scaffold, write_weekly_focus_json

base = Path('docs/radar-runs/current-focus-check')
candidates = [Candidate.from_dict(item) for item in json.loads((base / 'candidates.json').read_text())]
theme_signals = [ThemeSignal.from_dict(item) for item in json.loads((base / 'theme-signals.json').read_text())]
sector_intelligence = [SectorIntelligence.from_dict(item) for item in json.loads((base / 'sector-intelligence.json').read_text())]

candidates, resolutions = apply_identity_resolution(candidates)
(base / 'identity-resolution.json').write_text(json.dumps([item.to_dict() for item in resolutions], indent=2, sort_keys=True))
artifact = build_weekly_focus_artifact(candidates=candidates, theme_signals=theme_signals, sector_intelligence=sector_intelligence, run_id='2026-05-07')
write_weekly_focus_json(artifact, base / 'weekly-focus.json')
(base / 'weekly-focus.md').write_text(render_weekly_focus_markdown(artifact))
write_feedback_scaffold('2026-05-07', artifact.partner_focus, base / 'feedback.json')

print('partner focus:')
for item in artifact.partner_focus:
    print(f'- {item.name}: {item.identity_type if hasattr(item, "identity_type") else ""} | {item.recommended_action} | {item.company_identity_quality_score}')
print('identity resolutions:', len(resolutions))
PY
```

- [ ] **Step 2: Inspect Burrow-like rows**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('docs/radar-runs/current-focus-check/identity-resolution.json').read_text())
for item in data:
    if item['original_name'].lower() == 'burrow' or item['identity_type'] == 'launch_style_needs_identity':
        print(json.dumps(item, indent=2))
PY
```

Expected for the current saved artifact:

- Burrow remains `launch_style_needs_identity` unless a domain/founder already exists in the saved candidate.
- Burrow remains `Research deeper` if identity evidence is still missing.
- No row is upgraded to `Assign owner` without verified domain and sufficient identity/commercial score.

- [ ] **Step 3: Inspect `weekly-focus.md` first 120 lines**

Run:

```bash
sed -n '1,120p' docs/radar-runs/current-focus-check/weekly-focus.md
```

Expected:

- Executive Snapshot remains understandable.
- Weak identity rows are not falsely owner-ready.
- Any upgraded row has visible stronger identity evidence.
- `weekly-preview.md` remains unchanged.

- [ ] **Step 4: Check weekly-preview unchanged**

Run:

```bash
git diff -- docs/radar-runs/current-focus-check/weekly-preview.md docs/radar-runs/current/weekly-preview.md
```

Expected: no diff.

---

## Task 8: Full Test And Product Acceptance Review

**Files:**
- All touched source/tests.

- [ ] **Step 1: Run full tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Check generated files are not staged**

Run:

```bash
git status --short
```

Expected:

- Source and test files are committed.
- Generated `docs/radar-runs/...` artifacts are untracked or unstaged.
- `candidate_history.json` remains ignored/local runtime state.

- [ ] **Step 3: Product acceptance review**

Open:

```bash
sed -n '1,220p' docs/radar-runs/current-focus-check/weekly-focus.md
```

Answer:

- Does the artifact still clearly say when it is a research queue?
- Did any row become `Assign owner` only with verified domain, sufficient identity confidence, and commercial intent?
- Did weak OSS/project-only rows get demoted or stay `Research deeper` / `Monitor only`?
- Is Burrow-style launch evidence handled honestly?
- Can an associate see the identity-resolution target and missing evidence without reading JSON?

- [ ] **Step 4: Commit final integration if needed**

If any Task 7/8 source changes were required:

```bash
git add .claude/skills/vc-signals/scripts .claude/skills/vc-signals/tests docs/superpowers/plans/2026-05-07-phase-2-identity-resolution.md
git commit -m "Complete identity resolution phase 2"
```

---

## Definition Of Done

Phase 2 is done when:

- `IdentityResolution` exists and roundtrips through JSON.
- Existing focus rows can be resolved without broad new source adapters.
- The resolver parses already-present evidence URLs, including HN item outbound URLs and GitHub owner/repo URLs.
- HN fetch or parsing failures fail closed and keep launch-style rows in `Research deeper`.
- GitHub-only rows can produce project identity but must not infer a company domain.
- Burrow-style launch rows are explicitly classified as `launch_style_needs_identity` when domain/founder evidence is missing.
- Rows with verified domain + founder/maintainer + commercial intent can move from `Research deeper` to `Assign owner` when Attio status supports it.
- `Assign owner` requires actionable identity: verified domain, or founder/maintainer identity plus launch evidence.
- Stale/passed Attio rows with resolved identity can move to `Refresh Attio`.
- Weak OSS/project rows are demoted or kept out of Partner Focus when identity/commercial intent is weak.
- `identity-resolution.json` is written in weekly runs.
- Identity resolution runs before read-only Attio matching.
- `weekly-preview.md` remains unchanged.
- No broad new source adapters are added.
- Full tests pass.
- A real regenerated artifact passes the product acceptance review.

## Verification Commands

Run these before asking for review:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py -q
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py -q
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py -q
python3 -m pytest .claude/skills/vc-signals/tests -q
git diff -- docs/radar-runs/current-focus-check/weekly-preview.md docs/radar-runs/current/weekly-preview.md
```

Expected:

- All tests pass.
- `weekly-preview.md` diff is empty.
- Generated run artifacts are not committed unless explicitly requested.
