# Weekly Focus Phase 1A/1B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate `weekly-focus.json`, render `weekly-focus.md`, and scaffold `feedback.json` from the existing weekly radar artifacts so Alex can quickly see the top companies/projects, market movements, Marathon/Attio context, and recommended actions.

**Architecture:** Add a focused weekly-focus layer beside the current radar pipeline. `weekly-preview.md` remains unchanged; the new layer converts existing `Candidate`, `Signal`, `ThemeSignal`, and `SectorIntelligence` objects into `FocusItem`, `MarketMovement`, and `WeeklyFocusArtifact`, writes JSON first, then renders Markdown from JSON. Scoring is deterministic and basis-backed; no live LLM calls or new sources are added.

**Tech Stack:** Python dataclasses, existing `.claude/skills/vc-signals/scripts` modules, pytest, JSON artifacts, Markdown rendering.

---

## Product Guardrails

This plan implements only Phase 1A and Phase 1B from:

- `docs/superpowers/specs/2026-05-07-market-movement-intelligence-product-spec.md`
- `docs/superpowers/specs/2026-05-07-weekly-focus-market-movement-design.md`

Explicitly excluded:

- new source adapters
- X / LinkedIn / Product Hunt / package registries
- movement time-series
- live LLM dependency
- Slack delivery
- Attio writeback
- changes to `weekly-preview.md`

Implementation principle:

> Build the smallest model/renderer that can produce useful `weekly-focus.json` and `weekly-focus.md` from current artifacts with deterministic tests.

## Files And Responsibilities

### New Files

- `.claude/skills/vc-signals/scripts/radar_focus.py`
  - Defines focus scoring, gates, action selection, movement grouping, artifact construction, JSON writing, Markdown rendering, and feedback scaffold generation.
  - Does not call external APIs.
  - Does not mutate existing candidates.

- `.claude/skills/vc-signals/tests/test_radar_focus.py`
  - Unit tests for focus models, scoring basis, eligibility gates, action gates, rendering, output limits, and feedback scaffold.

### Modified Files

- `.claude/skills/vc-signals/scripts/radar_models.py`
  - Add `FocusItem`, `MarketMovement`, `ExecutiveSnapshot`, `WeeklyFocusArtifact`, and `AlexFeedback` dataclasses with `to_dict()` / `from_dict()`.

- `.claude/skills/vc-signals/tests/test_radar_models.py`
  - Add roundtrip tests for new focus dataclasses.

- `.claude/skills/vc-signals/scripts/radar_run.py`
  - Import `build_weekly_focus_artifact`, `render_weekly_focus_markdown`, `write_feedback_scaffold`.
  - Write `weekly-focus.json`, `weekly-focus.md`, and `feedback.json` after `weekly-preview.md` is written.
  - Include paths in the weekly command JSON result.
  - Do not change `_render_weekly_brief()` arguments or `weekly-preview.md` content.

- `.claude/skills/vc-signals/tests/test_radar_run.py`
  - Verify weekly run writes focus artifacts.
  - Verify `weekly-preview.md` content is still produced by the existing renderer path.

### Existing Files To Read, Not Modify

- `.claude/skills/vc-signals/scripts/radar_render.py`
  - Keep unchanged in this phase.

- `.claude/skills/vc-signals/scripts/radar_partner_review.py`
  - Keep unchanged unless tests reveal existing ranking is reused incorrectly.

---

## Model Definitions

Add these dataclasses to `.claude/skills/vc-signals/scripts/radar_models.py`.

```python
@dataclass
class FocusItem:
    id: str
    rank: int = 0
    name: str = ""
    company_domain: str = ""
    project_url: str = ""
    market_movement_id: str = ""
    market_movement: str = ""
    market_sector: str = ""
    why_focus_this_week: str = ""
    who_is_talking: list[str] = field(default_factory=list)
    talker_types: list[str] = field(default_factory=list)
    talker_type_confidence: str = "Low"
    evidence_snapshot: list[str] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    attio_status: str = "unknown"
    attio_owner: str = ""
    attio_last_touch: str = ""
    recommended_action: str = "Research deeper"
    investment_interest_score: int = 0
    evidence_confidence_score: int = 0
    focus_priority_score: int = 0
    actionability_score: int = 0
    freshness_score: int = 0
    market_movement_score: int = 0
    marathon_fit_score: int = 0
    noise_risk_score: int = 0
    consensus_risk_score: int = 0
    company_identity_quality_score: int = 0
    company_identity_quality_basis: list[str] = field(default_factory=list)
    focus_priority_basis: list[str] = field(default_factory=list)
    actionability_basis: list[str] = field(default_factory=list)
    freshness_basis: list[str] = field(default_factory=list)
    market_movement_basis: list[str] = field(default_factory=list)
    marathon_fit_basis: list[str] = field(default_factory=list)
    noise_risk_basis: list[str] = field(default_factory=list)
    consensus_risk_basis: list[str] = field(default_factory=list)
    movement_assignment_method: str = "direct_match"
    movement_assignment_confidence: str = "Medium"
    movement_assignment_evidence_url: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    seen_in_prior_runs: bool = False
    weekly_tag: str = ""
    new_evidence_this_week: list[str] = field(default_factory=list)
    why_this_may_be_noise: str = ""
    skepticism_events: list[str] = field(default_factory=list)
    source_candidate_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "FocusItem":
        return cls(**_known_payload(cls, payload))


@dataclass
class MarketMovement:
    id: str
    name: str = ""
    market_sector: str = ""
    what_is_moving: str = ""
    why_now: str = ""
    why_not_now: str = ""
    buyer_persona: list[str] = field(default_factory=list)
    user_persona: list[str] = field(default_factory=list)
    budget_owner: str = ""
    who_is_talking: list[str] = field(default_factory=list)
    talker_mix: dict = field(default_factory=dict)
    companies_or_projects: list[str] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    skepticism_events: list[str] = field(default_factory=list)
    momentum_label: str = "PERSISTENT"
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "MarketMovement":
        return cls(**_known_payload(cls, payload))


@dataclass
class ExecutiveSnapshot:
    top_movement: str = ""
    top_new_to_marathon: str = ""
    rows_needing_owner: int = 0
    rows_needing_attio_refresh: int = 0
    biggest_source_gap: str = ""
    top_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ExecutiveSnapshot":
        return cls(**_known_payload(cls, payload))


@dataclass
class WeeklyFocusArtifact:
    run_id: str = ""
    executive_snapshot: ExecutiveSnapshot = field(default_factory=ExecutiveSnapshot)
    partner_focus: list[FocusItem] = field(default_factory=list)
    market_movements: list[MarketMovement] = field(default_factory=list)
    new_to_marathon: list[FocusItem] = field(default_factory=list)
    workflow_view: dict[str, list[FocusItem]] = field(default_factory=dict)
    extended_watchlist: list[FocusItem] = field(default_factory=list)
    appendix: dict = field(default_factory=dict)
    source_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "executive_snapshot": self.executive_snapshot.to_dict(),
            "partner_focus": [item.to_dict() for item in self.partner_focus],
            "market_movements": [item.to_dict() for item in self.market_movements],
            "new_to_marathon": [item.to_dict() for item in self.new_to_marathon],
            "workflow_view": {
                action: [item.to_dict() for item in items]
                for action, items in self.workflow_view.items()
            },
            "extended_watchlist": [item.to_dict() for item in self.extended_watchlist],
            "appendix": deepcopy(self.appendix),
            "source_gaps": list(self.source_gaps),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "WeeklyFocusArtifact":
        snapshot = payload.get("executive_snapshot") or {}
        return cls(
            run_id=payload.get("run_id", ""),
            executive_snapshot=ExecutiveSnapshot.from_dict(snapshot),
            partner_focus=[FocusItem.from_dict(item) for item in payload.get("partner_focus", [])],
            market_movements=[MarketMovement.from_dict(item) for item in payload.get("market_movements", [])],
            new_to_marathon=[FocusItem.from_dict(item) for item in payload.get("new_to_marathon", [])],
            workflow_view={
                action: [FocusItem.from_dict(item) for item in items]
                for action, items in (payload.get("workflow_view") or {}).items()
            },
            extended_watchlist=[FocusItem.from_dict(item) for item in payload.get("extended_watchlist", [])],
            appendix=deepcopy(payload.get("appendix") or {}),
            source_gaps=list(payload.get("source_gaps") or []),
        )


@dataclass
class AlexFeedback:
    run_id: str
    feedback: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "AlexFeedback":
        return cls(**_known_payload(cls, payload))
```

