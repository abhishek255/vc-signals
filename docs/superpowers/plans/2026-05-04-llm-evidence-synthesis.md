# LLM Evidence Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in LLM synthesis layer that reasons across collected evidence, writes auditable `synthesis.json`, and improves follow-up guidance without letting uncited LLM claims pollute canonical candidate rows.

**Architecture:** Keep the deterministic weekly radar as the default. Add focused synthesis models and a `radar_synthesis.py` module that can run with a fake provider in tests, skip gracefully when no OpenAI key exists, validate citations against known evidence URLs, and render optional synthesis notes only when requested.

**Tech Stack:** Python dataclasses, pytest, existing `.claude/skills/vc-signals/scripts` modules, OpenAI HTTPS API via stdlib `urllib` for runtime, JSON artifacts, Markdown renderer.

---

## Product Success Criteria

This phase is complete when:

1. `weekly --with-synthesis` writes `synthesis.json`.
2. default `weekly` does not write or render synthesis output.
3. uncited LLM leads/themes are dropped.
4. hallucinated enrichment does not enter `candidates.json`.
5. synthesis notes explain source gaps and next hunts in the weekly preview.
6. tests never call the real OpenAI API.

## Files And Responsibilities

### New Files

- `.claude/skills/vc-signals/scripts/radar_synthesis.py`
  - Builds source digest.
  - Calls provider abstraction.
  - Validates citations and drops unsupported claims.
  - Produces `SynthesisResult`.

- `.claude/skills/vc-signals/tests/test_radar_synthesis.py`
  - Unit tests for validation, fake provider, disabled provider, citation filtering, and source digest.

### Modified Files

- `.claude/skills/vc-signals/scripts/radar_models.py`
  - Add synthesis dataclasses with `to_dict()` / `from_dict()`.

- `.claude/skills/vc-signals/tests/test_radar_models.py`
  - Add synthesis model roundtrip tests.

- `.claude/skills/vc-signals/scripts/radar_render.py`
  - Accept optional `synthesis`.
  - Render `## LLM Synthesis Notes` only when enabled and useful.

- `.claude/skills/vc-signals/tests/test_radar_render.py`
  - Cover synthesis section and default absence.

- `.claude/skills/vc-signals/scripts/radar_run.py`
  - Add `with_synthesis` parameter.
  - Parse `--with-synthesis`.
  - Write `synthesis.json` only when requested.
  - Pass synthesis to renderer only when requested.

- `.claude/skills/vc-signals/tests/test_radar_run.py`
  - Cover opt-in artifact generation and default deterministic behavior.

- `README.md`
  - Explain opt-in synthesis after implementation.

- `docs/radar-runs/marathon-weekly-v4-synthesis/*`
  - Captured fake-synthesis A/B sample artifact.

---

## Checkpoint A: Synthesis Contract

Run after Tasks 1-2:

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_synthesis.py \
  .claude/skills/vc-signals/tests/test_radar_models.py \
  -q
```

Expected:

- Synthesis models roundtrip.
- Missing provider is graceful.
- Fake provider output validates.
- Uncited or unsupported claims are dropped.

## Checkpoint B: Weekly Integration

Run after Tasks 3-4:

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  .claude/skills/vc-signals/tests/test_radar_render.py \
  -q
```

Expected:

- `--with-synthesis` writes `synthesis.json`.
- default weekly output remains deterministic.
- renderer includes synthesis notes only when available.

## Checkpoint C: Captured A/B Artifact

Run after Task 5:

```bash
rm -rf docs/radar-runs/marathon-weekly-v4-synthesis
python3 - <<'PY'
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.claude/skills/vc-signals/scripts').resolve()))
import radar_run
from radar_models import PossibleCompanyLead, SectorDiagnosis, SynthesisResult, ThemeHypothesis

source = Path('docs/radar-runs/marathon-weekly-v3/2026-05-04-raw-evidence.json')
if not source.exists():
    raise SystemExit('missing captured raw evidence')
evidence = json.loads(source.read_text())
output_dir = Path('docs/radar-runs/marathon-weekly-v4-synthesis')
if output_dir.exists():
    shutil.rmtree(output_dir)

def fake_synthesis(**kwargs):
    return SynthesisResult(
        enabled=True,
        model='fake-synthesis',
        source_digest={'candidate_count': 50},
        sector_diagnoses=[
            SectorDiagnosis(
                market_sector='Vertical AI',
                diagnosis='Source failure / incomplete coverage',
                recommended_next_queries=['vertical AI workflow automation startup launch'],
                confidence='High',
            )
        ],
        theme_hypotheses=[
            ThemeHypothesis(
                market_sector='Cybersecurity',
                theme='AI agent permission security',
                evidence_summary='OSS projects point to MCP/tool permission risk.',
                evidence_urls=['https://github.com/affaan-m/agentshield'],
                why_it_matters='Agent adoption creates new runtime permission surfaces.',
                why_this_may_be_noise='Evidence is mostly OSS.',
                confidence='Medium',
            )
        ],
        possible_company_leads=[
            PossibleCompanyLead(
                name='AgentShield',
                market_sector='Cybersecurity',
                source_lane='OSS',
                evidence_urls=['https://github.com/affaan-m/agentshield'],
                why_on_radar='Fast OSS momentum around AI agent security.',
                verification_needed=['Confirm company formation'],
                suggested_action='track company formation',
                confidence='Medium',
            )
        ],
        partner_notes=['This run is OSS-heavy because grounded company discovery is unavailable.'],
    )

radar_run.collect_live_evidence = lambda **kwargs: evidence
radar_run.run_synthesis = fake_synthesis
result = radar_run.run_weekly_artifacts(
    output_dir=output_dir,
    sectors=radar_run.DEFAULT_SECTORS,
    github_limit=80,
    max_queries_per_sector=2,
    candidate_limit=50,
    with_synthesis=True,
)
print(json.dumps(result))
PY
test -f docs/radar-runs/marathon-weekly-v4-synthesis/synthesis.json
rg -n "LLM Synthesis Notes|Possible Companies Requiring Verification|AgentShield|Vertical AI" docs/radar-runs/marathon-weekly-v4-synthesis/weekly-preview.md
```

Expected:

- fake synthesis artifact renders.
- deterministic V3 path remains unchanged unless `with_synthesis=True`.
- synthesis output is clearly separate from canonical Full Radar.

## Checkpoint D: Final Quality

Run after all tasks:

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
git diff --check
rg -n "ATTIO_ACCESS_TOKEN='|Bearer [A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-or-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|fwKR[A-Za-z0-9_-]{10,}" . --glob '!vendor/**' --glob '!.git/**' --glob '!docs/superpowers/plans/**'
```

Expected:

- full tests pass.
- `git diff --check` has no output.
- secret scan exits `1` with no output.

---

## Task 1: Add Synthesis Data Models

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_models.py`

- [ ] **Step 1: Add failing model tests**

Append to `.claude/skills/vc-signals/tests/test_radar_models.py`:

```python
def test_synthesis_result_roundtrip():
    from radar_models import PossibleCompanyLead, SectorDiagnosis, SynthesisResult, ThemeHypothesis

    result = SynthesisResult(
        enabled=True,
        model="fake-synthesis",
        generated_at="2026-05-04T12:00:00Z",
        source_digest={"candidate_count": 50, "source_lanes": {"OSS": 50}},
        sector_diagnoses=[
            SectorDiagnosis(
                market_sector="Vertical AI",
                diagnosis="Source failure / incomplete coverage",
                evidence_urls=[],
                recommended_next_queries=["vertical AI workflow automation startup launch"],
                confidence="High",
            )
        ],
        theme_hypotheses=[
            ThemeHypothesis(
                market_sector="Cybersecurity",
                theme="AI agent permission security",
                evidence_summary="Operators and OSS projects point to MCP/tool permission risk.",
                evidence_urls=["https://github.com/affaan-m/agentshield"],
                why_it_matters="Agent adoption creates new security surfaces.",
                why_this_may_be_noise="Evidence is mostly OSS.",
                confidence="Medium",
            )
        ],
        possible_company_leads=[
            PossibleCompanyLead(
                name="AgentShield",
                market_sector="Cybersecurity",
                source_lane="OSS",
                domain="",
                evidence_urls=["https://github.com/affaan-m/agentshield"],
                why_on_radar="Fast OSS momentum.",
                verification_needed=["Confirm company formation"],
                suggested_action="track company formation",
                confidence="Medium",
            )
        ],
        partner_notes=["This run is OSS-heavy."],
        warnings=[],
    )

    restored = SynthesisResult.from_dict(result.to_dict())

    assert restored.enabled is True
    assert restored.sector_diagnoses[0].market_sector == "Vertical AI"
    assert restored.theme_hypotheses[0].theme == "AI agent permission security"
    assert restored.possible_company_leads[0].name == "AgentShield"
    assert restored.partner_notes == ["This run is OSS-heavy."]


def test_synthesis_result_ignores_unknown_payload_fields():
    from radar_models import SynthesisResult

    restored = SynthesisResult.from_dict({
        "enabled": False,
        "model": "",
        "unknown_future_field": "ok",
        "sector_diagnoses": [{"market_sector": "AI Infra", "extra": "ignored"}],
    })

    assert restored.enabled is False
    assert restored.sector_diagnoses[0].market_sector == "AI Infra"
```

