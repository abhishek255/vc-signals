# Sector-Balanced Radar V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sector-balanced weekly radar that separates market sector from source lane, prevents OSS from dominating the partner artifact, and turns non-company signal into useful sector intelligence instead of fake company rows.

**Architecture:** Keep the V2 deterministic pipeline: collect evidence, normalize signals, promote candidates, score/enrich, apply history, render. Add focused V3 modules for sector classification, theme/hunt-signal extraction, sector intelligence, and partner-priority ranking. Preserve backward-compatible JSON fields while rendering `market_sector` and `source_lane` as the partner-facing concepts.

**Tech Stack:** Python 3.12+, pytest, existing VC Signals scripts under `.claude/skills/vc-signals/scripts`, JSON artifacts, Markdown renderer.

---

## Product Success Criteria

This work is complete only when a Marathon partner can open a weekly preview and understand:

1. Why Partner Review has the first 10-15 things to inspect.
2. Which market sector each row belongs to.
3. Which source lane produced the evidence.
4. Which sectors have qualified companies/projects.
5. Which sectors have market pain or weak signal but no company yet.
6. Why non-OSS sectors are quiet if they have no rows.
7. Whether the artifact is OSS-heavy because the market was OSS-heavy or because company discovery was weak.

The artifact must not pad weak company rows. It must also not hide non-OSS market signal behind an all-OSS Full Radar.

---

## Files And Responsibilities

### New Files

- `.claude/skills/vc-signals/scripts/radar_sector_classifier.py`
  - Deterministically maps evidence/candidates to market sectors.
  - Assigns `market_sector`, `sector_confidence`, and `sector_reason`.
  - Keeps `source_lane` separate from sector.

- `.claude/skills/vc-signals/scripts/radar_theme_signals.py`
  - Converts non-candidate evidence into bounded `ThemeSignal` hunt prompts.
  - Filters out job posts, resume reviews, generic news digests, and social hype.

- `.claude/skills/vc-signals/scripts/radar_sector_intelligence.py`
  - Builds sector-level status blocks using raw signal counts, candidates, rejections, source errors, and theme signals.
  - Produces partner-readable explanations and next-hunt prompts.

- `.claude/skills/vc-signals/scripts/radar_partner_review.py`
  - Computes `partner_priority_score`.
  - Selects 10-15 Partner Review rows with soft source/sector diversity.

- `.claude/skills/vc-signals/tests/test_radar_sector_classifier.py`
- `.claude/skills/vc-signals/tests/test_radar_theme_signals.py`
- `.claude/skills/vc-signals/tests/test_radar_sector_intelligence.py`
- `.claude/skills/vc-signals/tests/test_radar_partner_review.py`

### Modified Files

- `.claude/skills/vc-signals/scripts/radar_models.py`
  - Add `market_sector`, `source_lane`, `evidence_role`, `sector_confidence`, `sector_reason`, `partner_priority_score`.
  - Add `ThemeSignal` and `SectorIntelligence` dataclasses.

- `.claude/skills/vc-signals/scripts/radar_sources.py`
  - Normalize source lanes and evidence roles, including ScrapeCreators social/video lanes.

- `.claude/skills/vc-signals/scripts/radar_run.py`
  - Wire V3 classification, theme signals, sector intelligence, and partner review selection.
  - Preserve V2 artifacts while adding V3 fields.

- `.claude/skills/vc-signals/scripts/radar_render.py`
  - Render run summary, Partner Review, Full Radar, Sector Intelligence, and Themes With No Company Yet.

- `.claude/skills/vc-signals/config/sectors.json`
  - Add `company_discovery_queries` for devtools, cybersecurity, ai-infra, vertical-ai, and data-infra.

- `.claude/skills/vc-signals/tests/test_radar_run.py`
  - Add integration tests for V3 weekly artifact contract.

- `.claude/skills/vc-signals/tests/test_radar_render.py`
  - Add rendering tests for the partner-facing sections.

- `README.md`
  - Explain Market Sector vs Source Lane.
  - Update sample artifact and limitations.

- `docs/radar-runs/marathon-weekly-v3/*`
  - Regenerate a product-reviewable captured artifact.

---

## Verification Philosophy

Each checkpoint has two gates:

- **Technical gate:** targeted tests pass and JSON/Markdown contracts are present.
- **Product gate:** the generated artifact answers a partner question better than V2.

Do not mark a checkpoint complete if tests pass but the artifact still looks like an OSS leaderboard or hides non-OSS sector signal.

---

## Checkpoint A: Market Sector And Source Lane Are Separate

Run after Tasks 1-2.

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_models.py \
  .claude/skills/vc-signals/tests/test_radar_sources.py \
  .claude/skills/vc-signals/tests/test_radar_sector_classifier.py \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  -q
```

Technical expected:

- OSS repo candidates can have `source_lane == "OSS"` and `market_sector == "Cybersecurity"` or `Devtools`.
- `sector` is still present for backward compatibility.
- Social/video source lanes normalize to `YouTube`, `TikTok`, `Instagram`, `Threads`, or `Social / Video`.
- Domainless OSS repos are not sent to Attio by repo slug.

Product expected:

- A row like AgentShield no longer appears as market sector `OSS`; it appears as `Cybersecurity` with source lane `OSS`.
- A row like agent-ci appears as `Devtools` or `AI Infra`, not blindly as `OSS`.

---

## Checkpoint B: Non-Company Signal Becomes Hunt Prompts

Run after Task 3.

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_theme_signals.py \
  .claude/skills/vc-signals/tests/test_radar_sector_intelligence.py \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  -q
```

Technical expected:

- Reddit pain alone does not create candidates.
- Clustered pain/activity creates `ThemeSignal`.
- Job posts, resume reviews, generic digests, and unnamed social hype do not create `ThemeSignal`.

Product expected:

- A sector with pain but no company now gives Marathon a useful hunt prompt.
- "No qualified candidates" is paired with a concrete reason and suggested next search, not just a rejection count.

---

## Checkpoint C: Partner Review Is Useful, Not Empty

Run after Task 4.

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_partner_review.py \
  .claude/skills/vc-signals/tests/test_radar_render.py \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  -q
```

Technical expected:

- Partner Review returns 10-15 rows when at least 10 qualified rows exist.
- Partner Review applies max 5 OSS-source-lane rows when other source lanes/sectors are available.
- Partner Review still allows OSS-heavy output when no other qualified rows exist, but renders an OSS-heavy warning.

Product expected:

- Partner Review feels like "inspect this first" instead of "only one row passed a rigid threshold."
- The section does not bury promising non-OSS rows below 40 GitHub projects.

---

## Checkpoint D: Renderer Explains The Market Map

Run after Task 5.

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_render.py \
  .claude/skills/vc-signals/tests/test_radar_sector_intelligence.py \
  -q
```

Technical expected:

- Markdown includes:
  - Run Summary
  - Partner Review
  - Full Radar
  - Sector Intelligence
  - Themes With No Company Yet
  - Weak Evidence / Rejected Summary
- Partner Review uses compact columns.
- Full Radar uses `Market Sector` and `Source Lane`.

Product expected:

- A reader can tell the difference between market sector and evidence source without asking.
- A sector with no rows still tells the partner whether it was quiet, weak, source-failed, or missing grounded company discovery.

---

## Checkpoint E: Company Discovery Queries Improve Coverage