Also update the import line in `radar_models.py`:

```python
from copy import deepcopy
```

This import already exists today and should be reused by `WeeklyFocusArtifact.to_dict()`.

---

## Task 1: Focus Models

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_models.py`

- [ ] **Step 1: Write failing model roundtrip tests**

Append these tests to `.claude/skills/vc-signals/tests/test_radar_models.py`:

```python
def test_focus_item_roundtrips_and_ignores_extra_fields():
    from radar_models import FocusItem

    item = FocusItem(
        id="agent-security_agentshield",
        name="AgentShield",
        market_movement="AI agent permission security",
        evidence_urls=["https://github.com/affaan-m/agentshield"],
        company_identity_quality_score=60,
        company_identity_quality_basis=["maintainer_identity_present"],
        actionability_score=70,
        actionability_basis=["clear_founder_to_investigate"],
        focus_priority_score=62,
        focus_priority_basis=["formula_v1"],
        missing_evidence=["no verified company domain"],
        recommended_action="Research deeper",
    )

    payload = item.to_dict()
    payload["future_field"] = "ignored"

    restored = FocusItem.from_dict(payload)

    assert restored.id == "agent-security_agentshield"
    assert restored.name == "AgentShield"
    assert restored.evidence_urls == ["https://github.com/affaan-m/agentshield"]
    assert restored.company_identity_quality_basis == ["maintainer_identity_present"]
    assert restored.missing_evidence == ["no verified company domain"]


def test_weekly_focus_artifact_roundtrips_nested_models():
    from radar_models import ExecutiveSnapshot, FocusItem, MarketMovement, WeeklyFocusArtifact

    focus = FocusItem(id="mintmcp", name="MintMCP", recommended_action="Assign owner")
    movement = MarketMovement(id="mcp-security", name="MCP security", companies_or_projects=["MintMCP"])
    artifact = WeeklyFocusArtifact(
        run_id="2026-05-11",
        executive_snapshot=ExecutiveSnapshot(
            top_movement="MCP security",
            top_new_to_marathon="MintMCP",
            rows_needing_owner=1,
        ),
        partner_focus=[focus],
        market_movements=[movement],
        workflow_view={"Assign owner": [focus]},
        source_gaps=["No X adapter configured."],
    )

    restored = WeeklyFocusArtifact.from_dict(artifact.to_dict())

    assert restored.run_id == "2026-05-11"
    assert restored.executive_snapshot.top_movement == "MCP security"
    assert restored.partner_focus[0].name == "MintMCP"
    assert restored.market_movements[0].companies_or_projects == ["MintMCP"]
    assert restored.workflow_view["Assign owner"][0].id == "mintmcp"
    assert restored.source_gaps == ["No X adapter configured."]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_models.py::test_focus_item_roundtrips_and_ignores_extra_fields \
  .claude/skills/vc-signals/tests/test_radar_models.py::test_weekly_focus_artifact_roundtrips_nested_models \
  -q
```

Expected:

- FAIL with `ImportError` or `AttributeError` because focus models do not exist.

- [ ] **Step 3: Add the dataclasses**

Add the dataclasses from the **Model Definitions** section to `.claude/skills/vc-signals/scripts/radar_models.py` after `SynthesisResult` and before `RejectedSignal`.

- [ ] **Step 4: Run model tests**

Run:

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_models.py::test_focus_item_roundtrips_and_ignores_extra_fields \
  .claude/skills/vc-signals/tests/test_radar_models.py::test_weekly_focus_artifact_roundtrips_nested_models \
  -q
```

Expected:

- `2 passed`

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/tests/test_radar_models.py
git commit -m "Add weekly focus artifact models"
```

---

## Task 2: Focus Scoring, Gates, And Action Selection

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_focus.py`
- Create/Modify: `.claude/skills/vc-signals/tests/test_radar_focus.py`

### Scoring Functions

Implement these functions in `radar_focus.py`:

```python
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from radar_models import (
    AlexFeedback,
    Candidate,
    ExecutiveSnapshot,
    FocusItem,
    MarketMovement,
    SectorIntelligence,
    ThemeSignal,
    WeeklyFocusArtifact,
)


ACTION_ASSIGN_OWNER = "Assign owner"
ACTION_RESEARCH_DEEPER = "Research deeper"
ACTION_REFRESH_ATTIO = "Refresh Attio"
ACTION_TAKE_MEETING = "Take meeting"
ACTION_MONITOR_ONLY = "Monitor only"

ATTIO_NEW_STATUSES = {"unknown", "", "no_match", "not_found", "new"}
ATTIO_STALE_TERMS = ("stale", "no owner", "no_owner", "passed")


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))


def _stable_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "unknown"


def score_company_identity(candidate: Candidate) -> tuple[int, list[str], list[str]]:
    basis = []
    missing = []
    score = 20

    if candidate.domain:
        score = max(score, 80)
        basis.append("verified_domain_present")
    else:
        missing.append("no verified company domain")

    if candidate.company_linkedin:
        score = max(score, 80)
        basis.append("company_linkedin_present")

    if candidate.founder_profiles or candidate.founders or candidate.maintainer_profiles:
        score = max(score, 60)
        basis.append("founder_or_maintainer_identity_present")
    else:
        missing.append("no founder identity")

    sources = [source for source in candidate.sources if source]
    if sources:
        basis.append("evidence_urls_present")
    if any("ycombinator.com" in source or "launch" in source.lower() or "show hn" in source.lower() for source in sources):
        score = max(score, 80)
        basis.append("launch_source_present")

    if candidate.attio_status and candidate.attio_status != "unknown":
        score = max(score, 70)
        basis.append("attio_match_present")

    if candidate.candidate_type == "oss_project":
        if candidate.maintainer_profiles or candidate.oss_company_formation_score >= 50:
            score = max(score, 60)
            basis.append("oss_project_with_company_formation_signal")
        else:
            score = min(score, 40)
            basis.append("oss_project_commercial_intent_unclear")

    if score <= 20:
        basis.append("inferred_name_only")

    return _clamp(score), basis, missing


def score_actionability(candidate: Candidate, identity_score: int) -> tuple[int, list[str]]:
    basis = []
    score = 35
    status = (candidate.attio_status or "unknown").lower()
    staleness = " ".join([candidate.attio_staleness_reason or "", candidate.attio_action or ""]).lower()

    if status in ATTIO_NEW_STATUSES and identity_score >= 60:
        score += 25
        basis.append("new_to_attio")
    if "stale" in staleness or "stale" in status:
        score += 20
        basis.append("attio_stale_with_new_signal")
    if "no owner" in staleness or "no_owner" in status or (candidate.attio_status != "unknown" and not candidate.attio_owner):
        score += 15
        basis.append("attio_no_owner")
    if "passed" in status or "passed" in staleness:
        score += 10
        basis.append("passed_with_new_signal")
    if candidate.founder_profiles or candidate.maintainer_profiles:
        score += 10
        basis.append("clear_founder_to_investigate")
    if identity_score < 40:
        score -= 20
        basis.append("no_company_identity")
    if not basis:
        basis.append("baseline_actionability")

    return _clamp(score), basis


def score_freshness(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 40
    tag = (candidate.weekly_tag or "").upper()
    if tag == "NEW":
        score += 35
        basis.append("weekly_tag_new")
    elif tag in {"RETURNING", "CHANGED"}:
        score += 25
        basis.append(f"weekly_tag_{tag.lower()}")
    elif tag == "PERSISTENT":
        score += 10
        basis.append("weekly_tag_persistent")
    if candidate.stars_30d >= 100:
        score += 15
        basis.append("high_oss_star_velocity")
    if not basis:
        basis.append("no_strong_freshness_signal")
    return _clamp(score), basis


def score_marathon_fit(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 45
    sector = (candidate.market_sector or candidate.sector or "").lower()
    target_terms = ("devtools", "cybersecurity", "ai infra", "vertical ai", "data infra", "oss")
    if any(term in sector for term in target_terms):
        score += 25
        basis.append("target_sector")
    if candidate.stage and any(stage in candidate.stage.lower() for stage in ("seed", "series a", "series b", "pre-seed")):
        score += 20
        basis.append("seed_to_series_b_stage")
    elif not candidate.stage:
        score += 10
        basis.append("stage_unknown_but_not_disqualifying")
    if candidate.domain or candidate.attio_status != "unknown":
        score += 10
        basis.append("actionable_company_or_attio_context")
    text = " ".join([candidate.name, candidate.why_on_radar, candidate.theme]).lower()
    if any(term in text for term in ("consumer", "prosumer", "creator")):
        score -= 20
        basis.append("possible_consumer_or_prosumer_fit_risk")
    if any(term in text for term in ("series c", "series d", "unicorn", "$1b")):
        score -= 25
        basis.append("likely_late_or_consensus")
    return _clamp(score), basis or ["baseline_marathon_fit"]


def score_noise_risk(candidate: Candidate, identity_score: int) -> tuple[int, list[str]]:
    basis = []
    score = 35
    text = " ".join([candidate.why_on_radar, candidate.why_this_may_be_noise, candidate.theme]).lower()
    if identity_score < 60:
        score += 25
        basis.append("weak_company_identity")
    if candidate.candidate_type == "oss_project" and candidate.oss_company_formation_score < 50:
        score += 15
        basis.append("oss_commercialization_unclear")
    if "hype" in text or "crowded" in text:
        score += 15
        basis.append("explicit_hype_or_crowding_risk")
    if not candidate.sources:
        score += 20
        basis.append("no_evidence_url")
    return _clamp(score), basis or ["baseline_noise_risk"]


def score_consensus_risk(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 20
    text = " ".join([candidate.stage, candidate.raised, candidate.headcount, candidate.why_on_radar]).lower()
    if any(term in text for term in ("series c", "series d", "series e")):
        score += 40
        basis.append("series_c_or_later")
    if any(term in text for term in ("unicorn", "$1b", "$100m", "$200m")):
        score += 30
        basis.append("large_funding_or_valuation_signal")
    if "consensus" in text or "top-tier" in text:
        score += 20
        basis.append("consensus_chatter")
    if candidate.attio_status and candidate.attio_status.lower() in {"active", "passed"}:
        score += 10
        basis.append(f"attio_{candidate.attio_status.lower()}")
    return _clamp(score), basis or ["low_consensus_signal"]


def score_market_movement(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 45
    if candidate.theme:
        score += 15
        basis.append("theme_present")
    if candidate.source_count >= 2:
        score += 15
        basis.append("multiple_sources")
    if candidate.market_sector:
        score += 10
        basis.append("market_sector_classified")
    return _clamp(score), basis or ["baseline_market_movement"]


def compute_focus_priority(
    *,
    investment_interest_score: int,
    actionability_score: int,
    freshness_score: int,
    market_movement_score: int,
    marathon_fit_score: int,
    evidence_confidence_score: int,
    noise_risk_score: int,
    consensus_risk_score: int,
) -> tuple[int, list[str]]:
    score = (
        0.25 * investment_interest_score
        + 0.20 * actionability_score
        + 0.15 * freshness_score
        + 0.15 * market_movement_score
        + 0.15 * marathon_fit_score
        + 0.10 * evidence_confidence_score
        - 0.20 * noise_risk_score
        - 0.15 * consensus_risk_score
    )
    return _clamp(round(score)), ["focus_formula_v1"]
```

### Eligibility And Actions

Implement:

```python
def can_take_meeting(item: FocusItem) -> bool:
    return (
        item.evidence_confidence_score >= 75
        and item.company_identity_quality_score >= 80
        and item.actionability_score >= 75
        and item.noise_risk_score <= 40
        and not (item.attio_status.lower() == "active" and item.attio_owner)
    )


def choose_recommended_action(candidate: Candidate, item: FocusItem) -> str:
    status = (candidate.attio_status or "unknown").lower()
    staleness = " ".join([candidate.attio_staleness_reason or "", candidate.attio_action or ""]).lower()
    if can_take_meeting(item):
        return ACTION_TAKE_MEETING
    if "stale" in status or "stale" in staleness or "passed" in status or "passed" in staleness:
        return ACTION_REFRESH_ATTIO
    if item.company_identity_quality_score < 60 or item.evidence_confidence_score < 45:
        return ACTION_RESEARCH_DEEPER
    if item.attio_status.lower() in ATTIO_NEW_STATUSES or not candidate.attio_owner:
        return ACTION_ASSIGN_OWNER
    return ACTION_MONITOR_ONLY


def is_partner_focus_eligible(item: FocusItem) -> bool:
    return (
        item.company_identity_quality_score >= 60
        and len(item.evidence_urls) > 0
        and "pure_llm_inferred" not in item.focus_priority_basis
        and item.noise_risk_score < 70
        and bool(item.recommended_action)
        and (
            bool(item.company_domain)
            or bool(item.project_url)
            or item.attio_status.lower() in {"no_match", "no_owner", "stale", "passed", "unknown"}
        )
        and not (item.recommended_action == ACTION_MONITOR_ONLY and item.focus_priority_score < 85)
    )
```

### Tests

- [ ] **Step 1: Write failing scoring and gate tests**

Create `.claude/skills/vc-signals/tests/test_radar_focus.py` with:

```python
from radar_models import Candidate, FocusItem


def _candidate(**overrides):
    data = {
        "name": "AgentShield",
        "sector": "Cybersecurity",
        "market_sector": "Cybersecurity",
        "theme": "AI agent permission security",
        "source": "https://github.com/affaan-m/agentshield",
        "candidate_type": "oss_project",
        "why_on_radar": "AI agent security scanner with MCP permissions focus.",
        "why_this_may_be_noise": "Commercial intent needs verification.",
        "sources": ["https://github.com/affaan-m/agentshield"],
        "source_count": 1,
        "investment_interest_score": 70,
        "evidence_confidence_score": 50,
        "attio_status": "unknown",
        "weekly_tag": "NEW",
        "maintainer_profiles": [{"name": "affaan-m"}],
        "oss_company_formation_score": 60,
    }
    data.update(overrides)
    return Candidate(**data)


def test_company_identity_score_records_basis_and_missing_evidence():
    from radar_focus import score_company_identity

    score, basis, missing = score_company_identity(_candidate(domain="agentshield.dev"))

    assert score >= 80
    assert "verified_domain_present" in basis
    assert "evidence_urls_present" in basis
    assert "no verified company domain" not in missing


def test_partner_focus_requires_evidence_url_and_identity_quality():
    from radar_focus import is_partner_focus_eligible

    item = FocusItem(
        id="weak",
        name="Weak Project",
        company_identity_quality_score=40,
        evidence_urls=[],
        noise_risk_score=30,
        recommended_action="Research deeper",
        focus_priority_basis=["focus_formula_v1"],
        project_url="https://github.com/example/weak",
    )

    assert is_partner_focus_eligible(item) is False


def test_partner_focus_accepts_credible_actionable_project():
    from radar_focus import is_partner_focus_eligible

    item = FocusItem(
        id="agentshield",
        name="AgentShield",
        company_identity_quality_score=60,
        evidence_urls=["https://github.com/affaan-m/agentshield"],
        noise_risk_score=45,
        recommended_action="Research deeper",
        focus_priority_basis=["focus_formula_v1"],
        project_url="https://github.com/affaan-m/agentshield",
    )

    assert is_partner_focus_eligible(item) is True


def test_take_meeting_gate_is_strict():
    from radar_focus import ACTION_TAKE_MEETING, can_take_meeting, choose_recommended_action

    candidate = _candidate(domain="agentshield.dev", evidence_confidence_score=74)
    item = FocusItem(
        id="agentshield",
        evidence_confidence_score=74,
        company_identity_quality_score=90,
        actionability_score=90,
        noise_risk_score=20,
        attio_status="unknown",
    )

    assert can_take_meeting(item) is False
    assert choose_recommended_action(candidate, item) != ACTION_TAKE_MEETING


def test_take_meeting_allowed_only_when_all_gates_clear():
    from radar_focus import ACTION_TAKE_MEETING, can_take_meeting, choose_recommended_action

    candidate = _candidate(domain="agentshield.dev", evidence_confidence_score=85)
    item = FocusItem(
        id="agentshield",
        evidence_confidence_score=85,
        company_identity_quality_score=90,
        actionability_score=90,
        noise_risk_score=20,
        attio_status="unknown",
    )

    assert can_take_meeting(item) is True
    assert choose_recommended_action(candidate, item) == ACTION_TAKE_MEETING
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected:

- FAIL because `radar_focus.py` does not exist.

- [ ] **Step 3: Create scoring/gate implementation**

Create `.claude/skills/vc-signals/scripts/radar_focus.py` with the scoring and eligibility code from this task.

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected:

- These five tests pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_focus.py .claude/skills/vc-signals/tests/test_radar_focus.py
git commit -m "Add weekly focus scoring and gates"
```

---

## Task 3: Candidate To FocusItem Mapping

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_focus.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_focus.py`

### Mapping Logic

Add:

```python
def _market_sector(candidate: Candidate) -> str:
    return candidate.market_sector or candidate.sector or "Unclassified"


def _source_urls(candidate: Candidate) -> list[str]:
    urls = [source for source in candidate.sources if source and source.startswith(("http://", "https://"))]
    if candidate.source and candidate.source.startswith(("http://", "https://")):
        urls.append(candidate.source)
    return list(dict.fromkeys(urls))


def _project_url(candidate: Candidate) -> str:
    for url in _source_urls(candidate):
        if "github.com" in url:
            return url
    return ""


def _movement_name(candidate: Candidate) -> str:
    return candidate.theme or _market_sector(candidate)


def _movement_id(candidate: Candidate) -> str:
    return _stable_id(f"{_market_sector(candidate)}-{_movement_name(candidate)}")


def _talker_types(candidate: Candidate) -> tuple[list[str], str, list[str]]:
    if candidate.founder_profiles:
        return ["founder"], "Medium", ["founder/company evidence"]
    if candidate.maintainer_profiles or candidate.candidate_type == "oss_project":
        return ["oss_maintainer"], "Medium", ["OSS maintainer/project evidence"]
    if candidate.source_lane in {"Reddit", "Hacker News"}:
        return ["practitioner"], "Medium", [candidate.source_lane]
    return ["unknown"], "Low", ["actor unclear"]


def build_focus_item(candidate: Candidate) -> FocusItem:
    identity_score, identity_basis, missing = score_company_identity(candidate)
    actionability_score, actionability_basis = score_actionability(candidate, identity_score)
    freshness_score, freshness_basis = score_freshness(candidate)
    movement_score, movement_basis = score_market_movement(candidate)
    marathon_fit_score, marathon_fit_basis = score_marathon_fit(candidate)
    noise_score, noise_basis = score_noise_risk(candidate, identity_score)
    consensus_score, consensus_basis = score_consensus_risk(candidate)
    focus_score, focus_basis = compute_focus_priority(
        investment_interest_score=candidate.investment_interest_score,
        actionability_score=actionability_score,
        freshness_score=freshness_score,
        market_movement_score=movement_score,
        marathon_fit_score=marathon_fit_score,
        evidence_confidence_score=candidate.evidence_confidence_score,
        noise_risk_score=noise_score,
        consensus_risk_score=consensus_score,
    )
    talker_types, talker_confidence, who_is_talking = _talker_types(candidate)
    urls = _source_urls(candidate)
    movement_id = _movement_id(candidate)
    item = FocusItem(
        id=candidate.stable_key or _stable_id(candidate.name),
        name=candidate.name,
        company_domain=candidate.domain,
        project_url=_project_url(candidate),
        market_movement_id=movement_id,
        market_movement=_movement_name(candidate),
        market_sector=_market_sector(candidate),
        why_focus_this_week=candidate.why_on_radar,
        who_is_talking=who_is_talking,
        talker_types=talker_types,
        talker_type_confidence=talker_confidence,
        evidence_snapshot=[candidate.why_on_radar] if candidate.why_on_radar else [],
        evidence_urls=urls,
        missing_evidence=missing,
        attio_status=candidate.attio_status,
        attio_owner=candidate.attio_owner,
        attio_last_touch=candidate.attio_last_interaction,
        investment_interest_score=candidate.investment_interest_score,
        evidence_confidence_score=candidate.evidence_confidence_score,
        actionability_score=actionability_score,
        freshness_score=freshness_score,
        market_movement_score=movement_score,
        marathon_fit_score=marathon_fit_score,
        noise_risk_score=noise_score,
        consensus_risk_score=consensus_score,
        company_identity_quality_score=identity_score,
        company_identity_quality_basis=identity_basis,
        actionability_basis=actionability_basis,
        freshness_basis=freshness_basis,
        market_movement_basis=movement_basis,
        marathon_fit_basis=marathon_fit_basis,
        noise_risk_basis=noise_basis,
        consensus_risk_basis=consensus_basis,
        focus_priority_score=focus_score,
        focus_priority_basis=focus_basis,
        movement_assignment_method="direct_match",
        movement_assignment_confidence="Medium" if candidate.theme else "Low",
        movement_assignment_evidence_url=urls[0] if urls else "",
        first_seen_at="",
        last_seen_at="",
        seen_in_prior_runs=bool(candidate.weekly_tag and candidate.weekly_tag != "NEW"),
        weekly_tag=candidate.weekly_tag,
        new_evidence_this_week=urls[:2],
        why_this_may_be_noise=candidate.why_this_may_be_noise,
        skepticism_events=[candidate.why_this_may_be_noise] if candidate.why_this_may_be_noise else [],
        source_candidate_id=candidate.stable_key or candidate.name,
    )
    item.recommended_action = choose_recommended_action(candidate, item)
    return item
