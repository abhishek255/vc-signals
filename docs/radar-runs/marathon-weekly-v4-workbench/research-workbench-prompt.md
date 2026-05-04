# VC Signals Research Workbench

Use your own LLM reasoning to synthesize the supplied evidence into a research workbench. This is a verification artifact, not the canonical weekly radar.

## Hard Rules

- Do not add rows to candidates.json.
- Do not claim a company, domain, funding, headcount, founder, customer, or stage unless it appears in supplied evidence.
- Treat possible company names as leads requiring verification unless they already have a credible supplied URL.
- Separate facts, inferences, assumptions, open questions, and recommended searches.

## Required Output Sections

1. Partner Notes
2. Source Gap Diagnosis
3. Theme Hypotheses
4. Possible Companies Requiring Verification
5. Recommended Next Searches

## Current Source Gaps

- devtools: last30days query timed out (120s)
- vertical-ai: last30days exited with code 1

## Suggested Next Searches

- No next searches generated.

## Evidence Pack

The companion JSON file is `research-workbench-input.json`. Use it as the only factual source.
