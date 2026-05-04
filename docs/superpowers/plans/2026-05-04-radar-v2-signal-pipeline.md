# Radar V2 Signal Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Marathon-ready weekly radar that casts a wide net, ranks up to 50 qualified companies/projects without filler, shows the top 10-15 first, and explicitly explains sector gaps instead of silently returning OSS-only output.

**Architecture:** Split the radar into a signal pipeline: collect source-specific evidence, normalize it into `Signal` objects, promote only eligible signals into `Candidate` rows, enrich candidates with Attio/LinkedIn/X/founder fields when available, score into tiers, and render a partner brief with sector gap notes. Reddit/HN/YouTube/social should usually create evidence and themes; grounded web, HN launches, GitHub repos, Attio seeds, and user seeds can create candidates.

**Tech Stack:** Python 3.12+, pytest, existing `.claude/skills/vc-signals/scripts/radar_run.py`, `last30days_adapter.py`, `attio.py`, JSON/Markdown artifacts.

---

## Target End State

The Marathon weekly command:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly \
  --sectors all \
  --output-dir docs/radar-runs/<run-id> \
  --max-queries-per-sector 3 \
  --github-limit 80 \
  --limit 50
```

must produce:

- `raw-evidence.json`: raw source evidence and warnings.
- `signals.json`: normalized signals by source role.
- `candidates.json`: scored candidates, including filtered/rejected reasons.
- `weekly-preview.md`: partner-readable artifact.

The preview must show:

1. **Partner Review:** top 10-15 candidates.
2. **Full Radar:** up to 50 qualified candidates/projects when available, with no padding or filler rows.
3. **Sector Coverage:** every requested sector, including "No qualified candidates" notes with reasons.
4. **Weak Evidence / Rejected Summary:** counts and examples by reason, including "Needs More Evidence" rows in both Markdown and `candidates.json`.
5. **Columns:** Company/Project, Sector, Theme, Tier, Investment Interest, Evidence Confidence, Attio, Action, LinkedIn, Founders, X, Why On Radar, Why This May Be Noise, Best Source.

---

## Files And Responsibilities

- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
  - Keep CLI orchestration and rendering.
  - Import/use new model and scoring helpers.
  - Stop treating every evidence title as a candidate.

- Create: `.claude/skills/vc-signals/scripts/radar_models.py`
  - Dataclasses for `Signal`, `Candidate`, `Score`, `SectorCoverage`, `RejectedSignal`.
  - Serialization helpers.

- Create: `.claude/skills/vc-signals/scripts/radar_sources.py`
  - Source role policy: Reddit pain, HN launch/discussion, GitHub OSS, YouTube demo, social vertical AI, grounded company, Attio seed.
  - Candidate-creation eligibility rules.

- Create: `.claude/skills/vc-signals/scripts/radar_scoring.py`
  - Investment Interest score.
  - Evidence Confidence score.
  - Tier assignment.
  - Rejection reasons.

- Create: `.claude/skills/vc-signals/scripts/radar_render.py`
  - Markdown renderer for Partner Review, Full Radar, Sector Coverage, and rejected summary.

- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`
  - Keep CLI and integration tests.

- Create: `.claude/skills/vc-signals/tests/test_radar_models.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_sources.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_scoring.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_render.py`

- Modify: `README.md`
  - Document expected weekly command and output sections.

- Modify: `.claude/skills/vc-signals/SKILL.md`
  - Update partner output contract and source-role rules.

---

## Task 1: Add Typed Radar Models

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_models.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_models.py`

- [ ] **Step 1: Write failing model serialization tests**

```python
def test_signal_roundtrip_dict():
    from radar_models import Signal

    signal = Signal(
        source="reddit",
        role="pain",
        title="Teams hate debugging flaky AI agents",
        url="https://reddit.com/r/devops/example",
        sector="devtools",
        theme="Agent reliability",
        text="Repeated complaints about flaky agent runs.",
        can_create_candidate=False,
        evidence_strength=35,
        reason="Reddit pain evidence should support themes, not directly create rows.",
    )

    assert Signal.from_dict(signal.to_dict()) == signal


def test_candidate_serializes_profile_fields():
    from radar_models import Candidate

    candidate = Candidate(
        name="AgentShield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        company_linkedin="",
        company_x="",
        founder_profiles=[{"name": "affaan-m", "github": "https://github.com/affaan-m"}],
    )

    payload = candidate.to_dict()
    assert payload["name"] == "AgentShield"
    assert payload["founder_profiles"][0]["github"] == "https://github.com/affaan-m"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py -q
```

Expected: import error for `radar_models`.

- [ ] **Step 3: Implement models**

Create `.claude/skills/vc-signals/scripts/radar_models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Signal:
    source: str
    role: str
    title: str
    url: str = ""
    sector: str = ""
    theme: str = ""
    text: str = ""
    can_create_candidate: bool = False
    evidence_strength: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Signal":
        return cls(**payload)


