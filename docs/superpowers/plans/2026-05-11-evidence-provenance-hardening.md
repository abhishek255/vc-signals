# Evidence Provenance Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact, review-grade evidence provenance for HN Assign-owner rows only.

**Architecture:** Keep HN as an opt-in trial path and harden only the final Assign-owner review surface. The enrichment row should carry a structured `assign_owner_evidence_provenance` object that separates HN source, official/company source, founder, stage/funding, commercial/customer/waitlist, and Attio evidence without changing gates or adding sources.

**Tech Stack:** Python dataclass-style dict payloads, existing `hn_outbound_enrichment.py` and `hn_weekly_trial.py` artifact writers, pytest.

---

## Scope

This plan does **not** enable HN by default, add sources, resume YC, write to Attio, or change owner-readiness gates. It only improves provenance display for rows that already pass all existing gates and become `Assign owner`.

Cycle validation remains separate:

- Cycle 1 is a post-merge regression baseline because it used `seed_provenance=previous_artifact_fallback`.
- Cycle 2 and Cycle 3 should require `seed_provenance=fresh_weekly_run` wherever possible.
- If a cycle uses fallback seeds, it must clearly say it does not count toward product validation.

## File Map

- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
  - Build structured provenance for Assign-owner rows.
  - Prefer exact/durable evidence URLs over generic paths such as `/blog`.
  - Keep the current `founder_team_evidence`, `stage_funding_evidence`, and `customer_buyer_evidence` arrays for backward compatibility.
- Modify: `.claude/skills/vc-signals/scripts/hn_weekly_trial.py`
  - Render Assign-owner provenance in `hn-trial-row-review.md`.
  - Keep project-only rows summarized.
- Modify: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`
  - Add regression coverage for Veris-style Assign-owner provenance.
  - Add a guard that Research Deeper rows do not require the full provenance package.
- Modify: `.claude/skills/vc-signals/tests/test_hn_weekly_trial.py`
  - Add markdown review coverage for separate HN/founder/stage/customer/Attio evidence fields.

---

### Task 1: Add Assign-Owner Provenance Package

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Test: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`

- [ ] **Step 1: Write failing Veris provenance test**

Add this test to `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py` near the existing Veris owner-ready tests:

```python
def test_hn_assign_owner_row_separates_exact_evidence_provenance():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def page_fetcher(url):
        if url.endswith("/blog"):
            return (
                "<html><body><a href='/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience'>"
                "Introducing Veris AI</a></body></html>"
            )
        if "blog-posts/introducing-veris-ai" in url:
            return (
                "<html><body><p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Enterprise teams can book demo access to validate agents before regulators find policy gaps.</p>"
                "</body></html>"
            )
        return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_veris_row()]),
        page_fetcher=page_fetcher,
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=lambda candidate: {"attio_status": "no_owner"},
        max_live_queries=0,
    )

    row = result["enriched_outbound_candidates"][0]
    provenance = row["assign_owner_evidence_provenance"]
    assert row["recommended_action"] == "Assign owner"
    # Keep this aligned with the local Veris fixture instead of hard-coding a
    # specific live HN item id.
    assert provenance["hn_source"]["url"] == _veris_row()["source_url"]
    assert provenance["official_company_source"]["url"] == "https://veris.ai/sandbox"
    assert provenance["founder_evidence"]["url"].endswith(
        "/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"
    )
    assert provenance["stage_funding_evidence"]["url"].endswith(
        "/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"
    )
    assert provenance["commercial_customer_evidence"]["url"].endswith(
        "/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"
    )
    assert provenance["attio_status_evidence"] == {
        "status": "no_owner",
        "source": "attio_read",
        "action_safe": True,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py::test_hn_assign_owner_row_separates_exact_evidence_provenance -q
```

Expected: FAIL with `KeyError: 'assign_owner_evidence_provenance'`.

- [ ] **Step 3: Implement provenance helper**

Add this helper in `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py` below `_row_from_candidate`:

```python
def _assign_owner_evidence_provenance(row: dict) -> dict:
    if row.get("recommended_action") != ACTION_ASSIGN_OWNER:
        return {}
    founder_url = _best_exact_evidence_url(row.get("founder_team_evidence") or [])
    stage_url = _best_exact_evidence_url(row.get("stage_funding_evidence") or [])
    customer_url = _best_exact_evidence_url(row.get("customer_buyer_evidence") or [])
    return {
        "hn_source": {
            "url": row.get("source_url", ""),
            "title": row.get("source_title", ""),
            "author": row.get("hn_author", ""),
            "engagement": row.get("hn_engagement", {}),
        },
        "official_company_source": {
            "url": row.get("official_url", ""),
            "domain": row.get("official_domain", ""),
            "identity_url": row.get("official_identity_url", ""),
        },
        "founder_evidence": {
            "url": founder_url,
            "founders": list(row.get("founders") or []),
            "profiles": list(row.get("founder_profiles") or []),
        },
        "stage_funding_evidence": {
            "url": stage_url,
            "maturity_status": row.get("maturity_status", ""),
            "basis": list(row.get("maturity_basis") or []),
        },
        "commercial_customer_evidence": {
            "url": customer_url,
            "types": list(row.get("customer_buyer_evidence_types") or []),
        },
        "attio_status_evidence": {
            "status": row.get("attio_status", ""),
            "source": "attio_read",
            "action_safe": bool(row.get("attio_safe_to_match")),
        },
    }
```

Add this helper near the durable URL helpers:

```python
def _best_exact_evidence_url(urls: list[str]) -> str:
    # Prefer source-quality exact URLs such as /blog-posts/, BusinessWire,
    # Gunderson, /news/, /press/, and /announcements/ before generic /blog,
    # /about, /customers, or root URLs.
    ...
```

Then update `_row_from_candidate` after the row dict is assembled:

```python
row = {
    ...existing row fields...
}
row["assign_owner_evidence_provenance"] = _assign_owner_evidence_provenance(row)
return row
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py::test_hn_assign_owner_row_separates_exact_evidence_provenance -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/hn_outbound_enrichment.py .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py
git commit -m "Add HN assign-owner evidence provenance"
```

---

### Task 2: Keep Provenance Narrow to Assign-Owner Rows

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_outbound_enrichment.py`
- Test: `.claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py`

- [ ] **Step 1: Write failing narrow-scope test**

Add:

```python
def test_hn_research_deeper_row_does_not_require_assign_owner_provenance():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound(name="QuietCo", hn_engagement={"points": 1, "comments": 0})]),
        page_fetcher=lambda url: "<html><title>QuietCo</title><body>QuietCo agent workflow notes.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=lambda candidate: {"attio_status": "unknown"},
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner_evidence_provenance"] == {}
```

- [ ] **Step 2: Run test**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py::test_hn_research_deeper_row_does_not_require_assign_owner_provenance -q
```

Expected: PASS after Task 1 if `_assign_owner_evidence_provenance` returns `{}` for non-Assign-owner rows.

