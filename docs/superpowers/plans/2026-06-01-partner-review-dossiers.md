# Partner Review Dossier Sprint

## Goal

Make the packet useful for partner review before automation is perfect. The pipeline should separate strict owner-ready rows from good/decent companies worth review, explicit manual evidence gaps, and market signals that reveal where to search next.

## Product Shape

- Keep `Assign Owner` strict. Do not relax the weekly owner gate.
- Add `Partner Review Companies`: company rows with enough official identity, operator, product, or commercial evidence to deserve analyst review, even when stage/funding/headcount still needs manual confirmation.
- Keep `Review-Worthy Companies` as the stricter evidence-cleared tier.
- Keep `Manual Evidence Queue`: top blocked rows with the exact missing field, suggested source, promote-if/discard-if guidance, and likely payoff.
- Keep `Review-Worthy Market Signals`: OSS and theme movement that should guide company discovery.

## Implementation Steps

1. Add a reusable company dossier layer that grades identity, founder/operator, product, commercial, structured metadata, social confidence, risk flags, missing evidence, and manual checks.
2. Wire dossiers into source-yield validation, decision packet, markdown, and ledger action report.
3. Add official-site evidence crawling helpers for about/team, pricing, docs, customers, careers, and blog pages, without treating social/directory pages as official domains.
4. Add a Coresignal-ready structured provider path that can use direct access when configured and otherwise remains honest manual-mode.
5. Verify with focused tests, then a fresh validation run.

## Completion Bar

- Tests prove Partner Review and Manual Evidence Queue exist in report and packet surfaces.
- Tests prove the dossier layer does not invent facts and gives a confidence grade.
- Tests prove official-site page classification feeds product/commercial/founder evidence.
- Tests prove structured-provider direct access can be used through an injectable provider adapter while manual mode remains honest.
- Fresh validation is generated and compared to the current blessed run.