@dataclass
class Candidate:
    name: str
    sector: str
    theme: str
    source: str
    candidate_type: str
    domain: str = ""
    why_on_radar: str = ""
    why_this_may_be_noise: str = ""
    sources: list[str] = field(default_factory=list)
    source_count: int = 1
    company_linkedin: str = ""
    company_x: str = ""
    founder_profiles: list[dict] = field(default_factory=list)
    attio_status: str = "unknown"
    action: str = "watch"
    investment_interest_score: int = 0
    evidence_confidence_score: int = 0
    investment_interest: str = ""
    evidence_confidence: str = ""
    tier: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Candidate":
        return cls(**payload)


@dataclass
class RejectedSignal:
    sector: str
    source: str
    title: str
    reason: str
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SectorCoverage:
    sector: str
    raw_signals: int = 0
    candidates: int = 0
    rejected: int = 0
    status: str = "no qualified candidates"
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/tests/test_radar_models.py
git commit -m "Add radar signal data models"
```

---

## Task 2: Encode Source Roles And Candidate Eligibility

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_sources.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_sources.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`

- [ ] **Step 1: Write failing source-role tests**

```python
def test_reddit_pain_signal_cannot_create_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="data-infra",
        item={
            "source": "reddit",
            "title": "What are people using for data lineage now?",
            "url": "https://reddit.com/r/dataengineering/example",
            "snippet": "Comments mention broken pipelines and lineage pain.",
        },
    )

    assert signal.role == "pain"
    assert signal.can_create_candidate is False
    assert "support themes" in signal.reason


def test_hn_show_can_create_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="cybersecurity",
        item={
            "source": "hackernews",
            "title": "Show HN: BeeSafe AI stops voice phishing for banks",
            "url": "https://news.ycombinator.com/item?id=1",
        },
    )

    assert signal.role == "launch"
    assert signal.can_create_candidate is True


def test_github_issue_cannot_create_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="oss",
        item={
            "source": "github",
            "title": "Add MCP server",
            "url": "https://github.com/org/repo/issues/1",
        },
    )

    assert signal.role == "activity"
    assert signal.can_create_candidate is False
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_sources.py -q
```

Expected: import error.

- [ ] **Step 3: Implement role classifier**

Create `.claude/skills/vc-signals/scripts/radar_sources.py`:

```python
from __future__ import annotations

from radar_models import Signal


def classify_source_item(*, sector: str, item: dict) -> Signal:
    source = (item.get("source") or "").lower()
    title = item.get("title", "")
    url = item.get("url", "")
    text = item.get("snippet", "")

    if source == "reddit":
        return Signal(
            source=source,
            role="pain",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=False,
            evidence_strength=30,
            reason="Reddit pain should support themes/candidates, not directly create company rows.",
        )

    if source == "hackernews" and title.lower().startswith(("show hn:", "launch hn:")):
        return Signal(
            source=source,
            role="launch",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=True,
            evidence_strength=45,
            reason="HN launch posts can create candidates when the product name is clear.",
        )

    if source == "github" and ("/issues/" in url or "/pull/" in url):
        return Signal(
            source=source,
            role="activity",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=False,
            evidence_strength=20,
            reason="GitHub issues and PRs are activity evidence, not company/project candidates.",
        )

    if source == "github":
        return Signal(
            source=source,
            role="oss_project",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=True,
            evidence_strength=45,
            reason="GitHub repo results can create OSS project candidates.",
        )

    if source in {"youtube", "tiktok", "instagram", "threads"}:
        return Signal(
            source=source,
            role="social_demo",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=False,
            evidence_strength=25,
            reason="Social/video evidence supports demos or demand, but should not alone create company rows.",
        )

    if source in {"grounding", "web"}:
        return Signal(
            source=source,
            role="company_web",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=True,
            evidence_strength=55,
            reason="Grounded web/company pages can create company candidates.",
        )

    return Signal(source=source, role="unknown", title=title, url=url, sector=sector, text=text)
```

- [ ] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_sources.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_sources.py .claude/skills/vc-signals/tests/test_radar_sources.py
git commit -m "Add radar source role policy"
```

---

## Task 2A: Add Curated Reddit Pain Discovery

**Files:**
- Modify: `.claude/skills/vc-signals/config/sectors.json`
- Create: `.claude/skills/vc-signals/config/reddit_sources.json`
- Create: `.claude/skills/vc-signals/tests/test_reddit_sources.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`

**Research basis:** See `docs/2026-05-04-curated-reddit-sources.md`. Reddit should be used as an early practitioner-pain source for devtools, cybersecurity, AI infra, vertical AI, data infra, and OSS. The source role remains evidence-first: Reddit can create themes, pain signals, and "Needs More Evidence" rows, but not standalone investable company rows.

- [ ] **Step 1: Write failing curated subreddit tests**

```python
def test_reddit_sources_include_curated_pain_subreddits():
    import json
    from pathlib import Path

    path = Path(".claude/skills/vc-signals/config/reddit_sources.json")
    config = json.loads(path.read_text())

    assert "devtools" in config
    assert "platformengineering" in config["devtools"]["primary"]
    assert "cybersecurity" in config
    assert "blueteamsec" in config["cybersecurity"]["primary"]
    assert "data-infra" in config
    assert "dataengineering" in config["data-infra"]["primary"]