- [ ] **Step 2: Run model tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py -q
```

Expected: fails because `SynthesisResult`, `SectorDiagnosis`, `ThemeHypothesis`, and `PossibleCompanyLead` are not defined.

- [ ] **Step 3: Implement synthesis models**

Append to `.claude/skills/vc-signals/scripts/radar_models.py` after `SectorIntelligence`:

```python
@dataclass
class SectorDiagnosis:
    market_sector: str
    diagnosis: str = ""
    evidence_urls: list[str] = field(default_factory=list)
    recommended_next_queries: list[str] = field(default_factory=list)
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "SectorDiagnosis":
        return cls(**_known_payload(cls, payload))


@dataclass
class ThemeHypothesis:
    market_sector: str
    theme: str
    evidence_summary: str = ""
    evidence_urls: list[str] = field(default_factory=list)
    why_it_matters: str = ""
    why_this_may_be_noise: str = ""
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ThemeHypothesis":
        return cls(**_known_payload(cls, payload))


@dataclass
class PossibleCompanyLead:
    name: str
    market_sector: str = ""
    source_lane: str = ""
    domain: str = ""
    evidence_urls: list[str] = field(default_factory=list)
    why_on_radar: str = ""
    verification_needed: list[str] = field(default_factory=list)
    suggested_action: str = "investigate"
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "PossibleCompanyLead":
        return cls(**_known_payload(cls, payload))


@dataclass
class SynthesisResult:
    enabled: bool = False
    model: str = ""
    generated_at: str = ""
    source_digest: dict = field(default_factory=dict)
    sector_diagnoses: list[SectorDiagnosis] = field(default_factory=list)
    theme_hypotheses: list[ThemeHypothesis] = field(default_factory=list)
    possible_company_leads: list[PossibleCompanyLead] = field(default_factory=list)
    partner_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "model": self.model,
            "generated_at": self.generated_at,
            "source_digest": self.source_digest,
            "sector_diagnoses": [item.to_dict() for item in self.sector_diagnoses],
            "theme_hypotheses": [item.to_dict() for item in self.theme_hypotheses],
            "possible_company_leads": [item.to_dict() for item in self.possible_company_leads],
            "partner_notes": list(self.partner_notes),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "SynthesisResult":
        known = _known_payload(cls, payload)
        known["sector_diagnoses"] = [
            item if isinstance(item, SectorDiagnosis) else SectorDiagnosis.from_dict(item)
            for item in known.get("sector_diagnoses", [])
        ]
        known["theme_hypotheses"] = [
            item if isinstance(item, ThemeHypothesis) else ThemeHypothesis.from_dict(item)
            for item in known.get("theme_hypotheses", [])
        ]
        known["possible_company_leads"] = [
            item if isinstance(item, PossibleCompanyLead) else PossibleCompanyLead.from_dict(item)
            for item in known.get("possible_company_leads", [])
        ]
        return cls(**known)
```

- [ ] **Step 4: Run model tests to verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py -q
```

Expected: all model tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/tests/test_radar_models.py
git commit -m "Add radar synthesis models"
```

---

## Task 2: Add Synthesis Module With Citation Guardrails

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_synthesis.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_synthesis.py`

- [ ] **Step 1: Add failing synthesis tests**

Create `.claude/skills/vc-signals/tests/test_radar_synthesis.py`:

```python
from __future__ import annotations


def _candidate():
    from radar_models import Candidate

    return Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        market_sector="Cybersecurity",
        source_lane="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )


def _signal():
    from radar_models import Signal

    return Signal(
        source="reddit",
        role="pain",
        title="How are teams controlling AI agent permissions?",
        url="https://reddit.com/r/cybersecurity/comments/1",
        sector="cybersecurity",
        text="MCP tools and AI agents are creating permission review headaches.",
        can_create_candidate=False,
    )


def test_build_source_digest_counts_sources_and_sectors():
    from radar_synthesis import build_source_digest

    digest = build_source_digest(candidates=[_candidate()], signals=[_signal()])

    assert digest["candidate_count"] == 1
    assert digest["signal_count"] == 1
    assert digest["source_lanes"] == {"OSS": 1}
    assert digest["market_sectors"] == {"Cybersecurity": 1}


def test_run_synthesis_without_provider_returns_disabled_result(monkeypatch):
    import radar_synthesis

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = radar_synthesis.run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=None,
    )

    assert result.enabled is False
    assert "OPENAI_API_KEY" in result.warnings[0]


def test_run_synthesis_keeps_cited_items_from_fake_provider():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "sector_diagnoses": [
                {
                    "market_sector": "Cybersecurity",
                    "diagnosis": "OSS-heavy but relevant AI agent security signal.",
                    "evidence_urls": ["https://github.com/affaan-m/agentshield"],
                    "recommended_next_queries": ["AI agent security startup MCP permissions"],
                    "confidence": "Medium",
                }
            ],
            "theme_hypotheses": [
                {
                    "market_sector": "Cybersecurity",
                    "theme": "AI agent permission security",
                    "evidence_summary": "AgentShield and Reddit pain point to permission risk.",
                    "evidence_urls": [
                        "https://github.com/affaan-m/agentshield",
                        "https://reddit.com/r/cybersecurity/comments/1",
                    ],
                    "why_it_matters": "Agent tool use creates new security review surfaces.",
                    "why_this_may_be_noise": "Evidence is early and mostly OSS.",
                    "confidence": "Medium",
                }
            ],
            "possible_company_leads": [
                {
                    "name": "AgentShield",
                    "market_sector": "Cybersecurity",
                    "source_lane": "OSS",
                    "evidence_urls": ["https://github.com/affaan-m/agentshield"],
                    "why_on_radar": "Fast OSS momentum.",
                    "verification_needed": ["Confirm company formation"],
                    "suggested_action": "track company formation",
                    "confidence": "Medium",
                }
            ],
            "partner_notes": ["This run is OSS-heavy because grounded company discovery is unavailable."],
            "warnings": [],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
        model="fake-synthesis",
    )

    assert result.enabled is True
    assert result.model == "fake-synthesis"
    assert result.theme_hypotheses[0].theme == "AI agent permission security"
    assert result.possible_company_leads[0].name == "AgentShield"


def test_run_synthesis_drops_uncited_and_unknown_url_items():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "theme_hypotheses": [
                {
                    "market_sector": "Cybersecurity",
                    "theme": "Uncited theme",
                    "evidence_summary": "No citations.",
                    "evidence_urls": [],
                    "why_it_matters": "Cannot trust this.",
                    "why_this_may_be_noise": "",
                    "confidence": "High",
                },
                {
                    "market_sector": "Cybersecurity",
                    "theme": "Unknown URL theme",
                    "evidence_summary": "Unknown citation.",
                    "evidence_urls": ["https://made-up.example.com"],
                    "why_it_matters": "Cannot trust this.",
                    "why_this_may_be_noise": "",
                    "confidence": "High",
                },
            ],
            "possible_company_leads": [
                {
                    "name": "MadeUpCo",
                    "market_sector": "Cybersecurity",
                    "evidence_urls": ["https://made-up.example.com"],
                    "why_on_radar": "Invented.",
                    "verification_needed": [],
                    "suggested_action": "take meeting",
                    "confidence": "High",
                }
            ],
            "sector_diagnoses": [],
            "partner_notes": [],
            "warnings": [],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    assert result.theme_hypotheses == []
    assert result.possible_company_leads == []
    assert any("dropped" in warning.lower() for warning in result.warnings)


def test_prompt_payload_does_not_include_attio_secrets():
    from radar_synthesis import build_synthesis_payload

    payload = build_synthesis_payload(
        evidence={"warnings": ["ok"]},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
    )
    rendered = repr(payload)

    assert "ATTIO_ACCESS_TOKEN" not in rendered
    assert "OPENAI_API_KEY" not in rendered
```

- [ ] **Step 2: Run synthesis tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_synthesis.py -q
```

Expected: fails because `radar_synthesis` does not exist.

- [ ] **Step 3: Implement synthesis module**

Create `.claude/skills/vc-signals/scripts/radar_synthesis.py`:

```python
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib import request

from radar_models import (
    Candidate,
    PossibleCompanyLead,
    SectorDiagnosis,
    SynthesisResult,
    ThemeHypothesis,
)


DEFAULT_SYNTHESIS_MODEL = "gpt-4.1-mini"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(item):
    return item.to_dict() if hasattr(item, "to_dict") else dict(item)


def build_source_digest(*, candidates: list, signals: list) -> dict:
    source_lanes = {}
    market_sectors = {}
    for candidate in candidates:
        lane = getattr(candidate, "source_lane", "") or getattr(candidate, "source", "") or "Unknown"
        sector = getattr(candidate, "market_sector", "") or getattr(candidate, "sector", "") or "Unclassified"
        source_lanes[lane] = source_lanes.get(lane, 0) + 1
        market_sectors[sector] = market_sectors.get(sector, 0) + 1
    return {
        "candidate_count": len(candidates),
        "signal_count": len(signals),
        "source_lanes": source_lanes,
        "market_sectors": market_sectors,
    }


def _known_urls(*, evidence: dict, signals: list, candidates: list, sector_intelligence: list, theme_signals: list) -> set[str]:
    urls: set[str] = set()
    for candidate in candidates:
        urls.update(url for url in getattr(candidate, "sources", []) if url)
        source = getattr(candidate, "source", "")
        if source:
            urls.add(source)
    for signal in signals:
        url = getattr(signal, "url", "")
        if url:
            urls.add(url)
    for item in theme_signals:
        urls.update(url for url in getattr(item, "source_urls", []) if url)
    for sector_payload in (evidence.get("last30days") or {}).values():
        for item in sector_payload.get("items", []):
            if item.get("url"):
                urls.add(item["url"])
    for item in evidence.get("github", []) or []:
        if item.get("url"):
            urls.add(item["url"])
        if item.get("html_url"):
            urls.add(item["html_url"])
    return urls


