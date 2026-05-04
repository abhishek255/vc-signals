# Deep Research: OSS Startup Radar and StartupRadar

**Date:** 2026-05-04
**Purpose:** Decide what VC Signals should borrow from Gokul Rajaram's OSS Startup Radar and StartupRadar.co.
**Recommendation:** Take inspiration from both, but keep VC Signals focused on Marathon's weekly, skeptical, CRM-aware investment workflow.

## Bottom Line

Yes, we should take inspiration from Gokul's OSS Startup Radar. It is directly adjacent to what Marathon asked for: early OSS/company discovery, GitHub star velocity, Reddit/HN community signal, pre-Series-A filtering, and a ranked output. It should heavily influence the first-class `/vc-signals oss` mode.

StartupRadar.co is a more mature competitive reference. It validates the bigger product direction: agents, curated source monitoring, CRM integration, thesis learning, feedback loops, startup similarity, and Slack/CRM delivery. But it is trying to become a broad autonomous sourcing platform. VC Signals should not chase that full surface yet. Our near-term wedge should be narrower and sharper: a weekly Marathon analyst that finds investable companies and explains why they matter.

## Sources Reviewed

- Gokul Rajaram OSS Startup Radar: https://github.com/gokulrajaram/oss-startup-radar
- StartupRadar: https://startupradar.co/
- StartupRadar discovery page: https://startupradar.co/discovery
- StartupRadar use cases: https://startupradar.co/use-cases
- StartupRadar data page: https://startupradar.co/data
- StartupRadar changelog: https://startupradar.co/changelog
- StartupRadar GitHub org: https://github.com/startupradar
- StartupRadar public repos:
  - https://github.com/startupradar/transformers
  - https://github.com/startupradar/demo-find-similar-startups
  - https://github.com/startupradar/ingestion
- GitHub fake-star research: https://arxiv.org/abs/2412.13459

## Gokul's OSS Startup Radar

### What It Is

Gokul's repo describes itself as a Claude Code skill for finding fast-growing pre-Series-A open-source AI/ML startups. It outputs the top 25 repos ranked by a composite score and the top 5 trending themes.

The public README says the scoring is:

```text
composite = 0.60 * velocity_score + 0.40 * community_score
```

The pipeline is:

1. Fetch candidates from GitHub.
2. Compute 30/60/90-day star velocity.
3. Search Reddit and Hacker News for community signal through last30days.
4. Run a funding check to exclude Series A+ companies.
5. Score, rank, and emit a Markdown report.

### What Is Strong

**1. It understands OSS discovery as a separate mode.**
This is the biggest lesson. OSS startup discovery is not normal company discovery. Repos can matter before a company exists. The system ranks projects first, then infers startup relevance.

**2. Star velocity is windowed, not just total stars.**
It computes 30/60/90-day gains and stars/day. That is better than total stars because total stars mostly rewards old winners.

**3. It rewards newer repos.**
The age multiplier is opinionated: younger repos get more credit, older repos get penalized unless recent momentum is high. This matches the VC use case: find what is becoming important, not what is already obvious.

**4. It combines quantitative and community signal.**
GitHub momentum alone is fragile. Adding Reddit and HN reduces false positives and helps distinguish real developer pull from empty starring.

**5. It has a clean report shape.**
The output is simple: top themes, top projects, velocity table, community signal, score breakdown, methodology. That is the right level of transparency.

### Weaknesses And Risks

**1. GitHub stars are gameable.**
Research on fake GitHub stars found large-scale suspected fake-star activity and notes that fake stars can be used for growth hacking and malicious promotion. VC Signals should treat stars as a signal, never as proof.

**2. Funding check is brittle.**
Scraping Crunchbase, homepages, GitHub org data, and DuckDuckGo snippets is useful but noisy. VC Signals should keep this as an enrichment hint, not a hard exclusion rule.

**3. "Pre-Series-A" is too narrow for Marathon.**
Marathon's strike zone is Seed to Series B. We should label late/consensus companies instead of excluding everything past Series A.

**4. AI/ML only is too narrow.**
Gokul's repo is optimized for AI/ML OSS. VC Signals needs OSS discovery across devtools, cyber, AI infra, data infra, and vertical AI.

**5. Community signal is limited.**
Reddit + HN are good, but OSS radar should also use GitHub issues/discussions, package downloads, release cadence, contributor quality, docs quality, X, YouTube, and last30days' wider source set where useful.

**6. Permission and provenance.**
The cloned public repo did not include a `LICENSE` file, but Abhishek confirmed permission to reuse it. We can borrow implementation ideas or code where useful, while preserving provenance and adapting the output to Marathon rather than forking it as-is.

## What VC Signals Should Borrow From Gokul

### Borrow Directly As Product Concepts

