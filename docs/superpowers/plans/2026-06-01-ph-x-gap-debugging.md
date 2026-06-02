# Product Hunt, X, And Evidence Gap Debugging Sprint

## Goal

Run a focused source-yield debugging sprint without Coresignal. The work is complete only when Product Hunt unresolved launches are audited, X access is proven or clearly marked unavailable, Evidence Gap Queue rows tell Alex exactly what to check next, and focused tests plus a small validation artifact prove the state.

## Scope Guardrails

- Do not change scoring thresholds in this sprint.
- Do not run Coresignal or any structured-provider trial.
- Do not run another broad weekly/deep validation until Product Hunt and X are debugged in smaller controlled steps.
- Keep Assign Owner strict and preserve unsafe promotions at zero.
- Treat Product Hunt and X as signal sources. They can start evidence work, but they cannot promote rows without official company identity and proof.

## Tasks

1. Add a source-debug audit script.
   - Input: an existing run directory.
   - Read raw Product Hunt rows, validation report, runtime ledger/source health, and Evidence Gap Queue.
   - Classify unresolved Product Hunt failures:
     - Product Hunt redirect blocked by 403.
     - web resolver timeout.
     - web resolver found no verified official domain.
     - missing row-level URL fields.
   - Emit per-launch manual resolver queries and the fields Product Hunt actually provided.
   - Summarize X source health and whether it returned rows, errors, warnings, or only empty output.
   - Flag Evidence Gap rows that are missing recommended manual checks.
   - Write JSON and Markdown artifacts into the run directory.

2. Add a focused X proof mode.
   - Use one known-good launch-style movement query through the existing `x_launches` lane.
   - Cap it tightly with one query, a short timeout, and no broad domain-resolution crawl.
   - Record whether credentials are present, whether last30days returns X items, and whether rows normalize into launch candidates.
   - Do not print or store secrets.

3. Make Evidence Gap Queue operational.
   - Add `recommended_manual_check` to each raw Evidence Gap row.
   - Add `recommended_next_step` to each raw Evidence Gap row.
   - Add `manual_work_required`, `promote_if`, `discard_if`, and `likely_payoff` so the queue is useful before manual enrichment.
   - Keep the existing `manual_evidence_queue` compatible.

4. Add targeted tests.
   - Test Product Hunt unresolved audit classification.
   - Test X empty/unavailable source-health audit behavior.
   - Test Evidence Gap rows include recommended manual next steps.
   - Test the audit script catches gap rows that are still missing manual-check fields.

5. Run focused validation.
   - Run the targeted tests first.
   - Run the audit script against `docs/radar-runs/ph-x-resolver-coresignal-validation-2026-06-01-r5`.
   - Run the X proof mode once with a short timeout.
   - Regenerate the source-yield validation report for r5 after the Evidence Gap Queue surface fix.
   - Run the full vc-signals test suite.

## Done Criteria

- `source-debug-audit.json` and `source-debug-audit.md` exist in the r5 run directory.
- The audit explains why each unresolved Product Hunt row failed and gives a specific manual resolver query.
- The audit records X as working, empty, or unavailable based on a live proof attempt.
- Evidence Gap Queue rows include recommended manual check fields directly, not only in the derived manual queue.
- Focused tests and the full vc-signals tests pass.
- Source-yield validation still reports zero unsafe promotions.