```

### Tests

- [ ] **Step 1: Add mapping tests**

Append:

```python
def test_build_focus_item_includes_basis_missing_evidence_and_action():
    from radar_focus import build_focus_item

    item = build_focus_item(_candidate(domain="", attio_status="unknown"))

    assert item.name == "AgentShield"
    assert item.market_movement == "AI agent permission security"
    assert item.company_identity_quality_basis
    assert item.actionability_basis
    assert item.focus_priority_basis == ["focus_formula_v1"]
    assert "no verified company domain" in item.missing_evidence
    assert item.recommended_action in {"Assign owner", "Research deeper", "Refresh Attio", "Monitor only"}


def test_build_focus_item_uses_attio_stale_for_refresh_action():
    from radar_focus import ACTION_REFRESH_ATTIO, build_focus_item

    item = build_focus_item(
        _candidate(
            domain="agentshield.dev",
            attio_status="stale",
            attio_staleness_reason="No interaction in 180 days",
        )
    )

    assert item.recommended_action == ACTION_REFRESH_ATTIO
    assert "attio_stale_with_new_signal" in item.actionability_basis
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_focus.py::test_build_focus_item_includes_basis_missing_evidence_and_action \
  .claude/skills/vc-signals/tests/test_radar_focus.py::test_build_focus_item_uses_attio_stale_for_refresh_action \
  -q
```

Expected:

- FAIL because `build_focus_item` is not implemented.

- [ ] **Step 3: Implement mapping**

Add mapping code above to `radar_focus.py`.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected:

- All `test_radar_focus.py` tests pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_focus.py .claude/skills/vc-signals/tests/test_radar_focus.py
git commit -m "Map radar candidates to focus items"
```

---

## Task 4: Weekly Focus Artifact Builder

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_focus.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_focus.py`

### Artifact Construction

Add:

```python
WORKFLOW_ACTIONS = [
    ACTION_ASSIGN_OWNER,
    ACTION_RESEARCH_DEEPER,
    ACTION_REFRESH_ATTIO,
    ACTION_TAKE_MEETING,
    ACTION_MONITOR_ONLY,
]


def _rank_focus_items(items: list[FocusItem]) -> list[FocusItem]:
    ranked = sorted(
        items,
        key=lambda item: (
            item.focus_priority_score,
            item.investment_interest_score,
            item.evidence_confidence_score,
        ),
        reverse=True,
    )
    for index, item in enumerate(ranked, start=1):
        item.rank = index
    return ranked


def _cap_oss_project_only(items: list[FocusItem], *, max_oss: int = 5) -> list[FocusItem]:
    kept = []
    oss_count = 0
    for item in items:
        is_project_only = bool(item.project_url) and not item.company_domain
        if is_project_only:
            if oss_count >= max_oss:
                continue
            oss_count += 1
        kept.append(item)
    return kept


def build_market_movements(items: list[FocusItem], theme_signals: list[ThemeSignal] | None = None) -> list[MarketMovement]:
    grouped = defaultdict(list)
    for item in items:
        grouped[item.market_movement_id].append(item)

    movements = []
    for movement_id, group in grouped.items():
        first = group[0]
        evidence_urls = []
        for item in group:
            evidence_urls.extend(item.evidence_urls[:2])
        evidence_urls = list(dict.fromkeys(evidence_urls))
        talker_mix = Counter(talker for item in group for talker in item.talker_types)
        movements.append(
            MarketMovement(
                id=movement_id,
                name=first.market_movement,
                market_sector=first.market_sector,
                what_is_moving=f"{first.market_movement} is showing enough signal to attach companies/projects.",
                why_now=first.why_focus_this_week,
                why_not_now=first.why_this_may_be_noise,
                who_is_talking=list(dict.fromkeys(talker for item in group for talker in item.who_is_talking)),
                talker_mix=dict(talker_mix),
                companies_or_projects=[item.name for item in group[:6]],
                evidence_urls=evidence_urls[:5],
                skepticism_events=[item.why_this_may_be_noise for item in group if item.why_this_may_be_noise][:5],
                momentum_label="NEW" if any(item.weekly_tag == "NEW" for item in group) else "PERSISTENT",
                confidence="Medium" if len(group) >= 2 else "Low",
            )
        )

    return sorted(movements, key=lambda movement: len(movement.companies_or_projects), reverse=True)[:6]


def _new_to_marathon(items: list[FocusItem]) -> list[FocusItem]:
    selected = []
    for item in items:
        status = item.attio_status.lower()
        basis_text = " ".join(item.actionability_basis).lower()
        if status in ATTIO_NEW_STATUSES or "attio_no_owner" in basis_text or "attio_stale" in basis_text or "passed" in basis_text:
            selected.append(item)
    return selected[:10]


def _workflow_view(items: list[FocusItem]) -> dict[str, list[FocusItem]]:
    grouped = {action: [] for action in WORKFLOW_ACTIONS}
    for item in items:
        grouped.setdefault(item.recommended_action, []).append(item)
    return {action: rows for action, rows in grouped.items() if rows}


def _source_gaps(sector_intelligence: list[SectorIntelligence] | None) -> list[str]:
    gaps = [
        "No X/Product Hunt/package-registry adapters in Phase 1A/1B; focus list is based on current candidates, signals, and Attio fields only."
    ]
    for item in sector_intelligence or []:
        if item.source_errors:
            gaps.append(f"{item.market_sector}: {'; '.join(item.source_errors)}")
        elif "grounded" in (item.why_no_more_companies or "").lower():
            gaps.append(f"{item.market_sector}: {item.why_no_more_companies}")
    return list(dict.fromkeys(gaps))[:8]


def _executive_snapshot(
    *,
    partner_focus: list[FocusItem],
    movements: list[MarketMovement],
    new_to_marathon: list[FocusItem],
    source_gaps: list[str],
) -> ExecutiveSnapshot:
    action_counts = Counter(item.recommended_action for item in partner_focus)
    return ExecutiveSnapshot(
        top_movement=movements[0].name if movements else "",
        top_new_to_marathon=new_to_marathon[0].name if new_to_marathon else "",
        rows_needing_owner=action_counts.get(ACTION_ASSIGN_OWNER, 0),
        rows_needing_attio_refresh=action_counts.get(ACTION_REFRESH_ATTIO, 0),
        biggest_source_gap=source_gaps[0] if source_gaps else "",
        top_actions=[f"{action}: {count}" for action, count in action_counts.most_common(5)],
    )