Run after Task 6.

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_sector_config.py \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  -q
python3 - <<'PY'
import json
from pathlib import Path
config = json.loads(Path('.claude/skills/vc-signals/config/sectors.json').read_text())
for sector in ['devtools', 'cybersecurity', 'ai-infra', 'vertical-ai', 'data-infra']:
    block = config[sector].get('company_discovery_queries', {})
    assert block.get('company_launch_queries')
    assert block.get('funding_queries')
    assert block.get('yc_queries')
print('company discovery query config ok')
PY
```

Technical expected:

- Each priority sector has explicit company-discovery query blocks.
- `build_sector_collection_queries()` uses grounded web when available.
- Without grounded web, the artifact says company discovery is limited.

Product expected:

- The tool is no longer only asking "what is trending on GitHub?"
- It explicitly searches for startups, launches, YC/company pages, founder/blog evidence, and funding cues per sector.

---

## Checkpoint F: Captured All-Sector Artifact Meets Product Bar

Run after Tasks 1-7.

Use captured raw evidence first to avoid slow external runs while validating deterministic behavior:

```bash
python3 - <<'PY'
import json
import sys
import shutil
from pathlib import Path
sys.path.insert(0, str(Path('.claude/skills/vc-signals/scripts').resolve()))
import radar_run

source = Path('docs/radar-runs/marathon-weekly-v3/2026-05-04-raw-evidence.json')
if not source.exists():
    source = Path('docs/radar-runs/checkpoint-oss/2026-05-04-raw-evidence.json')
if not source.exists():
    raise SystemExit('missing captured raw evidence; run a live weekly run first')
evidence = json.loads(source.read_text())
output_dir = Path('docs/radar-runs/marathon-weekly-v3')
if output_dir.exists():
    shutil.rmtree(output_dir)
radar_run.collect_live_evidence = lambda **kwargs: evidence
result = radar_run.run_weekly_artifacts(
    output_dir=output_dir,
    sectors=radar_run.DEFAULT_SECTORS,
    github_limit=80,
    max_queries_per_sector=2,
    candidate_limit=50,
)
print(json.dumps(result))
PY
test -f docs/radar-runs/marathon-weekly-v3/weekly-preview.md
test -f docs/radar-runs/marathon-weekly-v3/candidates.json
rg -n "Run Summary|Market Sector|Source Lane|Sector Intelligence|Themes With No Company Yet|OSS-heavy|company discovery" docs/radar-runs/marathon-weekly-v3/weekly-preview.md
python3 - <<'PY'
import json
from pathlib import Path
items = json.loads(Path('docs/radar-runs/marathon-weekly-v3/candidates.json').read_text())
assert len(items) <= 50
assert all('market_sector' in item for item in items)
assert all('source_lane' in item for item in items)
assert all(item.get('market_sector') != 'OSS' for item in items if item.get('source_lane') == 'OSS' and item.get('sector_confidence') in {'High', 'Medium'})
assert not any(item.get('candidate_type') == 'oss_project' and '/' in item.get('name', '') and not item.get('domain') and item.get('attio_record_url') for item in items)
print({'candidate_count': len(items), 'market_sectors': sorted(set(item.get('market_sector', '') for item in items)), 'source_lanes': sorted(set(item.get('source_lane', '') for item in items))})
PY
```

Technical expected:

- Artifact and JSON are present.
- Candidate rows include `market_sector` and `source_lane`.
- No confident OSS-source rows render market sector `OSS`.
- No domainless OSS row has an Attio record URL.

Product review loop:

Open [weekly-preview.md](/Users/abhishekgarg/web/vc-signals/docs/radar-runs/marathon-weekly-v3/weekly-preview.md) and answer:

- Would Chase/Michael understand why a project is in Cybersecurity vs Devtools vs AI Infra?
- Does Partner Review have 10-15 useful rows or a clear warning when it cannot?
- Does every requested sector have an intelligible status?
- If rows are still mostly OSS-source-lane, does the artifact explain why and show non-company sector intelligence?
- Are there any obvious garbage rows that should have been filtered?
- Are there any non-OSS sector signals hidden only in rejection counts?

Do not proceed to README updates until the answer to the first four questions is "yes".

---

## Checkpoint G: Optional Live All-Sector Product Run

Run only after Checkpoint F passes. This can be slow.

```bash
rm -rf docs/radar-runs/marathon-weekly-v3-live
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly \
  --sectors all \
  --output-dir docs/radar-runs/marathon-weekly-v3-live \
  --max-queries-per-sector 2 \
  --github-limit 80 \
  --limit 50
test -f docs/radar-runs/marathon-weekly-v3-live/weekly-preview.md
rg -n "Run Summary|Market Sector|Source Lane|Sector Intelligence|Themes With No Company Yet" docs/radar-runs/marathon-weekly-v3-live/weekly-preview.md
```

Product expected:

- If the live run is OSS-heavy, the top summary says so and sector intelligence still gives non-OSS market context.
- If non-OSS company candidates appear, they are not buried under OSS rows in Partner Review.
- Runtime should be recorded in final notes. If it exceeds 10 minutes, recommend a follow-up performance plan.

---

## Checkpoint H: README, Secret Scan, Final Quality

Run after README and sample artifacts are updated.

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
rg -n "Market Sector|Source Lane|Sector Intelligence|Themes With No Company Yet|OSS-heavy|ScrapeCreators|TikTok|Instagram|YouTube" README.md docs/superpowers/specs/2026-05-04-sector-balanced-radar-v3-design.md
rg -n "ATTIO_ACCESS_TOKEN='|Bearer [A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-or-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|fwKR[A-Za-z0-9_-]{10,}" . --glob '!vendor/**' --glob '!.git/**' --glob '!docs/superpowers/plans/**'
git diff --check
```

Expected:

- Full test suite passes.
- README explains market sector vs source lane in plain language.
- Secret scan exits `1` with no output.
- `git diff --check` has no whitespace errors.

Product expected:

- A brand-new user can understand why a row can be `Market Sector = Cybersecurity` and `Source Lane = OSS`.
- README does not promise guaranteed funding/headcount/founder fields.
- README does not imply social/video evidence alone is enough to create high-confidence company rows.

---

## Task 1: Extend Models For V3 Concepts

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_models.py`

- [ ] **Step 1: Add failing model tests**

Append to `.claude/skills/vc-signals/tests/test_radar_models.py`:

```python
def test_candidate_v3_fields_roundtrip():
    from radar_models import Candidate

    candidate = Candidate(
        name="AgentShield",
        sector="OSS",
        market_sector="Cybersecurity",
        source_lane="OSS",
        evidence_role="oss_project",
        sector_confidence="High",
        sector_reason="Matched agent security keywords.",
        partner_priority_score=82,
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )

    payload = candidate.to_dict()
    restored = Candidate.from_dict(payload)

    assert restored.market_sector == "Cybersecurity"
    assert restored.source_lane == "OSS"
    assert restored.evidence_role == "oss_project"
    assert restored.sector_confidence == "High"
    assert restored.sector_reason == "Matched agent security keywords."
    assert restored.partner_priority_score == 82


