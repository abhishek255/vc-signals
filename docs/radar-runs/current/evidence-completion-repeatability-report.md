# Evidence Completion Repeatability Report - 2026-06-02

This is a diagnostic report, not a replacement for the blessed current partner packet.

The current blessed packet remains `docs/radar-runs/full-source-dossier-validation-2026-06-01-r1` because it is the strongest partner-facing packet shape. The June 2 repeatability sprint tested whether that quality repeats under safe weekly settings.

The diagnostic run directories were generated locally for this sprint and are summarized here instead of being kept as another blessed artifact surface.

## Result

Repeatability is not proven yet.

The system is conservative and trustworthy: unsafe promotions stayed at 0. It can repeatedly produce a Partner Review queue, Market Signals, and Evidence Gap Queue rows. It does not yet repeatedly produce 8-15 strict Review-Worthy Companies from public/manual sources.

## Runs Compared

| Run | Mode | Assign Owner | Partner Review | Review-Worthy Companies | Market Signals | Evidence Gaps | Unsafe |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `evidence-completion-safe-bounded-fast-2026-06-02-r1` | bounded safe weekly | 0 | 17 | 1 | 5 | 12 | 0 |
| `evidence-completion-safe-bounded-fast-2026-06-02-r2` | bounded safe weekly | 0 | 17 | 1 | 5 | 12 | 0 |
| `evidence-completion-safe-weekly-2026-06-02-r4` | broader safe weekly | 0 | 14 | 1 | 5 | 12 | 0 |

## Source Yield

- Product Hunt improved as a launch/domain source, but not enough for the final bar.
- In the broader r4 run, Product Hunt returned 20 launches; hard evidence investigated 15 and resolved 8 official domains.
- X returned 2 launch/social rows in r4, but resolved 0 official domains.
- GitHub produced strong OSS market-radar rows. It should stay split between company candidates and market signals rather than being forced into company rows.
- Focused manual enrichment ran on 12 top gaps in r4: 24 queries, 144 public-search items, 0 errors, about `$0.014` incremental paid-search spend due cache hits.

## Cost And Reliability

- r4 weekly paid-search spend: about `$0.394`.
- Broad last30days grounding stayed disabled.
- The first broader validation attempt stalled before final artifacts. The fix added a signal-investigation runtime cap so weekly runs finish and record partial investigation instead of quietly waiting too long.

## Decision

Public/manual sources are currently good enough for:

- Partner Review queue
- Review-Worthy Market Signals
- Evidence Gap Queue
- conservative gatekeeping with 0 unsafe promotions

Public/manual sources are not yet good enough for:

- repeatable 8-15 strict Review-Worthy Companies
- reliable founder/stage/funding/headcount fill
- reliable X official-domain/company-identity resolution

## Recommendation

Next work should focus on source yield, not scoring:

- improve Product Hunt official-domain and founder/company resolution
- make X a bounded launch radar with stronger URL/domain extraction
- keep GitHub as market radar first
- keep manual enrichment targeted to the top 10-15 gaps
- use a small structured metadata trial only if the strict Review-Worthy Company target must be hit repeatably
