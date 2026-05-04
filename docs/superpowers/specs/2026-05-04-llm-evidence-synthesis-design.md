# LLM Evidence Synthesis Design

## Goal

Add an optional LLM synthesis layer to VC Signals that helps Marathon find real companies and sharper themes from messy multi-source evidence, without losing the current auditability and skepticism of the deterministic radar.

The product principle is:

> Let the LLM reason across evidence, but never let it invent evidence.

This phase should improve the weekly radar's ability to answer:

1. Which non-OSS companies might be emerging from weak or fragmented evidence?
2. Which themes are real buyer/operator pain versus generic activity?
3. Which sectors are quiet because the market is quiet versus because source coverage failed?
4. What should a partner or associate investigate next?

## Context

Radar V3 made the artifact more honest and useful:

- Market Sector and Source Lane are separate.
- OSS projects are reclassified into investment sectors.
- Partner Review is priority-ranked.
- Sector Intelligence explains source gaps.
- Weak non-company signal is not inflated into fake rows.

The remaining gap is source synthesis. Captured V3 output is still OSS-heavy because grounded company discovery, social/video demos, HN launches, and Reddit pain did not produce enough structured company evidence. Deterministic rules correctly avoided weak rows, but they are not smart enough to connect fragmented evidence into high-quality follow-up hypotheses.

## Scope

Included:

- Optional synthesis mode for weekly radar, gated by `--with-synthesis`.
- A new `synthesis.json` artifact.
- LLM-generated theme clusters, possible company leads, source-gap diagnosis, and follow-up searches.
- Guardrails requiring citations and source evidence for every claim.
- Renderer support for a compact "LLM Synthesis Notes" section.
- Tests using deterministic/fake LLM responses.
- A/B validation against captured evidence.

Excluded:

- Making LLM synthesis default immediately.
- Letting LLM suggestions directly bypass candidate promotion rules.
- Writing to Attio.
- Slack delivery.
- Deep IC memos for every company.
- Uncited funding, headcount, founder, customer, or stage claims.

## Operating Mode

LLM synthesis starts as an explicit weekly option:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly \
  --sectors all \
  --output-dir docs/radar-runs/marathon-weekly-v4-synthesis \
  --with-synthesis
```

The default weekly command remains deterministic until the synthesis layer proves it improves Marathon-quality output without hallucination.

## Inputs

The synthesis layer consumes the existing artifact contract:

- `raw-evidence.json` or `<date>-raw-evidence.json`
- `signals.json`
- `candidates.json`
- `sector-intelligence.json`
- `theme-signals.json`

The runtime function should accept in-memory objects as well, so tests do not need filesystem setup.

## Outputs

Add `synthesis.json`:

```json
{
  "enabled": true,
  "model": "gpt-4.1-mini",
  "generated_at": "2026-05-04T12:00:00Z",
  "source_digest": {
    "candidate_count": 50,
    "signal_count": 102,
    "source_lanes": {"OSS": 50},
    "market_sectors": {"Cybersecurity": 18, "Devtools": 20}
  },
  "sector_diagnoses": [
    {
      "market_sector": "Vertical AI",
      "diagnosis": "Source failure / incomplete coverage",
      "evidence_urls": [],
      "recommended_next_queries": [
        "vertical AI workflow automation startup launch",
        "AI front office automation seed startup"
      ],
      "confidence": "High"
    }
  ],
  "theme_hypotheses": [
    {
      "market_sector": "Cybersecurity",
      "theme": "AI agent permission security",
      "evidence_summary": "Operators and OSS projects point to MCP/tool permission risk.",
      "evidence_urls": [
        "https://github.com/affaan-m/agentshield"
      ],
      "why_it_matters": "Agent adoption creates new security review and runtime permission surfaces.",
      "why_this_may_be_noise": "Current evidence is mostly OSS and may not map to budgeted buyer urgency.",
      "confidence": "Medium"
    }
  ],
  "possible_company_leads": [
    {
      "name": "AgentShield",
      "market_sector": "Cybersecurity",
      "source_lane": "OSS",
      "domain": "",
      "evidence_urls": [
        "https://github.com/affaan-m/agentshield"
      ],
      "why_on_radar": "Fast OSS momentum around AI agent security and MCP permissions.",
      "verification_needed": [
        "Confirm maintainer identity",
        "Check whether this is a company or project",
        "Search for customer/funding/founder evidence"
      ],
      "suggested_action": "track company formation",
      "confidence": "Medium"
    }
  ],
  "partner_notes": [
    "The run is OSS-heavy because grounded company discovery is unavailable.",
    "Security signal is stronger than vertical AI signal in this captured run."
  ],
  "warnings": []
}
```

## Data Model

Add new dataclasses in `radar_models.py` or a focused synthesis module:

- `SynthesisResult`
- `SectorDiagnosis`
- `ThemeHypothesis`
- `PossibleCompanyLead`

Each model must support `to_dict()` and `from_dict()` and tolerate older/extra fields.

## Provider Strategy

Use OpenAI first because the user has configured an OpenAI key and the repo should avoid OpenRouter for this phase.

Provider behavior:

- If `OPENAI_API_KEY` is present, use OpenAI structured JSON output.
- If no provider key is present, skip synthesis and write `synthesis.json` with `enabled: false` and a warning.
- Do not fail the weekly run just because synthesis fails.
- Do not log API keys.

Default model should be configurable via environment:

- `VC_SIGNALS_SYNTHESIS_MODEL`
- Default: a cost-conscious structured-output capable model.

## Prompt Contract

The system prompt should frame the LLM as a skeptical VC research analyst for Marathon Management Partners.

Required behavior:

- Separate facts, inferences, assumptions, and open questions.
- Use only supplied evidence.
- Cite evidence URLs for every theme or possible company lead.
- Do not invent company domains, funding, headcount, stage, founders, customers, or LinkedIn URLs.
- Prefer "needs verification" over confident claims when evidence is weak.
- Penalize generic activity, tutorials, jobs, bounties, PR chores, resume reviews, and broad news digests.
- Keep output concise enough for a weekly radar.

The prompt should include the current Marathon assumptions:

- Seed to Series B.
- Label likely-too-late companies rather than hiding them.
- Attio context matters but no writeback in this phase.
- Partner Review should surface what a partner should inspect first.

## Promotion Rules

LLM suggestions do not automatically become final candidates.

A `possible_company_lead` can be promoted into `candidates.json` only if it has:

- at least one evidence URL,
- an extractable company/project name,
- a clear evidence role,
- and one of:
  - domain,
  - credible company/launch page,
  - funding/news evidence,
  - founder/company account,
  - product demo with corroboration,
  - OSS project with company-formation potential.

If these conditions are not met, the lead remains in `synthesis.json` and may render as "Possible Companies Requiring Verification".

## Rendering

Add an optional section to `weekly-preview.md` when synthesis is enabled:

```markdown
## LLM Synthesis Notes

