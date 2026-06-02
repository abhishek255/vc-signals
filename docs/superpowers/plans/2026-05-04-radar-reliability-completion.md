# Radar Reliability Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Complete the missing reliability layer for VC Signals: week-over-week tags, company enrichment, OSS company-formation judgment, and richer Attio context.

**Architecture:** Keep the current radar-v2 pipeline intact: collect evidence, normalize signals, promote candidates, score, enrich, render. Add three focused modules: `radar_history.py` for weekly candidate/project persistence, `radar_enrichment.py` for funding/headcount/founder fields with evidence, and `radar_oss.py` for OSS-specific scoring. Extend `attio.py` to return richer but still read-only CRM fields.

**Tech Stack:** Python 3.12+, pytest, existing `.claude/skills/vc-signals/scripts/radar_run.py`, `radar_models.py`, `radar_render.py`, `attio.py`, `enrichment.py`, JSON artifacts.

---

## User-Facing Outcome

After this plan, a Marathon partner can run:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/current --limit 50
```

and expect:

- `NEW`, `RETURNING`, `PERSISTENT`, and `FADED` company/project status based on previous weekly runs.
- Funding/stage/headcount/founder fields when evidence-backed, blank when not found.
- OSS rows that distinguish "interesting repo" from "possible company formation."
- Attio rows with status, action, owner/staleness context, and a direct record URL when available.
- Auditability: every enriched field has a source/evidence reason or remains blank.

---

## Files And Responsibilities

- Create: `.claude/skills/vc-signals/scripts/radar_history.py`
  - Stable candidate/project keys.
  - Load/save `candidate_history.json`.
  - Apply weekly tags.
  - Emit faded candidates/projects.

- Create: `.claude/skills/vc-signals/tests/test_radar_history.py`
  - Unit tests for stable keys, tags, faded logic, and history writes.

- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
  - Add optional fields: `stable_key`, `weekly_tag`, `stage`, `raised`, `headcount`, `founders`, `founding_year`, `lead_investor`, `enrichment_evidence`, `attio_record_url`, `attio_owner`, `attio_last_interaction`, `attio_staleness_reason`, `oss_company_formation_score`, `oss_action_reason`, `license`, `repo_age_days`, `stars`, `stars_30d`, `maintainer_profiles`.

- Create: `.claude/skills/vc-signals/scripts/radar_enrichment.py`
  - Merge cache, source metadata, and Attio attributes into candidate objects.
  - Preserve evidence per field.
  - Respect cache TTL.

- Create: `.claude/skills/vc-signals/tests/test_radar_enrichment.py`
  - Unit tests for evidence-backed field merge, stale cache handling, and no hallucinated fields.

- Create: `.claude/skills/vc-signals/scripts/radar_oss.py`
  - OSS-specific enrichment and action scoring.
  - Company-formation score.
  - Maintainer/profile extraction from GitHub metadata.

- Create: `.claude/skills/vc-signals/tests/test_radar_oss.py`
  - Unit tests for action vocabulary, company-formation score, and repo metadata preservation.

- Modify: `.claude/skills/vc-signals/scripts/attio.py`
  - Return `attio_record_url`, `attio_owner`, `attio_last_interaction`, mapped stage/raised/headcount, and staleness reason.
  - Cache list lookup per client instance.

- Modify: `.claude/skills/vc-signals/tests/test_attio.py`
  - Tests for record URL, owner extraction, stale policy, mapped fields, and list cache.

- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
  - Wire history, enrichment, OSS scoring, Attio fields, and candidate artifacts into the weekly run.

- Modify: `.claude/skills/vc-signals/scripts/radar_render.py`
  - Render tag, stage, raised, headcount, founders, Attio URL/owner context, OSS action reason, and faded section.

- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`
  - Integration tests for weekly artifacts.

- Modify: `README.md`
  - Document the completed behavior once implemented.
  - Keep "Current state" honest at each milestone: only mark a capability complete after the corresponding verification checkpoint passes.

---

## Verification Checkpoints

Run these checkpoints exactly. Do not wait until the final task to discover that the user-facing artifact or README drifted.

### Checkpoint A: History Works Before Enrichment

Run after Task 2:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_history.py .claude/skills/vc-signals/tests/test_radar_render.py .claude/skills/vc-signals/tests/test_radar_run.py -q
rm -rf docs/radar-runs/checkpoint-history
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors oss --output-dir docs/radar-runs/checkpoint-history --max-queries-per-sector 1 --github-limit 20 --limit 20
test -f docs/radar-runs/checkpoint-history/weekly-preview.md
test -f .claude/skills/vc-signals/data/companies/candidate_history.json
rg -n "Tag|Faded Off Radar|NEW|RETURNING|PERSISTENT" docs/radar-runs/checkpoint-history/weekly-preview.md .claude/skills/vc-signals/data/companies/candidate_history.json
```

Expected:

- pytest passes.
- The weekly artifact exists.
- `candidate_history.json` exists.
- The preview table has a `Tag` column.
- At least one current candidate has a tag, usually `NEW` on the first run.

README update required after Checkpoint A:

- Update "What's New" to say week-over-week candidate/project tags are implemented.
- Update "Weekly Partner Artifact" to list `Tag` and `Faded Off Radar`.
- Do not mention funding/headcount/founders as complete yet.

### Checkpoint B: Enrichment Fields Are Evidence-Backed

Run after Task 4:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_enrichment.py .claude/skills/vc-signals/tests/test_radar_render.py .claude/skills/vc-signals/tests/test_radar_run.py -q
python3 - <<'PY'
import json
from pathlib import Path
path = Path('.claude/skills/vc-signals/data/companies/enrichment_cache.json')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({
  "beesafe ai": {
    "fetched_at": "2026-05-04",
    "stage": "Seed",
    "raised": "$4M",
    "headcount": "12",
    "founders": ["Asha Rao"],
    "evidence": {
      "stage": "https://beesafe.ai/about",
      "raised": "https://beesafe.ai/blog/seed",
      "headcount": "https://linkedin.com/company/beesafe-ai",
      "founders": "https://beesafe.ai/about"
    }
  }
}, indent=2))
PY
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors cybersecurity --output-dir docs/radar-runs/checkpoint-enrichment --max-queries-per-sector 1 --github-limit 0 --limit 10
test -f docs/radar-runs/checkpoint-enrichment/candidates.json
rg -n "Stage|Raised|Headcount|Founders|Seed|\\$4M" docs/radar-runs/checkpoint-enrichment/weekly-preview.md docs/radar-runs/checkpoint-enrichment/candidates.json
```