def build_synthesis_payload(*, evidence: dict, signals: list, candidates: list, sector_intelligence: list, theme_signals: list) -> dict:
    return {
        "source_digest": build_source_digest(candidates=candidates, signals=signals),
        "signals": [_as_dict(item) for item in signals],
        "candidates": [_as_dict(item) for item in candidates],
        "sector_intelligence": [_as_dict(item) for item in sector_intelligence],
        "theme_signals": [_as_dict(item) for item in theme_signals],
        "source_warnings": evidence.get("warnings", []),
    }


def _all_urls_known(urls: list[str], known_urls: set[str]) -> bool:
    return bool(urls) and all(url in known_urls for url in urls)


def _validate_result(payload: dict, *, known_urls: set[str], model: str, source_digest: dict) -> SynthesisResult:
    warnings = list(payload.get("warnings", []))
    sector_diagnoses = []
    for item in payload.get("sector_diagnoses", []):
        urls = item.get("evidence_urls", [])
        if urls and not all(url in known_urls for url in urls):
            warnings.append(f"Dropped sector diagnosis with unknown citation: {item.get('market_sector', '')}")
            continue
        sector_diagnoses.append(SectorDiagnosis.from_dict(item))

    theme_hypotheses = []
    for item in payload.get("theme_hypotheses", []):
        urls = item.get("evidence_urls", [])
        if not _all_urls_known(urls, known_urls):
            warnings.append(f"Dropped uncited or unsupported theme: {item.get('theme', '')}")
            continue
        theme_hypotheses.append(ThemeHypothesis.from_dict(item))

    possible_company_leads = []
    for item in payload.get("possible_company_leads", []):
        urls = item.get("evidence_urls", [])
        if not _all_urls_known(urls, known_urls):
            warnings.append(f"Dropped uncited or unsupported company lead: {item.get('name', '')}")
            continue
        possible_company_leads.append(PossibleCompanyLead.from_dict(item))

    return SynthesisResult(
        enabled=True,
        model=model,
        generated_at=_now_iso(),
        source_digest=source_digest,
        sector_diagnoses=sector_diagnoses,
        theme_hypotheses=theme_hypotheses,
        possible_company_leads=possible_company_leads,
        partner_notes=list(payload.get("partner_notes", []))[:8],
        warnings=warnings,
    )


def call_openai_synthesis(payload: dict, *, model: str, api_key: str) -> dict:
    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a skeptical VC research analyst for Marathon Management Partners. "
                    "Use only supplied evidence. Cite evidence_urls for every theme or company lead. "
                    "Do not invent funding, headcount, founders, domains, customers, or LinkedIn URLs. "
                    "Return only valid JSON with sector_diagnoses, theme_hypotheses, possible_company_leads, partner_notes, warnings."
                ),
            },
            {"role": "user", "content": json.dumps(payload)},
        ],
    }
    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read() or b"{}")
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def run_synthesis(
    *,
    evidence: dict,
    signals: list,
    candidates: list[Candidate],
    sector_intelligence: list,
    theme_signals: list,
    provider=None,
    model: str | None = None,
) -> SynthesisResult:
    model = model or os.environ.get("VC_SIGNALS_SYNTHESIS_MODEL", DEFAULT_SYNTHESIS_MODEL)
    payload = build_synthesis_payload(
        evidence=evidence,
        signals=signals,
        candidates=candidates,
        sector_intelligence=sector_intelligence,
        theme_signals=theme_signals,
    )
    source_digest = payload["source_digest"]
    known_urls = _known_urls(
        evidence=evidence,
        signals=signals,
        candidates=candidates,
        sector_intelligence=sector_intelligence,
        theme_signals=theme_signals,
    )

    if provider is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return SynthesisResult(
                enabled=False,
                model=model,
                generated_at=_now_iso(),
                source_digest=source_digest,
                warnings=["OPENAI_API_KEY is not set; LLM synthesis skipped."],
            )
        provider = lambda request_payload: call_openai_synthesis(request_payload, model=model, api_key=api_key)

    try:
        raw = provider(payload)
    except Exception as exc:
        return SynthesisResult(
            enabled=False,
            model=model,
            generated_at=_now_iso(),
            source_digest=source_digest,
            warnings=[f"LLM synthesis failed: {exc}"],
        )

    return _validate_result(raw or {}, known_urls=known_urls, model=model, source_digest=source_digest)
```

- [ ] **Step 4: Run synthesis tests to verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_synthesis.py -q
```

Expected: all synthesis tests pass.

- [ ] **Step 5: Run Checkpoint A**

Run:

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_synthesis.py \
  .claude/skills/vc-signals/tests/test_radar_models.py \
  -q
