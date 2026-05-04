# VC Signals Audit and Roadmap

**Date:** 2026-05-04
**Audience:** Abhishek, Marathon Management Partners users, future implementation agents
**Decision:** Keep the main radar weekly, all-sector, company-first.
**Related research:** `docs/2026-05-04-deep-research-oss-startup-radar-startupradar.md`

## Executive View

VC Signals is directionally right but still too much like a smart research prompt and not enough like an investor workflow system. The durable product is not "summarize what people are saying." The durable product is "surface non-obvious, investable companies and explain why a Marathon partner should care this week."

The best near-term wedge is a weekly all-sector radar for Marathon:

- 30-50 companies across devtools, cybersecurity, AI infra, vertical AI, data infra, and OSS.
- Seed to Series B as the explicit strike zone.
- Companies that are already consensus should remain visible but be labeled "likely too late."
- Attio should be treated as core workflow infrastructure, not a nice-to-have integration.
- "Already in Attio but stale/no owner" should surface as an action item.
- Companies previously passed in Attio should be flagged quietly when new signal appears, not automatically reopened.
- Scores should be split into Investment Interest and Evidence Confidence.
- Every row should include a skeptical "Why this may be noise" note.
- OSS should be first-class, including non-company repos, because non-company OSS often becomes company formation, acquisition, or thesis evidence.

My opinionated take: VC Signals should become a weekly "deal radar plus research memory" system before it tries to become a dashboard. The CLI skill is enough for now if the output is excellent, auditable, and tied into Attio/Slack.

## What The Skill Does Today

The current skill:

- Parses slash commands like `/vc-signals radar devtools`, `/vc-signals theme`, `/vc-signals company`, `/vc-signals github`, and `/vc-signals setup`.
- Uses a sector taxonomy from `config/sectors.json` to guide searches by sector, subcategory, subreddit, HN query, and discovery query.
- Uses public signal sources through WebSearch and local scripts:
  - `persistence.py` saves markdown briefs, diffs themes, and maintains local radar history.
  - `github_trending.py` searches GitHub repos and computes recent star velocity.
  - `last30days_adapter.py` is intended to call the external last30days research engine.
  - `enrichment.py` now provides cache load/save, TTL freshness, update, and merge scaffolding for company enrichment.
- Produces a company-first radar with themes as context and companies as the main artifact.
- Has a real test suite. The current repo has meaningful TDD coverage for persistence, GitHub trending, last30days adapter behavior, and enrichment cache behavior.

This is a strong foundation. The repo has moved beyond a demo. The biggest issue is that the live skill contract, docs, and scripts have not fully converged around the Marathon workflow.

## What It Does Well

**Company-first pivot is correct.**
The meeting feedback from Chase and Michael was company-centric: source links, CRM matching, funding, headcount, founder history, and filtering. The product docs correctly name the key insight: VCs invest in companies, not themes.

**Persistence is a differentiator.**
Most generic AI research flows are stateless. VC Signals already thinks in terms of what is new, persistent, returning, and faded. That is exactly how a partner wants to consume emerging-market signal.

**The setup philosophy is pragmatic.**
The skill degrades from last30days and scripts to WebSearch instead of failing hard. This matters because an internal VC tool must work even before every key and integration is configured.

**The test posture is unusually good for a skill.**
The tests already catch behavior in persistence, malformed inputs, command-line JSON errors, cache TTL, and GitHub failure cases. This lets us keep moving quickly without turning the skill into a brittle prompt pile.

## Where It Lacks

**1. The live skill is not yet Marathon-specific enough.**
`SKILL.md` still reads like a general VC signal skill. It does not yet encode the most important Marathon decisions as non-negotiable output rules:

- Weekly all-sector radar.
- Seed to Series B strike zone.
- Consensus companies labeled but not hidden.
- Attio status as a required workflow column.
- Stale/no-owner Attio matches as resurfacing opportunities.
- "Why this may be noise" as a default column.

**2. The scoring model is underspecified.**
The current `confidence` idea is too close to source confidence. Marathon needs two separate LLM-judged scores:

- **Investment Interest:** how much a Marathon partner should care, assuming the evidence is true.
- **Evidence Confidence:** how well-supported the claim is by sources, enrichment, and CRM context.

