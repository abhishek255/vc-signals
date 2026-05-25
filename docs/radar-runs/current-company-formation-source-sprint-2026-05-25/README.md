# Company-Formation Source Sprint - 2026-05-25

## Verdict

Product Hunt is now available as a narrow, optional company-formation source lane, but the locally available public feed is not enough to produce credible review-worthy company rows by itself.

The lane successfully extracts launch names, launch dates, Product Hunt URLs, taglines, outbound redirect URLs, and maker text when it is present in the launch title. In this environment, every Product Hunt outbound redirect resolution returned `403 Forbidden`, and no Product Hunt API token was configured, so the run could not verify official domains, founder/team evidence, stage/funding evidence, or customer/commercial evidence. The right outcome is to track the launches as weak Research Deeper signals and keep them out of owner routing.

## What Changed

- Added `.claude/skills/vc-signals/scripts/product_hunt_launches.py`, a public Atom-feed Product Hunt adapter.
- Added optional `--product-hunt-limit` / `--producthunt-limit` and Product Hunt timeout flags to `radar_run.py`.
- Kept Product Hunt disabled by default so existing weekly runs, HN behavior, Attio behavior, ranking thresholds, and Assign Owner gates are unchanged.
- Added Product Hunt source classification as `company-formation` with weak Research Deeper evidence strength.
- Prevented Product Hunt marketplace URLs from becoming fake candidate domains.
- Updated weekly source-gap wording so Product Hunt is no longer listed as a missing adapter when its source health shows the lane ran.

## Feasibility Check

Local checks found:

- `https://www.producthunt.com/feed` returns a usable Atom feed.
- `https://api.producthunt.com/v2/api/graphql` returns `401 invalid_oauth_token` without a token.
- Product Hunt web/product redirect resolution returned `403 Forbidden` locally.
- No Product Hunt token was present in the local environment or `~/.config/last30days/.env`.

This makes the feed useful for launch timing and product names, but not sufficient for official company identity without either API access or an approved redirect/domain resolver.

## Bounded Validation

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 .claude/skills/vc-signals/scripts/radar_run.py weekly \
  --output-dir docs/radar-runs/current-company-formation-source-sprint-2026-05-25/loop-2-product-hunt-source-gap-patch \
  --sectors all \
  --github-limit 0 \
  --product-hunt-limit 20 \
  --product-hunt-timeout-seconds 15 \
  --max-queries-per-sector 0 \
  --query-timeout-seconds 60 \
  --limit 20 \
  --discovery-budget-mode weekly \
  --max-runtime-seconds 420 \
  --max-company-discovery-queries 0 \
  --max-maturity-queries 0 \
  --max-article-fetches 0 \
  --max-results-per-query 0 \
  --per-movement-query-cap 0 \
  --hn-launch-max-candidates 5 \
  --hn-launch-max-runtime-seconds 300 \
  --hn-launch-max-attio-checks 5 \
  --hn-launch-max-live-queries 30 \
  --hn-launch-per-candidate-timeout-seconds 30 \
  --progress \
  --update-signal-ledger \
  --signal-ledger-path .claude/skills/vc-signals/data/radar_runs/company_signal_ledger.json
```

Results:

| Metric | GitHub-only baseline | Product Hunt isolated loop |
| --- | ---: | ---: |
| Fresh structured items | 30 GitHub items | 20 Product Hunt launches |
| Signals | 18 | 20 |
| Candidate-eligible signals | 18 | 20 |
| Candidates emitted | 18 OSS/project rows | 2 launch rows |
| Verified candidate domains | 3 | 0 |
| Founder/team evidence | 0 | 0 |
| Stage/funding evidence | 0 | 0 |
| Accepted company-discovery leads | 0 | 0 |
| Owner-ready rows | 0 | 0 |
| Unsafe promotions | 0 | 0 |

The two Product Hunt rows that survived candidate creation were:

- Runway Agent - Research Deeper, missing verified company identity, founder/team, stage/funding, and commercial evidence.
- Vibedock - Research Deeper, missing verified company identity, founder/team, stage/funding, and commercial evidence.

They are useful memory entries, not partner-ready company leads.

## Final Ledger And Packet

Generated from the updated ledger:

- `final-ledger-action-report/ledger-action-report.json`
- `final-partner-packet/partner-decision-packet.json`

Final packet summary:

- Entities: 66
- Sightings: 360
- Owner follow-up: 1, Voker
- Continue research: 3, 3D-Agent, Hypercubic, Runtime (YC P26)
- Category/context: 6, including Arize and Blackduck
- Stale/skipped rows: 53
- Unsafe promotions: 0

Product Hunt rows appear in the ledger action report as Research Deeper with next action `Verify official identity`. They are not promoted into owner follow-up.

## Decision

This sprint proves that Product Hunt feed-only sourcing is not enough locally for company-ready sourcing. The narrow hook should stay because it creates durable launch sightings and a safe future weekly path, but higher-yield company formation needs one of:

- Product Hunt API credentials with official website/maker fields.
- A permitted redirect resolver for Product Hunt outbound URLs.
- A different structured formation source with verified domains and founder/company metadata.

Until then, Product Hunt should remain optional and weak-signal only.
