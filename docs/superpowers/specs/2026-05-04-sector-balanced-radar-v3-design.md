# Sector-Balanced Radar V3 Design

## Goal

Make the weekly VC Signals artifact feel like a Marathon partner radar, not an OSS/GitHub leaderboard. The V3 weekly output must show what is investable across Marathon's priority markets, while still preserving the current rule that weak evidence should not be inflated into fake company rows.

The product principle is:

> Do not invent weak companies, but do not let OSS crowd out the market map.

## Problem Statement

The current V2 artifact is structurally reliable but strategically lopsided. In the latest all-sector run, every qualified candidate row was labeled `OSS` because GitHub trending produced the cleanest candidate-eligible evidence, while devtools, cybersecurity, AI infra, vertical AI, and data infra mostly returned Reddit pain or GitHub issues/PRs. The pipeline behaved according to its current rules, but the partner experience looked wrong: it implied no non-OSS market movement.

The root issue is semantic mixing:

- `OSS` is currently both a source lane and a displayed sector.
- GitHub projects are not reclassified into their real business sectors.
- Non-company evidence is only summarized as rejection counts, not transformed into useful hunt prompts.
- Partner Review is too strict; it can show one row even when there are many worth triage.
- Sector coverage explains absence, but not enough to guide a partner's next action.

## Desired Partner Experience

A Marathon partner should be able to open the weekly artifact and answer three questions in under ten minutes:

1. What should I inspect first?
2. What companies/projects entered or changed on our radar?
3. Where is there market signal but no investable company yet?

The output should feel broad, skeptical, and actionable. It should not pad weak rows, but every requested sector should have a visible status: qualified companies/projects, only OSS/projects, pain signal with no company yet, no meaningful signal, or source failure.

## Scope

Included:

- Separate market sector from source lane.
- Reclassify OSS repos into business sectors.
- Add sector-specific company-discovery query templates.
- Add richer sector coverage explanations.
- Add a "Themes With No Company Yet" section.
- Make Partner Review top 10-15 ranked rows with soft sector/source diversity.
- Update tests, sample artifacts, and README.

Excluded:

- Slack delivery.
- Attio writeback or owner assignment.
- Paid data providers for funding/headcount beyond current evidence-backed enrichment.
- A web dashboard.
- Fully automated LLM research synthesis inside the deterministic weekly pipeline. In this spec, that means the weekly command should not automatically run deep LLM-written market memos for every sector/company/theme. The weekly radar should remain auditable evidence collection, scoring, ranking, and rendering. LLM synthesis belongs in drill-down flows after a partner selects a company/theme, or in a later optional "generate memo for selected rows" command.

## Core Concepts

### Market Sector

The investment category Marathon wants to cover:

- `Devtools`
- `Cybersecurity`
- `AI Infra`
- `Vertical AI`
- `Data Infra`

`OSS` should no longer be a market sector by default. It should remain available as a requested source/mode, but OSS projects in the weekly artifact should be assigned to the closest market sector when possible.

### Source Lane

Where the signal came from:

- `OSS`
- `Reddit`
- `Hacker News`
- `GitHub activity`
- `Grounded web`
- `Funding`
- `Attio`
- `Structured seed`
- `YouTube`
- `TikTok`
- `Instagram`
- `Threads`
- `Social / Video`

Source lane explains evidence provenance. It should not replace market sector.

Social/video lanes are primarily powered by ScrapeCreators through last30days. They matter most for vertical AI, consumer workflows, SMB tools, creator-led SaaS, founder demos, and early product pull that appears before funding/news coverage. The renderer may group `YouTube`, `TikTok`, `Instagram`, and `Threads` under `Social / Video` in summaries, while preserving the exact source in JSON.

### Evidence Role

What the signal can support:

- `company_candidate`
- `oss_project`
- `pain_signal`
- `launch_signal`
- `funding_signal`
- `customer_pull`
- `product_demo`
- `founder_signal`
- `ecosystem_signal`
- `activity_signal`

Evidence role controls promotion rules. Reddit pain and GitHub issues should still not directly create company rows, but they can create themes, hunt prompts, and source-specific follow-up searches.

### Partner Action

What the investor should do:

- `take meeting`
- `assign owner`
- `refresh Attio`
- `contact maintainer`
- `track company formation`
- `map category`
- `watch`
- `ignore`

Actions should be derived from candidate type, evidence quality, Attio status, source lane, and score.

## Data Model Changes

Extend `Candidate` with:

- `market_sector: str`
- `source_lane: str`
- `evidence_role: str`
- `sector_confidence: str`
- `sector_reason: str`
- `partner_priority_score: int`

Keep existing `sector` temporarily for backward compatibility, but V3 rendering should treat `market_sector` as the displayed sector. During migration:

- `candidate.market_sector` is the partner-facing sector.
- `candidate.source_lane` says `OSS`, `HN`, `Reddit`, etc.
- `candidate.sector` remains populated for older code/tests, but should eventually be deprecated or aliased to `market_sector`.

Add a new lightweight model for non-company signal:

```python
@dataclass
class ThemeSignal:
    market_sector: str
    theme: str
    source_lanes: list[str]
    evidence_count: int
    evidence_summary: str
    why_it_matters: str
    why_no_company_yet: str
    suggested_search: str
    confidence: str
```

Theme signals are not candidates. They render in "Themes With No Company Yet".

## Sector Classification

Add `radar_sector_classifier.py`.

The classifier should use deterministic keyword/topic rules first. This keeps tests stable and avoids LLM drift in the core weekly command.

Examples:

- Cybersecurity: `security`, `soc`, `appsec`, `pentest`, `prompt injection`, `jailbreak`, `mcp permission`, `vulnerability`, `auth`, `secrets`, `compliance`
- Devtools: `ci`, `testing`, `github actions`, `build`, `deploy`, `developer workflow`, `code review`, `sdk`, `ide`, `terminal`
- AI Infra: `agent runtime`, `mcp`, `eval`, `inference`, `observability`, `model routing`, `rag`, `vector`, `llm app`
- Data Infra: `pipeline`, `warehouse`, `etl`, `lineage`, `data quality`, `lakehouse`, `analytics`, `dbt`
- Vertical AI: `sales`, `legal`, `healthcare`, `finance`, `insurance`, `recruiting`, `customer support`, `back office`, `operator workflow`

Classification output:

- `market_sector`
- `sector_confidence`: `High`, `Medium`, or `Low`
- `sector_reason`: short explanation, such as "Matched security + MCP permission keywords."

If no market sector is confidently detected:

- Use `market_sector = "Unclassified"`
- Keep `source_lane = "OSS"` if it came from GitHub/OSS
- Penalize Partner Review ranking unless evidence is otherwise very strong

## Source Collection Changes

### Sector-Specific Company Queries

Add a new `company_discovery_queries` block per sector in `sectors.json`.

Each sector should include:

- `company_launch_queries`
- `funding_queries`
- `founder_queries`
- `yc_queries`
- `technical_blog_queries`

Example for cybersecurity:

```json
{
  "company_launch_queries": [
    "Show HN AI security startup MCP agent permissions",
    "Launch HN AI SOC AppSec cloud security startup"
  ],
  "funding_queries": [
    "AI security startup raises seed agent security",
    "cybersecurity startup Seed Series A AI security"
  ],
  "yc_queries": [
    "site:ycombinator.com/companies AI security startup",
    "site:ycombinator.com/companies cybersecurity AI agents"
  ],
  "technical_blog_queries": [
    "AI agent security startup technical blog MCP",
    "prompt injection security startup founder blog"
  ]
}
```

The weekly command should prefer grounded web search when available. Without a grounded web key, it should still run narrower HN/GitHub queries, but clearly report that company discovery coverage is limited.

### Pain Signals Trigger Hunt Prompts

Reddit pain remains non-candidate-eligible. However, clustered pain signals should become `ThemeSignal` objects when they meet one of these thresholds:

- At least 2 evidence items in the same sector/theme from different posts or sources.
- One high-quality pain item plus one supporting GitHub/HN activity item.
- One source failure plus configured query intent that identifies a sector gap, rendered as low confidence.

Avoid turning generic jobs, resume reviews, news digests, or broad discussion threads into theme signals.

## Candidate Promotion Rules

Candidate rows can be created from:

- Grounded company pages.
- HN Show/Launch posts with extractable company/project names.
- Funding/news/company discovery items with domain or credible company name.
- GitHub/OSS repos as `oss_project`, then classified into market sectors.
- Social/video evidence when it clearly identifies a company/product name and includes at least one of: founder/company account, product demo, customer/user pull, website, waitlist, or corroborating source.
- Structured seed input.

Candidate rows should not be created from:

- Reddit pain alone.
- GitHub issues/PRs alone.
- Social/video posts that only show generic hype, commentary, memes, personal productivity tips, or unnamed products.
- Generic news digests.
- Funding announcements for obvious late-stage/consensus companies unless labeled `likely too late`.

## Partner Review Ranking

Partner Review should show the top 10-15 ranked items, not only strict `Partner Review` tier rows.

Use `partner_priority_score`, derived from:

- Investment Interest score.
- Evidence Confidence score.
- Attio status/action.
- Weekly tag.
- Sector diversity.
- Source lane diversity.
- OSS company-formation score.
- "Likely too late" penalty.
- Unclassified sector penalty.

Soft diversity rules:

- Max 5 OSS-source-lane rows in Partner Review by default.
- Prefer at least 1 visible item from any market sector with qualified candidates.
- If a sector has no qualified candidates but meaningful theme signals, include a compact hunt prompt in the sector intelligence section, not as a fake candidate row.

