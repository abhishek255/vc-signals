# PH/X Resolver And Coresignal Unlock Plan

## Goal

Improve weak-source conversion without loosening promotion gates:

- Product Hunt and X should extract official-domain candidates already present in text/link fields before using redirect or web fallback.
- Social/app-directory/news/repo URLs must remain evidence only, never official company domains.
- Coresignal should become a narrow direct structured-data trial when `CORESIGNAL_API_KEY` exists, using only rows that already have a domain.
- Completion requires tests plus a fresh validation run that compares PH/X conversion against the current baseline.

## Current Diagnosis

- Product Hunt already has API/feed ingestion, direct outbound handling, and web fallback, but `enrich_launch_domains` does not first inspect all row-level text/link/source URL fields.
- X already resolves URLs embedded in snippets, but ignores structured link fields before falling back to web resolver.
- Structured-provider trial detects Coresignal access but only uses an injected fake runner; live use still skips.
- The end goal is not more candidate rows. It is more strict Partner Review rows with official domains, founders/team evidence, commercial proof, and explicit gaps.

## Implementation Steps

1. Add failing resolver tests.
   - Product Hunt resolves from `source_outbound_urls` or text URLs before Product Hunt redirect.
   - X resolves from structured `links` or `outbound_links` before web fallback.
   - Blocked domains stay rejected.

2. Add failing Coresignal tests.
   - With `CORESIGNAL_API_KEY` and a target domain, the direct adapter calls the documented website enrich endpoint.
   - It normalizes website, LinkedIn/company profile, headcount, stage/funding-like fields, and founder-like fields where present.
   - With a key but no target domain, it skips safely instead of guessing.

3. Implement shared-enough resolver behavior inside existing adapters.
   - Keep changes scoped to current PH/X modules unless duplication becomes harmful.
   - Prefer deterministic extraction and verification over LLM “vibes.”

4. Implement Coresignal direct adapter.
   - Endpoint: clean company enrich by website URL.
   - Auth: `apikey` header.
   - Gate live calls by `CORESIGNAL_API_KEY` and existing target domain only.
   - Preserve manual-mode fallback when no key exists.

5. Verify.
   - Run focused PH/X/Coresignal tests.
   - Run full vc-signals test suite.
   - Run a fresh PH/X-focused validation and compare PH/X resolved counts, Partner Review rows, strict Review-Worthy rows, Market Signals, Evidence Gap rows, and unsafe promotions.