def test_curated_reddit_pain_queries_do_not_create_company_rows():
    from radar_run import build_sector_collection_queries

    config = {
        "devtools": {
            "display_name": "Developer Tools",
            "discovery_queries": ["developer tooling pain"],
            "reddit_pain_queries": ["platform engineering pain points"],
        }
    }

    queries = build_sector_collection_queries("devtools", config, grounded_available=False, social_available=False, max_queries=3)

    reddit_queries = [query for query in queries if query.get("kind") == "reddit_pain"]
    assert reddit_queries
    assert all(query["sources"] == "reddit" for query in reddit_queries)
    assert all(query.get("candidate_eligible") is False for query in reddit_queries)
```

- [ ] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_reddit_sources.py .claude/skills/vc-signals/tests/test_radar_run.py::test_curated_reddit_pain_queries_do_not_create_company_rows -q
```

Expected: missing config or missing query metadata.

- [ ] **Step 3: Implement curated Reddit config**

Create `.claude/skills/vc-signals/config/reddit_sources.json` with sector-level tiers:

```json
{
  "devtools": {
    "primary": ["devops", "sre", "platformengineering", "ExperiencedDevs", "programming"],
    "secondary": ["kubernetes", "terraform", "cicd", "softwareengineering", "webdev", "selfhosted"],
    "pain_queries": ["developer productivity pain", "CI/CD frustration", "platform engineering bottleneck", "observability debugging pain", "AI coding workflow failure"]
  },
  "cybersecurity": {
    "primary": ["netsec", "cybersecurity", "blueteamsec", "AskNetsec", "AppSec"],
    "secondary": ["devsecops", "cloudsecurity", "ReverseEngineering", "Malware", "osint", "privacytoolsIO"],
    "pain_queries": ["security operations pain", "application security backlog", "cloud security false positives", "AI security prompt injection", "SOC alert fatigue"]
  },
  "ai-infra": {
    "primary": ["LocalLLaMA", "MachineLearning", "mlops", "LangChain", "LLMDevs"],
    "secondary": ["OpenAI", "ChatGPTCoding", "artificial", "datascience", "DataEngineering"],
    "pain_queries": ["LLMOps pain", "LLM inference cost", "agent evaluation failure", "RAG quality problem", "model deployment monitoring"]
  },
  "vertical-ai": {
    "primary": ["SaaS", "startups", "sales", "CustomerSuccess", "healthIT", "legaltech", "Accounting"],
    "secondary": ["smallbusiness", "Entrepreneur", "edtech", "recruiting", "HumanResources", "insurance"],
    "pain_queries": ["manual workflow pain", "AI agent for operations", "AI SDR frustration", "healthcare admin automation", "legal document automation"]
  },
  "data-infra": {
    "primary": ["dataengineering", "analyticsengineering", "dbt", "snowflake", "databricks"],
    "secondary": ["Database", "bigdata", "SQL", "dataops", "ETL", "aws", "cloudcomputing"],
    "pain_queries": ["data pipeline testing pain", "data lineage pain", "data quality incident", "warehouse cost pain", "Airflow orchestration frustration"]
  },
  "oss": {
    "primary": ["opensource", "github", "selfhosted", "programming", "LocalLLaMA"],
    "secondary": ["MachineLearning", "mcp", "ClaudeCode", "dataengineering", "cybersecurity", "devops"],
    "pain_queries": ["open source tool adoption", "GitHub repo production use", "maintainer burnout", "open source alternative", "MCP open source"]
  }
}
```

- [ ] **Step 4: Add Reddit pain query lane**

`build_sector_collection_queries` should add one `kind="reddit_pain"` query per sector when curated Reddit sources exist. Pass curated subreddits to `last30days_adapter.py` via the existing `subreddits` argument. Keep `candidate_eligible=False` on these query descriptors so downstream code cannot accidentally treat Reddit discussion titles as company rows.

- [ ] **Step 5: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_reddit_sources.py .claude/skills/vc-signals/tests/test_radar_run.py::test_curated_reddit_pain_queries_do_not_create_company_rows -q
```

Expected: tests pass.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/config/reddit_sources.json .claude/skills/vc-signals/config/sectors.json .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_reddit_sources.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Add curated Reddit pain discovery"
```

