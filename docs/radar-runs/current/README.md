# Blessed Current Radar Run

This folder is the small, current-state pointer for the radar. It does not delete older experiment folders; it tells us which artifacts to trust first.

- Source run: `docs/radar-runs/full-source-dossier-validation-2026-06-01-r1`
- Generated at: `2026-06-02T01:29:18.416372+00:00`
- Decision packet rows: 9
- Assign Owner rows: 1
- Unsafe promotion policy: unchanged_high_confidence_only

## Files

- `partner-decision-packet.json`
- `ledger-action-report.json`
- `run-manifest.json`
- `source-yield-validation-report.json`
- `source-yield-validation-report.md`
- `source-yield-repeatability-report.json`
- `source-yield-repeatability-report.md`
- `targeted-manual-enrichment.json`
- `structured-provider-trial.json`
- `review-worthy-sanity-check.md`

## Sanity Check

The 8 Product Hunt-sourced Review-Worthy rows were manually click-checked after the run.

- 8 / 8 official domains loaded.
- 8 / 8 have a real product surface.
- 6 / 8 look reasonably strong for Partner Review.
- 2 / 8 need extra identity caution because of noisy name-collision evidence.
- 0 / 8 should be promoted to Assign Owner without founder/team and stage/headcount/funding checks.

Older `docs/radar-runs/current-*` folders are historical experiments unless this manifest points at them.
