# Blessed Current Radar Run

This folder is the small, current-state pointer for the radar. It does not delete older experiment folders; it tells us which artifacts to trust first.

- Source run: `docs/radar-runs/full-source-dossier-validation-2026-06-01-r1`
- Generated at: `2026-06-02T02:15:51.936301+00:00`
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
- `evidence-completion-repeatability-report.md`
- `evidence-completion-repeatability-report.json`

## Sanity Check

The 8 Product Hunt-sourced Review-Worthy rows were manually click-checked after the run.

- 8 / 8 official domains loaded.
- 8 / 8 have a real product surface.
- 6 / 8 look reasonably strong for Partner Review.
- 2 / 8 need extra identity caution because of noisy name-collision evidence.
- 0 / 8 should be promoted to Assign Owner without founder/team and stage/headcount/funding checks.

Older `docs/radar-runs/current-*` folders are historical experiments unless this manifest points at them.

## June 2 Repeatability Check

The June 2 evidence-completion sprint compared two bounded safe weekly runs and one broader safe weekly run. It did **not** replace the blessed partner packet because repeatability against the strict Review-Worthy Company target is not proven yet.

- Best broader run: 0 Assign Owner, 14 Partner Review companies, 1 strict Review-Worthy Company, 5 market signals, 12 evidence gaps, 0 unsafe promotions.
- Product Hunt hard evidence in the broader run: 15 rows investigated, 8 official domains resolved.
- X in the broader run: 2 launch rows, 0 official domains resolved.
- Manual enrichment: 12 top gaps enriched, 24 focused public-search queries, 144 items, 0 errors.

Decision: public/manual sources are useful for Partner Review, Market Signals, and Evidence Gap Queue rows, but not yet enough for repeatable 8-15 strict Review-Worthy Companies without stronger PH/X resolution or structured company metadata.