def build_weekly_focus_artifact(
    *,
    candidates: list[Candidate],
    theme_signals: list[ThemeSignal] | None = None,
    sector_intelligence: list[SectorIntelligence] | None = None,
    run_id: str = "",
) -> WeeklyFocusArtifact:
    focus_items = _rank_focus_items([build_focus_item(candidate) for candidate in candidates])
    eligible = _cap_oss_project_only([item for item in focus_items if is_partner_focus_eligible(item)])
    partner_focus = eligible[:15]
    partner_ids = {item.id for item in partner_focus}
    extended_watchlist = [item for item in focus_items if item.id not in partner_ids][:15]
    movements = build_market_movements(partner_focus or extended_watchlist, theme_signals)
    new_to_marathon = _new_to_marathon(partner_focus + extended_watchlist)
    workflow_view = _workflow_view(partner_focus)
    gaps = _source_gaps(sector_intelligence)
    appendix = {
        "needs_more_evidence": [
            item.to_dict()
            for item in extended_watchlist
            if item.company_identity_quality_score < 60 or item.evidence_confidence_score < 45
        ][:10],
        "source_gaps": gaps,
    }
    return WeeklyFocusArtifact(
        run_id=run_id,
        executive_snapshot=_executive_snapshot(
            partner_focus=partner_focus,
            movements=movements,
            new_to_marathon=new_to_marathon,
            source_gaps=gaps,
        ),
        partner_focus=partner_focus,
        market_movements=movements,
        new_to_marathon=new_to_marathon,
        workflow_view=workflow_view,
        extended_watchlist=extended_watchlist,
        appendix=appendix,
        source_gaps=gaps,
    )
```

### Tests

- [ ] **Step 1: Add artifact tests**

Append:

```python
def test_build_weekly_focus_artifact_splits_focus_watchlist_and_limits_rows():
    from radar_focus import build_weekly_focus_artifact

    candidates = [
        _candidate(
            name=f"Company {i}",
            stable_key=f"company-{i}",
            domain=f"company{i}.com",
            sources=[f"https://company{i}.com"],
            evidence_confidence_score=70,
            investment_interest_score=70 - i,
        )
        for i in range(20)
    ]

    artifact = build_weekly_focus_artifact(candidates=candidates, run_id="2026-05-11")

    assert len(artifact.partner_focus) <= 15
    assert len(artifact.extended_watchlist) <= 15
    assert artifact.run_id == "2026-05-11"
    assert artifact.executive_snapshot.top_movement


def test_build_weekly_focus_artifact_caps_project_only_rows():
    from radar_focus import build_weekly_focus_artifact

    candidates = [
        _candidate(
            name=f"Repo {i}",
            stable_key=f"repo-{i}",
            domain="",
            sources=[f"https://github.com/example/repo-{i}"],
            maintainer_profiles=[{"name": f"maintainer-{i}"}],
            oss_company_formation_score=65,
            evidence_confidence_score=60,
            investment_interest_score=80 - i,
        )
        for i in range(10)
    ]

    artifact = build_weekly_focus_artifact(candidates=candidates, run_id="2026-05-11")
    project_only = [item for item in artifact.partner_focus if item.project_url and not item.company_domain]

    assert len(project_only) <= 5


def test_new_to_marathon_and_workflow_view_use_attio_context():
    from radar_focus import ACTION_REFRESH_ATTIO, build_weekly_focus_artifact

    artifact = build_weekly_focus_artifact(
        candidates=[
            _candidate(
                name="KnownCo",
                stable_key="knownco",
                domain="known.co",
                sources=["https://known.co"],
                attio_status="stale",
                attio_staleness_reason="No interaction in 180 days",
                evidence_confidence_score=75,
            )
        ],
        run_id="2026-05-11",
    )

    assert artifact.new_to_marathon[0].name == "KnownCo"
    assert ACTION_REFRESH_ATTIO in artifact.workflow_view
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_focus.py::test_build_weekly_focus_artifact_splits_focus_watchlist_and_limits_rows \
  .claude/skills/vc-signals/tests/test_radar_focus.py::test_build_weekly_focus_artifact_caps_project_only_rows \
  .claude/skills/vc-signals/tests/test_radar_focus.py::test_new_to_marathon_and_workflow_view_use_attio_context \
  -q
```

Expected:

- FAIL because `build_weekly_focus_artifact` is not implemented.

- [ ] **Step 3: Implement artifact builder**

Add artifact builder code above to `radar_focus.py`.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected:

- All focus tests pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_focus.py .claude/skills/vc-signals/tests/test_radar_focus.py
git commit -m "Build weekly focus artifact"
```

---

## Task 5: JSON, Markdown Rendering, And Feedback Scaffold

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_focus.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_focus.py`

### Rendering Logic

Add:

```python
def write_weekly_focus_json(artifact: WeeklyFocusArtifact, path: Path) -> Path:
    path.write_text(json.dumps(artifact.to_dict(), indent=2))
    return path


def _cell(value) -> str:
    return ("" if value is None else str(value)).replace("\n", " ").replace("|", "\\|")


def _item_row(item: FocusItem) -> str:
    return " | ".join(
        [
            str(item.rank),
            _cell(item.name),
            _cell(item.market_movement),
            _cell(item.market_sector),
            _cell(item.why_focus_this_week),
            _cell("; ".join(item.who_is_talking[:2])),
            _cell("; ".join(item.evidence_snapshot[:2])),
            _cell(item.attio_status),
            _cell(item.recommended_action),
            str(item.investment_interest_score),
            str(item.evidence_confidence_score),
            _cell("; ".join(item.missing_evidence[:2])),
            _cell(item.why_this_may_be_noise),
        ]
    )