def test_theme_signal_roundtrip():
    from radar_models import ThemeSignal

    signal = ThemeSignal(
        market_sector="Cybersecurity",
        theme="AI agent permission sprawl",
        source_lanes=["Reddit", "GitHub activity"],
        evidence_count=3,
        evidence_summary="Operators complain about agent permissions and MCP tool access.",
        why_it_matters="Security teams need visibility before agent use expands.",
        why_no_company_yet="No verified company/domain evidence appeared in this run.",
        suggested_search="AI agent security startups MCP permissions",
        confidence="Medium",
    )

    assert ThemeSignal.from_dict(signal.to_dict()).theme == "AI agent permission sprawl"


def test_sector_intelligence_roundtrip():
    from radar_models import SectorIntelligence

    item = SectorIntelligence(
        market_sector="Cybersecurity",
        status="Pain signal, no company yet",
        raw_signals=5,
        candidate_eligible_signals=0,
        promoted_candidates=0,
        rejected_signals=5,
        best_evidence="Reddit pain around AI SOC alert fatigue.",
        why_no_more_companies="No company domain or launch evidence.",
        next_hunt="Search AI SOC seed startups and founder launch posts.",
        source_errors=["last30days query timed out (120s)"],
    )

    restored = SectorIntelligence.from_dict(item.to_dict())
    assert restored.status == "Pain signal, no company yet"
    assert restored.source_errors == ["last30days query timed out (120s)"]
```

- [ ] **Step 2: Run test to verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py -q
```

Expected: fails because fields/classes do not exist.

- [ ] **Step 3: Implement model fields**

In `.claude/skills/vc-signals/scripts/radar_models.py`, add imports/classes/fields:

```python
@dataclass
class Candidate:
    ...
    market_sector: str = ""
    source_lane: str = ""
    evidence_role: str = ""
    sector_confidence: str = ""
    sector_reason: str = ""
    partner_priority_score: int = 0
```

Add after `SectorCoverage`:

```python
@dataclass
class ThemeSignal:
    market_sector: str
    theme: str
    source_lanes: list[str] = field(default_factory=list)
    evidence_count: int = 0
    evidence_summary: str = ""
    why_it_matters: str = ""
    why_no_company_yet: str = ""
    suggested_search: str = ""
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ThemeSignal":
        return cls(**_known_payload(cls, payload))


@dataclass
class SectorIntelligence:
    market_sector: str
    status: str = "No meaningful signal this week"
    raw_signals: int = 0
    candidate_eligible_signals: int = 0
    promoted_candidates: int = 0
    rejected_signals: int = 0
    best_evidence: str = ""
    why_no_more_companies: str = ""
    next_hunt: str = ""
    source_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "SectorIntelligence":
        return cls(**_known_payload(cls, payload))
```

- [ ] **Step 4: Run test to verify pass**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py -q
```

Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/tests/test_radar_models.py
git commit -m "Add radar v3 model fields"
```

---

## Task 2: Add Sector Classifier And Source Lane Normalization

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_sector_classifier.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_sector_classifier.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_sources.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_sources.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Add classifier tests**

Create `.claude/skills/vc-signals/tests/test_radar_sector_classifier.py`:

```python
from __future__ import annotations


def test_classifies_agent_security_repo_as_cybersecurity():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="affaan-m/agentshield",
        text="AI agent security scanner for MCP servers and tool permissions",
        source_lane="OSS",
    )

    assert result.market_sector == "Cybersecurity"
    assert result.sector_confidence == "High"
    assert "security" in result.sector_reason.lower()


def test_classifies_github_actions_repo_as_devtools():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="redwoodjs/agent-ci",
        text="Agent-CI is local GitHub Actions for your agents",
        source_lane="OSS",
    )

    assert result.market_sector == "Devtools"
    assert result.sector_confidence in {"High", "Medium"}


def test_classifies_lineage_signal_as_data_infra():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="What are people using for data lineage now?",
        text="data warehouse ETL lineage dbt pain",
        source_lane="Reddit",
    )

    assert result.market_sector == "Data Infra"


def test_unclassified_when_keywords_are_weak():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="Small helper script",
        text="tiny utility",
        source_lane="OSS",
    )

    assert result.market_sector == "Unclassified"
    assert result.sector_confidence == "Low"
```

- [ ] **Step 2: Run classifier tests to verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_sector_classifier.py -q
```

Expected: fails because module does not exist.

- [ ] **Step 3: Implement classifier**

Create `.claude/skills/vc-signals/scripts/radar_sector_classifier.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectorClassification:
    market_sector: str
    sector_confidence: str
    sector_reason: str


SECTOR_KEYWORDS = {
    "Cybersecurity": (
        "security", "soc", "appsec", "pentest", "penetration", "prompt injection",
        "jailbreak", "mcp permission", "vulnerability", "auth", "secrets",
        "compliance", "red team", "cloud security", "phishing",
    ),
    "Devtools": (
        "ci", "testing", "github actions", "build", "deploy", "developer workflow",
        "code review", "sdk", "ide", "terminal", "pull request", "test automation",
    ),
    "AI Infra": (
        "agent runtime", "mcp", "eval", "inference", "observability", "model routing",
        "rag", "vector", "llm app", "agent", "embedding", "trace",
    ),
    "Data Infra": (
        "pipeline", "warehouse", "etl", "lineage", "data quality", "lakehouse",
        "analytics", "dbt", "database", "data engineering",
    ),
    "Vertical AI": (
        "sales", "legal", "healthcare", "finance", "insurance", "recruiting",
        "customer support", "back office", "operator workflow", "smb", "workflow",
    ),
}


def _score(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def classify_market_sector(*, title: str = "", text: str = "", source_lane: str = "") -> SectorClassification:
    blob = f"{title} {text}".lower()
    matches = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        matched = _score(blob, keywords)
        if matched:
            matches.append((sector, matched))

    if not matches:
        return SectorClassification(
            market_sector="Unclassified",
            sector_confidence="Low",
            sector_reason=f"No strong market-sector keywords found; source lane is {source_lane or 'unknown'}.",
        )

    matches.sort(key=lambda item: (len(item[1]), sum(len(keyword) for keyword in item[1])), reverse=True)
    sector, matched = matches[0]
    confidence = "High" if len(matched) >= 2 else "Medium"
    return SectorClassification(
        market_sector=sector,
        sector_confidence=confidence,
        sector_reason="Matched " + ", ".join(matched[:4]) + " keywords.",
    )
```

- [ ] **Step 4: Add source lane tests**

Append to `.claude/skills/vc-signals/tests/test_radar_sources.py`:

```python
def test_source_lane_preserves_social_video_sources():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="vertical-ai",
        item={
            "source": "tiktok",
            "title": "Founder demo: AI receptionist for dental offices",
            "url": "https://tiktok.com/@demo/video/1",
            "company_name": "DentalDesk AI",
            "website": "https://dentaldesk.ai",
        },
    )

    assert signal.role == "product_demo"
    assert signal.metadata["source_lane"] == "TikTok"
    assert signal.can_create_candidate is True


def test_generic_social_video_does_not_create_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="vertical-ai",
        item={
            "source": "instagram",
            "title": "AI will change everything",
            "url": "https://instagram.com/p/1",
        },
    )

    assert signal.role == "social_demo"
    assert signal.metadata["source_lane"] == "Instagram"
    assert signal.can_create_candidate is False