- This run is OSS-heavy because grounded company discovery is unavailable.
- Cybersecurity shows repeated AI agent permission/security signal.

### Possible Companies Requiring Verification

| Name | Market Sector | Evidence | Suggested Action | Verification Needed |
|---|---|---|---|---|
```

Do not let this section replace Partner Review or Full Radar. It is a research-assistant layer, not the canonical candidate table.

## Error Handling

- Invalid JSON from the LLM should produce a warning and no promoted synthesis.
- Missing citations should cause that item to be dropped.
- Items referencing unknown URLs should be dropped or marked invalid.
- Provider timeout should not fail the weekly artifact.
- The artifact should say "LLM synthesis unavailable" when skipped.

## Testing Strategy

Add tests for:

- Model roundtrips.
- Provider unavailable path writes disabled synthesis.
- Fake LLM valid response produces `synthesis.json`.
- Fake LLM uncited claims are dropped.
- Fake LLM hallucinated domain/funding/headcount is not merged into candidate fields.
- Possible company leads remain separate unless promotion criteria are met.
- Renderer includes LLM Synthesis Notes only when synthesis is enabled.
- Captured evidence A/B run produces deterministic artifact plus synthesis artifact.

Tests must not call the real OpenAI API.

## Verification Checkpoints

### Checkpoint A: Synthesis Contract

Run:

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

### Checkpoint B: Weekly Integration

Run:

```bash
python3 -m pytest \
  .claude/skills/vc-signals/tests/test_radar_run.py \
  .claude/skills/vc-signals/tests/test_radar_render.py \
  -q
```

Expected:

- `--with-synthesis` writes `synthesis.json`.
- Default weekly output remains deterministic.
- Renderer includes synthesis notes only when available.

### Checkpoint C: Captured A/B Artifact

Run captured evidence twice:

- deterministic V3,
- V3 with fake synthesis.

Expected:

- Deterministic artifacts remain unchanged unless synthesis is explicitly enabled.
- Synthesis artifact identifies source gaps and possible leads with citations.
- No hallucinated funding/headcount/founder fields appear.

### Checkpoint D: Final Quality

Run:

```bash
python3 -m pytest .claude/skills/vc-signals/tests -q
git diff --check
rg -n "ATTIO_ACCESS_TOKEN='|Bearer [A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|sk-or-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|fwKR[A-Za-z0-9_-]{10,}" . --glob '!vendor/**' --glob '!.git/**' --glob '!docs/superpowers/plans/**' --glob '!docs/superpowers/specs/**'
```

Expected:

- Full test suite passes.
- No whitespace errors.
- Secret scan has no matches outside the docs that define the scan itself.

## Success Criteria

This phase is successful when:

1. The weekly run can produce `synthesis.json` behind `--with-synthesis`.
2. The LLM explains why an OSS-heavy run happened.
3. The LLM suggests better follow-up searches by sector.
4. Possible company leads are cited and kept separate unless promotion criteria are met.
5. No uncited or hallucinated enrichment enters `candidates.json`.
6. A partner can read the synthesis notes and know what to investigate next.

## Rollout Decision

Do not enable synthesis by default until at least three captured or live weekly runs show:

- better non-OSS company discovery,
- no material hallucinations,
- useful partner notes,
- and no degradation in Partner Review trust.

Until then, synthesis remains opt-in.