def render_weekly_focus_markdown(artifact: WeeklyFocusArtifact) -> str:
    lines = [
        "# Marathon Signal Radar: Weekly Focus",
        "",
        "## Executive Snapshot",
        "",
        f"- Top movement: {artifact.executive_snapshot.top_movement or 'None'}",
        f"- Top new-to-Marathon row: {artifact.executive_snapshot.top_new_to_marathon or 'None'}",
        f"- Rows needing owner: {artifact.executive_snapshot.rows_needing_owner}",
        f"- Rows needing Attio refresh: {artifact.executive_snapshot.rows_needing_attio_refresh}",
        f"- Biggest source gap: {artifact.executive_snapshot.biggest_source_gap or 'None'}",
    ]
    if artifact.executive_snapshot.top_actions:
        lines.append("- Top actions: " + "; ".join(artifact.executive_snapshot.top_actions))

    lines.extend(
        [
            "",
            "## Partner Focus",
            "",
            "| # | Company / Project | Market Movement | Sector | Why Focus This Week | Who Is Talking | Evidence | Attio | Action | Interest | Confidence | Missing Evidence | Why This May Be Noise |",
            "|---|---|---|---|---|---|---|---|---|---:|---:|---|---|",
        ]
    )
    if artifact.partner_focus:
        lines.extend(f"| {_item_row(item)} |" for item in artifact.partner_focus)
    else:
        lines.append("|  | No rows cleared Partner Focus gates. |  |  |  |  |  |  |  |  |  |  |  |")

    lines.extend(["", "## Market Movements", ""])
    for movement in artifact.market_movements[:6]:
        lines.extend(
            [
                f"### {movement.name}",
                f"- What is moving: {movement.what_is_moving}",
                f"- Why now: {movement.why_now}",
                f"- Why not now: {movement.why_not_now or 'No specific skepticism captured.'}",
                f"- Who is talking: {', '.join(movement.who_is_talking[:4]) or 'Unknown'}",
                f"- Companies/projects: {', '.join(movement.companies_or_projects[:6]) or 'None'}",
                "",
            ]
        )
    if not artifact.market_movements:
        lines.append("- No market movements generated.")

    lines.extend(["", "## New To Marathon", ""])
    if artifact.new_to_marathon:
        for item in artifact.new_to_marathon[:10]:
            lines.append(f"- **{item.name}** — {item.attio_status}; action: {item.recommended_action}")
    else:
        lines.append("- No new/stale/no-owner Attio rows surfaced.")

    lines.extend(["", "## Workflow View", ""])
    if artifact.workflow_view:
        for action, items in artifact.workflow_view.items():
            names = ", ".join(item.name for item in items[:10])
            lines.append(f"- **{action}** ({len(items)}): {names}")
    else:
        lines.append("- No workflow actions generated.")

    lines.extend(["", "## Extended Watchlist", ""])
    if artifact.extended_watchlist:
        for item in artifact.extended_watchlist[:15]:
            lines.append(f"- **{item.name}** — {item.recommended_action}; missing: {', '.join(item.missing_evidence[:2]) or 'none'}")
    else:
        lines.append("- No extended watchlist rows.")

    lines.extend(["", "## Appendix", ""])
    gaps = artifact.source_gaps or artifact.appendix.get("source_gaps", [])
    if gaps:
        lines.append("### Source Gaps")
        for gap in gaps[:8]:
            lines.append(f"- {gap}")
    needs_more = artifact.appendix.get("needs_more_evidence", [])
    if needs_more:
        lines.extend(["", "### Needs More Evidence"])
        for row in needs_more[:10]:
            lines.append(f"- **{row.get('name', 'Unknown')}** — {', '.join(row.get('missing_evidence', [])[:2])}")

    return "\n".join(lines).rstrip() + "\n"


def write_feedback_scaffold(run_id: str, focus_items: list[FocusItem], path: Path) -> Path:
    payload = AlexFeedback(
        run_id=run_id,
        feedback=[
            {
                "focus_item_id": item.id,
                "rating": "",
                "notes": "",
            }
            for item in focus_items[:15]
        ],
    )
    path.write_text(json.dumps(payload.to_dict(), indent=2))
    return path
```

### Tests

- [ ] **Step 1: Add rendering and feedback tests**

Append:

```python
def test_render_weekly_focus_markdown_has_executive_snapshot_and_compact_basis():
    from radar_focus import build_weekly_focus_artifact, render_weekly_focus_markdown

    artifact = build_weekly_focus_artifact(
        candidates=[_candidate(domain="agentshield.dev", sources=["https://agentshield.dev"])],
        run_id="2026-05-11",
    )
    markdown = render_weekly_focus_markdown(artifact)

    assert markdown.startswith("# Marathon Signal Radar: Weekly Focus")
    assert "## Executive Snapshot" in markdown
    assert "## Partner Focus" in markdown
    assert "company_identity_quality_basis" not in markdown
    assert "Missing Evidence" in markdown


def test_write_weekly_focus_json_and_feedback_scaffold(tmp_path):
    import json
    from radar_focus import build_weekly_focus_artifact, write_feedback_scaffold, write_weekly_focus_json

    artifact = build_weekly_focus_artifact(
        candidates=[_candidate(domain="agentshield.dev", sources=["https://agentshield.dev"])],
        run_id="2026-05-11",
    )
    focus_path = write_weekly_focus_json(artifact, tmp_path / "weekly-focus.json")
    feedback_path = write_feedback_scaffold("2026-05-11", artifact.partner_focus, tmp_path / "feedback.json")

    focus_payload = json.loads(focus_path.read_text())
    feedback_payload = json.loads(feedback_path.read_text())

    assert focus_payload["run_id"] == "2026-05-11"
    assert "partner_focus" in focus_payload
    assert feedback_payload["run_id"] == "2026-05-11"
    assert feedback_payload["feedback"][0]["focus_item_id"] == artifact.partner_focus[0].id
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_focus.py::test_render_weekly_focus_markdown_has_executive_snapshot_and_compact_basis \
  .claude/skills/vc-signals/tests/test_radar_focus.py::test_write_weekly_focus_json_and_feedback_scaffold \
  -q
```

Expected:

- FAIL because render/write functions do not exist.

- [ ] **Step 3: Implement rendering and writers**

Add rendering code above to `radar_focus.py`.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_focus.py -q
```

Expected:

- All focus tests pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_focus.py .claude/skills/vc-signals/tests/test_radar_focus.py
git commit -m "Render weekly focus artifacts"
```

---

## Task 6: Weekly Pipeline Integration

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

### Integration Logic

Modify imports near the existing optional imports:

```python
try:
    from radar_focus import (
        build_weekly_focus_artifact,
        render_weekly_focus_markdown,
        write_feedback_scaffold,
        write_weekly_focus_json,
    )
except ImportError:
    build_weekly_focus_artifact = None
    render_weekly_focus_markdown = None
    write_feedback_scaffold = None
    write_weekly_focus_json = None
```

After `preview_path.write_text(...)` in `run_weekly_artifacts()`, add:

```python
    focus_path = None
    focus_json_path = None
    feedback_path = None
    if build_weekly_focus_artifact and render_weekly_focus_markdown and write_weekly_focus_json and write_feedback_scaffold:
        focus_artifact = build_weekly_focus_artifact(
            candidates=scored_candidates,
            theme_signals=theme_signals,
            sector_intelligence=sector_intelligence,
            run_id=run_date,
        )
        focus_json_path = output_dir / "weekly-focus.json"
        focus_path = output_dir / "weekly-focus.md"
        feedback_path = output_dir / "feedback.json"
        write_weekly_focus_json(focus_artifact, focus_json_path)
        focus_path.write_text(render_weekly_focus_markdown(focus_artifact))
        write_feedback_scaffold(run_date, focus_artifact.partner_focus, feedback_path)
```

Add to `result`:

```python
        "weekly_focus": str(focus_path) if focus_path else "",
        "weekly_focus_json": str(focus_json_path) if focus_json_path else "",
        "feedback": str(feedback_path) if feedback_path else "",