Expected:

- pytest passes.
- Enrichment columns render.
- Seed, raised, headcount, and founder values only appear when backed by cache/source evidence.

README update required after Checkpoint B:

- Update "What You Get" to say stage/raised/headcount/founders appear when evidence-backed.
- Add one sentence under "Known Limitations": blank enrichment fields mean no trusted evidence was found.
- Do not imply these fields are guaranteed for every row.

### Checkpoint C: OSS Radar Has Company-Formation Semantics

Run after Task 5:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_oss.py .claude/skills/vc-signals/tests/test_radar_run.py -q
rm -rf docs/radar-runs/checkpoint-oss
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors oss --output-dir docs/radar-runs/checkpoint-oss --max-queries-per-sector 1 --github-limit 30 --limit 30
test -f docs/radar-runs/checkpoint-oss/candidates.json
rg -n "oss_company_formation_score|oss_action_reason|contact maintainer|track company formation|watch" docs/radar-runs/checkpoint-oss/candidates.json docs/radar-runs/checkpoint-oss/weekly-preview.md
```

Expected:

- pytest passes.
- OSS candidates include `oss_company_formation_score`.
- OSS candidates include an `oss_action_reason`.
- Action values are from the approved vocabulary.

README update required after Checkpoint C:

- Move OSS radar from partial to implemented only for: velocity, action vocabulary, company-formation scoring, and maintainer/profile extraction.
- Keep "ecosystem mapping" and "contact enrichment" as next/partial unless they are also implemented.

### Checkpoint D: Attio Context Is Partner-Readable

Run after Task 6:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_attio.py .claude/skills/vc-signals/tests/test_radar_render.py .claude/skills/vc-signals/tests/test_radar_run.py -q
python3 .claude/skills/vc-signals/scripts/attio.py check
rg -n "Attio Owner|Attio URL|attio_record_url|attio_owner|attio_staleness_reason" .claude/skills/vc-signals/scripts .claude/skills/vc-signals/tests
```

Expected:

- pytest passes.
- `attio.py check` reports configured or a clear missing-token error without revealing a token.
- Renderer and candidates model include Attio owner, URL, and staleness fields.

README update required after Checkpoint D:

- Move Attio integration from partial to implemented only for read-only matching, owner/staleness context, record URL, and mapped enrichment fields.
- Keep "CRM writeback", "automatic owner assignment", and "bulk background sync" out of README unless implemented.

### Checkpoint E: End-To-End Partner Workflow

Run after Task 7:

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
rm -rf docs/radar-runs/marathon-weekly-v3
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/marathon-weekly-v3 --max-queries-per-sector 2 --github-limit 80 --limit 50
test -f docs/radar-runs/marathon-weekly-v3/weekly-preview.md
test -f docs/radar-runs/marathon-weekly-v3/signals.json
test -f docs/radar-runs/marathon-weekly-v3/candidates.json
test -f .claude/skills/vc-signals/data/companies/candidate_history.json
rg -n "## Partner Review|## Full Radar|## Sector Coverage|## Weak Evidence|Tag|Stage|Raised|Headcount|Attio" docs/radar-runs/marathon-weekly-v3/weekly-preview.md
python3 - <<'PY'
import json
from pathlib import Path
items = json.loads(Path('docs/radar-runs/marathon-weekly-v3/candidates.json').read_text())
assert len(items) <= 50
assert all('stable_key' in item for item in items)
assert all('weekly_tag' in item for item in items)
assert all('enrichment_evidence' in item for item in items)
print({'candidate_count': len(items), 'tags': sorted(set(item.get('weekly_tag', '') for item in items))})
PY
rg -n "ATTIO_ACCESS_TOKEN='|Bearer [A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-or-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|fwKR[A-Za-z0-9_-]{10,}" . --glob '!vendor/**' --glob '!.git/**' --glob '!docs/superpowers/plans/**'
```

Expected:

- pytest passes.
- Weekly command emits all artifacts.
- Partner preview has all required sections and columns.
- `candidates.json` has no more than 50 rows.
- Every candidate has `stable_key`, `weekly_tag`, and `enrichment_evidence`.
- Secret scan exits `1` with no output.

README update required after Checkpoint E:

- Run `rg -n "partial|next enrichment|not guaranteed|Current state|Roadmap|Known Limitations" README.md`.
- Verify the README no longer says a now-completed feature is future-only.
- Verify the README still does not promise fields that remain evidence-dependent.

---

## Task 1: Add Candidate History And Week-Over-Week Tags

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_history.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_history.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`

- [x] **Step 1: Add candidate history fields to the model**

Add these fields to `Candidate` in `.claude/skills/vc-signals/scripts/radar_models.py`:

```python
    stable_key: str = ""
    weekly_tag: str = ""
```

- [x] **Step 2: Write stable-key tests**

Create `.claude/skills/vc-signals/tests/test_radar_history.py`:

```python
from pathlib import Path


def test_stable_candidate_key_prefers_domain():
    from radar_history import stable_candidate_key
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://news.ycombinator.com/item?id=1",
        candidate_type="launch",
        domain="www.beesafe.ai",
    )

    assert stable_candidate_key(candidate) == "company:beesafe.ai"


def test_stable_candidate_key_uses_repo_for_oss():
    from radar_history import stable_candidate_key
    from radar_models import Candidate

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )

    assert stable_candidate_key(candidate) == "repo:github.com/affaan-m/agentshield"


def test_stable_candidate_key_falls_back_to_name_and_sector():
    from radar_history import stable_candidate_key
    from radar_models import Candidate

    candidate = Candidate(
        name="LineageWatch",
        sector="Data Infra",
        theme="Data lineage",
        source="",
        candidate_type="theme_probe",
    )

    assert stable_candidate_key(candidate) == "candidate:data-infra:lineagewatch"
```

- [x] **Step 3: Run tests and verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_history.py -q
```

Expected: import error for `radar_history`.

- [x] **Step 4: Implement stable keys**

Create `.claude/skills/vc-signals/scripts/radar_history.py`:

```python
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from radar_models import Candidate

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
PERSISTENT_WEEKS = 3
RETURNING_AFTER_MISSED_WEEKS = 2


def _normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.split("/", 1)[0]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def stable_candidate_key(candidate: Candidate) -> str:
    domain = _normalize_domain(candidate.domain)
    if domain:
        return f"company:{domain}"

    parsed = urlparse(candidate.source or "")
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [part for part in parsed.path.split("/") if part]
    if host == "github.com" and len(parts) >= 2:
        return f"repo:{host}/{parts[0]}/{parts[1]}".lower()

    return f"candidate:{_slug(candidate.sector)}:{_slug(candidate.name)}"
```

- [x] **Step 5: Verify stable-key tests pass**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_history.py::test_stable_candidate_key_prefers_domain .claude/skills/vc-signals/tests/test_radar_history.py::test_stable_candidate_key_uses_repo_for_oss .claude/skills/vc-signals/tests/test_radar_history.py::test_stable_candidate_key_falls_back_to_name_and_sector -q
```

Expected: `3 passed`.

- [x] **Step 6: Add tag and faded tests**

Append to `.claude/skills/vc-signals/tests/test_radar_history.py`:

```python
def test_apply_weekly_tags_marks_new_candidate(tmp_path: Path):
    from radar_history import apply_weekly_tags, load_candidate_history
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        domain="beesafe.ai",
    )

    history = load_candidate_history(tmp_path)
    result = apply_weekly_tags([candidate], history, run_date="2026-05-04")

    assert result.candidates[0].weekly_tag == "NEW"
    assert result.candidates[0].stable_key == "company:beesafe.ai"
    assert result.faded == []


def test_apply_weekly_tags_marks_persistent_on_third_seen_week(tmp_path: Path):
    from radar_history import apply_weekly_tags
    from radar_models import Candidate

    history = {
        "company:beesafe.ai": {
            "display_name": "BeeSafe AI",
            "first_seen": "2026-04-20",
            "last_seen": "2026-04-27",
            "weeks_seen": 2,
            "missed_weeks": 0,
            "sectors": ["Cybersecurity"],
            "themes": ["AI fraud defense"],
            "last_source": "https://beesafe.ai",
        }
    }
    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        domain="beesafe.ai",
    )

    result = apply_weekly_tags([candidate], history, run_date="2026-05-04")

    assert result.candidates[0].weekly_tag == "PERSISTENT"
    assert history["company:beesafe.ai"]["weeks_seen"] == 3


def test_apply_weekly_tags_marks_returning_after_two_missed_weeks(tmp_path: Path):
    from radar_history import apply_weekly_tags
    from radar_models import Candidate

    history = {
        "company:beesafe.ai": {
            "display_name": "BeeSafe AI",
            "first_seen": "2026-04-06",
            "last_seen": "2026-04-13",
            "weeks_seen": 1,
            "missed_weeks": 0,
            "sectors": ["Cybersecurity"],
            "themes": ["AI fraud defense"],
            "last_source": "https://beesafe.ai",
        }
    }
    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        domain="beesafe.ai",
    )

    result = apply_weekly_tags([candidate], history, run_date="2026-05-04")

    assert result.candidates[0].weekly_tag == "RETURNING"


def test_apply_weekly_tags_emits_faded_for_missing_prior_candidate(tmp_path: Path):
    from radar_history import apply_weekly_tags

    history = {
        "company:oldco.ai": {
            "display_name": "OldCo",
            "first_seen": "2026-04-20",
            "last_seen": "2026-04-27",
            "weeks_seen": 1,
            "missed_weeks": 0,
            "sectors": ["AI Infra"],
            "themes": ["Agent runtime"],
            "last_source": "https://oldco.ai",
        }
    }

    result = apply_weekly_tags([], history, run_date="2026-05-04")

    assert result.faded == [{
        "stable_key": "company:oldco.ai",
        "name": "OldCo",
        "sector": "AI Infra",
        "theme": "Agent runtime",
        "last_seen": "2026-04-27",
        "source": "https://oldco.ai",
        "weekly_tag": "FADED",
    }]
```

- [x] **Step 7: Implement history load/save and tags**

Add to `.claude/skills/vc-signals/scripts/radar_history.py`:

```python
from dataclasses import dataclass


@dataclass
class HistoryResult:
    candidates: list[Candidate]
    faded: list[dict]
    history: dict


def _history_path(data_dir: Path) -> Path:
    return data_dir / "companies" / "candidate_history.json"


def load_candidate_history(data_dir: Path | None = None) -> dict:
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = _history_path(data_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_candidate_history(history: dict, data_dir: Path | None = None) -> None:
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = _history_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2))


def _weeks_between(later: str, earlier: str) -> int:
    later_dt = datetime.strptime(later, "%Y-%m-%d")
    earlier_dt = datetime.strptime(earlier, "%Y-%m-%d")
    return max(0, (later_dt - earlier_dt).days // 7)


def apply_weekly_tags(candidates: list[Candidate], history: dict, *, run_date: str) -> HistoryResult:
    current_keys = set()
    tagged = []

    for candidate in candidates:
        key = stable_candidate_key(candidate)
        current_keys.add(key)
        candidate.stable_key = key
        previous = history.get(key)

        if previous is None:
            candidate.weekly_tag = "NEW"
            weeks_seen = 1
            first_seen = run_date
        else:
            missed = _weeks_between(run_date, previous.get("last_seen", run_date)) - 1
            weeks_seen = int(previous.get("weeks_seen") or 0) + 1
            first_seen = previous.get("first_seen", run_date)
            if missed >= RETURNING_AFTER_MISSED_WEEKS:
                candidate.weekly_tag = "RETURNING"
            elif weeks_seen >= PERSISTENT_WEEKS:
                candidate.weekly_tag = "PERSISTENT"
            else:
                candidate.weekly_tag = ""

        history[key] = {
            "display_name": candidate.name,
            "first_seen": first_seen,
            "last_seen": run_date,
            "weeks_seen": weeks_seen,
            "missed_weeks": 0,
            "sectors": sorted(set((previous or {}).get("sectors", []) + [candidate.sector])),
            "themes": sorted(set((previous or {}).get("themes", []) + [candidate.theme])),
            "last_source": candidate.source,
        }
        tagged.append(candidate)

    faded = []
    for key, entry in history.items():
        if key in current_keys:
            continue
        missed_weeks = _weeks_between(run_date, entry.get("last_seen", run_date))
        entry["missed_weeks"] = missed_weeks
        if missed_weeks == 1:
            faded.append({
                "stable_key": key,
                "name": entry.get("display_name", ""),
                "sector": (entry.get("sectors") or [""])[0],
                "theme": (entry.get("themes") or [""])[0],
                "last_seen": entry.get("last_seen", ""),
                "source": entry.get("last_source", ""),
                "weekly_tag": "FADED",
            })

    return HistoryResult(candidates=tagged, faded=faded, history=history)
```

- [x] **Step 8: Verify history tests pass**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_history.py -q
```

Expected: all tests pass.

- [x] **Step 9: Wire history into weekly run**

Modify `run_weekly_artifacts` in `.claude/skills/vc-signals/scripts/radar_run.py`:

```python
from radar_history import apply_weekly_tags, load_candidate_history, save_candidate_history
```

After candidate scoring and before writing `candidates.json`:

```python
run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
history = load_candidate_history()
history_result = apply_weekly_tags(scored_candidates, history, run_date=run_date)
scored_candidates = history_result.candidates
save_candidate_history(history_result.history)
faded_candidates = history_result.faded
```

Pass `faded_candidates` into the renderer after Task 2 updates `render_weekly_brief`.

- [x] **Step 10: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_history.py .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_history.py
git commit -m "Add weekly radar candidate history"
```

---

## Task 2: Render Weekly Tags And Faded Rows

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_render.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_render.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`

- [x] **Step 1: Write render test for tags and faded rows**

Append to `.claude/skills/vc-signals/tests/test_radar_render.py`:

```python
def test_render_weekly_brief_includes_tags_and_faded_section():
    from radar_models import Candidate
    from radar_render import render_weekly_brief

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        tier="Partner Review",
        investment_interest="High",
        evidence_confidence="Medium",
        weekly_tag="NEW",
        why_on_radar="HN launch plus company evidence.",
        why_this_may_be_noise="Early signal may be founder-led.",
    )
    faded = [{
        "name": "OldCo",
        "sector": "AI Infra",
        "theme": "Agent runtime",
        "last_seen": "2026-04-27",
        "source": "https://oldco.ai",
        "weekly_tag": "FADED",
    }]

    markdown = render_weekly_brief([candidate], {}, [], faded=faded)

    assert "| BeeSafe AI | Cybersecurity | AI fraud defense | NEW | Partner Review |" in markdown
    assert "## Faded Off Radar" in markdown
    assert "OldCo" in markdown
    assert "2026-04-27" in markdown
```

- [x] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_render.py::test_render_weekly_brief_includes_tags_and_faded_section -q
```

Expected: `render_weekly_brief` does not accept `faded`.

- [x] **Step 3: Update renderer signature and table**

Modify `.claude/skills/vc-signals/scripts/radar_render.py`:

```python
def render_weekly_brief(candidates: list, coverage: dict, rejected: list, *, faded: list[dict] | None = None) -> str:
    faded = faded or []
```

Add a `Tag` column immediately after `Theme`:

```python
        "| Company / Project | Sector | Theme | Tag | Tier | Interest | Evidence | Attio | Action | LinkedIn | Founders | X | Why On Radar | Why This May Be Noise | Best Source |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
```

Update row formatting:

```python
            f"| {candidate.name} | {candidate.sector} | {candidate.theme} | {candidate.weekly_tag} | {candidate.tier} | "
```

After the weak-evidence section, add:

```python
    if faded:
        lines.extend(["", "## Faded Off Radar", ""])
        for item in faded:
            lines.append(
                f"- **{item.get('name', '')}** ({item.get('sector', '')}, {item.get('theme', '')}) "
                f"last seen {item.get('last_seen', '')}: {item.get('source', '')}"
            )
```

- [x] **Step 4: Pass faded rows from weekly run**

In `.claude/skills/vc-signals/scripts/radar_run.py`, change:

```python
preview_path.write_text(render_weekly_brief(scored_candidates, signal_result["coverage"], promotion["rejected"]))
```

to:

```python
preview_path.write_text(render_weekly_brief(scored_candidates, signal_result["coverage"], promotion["rejected"], faded=faded_candidates))
```

- [x] **Step 5: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_render.py .claude/skills/vc-signals/tests/test_radar_run.py -q
```

Expected: tests pass.

- [x] **Step 6: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_render.py .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_render.py
git commit -m "Render weekly radar history tags"
```