```

- [ ] **Step 5: Implement source lane normalization**

Modify `.claude/skills/vc-signals/scripts/radar_sources.py`:

```python
SOURCE_LANE_LABELS = {
    "reddit": "Reddit",
    "hackernews": "Hacker News",
    "github": "OSS",
    "grounding": "Grounded web",
    "web": "Grounded web",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "threads": "Threads",
}


def source_lane_for(source: str) -> str:
    return SOURCE_LANE_LABELS.get((source or "").lower(), source or "Unknown")


def _social_has_company_evidence(item: dict) -> bool:
    return bool(
        (item.get("company_name") or item.get("name"))
        and (
            item.get("website")
            or item.get("domain")
            or item.get("company_linkedin")
            or item.get("founder")
            or item.get("founders")
            or item.get("waitlist_url")
        )
    )
```

Then ensure every `Signal(... metadata=item.copy())` path sets:

```python
metadata = item.copy()
metadata.setdefault("source_lane", source_lane_for(source))
```

For `source in {"youtube", "tiktok", "instagram", "threads"}`:

```python
role = "product_demo" if _social_has_company_evidence(item) else "social_demo"
return Signal(
    source=source,
    role=role,
    title=title,
    url=url,
    sector=sector,
    text=text,
    can_create_candidate=role == "product_demo",
    evidence_strength=40 if role == "product_demo" else 25,
    reason="Social/video evidence can create a candidate only when company identity and product evidence are clear." if role == "product_demo" else "Social/video evidence supports demos or demand, but should not alone create company rows.",
    metadata=metadata,
)
```

- [ ] **Step 6: Wire classifier into candidate creation**

Modify `_candidate_from_signal()` in `.claude/skills/vc-signals/scripts/radar_run.py`:

```python
from radar_sector_classifier import classify_market_sector
```

After `candidate = Candidate(...)`, before source enrichment:

```python
classification = classify_market_sector(
    title=name,
    text=f"{signal.title} {signal.text} {item.get('description', '')} {' '.join(item.get('topics', []) or [])}",
    source_lane=item.get("source_lane", ""),
)
candidate.market_sector = classification.market_sector
candidate.source_lane = item.get("source_lane") or ("OSS" if signal.role == "oss_project" else signal.source)
candidate.evidence_role = signal.role
candidate.sector_confidence = classification.sector_confidence
candidate.sector_reason = classification.sector_reason
candidate.sector = candidate.market_sector if candidate.market_sector != "Unclassified" else candidate.sector
```

- [ ] **Step 7: Add integration tests**

Append to `.claude/skills/vc-signals/tests/test_radar_run.py`:

```python
def test_candidate_promotion_sets_market_sector_and_source_lane_for_oss():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="oss",
        item={
            "source": "github",
            "title": "affaan-m/agentshield",
            "url": "https://github.com/affaan-m/agentshield",
            "description": "AI agent security scanner for MCP servers and tool permissions",
            "velocity": {"stars_last_30d": 187},
        },
    )

    candidate = promote_signals_to_candidates([signal])["candidates"][0]

    assert candidate.source_lane == "OSS"
    assert candidate.market_sector == "Cybersecurity"
    assert candidate.sector == "Cybersecurity"
    assert candidate.evidence_role == "oss_project"
    assert candidate.sector_confidence == "High"


def test_social_product_demo_can_create_candidate_with_source_lane():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="vertical-ai",
        item={
            "source": "tiktok",
            "title": "Founder demo: AI receptionist for dental offices",
            "url": "https://tiktok.com/@demo/video/1",
            "company_name": "DentalDesk AI",
            "website": "https://dentaldesk.ai",
            "snippet": "demo of appointment scheduling workflow",
        },
    )

    candidate = promote_signals_to_candidates([signal])["candidates"][0]

    assert candidate.name == "DentalDesk AI"
    assert candidate.source_lane == "TikTok"
    assert candidate.evidence_role == "product_demo"
    assert candidate.market_sector == "Vertical AI"
```

- [ ] **Step 8: Run Checkpoint A**

Run all commands in Checkpoint A. Fix failures before proceeding.

- [ ] **Step 9: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_sector_classifier.py .claude/skills/vc-signals/scripts/radar_sources.py .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_sector_classifier.py .claude/skills/vc-signals/tests/test_radar_sources.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Separate market sector from source lane"
```

---

## Task 3: Add Theme Signals And Sector Intelligence

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_theme_signals.py`
- Create: `.claude/skills/vc-signals/scripts/radar_sector_intelligence.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_theme_signals.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_sector_intelligence.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Add theme signal tests**

Create `.claude/skills/vc-signals/tests/test_radar_theme_signals.py`:

```python
from __future__ import annotations


def test_clustered_reddit_pain_creates_theme_signal():
    from radar_theme_signals import build_theme_signals
    from radar_sources import classify_source_item

    signals = [
        classify_source_item(
            sector="cybersecurity",
            item={"source": "reddit", "title": "How are teams controlling AI agent permissions?", "url": "https://reddit.com/1"},
        ),
        classify_source_item(
            sector="cybersecurity",
            item={"source": "reddit", "title": "MCP tools are creating security review headaches", "url": "https://reddit.com/2"},
        ),
    ]

    themes = build_theme_signals(signals, sectors=("cybersecurity",))

    assert len(themes) == 1
    assert themes[0].market_sector == "Cybersecurity"
    assert themes[0].theme == "AI agent security"
    assert themes[0].confidence == "Medium"
    assert "No verified company" in themes[0].why_no_company_yet


def test_generic_jobs_and_resume_posts_do_not_create_theme_signal():
    from radar_theme_signals import build_theme_signals
    from radar_sources import classify_source_item

    signals = [
        classify_source_item(
            sector="data-infra",
            item={"source": "reddit", "title": "Remote Job - Data Engineering Manager", "url": "https://reddit.com/job"},
        ),
        classify_source_item(
            sector="data-infra",
            item={"source": "reddit", "title": "Review my resume for data engineer roles", "url": "https://reddit.com/resume"},
        ),
    ]

    assert build_theme_signals(signals, sectors=("data-infra",)) == []
```

- [ ] **Step 2: Implement theme signals**

Create `.claude/skills/vc-signals/scripts/radar_theme_signals.py`:

```python
from __future__ import annotations

from collections import defaultdict

from radar_models import Signal, ThemeSignal
from radar_sector_classifier import classify_market_sector


NOISE_TERMS = (
    "remote job", "review my resume", "hiring", "salary", "job -", "daily digest",
    "news roundup", "statistics of the week", "course", "tutorial",
)
THEME_KEYWORDS = (
    ("security", "AI agent security"),
    ("permission", "AI agent security"),
    ("mcp", "Agent runtime infrastructure"),
    ("lineage", "AI data infrastructure"),
    ("data", "AI data infrastructure"),
    ("workflow", "Vertical AI operations"),
    ("sales", "Vertical AI operations"),
    ("eval", "Agent reliability and evals"),
    ("testing", "Agent reliability and evals"),
)


def _is_noise(signal: Signal) -> bool:
    text = f"{signal.title} {signal.text}".lower()
    return any(term in text for term in NOISE_TERMS)


def infer_theme_from_text(text: str) -> str:
    lower = text.lower()
    for keyword, theme in THEME_KEYWORDS:
        if keyword in lower:
            return theme
    return "Emerging technical signal"


def build_theme_signals(signals: list[Signal], *, sectors: tuple[str, ...]) -> list[ThemeSignal]:
    grouped = defaultdict(list)
    for signal in signals:
        if signal.can_create_candidate or _is_noise(signal):
            continue
        if signal.source not in {"reddit", "github", "hackernews", "youtube", "tiktok", "instagram", "threads"}:
            continue
        classification = classify_market_sector(title=signal.title, text=signal.text, source_lane=signal.metadata.get("source_lane", signal.source))
        market_sector = classification.market_sector if classification.market_sector != "Unclassified" else signal.sector
        theme = infer_theme_from_text(f"{signal.title} {signal.text}")
        grouped[(market_sector, theme)].append(signal)

    out = []
    for (market_sector, theme), items in grouped.items():
        source_lanes = sorted({item.metadata.get("source_lane", item.source) for item in items})
        if len(items) < 2 and len(source_lanes) < 2:
            continue
        titles = "; ".join(item.title for item in items[:3])
        out.append(ThemeSignal(
            market_sector=market_sector if market_sector else "Unclassified",
            theme=theme,
            source_lanes=source_lanes,
            evidence_count=len(items),
            evidence_summary=titles,
            why_it_matters=f"Repeated non-company signal suggests buyer/operator pain around {theme}.",
            why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
            suggested_search=f"{theme} startups Seed Series A founder launch",
            confidence="Medium" if len(items) >= 2 else "Low",
        ))
    return sorted(out, key=lambda item: (item.confidence == "Medium", item.evidence_count), reverse=True)[:8]
```

- [ ] **Step 3: Add sector intelligence tests**

Create `.claude/skills/vc-signals/tests/test_radar_sector_intelligence.py`:

```python
from __future__ import annotations


def test_sector_intelligence_explains_pain_signal_no_company():
    from radar_models import RejectedSignal, SectorCoverage, ThemeSignal
    from radar_sector_intelligence import build_sector_intelligence

    coverage = {
        "cybersecurity": SectorCoverage(sector="cybersecurity", raw_signals=2, candidates=0, rejected=2)
    }
    theme_signals = [
        ThemeSignal(
            market_sector="Cybersecurity",
            theme="AI agent security",
            source_lanes=["Reddit"],
            evidence_count=2,
            evidence_summary="Agent permission pain",
            why_it_matters="Repeated security pain.",
            why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
            suggested_search="AI agent security startups",
            confidence="Medium",
        )
    ]

    result = build_sector_intelligence(
        sectors=("cybersecurity",),
        coverage=coverage,
        candidates=[],
        rejected=[RejectedSignal(sector="cybersecurity", source="reddit", title="x", reason="source_not_candidate_eligible")],
        theme_signals=theme_signals,
        source_errors={},
        grounded_available=False,
    )

    item = result[0]
    assert item.market_sector == "Cybersecurity"
    assert item.status == "Pain signal, no company yet"
    assert "grounded company discovery" in item.why_no_more_companies.lower()
    assert "AI agent security startups" in item.next_hunt


def test_sector_intelligence_marks_oss_project_candidates():
    from radar_models import Candidate, SectorCoverage
    from radar_sector_intelligence import build_sector_intelligence

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        market_sector="Cybersecurity",
        source_lane="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )

    result = build_sector_intelligence(
        sectors=("cybersecurity",),
        coverage={"cybersecurity": SectorCoverage(sector="cybersecurity", raw_signals=4, candidates=1, rejected=3)},
        candidates=[candidate],
        rejected=[],
        theme_signals=[],
        source_errors={},
        grounded_available=True,
    )

    assert result[0].status == "OSS/project candidates found"
    assert "OSS" in result[0].best_evidence
```

- [ ] **Step 4: Implement sector intelligence**

Create `.claude/skills/vc-signals/scripts/radar_sector_intelligence.py`:

```python
from __future__ import annotations

from radar_models import Candidate, RejectedSignal, SectorCoverage, SectorIntelligence, ThemeSignal


MARKET_SECTOR_LABELS = {
    "devtools": "Devtools",
    "cybersecurity": "Cybersecurity",
    "ai-infra": "AI Infra",
    "vertical-ai": "Vertical AI",
    "data-infra": "Data Infra",
    "oss": "OSS",
}


def _label(sector: str) -> str:
    return MARKET_SECTOR_LABELS.get(sector, sector)


def _sector_candidates(candidates: list[Candidate], market_sector: str) -> list[Candidate]:
    return [candidate for candidate in candidates if (candidate.market_sector or candidate.sector) == market_sector]


def _sector_themes(theme_signals: list[ThemeSignal], market_sector: str) -> list[ThemeSignal]:
    return [theme for theme in theme_signals if theme.market_sector == market_sector]


def build_sector_intelligence(
    *,
    sectors: tuple[str, ...],
    coverage: dict[str, SectorCoverage],
    candidates: list[Candidate],
    rejected: list[RejectedSignal],
    theme_signals: list[ThemeSignal],
    source_errors: dict[str, list[str]],
    grounded_available: bool,
) -> list[SectorIntelligence]:
    out = []
    for sector in sectors:
        if sector == "oss":
            continue
        market_sector = _label(sector)
        cov = coverage.get(sector, SectorCoverage(sector=sector))
        sector_candidates = _sector_candidates(candidates, market_sector)
        sector_rejected = [item for item in rejected if item.sector == sector]
        sector_themes = _sector_themes(theme_signals, market_sector)
        source_lanes = sorted({candidate.source_lane for candidate in sector_candidates if candidate.source_lane})

        if any(candidate.candidate_type != "oss_project" for candidate in sector_candidates):
            status = "Company candidates found"
        elif sector_candidates:
            status = "OSS/project candidates found"
        elif sector_themes:
            status = "Pain signal, no company yet"
        elif source_errors.get(sector):
            status = "Source failure / incomplete coverage"
        else:
            status = "No meaningful signal this week"

        if sector_candidates:
            best_evidence = f"{len(sector_candidates)} promoted rows from {', '.join(source_lanes) or 'available sources'}."
        elif sector_themes:
            best_evidence = sector_themes[0].evidence_summary
        else:
            best_evidence = "No promoted candidate evidence."

        why = ""
        if not sector_candidates:
            why = "No verified company/domain/founder evidence appeared in this run."
            if not grounded_available:
                why += " Grounded company discovery is not configured, so non-OSS discovery is limited."
        elif not any(candidate.candidate_type != "oss_project" for candidate in sector_candidates):
            why = "Promoted rows are OSS/project evidence; no verified company pages or funding/company discovery rows qualified."

        next_hunt = sector_themes[0].suggested_search if sector_themes else f"{market_sector} startups Seed Series A founder launch"

        out.append(SectorIntelligence(
            market_sector=market_sector,
            status=status,
            raw_signals=cov.raw_signals,
            candidate_eligible_signals=sum(1 for candidate in sector_candidates if candidate.source_lane != "Reddit"),
            promoted_candidates=len(sector_candidates),
            rejected_signals=len(sector_rejected) or cov.rejected,
            best_evidence=best_evidence,
            why_no_more_companies=why,
            next_hunt=next_hunt,
            source_errors=source_errors.get(sector, []),
        ))
    return out
```

- [ ] **Step 5: Wire theme signals and sector intelligence into weekly run**

Modify `run_weekly_artifacts()` in `.claude/skills/vc-signals/scripts/radar_run.py`:

```python
from radar_theme_signals import build_theme_signals
from radar_sector_intelligence import build_sector_intelligence
```

After `promotion = promote_signals_to_candidates(...)`:

```python
theme_signals = build_theme_signals(signal_result["signals"], sectors=sectors)
source_errors = {
    sector: payload.get("errors", [])
    for sector, payload in evidence.get("last30days", {}).items()
    if payload.get("errors")
}
```

After `_update_sector_coverage(...)`:

```python
sector_intelligence = build_sector_intelligence(
    sectors=sectors,
    coverage=signal_result["coverage"],
    candidates=scored_candidates,
    rejected=promotion["rejected"],
    theme_signals=theme_signals,
    source_errors=source_errors,
    grounded_available=_grounded_search_available(),
)
```

Pass `theme_signals` and `sector_intelligence` to `render_weekly_brief()` and write JSON artifacts:

```python
(output_dir / "theme-signals.json").write_text(json.dumps([item.to_dict() for item in theme_signals], indent=2))
(output_dir / "sector-intelligence.json").write_text(json.dumps([item.to_dict() for item in sector_intelligence], indent=2))
```

- [ ] **Step 6: Add run artifact integration test**

Append to `.claude/skills/vc-signals/tests/test_radar_run.py`:

```python
def test_run_weekly_artifacts_writes_theme_and_sector_intelligence(tmp_path, monkeypatch):
    import json
    import radar_run

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {"source": "reddit", "title": "How are teams controlling AI agent permissions?", "url": "https://reddit.com/1"},
                        {"source": "reddit", "title": "MCP tools are creating security review headaches", "url": "https://reddit.com/2"},
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

    radar_run.run_weekly_artifacts(output_dir=tmp_path, sectors=("cybersecurity",), github_limit=0)

    assert (tmp_path / "theme-signals.json").exists()
    assert (tmp_path / "sector-intelligence.json").exists()
    themes = json.loads((tmp_path / "theme-signals.json").read_text())
    sectors = json.loads((tmp_path / "sector-intelligence.json").read_text())
    assert themes[0]["market_sector"] == "Cybersecurity"
    assert sectors[0]["status"] == "Pain signal, no company yet"
```

- [ ] **Step 7: Run Checkpoint B**

Run all commands in Checkpoint B. Fix failures before proceeding.

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_theme_signals.py .claude/skills/vc-signals/scripts/radar_sector_intelligence.py .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_theme_signals.py .claude/skills/vc-signals/tests/test_radar_sector_intelligence.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Add sector intelligence and theme signals"
```

---

## Task 4: Add Partner Review Priority And Diversity

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_partner_review.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_partner_review.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_render.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_render.py`

- [ ] **Step 1: Add partner review tests**

Create `.claude/skills/vc-signals/tests/test_radar_partner_review.py`:

```python
from __future__ import annotations


def _candidate(name, market_sector, source_lane, score=70, evidence=50, tier="Watchlist"):
    from radar_models import Candidate

    return Candidate(
        name=name,
        sector=market_sector,
        market_sector=market_sector,
        source_lane=source_lane,
        theme="Agent security",
        source=f"https://example.com/{name}",
        candidate_type="oss_project" if source_lane == "OSS" else "company_web",
        investment_interest_score=score,
        evidence_confidence_score=evidence,
        investment_interest="High" if score >= 70 else "Medium",
        evidence_confidence="Medium",
        tier=tier,
        action="watch",
    )


def test_partner_review_returns_10_to_15_rows_when_available():
    from radar_partner_review import select_partner_review

    candidates = [_candidate(f"Company {i}", "Cybersecurity", "Grounded web", 80 - i, 60) for i in range(20)]

    partner = select_partner_review(candidates, min_rows=10, max_rows=15)

    assert 10 <= len(partner) <= 15
    assert all(item.partner_priority_score > 0 for item in partner)


def test_partner_review_caps_oss_when_other_sources_exist():
    from radar_partner_review import select_partner_review

    candidates = []
    candidates.extend(_candidate(f"OSS {i}", "Cybersecurity", "OSS", 90 - i, 70) for i in range(12))
    candidates.extend(_candidate(f"Web {i}", "Devtools", "Grounded web", 70 - i, 60) for i in range(6))

    partner = select_partner_review(candidates, min_rows=10, max_rows=15, max_oss_rows=5)

    assert sum(1 for item in partner if item.source_lane == "OSS") <= 5
    assert any(item.source_lane == "Grounded web" for item in partner)


def test_partner_review_allows_oss_heavy_when_no_alternative_exists():
    from radar_partner_review import select_partner_review

    candidates = [_candidate(f"OSS {i}", "Cybersecurity", "OSS", 90 - i, 70) for i in range(12)]

    partner = select_partner_review(candidates, min_rows=10, max_rows=15, max_oss_rows=5)

    assert len(partner) == 12
    assert sum(1 for item in partner if item.source_lane == "OSS") == 12
```

- [ ] **Step 2: Implement partner review selector**

Create `.claude/skills/vc-signals/scripts/radar_partner_review.py`:

```python
from __future__ import annotations

from radar_models import Candidate


def compute_partner_priority(candidate: Candidate) -> int:
    score = int(candidate.investment_interest_score or 0)
    score += int(candidate.evidence_confidence_score or 0) // 2
    if candidate.tier == "Partner Review":
        score += 15
    if candidate.weekly_tag == "NEW":
        score += 8
    if candidate.weekly_tag == "RETURNING":
        score += 5
    if candidate.attio_status in {"no_match", "stale", "no_owner"}:
        score += 5
    if candidate.source_lane == "OSS":
        score += min(15, int(candidate.oss_company_formation_score or 0) // 5)
    if candidate.action == "likely too late":
        score -= 30
    if candidate.market_sector == "Unclassified":
        score -= 15
    return max(0, min(150, score))


def select_partner_review(
    candidates: list[Candidate],
    *,
    min_rows: int = 10,
    max_rows: int = 15,
    max_oss_rows: int = 5,
) -> list[Candidate]:
    for candidate in candidates:
        candidate.partner_priority_score = compute_partner_priority(candidate)

    ranked = sorted(candidates, key=lambda item: item.partner_priority_score, reverse=True)
    non_oss_exists = any(item.source_lane != "OSS" for item in ranked)
    selected = []
    oss_count = 0
    seen_keys = set()

    for candidate in ranked:
        if len(selected) >= max_rows:
            break
        key = candidate.stable_key or candidate.name
        if key in seen_keys:
            continue
        if non_oss_exists and candidate.source_lane == "OSS" and oss_count >= max_oss_rows:
            continue
        selected.append(candidate)
        seen_keys.add(key)
        if candidate.source_lane == "OSS":
            oss_count += 1

    if len(selected) < min_rows:
        for candidate in ranked:
            if len(selected) >= min(max_rows, len(ranked)):
                break
            key = candidate.stable_key or candidate.name
            if key in seen_keys:
                continue
            selected.append(candidate)
            seen_keys.add(key)

    return selected
```

- [ ] **Step 3: Wire Partner Review into renderer**

Modify `.claude/skills/vc-signals/scripts/radar_render.py` so `render_weekly_brief()` accepts optional `partner_review`:

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
) -> str:
    partner = partner_review if partner_review is not None else candidates[:15]
