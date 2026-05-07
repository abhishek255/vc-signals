# Weekly Focus Market Movement Design

**Status:** Phase 1 design under the broader product spec in `docs/superpowers/specs/2026-05-07-market-movement-intelligence-product-spec.md`.

This document should not be treated as the full product destination. It is the first implementation slice: a partner-facing `weekly-focus.md` / `weekly-focus.json` artifact built from current weekly radar artifacts. The product destination is market movement intelligence with source role normalization, movement time-series, company discovery, Attio workflow context, and Alex feedback.

## Goal

Add a new `weekly-focus.md` artifact that turns VC Signals from a broad radar report into a Marathon partner focus brief.

The product principle is:

> Here are the 10-15 companies/projects Marathon should focus on this week, and the market movement behind each one.

This artifact should answer:

1. What markets are starting to move?
2. Which new companies/projects matter this week?
3. Who is talking about the movement?
4. What evidence supports the signal?
5. What does Marathon already know through Attio?
6. What action should the team take?

## Product Framing

VC Signals should become market movement intelligence for Marathon Management Partners.

Pain is one signal. New companies are another signal. Social chatter is another signal. Adoption is another signal. Attio/proprietary context is the edge layer.

The product should not become only a pain tracker, because pain without company discovery is not directly actionable for Alex. It should also not become only a startup list generator, because a startup list without "why now" and Marathon context has little edge.

The durable workflow is:

```text
Market pain / chatter
        +
New company / founder / product evidence
        +
Adoption / momentum / timing evidence
        +
Attio context
        ↓
Weekly Focus List
```

The current `weekly-preview.md` remains the broader radar artifact for now. `weekly-focus.md` is a new artifact beside it so Alex can compare the new partner-facing shape before it becomes the default.

## User And Job

Primary user:

- Alex / Marathon partners.

Secondary users:

- Marathon associates and affiliated angels who help validate rows, refresh Attio, or run deeper diligence.

The job:

> Show Alex the top 10-15 companies/projects worth attention this week, explain why each one matters now, show whether Marathon already knows it, and recommend the next action.

The artifact should be readable in under ten minutes. It should not require Alex to inspect JSON files or reason through source mechanics.

## Output Structure

`weekly-focus.md` should have six sections.

### 1. Focus List

The main section. A ranked list of 10-15 companies/projects Marathon should inspect this week.

Each row should include:

- Rank.
- Company/project.
- Market movement.
- Market sector.
- Why focus this week.
- Who is talking.
- Evidence snapshot.
- Attio status.
- Recommended action.
- Investment Interest.
- Evidence Confidence.
- Why this may be noise.

The visible evidence should be short. Prefer one or two snippets plus source names in the table, such as:

```text
GitHub +189 stars/30d; HN launch; founder launch thread
```

Full evidence URLs can live below the table or in the existing JSON artifacts. The table must not become unreadable link soup.

### 2. Market Movements

Three to six market movements that explain why the focus-list rows surfaced.

Each movement should include:

- What is moving.
- Why now.
- Who is talking.
- Companies/projects attached.
- Evidence.
- Marathon already knows.
- Suggested action.

Example shape:

```text
### AI Agent Permission Security

What is moving:
Teams are starting to worry about what AI agents can access, execute, and mutate across internal systems.

Who is talking:
- Security engineers on Reddit
- Maintainers building MCP permission tools
- HN discussion around agent sandboxing
- Founders posting about agent governance

Companies/projects:
- AgentShield
- MintMCP
- ToolHive

Marathon already knows:
- MintMCP: not in Attio
- ToolHive: in Attio, no owner
- AgentShield: no Attio match

Action:
- Assign owner to MintMCP
- Research AgentShield maintainer
- Refresh ToolHive record
```

### 3. New To Marathon

Rows that represent Marathon-specific workflow opportunities:

- No Attio match.
- Attio match with no owner.
- Attio match with stale last touch.
- Passed Attio company with new signal.

### 4. Marathon Workflow View

Group focus-list rows by recommended action:

- `Assign owner`
- `Research deeper`
- `Refresh Attio`
- `Take meeting`
- `Monitor only`

This section exists so Marathon can turn the brief into team workflow.

### 5. Extended Watchlist

Good but not top-focus rows. The combined Partner Focus + Extended Watchlist should not exceed 30 rows.

### 6. Appendix

Keep lower-confidence material out of Alex's main flow but preserve it for audit and associate research:

- Needs More Evidence.
- OSS/project watchlist.
- Themes with no company yet.
- Source gaps.

## Recommended Actions

The action vocabulary should be:

- `Research deeper`: associate validates weak but interesting signal.
- `Assign owner`: clear enough that someone should own next steps.
- `Refresh Attio`: already known, but stale or newly relevant.
- `Take meeting`: rare, high-confidence, actionable company.
- `Monitor only`: relevant but too early, too late, or too noisy.