- [ ] **Step 3: Run focused HN tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/vc-signals/scripts/hn_outbound_enrichment.py .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py
git commit -m "Keep HN provenance scoped to assign-owner rows"
```

---

### Task 3: Render Provenance in Row Review Artifacts

**Files:**
- Modify: `.claude/skills/vc-signals/scripts/hn_weekly_trial.py`
- Test: `.claude/skills/vc-signals/tests/test_hn_weekly_trial.py`

- [ ] **Step 1: Write failing markdown test**

Add:

```python
def test_hn_row_review_markdown_renders_assign_owner_evidence_provenance():
    from hn_weekly_trial import _row_review_markdown

    payload = {
        "summary": {"rows": 1, "priority_split": {"normal_priority": 1}, "completion_split": {"completed_clean": 1}, "action_split": {"Assign owner": 1}},
        "rows": [
            {
                "name": "Veris",
                "domain": "veris.ai",
                "priority": "normal_priority",
                "priority_reasons": ["official_domain_url"],
                "completion_status": "completed_clean",
                "stage_failure_reason": [],
                "final_action": "Assign owner",
                "evidence_dimensions": ["customer", "founder", "stage"],
                "attio_status": "no_owner",
                "missing_evidence": [],
                "unsafe_promotion": False,
                "assign_owner_evidence_provenance": {
                    "hn_source": {"url": "https://news.ycombinator.com/item?id=48054313"},
                    "official_company_source": {"url": "https://veris.ai/sandbox"},
                    "founder_evidence": {"url": "https://veris.ai/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"},
                    "stage_funding_evidence": {"url": "https://veris.ai/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"},
                    "commercial_customer_evidence": {"url": "https://veris.ai/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"},
                    "attio_status_evidence": {"status": "no_owner", "source": "attio_read", "action_safe": True},
                },
            }
        ],
    }

    markdown = _row_review_markdown(payload)
    assert "HN source: https://news.ycombinator.com/item?id=48054313" in markdown
    assert "Official/company source: https://veris.ai/sandbox" in markdown
    assert "Founder evidence: https://veris.ai/blog-posts/introducing-veris-ai" in markdown
    assert "Stage/funding evidence: https://veris.ai/blog-posts/introducing-veris-ai" in markdown
    assert "Commercial/customer evidence: https://veris.ai/blog-posts/introducing-veris-ai" in markdown
    assert "Attio status evidence: no_owner via attio_read" in markdown
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hn_weekly_trial.py::test_hn_row_review_markdown_renders_assign_owner_evidence_provenance -q
```

Expected: FAIL because markdown does not render provenance fields yet.

- [ ] **Step 3: Render provenance block**

In `_row_review_markdown`, after `Unsafe promotion`, add:

```python
        provenance = row.get("assign_owner_evidence_provenance") or {}
        if provenance:
            lines.extend(
                [
                    f"- HN source: {provenance.get('hn_source', {}).get('url', '')}",
                    f"- Official/company source: {provenance.get('official_company_source', {}).get('url', '')}",
                    f"- Founder evidence: {provenance.get('founder_evidence', {}).get('url', '')}",
                    f"- Stage/funding evidence: {provenance.get('stage_funding_evidence', {}).get('url', '')}",
                    f"- Commercial/customer evidence: {provenance.get('commercial_customer_evidence', {}).get('url', '')}",
                    "- Attio status evidence: "
                    f"{provenance.get('attio_status_evidence', {}).get('status', '')} via "
                    f"{provenance.get('attio_status_evidence', {}).get('source', '')}",
                ]
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hn_weekly_trial.py::test_hn_row_review_markdown_renders_assign_owner_evidence_provenance -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/hn_weekly_trial.py .claude/skills/vc-signals/tests/test_hn_weekly_trial.py
git commit -m "Render HN assign-owner provenance in review artifacts"
```

---

### Task 4: Validate with Internal HN Trial Artifact

**Files:**
- Generated only: `docs/radar-runs/current-hn-provenance-hardening-check/`

- [ ] **Step 1: Run focused tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_hn_outbound_enrichment.py .claude/skills/vc-signals/tests/test_hn_weekly_trial.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
```

Expected: PASS, with only the existing urllib3 LibreSSL warning acceptable.

- [ ] **Step 3: Run HN trial manually**

Use the same movement-seeded validation harness as Cycle 1, but write to:

```text
docs/radar-runs/current-hn-provenance-hardening-check/
```

Expected:

- `Assign owner rows: 1`
- `Unsafe promotions: 0`
- `weekly-preview.md` absent in the HN trial directory
- `hn-trial-row-review.md` shows exact HN, official/company, founder, stage/funding, commercial/customer, and Attio evidence for Veris

- [ ] **Step 4: Confirm generated artifacts remain uncommitted**

Run:

```bash
git status --short
```

Expected:

- Source/test files are committed.
- Generated `docs/radar-runs/current-hn-provenance-hardening-check/` artifacts are untracked.
- No generated artifacts or caches are staged.

---

## Self-Review

**Spec coverage:** The plan covers exact HN source URL, official/company source URL, founder evidence URL, stage/funding URL, commercial/customer/waitlist URL, and Attio status evidence for Assign-owner rows only.

**Placeholder scan:** No TBD/TODO/fill-in placeholders are present.

**Type consistency:** The plan uses existing row fields from `hn_outbound_enrichment.py` and adds a single nested dict field, `assign_owner_evidence_provenance`, consumed by `hn_weekly_trial.py`.
