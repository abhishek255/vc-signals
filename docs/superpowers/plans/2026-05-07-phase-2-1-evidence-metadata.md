# Phase 2.1 Evidence Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Preserve compact identity-useful metadata from already-collected evidence and make identity resolution consume stored metadata before live fetching evidence URLs.

**Architecture:** Add a compact `EvidenceMetadata` dataclass and `Candidate.evidence_metadata` field. Candidate promotion will carry source metadata from `Signal.metadata` into `Candidate.evidence_metadata`; identity resolution will inspect candidate fields, then evidence metadata, then live-fetch already-present URLs only as fallback. This is not source expansion: no new sources, no broad search, no X/LinkedIn/Product Hunt/package registries, no Attio writeback, and no `weekly-preview.md` changes.

**Tech Stack:** Python dataclasses, existing radar models/run/focus/identity modules, pytest, JSON artifacts.

---

## Scope

Build only:

- Compact metadata retention from raw evidence to candidates.
- Metadata-first identity resolution.
- Controlled HN/GitHub launch verification using already-collected fields.

Do not build:

- broad web search
- X/Twitter
- LinkedIn
- Product Hunt
- package registries
- Slack
- Attio writeback
- `weekly-preview.md` changes

## Files

Modify:

- `.claude/skills/vc-signals/scripts/radar_models.py`
- `.claude/skills/vc-signals/scripts/radar_run.py`
- `.claude/skills/vc-signals/scripts/identity_resolution.py`
- `.claude/skills/vc-signals/tests/test_radar_models.py`
- `.claude/skills/vc-signals/tests/test_radar_run.py`
- `.claude/skills/vc-signals/tests/test_identity_resolution.py`

Generated run artifacts under `docs/radar-runs/...` must remain uncommitted.

## Task 1: Evidence Metadata Model

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_models.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_models.py`

- [x] **Step 1: Add failing roundtrip test**

Add:

```python
def test_evidence_metadata_roundtrip_and_candidate_field():
    from radar_models import Candidate, EvidenceMetadata

    metadata = EvidenceMetadata(
        candidate_key="candidate:cybersecurity:burrow",
        source_url="https://news.ycombinator.com/item?id=47761957",
        source="hackernews",
        title="Show HN: Burrow - Runtime Security for AI Agents",
        author="saranshrana",
        outbound_url="https://burrow.security",
        domain="burrow.security",
        query_kind="theme_company_search",
        query_topic="AI agent security startups Seed Series A founder launch",
    )
    restored = EvidenceMetadata.from_dict({**metadata.to_dict(), "future": "ignored"})

    candidate = Candidate(
        name="Burrow",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=47761957",
        candidate_type="launch",
        evidence_metadata=[restored.to_dict()],
    )

    assert restored.outbound_url == "https://burrow.security"
    assert Candidate.from_dict(candidate.to_dict()).evidence_metadata[0]["domain"] == "burrow.security"
```

- [x] **Step 2: Run test**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py::test_evidence_metadata_roundtrip_and_candidate_field -q
```

Expected: FAIL because `EvidenceMetadata` and `Candidate.evidence_metadata` do not exist.

- [x] **Step 3: Implement model**

Add to `radar_models.py`:

```python
@dataclass
class EvidenceMetadata:
    candidate_key: str = ""
    source_url: str = ""
    source: str = ""
    title: str = ""
    author: str = ""
    published_at: str = ""
    container: str = ""
    query_kind: str = ""
    query_topic: str = ""
    outbound_url: str = ""
    domain: str = ""
    owner_name: str = ""
    owner_type: str = ""
    topics: list[str] = field(default_factory=list)
    description: str = ""
    homepage: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "EvidenceMetadata":
        return cls(**_known_payload(cls, payload))
```

Add to `Candidate`:

```python
evidence_metadata: list[dict] = field(default_factory=list)
```

- [x] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_models.py::test_evidence_metadata_roundtrip_and_candidate_field -q
```

Expected: PASS.

## Task 2: Preserve Metadata During Candidate Promotion

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/radar_run.py`
- Modify: `.claude/skills/vc-signals/tests/test_radar_run.py`