```

Expected: both test files pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add .claude/skills/vc-signals/scripts/radar_synthesis.py .claude/skills/vc-signals/tests/test_radar_synthesis.py
git commit -m "Add guarded radar synthesis module"
```

---

## Task 3: Render Optional LLM Synthesis Notes

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_render.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_render.py`

- [ ] **Step 1: Add failing renderer tests**

Append to `.claude/skills/vc-signals/tests/test_radar_render.py`:

```python
def test_render_weekly_brief_includes_synthesis_notes_when_enabled():
    from radar_models import PossibleCompanyLead, SectorDiagnosis, SynthesisResult
    from radar_render import render_weekly_brief

    synthesis = SynthesisResult(
        enabled=True,
        model="fake-synthesis",
        sector_diagnoses=[
            SectorDiagnosis(
                market_sector="Vertical AI",
                diagnosis="Source failure / incomplete coverage",
                recommended_next_queries=["vertical AI workflow automation startup launch"],
                confidence="High",
            )
        ],
        possible_company_leads=[
            PossibleCompanyLead(
                name="AgentShield",
                market_sector="Cybersecurity",
                source_lane="OSS",
                evidence_urls=["https://github.com/affaan-m/agentshield"],
                why_on_radar="Fast OSS momentum around AI agent security.",
                verification_needed=["Confirm company formation"],
                suggested_action="track company formation",
                confidence="Medium",
            )
        ],
        partner_notes=["This run is OSS-heavy because grounded company discovery is unavailable."],
    )

    markdown = render_weekly_brief([], {}, [], synthesis=synthesis)

    assert "## LLM Synthesis Notes" in markdown
    assert "This run is OSS-heavy" in markdown
    assert "### Possible Companies Requiring Verification" in markdown
    assert "| AgentShield | Cybersecurity | https://github.com/affaan-m/agentshield | track company formation | Confirm company formation |" in markdown
    assert "Vertical AI: Source failure / incomplete coverage" in markdown


def test_render_weekly_brief_omits_synthesis_notes_by_default():
    from radar_render import render_weekly_brief

    markdown = render_weekly_brief([], {}, [])

    assert "## LLM Synthesis Notes" not in markdown
```

- [ ] **Step 2: Run renderer tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_render.py -q
```

Expected: fails because `render_weekly_brief()` does not accept `synthesis`.

- [ ] **Step 3: Implement renderer support**

Modify `.claude/skills/vc-signals/scripts/radar_render.py`.

Change the function signature:

```python
def render_weekly_brief(
    candidates: list,
    coverage: dict,
    rejected: list,
    *,
    faded: list[dict] | None = None,
    theme_signals: list | None = None,
    sector_intelligence: list | None = None,
    partner_review: list | None = None,
    synthesis=None,
) -> str:
```

Add after `_theme_signals_table(theme_signals or [])` in the `lines.extend([...])` block:

```python
        "",
        _synthesis_section(synthesis),
```

Add helper functions before `_faded_table()`:

```python
def _synthesis_section(synthesis) -> str:
    if not synthesis or not getattr(synthesis, "enabled", False):
        return ""

    lines = ["## LLM Synthesis Notes", ""]
    notes = list(getattr(synthesis, "partner_notes", []) or [])
    if notes:
        for note in notes[:8]:
            lines.append(f"- {note}")
    else:
        lines.append("- No partner synthesis notes generated.")

    diagnoses = list(getattr(synthesis, "sector_diagnoses", []) or [])
    if diagnoses:
        lines.extend(["", "### Source Gap Diagnosis", ""])
        for item in diagnoses[:8]:
            query_text = "; ".join(getattr(item, "recommended_next_queries", []) or [])
            suffix = f" Next queries: {query_text}." if query_text else ""
            lines.append(f"- **{item.market_sector}: {item.diagnosis}** ({item.confidence}).{suffix}")

    leads = list(getattr(synthesis, "possible_company_leads", []) or [])
    if leads:
        lines.extend([
            "",
            "### Possible Companies Requiring Verification",
            "",
            "| Name | Market Sector | Evidence | Suggested Action | Verification Needed |",
            "|---|---|---|---|---|",
        ])
        for lead in leads[:12]:
            lines.append(
                f"| {lead.name} | {lead.market_sector} | {'; '.join(lead.evidence_urls)} | "
                f"{lead.suggested_action} | {'; '.join(lead.verification_needed)} |"
            )

    warnings = list(getattr(synthesis, "warnings", []) or [])
    if warnings:
        lines.extend(["", "### Synthesis Warnings", ""])
        for warning in warnings[:8]:
            lines.append(f"- {warning}")

    return "\n".join(lines)
```

Do not add a blank-line cleanup pass. Disabled synthesis returns an empty string, and the existing `rstrip()` at the end of `render_weekly_brief()` is enough for this artifact.