- First-class OSS mode.
- Top 25 OSS projects/repo output.
- 30/60/90-day star velocity.
- Composite scoring with visible score components.
- Age-adjusted momentum.
- "Top themes from top projects" synthesis.
- Funding/stage check as enrichment.
- Report methodology appendix.
- Strong non-startup filtering for lists, tutorials, big-tech repos, research orgs, personal experiments, and prompt dumps.

### Modify For Marathon

Gokul's score should evolve into two VC Signals scores:

```text
Investment Interest = investor judgment score
Evidence Confidence = support/evidence quality score
```

For OSS radar, I recommend this scoring model:

| Dimension | Score | Weight |
|---|---|---:|
| Star velocity | Investment Interest | 20 |
| Contributor quality | Investment Interest | 15 |
| Commercial path | Investment Interest | 15 |
| Developer pain severity | Investment Interest | 15 |
| Community pull | Investment Interest | 10 |
| Repo quality | Investment Interest | 10 |
| Marathon sector fit | Investment Interest | 10 |
| Non-consensus timing | Investment Interest | 5 |

Evidence Confidence should be separate:

| Dimension | Score | Weight |
|---|---|---:|
| GitHub data quality | Evidence Confidence | 25 |
| Cross-source support | Evidence Confidence | 25 |
| Source specificity | Evidence Confidence | 20 |
| Recency | Evidence Confidence | 15 |
| Manipulation/noise check | Evidence Confidence | 15 |

### Add What Gokul Does Not Yet Emphasize

- Stargazer authenticity checks.
- Contributor and maintainer identity quality.
- Package/download signal when available.
- Issue/discussion health.
- Fork-to-star ratio.
- Commit/release cadence.
- License and commercialization risk.
- Company formation probability.
- Attio matching.
- Action vocabulary:
  - `watch`
  - `contact maintainer`
  - `map ecosystem`
  - `track company formation`
  - `ignore`

## StartupRadar.co

### What It Is

StartupRadar positions itself as autonomous deal-sourcing agents for VC. Its homepage claims agents find startups continuously after the investor defines a thesis. It emphasizes CRM learning, Slack/CRM delivery, and pre-funding discovery.

Public claims from the site:

- 91% of startups in its database are tracked before first funding announcement.
- Users screen 1,000+ relevant deals per month.
- It tracks 20M+ companies across 850+ curated sources.
- It crawls 100k+ pages daily according to the homepage and 500k+ pages/day on the data page.
- It integrates with CRM and workflow tools including Attio, Slack, Salesforce, HubSpot, Affinity, Notion, Dealroom, Crunchbase, PitchBook, LinkedIn, and others.

### What Is Strong

**1. The positioning is right: agents, not databases.**
StartupRadar frames the old workflow as "you search databases" and the new workflow as "agents search for you." This is exactly where the market is moving.

**2. It treats feedback as product data.**
It claims models learn from user evaluations. This is important. VC Signals should eventually learn from Marathon's ratings, passes, meetings, and partner comments.

**3. It connects sourcing to CRM.**
StartupRadar knows the CRM is the workflow home. VC Signals should do the same with Attio.

**4. It has curated discovery sources.**
Its discovery page lists source categories such as academia, accelerators/incubators, press, and investors. This is a useful framing for VC Signals source profiles.

**5. It supports similarity/lookalike workflows.**
The public demo repo uses StartupRadar API descriptions plus OpenAI embeddings to find similar startups. This maps well to "find companies like X" and "find competitors to portfolio company Y."

**6. It has an evaluation UX concept.**
The changelog describes ratings, queue preview, keyboard shortcuts, team ranking, and evaluation sessions. That matters if VC Signals grows beyond CLI.

### Weaknesses / Difference From VC Signals

**1. It is broad.**
StartupRadar wants to be a sourcing platform. VC Signals should initially be a weekly investor-grade research workflow for Marathon, not a general-purpose database.

**2. It may optimize volume.**
Screening 1,000+ deals per user per month is useful for some funds, but Marathon's current ask is not "more volume." It is "fewer, sharper, earlier, better explained signals."

**3. It does not visibly foreground skepticism.**
The public marketing emphasizes discovery and fit. VC Signals should emphasize "why this may be noise" and explicit risk/assumption separation.

**4. It is not OSS-native in the same way.**
StartupRadar covers developer platforms and open-source traction, but Gokul's repo is much closer to OSS-native ranking.

## What VC Signals Should Borrow From StartupRadar

### Borrow

- "Agents, not databases" positioning.
- Thesis profile as a first-class object.
- CRM learning from prior evaluations.
- "New, stale, no owner, active, passed" CRM states.
- Similar-company / lookalike search.
- Source category profiles:
  - Developer platforms
  - Launch platforms
  - Accelerators/incubators
  - University/academia
  - Investor portfolios
  - Funding/news
  - Company growth updates
- Feedback loop: partner ratings improve future scoring.
- Delivery to Slack and Attio, not just Markdown.