- [x] **Step 1: Add failing promotion tests**

Add:

```python
def test_candidate_promotion_preserves_compact_hn_evidence_metadata():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="cybersecurity",
        item={
            "source": "hackernews",
            "title": "Show HN: Burrow - Runtime Security for AI Agents",
            "url": "https://news.ycombinator.com/item?id=47761957",
            "author": "saranshrana",
            "published_at": "2026-04-14",
            "container": "Hacker News",
            "query_kind": "theme_company_search",
            "query_topic": "AI agent security startups Seed Series A founder launch",
            "outbound_url": "https://burrow.security",
            "domain": "burrow.security",
        },
    )

    candidate = promote_signals_to_candidates([signal])["candidates"][0]

    assert candidate.evidence_metadata
    metadata = candidate.evidence_metadata[0]
    assert metadata["source"] == "hackernews"
    assert metadata["author"] == "saranshrana"
    assert metadata["outbound_url"] == "https://burrow.security"
    assert metadata["domain"] == "burrow.security"
    assert "snippet" not in metadata
```

Add:

```python
def test_candidate_promotion_preserves_compact_github_evidence_metadata():
    from radar_run import build_signals_from_evidence, promote_signals_to_candidates

    evidence = {
        "last30days": {},
        "github": [
            {
                "full_name": "slowql/slowql",
                "description": "SQL static analyzer for performance and compliance",
                "url": "https://github.com/slowql/slowql",
                "owner_name": "slowql",
                "owner_type": "Organization",
                "topics": ["sql", "security", "compliance"],
                "homepage": "https://slowql.dev",
            }
        ],
    }

    candidate = promote_signals_to_candidates(build_signals_from_evidence(evidence)["signals"])["candidates"][0]
    metadata = candidate.evidence_metadata[0]

    assert metadata["owner_name"] == "slowql"
    assert metadata["owner_type"] == "Organization"
    assert metadata["topics"] == ["sql", "security", "compliance"]
    assert metadata["description"] == "SQL static analyzer for performance and compliance"
    assert metadata["homepage"] == "https://slowql.dev"
```

- [x] **Step 2: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_candidate_promotion_preserves_compact_hn_evidence_metadata .claude/skills/vc-signals/tests/test_radar_run.py::test_candidate_promotion_preserves_compact_github_evidence_metadata -q
```

Expected: FAIL because metadata is not preserved.

- [x] **Step 3: Implement metadata extraction**

In `radar_run.py`, import `EvidenceMetadata` and add:

```python
def _compact_evidence_metadata(candidate_key: str, item: dict) -> dict:
    metadata = EvidenceMetadata(
        candidate_key=candidate_key,
        source_url=item.get("url", ""),
        source=item.get("source", ""),
        title=item.get("title") or item.get("full_name") or item.get("name") or "",
        author=item.get("author", ""),
        published_at=item.get("published_at", ""),
        container=item.get("container", ""),
        query_kind=item.get("query_kind", ""),
        query_topic=item.get("query_topic", ""),
        outbound_url=item.get("outbound_url") or item.get("resolved_url") or "",
        domain=item.get("domain") or item.get("website_domain") or "",
        owner_name=item.get("owner_name", ""),
        owner_type=item.get("owner_type", ""),
        topics=list(item.get("topics") or []),
        description=item.get("description") or item.get("snippet") or "",
        homepage=item.get("homepage") or item.get("website") or "",
    )
    return metadata.to_dict()
```

In `_candidate_from_signal()`, after candidate creation and before `merge_source_enrichment`, assign:

```python
    candidate.evidence_metadata = [_compact_evidence_metadata(candidate.stable_key or candidate.name, item)]
```

If `stable_key` is not set until later in `promote_signals_to_candidates`, set `candidate_key` to `name` here. Do not include full raw blobs.

- [x] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_radar_run.py::test_candidate_promotion_preserves_compact_hn_evidence_metadata .claude/skills/vc-signals/tests/test_radar_run.py::test_candidate_promotion_preserves_compact_github_evidence_metadata -q
```