- [ ] **Step 4: Run renderer tests to verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_render.py -q
```

Expected: renderer tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add .claude/skills/vc-signals/scripts/radar_render.py .claude/skills/vc-signals/tests/test_radar_render.py
git commit -m "Render optional synthesis notes"
```

---

## Task 4: Wire Synthesis Into Weekly Run

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Add failing weekly integration tests**

Append to `.claude/skills/vc-signals/tests/test_radar_run.py`:

```python
def test_run_weekly_artifacts_writes_synthesis_only_when_enabled(tmp_path, monkeypatch):
    import json
    import radar_run
    from radar_models import SynthesisResult

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {"last30days": {}, "github": [], "warnings": []},
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)

    default_dir = tmp_path / "default"
    radar_run.run_weekly_artifacts(output_dir=default_dir, sectors=("devtools",), github_limit=0)
    assert not (default_dir / "synthesis.json").exists()
    assert "LLM Synthesis Notes" not in (default_dir / "weekly-preview.md").read_text()

    def fake_synthesis(**kwargs):
        return SynthesisResult(
            enabled=True,
            model="fake-synthesis",
            partner_notes=["Synthesis enabled for test."],
        )

    monkeypatch.setattr(radar_run, "run_synthesis", fake_synthesis)
    synthesis_dir = tmp_path / "synthesis"
    result = radar_run.run_weekly_artifacts(
        output_dir=synthesis_dir,
        sectors=("devtools",),
        github_limit=0,
        with_synthesis=True,
    )

    assert (synthesis_dir / "synthesis.json").exists()
    payload = json.loads((synthesis_dir / "synthesis.json").read_text())
    assert payload["enabled"] is True
    assert result["synthesis"].endswith("synthesis.json")
    assert "LLM Synthesis Notes" in (synthesis_dir / "weekly-preview.md").read_text()


def test_cli_weekly_parses_with_synthesis_flag(tmp_path, monkeypatch, capsys):
    import json
    import radar_run

    seen = {}

    def fake_run_weekly_artifacts(**kwargs):
        seen.update(kwargs)
        return {"preview": str(tmp_path / "weekly-preview.md"), "companies": 0}

    monkeypatch.setattr(radar_run, "run_weekly_artifacts", fake_run_weekly_artifacts)
    monkeypatch.setattr(radar_run.sys, "argv", [
        "radar_run.py",
        "weekly",
        "--output-dir",
        str(tmp_path),
        "--with-synthesis",
    ])

    radar_run._cli_main()
    out = json.loads(capsys.readouterr().out)

    assert out["companies"] == 0
    assert seen["with_synthesis"] is True
```

- [ ] **Step 2: Run weekly integration tests to verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_writes_synthesis_only_when_enabled .claude/skills/vc-signals/tests/test_radar_run.py::test_cli_weekly_parses_with_synthesis_flag -q
```

Expected: fails because `run_weekly_artifacts()` does not accept `with_synthesis` and CLI does not pass it.

- [ ] **Step 3: Implement weekly synthesis wiring**

Modify `.claude/skills/vc-signals/scripts/radar_run.py`.

Add import near other radar imports:

```python
from radar_synthesis import run_synthesis
```

Change `_render_weekly_brief()` signature:

```python
def _render_weekly_brief(
    candidates: list[Candidate],
    coverage: dict,
    rejected: list,
    *,
    faded: list[dict],
    theme_signals: list,
    sector_intelligence: list,
    partner_review: list[Candidate],
    synthesis=None,
) -> str:
```

Inside `_render_weekly_brief()`, add:

```python
    if "synthesis" in accepted or accepts_kwargs:
        kwargs["synthesis"] = synthesis
```

Change `run_weekly_artifacts()` signature:

```python
def run_weekly_artifacts(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    sectors: tuple[str, ...] = DEFAULT_SECTORS,
    github_limit: int = 40,
    max_queries_per_sector: int = 3,
    candidate_limit: int = 15,
    with_synthesis: bool = False,
) -> dict:
```

After `sector_intelligence = build_sector_intelligence(...)`, add:

```python
    synthesis = None
    synthesis_path = None
    if with_synthesis:
        synthesis = run_synthesis(
            evidence=evidence,
            signals=signal_result["signals"],
            candidates=scored_candidates,
            sector_intelligence=sector_intelligence,
            theme_signals=theme_signals,
        )
        synthesis_path = output_dir / "synthesis.json"
        synthesis_path.write_text(json.dumps(synthesis.to_dict(), indent=2))
```

When calling `_render_weekly_brief(...)`, pass:

```python
            synthesis=synthesis,