`Take meeting` should be rare. If the radar recommends too many meetings, Alex will stop trusting it.

The main success path should be `Assign owner` and `Refresh Attio`, because those convert messy signal into Marathon workflow without pretending the system can make an investment decision.

## Focus List Eligibility

The focus list should be mostly companies, with a small number of high-signal OSS/project rows allowed.

Rules:

- Target 10-15 Partner Focus rows.
- Allow fewer when fewer rows qualify.
- Put additional credible rows in Extended Watchlist, up to 30 total across Partner Focus + Extended Watchlist.
- Do not pad with weak rows.
- Prefer companies with a domain, founder/company source, launch page, funding signal, Attio match, or strong OSS-to-company evidence.
- Allow up to 3-5 OSS/project-only rows when the action is clear:
  - `Research deeper`
  - `Assign owner`
  - `Monitor only`
- Do not allow generic OSS utilities into the focus list only because they have star velocity.
- Put interesting but ambiguous repos into the appendix.
- Keep late/consensus companies visible when relevant, but label them as `likely too late` or route them to `Monitor only`.

## Ranking Model

The focus list should optimize for focus-worthiness, not raw popularity.

Suggested top-level model:

```text
Focus Priority =
  Investment Interest
  + Actionability
  + Freshness
  + Non-consensus potential
  + Marathon fit
  - Noise risk
```

Investment Interest and Evidence Confidence remain separate.

Interpretation:

- High interest + medium confidence: worth quick verification.
- Medium interest + high confidence: watchlist or monitor.
- High confidence + too late: label likely too late.
- Low confidence + interesting theme: appendix, not focus list.

Focus Priority should decide the rank order inside `weekly-focus.md`. It should not replace the existing scores in `candidates.json`.

## Signal Roles

The system should combine source lanes by role.

### Pain Lane

Sources:

- Reddit.
- HN comments.
- Customer/community forums when available.
- GitHub issues and discussions.

Purpose:

- Explain market pull.
- Identify buyer/user pain.
- Improve "why now."

Pain alone should not create a focus-list row.

### Launch Lane

Sources:

- HN Show/Launch.
- Product Hunt.
- YC and accelerator pages.
- Founder launch posts.
- Company launch blogs.

Purpose:

- Create or support company candidates.
- Explain what changed this week.

### Founder And Chatter Lane

Sources:

- X.
- LinkedIn.
- Technical blogs.
- Podcasts or YouTube when relevant.

Purpose:

- Surface founder/company activity before press coverage.
- Show who is talking.
- Provide early market narrative.

### Adoption Lane

Sources:

- GitHub stars and contributors.
- Package registries such as npm, PyPI, crates, Docker Hub.
- Integrations.
- Docs/changelog activity.
- Hiring signal.

Purpose:

- Show traction or technical adoption.
- Separate real usage from generic chatter.

### Company And Financing Lane

Sources:

- Company websites.
- YC/company directories.
- Funding announcements.
- Investor portfolio pages.
- Form D where practical.
- LinkedIn/company profile data when available.

Purpose:

- Resolve company identity.
- Enrich stage, funding, headcount, founders, and domain.
- Decide whether the company is in Marathon's Seed-to-Series-B strike zone.

### Proprietary Context Lane

Sources:

- Attio.
- User-provided seed lists.
- Marathon-specific notes when available.

Purpose:

- Determine whether the company is new to Marathon.
- Surface stale/no-owner records.
- Flag passed companies quietly when new signal appears.
- Avoid duplicate work.

This is the edge layer. Without Attio context, the product is a useful research assistant. With Attio context, it becomes Marathon workflow software.

## Data Inputs

`weekly-focus.md` should be derived from existing weekly artifacts first:

- `candidates.json`
- `signals.json`
- `theme-signals.json`
- `sector-intelligence.json`
- `company-discovery.json`
- optional `synthesis.json`

This design should not require replacing the existing collection pipeline before producing the first artifact.

## Data Model Additions

Add a focused model for the rendered artifact rather than overloading `Candidate`.

Suggested model:

```python
@dataclass
class FocusItem:
    rank: int
    name: str
    market_movement: str
    market_sector: str
    why_focus_this_week: str
    who_is_talking: list[str]
    evidence_snapshot: list[str]
    evidence_urls: list[str]
    attio_status: str
    recommended_action: str
    investment_interest: str
    investment_interest_score: int
    evidence_confidence: str
    evidence_confidence_score: int
    focus_priority_score: int
    why_this_may_be_noise: str
    source_candidate_id: str
```

Suggested market movement model:

```python
@dataclass
class MarketMovement:
    name: str
    market_sector: str
    what_is_moving: str
    why_now: str
    who_is_talking: list[str]
    companies_or_projects: list[str]
    evidence_urls: list[str]
    marathon_context: list[str]
    suggested_actions: list[str]
    confidence: str
```

These models should support `to_dict()` and `from_dict()` so future versions can also write `weekly-focus.json`.

## Rendering Rules

The renderer should produce:

- `weekly-focus.md`
- optionally `weekly-focus.json` if useful for tests and future Slack formatting.

Rendering rules:

- Focus List first.
- Market Movement sections second.
- Workflow View third.
- Appendix fourth.
- Use compact prose, not long memo paragraphs.
- Do not display more than 30 focus-list rows.
- Do not hide source gaps.
- Do not promote uncited synthesis into focus rows.
- Use blank or `unknown` for missing enrichment; do not invent founders, domains, LinkedIn, funding, headcount, customers, or stage.

## Relationship To Existing Artifacts

`weekly-preview.md` remains the broad radar and current compatibility artifact.

`weekly-focus.md` becomes the experimental partner-facing artifact.

The intended relationship:

```text
weekly-preview.md
  Broad evidence-backed radar and audit view.

weekly-focus.md
  Curated partner focus brief.

candidates.json / signals.json / theme-signals.json
  Source of truth for evidence and scoring.
```

Once `weekly-focus.md` consistently feels better for Alex, it can become the default partner artifact and `weekly-preview.md` can become the appendix/audit artifact.

## LLM Role

LLM judgment is useful for clustering fragmented evidence into market movements and writing concise "why focus this week" explanations.

Guardrail:

> Let the LLM reason across evidence, but never let it invent evidence.

LLM output can:

- Name market movements.
- Summarize why now.
- Explain who is talking.
- Recommend next actions.
- Draft concise partner-facing text.

LLM output cannot:

- Invent company domains.
- Invent funding/headcount/stage.
- Invent founder names or LinkedIn URLs.
- Promote a row without evidence URLs.
- Override Attio status.

If `synthesis.json` is missing or disabled, `weekly-focus.md` should still render using deterministic grouping and candidate fields, but its prose may be more mechanical.

## Acceptance Criteria

Product acceptance:

- Alex can open `weekly-focus.md` and see the 10-15 companies/projects worth attention first.
- Every focus row answers "why focus this week?"
- Every focus row has an action.
- Every focus row has at least one evidence snapshot or clearly says evidence is weak.
- Attio context is visible when available.
- Market movement sections explain why the companies/projects surfaced.
- OSS/project rows do not dominate unless they are genuinely the strongest focus items.
- Weak but interesting material is preserved in the appendix instead of polluting the focus list.

Technical acceptance:

- Existing weekly artifacts still generate.
- `weekly-preview.md` remains unchanged unless explicitly updated later.
- New renderer writes `weekly-focus.md`.
- Tests cover focus-list eligibility, action grouping, ranking, rendering, and missing-data behavior.
- No generated local run artifacts are required to implement the model/renderer tests.

## Non-Goals

This phase does not include:

- Replacing `weekly-preview.md`.
- Slack delivery.
- Attio writeback.
- Dashboard UI.
- Paid data provider integrations.
- Fully solving source coverage for X, LinkedIn, Product Hunt, package registries, or funding data.
- Automatically sending meeting recommendations to partners.

## Implementation Decisions

These decisions keep the first implementation concrete:

1. `weekly-focus.md` should target 10-15 Partner Focus rows, but allow fewer when fewer candidates qualify. Do not pad. Additional credible rows go into Extended Watchlist, up to 30 total rows across Focus + Watchlist.
2. The first implementation should write `weekly-focus.json` alongside Markdown. This makes tests easier and gives future Slack formatting a structured input.
3. `Take meeting` should require high Evidence Confidence and clear company evidence. Deterministic scores alone are not enough unless the row has credible company/launch/Attio evidence.
4. Market movement naming should work without `--with-synthesis` by using candidate themes, theme signals, and sector labels. When `synthesis.json` exists, it can improve naming and prose but cannot invent evidence.
5. The focus artifact should be generated by default on every weekly run because it is a sibling artifact, not a replacement for `weekly-preview.md`.

## Recommendation

Build `weekly-focus.md` as a new default-generated artifact in the weekly pipeline, but keep it separate from `weekly-preview.md`.

Do not wait for perfect source coverage. Start by rendering a better partner-facing focus layer from current artifacts, then improve source lanes underneath it.

The first implementation should be conservative:

- Use existing candidates/signals/theme-signals.
- Rank by current scores plus simple actionability/freshness/Attio heuristics.
- Cap OSS/project-only rows.
- Generate market movements from candidate themes and theme signals.
- Preserve weak/source-gap material in the appendix.

This gives Alex a better artifact quickly while keeping the evidence model honest.