These should be opinionated but auditable and decomposed into visible sub-scores:

- Signal freshness: why this week.
- Market pull: buyer/user pain and budget urgency.
- Founder credibility: founder-market fit, technical depth, prior execution.
- Product wedge: why this product can enter the market.
- Traction quality: customers, OSS velocity, usage, revenue proxy, community pull.
- Timing: why now, and why not already consensus.
- Marathon fit: Seed to Series B, sector fit, likely entry point.
- Noise risk: why this may be hype, stale, crowded, or not venture-scale.

The final scores can be LLM-judged, but each row needs enough explanation that a partner can challenge them.

**3. Attio is still treated as future integration, but it is actually core.**
For Marathon, "new to radar" is not enough. The valuable workflow states are:

- Not in Attio: new discovery.
- In Attio, no owner: needs assignment.
- In Attio, stale notes: needs refresh.
- In Attio, active deal: avoid duplicate work, enrich existing record.
- In Attio, passed: explain why the new signal may change the prior decision.

For passed companies, the intended behavior is simple: the tool does not say "you were wrong" and does not reopen the deal. It says, "You passed before, but something new happened. Here is the new signal, here is why it might matter, and here is why it still may be noise." That keeps the tool respectful of partner judgment while preventing stale decisions from hiding newly relevant companies.

This is where VC Signals becomes workflow software instead of a research report.

**4. Source attribution is still not first-class in the output.**
Michael explicitly asked for attribution and links. The company table should not just say "why on radar"; it should expose 1-3 source links per company and keep the deeper evidence behind the row. Without this, the tool feels magical and hard to trust.

**5. OSS mode needs different ranking rules.**
OSS discovery cannot use the same ranking logic as company discovery. A repo can be valuable even when there is no company yet. For OSS, the radar should distinguish:

- Investable company already behind the repo.
- Founder/project likely to become a company.
- Important ecosystem project that indicates theme momentum.
- Non-commercial infrastructure with portfolio-support or acquisition relevance.
- High-noise repo with star growth but weak production evidence.

**6. The docs still overfit the previous phase plan.**
The product context, README, and skill contract should all say the same thing. At the moment, product direction has advanced faster than the runtime instructions.

## last30days Audit

The last30days skill is highly relevant because it searches social and community sources in parallel, scores by engagement, and synthesizes grounded briefs. Its current README says zero-config usage includes Reddit, HN, Polymarket, and GitHub, while setup unlocks X, YouTube, TikTok, and more. It also includes web and Perplexity/Sonar-style grounded research when configured. Source: [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill).

The local adapter is underusing it.

**Path detection is stale.**
The current adapter looks for:

```text
vendor/last30days-skill/scripts/last30days.py
```

The current upstream skill entrypoint lives under:

```text
skills/last30days/scripts/last30days.py
```

This means a fresh clone can exist locally and still be reported as not installed.

**Capability detection is wrong for product purposes.**
The adapter treats "configured" as the practical gateway, but last30days has useful zero-config sources. VC Signals should expose capabilities by level:

- Installed: engine exists.
- Free sources: Reddit, HN, Polymarket, GitHub.
- Social sources: X, YouTube, TikTok, Instagram, Threads, etc.
- Grounded web/deep research: OpenRouter/Sonar or equivalent.
- Store enabled: local SQLite research memory available.

**Source selection is too narrow.**
For Marathon's weekly all-sector radar, the default should use:

```text
reddit,hackernews,x,youtube,github,polymarket,grounding
```

My recommendation on TikTok/Instagram: keep them off by default for devtools, cyber, AI infra, data infra, and OSS. Turn them on for vertical AI, prosumer AI, creator tools, design tools, sales/marketing automation, recruiting, education, healthcare consumerization, and other categories where creator/customer pull matters. In infra sectors, TikTok and Instagram are usually higher-noise than Reddit, HN, GitHub, X, YouTube, and technical blogs.

**`--plan` should become mandatory for serious runs.**
The upstream last30days contract strongly prefers model-generated query plans for named entities and serious research. VC Signals should generate a VC-specific plan instead of relying on generic topic search. Each sector run should pass a plan with:

- Sector synonyms and subthemes.
- Subreddits and communities.
- GitHub query targets.
- Exclusion terms.
- Company extraction instructions.
- Stage and "likely too late" tagging instructions.
- Explicit skeptical evidence prompts.

**`--store` should be enabled for radar runs.**
last30days can persist ranked findings to local SQLite. VC Signals already has persistence, but last30days store gives source-level memory and dedupe. We should use both:

- last30days store: raw source memory.
- vc-signals persistence: investor brief memory and company/theme state.

**GitHub project/person mode is underused.**
For company or OSS deep dives, VC Signals should pass `--github-repo` and, where known, founder `--github-user`. OSS radar should use this heavily.

## VC Judgment Model

Based on public VC memo patterns and institutional VC writing, the useful judgment dimensions are not exotic. Bessemer's public memo library emphasizes how early-stage decisions often center on people, while a16z describes seed investing as a bet on team and idea before much else. Sources: [Bessemer Memos](https://www.bvp.com/memos), [a16z Seed Fund](https://a16z.com/introducing-a16zs-seed-fund/), [a16z About](https://a16z.com/about).

For Marathon, the system should judge companies through this lens:

Investment Interest should use:

| Dimension | Question | Suggested Weight |
|---|---|---:|
| Founder-market fit | Is the team unusually suited to win? | 20 |
| Market timing | Why is this opportunity opening now? | 15 |
| Pain and budget | Is the problem urgent and fundable? | 15 |
| Product wedge | Is the entry point sharp enough? | 15 |
| Traction quality | Is adoption meaningful for the company's stage? | 15 |
| Marathon fit | Is it Seed to Series B, in sector, and actionable? | 10 |
| Non-consensus upside | Is this early enough to matter? | 10 |

Evidence Confidence should use:

| Dimension | Question | Suggested Weight |
|---|---|---:|
| Source quality | Are sources primary, recent, and credible? | 30 |
| Cross-source support | Do independent sources point to the same conclusion? | 25 |
| Data specificity | Are funding, headcount, repo, customer, or usage claims concrete? | 20 |
| Recency | Did the important signal happen within the relevant window? | 15 |
| Contradiction check | Are there unresolved conflicts or weak assumptions? | 10 |

Then apply penalties:

- Likely too late: already consensus, intense press/funding heat, or late-stage category leader.
- Weak evidence: only one low-quality source.
- Hype risk: lots of AI language, little customer proof.
- Crowded market: many similar companies with unclear differentiation.
- Non-venture-scale: useful product but unclear large outcome.
- OSS-to-company gap: repo is interesting but no credible commercial path yet.

The score should be LLM-judged, but the evidence should be structured:

```json
{
  "company": "ExampleCo",
  "investment_interest": 82,
  "evidence_confidence": 64,
  "stage_fit": "Seed-Series B",
  "marathon_action": "Assign owner",
  "why_now": "...",
  "why_this_company": "...",
  "why_this_may_be_noise": "...",
  "evidence": [
    {"source": "github", "url": "...", "claim": "..."},
    {"source": "hn", "url": "...", "claim": "..."}
  ]
}
```

## Recommended Weekly Workflow

**1. Weekly all-sector collection**
Run one weekly scan across the core sectors, not one daily scan. The product should avoid noise and create a Monday-quality artifact.

Recommended format: one unified brief with compact sector sections. The top of the brief should have a cross-sector executive summary and the top 10-15 companies overall. The body should then group companies by sector so a partner can jump directly to devtools, cybersecurity, AI infra, vertical AI, data infra, or OSS.

**2. Sector-level retrieval through last30days**
Run last30days with VC-specific plans and source sets. Use zero-config sources when possible, and deeper configured sources when available.

**3. Company extraction and normalization**
Extract candidate companies, repos, founders, domains, and source URLs. Normalize company names and domains before scoring.

**4. Enrichment**
Use cached enrichment for stage, funding, headcount, founders, founding year, lead investors, and repo/founder activity. Refresh stale entries by TTL.

**5. Attio match**
Match by domain first. Surface:

- New to Marathon.
- Already in Attio but stale.
- Already in Attio with no owner.
- Active deal.
- Passed but new signal emerged.

Passed companies should be flagged quietly. In simple terms: the tool remembers that Marathon already said no, but if something important changes, it puts a small flag on the company and explains the change. It does not tell the partner to reopen it automatically.