```

Add compact partner table helper:

```python
def _partner_table(candidates: list) -> str:
    rows = [
        "| Company / Project | Market Sector | Source Lane | Theme | Tag | Tier | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for candidate in candidates:
        rows.append(
            f"| {candidate.name} | {candidate.market_sector or candidate.sector} | {candidate.source_lane} | {candidate.theme} | "
            f"{candidate.weekly_tag} | {candidate.tier} | {candidate.investment_interest} | {candidate.evidence_confidence} | "
            f"{candidate.attio_status} | {candidate.action} | {candidate.why_on_radar} | {candidate.why_this_may_be_noise} |"
        )
    return "\n".join(rows)
```

Use `_partner_table(partner)` for Partner Review.

- [ ] **Step 4: Wire selector into weekly run**

Modify `.claude/skills/vc-signals/scripts/radar_run.py`:

```python
from radar_partner_review import select_partner_review
```

After history:

```python
partner_review = select_partner_review(scored_candidates)
```

Pass `partner_review=partner_review` into `render_weekly_brief()`.

- [ ] **Step 5: Add render assertion**

Append to `.claude/skills/vc-signals/tests/test_radar_render.py`:

```python
def test_partner_review_uses_compact_market_sector_source_lane_columns():
    from radar_models import Candidate
    from radar_render import render_weekly_brief

    candidate = Candidate(
        name="AgentShield",
        sector="Cybersecurity",
        market_sector="Cybersecurity",
        source_lane="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        tier="Watchlist",
        investment_interest="High",
        evidence_confidence="Medium",
        attio_status="no_match",
        action="track company formation",
        why_on_radar="Fast OSS momentum.",
        why_this_may_be_noise="Repo may not become a company.",
    )

    markdown = render_weekly_brief([candidate], {}, [], partner_review=[candidate])

    assert "| Company / Project | Market Sector | Source Lane | Theme | Tag | Tier | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise |" in markdown
    assert "| AgentShield | Cybersecurity | OSS | AI agent security |" in markdown
```

- [ ] **Step 6: Run Checkpoint C**

Run all commands in Checkpoint C. Fix failures before proceeding.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_partner_review.py .claude/skills/vc-signals/scripts/radar_render.py .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_partner_review.py .claude/skills/vc-signals/tests/test_radar_render.py
git commit -m "Add sector-balanced partner review"
```

---

## Task 5: Render V3 Partner Artifact

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_render.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_render.py`

- [ ] **Step 1: Add V3 artifact render test**

Append to `.claude/skills/vc-signals/tests/test_radar_render.py`:

```python
def test_weekly_brief_renders_sector_intelligence_and_theme_signals():
    from radar_models import Candidate, SectorIntelligence, ThemeSignal
    from radar_render import render_weekly_brief

    candidate = Candidate(
        name="AgentShield",
        sector="Cybersecurity",
        market_sector="Cybersecurity",
        source_lane="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        tier="Partner Review",
        investment_interest="High",
        evidence_confidence="Medium",
        attio_status="no_match",
        action="track company formation",
        why_on_radar="Fast OSS momentum.",
        why_this_may_be_noise="Repo may not become a company.",
    )
    intelligence = [
        SectorIntelligence(
            market_sector="Cybersecurity",
            status="OSS/project candidates found",
            raw_signals=12,
            candidate_eligible_signals=4,
            promoted_candidates=1,
            rejected_signals=8,
            best_evidence="1 promoted row from OSS.",
            why_no_more_companies="No verified company pages qualified.",
            next_hunt="AI agent security startups",
        )
    ]
    themes = [
        ThemeSignal(
            market_sector="Data Infra",
            theme="Data lineage",
            source_lanes=["Reddit"],
            evidence_count=2,
            evidence_summary="Teams complain about lineage gaps.",
            why_it_matters="Operator pain is recurring.",
            why_no_company_yet="No verified company/domain evidence.",
            suggested_search="data lineage AI startups",
            confidence="Medium",
        )
    ]

    markdown = render_weekly_brief(
        [candidate],
        {},
        [],
        partner_review=[candidate],
        sector_intelligence=intelligence,
        theme_signals=themes,
    )

    assert "## Run Summary" in markdown
    assert "## Sector Intelligence" in markdown
    assert "### Cybersecurity" in markdown
    assert "Status: OSS/project candidates found" in markdown
    assert "## Themes With No Company Yet" in markdown
    assert "| Data Infra | Data lineage |" in markdown
```

- [ ] **Step 2: Implement run summary**

In `.claude/skills/vc-signals/scripts/radar_render.py`, add:

```python
def _run_summary(candidates: list) -> str:
    market_sectors = sorted({(candidate.market_sector or candidate.sector) for candidate in candidates if (candidate.market_sector or candidate.sector)})
    source_counts = {}
    for candidate in candidates:
        lane = candidate.source_lane or "Unknown"
        source_counts[lane] = source_counts.get(lane, 0) + 1
    source_mix = ", ".join(f"{count} {lane}" for lane, count in sorted(source_counts.items(), key=lambda item: item[0]))
    lines = [
        "## Run Summary",
        "",
        f"This run produced {len(candidates)} qualified rows across {len(market_sectors)} market sectors.",
        f"Source mix: {source_mix or 'No qualified source lanes.'}.",
    ]
    if candidates and all((candidate.source_lane == "OSS") for candidate in candidates):
        lines.append("Warning: this run is OSS-heavy; non-OSS company discovery did not produce qualified rows.")
    return "\n".join(lines)
```

- [ ] **Step 3: Implement sector intelligence rendering**

Add:

```python
def _sector_intelligence_section(items: list) -> str:
    lines = ["## Sector Intelligence", ""]
    if not items:
        return "## Sector Intelligence\n\n- No sector intelligence generated."
    for item in items:
        lines.extend([
            f"### {item.market_sector}",
            f"Status: {item.status}",
            f"Signals: {item.raw_signals} raw, {item.candidate_eligible_signals} candidate-eligible, {item.promoted_candidates} promoted, {item.rejected_signals} rejected.",
            f"Best evidence: {item.best_evidence or 'No promoted evidence.'}",
            f"Why no more companies: {item.why_no_more_companies or 'Qualified candidates were found.'}",
            f"Next hunt: {item.next_hunt or 'No follow-up search suggested.'}",
            "",
        ])
        if item.source_errors:
            lines.append("Source errors: " + "; ".join(item.source_errors))
            lines.append("")
    return "\n".join(lines).rstrip()
```

- [ ] **Step 4: Implement theme signal rendering**

Add:

```python
def _theme_signals_table(theme_signals: list) -> str:
    if not theme_signals:
        return "## Themes With No Company Yet\n\n- No meaningful non-company themes met the evidence bar."
    rows = [
        "## Themes With No Company Yet",
        "",
        "| Market Sector | Theme | Evidence | Why It Matters | Why No Company Yet | Suggested Search |",
        "|---|---|---|---|---|---|",
    ]
    for item in theme_signals[:8]:
        rows.append(
            f"| {item.market_sector} | {item.theme} | {item.evidence_summary} | {item.why_it_matters} | "
            f"{item.why_no_company_yet} | {item.suggested_search} |"
        )
    return "\n".join(rows)
```

- [ ] **Step 5: Update Full Radar table columns**

Modify `_table()` header in `radar_render.py`:

```python
"| Company / Project | Market Sector | Source Lane | Theme | Tag | Stage | Raised | Headcount | Founders | Tier | Interest | Evidence | Attio | Attio Owner | Attio Last Touch | Attio URL | Staleness | Action | OSS Score | Action Reason | LinkedIn | X | Why On Radar | Why This May Be Noise | Best Source |"
```

Rows should use:

```python
candidate.market_sector or candidate.sector
candidate.source_lane
```

- [ ] **Step 6: Run Checkpoint D**

Run all commands in Checkpoint D. Fix failures before proceeding.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_render.py .claude/skills/vc-signals/tests/test_radar_render.py
git commit -m "Render sector-balanced radar artifact"
```

---

## Task 6: Add Sector-Specific Company Discovery Query Config

**Files:**
- Modify: `.claude/skills/vc-signals/config/sectors.json`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_sector_config.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Add config validation test**

Append to `.claude/skills/vc-signals/tests/test_sector_config.py`:

```python
def test_priority_sectors_have_company_discovery_queries():
    import json
    from pathlib import Path

    config = json.loads(Path(".claude/skills/vc-signals/config/sectors.json").read_text())
    for sector in ["devtools", "cybersecurity", "ai-infra", "vertical-ai", "data-infra"]:
        block = config[sector].get("company_discovery_queries", {})
        assert block.get("company_launch_queries"), sector
        assert block.get("funding_queries"), sector
        assert block.get("yc_queries"), sector
```

- [ ] **Step 2: Add query builder test**

Append to `.claude/skills/vc-signals/tests/test_radar_run.py`:

```python
def test_build_sector_collection_queries_uses_company_discovery_block_when_grounded():
    from radar_run import build_sector_collection_queries

    config = {
        "cybersecurity": {
            "display_name": "Cybersecurity",
            "discovery_queries": [],
            "company_discovery_queries": {
                "company_launch_queries": ["AI security startup launch"],
                "funding_queries": ["AI security startup raises seed"],
                "yc_queries": ["site:ycombinator.com/companies AI security startup"],
                "founder_queries": ["AI security startup founder blog"],
                "technical_blog_queries": ["AI security startup technical blog"],
            },
        }
    }

    queries = build_sector_collection_queries(
        "cybersecurity",
        config,
        grounded_available=True,
        social_available=False,
        max_queries=4,
    )

    topics = " ".join(query["topic"] for query in queries)
    assert "site:ycombinator.com/companies AI security startup" in topics
    assert "AI security startup raises seed" in topics
    assert any(query.get("kind") == "company_discovery" for query in queries)
```

- [ ] **Step 3: Update sectors config**

Add `company_discovery_queries` to each priority sector in `.claude/skills/vc-signals/config/sectors.json`.

Use this shape for each sector:

```json
"company_discovery_queries": {
  "company_launch_queries": [
    "Show HN <sector phrase> startup AI",
    "Launch HN <sector phrase> Seed Series A"
  ],
  "funding_queries": [
    "<sector phrase> startup raises seed AI",
    "<sector phrase> startup Series A emerging"
  ],
  "yc_queries": [
    "site:ycombinator.com/companies <sector phrase> startup",
    "site:ycombinator.com/companies AI <sector phrase>"
  ],
  "founder_queries": [
    "<sector phrase> startup founder technical blog",
    "<sector phrase> founder launch AI startup"
  ],
  "technical_blog_queries": [
    "<sector phrase> startup technical blog",
    "<sector phrase> product launch engineering blog"
  ]
}
```

Use sector phrases:

- devtools: `developer tools AI coding agents CI testing`
- cybersecurity: `AI security MCP agent permissions SOC AppSec`
- ai-infra: `AI infrastructure agent runtime evals observability inference`
- vertical-ai: `vertical AI workflow automation SMB operator`
- data-infra: `data infrastructure AI data pipelines lineage observability`

- [ ] **Step 4: Update query builder**

In `build_sector_collection_queries()`, when `grounded_available` is true and `company_discovery_queries` exists, build company-discovery query specs from `yc_queries`, `funding_queries`, and `company_launch_queries` before the generic conversation query:

```python
company_queries = config.get("company_discovery_queries", {})
if grounded_available and company_queries:
    for kind, key in (
        ("yc_company", "yc_queries"),
        ("funding_company", "funding_queries"),
        ("company_launch", "company_launch_queries"),
    ):
        for topic in company_queries.get(key, [])[:1]:
            queries.append({
                "kind": kind,
                "topic": topic,
                "sources": _sources("grounding", "hackernews", "github", social_available=social_available),
                "web_backend": "auto",
                "lookback_days": lookback_days,
            })
```

- [ ] **Step 5: Run Checkpoint E**

Run all commands in Checkpoint E. Fix failures before proceeding.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/config/sectors.json .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_sector_config.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Add sector-specific company discovery queries"
```

---

## Task 7: End-To-End Artifact And README

**Files:**
- Modify: `README.md`
- Modify/Add: `docs/radar-runs/marathon-weekly-v3/*`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Run Checkpoint F**

Run all commands in Checkpoint F. Fix product failures before proceeding.

- [ ] **Step 2: Inspect artifact product quality**

Open:

[weekly-preview.md](/Users/abhishekgarg/web/vc-signals/docs/radar-runs/marathon-weekly-v3/weekly-preview.md)

Manually check and record in final notes:

- Partner Review row count.
- Whether Market Sector differs from Source Lane for OSS rows.
- Whether every priority sector appears in Sector Intelligence.
- Whether non-company signal appears as hunt prompts instead of fake company rows.
- Whether the artifact clearly explains OSS-heavy runs.
- Three rows that look useful to Marathon.
- Three rows that look questionable/noisy and why.

- [ ] **Step 3: Update README**

Update README sections:

- `What You Get`
- `Weekly Partner Artifact`
- `Known Limitations`
- `What's New`
- `Roadmap`

Add plain-language explanation:

```markdown
Market Sector is the investment category, such as Cybersecurity or AI Infra.
Source Lane is where the evidence came from, such as OSS, Reddit, HN, Grounded Web, or TikTok.
An OSS repo can therefore be Market Sector = Cybersecurity and Source Lane = OSS.
```

Add social/video caveat:

```markdown
YouTube, TikTok, Instagram, and Threads are supporting source lanes through ScrapeCreators/last30days. They can create a candidate only when the company/product identity is clear and corroborated by a founder/company account, demo, website, waitlist, or another source.
```

- [ ] **Step 4: Run Checkpoint G if time allows**

If the user wants live verification or if captured evidence is stale, run Checkpoint G. Record runtime.

- [ ] **Step 5: Run Checkpoint H**

Run all commands in Checkpoint H. Fix failures before proceeding.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/radar-runs/marathon-weekly-v3 .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Update docs and sample artifact for radar v3"
```

---

## Final Review Checklist

Before final response, run:

```bash
git status --short --branch
git log --oneline -5
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Confirm:

- Branch is not dirty except for intentional uncommitted changes, if any.
- All task commits exist.
- Full tests pass.
- Final artifact has `Market Sector`, `Source Lane`, `Sector Intelligence`, and `Themes With No Company Yet`.
- Secret scan passed.
- README is honest about remaining limitations.

Final response should include:

- What changed.
- Which product gaps are now addressed.
- Test results.
- Artifact path.
- Any residual concerns, especially runtime or source-key limitations.
