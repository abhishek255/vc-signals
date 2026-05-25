# Identity/Evidence Unlock Sprint - 2026-05-25

## Verdict

The sprint added a narrow, optional weak-source identity enrichment path for Product Hunt and GitHub rows, but the current local no-secret environment still cannot turn weak Product Hunt/GitHub rows into 2-3 new credible review-worthy companies.

The new hook is useful: it queries exact official-identity searches for weak rows, writes a per-run enrichment report, and lets resolved domains flow through the existing identity, founder/team, maturity, and owner-evidence gates. It does not change Assign Owner thresholds, ranking gates, HN behavior, or Attio writeback behavior.

The validation result is a provider/credential limitation rather than a routing failure:

- Product Hunt API credentials were unavailable, and unauthenticated GraphQL returned `401 Unauthorized`.
- Product Hunt feed rows still had public redirect resolution blocked with `403 Forbidden`.
- Exact weak-row identity searches resolved only Runway Agent to `runwayml.com`; existing maturity/context gates correctly kept it Monitor only.
- Vibedock remained unresolved because the available evidence was only the Product Hunt marketplace page.
- GitHub weak-row searches did not resolve official company identity beyond rows that were already project/domain watch rows.
- Entro Security was the only new company to land in Continue Research, but it still lacks founder/team, stage/funding, and strong customer/buyer evidence.

Safety held:

- Voker remains the only Assign Owner.
- Unsafe promotions remain 0.
- Weak Product Hunt/GitHub rows were not promoted unless they cleared existing evidence gates.
- Mature/context rows such as Runway Agent, LangChain, and Temporal stayed out of owner flow.

## What Changed

- Added `.claude/skills/vc-signals/scripts/weak_source_identity_enrichment.py`.
- Added optional weekly flags:
  - `--weak-source-identity-enrichment-limit`
  - `--weak-identity-enrichment-limit`
  - `--weak-source-identity-limit`
- Kept the feature disabled by default with limit `0`.
- Added `weak-source-identity-enrichment.json` as a per-run report artifact.
- Ran weak-source identity enrichment after candidate enrichment and before weekly-focus preparation so downstream gates recompute from any resolved domains.
- Prioritized Product Hunt weak rows within the bounded enrichment budget so Product Hunt does not get starved by GitHub project rows.

## Validation

Baseline was the Product Hunt sprint final packet:

- Artifact: `docs/radar-runs/current-company-formation-source-sprint-2026-05-25/README.md`
- Final packet: `docs/radar-runs/current-company-formation-source-sprint-2026-05-25/final-partner-packet/partner-decision-packet.json`
- Entities: 66
- Sightings: 360
- Owner follow-up: 1, Voker
- Continue Research: 3
- Stale/skipped rows: 53
- Unsafe promotions: 0

### Loop 1: First Weak-Identity Run

Artifact:

- `docs/radar-runs/current-identity-evidence-unlock-sprint-2026-05-25/loop-1-weak-source-enrichment/`

Result:

- GitHub items: 30
- Product Hunt launches: 20
- Weak identity queries: 8
- Domains resolved: 0
- Unsafe promotions: 0

Learning:

- The enrichment hook worked, but the first budget allocation spent all weak identity queries on GitHub OSS/project rows before reaching Product Hunt.

### Loop 2: Product Hunt Prioritized

Artifact:

- `docs/radar-runs/current-identity-evidence-unlock-sprint-2026-05-25/loop-2-prioritized-weak-source-enrichment/`

Result:

- GitHub items: 30
- Product Hunt launches: 20
- Weak identity queries: 8
- Domains resolved: 1
- Product Hunt resolved domain: Runway Agent -> `runwayml.com`
- Product Hunt unresolved row: Vibedock
- Owner-ready rows in the live run: 0
- Unsafe promotions: 0

Learning:

- Product Hunt weak rows need explicit priority in the limited identity budget.
- The only resolved Product Hunt row was a mature/context row and was correctly kept out of owner routing.

### Loop 3: Broader Bounded Evidence Run

Artifact:

- `docs/radar-runs/current-identity-evidence-unlock-sprint-2026-05-25/loop-3-broader-bounded-evidence/`

Result:

| Metric | Result |
| --- | ---: |
| GitHub items | 30 |
| Product Hunt launches | 20 |
| Weak identity queries | 12 |
| Weak domains resolved | 1 |
| Company discovery queries | 8 |
| Provider items seen | 40 |
| Company discovery accepted leads | 3 |
| Verified candidate domains in run | 6 |
| New credible Continue Research companies | 1 |
| Founder/team evidence found for new rows | 0 |
| Stage/funding evidence found for new rows | 0 |
| Strong customer/commercial evidence found for new rows | 0 |
| Owner-ready rows in the live run | 0 |
| Unsafe promotions | 0 |

Accepted company-discovery leads:

- Entro Security, `entro.security` - Research Deeper, still missing founder/team, stage/funding, and customer/buyer pull evidence.
- LangChain, `langchain.com` - Monitor only/acquired, context only.
- Durable Execution Solutions, `temporal.io` - later categorized as likely too late/context.

Weak-source enrichment:

- Runway Agent resolved to `runwayml.com`, then stayed Monitor only / Category Context.
- Vibedock remained unresolved because only the Product Hunt marketplace page was available.
- OSS rows remained project/company-formation watch unless they already had a project homepage; they did not become Attio-safe company identities.

Evidence completion:

- Founder/team verification had 1 eligible new company and found 0 founders.
- Owner evidence had 1 eligible new company and found no owner-complete row.
- Entro Security reached owner readiness score 45 with missing evidence: founder/team, stage/funding, and customer/buyer pull.

## Final Ledger And Packet

Generated after Loop 3:

- `final-ledger-action-report/ledger-action-report.json`
- `final-partner-packet/partner-decision-packet.json`

Final packet summary:

- Entities: 67
- Sightings: 484
- Owner follow-up: 1, Voker
- Continue Research: 3, Hypercubic, Runtime (YC P26), Entro Security
- Category/project/context: 25
- Stale/skipped rows: 35
- Unsafe promotions: 0

Owner follow-up:

- Voker, `voker.ai` - Assign Owner, no missing evidence.

Continue Research:

- Hypercubic, `hypercubic.ai` - missing founder/team, stage/funding, commercial/funding evidence, Attio status, and maturity completion.
- Runtime (YC P26), `runtm.com` - missing founder/team, stage/funding, Attio status, and maturity completion.
- Entro Security, `entro.security` - missing founder/team, stage/funding, and customer/buyer pull evidence.

## Decision

Keep the weak-source identity enrichment hook as an optional weekly input because it preserves memory and gives weak rows a safe path into existing evidence gates. Do not turn it on by default yet.

The next unlock is not another routing or threshold change. It needs a source/provider that can reliably provide official company domains and founder/stage metadata for Product Hunt/GitHub weak rows:

- Product Hunt API credentials with website and maker fields.
- A permitted Product Hunt redirect/domain resolver.
- A structured company/provider source with official-domain, founder/team, funding/stage, and customer/commercial metadata.

Until then, weak Product Hunt and GitHub rows should remain Research Deeper, OSS Watch, or Category Context memory entries, not owner-ready leads.