---

## Task 3: Normalize Raw Evidence Into Signals

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Write failing signal normalization test**

Add to `test_radar_run.py`:

```python
def test_build_signals_from_evidence_preserves_sector_coverage():
    from radar_run import build_signals_from_evidence

    evidence = {
        "last30days": {
            "data-infra": {
                "items": [
                    {
                        "source": "reddit",
                        "title": "What are people using for data lineage now?",
                        "url": "https://reddit.com/r/dataengineering/example",
                    }
                ]
            },
            "oss": {
                "items": [
                    {
                        "source": "hackernews",
                        "title": "Show HN: MenteDB, an open-source memory database for AI agents",
                        "url": "https://news.ycombinator.com/item?id=2",
                    }
                ]
            },
        },
        "github": [],
    }

    result = build_signals_from_evidence(evidence)
    assert len(result["signals"]) == 2
    assert result["coverage"]["data-infra"].raw_signals == 1
    assert result["coverage"]["oss"].raw_signals == 1
```

- [ ] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_build_signals_from_evidence_preserves_sector_coverage -q
```

Expected: `build_signals_from_evidence` missing.

- [ ] **Step 3: Implement normalization**

Add to `radar_run.py`:

```python
from radar_models import SectorCoverage
from radar_sources import classify_source_item


def build_signals_from_evidence(evidence: dict) -> dict:
    signals = []
    coverage = {}

    for sector, payload in evidence.get("last30days", {}).items():
        sector_signals = []
        for item in filter_evidence(payload.get("items", [])):
            signal = classify_source_item(sector=sector, item=item)
            signals.append(signal)
            sector_signals.append(signal)
        coverage[sector] = SectorCoverage(
            sector=sector,
            raw_signals=len(sector_signals),
            reason="No candidate-eligible signals yet." if not any(s.can_create_candidate for s in sector_signals) else "",
        )

    return {"signals": signals, "coverage": coverage}
```

- [ ] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_build_signals_from_evidence_preserves_sector_coverage -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Normalize radar evidence into source signals"
```

---

## Task 4: Candidate Promotion Rules

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Write failing promotion tests**

```python
def test_candidate_promotion_ignores_reddit_only_signal():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signals = [
        classify_source_item(
            sector="data-infra",
            item={"source": "reddit", "title": "What data quality tools are people using?", "url": "https://reddit.com/x"},
        )
    ]

    result = promote_signals_to_candidates(signals)
    assert result["candidates"] == []
    assert result["rejected"][0].reason == "source_not_candidate_eligible"


def test_candidate_promotion_allows_hn_launch():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signals = [
        classify_source_item(
            sector="cybersecurity",
            item={"source": "hackernews", "title": "Show HN: BeeSafe AI stops voice phishing for banks", "url": "https://news.ycombinator.com/item?id=1"},
        )
    ]

    result = promote_signals_to_candidates(signals)
    assert result["candidates"][0].name == "BeeSafe AI"
```

- [ ] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_candidate_promotion_ignores_reddit_only_signal .claude/skills/vc-signals/tests/test_radar_run.py::test_candidate_promotion_allows_hn_launch -q
```

Expected: missing function.

- [ ] **Step 3: Implement promotion**

Add to `radar_run.py`:

```python
from radar_models import Candidate, RejectedSignal


def promote_signals_to_candidates(signals: list) -> dict:
    candidates = []
    rejected = []

    for signal in signals:
        if not signal.can_create_candidate:
            rejected.append(RejectedSignal(
                sector=signal.sector,
                source=signal.source,
                title=signal.title,
                url=signal.url,
                reason="source_not_candidate_eligible",
            ))
            continue
        name = _extract_name_from_title(signal.title)
        if not name:
            rejected.append(RejectedSignal(
                sector=signal.sector,
                source=signal.source,
                title=signal.title,
                url=signal.url,
                reason="candidate_name_not_extractable",
            ))
            continue
        candidates.append(Candidate(
            name=name,
            sector=SECTOR_LABELS.get(signal.sector, signal.sector),
            theme=infer_theme(signal.title + " " + signal.text),
            source=signal.url,
            candidate_type=signal.role,
            why_on_radar=signal.title,
            why_this_may_be_noise="Needs verification across stronger company/founder/customer evidence.",
            sources=[signal.url] if signal.url else [],
        ))

    return {"candidates": candidates, "rejected": rejected}
```

- [ ] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_candidate_promotion_ignores_reddit_only_signal .claude/skills/vc-signals/tests/test_radar_run.py::test_candidate_promotion_allows_hn_launch -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Promote only eligible radar signals"
```

---