Full Radar remains up to 50 qualified rows with no filler. It can be rank-based, but should display `Market Sector` and `Source Lane` separately.

## Rendering Changes

### Top Summary

Add a short run summary:

```markdown
This run produced 50 qualified rows across 5 market sectors.
Source mix: 34 OSS, 8 HN/Launch, 5 Grounded Web, 3 Attio/Seed.
Non-OSS company discovery was limited because grounded web search is not configured.
```

### Partner Review

Columns should include:

- Company / Project
- Market Sector
- Source Lane
- Theme
- Tag
- Tier
- Interest
- Evidence
- Attio
- Action
- Why On Radar
- Why This May Be Noise

Detailed enrichment columns can remain in Full Radar, but Partner Review should be more readable.

### Full Radar

Keep expanded columns, but rename:

- `Sector` -> `Market Sector`
- add `Source Lane`
- keep `OSS Score` and `Action Reason`

### Sector Intelligence

Replace terse Sector Coverage with richer per-sector blocks:

```markdown
## Sector Intelligence

### Cybersecurity
Status: Qualified OSS/project candidates found; no verified company candidates.
Signals: 12 raw, 4 candidate-eligible, 2 promoted, 8 rejected.
Best evidence: OSS security scanners for MCP/agent permissions.
Why no more companies: no grounded company pages or funding/company discovery evidence.
Next hunt: search AI agent security startups, MCP permission platforms, AI SOC workflow startups.
```

Statuses:

- `Company candidates found`
- `OSS/project candidates found`
- `Pain signal, no company yet`
- `No meaningful signal this week`
- `Source failure / incomplete coverage`

### Themes With No Company Yet

Render only meaningful non-company signals:

```markdown
| Market Sector | Theme | Evidence | Why It Matters | Why No Company Yet | Suggested Search |
```

This section should be short: 3-8 rows, not a dumping ground.

## Error Handling

- If a sector query times out, include that in Sector Intelligence.
- If grounded web is unavailable, state that company discovery is limited.
- If every qualified row is OSS-source-lane, show a warning in the top summary:
  "This run is OSS-heavy; non-OSS company discovery did not produce qualified rows."
- If sector classification confidence is low, render `Unclassified` and keep the source lane visible.

## Testing Strategy

Add focused tests for:

- OSS repo reclassification into market sectors.
- Source lane preserved separately from market sector.
- Domainless OSS repos do not match Attio by repo slug.
- Partner Review returns 10-15 ranked items when enough rows exist.
- Partner Review respects max OSS soft cap when other qualified sectors exist.
- Sector Intelligence explains no-company sectors with raw/rejected counts.
- ThemeSignal creation from clustered pain/activity evidence.
- No ThemeSignal creation from job posts, resume reviews, or generic digests.
- Full Radar still caps at 50 and does not pad.
- Sample artifact includes Market Sector, Source Lane, Sector Intelligence, and Themes With No Company Yet.

## Verification Checkpoints

1. Unit tests pass for sector classification and source-lane preservation.
2. Synthetic mixed-sector run produces:
   - Cybersecurity OSS repo classified as Cybersecurity, not OSS.
   - Devtools repo classified as Devtools.
   - Reddit pain rendered as ThemeSignal, not Candidate.
3. Partner Review test with 30 candidates across 5 sectors returns 10-15 rows and includes sector/source diversity.
4. Live or captured all-sector artifact includes:
   - Partner Review with 10-15 rows.
   - Full Radar with Market Sector and Source Lane.
   - Sector Intelligence for every requested sector.
   - Themes With No Company Yet when non-company signals exist.
   - No domainless OSS Attio record URLs.
5. README updated to explain Market Sector vs Source Lane.
6. Secret scan passes.

## Migration Notes

Keep existing artifacts readable. Do not rename old JSON fields destructively in one step. For V3:

- Add new fields first.
- Render new fields first.
- Preserve old `sector` in JSON for compatibility.
- Update README to explain that `source_lane = OSS` does not mean the investment sector is OSS.

## Open Product Questions

These do not block implementation, but should be revisited after the first V3 artifact:

- Should `Unclassified` rows appear in Partner Review if their evidence is very strong?
- Should the OSS source-lane cap be configurable per run?
- Should "Themes With No Company Yet" count toward the top partner summary?
- Should grounded web absence lower confidence globally or only for company-discovery claims?

## Recommended Implementation Order

1. Add model fields and sector classifier.
2. Reclassify OSS repos and preserve source lane.
3. Add richer sector intelligence data structures.
4. Add ThemeSignal extraction for non-company evidence.
5. Tune Partner Review ranking and diversity.
6. Add sector-specific company query config.
7. Update renderer, README, and sample artifacts.