```

Before return, build result object:

```python
    result = {
        "raw_evidence": str(raw_path),
        "signals": str(signals_path),
        "candidates": str(candidates_path),
        "theme_signals": str(theme_signals_path),
        "sector_intelligence": str(sector_intelligence_path),
        "preview": str(preview_path),
        "companies": len(scored_candidates),
        "sectors": list(sectors),
    }
    if synthesis_path:
        result["synthesis"] = str(synthesis_path)
    return result
```

Replace the existing direct return dict with the result object above.

In `_cli_main()` weekly command, add:

```python
            with_synthesis=bool(args.get("with_synthesis", False)),
```

- [ ] **Step 4: Run weekly integration tests to verify pass**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_writes_synthesis_only_when_enabled .claude/skills/vc-signals/tests/test_radar_run.py::test_cli_weekly_parses_with_synthesis_flag -q
```

Expected: both tests pass.

- [ ] **Step 5: Run Checkpoint B**

Run:

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  .claude/skills/vc-signals/tests/test_radar_render.py \
  -q
```

Expected: both files pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Wire synthesis into weekly radar"
```

---

## Task 5: Add Captured A/B Artifact And README

**Files:**
- Modify: `README.md`
- Add/Modify: `docs/radar-runs/marathon-weekly-v4-synthesis/*`

- [ ] **Step 1: Run Checkpoint C captured fake-synthesis artifact**

Run the full Checkpoint C command from this plan.

Expected:

- `docs/radar-runs/marathon-weekly-v4-synthesis/synthesis.json` exists.
- `weekly-preview.md` includes `LLM Synthesis Notes`.
- `AgentShield` appears under possible companies requiring verification.

- [ ] **Step 2: Inspect captured artifact**

Run:

```bash
sed -n '1,220p' docs/radar-runs/marathon-weekly-v4-synthesis/weekly-preview.md
python3 - <<'PY'
import json
from pathlib import Path
p = Path('docs/radar-runs/marathon-weekly-v4-synthesis')
synthesis = json.loads((p / 'synthesis.json').read_text())
assert synthesis['enabled'] is True
assert synthesis['possible_company_leads'][0]['evidence_urls']
print({
    'partner_notes': len(synthesis.get('partner_notes', [])),
    'possible_company_leads': len(synthesis.get('possible_company_leads', [])),
    'theme_hypotheses': len(synthesis.get('theme_hypotheses', [])),
})
PY
```

Expected:

- preview is readable.
- synthesis JSON is cited and separate from Full Radar.

- [ ] **Step 3: Update README**

In `README.md`, update the weekly artifact section to include:

```markdown
- `synthesis.json`: optional LLM synthesis output when `--with-synthesis` is used. It contains partner notes, source-gap diagnoses, theme hypotheses, and possible company leads that require verification.
```

Add a short subsection near `Weekly Partner Artifact`:

````markdown
### Optional LLM Synthesis

Run with `--with-synthesis` to ask the LLM to reason across the collected evidence:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly \
  --sectors all \
  --output-dir docs/radar-runs/marathon-weekly-v4-synthesis \
  --limit 50 \
  --with-synthesis
```

Synthesis is opt-in. It can suggest themes, source gaps, follow-up searches, and possible company leads, but it cannot add uncited facts to `candidates.json`. Treat possible company leads as research prompts until a partner or associate verifies the cited evidence.
````

Add to Known Limitations:

```markdown
- **LLM synthesis is opt-in and advisory** — it can connect weak evidence and suggest next searches, but uncited or unsupported claims are dropped and possible company leads require verification.
```

- [ ] **Step 4: Run README term check**

Run:

```bash
rg -n "synthesis.json|--with-synthesis|Optional LLM Synthesis|LLM synthesis is opt-in" README.md
```

Expected: all four terms appear.

- [ ] **Step 5: Run Checkpoint D**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
git diff --check
rg -n "ATTIO_ACCESS_TOKEN='|Bearer [A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-or-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|fwKR[A-Za-z0-9_-]{10,}" . --glob '!vendor/**' --glob '!.git/**' --glob '!docs/superpowers/plans/**'
```

Expected:

- tests pass.
- no whitespace errors.
- secret scan exits `1` with no output.

- [ ] **Step 6: Commit**

Run:

```bash
git add README.md docs/radar-runs/marathon-weekly-v4-synthesis
git commit -m "Document optional radar synthesis"
```

---

## Final Review Checklist

Before final response, run:

```bash
git status --short --branch
git log --oneline -8
python3 -m pytest .claude/skills/vc-signals/tests -q
test -f docs/radar-runs/marathon-weekly-v4-synthesis/synthesis.json
rg -n "LLM Synthesis Notes|Possible Companies Requiring Verification" docs/radar-runs/marathon-weekly-v4-synthesis/weekly-preview.md
```

Confirm:

- branch is clean,
- synthesis remains opt-in,
- full tests pass,
- sample synthesis artifact exists,
- no uncited fake facts enter `candidates.json`,
- README explains the advisory nature of LLM synthesis.