## Task 5: Scoring And Tiers For Up-To-50 Candidate Radar

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_scoring.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_scoring.py`

- [ ] **Step 1: Write failing scoring tests**

```python
def test_high_interest_low_confidence_becomes_watchlist_not_filtered():
    from radar_models import Candidate
    from radar_scoring import score_and_tier

    candidate = Candidate(
        name="AgentShield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        why_on_radar="AI agent security scanner for MCP servers. +184 stars in 30d.",
        source_count=1,
    )

    scored = score_and_tier(candidate)
    assert scored.investment_interest_score >= 45
    assert scored.tier in {"Watchlist", "Needs More Evidence"}


def test_partner_review_requires_interest_and_evidence():
    from radar_models import Candidate
    from radar_scoring import score_and_tier

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://runcandidate.example",
        candidate_type="company_web",
        domain="beesafe.ai",
        why_on_radar="Company page, HN launch, and GitHub repo all point to voice phishing defense for banks.",
        source_count=3,
        company_linkedin="https://www.linkedin.com/company/beesafe-ai",
    )

    scored = score_and_tier(candidate)
    assert scored.evidence_confidence_score >= 45
    assert scored.tier in {"Partner Review", "Watchlist"}


def test_needs_more_evidence_is_preserved_for_markdown_and_json():
    from radar_models import Candidate
    from radar_scoring import score_and_tier

    candidate = Candidate(
        name="LineageWatch",
        sector="Data Infrastructure",
        theme="Data lineage",
        source="https://reddit.com/r/dataengineering/example",
        candidate_type="theme_probe",
        why_on_radar="Repeated Reddit pain around lineage and schema drift, but no verified company yet.",
        source_count=1,
    )

    scored = score_and_tier(candidate)
    assert scored.tier == "Needs More Evidence"
    assert scored.evidence_confidence in {"Low", "Needs More Evidence"}
```

- [ ] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_scoring.py -q
```

Expected: import error.

- [ ] **Step 3: Implement scoring**

Create `.claude/skills/vc-signals/scripts/radar_scoring.py`:

```python
from __future__ import annotations

from radar_models import Candidate


INTEREST_TERMS = ("agent", "security", "mcp", "workflow", "enterprise", "bank", "developer", "infrastructure", "open source")
CONSENSUS_TERMS = ("series c", "series d", "$200m", "$1b", "consensus", "too late")


def label(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def score_and_tier(candidate: Candidate) -> Candidate:
    text = " ".join([
        candidate.name,
        candidate.sector,
        candidate.theme,
        candidate.why_on_radar,
        candidate.why_this_may_be_noise,
    ]).lower()

    interest = 30
    evidence = 20

    interest += min(35, sum(5 for term in INTEREST_TERMS if term in text))
    evidence += min(30, candidate.source_count * 10)

    if candidate.domain:
        evidence += 10
    if candidate.company_linkedin:
        evidence += 10
    if candidate.founder_profiles:
        evidence += 5
    if candidate.candidate_type == "oss_project":
        interest += 10
    if any(term in text for term in CONSENSUS_TERMS):
        interest -= 20

    interest = max(0, min(100, interest))
    evidence = max(0, min(100, evidence))

    candidate.investment_interest_score = interest
    candidate.evidence_confidence_score = evidence
    candidate.investment_interest = label(interest)
    candidate.evidence_confidence = label(evidence)

    if interest >= 70 and evidence >= 45:
        candidate.tier = "Partner Review"
    elif interest >= 45:
        candidate.tier = "Watchlist"
    elif interest >= 35:
        candidate.tier = "Needs More Evidence"
    else:
        candidate.tier = "Filtered"

    return candidate
```

- [ ] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_scoring.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_scoring.py .claude/skills/vc-signals/tests/test_radar_scoring.py
git commit -m "Add radar scoring tiers"
```

---

## Task 6: Render Partner Review, Full Radar, Sector Gaps, And Rejections

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_render.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_render.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`

- [ ] **Step 1: Write failing render test**

```python
def test_render_weekly_brief_includes_sector_gap_and_full_radar(tmp_path):
    from radar_models import Candidate, RejectedSignal, SectorCoverage
    from radar_render import render_weekly_brief

    candidates = [
        Candidate(
            name="AgentShield",
            sector="OSS",
            theme="AI agent security",
            source="https://github.com/affaan-m/agentshield",
            candidate_type="oss_project",
            tier="Watchlist",
            investment_interest="Medium",
            evidence_confidence="Low",
            attio_status="no_match",
            action="watch",
            why_on_radar="+184 stars in 30d.",
            why_this_may_be_noise="Repo traction may not map to company formation.",
        )
    ]
    coverage = {
        "data-infra": SectorCoverage(
            sector="data-infra",
            raw_signals=3,
            candidates=0,
            rejected=3,
            status="no qualified candidates",
            reason="Only Reddit pain and GitHub issue noise; no company/domain/founder evidence.",
        )
    }
    rejected = [RejectedSignal(sector="data-infra", source="reddit", title="What are people using?", reason="source_not_candidate_eligible")]

    markdown = render_weekly_brief(candidates, coverage, rejected)
    assert "## Partner Review" in markdown
    assert "## Full Radar" in markdown
    assert "## Sector Coverage" in markdown
    assert "data-infra: no qualified candidates" in markdown
    assert "Only Reddit pain and GitHub issue noise" in markdown
```