Expected: PASS.

## Task 3: Resolve Identity From Evidence Metadata First

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/identity_resolution.py`
- Modify: `.claude/skills/vc-signals/tests/test_identity_resolution.py`

- [x] **Step 1: Add failing resolver tests**

Add:

```python
def test_stored_hn_outbound_url_resolves_without_live_fetch(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    def fail_fetch(url, cache=None, timeout_seconds=8):
        raise AssertionError("live fetch should not run when metadata has outbound URL")

    monkeypatch.setattr("identity_resolution.fetch_existing_url", fail_fetch)

    result = resolve_candidate_identity(
        _candidate(
            evidence_metadata=[
                {
                    "source": "hackernews",
                    "source_url": "https://news.ycombinator.com/item?id=47761957",
                    "title": "Show HN: Burrow - Runtime Security for AI Agents",
                    "outbound_url": "https://burrow.security",
                    "domain": "burrow.security",
                }
            ]
        )
    )

    assert result.verified_domain == "burrow.security"
    assert result.domain_confidence == "High"
    assert "hn_outbound_url_metadata" in result.verified_domain_basis
    assert result.fetch_warnings == []
```

Add:

```python
def test_github_homepage_is_domain_candidate_not_owner_ready_by_itself():
    from identity_resolution import resolve_candidate_identity

    result = resolve_candidate_identity(
        _candidate(
            name="slowql/slowql",
            candidate_type="oss_project",
            source="https://github.com/slowql/slowql",
            sources=["https://github.com/slowql/slowql"],
            attio_status="no_match",
            evidence_metadata=[
                {
                    "source": "github",
                    "source_url": "https://github.com/slowql/slowql",
                    "owner_name": "slowql",
                    "owner_type": "Organization",
                    "description": "SQL static analyzer for performance and compliance",
                    "topics": ["sql", "security"],
                    "homepage": "https://slowql.dev",
                }
            ],
        )
    )

    assert result.verified_domain == "slowql.dev"
    assert "github_homepage_metadata" in result.verified_domain_basis
    assert result.project_url == "https://github.com/slowql/slowql"
    assert result.recommended_identity_action != "Assign owner"
```

- [x] **Step 2: Run tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py::test_stored_hn_outbound_url_resolves_without_live_fetch .claude/skills/vc-signals/tests/test_identity_resolution.py::test_github_homepage_is_domain_candidate_not_owner_ready_by_itself -q
```

Expected: FAIL because resolver ignores evidence metadata.

- [x] **Step 3: Implement metadata hints**

In `identity_resolution.py`, add:

```python
def _metadata_items(candidate: Candidate) -> list[dict]:
    return [item for item in candidate.evidence_metadata or [] if isinstance(item, dict)]


def resolve_from_evidence_metadata(candidate: Candidate) -> dict:
    hints = {
        "verified_domain": "",
        "domain_confidence": "Low",
        "verified_domain_basis": [],
        "project_url": "",
        "source_outbound_urls": [],
        "source_titles": [],
        "identity_confidence_basis": [],
        "resolved_from": [],
        "maintainers": [],
        "maintainer_profiles": [],
    }
    for item in _metadata_items(candidate):
        source = (item.get("source") or "").lower()
        source_url = item.get("source_url") or item.get("url") or ""
        title = item.get("title") or ""
        if title:
            hints["source_titles"].append(title)

        github = parse_github_url(source_url)
        if github:
            hints["project_url"] = hints["project_url"] or github["project_url"]
            hints["identity_confidence_basis"].append("github_project_identity")
            hints["resolved_from"].append("github_metadata")

        if item.get("owner_name"):
            hints["maintainers"].append(item["owner_name"])
            hints["maintainer_profiles"].append({
                "name": item["owner_name"],
                "type": item.get("owner_type", ""),
                "source": "github_metadata",
            })

        outbound_url = item.get("outbound_url") or ""
        domain = item.get("domain") or ""
        homepage = item.get("homepage") or ""
        if source == "hackernews" and outbound_url:
            hints["source_outbound_urls"].append(outbound_url)
            outbound_domain = _domain_from_url(outbound_url) or _normalize_domain(domain)
            if outbound_domain:
                hints["verified_domain"] = hints["verified_domain"] or outbound_domain
                hints["domain_confidence"] = "High"
                hints["verified_domain_basis"].append("hn_outbound_url_metadata")
                hints["resolved_from"].append("evidence_metadata")
        elif source == "github" and homepage:
            homepage_domain = _domain_from_url(homepage)
            if homepage_domain:
                hints["verified_domain"] = hints["verified_domain"] or homepage_domain
                hints["domain_confidence"] = "Medium"
                hints["verified_domain_basis"].append("github_homepage_metadata")
                hints["resolved_from"].append("evidence_metadata")

    for key in ("verified_domain_basis", "source_outbound_urls", "source_titles", "identity_confidence_basis", "resolved_from", "maintainers"):
        hints[key] = list(dict.fromkeys(hints[key]))
    return hints
```

Then update `resolve_candidate_identity()`:

1. Call `metadata_hints = resolve_from_evidence_metadata(candidate)`.
2. Prefer metadata hints before live URL hints.
3. Only call `resolve_from_existing_urls(candidate)` if metadata did not produce a verified domain for HN rows.
4. Merge maintainer hints into existing maintainers.
5. Add metadata `resolved_from`, titles, outbound URLs, and basis to the final `IdentityResolution`.

- [x] **Step 4: Verify**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_identity_resolution.py -q
```

Expected: PASS.

## Task 4: Regenerate Saved Artifact And Product Check

**Files:**
- Write local generated artifacts under `docs/radar-runs/current-focus-check/`
- Do not commit generated artifacts.

- [x] **Step 1: Rebuild saved artifact**

Run the same saved-artifact rebuild script used in Phase 2:

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
print('verified domains:', sum(1 for item in resolutions if item.verified_domain))
print('upgrades:', [item.original_name for item in resolutions if item.recommended_identity_action in {'Assign owner', 'Refresh Attio'}])
for item in resolutions:
    if item.original_name == 'Burrow':
        print(json.dumps(item.to_dict(), indent=2))
PY
```

- [x] **Step 2: Verify `weekly-preview.md` unchanged**

```bash
git diff -- docs/radar-runs/current-focus-check/weekly-preview.md docs/radar-runs/current/weekly-preview.md
```

Expected: no diff.

## Task 5: Full Verification And Commit

- [x] **Step 1: Run full tests**

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: all tests pass.

- [x] **Step 2: Commit source/test changes only**

```bash
git add .claude/skills/vc-signals/scripts/radar_models.py .claude/skills/vc-signals/scripts/radar_run.py .claude/skills/vc-signals/scripts/identity_resolution.py .claude/skills/vc-signals/tests/test_radar_models.py .claude/skills/vc-signals/tests/test_radar_run.py .claude/skills/vc-signals/tests/test_identity_resolution.py docs/superpowers/plans/2026-05-07-phase-2-1-evidence-metadata.md
git commit -m "Preserve evidence metadata for identity resolution"
git push
```

Do not add generated `docs/radar-runs/...` artifacts.

## Definition Of Done

- `EvidenceMetadata` exists and roundtrips.
- `Candidate.evidence_metadata` survives JSON roundtrip.
- HN and GitHub compact metadata are preserved during candidate promotion.
- Identity resolution prefers stored metadata over live fetch.
- HN stored outbound URL can resolve `verified_domain` without live fetch.
- HN 429 still fails closed when no stored outbound URL exists.
- GitHub homepage is treated as domain candidate with explicit basis, not automatic owner-ready proof.
- No new broad source adapters are added.
- `weekly-preview.md` diff is empty.
- Full tests pass.
- Generated run artifacts are not committed.