### Do Not Borrow Yet

- Full autonomous continuous sourcing.
- Heavy dashboard work.
- Broad global company database ambition.
- 1,000+ monthly deal throughput as a success metric.
- Ranking/team gamification before the core weekly brief is trusted.

## Competitive Positioning For VC Signals

VC Signals should not compete head-on with StartupRadar as a database/API platform. It should be positioned as:

> A weekly skeptical operator-investor analyst for Marathon: it reads public technical and market signals, finds non-obvious companies and OSS projects, checks CRM context, and explains what is actionable now.

That gives VC Signals a different wedge:

| Product | Wedge | What They Optimize |
|---|---|---|
| Gokul OSS Startup Radar | OSS AI/ML repo discovery | Fast-growing pre-Series-A OSS projects |
| StartupRadar | Autonomous deal sourcing platform | Continuous thesis-matched startup discovery |
| VC Signals | Marathon weekly investor workflow | Earlier, skeptical, CRM-aware investment judgment |

## Recommended Changes To VC Signals

### 1. Build `/vc-signals oss` As Its Own Mode

This should be the next major product addition after last30days adapter fixes.

Output should include:

- Top 25 OSS projects.
- Repo type:
  - company-backed
  - founder-likely
  - ecosystem signal
  - portfolio-support relevant
  - high-noise
- Action:
  - watch
  - contact maintainer
  - map ecosystem
  - track company formation
  - ignore
- Investment Interest.
- Evidence Confidence.
- 30/60/90-day star velocity.
- Contributor quality.
- Community signal.
- Commercialization path.
- Noise/manipulation risk.
- Attio match if a company/domain exists.

### 2. Add An OSS Signal Schema

Proposed JSON shape:

```json
{
  "repo": "owner/name",
  "project_name": "Name",
  "repo_url": "https://github.com/owner/name",
  "sector": "ai-infra",
  "repo_type": "founder-likely",
  "action": "contact maintainer",
  "investment_interest": 78,
  "evidence_confidence": 66,
  "stars_total": 4200,
  "star_velocity": {
    "30d": 900,
    "60d": 1400,
    "90d": 2100
  },
  "community_signal": {
    "reddit_mentions": 3,
    "hn_mentions": 2,
    "x_mentions": 8
  },
  "commercial_path": "Likely devtool SaaS around hosted control plane",
  "company_mapping": {
    "company": null,
    "domain": null,
    "attio_status": "no_match"
  },
  "why_now": "Recent MCP adoption creates urgency for this category",
  "why_noise": "Stars may reflect launch hype; no production users found",
  "evidence": []
}
```

### 3. Add Star Authenticity / Quality Checks

Do not blindly rank by star count. Add checks for:

- Very high star velocity with low forks/issues/discussions.
- Suspiciously new stargazer accounts.
- Geographic/time clustering if available.
- Weak commit activity after star spikes.
- README-heavy but code-light repos.
- No package, demo, docs, or usage path.

This is important because fake-star research shows GitHub popularity can be manipulated at scale.

### 4. Turn StartupRadar's Workflow Ideas Into Marathon Workflow States

Attio states should drive action:

- `no_match`: assign owner if high interest.
- `stale`: refresh note and route to owner.
- `no_owner`: assign owner.
- `active`: enrich current deal, do not duplicate.
- `passed`: flag quietly with what changed.

### 5. Add Similarity / Lookalike Search Later

StartupRadar's embedding demo is useful but should be Phase 2 after weekly radar quality is high.

Useful commands later:

```text
/vc-signals similar "MintMCP"
/vc-signals competitors "CodeRabbit"
/vc-signals portfolio-adjacent "Company in Attio"
```

## Proposed Roadmap Update

### Near-Term

1. Fix last30days adapter path/capability support.
2. Update `SKILL.md` around weekly Marathon workflow.
3. Add OSS signal schema and tests.
4. Add `/vc-signals oss <sector>` mode.
5. Port the ideas of star velocity, age adjustment, community signal, and funding/stage enrichment into VC Signals.

### Medium-Term

1. Add Attio matching.
2. Add partner feedback/rating capture.
3. Add similar-company / lookalike search.
4. Add source profiles for accelerators, academia, investor portfolios, and launch platforms.

### Later

1. Dashboard.
2. Continuous autonomous monitoring.
3. Custom Marathon thesis model trained from evaluations.
4. API/data platform behavior.

## My Opinionated Recommendation

Do not fork Gokul's tool as-is. Make VC Signals absorb the best parts:

- Use Gokul's OSS radar as the conceptual template for OSS mode.
- Use StartupRadar as the long-term product reference.
- Keep our near-term output tighter: one Monday 8 AM ET Marathon brief with sector sections, skeptical scoring, Attio context, and clear actions.

The key product distinction should be:

> StartupRadar finds lots of companies. VC Signals tells Marathon which ones deserve attention and why.