- [ ] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_render.py -q
```

Expected: import error.

- [ ] **Step 3: Implement renderer**

Create `.claude/skills/vc-signals/scripts/radar_render.py`:

```python
from __future__ import annotations


def render_weekly_brief(candidates: list, coverage: dict, rejected: list) -> str:
    partner = [c for c in candidates if c.tier == "Partner Review"][:15]
    if not partner:
        partner = [c for c in candidates if c.tier == "Watchlist"][:15]

    lines = [
        "# VC Signals Weekly Radar",
        "",
        "## Partner Review",
        "",
        _table(partner),
        "",
        "## Full Radar",
        "",
        _table(candidates[:50]),
        "",
        "## Sector Coverage",
        "",
    ]

    for sector, item in coverage.items():
        lines.append(f"- **{sector}: {item.status}** - {item.reason or 'Qualified candidates found.'}")

    lines.extend(["", "## Weak Evidence / Rejected Summary", ""])
    reason_counts = {}
    for item in rejected:
        reason_counts[item.reason] = reason_counts.get(item.reason, 0) + 1
    for reason, count in sorted(reason_counts.items()):
        lines.append(f"- {reason}: {count}")

    return "\n".join(lines).rstrip() + "\n"


def _table(candidates: list) -> str:
    rows = [
        "| Company / Project | Sector | Theme | Tier | Interest | Evidence | Attio | Action | LinkedIn | Founders | X | Why On Radar | Why This May Be Noise | Best Source |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in candidates:
        rows.append(
            f"| {c.name} | {c.sector} | {c.theme} | {c.tier} | {c.investment_interest} | {c.evidence_confidence} | "
            f"{c.attio_status} | {c.action} | {c.company_linkedin} | {_founders(c.founder_profiles)} | {c.company_x} | "
            f"{c.why_on_radar} | {c.why_this_may_be_noise} | {c.source} |"
        )
    return "\n".join(rows)


def _founders(founders: list[dict]) -> str:
    out = []
    for founder in founders:
        name = founder.get("name") or "Founder"
        links = [founder.get("linkedin"), founder.get("x"), founder.get("github")]
        links = [link for link in links if link]
        out.append(f"{name}: {', '.join(links)}" if links else name)
    return "; ".join(out)
```

- [ ] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_render.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_render.py .claude/skills/vc-signals/tests/test_radar_render.py
git commit -m "Render weekly radar with sector coverage"
```

---

## Task 7: Save Signals/Candidates Artifacts And Use New Renderer

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Write failing weekly artifact test**

```python
def test_run_weekly_artifacts_saves_signals_candidates_and_sector_coverage(tmp_path, monkeypatch):
    import radar_run

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "data-infra": {
                    "items": [
                        {"source": "reddit", "title": "What lineage tools are people using?", "url": "https://reddit.com/x"}
                    ]
                },
                "oss": {
                    "items": [
                        {"source": "hackernews", "title": "Show HN: MenteDB, memory database for AI agents", "url": "https://news.ycombinator.com/item?id=1"}
                    ]
                },
            },
            "github": [],
            "warnings": [],
        },
    )

    result = radar_run.run_weekly_artifacts(output_dir=tmp_path, sectors=("data-infra", "oss"), github_limit=0)
    assert (tmp_path / "signals.json").exists()
    assert (tmp_path / "candidates.json").exists()
    assert "Sector Coverage" in (tmp_path / "weekly-preview.md").read_text()
    assert "data-infra: no qualified candidates" in (tmp_path / "weekly-preview.md").read_text()
```

- [ ] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_saves_signals_candidates_and_sector_coverage -q
```

Expected: missing `signals.json` or missing sector coverage.

- [ ] **Step 3: Update weekly orchestration**

In `run_weekly_artifacts`, replace the current direct extraction path with:

```python
signal_result = build_signals_from_evidence(evidence)
promotion = promote_signals_to_candidates(signal_result["signals"])
scored = [score_and_tier(candidate) for candidate in promotion["candidates"]]
scored = merge_attio_context([candidate.to_dict() for candidate in scored], _attio_client_from_env())
scored_candidates = [Candidate.from_dict(candidate) for candidate in scored]

for sector, coverage in signal_result["coverage"].items():
    sector_candidates = [c for c in scored_candidates if c.sector.lower().replace(" ", "-") == sector]
    coverage.candidates = len(sector_candidates)
    sector_rejections = [r for r in promotion["rejected"] if r.sector == sector]
    coverage.rejected = len(sector_rejections)
    if sector_candidates:
        coverage.status = "qualified candidates found"
        coverage.reason = ""
    elif coverage.raw_signals:
        coverage.status = "no qualified candidates"
        coverage.reason = "Signals found, but none met candidate eligibility or evidence quality."
    else:
        coverage.status = "no signal found"
        coverage.reason = "No relevant source evidence returned for this sector."

(output_dir / "signals.json").write_text(json.dumps([s.to_dict() for s in signal_result["signals"]], indent=2))
(output_dir / "candidates.json").write_text(json.dumps([c.to_dict() for c in scored_candidates], indent=2))
render_weekly_brief(scored_candidates, signal_result["coverage"], promotion["rejected"])
```

- [ ] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_run_weekly_artifacts_saves_signals_candidates_and_sector_coverage -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Save weekly radar signal artifacts"
```

---

## Task 8: Full Radar Breadth And Limits

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Test: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [ ] **Step 1: Write failing breadth test**

```python
def test_weekly_radar_keeps_up_to_50_not_just_top_15(tmp_path, monkeypatch):
    import radar_run
    from radar_models import Candidate

    candidates = [
        Candidate(
            name=f"Company {i}",
            sector="AI Infra",
            theme="Agent runtime",
            source=f"https://example.com/{i}",
            candidate_type="company_web",
            tier="Watchlist",
            investment_interest="Medium",
            evidence_confidence="Medium",
            investment_interest_score=60 - (i % 10),
            evidence_confidence_score=50,
        )
        for i in range(60)
    ]

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "build_signals_from_evidence", lambda evidence: {"signals": [], "coverage": {}})
    monkeypatch.setattr(radar_run, "promote_signals_to_candidates", lambda signals: {"candidates": candidates, "rejected": []})

    result = radar_run.run_weekly_artifacts(output_dir=tmp_path, candidate_limit=50)
    import json
    saved = json.loads((tmp_path / "candidates.json").read_text())
    assert len(saved) == 50


def test_weekly_radar_does_not_pad_to_50(tmp_path, monkeypatch):
    import json
    import radar_run
    from radar_models import Candidate

    candidates = [
        Candidate(
            name=f"Company {i}",
            sector="AI Infra",
            theme="Agent runtime",
            source=f"https://example.com/{i}",
            candidate_type="company_web",
            tier="Watchlist",
            investment_interest="Medium",
            evidence_confidence="Medium",
            investment_interest_score=50,
            evidence_confidence_score=50,
        )
        for i in range(7)
    ]

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "build_signals_from_evidence", lambda evidence: {"signals": [], "coverage": {}})
    monkeypatch.setattr(radar_run, "promote_signals_to_candidates", lambda signals: {"candidates": candidates, "rejected": []})

    radar_run.run_weekly_artifacts(output_dir=tmp_path, candidate_limit=50)
    saved = json.loads((tmp_path / "candidates.json").read_text())
    assert len(saved) == 7
```

- [ ] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_weekly_radar_keeps_up_to_50_not_just_top_15 .claude/skills/vc-signals/tests/test_radar_run.py::test_weekly_radar_does_not_pad_to_50 -q
```

Expected: current code only saves/renders too few, does not use candidate_limit, or pads instead of preserving only qualified rows.

- [ ] **Step 3: Implement ranking limit**

In `run_weekly_artifacts`, after scoring:

```python
scored_candidates = sorted(
    scored_candidates,
    key=lambda c: (c.tier == "Partner Review", c.investment_interest_score, c.evidence_confidence_score),
    reverse=True,
)[:candidate_limit]
```

- [ ] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_weekly_radar_keeps_up_to_50_not_just_top_15 .claude/skills/vc-signals/tests/test_radar_run.py::test_weekly_radar_does_not_pad_to_50 -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py
git commit -m "Keep full radar candidate breadth"
```

---

## Task 9: Partner-Style Live Verification

**Files:**
- Generated only: `docs/radar-runs/marathon-weekly-v2/`

- [ ] **Step 1: Run the partner command**

```bash
rm -rf docs/radar-runs/marathon-weekly-v2
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly \
  --sectors all \
  --output-dir docs/radar-runs/marathon-weekly-v2 \
  --max-queries-per-sector 2 \
  --github-limit 80 \
  --limit 50
```

Expected stdout:

```json
{
  "raw_evidence": "docs/radar-runs/marathon-weekly-v2/<date>-raw-evidence.json",
  "signals": "docs/radar-runs/marathon-weekly-v2/signals.json",
  "candidates": "docs/radar-runs/marathon-weekly-v2/candidates.json",
  "preview": "docs/radar-runs/marathon-weekly-v2/weekly-preview.md",
  "companies": <number>,
  "sectors": ["devtools", "cybersecurity", "ai-infra", "vertical-ai", "data-infra", "oss"]
}
```

- [ ] **Step 2: Verify artifact presence**

```bash
test -f docs/radar-runs/marathon-weekly-v2/weekly-preview.md
test -f docs/radar-runs/marathon-weekly-v2/signals.json
test -f docs/radar-runs/marathon-weekly-v2/candidates.json
```

Expected: exit code `0`.

- [ ] **Step 3: Verify output sections**

```bash
rg -n "## Partner Review|## Full Radar|## Sector Coverage|## Weak Evidence" docs/radar-runs/marathon-weekly-v2/weekly-preview.md
```

Expected: all four headings present.

- [ ] **Step 4: Verify all sectors are mentioned**

```bash
rg -n "devtools|cybersecurity|ai-infra|vertical-ai|data-infra|oss" docs/radar-runs/marathon-weekly-v2/weekly-preview.md
```

Expected: all requested sectors appear, either with candidates or no-qualified-candidates notes.

- [ ] **Step 5: Verify tests and secret scan**

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
rg -n "ATTIO_ACCESS_TOKEN='|Bearer [A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-or-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|fwKR[A-Za-z0-9_-]{10,}" . --glob '!vendor/**' --glob '!.git/**' --glob '!docs/superpowers/plans/**'
```

Expected:

- pytest passes.
- `rg` exits `1` with no output.

- [ ] **Step 6: Commit code and intentional generated demo artifacts**

```bash
git status --short
```

Generated Marathon demo artifacts should be committed when intentionally created for review. Do not commit transient scratch runs, secrets, or `.env` files.

---

## Task 10: Docs And User Instructions

**Files:**
- Modify: `README.md`
- Modify: `.claude/skills/vc-signals/SKILL.md`
- Modify: `docs/product-context.md`

- [ ] **Step 1: Add README output contract**

Add this section to `README.md`:

```markdown
### Weekly Partner Artifact

The local partner command is:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/current --limit 50
```

The artifact contains:

- Partner Review: top 10-15 ranked candidates.
- Full Radar: up to 50 qualified companies/projects, with no filler rows.
- Sector Coverage: every requested sector, including no-qualified-candidates reasons.
- Weak Evidence Summary: what was filtered out and why, plus "Needs More Evidence" items when there is useful pain/theme signal without enough company verification.

Reddit is used primarily for curated pain discovery across devtools, cybersecurity, AI infra, vertical AI, data infra, and OSS. It rarely creates company rows directly. HN Show/Launch, GitHub repos, grounded web/company pages, Attio seeds, and user-provided companies are candidate-eligible sources.
```
```

- [ ] **Step 2: Add SKILL.md output contract**

Add this to `.claude/skills/vc-signals/SKILL.md` near the deterministic weekly run section:

```markdown
The weekly artifact must not silently omit sectors. If a sector has no qualified candidates, render a sector coverage note explaining whether the cause was no source evidence, source-not-candidate-eligible evidence, weak evidence, or missing grounded web/company enrichment.
```

- [ ] **Step 3: Verify docs mention source roles**

```bash
rg -n "Reddit is used primarily|must not silently omit sectors|Partner Review: top" README.md .claude/skills/vc-signals/SKILL.md
```

Expected: all phrases found.

- [ ] **Step 4: Commit**

```bash
git add README.md .claude/skills/vc-signals/SKILL.md docs/product-context.md
git commit -m "Document weekly radar output contract"
```

---

## Success Criteria

The plan is complete only when all are true:

- `python3 -m pytest .claude/skills/vc-signals/tests -q` passes.
- Weekly command produces raw evidence, signals, candidates, and preview artifacts.
- Preview has Partner Review, Full Radar, Sector Coverage, and Weak Evidence sections.
- Every requested sector appears in the artifact.
- Full Radar can contain up to 50 qualified candidates with no filler; Partner Review is a top slice, not the whole universe.
- "Needs More Evidence" appears in both `weekly-preview.md` and `candidates.json` when a signal is interesting but not yet verified enough for Watchlist or Partner Review.
- Reddit-only evidence does not directly create company rows.
- HN Show/Launch and GitHub repo velocity can create candidates.
- GitHub issues/PRs, Reddit chatter, YouTube/TikTok/Instagram/Threads titles alone become evidence or rejected signals, not rows.
- LinkedIn/X/founder fields are preserved when present and blank when not verified.
- Attio enrichment still works from `~/.config/vc-signals/.env`.
- Secret scan returns no committed secrets.

---

## Resolved Product Decisions

1. Full radar is up to 50 qualified rows, with no padding.
2. "Needs More Evidence" appears in both the Markdown brief and `candidates.json`.
3. Generated demo artifacts should be committed when they are intentionally created for review.
4. Reddit should be a curated pain discovery source across devtools, cybersecurity, AI infra, vertical AI, data infra, and OSS, not only vertical AI.