---

## Task 3: Add Evidence-Backed Company Enrichment Fields

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Create: `.claude/skills/vc-signals/scripts/radar_enrichment.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_enrichment.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`

- [x] **Step 1: Add enrichment fields to `Candidate`**

Add to `Candidate` in `.claude/skills/vc-signals/scripts/radar_models.py`:

```python
    stage: str = ""
    raised: str = ""
    headcount: str = ""
    founders: list[str] = field(default_factory=list)
    founding_year: str = ""
    lead_investor: str = ""
    enrichment_evidence: dict = field(default_factory=dict)
```

- [x] **Step 2: Write enrichment merge tests**

Create `.claude/skills/vc-signals/tests/test_radar_enrichment.py`:

```python
from datetime import date


def test_merge_source_metadata_enriches_only_evidence_backed_fields():
    from radar_enrichment import enrich_candidate
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
    )
    source_metadata = {
        "stage": "Seed",
        "raised": "$4M",
        "headcount": "12",
        "founders": ["Asha Rao", "Ben Lee"],
        "evidence": {
            "stage": "https://beesafe.ai/about",
            "raised": "https://beesafe.ai/blog/seed",
            "headcount": "https://linkedin.com/company/beesafe-ai",
            "founders": "https://beesafe.ai/about",
        },
    }

    enriched = enrich_candidate(candidate, source_metadata=source_metadata, cache={})

    assert enriched.stage == "Seed"
    assert enriched.raised == "$4M"
    assert enriched.headcount == "12"
    assert enriched.founders == ["Asha Rao", "Ben Lee"]
    assert enriched.enrichment_evidence["raised"] == "https://beesafe.ai/blog/seed"


def test_enrichment_does_not_invent_missing_fields():
    from radar_enrichment import enrich_candidate
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
    )

    enriched = enrich_candidate(candidate, source_metadata={}, cache={})

    assert enriched.stage == ""
    assert enriched.raised == ""
    assert enriched.headcount == ""
    assert enriched.founders == []
    assert enriched.enrichment_evidence == {}


def test_fresh_cache_enriches_candidate():
    from radar_enrichment import enrich_candidate
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
    )
    cache = {
        "beesafe ai": {
            "fetched_at": "2026-05-01",
            "stage": "Seed",
            "raised": "$4M",
            "evidence": {"stage": "https://beesafe.ai/about"},
        }
    }

    enriched = enrich_candidate(candidate, source_metadata={}, cache=cache, now=date(2026, 5, 4))

    assert enriched.stage == "Seed"
    assert enriched.raised == "$4M"
    assert enriched.enrichment_evidence["stage"] == "https://beesafe.ai/about"


def test_stale_cache_is_not_used_without_source_metadata():
    from radar_enrichment import enrich_candidate
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
    )
    cache = {
        "beesafe ai": {
            "fetched_at": "2026-04-01",
            "stage": "Seed",
            "raised": "$4M",
            "evidence": {"stage": "https://beesafe.ai/about"},
        }
    }

    enriched = enrich_candidate(candidate, source_metadata={}, cache=cache, now=date(2026, 5, 4), ttl_days=14)

    assert enriched.stage == ""
    assert enriched.raised == ""
```

- [x] **Step 3: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_enrichment.py -q
```

Expected: import error for `radar_enrichment`.

- [x] **Step 4: Implement enrichment helper**

Create `.claude/skills/vc-signals/scripts/radar_enrichment.py`:

```python
from __future__ import annotations

from datetime import date

from enrichment import is_cache_fresh
from persistence import _normalize_company_name
from radar_models import Candidate

FIELDS = ("stage", "raised", "headcount", "founding_year", "lead_investor")


def _merge_field(candidate: Candidate, field: str, value, evidence: dict) -> None:
    if not value:
        return
    if getattr(candidate, field):
        return
    setattr(candidate, field, str(value))
    if evidence.get(field):
        candidate.enrichment_evidence[field] = evidence[field]


def _merge_founders(candidate: Candidate, value, evidence: dict) -> None:
    if candidate.founders or not value:
        return
    if isinstance(value, list):
        candidate.founders = [str(item) for item in value if item]
    elif isinstance(value, str):
        candidate.founders = [part.strip() for part in value.split(",") if part.strip()]
    if candidate.founders and evidence.get("founders"):
        candidate.enrichment_evidence["founders"] = evidence["founders"]


def enrich_candidate(
    candidate: Candidate,
    *,
    source_metadata: dict,
    cache: dict,
    now: date | None = None,
    ttl_days: int = 14,
) -> Candidate:
    key = _normalize_company_name(candidate.name)
    cache_entry = cache.get(key) or {}
    if cache_entry and is_cache_fresh(cache_entry, ttl_days=ttl_days, now=now):
        cache_evidence = cache_entry.get("evidence", {})
        for field in FIELDS:
            _merge_field(candidate, field, cache_entry.get(field), cache_evidence)
        _merge_founders(candidate, cache_entry.get("founders"), cache_evidence)

    source_evidence = source_metadata.get("evidence", {})
    for field in FIELDS:
        _merge_field(candidate, field, source_metadata.get(field), source_evidence)
    _merge_founders(candidate, source_metadata.get("founders"), source_evidence)
    return candidate
```

- [x] **Step 5: Verify enrichment tests pass**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_enrichment.py -q
```

Expected: all tests pass.

- [x] **Step 6: Wire enrichment into weekly run**

In `radar_run.py`, import:

```python
from enrichment import load_enrichment_cache
from radar_enrichment import enrich_candidate
```

Add helper:

```python
def _source_metadata_for_candidate(candidate: Candidate) -> dict:
    metadata = {}
    for source in candidate.sources or [candidate.source]:
        if not source:
            continue
    return candidate.engagement.get("enrichment", {}) if isinstance(candidate.engagement, dict) else {}
```

