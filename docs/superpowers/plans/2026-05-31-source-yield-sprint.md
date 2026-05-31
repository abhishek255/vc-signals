# Source Yield Sprint

## Goal

Turn the current safe-but-thin weekly radar into a better Review-Worthy lead engine without lowering the Assign Owner gate.

## Current Truth

- The system already protects against unsafe owner promotion better than it finds enough credible leads.
- Product Hunt public feed and Reddit role safeguards exist, but they need to be represented honestly in source health and candidate routing.
- YC existed as search-query evidence only; it did not have a direct public directory adapter.
- X and LinkedIn access are not available through current Codex connectors. X can run only when last30days has `XAI_API_KEY` or `AUTH_TOKEN` plus `CT0`.
- Crunchbase, PitchBook, Coresignal, People Data Labs, Dealroom, Apollo, and Clay are not configured locally unless source-access detection finds keys.
- Generated run artifacts are too spread out; `docs/radar-runs/current/` should become the blessed pointer.

## Implementation Plan

1. Add focused tests for YC directory normalization, X credential gating, LinkedIn/manual enrichment targets, enrichment provider access detection, source classification, and blessed-current manifest shape.
2. Add a public YC directory adapter using `https://yc-oss.github.io/api/companies/all.json`.
3. Add a credential-gated X launch lane through last30days query runner.
4. Keep LinkedIn as a manual/high-value enrichment target only; do not scrape or invent LinkedIn data.
5. Keep Reddit as pain/corroboration evidence only.
6. Wire YC and X evidence into `radar_run.py` as Research Deeper candidates, not Assign Owner defaults.
7. Write `manual-enrichment-targets.json` and source-access diagnostics during weekly runs.
8. Create one blessed current run folder with `README.md`, `partner-decision-packet.json`, `ledger-action-report.json`, and `run-manifest.json`.
9. Run focused tests, then the full vc-signals test suite, then a bounded validation run with Product Hunt, YC, and X enabled.

## Definition Of Done

- Focused source tests pass.
- Full vc-signals test suite passes.
- Bounded validation run reports source health for Product Hunt, YC, X, and enrichment-provider access.
- Unsafe promotions remain 0.
- Final report separates actual Review-Worthy yield from missing external provider credentials.