```

Do not modify the `preview_path.write_text(_render_weekly_brief(...))` call.

### Tests

- [ ] **Step 1: Add weekly integration test**

Append to `.claude/skills/vc-signals/tests/test_radar_run.py`:

```python
def test_run_weekly_artifacts_writes_focus_artifacts_without_changing_preview(tmp_path, monkeypatch):
    import radar_run
    from radar_models import Candidate

    candidates = [
        Candidate(
            name="AgentShield",
            stable_key="agentshield",
            sector="Cybersecurity",
            market_sector="Cybersecurity",
            theme="AI agent permission security",
            source="https://github.com/affaan-m/agentshield",
            candidate_type="oss_project",
            why_on_radar="AI agent security scanner with MCP permissions focus.",
            why_this_may_be_noise="Commercial intent needs verification.",
            sources=["https://github.com/affaan-m/agentshield"],
            investment_interest_score=70,
            evidence_confidence_score=55,
            investment_interest="High",
            evidence_confidence="Medium",
            tier="Partner Review",
            weekly_tag="NEW",
            maintainer_profiles=[{"name": "affaan-m"}],
            oss_company_formation_score=60,
        )
    ]

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "build_signals_from_evidence", lambda evidence: {"signals": [], "coverage": {}})
    monkeypatch.setattr(radar_run, "build_theme_signals", lambda signals, sectors: [])
    monkeypatch.setattr(radar_run, "collect_company_discovery", lambda *args, **kwargs: {"queries": [], "items": [], "warnings": [], "errors": []})
    monkeypatch.setattr(radar_run, "promote_signals_to_candidates", lambda signals: {"candidates": candidates, "rejected": []})
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda rows: rows)
    monkeypatch.setattr(radar_run, "_apply_attio_to_candidates", lambda rows, client: rows)
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_weekly_tags", lambda rows, history, run_date: type("Result", (), {"candidates": rows, "history": {}, "faded": []})())
    monkeypatch.setattr(radar_run, "select_partner_review", lambda rows: rows)
    monkeypatch.setattr(radar_run, "build_sector_intelligence", lambda **kwargs: [])

    result = radar_run.run_weekly_artifacts(output_dir=tmp_path, candidate_limit=50)

    assert (tmp_path / "weekly-preview.md").exists()
    assert (tmp_path / "weekly-focus.json").exists()
    assert (tmp_path / "weekly-focus.md").exists()
    assert (tmp_path / "feedback.json").exists()
    assert result["preview"] == str(tmp_path / "weekly-preview.md")
    assert result["weekly_focus"] == str(tmp_path / "weekly-focus.md")
```

- [ ] **Step 2: Run test to verify failure**

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_writes_focus_artifacts_without_changing_preview \
  -q
```

Expected:

- FAIL because `weekly-focus` artifacts are not written yet.

- [ ] **Step 3: Integrate into `radar_run.py`**

Apply the integration code above.

- [ ] **Step 4: Run integration test**

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_writes_focus_artifacts_without_changing_preview \
  -q
```

Expected:

- Test passes.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Write weekly focus artifacts from weekly run"
```

---

## Task 7: Product Acceptance And Regression Verification

**Files:**
- No required code files.
- Generated local artifacts under a throwaway output directory.

- [ ] **Step 1: Run focused tests**

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_focus.py \
  .claude/skills/vc-signals/tests/test_radar_models.py \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  -q
```

Expected:

- All selected tests pass.

- [ ] **Step 2: Run full test suite**

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected:

- Full suite passes.

- [ ] **Step 3: Generate a real local focus artifact**

Use the current quality path, not `--first-pass`:

```bash
rm -rf docs/radar-runs/current-focus-check
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly \
  --sectors all \
  --output-dir docs/radar-runs/current-focus-check \
  --limit 50
```

Expected:

- `docs/radar-runs/current-focus-check/weekly-preview.md`
- `docs/radar-runs/current-focus-check/weekly-focus.json`
- `docs/radar-runs/current-focus-check/weekly-focus.md`
- `docs/radar-runs/current-focus-check/feedback.json`

- [ ] **Step 4: Check artifact limits and focus gates**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
base = Path('docs/radar-runs/current-focus-check')
focus = json.loads((base / 'weekly-focus.json').read_text())
assert len(focus['partner_focus']) <= 15
assert len(focus['market_movements']) <= 6
assert len(focus['new_to_marathon']) <= 10
assert len(focus['extended_watchlist']) <= 15
for row in focus['partner_focus']:
    assert row['company_identity_quality_score'] >= 60
    assert row['evidence_urls']
    assert row['noise_risk_score'] < 70
    assert row['recommended_action']
    assert row['focus_priority_basis']
    assert row['company_identity_quality_basis']
print('weekly focus gates ok')
PY
```

Expected:

- Prints `weekly focus gates ok`.

- [ ] **Step 5: Product acceptance read**

Open/read:

```bash
sed -n '1,220p' docs/radar-runs/current-focus-check/weekly-focus.md
```

Manually answer:

1. What are the top market movements?
2. Which 5 companies/projects should someone inspect first?
3. Which are new to Marathon?
4. Which Attio records need refresh?
5. Which rows are weak/noisy but worth watching?

Expected:

- If any answer is unclear from `weekly-focus.md`, fix rendering/ranking before adding more sources.

- [ ] **Step 6: Verify `weekly-preview.md` still exists and is not replaced**

Run:

```bash
test -s docs/radar-runs/current-focus-check/weekly-preview.md
test -s docs/radar-runs/current-focus-check/weekly-focus.md
grep -q "# VC Signals Weekly Radar" docs/radar-runs/current-focus-check/weekly-preview.md
grep -q "# Marathon Signal Radar: Weekly Focus" docs/radar-runs/current-focus-check/weekly-focus.md
```

Expected:

- Exit code 0.

- [ ] **Step 7: Commit final verification updates if any**

Only commit code/tests/docs. Do not commit `docs/radar-runs/current-focus-check` unless the user explicitly asks for generated artifacts.

```bash
git status --short
```

Expected:

- Only intended source/test changes are staged or committed.

---

## Definition Of Done

Phase 1A/1B is done when:

1. `weekly` writes `weekly-focus.json`, `weekly-focus.md`, and `feedback.json`.
2. `weekly-focus.json` is the canonical source for `weekly-focus.md`.
3. `weekly-preview.md` still generates through the existing renderer and is not replaced.
4. Partner Focus has max 15 rows.
5. Extended Watchlist has max 15 rows.
6. Market Movements has max 6 sections.
7. New To Marathon has max 10 rows.
8. Partner Focus gates are enforced by a direct tested `is_partner_focus_eligible()` function.
9. `Take meeting` is blocked unless the strict gate clears.
10. Score basis arrays exist in JSON for focus priority, company identity quality, actionability, freshness, market movement, Marathon fit, noise risk, and consensus risk.
11. Markdown renders compact rationale and does not dump basis arrays inline.
12. Row-level `missing_evidence` appears in JSON and compactly in Markdown.
13. `feedback.json` scaffolds focus item IDs for Alex feedback.
14. Tests cover:
    - model roundtrips
    - score basis presence
    - Partner Focus gates
    - no evidence URL exclusion
    - OSS/project-only cap
    - strict Take Meeting gate
    - Attio action grouping
    - New To Marathon section
    - missing evidence disclosure
    - max output limits
    - weekly run artifact integration
    - `weekly-preview.md` remains generated separately
15. The real generated `weekly-focus.md` lets Alex answer in under five minutes:
    - top market movements
    - top companies/projects to inspect
    - which are new to Marathon
    - which Attio records need refresh
    - which rows are weak/noisy but worth watching

## Self-Review Checklist

- Spec coverage: Phase 1A/1B scope is covered; excluded phases are not implemented.
- Placeholder scan: no `TBD`, `TODO`, or vague "add tests" steps.
- Type consistency: `FocusItem`, `MarketMovement`, `WeeklyFocusArtifact`, and `AlexFeedback` signatures match task code snippets.
- Product guardrail: no new sources, no live LLM dependency, no Slack, no Attio writeback, no `weekly-preview.md` renderer rewrite.
