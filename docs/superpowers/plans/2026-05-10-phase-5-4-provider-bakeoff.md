# Phase 5.4: Provider Bakeoff For Corrected Weekly Trial Harness

## Goal

Compare grounded search providers against the same corrected Phase 5.3 weekly-trial query set, without changing default weekly behavior.

The question is narrow:

> Does another provider, especially You.com, materially improve verified research-worthy or early-stage company yield for the same weekly trial families?

## Non-Goals

- Do not graduate query families into default weekly discovery.
- Do not add X, LinkedIn, Product Hunt, package registries, Slack, or Attio writeback.
- Do not loosen identity, source-authority, maturity, owner-readiness, Attio, or canonical-name gates.
- Do not use synthesized answer text as evidence.
- Do not change `weekly-preview.md`.

## Inputs

Use a completed weekly trial run directory, preferably:

```bash
docs/radar-runs/current-phase5-3-1-controlled-weekly-trial-full-v2
```

Load the trial queries from `company-discovery.json` where:

```text
discovery_lane == discovery_yield_trial
```

If a run has no trial queries, the bakeoff should fail closed with a warning, not invent broad queries.

## Providers

Required:

- `brave`
- `you`

Optional:

- `perplexity_search`, raw search results only

Provider credentials are loaded through existing provider env handling:

- Brave: `BRAVE_API_KEY`
- You.com: `YOU_API_KEY` or `YDC_API_KEY`
- Perplexity raw search: `PERPLEXITY_API_KEY`

## Query Families

Only compare the corrected weekly-trial families:

- `official_company_page`
- `founder_company_pages`
- `movement_platform`

Do not include:

- `movement_startup`
- `yc_company_pages`
- `seed_funding`
- `launch_stealth`
- `company_context`

## Execution

For every provider:

1. Run the exact same trial query list.
2. Cache provider results by provider and query.
3. Normalize result items into the existing provider item shape.
4. Run each item through `verify_discovery_item`.
5. For accepted leads, run exact-name maturity verification through the same provider.
6. Apply maturity routing.
7. Record provider-level and provider/family metrics.

This is an eval/trial artifact only. It should not write weekly artifacts or mutate the default weekly pipeline.

## Metrics

Per provider:

- queries planned
- queries run
- skipped queries
- cache hits
- live calls
- provider items seen
- verified domains
- verified domain list
- maturity-confirmed early-stage rows
- research-worthy unknown rows
- category anchors / monitor-only rows
- sourcing candidates
- Assign owner rows
- unsafe promotions
- accepted leads
- rejected leads
- rejection reasons
- junk/source-authority rejection rate
- latency
- cost

Per provider + query family:

- queries run
- verified domains
- maturity-confirmed early-stage rows
- research-worthy unknown rows
- category anchors
- accepted / rejected

## Tests First

Add tests for:

1. Loading trial queries from a weekly run filters only `discovery_yield_trial`.
2. Provider bakeoff runs the same query set for Brave and You.com.
3. Provider metrics are separated and unique-domain based.
4. A You.com-only verified official domain can improve research-worthy yield without affecting Brave metrics.
5. Mature/category evidence does not count as early-stage.
6. Missing provider keys / skipped provider are represented without failing the bakeoff.
7. Artifact writer creates `weekly-trial-provider-bakeoff.json` and summary markdown without touching `weekly-preview.md`.

## Validation Run

After implementation:

```bash
python3 .claude/skills/vc-signals/scripts/discovery_trial_provider_bakeoff.py \
  --weekly-run-dir docs/radar-runs/current-phase5-3-1-controlled-weekly-trial-full-v2 \
  --output-dir docs/radar-runs/current-phase5-4-provider-bakeoff-smoke \
  --providers brave,you \
  --max-results-per-query 10 \
  --max-runtime-seconds 900
```

If You.com credentials are unavailable, the artifact should show You.com as skipped with `missing_api_key`.

## Definition Of Done

- Full tests pass.
- Provider bakeoff artifact is written.
- `weekly-preview.md` is unchanged.
- Generated artifacts and provider caches remain uncommitted.
- Code/tests/plan are committed.
- Final report includes:
  - provider summary
  - query family summary
  - verified domains
  - early-stage confirmed rows
  - research-worthy unknown rows
  - category/monitor rows
  - false positives / unsafe promotions
  - junk rate
  - recommendation on whether You.com should stay in trial