**6. LLM investment scoring**
Generate an opinionated score with visible reasons and visible skepticism.

**7. Output**
Produce:

- Slack teaser: top 10-15 companies, action labels, links to full brief.
- Full brief: 30-50 companies, sources, scoring, Attio status, "why noise," and next actions.
- Appendix: raw source evidence and run metadata for auditability.

## Roadmap

### Phase A: Align Runtime Contract and Docs

- Update `SKILL.md` so weekly all-sector radar is the default Marathon workflow.
- Keep `/vc-signals radar <sector>` for focused scans, but add `/vc-signals radar all` or equivalent all-sector flow.
- Update README and product docs to consistently say weekly, not daily.
- Add required columns: Investment Interest, Evidence Confidence, Stage, Raised, Headcount, Attio Status, Action, Source Links, Why This May Be Noise, Likely Too Late.

### Phase B: Fix last30days Adapter

- Detect current upstream nested path: `skills/last30days/scripts/last30days.py`.
- Preserve support for older flat path.
- Report capability levels instead of binary configured/not configured.
- Add adapter support for:
  - `--x-related`
  - `--store`
  - `--save-dir`
  - `--web-backend`
  - `--deep`
  - `--tiktok-hashtags`
  - `--tiktok-creators`
  - `--ig-creators`
  - `--polymarket-keywords`
  - `--competitors` / `--competitors-list` for company comparisons
- Add tests for current upstream layout and command construction.

### Phase C: Scoring and Evidence Schema

- Define `company_score.json` style schema.
- Add deterministic validators around the LLM score.
- Require both scores to include evidence and a noise case.
- Make "likely too late" a judgment label, not a hard stage/funding filter.

### Phase D: OSS Radar

- Add `/vc-signals oss <sector>`.
- Include non-company repos.
- Use Gokul Rajaram's OSS Startup Radar as conceptual and implementation inspiration: 30/60/90-day star velocity, age-adjusted momentum, community signal, funding/stage enrichment, top themes, and transparent methodology. Abhishek confirmed permission to reuse it; preserve provenance and adapt it to Marathon's workflow rather than forking the experience unchanged.
- Label repo type:
  - Company-backed.
  - Founder-likely.
  - Ecosystem signal.
  - Portfolio-support relevant.
  - High-noise.
- Use explicit actions: watch, contact maintainer, map ecosystem, track company formation, ignore.
- Rank by star velocity, contributor quality, repo age, discussion quality, production usage, license/commercialization path, and company mapping.

### Phase E: Attio

- Implement domain-based matching.
- Add Attio status/action fields.
- Prioritize stale/no-owner records alongside net-new records.
- Preserve evidence trail when updating or recommending action.

### Phase F: Slack

- Weekly teaser only.
- Deliver Monday at 8:00 AM ET.
- Top 10-15 rows with action labels.
- Link or attach full brief.
- Avoid dumping 50 rows into Slack.

## What I Would Not Build Yet

- A dashboard before the scoring and Attio loop are useful.
- Fully autonomous daily alerts.
- A generic startup database.
- Natural-language thesis search before weekly radar quality is high.
- TikTok/Instagram by default for infra-heavy sectors.

## Open Questions For Abhishek

Resolved:

- Weekly radar lands Monday at 8:00 AM ET.
- Artifact should be one unified all-sector brief with sector sections.
- Passed Attio companies are flagged quietly when new signal appears.
- Scores are split into Investment Interest and Evidence Confidence.
- OSS actions are watch, contact maintainer, map ecosystem, track company formation, and ignore.

Still open:

1. Which Slack channel should receive the weekly teaser?
2. Who should own triage of "assign owner" and "flag quietly" actions inside Marathon?
3. Should the first implementation include vertical AI and data infra in `config/sectors.json`, or start with the existing three sectors plus OSS?

## Recommended Next Implementation Step

Start with Phase A and Phase B together:

1. Update `SKILL.md` and README to encode the weekly Marathon workflow.
2. Add TDD coverage for current last30days upstream path detection.
3. Fix the adapter path and capability model.
4. Add command construction support for `--store`, `--x-related`, source profiles, and optional creator sources.

This gives the product a stronger spine before adding Attio and scoring.