After Attio enrichment and before final scoring:

```python
cache = load_enrichment_cache()
scored_candidates = [
    enrich_candidate(candidate, source_metadata=_source_metadata_for_candidate(candidate), cache=cache)
    for candidate in scored_candidates
]
```

- [x] **Step 7: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/scripts/radar_enrichment.py .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_enrichment.py
git commit -m "Add evidence-backed company enrichment"
```

---

## Task 4: Render Enrichment Fields

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_render.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_render.py`

- [x] **Step 1: Write render test for enrichment fields**

Append to `.claude/skills/vc-signals/tests/test_radar_render.py`:

```python
def test_render_weekly_brief_includes_enrichment_fields():
    from radar_models import Candidate
    from radar_render import render_weekly_brief

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        tier="Partner Review",
        investment_interest="High",
        evidence_confidence="Medium",
        stage="Seed",
        raised="$4M",
        headcount="12",
        founders=["Asha Rao", "Ben Lee"],
        why_on_radar="HN launch plus company evidence.",
        why_this_may_be_noise="Early signal may be founder-led.",
    )

    markdown = render_weekly_brief([candidate], {}, [])

    assert "| Company / Project | Sector | Theme | Tag | Tier | Interest | Evidence | Stage | Raised | Headcount | Founders | Attio |" in markdown
    assert "| BeeSafe AI | Cybersecurity | AI fraud defense |  | Partner Review | High | Medium | Seed | $4M | 12 | Asha Rao, Ben Lee |" in markdown
```

- [x] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_render.py::test_render_weekly_brief_includes_enrichment_fields -q
```

Expected: table does not include enrichment columns.

- [x] **Step 3: Add columns to renderer**

In `_table`, replace the header with:

```python
"| Company / Project | Sector | Theme | Tag | Tier | Interest | Evidence | Stage | Raised | Headcount | Founders | Attio | Action | LinkedIn | Founder Profiles | X | Why On Radar | Why This May Be Noise | Best Source |",
"|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
```

Add helper:

```python
def _founder_names(candidate) -> str:
    return ", ".join(candidate.founders or [])
```

Update rows to include:

```python
f"{candidate.stage} | {candidate.raised} | {candidate.headcount} | {_founder_names(candidate)} | "
```

- [x] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_render.py -q
```

Expected: tests pass.

- [x] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_render.py .claude/skills/vc-signals/tests/test_radar_render.py
git commit -m "Render company enrichment fields"
```

---

## Task 5: Complete OSS Radar Semantics

**Files:**
- Create: `.claude/skills/vc-signals/scripts/radar_oss.py`
- Create: `.claude/skills/vc-signals/tests/test_radar_oss.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`

- [x] **Step 1: Add OSS fields to `Candidate`**

Add to `Candidate`:

```python
    oss_company_formation_score: int = 0
    oss_action_reason: str = ""
    license: str = ""
    repo_age_days: int = 0
    stars: int = 0
    stars_30d: int = 0
    maintainer_profiles: list[dict] = field(default_factory=list)
```

- [x] **Step 2: Write OSS scoring tests**

Create `.claude/skills/vc-signals/tests/test_radar_oss.py`:

```python
def test_score_oss_repo_contact_maintainer_when_user_owned_fast_growing():
    from radar_models import Candidate
    from radar_oss import enrich_oss_candidate

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )
    repo = {
        "full_name": "affaan-m/agentshield",
        "owner_name": "affaan-m",
        "owner_type": "User",
        "stars": 800,
        "age_days": 120,
        "license": {"spdx_id": "MIT"},
        "velocity": {"stars_last_30d": 185},
        "topics": ["ai-agent", "security", "mcp"],
    }

    enriched = enrich_oss_candidate(candidate, repo)

    assert enriched.oss_company_formation_score >= 70
    assert enriched.action == "contact maintainer"
    assert "user-owned fast-growing repo" in enriched.oss_action_reason
    assert enriched.license == "MIT"
    assert enriched.stars_30d == 185


def test_score_oss_repo_watch_when_org_owned_but_interesting():
    from radar_models import Candidate
    from radar_oss import enrich_oss_candidate

    candidate = Candidate(
        name="redwoodjs/agent-ci",
        sector="OSS",
        theme="Agent CI",
        source="https://github.com/redwoodjs/agent-ci",
        candidate_type="oss_project",
    )
    repo = {
        "full_name": "redwoodjs/agent-ci",
        "owner_name": "redwoodjs",
        "owner_type": "Organization",
        "stars": 300,
        "age_days": 80,
        "license": {"spdx_id": "MIT"},
        "velocity": {"stars_last_30d": 123},
        "topics": ["github-actions", "agents"],
    }

    enriched = enrich_oss_candidate(candidate, repo)

    assert enriched.action == "watch"
    assert enriched.oss_company_formation_score < 70
```

- [x] **Step 3: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_oss.py -q
```

Expected: import error for `radar_oss`.

- [x] **Step 4: Implement OSS enrichment**

Create `.claude/skills/vc-signals/scripts/radar_oss.py`:

```python
from __future__ import annotations

from radar_models import Candidate


def _license_id(repo: dict) -> str:
    license_payload = repo.get("license") or {}
    return license_payload.get("spdx_id") or repo.get("license") or ""


def enrich_oss_candidate(candidate: Candidate, repo: dict) -> Candidate:
    stars_30d = int((repo.get("velocity") or {}).get("stars_last_30d") or 0)
    stars = int(repo.get("stars") or 0)
    age_days = int(repo.get("age_days") or 0)
    owner_type = repo.get("owner_type") or ""
    topics = " ".join(repo.get("topics") or []).lower()

    score = 20
    if stars_30d >= 150:
        score += 35
    elif stars_30d >= 50:
        score += 25
    elif stars_30d >= 10:
        score += 10
    if owner_type == "User":
        score += 20
    if 30 <= age_days <= 365:
        score += 10
    if any(term in topics for term in ("ai-agent", "mcp", "security", "developer", "data")):
        score += 10
    if stars >= 500:
        score += 5

    candidate.oss_company_formation_score = min(100, score)
    candidate.license = _license_id(repo)
    candidate.repo_age_days = age_days
    candidate.stars = stars
    candidate.stars_30d = stars_30d
    candidate.maintainer_profiles = [{
        "name": repo.get("owner_name", ""),
        "github": candidate.source.rsplit("/", 1)[0] if "/" in candidate.source else candidate.source,
        "owner_type": owner_type,
    }]

    if candidate.oss_company_formation_score >= 70 and owner_type == "User":
        candidate.action = "contact maintainer"
        candidate.oss_action_reason = "High company-formation score from user-owned fast-growing repo."
    elif candidate.oss_company_formation_score >= 60:
        candidate.action = "track company formation"
        candidate.oss_action_reason = "Strong OSS momentum; verify maintainer intent and commercial wrapper."
    else:
        candidate.action = "watch"
        candidate.oss_action_reason = "Interesting OSS signal; company formation is not yet clear."
    return candidate
```

- [x] **Step 5: Verify OSS tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_oss.py -q
```

Expected: tests pass.

- [x] **Step 6: Wire OSS enrichment in candidate promotion**

In `radar_run.py`, import:

```python
from radar_oss import enrich_oss_candidate
```

In `_candidate_from_signal`, after building an OSS candidate:

```python
    candidate = Candidate(...)
    if signal.role == "oss_project":
        candidate = enrich_oss_candidate(candidate, item)
    return candidate
```

- [x] **Step 7: Commit**

```bash
git add .claude/skills/vc-signals/scripts/radar_oss.py .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_oss.py
git commit -m "Complete OSS radar scoring semantics"
```

---

## Task 6: Complete Attio Read-Only Context

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/attio.py`
- Modify: `.claude/skills/vc-signals/tests/test_attio.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Modify: `.claude/skills/vc-signals/scripts/radar_render.py`

- [x] **Step 1: Add Attio fields to `Candidate`**

Add to `Candidate`:

```python
    attio_record_url: str = ""
    attio_owner: str = ""
    attio_last_interaction: str = ""
    attio_staleness_reason: str = ""
```

- [x] **Step 2: Write Attio enrichment tests**

Append to `.claude/skills/vc-signals/tests/test_attio.py`:

```python
def test_summarize_attributes_extracts_owner_last_interaction_and_round_fields():
    from attio import summarize_attributes

    attributes = {
        "mmp_owner": [{"target_object": "people", "target_record_id": "person_1", "value": "Partner"}],
        "last_interaction": [{"interacted_at": "2026-02-01"}],
        "last_round_type": [{"value": "Seed"}],
        "headcount": [{"value": "24"}],
        "total_amount_raised_4": [{"value": "$5M"}],
    }

    summary = summarize_attributes(attributes)

    assert summary["owner"] == "Partner"
    assert summary["last_interaction"] == "2026-02-01"
    assert summary["last_round_type"] == "Seed"
    assert summary["headcount"] == "24"
    assert summary["total_amount_raised"] == "$5M"


def test_match_company_returns_record_url_and_enrichment_fields():
    from attio import AttioClient

    def fake_request(method, path, payload):
        if path == "/objects/records/search":
            return {"data": [{"record_text": "BeeSafe AI", "object_slug": "companies", "id": {"record_id": "rec_123"}}]}
        if path.endswith("/attributes/domains/values"):
            return {"data": [{"domain": "beesafe.ai"}]}
        if path.endswith("/attributes/mmp_owner/values"):
            return {"data": [{"value": "Partner"}]}
        if path.endswith("/attributes/status_8/values"):
            return {"data": []}
        if path.endswith("/attributes/last_interaction/values"):
            return {"data": [{"interacted_at": "2026-02-01"}]}
        if path.endswith("/attributes/last_round_type/values"):
            return {"data": [{"value": "Seed"}]}
        if path.endswith("/attributes/headcount/values"):
            return {"data": [{"value": "24"}]}
        if path.endswith("/attributes/total_amount_raised_4/values"):
            return {"data": [{"value": "$5M"}]}
        if path.endswith("/attributes/employee_range/values"):
            return {"data": []}
        if path.endswith("/entries"):
            return {"data": [{"list_api_slug": "pipeline_2"}]}
        if path == "/lists":
            return {"data": [{"api_slug": "pipeline_2", "name": "Pipeline", "parent_object": ["companies"]}]}
        raise AssertionError(path)

    client = AttioClient("token", request_fn=fake_request)
    result = client.match_company({"name": "BeeSafe AI", "domain": "beesafe.ai"})

    assert result["attio_record_url"].endswith("/rec_123")
    assert result["attio_owner"] == "Partner"
    assert result["stage"] == "Seed"
    assert result["headcount"] == "24"
    assert result["raised"] == "$5M"
```

- [x] **Step 3: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_attio.py::test_summarize_attributes_extracts_owner_last_interaction_and_round_fields .claude/skills/vc-signals/tests/test_attio.py::test_match_company_returns_record_url_and_enrichment_fields -q
```

Expected: missing fields.

- [x] **Step 4: Implement richer Attio fields**

In `summarize_attributes`, add:

```python
    if attributes.get("mmp_owner"):
        first_owner = attributes["mmp_owner"][0]
        out["has_owner"] = True
        out["owner"] = first_owner.get("value") or first_owner.get("target_record_id", "")
```

In `AttioClient.__init__`, add:

```python
        self._company_list_lookup = None
```

Create method:

```python
    def company_list_lookup(self) -> dict:
        if self._company_list_lookup is None:
            self._company_list_lookup = {item["api_slug"]: item["name"] for item in self.list_company_lists()}
        return self._company_list_lookup
```

Replace list lookup in `match_company` with:

```python
        list_lookup = self.company_list_lookup()
```

After `classification["attio_attributes"] = summarize_attributes(attributes)`, add:

```python
        summary = classification["attio_attributes"]
        classification["attio_record_url"] = f"https://app.attio.com/marathon/companies/record/{record_id}" if record_id else ""
        classification["attio_owner"] = summary.get("owner", "")
        classification["attio_last_interaction"] = summary.get("last_interaction", "")
        classification["stage"] = summary.get("last_round_type", "")
        classification["headcount"] = summary.get("headcount") or summary.get("employee_range", "")
        classification["raised"] = summary.get("total_amount_raised", "")
        if classification["attio_status"] in {"stale", "no_owner"}:
            classification["attio_staleness_reason"] = "No owner or stale pipeline context; refresh before outreach."
```

- [x] **Step 5: Verify Attio tests pass**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_attio.py -q
```

Expected: tests pass.

- [x] **Step 6: Render Attio owner and URL**

Update `radar_render.py` table columns to include `Attio Owner` and `Attio URL` after `Attio`. Render:

```python
f"{candidate.attio_status} | {candidate.attio_owner} | {candidate.attio_record_url} | "
```

- [x] **Step 7: Commit**

```bash
git add .claude/skills/vc-signals/scripts/attio.py .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/scripts/radar_render.py .claude/skills/vc-signals/tests/test_attio.py
git commit -m "Complete read-only Attio radar context"
```

---

## Task 7: Integration Verification And README Update

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`
- Modify: `README.md`

- [x] **Step 1: Add integration test for completed output contract**

Append to `.claude/skills/vc-signals/tests/test_radar_run.py`:

```python
def test_weekly_artifact_includes_history_enrichment_oss_and_attio_fields(tmp_path, monkeypatch):
    import json
    import radar_run

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [{
                        "source": "web",
                        "company_name": "BeeSafe AI",
                        "title": "BeeSafe AI stops AI voice phishing for banks",
                        "url": "https://beesafe.ai",
                        "domain": "beesafe.ai",
                    }]
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "_attio_client_from_env", lambda: None)
    monkeypatch.setattr(radar_run, "load_enrichment_cache", lambda: {
        "beesafe ai": {
            "fetched_at": "2026-05-04",
            "stage": "Seed",
            "raised": "$4M",
            "headcount": "12",
            "founders": ["Asha Rao"],
            "evidence": {"raised": "https://beesafe.ai/blog/seed"},
        }
    })

    radar_run.run_weekly_artifacts(output_dir=tmp_path, sectors=("cybersecurity",), github_limit=0)

    candidates = json.loads((tmp_path / "candidates.json").read_text())
    assert candidates[0]["weekly_tag"] == "NEW"
    assert candidates[0]["stage"] == "Seed"
    assert candidates[0]["raised"] == "$4M"
    assert candidates[0]["headcount"] == "12"
    assert "Stage" in (tmp_path / "weekly-preview.md").read_text()
```

- [x] **Step 2: Verify failure**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_weekly_artifact_includes_history_enrichment_oss_and_attio_fields -q
```

Expected: missing tag/enrichment/rendered columns until prior tasks are wired.

- [x] **Step 3: Update README current-state section**

After completing Tasks 1-6, update the README to say:

```markdown
Current weekly output includes week-over-week candidate tags, evidence-backed stage/raised/headcount/founder fields when available, OSS company-formation scoring, and richer read-only Attio context.
```

- [x] **Step 4: Run full verification**

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
rm -rf docs/radar-runs/marathon-weekly-v3
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/marathon-weekly-v3 --max-queries-per-sector 2 --github-limit 80 --limit 50
test -f docs/radar-runs/marathon-weekly-v3/weekly-preview.md
test -f docs/radar-runs/marathon-weekly-v3/signals.json
test -f docs/radar-runs/marathon-weekly-v3/candidates.json
rg -n "Tag|Stage|Raised|Headcount|Faded Off Radar|Attio" docs/radar-runs/marathon-weekly-v3/weekly-preview.md
rg -n "ATTIO_ACCESS_TOKEN='|Bearer [A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-or-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|fwKR[A-Za-z0-9_-]{10,}" . --glob '!vendor/**' --glob '!.git/**' --glob '!docs/superpowers/plans/**'
```

Expected:

- pytest passes.
- Weekly command emits all artifacts.
- `rg` finds the output headings/columns.
- Secret scan exits `1` with no output.

- [x] **Step 5: Commit**

```bash
git add README.md .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/tests/test_radar_run.py docs/radar-runs/marathon-weekly-v3
git commit -m "Verify completed radar reliability workflow"
```

---

## Success Criteria

- A brand-new user can read README and know how to install, configure, and run the weekly all-sector radar.
- The README does not imply that funding/headcount/founders are guaranteed unless evidence-backed.
- Weekly artifacts include `NEW`, `RETURNING`, `PERSISTENT`, and `FADED` where applicable.
- `candidates.json` contains stable keys, weekly tags, enrichment fields, enrichment evidence, OSS formation fields, and richer Attio fields.
- OSS rows have explicit action reasons and company-formation scores.
- Attio output includes record URL, owner/staleness context, and mapped stage/raised/headcount where available.
- All enrichment fields are blank unless backed by cache, Attio, source metadata, or explicit evidence.
- Full tests pass.
- Secret scan returns no committed keys.

---

## Self-Review

- The plan covers the three requested completion areas: week-over-week, funding/headcount/founders, and OSS/Attio completion.
- The README verification changes already made before this plan should be committed separately or together with a docs commit.
- The plan keeps candidate history, enrichment, OSS scoring, and Attio context in separate modules so the next implementation can be tested incrementally.
