# Market Movement Intelligence Product Spec

## Product Thesis

VC Signals should become market movement intelligence for Marathon Management Partners.

The user-facing promise:

> Every week, show Marathon the companies/projects worth focusing on, the market movement behind them, who is talking about it, the evidence, what Marathon already knows, and the recommended action.

The internal product model:

```text
Pain is one signal.
New companies are another signal.
Social chatter is another signal.
Adoption is another signal.
Attio/proprietary context is the edge layer.
```

The product should not stop at a nicer Markdown report. The destination is a system that detects market movement, finds companies/projects forming around it, overlays Marathon's proprietary context, and turns that into weekly team workflow.

## Customer And Job

Primary customer:

- Marathon Management Partners partners, especially Alex.

Secondary users:

- Marathon associates.
- Affiliated angels.
- Technical advisors and operator-angels helping validate markets and companies.

Core job:

> Tell me the top companies/projects Marathon should focus on this week and why.

Expanded job:

> This market is starting to move. Here are the new companies/projects. Here is who is talking about it. Here is the evidence. Here is what Marathon already knows. Here is the action.

## Product Principles

1. **Companies/projects are the action surface.** Markets and pain explain why, but Marathon acts on companies, projects, founders, and CRM records.
2. **Market movement creates edge.** A company list without "why now" is not differentiated enough.
3. **Attio is proprietary context, not enrichment garnish.** Without Attio, VC Signals is a useful public research assistant. With Attio, it becomes Marathon workflow software.
4. **Skepticism is a feature.** The system must explicitly explain why something may be noise or not investable now.
5. **Do not pad.** If only seven rows deserve partner attention, show seven rows and explain source gaps.
6. **Do not hide late/consensus companies.** Label likely-too-late rows and route them to monitor unless there is a clear Marathon action.
7. **LLM reasoning is allowed, invention is not.** Let the LLM connect evidence and write concise judgment, but never invent funding, headcount, founders, domains, customers, stage, or Attio status.
8. **Feedback should teach Marathon taste.** Alex's decisions should improve future ranking.

## Product Shape

The partner-facing weekly artifact should become:

```text
# Marathon Signal Radar: Weekly Focus

## 1. Partner Focus, Top 10-15
Rows Alex should actually inspect.

## 2. Market Movements, Top 3-6
Why those rows surfaced.

## 3. New To Marathon
No Attio match, no owner, stale records, or passed records with new signal.

## 4. Workflow View
Assign owner, research deeper, refresh Attio, take meeting, monitor only.

## 5. Extended Watchlist
Good but not top focus, up to 30 total rows across Focus + Watchlist.

## 6. Appendix
Needs more evidence, OSS watchlist, themes without companies, source gaps, noisy/ignore.
```

`weekly-focus.md` should be the new partner-facing artifact. `weekly-preview.md` remains the broader radar/audit artifact until the new artifact is validated.

## What Counts As Edge

VC Signals creates edge when it does at least one of these:

- Finds a credible company/project Marathon does not already know.
- Resurfaces a known Attio company with new signal, stale ownership, or no owner.
- Connects practitioner pain to companies/projects solving it before the category is obvious.
- Shows company formation around an emerging technical movement.
- Identifies adoption momentum before funding/news consensus.
- Separates real buyer pull from founder/investor hype.
- Shows why a row is actionable this week, not merely interesting.

It does not create enough edge when it only:

- Summarizes Reddit/HN chatter.
- Lists fast-growing OSS repos without company-formation context.
- Produces a generic startup list.
- Writes a prettier weekly report over weak source data.

## Signal Model

Every evidence item should eventually normalize into a `SignalEvent`.

```python
@dataclass
class SignalEvent:
    id: str
    source: str
    source_url: str
    observed_at: str
    captured_at: str
    source_lane: str
    signal_role: str
    market_sector: str
    market_movement: str
    company_name: str
    company_domain: str
    project_name: str
    actor_name: str
    talker_type: str
    talker_quality: str
    title: str
    summary: str
    raw_text: str
    engagement: dict
    confidence: str
```

### Signal Roles

`signal_role` must be one of:

- `pain`: user/operator problem signal.
- `launch`: new product/company/project announcement.
- `chatter`: narrative, conversation, founder/investor discussion.
- `adoption`: usage, technical traction, repo/package/download/contributor signal.
- `funding`: financing or investor involvement.
- `hiring`: hiring or team-growth signal.
- `crm`: Attio/proprietary context.
- `skepticism`: negative or cautionary evidence.

Why this matters:

- An X post is chatter, not proof.
- A GitHub issue is pain or adoption friction, not a company.
- A YC page is company formation, not traction.
- Attio is workflow context, not market evidence.

### Talker Type And Quality

"Who is talking" should describe actors, not just platforms.

`talker_type` should include:

- `founder`: supply-side narrative.
- `practitioner`: demand-side workflow pain.
- `buyer`: budget or purchase-intent signal.
- `customer`: high-quality validation.
- `oss_maintainer`: technical ecosystem signal.
- `investor`: consensus or hype signal.
- `influencer`: attention signal, often noisy.
- `incumbent`: validation or absorption risk.
- `unknown`: source lacks actor clarity.

`talker_quality` should be:

- `High`: buyer/customer/practitioner/founder with clear relevance.
- `Medium`: credible maintainer, technical operator, or specific community discussion.
- `Low`: influencer, generic investor chatter, vague social attention, unclear actor.

## Market Movement Model

A market movement is not just a rendered heading. It should become a durable object with memory.

```python
@dataclass
class MarketMovement:
    id: str
    name: str
    market_sector: str
    what_is_moving: str
    why_now: str
    why_not_now: str
    buyer_persona: list[str]
    user_persona: list[str]
    budget_owner: str
    who_is_talking: list[str]
    talker_mix: dict
    companies_or_projects: list[str]
    evidence_urls: list[str]
    skepticism_events: list[str]
    current_7d_signal_count: int
    previous_7d_signal_count: int
    current_30d_signal_count: int
    previous_30d_signal_count: int
    eight_week_baseline: float
    source_diversity_delta: int
    company_formation_delta: int
    momentum_label: str
    confidence: str
```

`momentum_label` should be one of:

- `NEW`
- `ACCELERATING`
- `PERSISTENT`
- `SPIKY`
- `FADING`
- `QUIET`

### Movement Assignment Rules

A company/project can attach to a movement only if:

- it has evidence matching the movement problem/category, or
- its product description directly addresses the movement, or
- it appears in source evidence for that movement.

The LLM must not attach companies to movements by vibe. Movement assignment requires evidence.

## Focus Item Model

```python
@dataclass
class FocusItem:
    id: str
    rank: int
    name: str
    company_domain: str
    project_url: str
    market_movement_id: str
    market_movement: str
    market_sector: str
    why_focus_this_week: str
    who_is_talking: list[str]
    talker_types: list[str]
    evidence_snapshot: list[str]
    evidence_urls: list[str]
    attio_status: str
    attio_owner: str
    attio_last_touch: str
    recommended_action: str
    investment_interest_score: int
    evidence_confidence_score: int
    focus_priority_score: int
    actionability_score: int
    freshness_score: int
    market_movement_score: int
    marathon_fit_score: int
    noise_risk_score: int
    consensus_risk_score: int
    company_identity_quality_score: int
    first_seen_at: str
    last_seen_at: str
    seen_in_prior_runs: bool
    weekly_tag: str
    new_evidence_this_week: list[str]
    why_this_may_be_noise: str
    skepticism_events: list[str]
```

### Weekly Tags

`weekly_tag` should be:

- `NEW`: first seen this week.
- `RETURNING`: seen before, absent recently, now back.
- `CHANGED`: known item with meaningful new signal this week.
- `PERSISTENT`: recurring signal without major change.
- `FADING`: previously stronger, now declining.

## Company Identity Quality

Company identity quality prevents inferred/project-only rows from polluting the partner focus list.

Suggested scoring:

| Score | Meaning |
|---:|---|
| 100 | Verified company domain + founder/company identity + launch/funding/company source |
| 80 | Verified company domain + credible launch/company source |
| 60 | OSS project with maintainer identity + clear commercial intent |
| 40 | Named project with weak/no company proof |
| 20 | Inferred name only |

Rows below 60 should generally stay out of Partner Focus unless explicitly routed to `Research deeper`.

## Focus Priority Formula

Focus Priority should be explicit and testable.

```text
focus_priority_score =
  0.25 * investment_interest_score
+ 0.20 * actionability_score
+ 0.15 * freshness_score
+ 0.15 * market_movement_score
+ 0.15 * marathon_fit_score
+ 0.10 * evidence_confidence_score
- 0.20 * noise_risk_score
- 0.15 * consensus_risk_score
```

Evidence confidence should matter, but it should not dominate. High-confidence late-stage consensus companies should not outrank fresh, actionable, non-consensus Seed-to-Series-B opportunities.

### Actionability Score Guidance

Examples:

- `+25`: no Attio match and credible company evidence.
- `+20`: stale Attio record with new signal.
- `+15`: Attio match with no owner.
- `+10`: clear founder/project to investigate.
- `+10`: passed Attio company with meaningful new evidence.
- `-20`: no company/project identity.
- `-20`: no plausible Marathon action.

## Recommended Actions

The action vocabulary:

- `Assign owner`: clear enough that someone should own next steps.
- `Research deeper`: interesting, but needs associate validation before partner action.
- `Refresh Attio`: already known, but stale or newly relevant.
- `Take meeting`: rare, high-confidence, actionable company.
- `Monitor only`: relevant but too early, too late, consensus, or noisy.

Rules:

- `Take meeting` should require high Evidence Confidence and clear company evidence.
- `Assign owner` is the main success path for new credible rows.
- `Refresh Attio` is the main success path for known/stale rows.
- `Research deeper` is the right action for high-interest but medium/low evidence rows.
- `Monitor only` is appropriate for likely-too-late or strategically relevant but low-actionability rows.

## Skepticism And Why Not Now

Skepticism should be data, not just prose.

Add `skepticism_events` to market movements and focus items.

Examples:

- Practitioners say this is a feature, not a company.
- HN comments call out weak differentiation.
- OSS maintainer says enterprise use case is out of scope.
- Investors are over-talking the category.
- Incumbent has shipped the same feature.
- Repeated complaints about pricing, reliability, or security.

Each market movement should include `why_not_now`, such as:

- No clear budget owner yet.
- May be a feature of incumbents.
- OSS project may not commercialize.
- Too much consensus already.
- Evidence is founder-led, not buyer-led.

## Alex Feedback Loop

Feedback should become a future scoring input.

```python
@dataclass
class AlexFeedback:
    run_id: str
    focus_item_id: str
    alex_rating: str
    notes: str
    created_at: str
```

`alex_rating` should include:

- `good_lead`
- `too_late`
- `noisy`
- `already_known`
- `take_meeting`
- `not_fit`
- `research_more`

Future ranking should learn from this feedback. In the first implementation, this can be a local JSON artifact or manually editable file. It does not need a UI.

## Source Adapter Contract

Future sources should plug into a common source adapter model.

```python
class SourceAdapter:
    def collect(self, query: str, since: str, until: str) -> list[dict]:
        ...

    def normalize(self, raw: dict) -> SignalEvent:
        ...

    def source_role(self, raw: dict) -> str:
        ...
```

This prevents X, LinkedIn, Product Hunt, package registries, GitHub issues, Stack Exchange, funding pages, and Attio from becoming arbitrary JSON blobs with inconsistent semantics.

Phase 1 does not need to build all adapters. It should define the contract and normalize existing artifacts into this shape where practical.

## Product Acceptance Test

Given `weekly-focus.md`, Alex should be able to answer in under five minutes:

1. What are the top 3 market movements?
2. Which 5 companies/projects should someone inspect first?
3. Which are new to Marathon?
4. Which Attio records need refresh?
5. Which rows are weak/noisy but worth watching?

If the artifact does not pass this test, the renderer failed even if the Markdown is technically valid.

## Phased Delivery Plan

### Phase 1: Partner Focus Artifact

Goal:

- Produce `weekly-focus.md` and `weekly-focus.json` from existing weekly artifacts.

Includes:

- Partner Focus, Top 10-15.
- Extended Watchlist, up to 30 total rows across Focus + Watchlist.
- Market Movements from current themes/candidates/theme-signals.
- Workflow View grouped by action.
- New To Marathon section from current Attio fields.
- Appendix for weak evidence, OSS watchlist, themes without companies, and source gaps.
- Explicit focus scoring and action rules.
- Company identity quality score.
- Basic `SignalEvent`, `FocusItem`, and `MarketMovement` models derived from existing artifacts.

Does not include:

- New external sources.
- Full time-series movement model.
- Alex feedback loop beyond model/file scaffolding.
- Slack delivery.

Why this phase matters:

- It immediately gives Alex a clearer artifact.
- It prevents the current radar from staying a broad table.
- It establishes the output contract that future intelligence layers must satisfy.

### Phase 2: Signal Role Normalization And Movement Memory

Goal:

- Turn raw evidence into durable `SignalEvent` records and track movement over time.

Includes:

- Persist signal role, talker type, talker quality, source URL, observed/captured dates.
- Movement time-series fields.
- Weekly tags for focus items.
- New/changing/fading movement logic.
- `skepticism_events` and `why_not_now`.
- Better "who is talking" summaries from actor types, not platform names.

Why this phase matters:

- Static reports become movement intelligence.
- Alex sees what changed, not just what exists.

### Phase 3: Company Discovery And Identity Resolution

Goal:

- Improve company/project discovery around market movements.

Includes:

- Company discovery searches generated from market movements.
- Company identity quality scoring.
- Domain-based dedupe.
- OSS project to company/founder mapping.
- Better founder/company/launch evidence handling.
- Stronger filters so inferred names do not pollute Partner Focus.

Why this phase matters:

- This is where the product moves beyond a better renderer and starts solving Alex's company discovery problem.

### Phase 4: Source Expansion

Goal:

- Add high-value source adapters behind the common `SignalEvent` contract.

Priority sources:

- X for founder/company chatter and launch threads.
- LinkedIn for company/founder/headcount context where accessible.
- Product Hunt and launch directories.
- YC and accelerator pages.
- Package registries such as npm, PyPI, crates, Docker Hub.
- GitHub issues/discussions, not just repos.
- Hiring/job-post signals.
- Funding/company pages and investor portfolio pages.
- Stack Exchange or practitioner Q&A where sector-relevant.

Why this phase matters:

- Alex needs chatter, launch, adoption, company formation, and buyer-pain signals in one product.

### Phase 5: Attio Workflow Intelligence

Goal:

- Make Attio the proprietary workflow layer.

Includes:

- New to Attio.
- In Attio, no owner.
- In Attio, stale.
- In Attio, active deal.
- Passed with new signal.
- Recommended action logic based on Attio state.
- Read-only first; writeback remains later and explicit.

Why this phase matters:

- This is the edge layer. It converts public market intelligence into Marathon-specific action.

### Phase 6: Alex Feedback And Ranking Calibration

Goal:

- Learn Marathon's taste from feedback.

Includes:

- Local `feedback.json` or similar artifact.
- Ratings: good lead, too late, noisy, already known, take meeting, not fit, research more.
- Use feedback to tune future ranking and noise penalties.
- Report what changed in ranking due to feedback.

Why this phase matters:

- Without feedback, the system stays generic.
- With feedback, it becomes increasingly Marathon-specific.

### Phase 7: Delivery And Operating Workflow

Goal:

- Make the weekly focus workflow easy for Marathon to consume.

Includes:

- Slack teaser with top rows and link/artifact.
- Full `weekly-focus.md`.
- Associate workflow instructions.
- Optional one-click/manual feedback capture.
- Scheduling Monday 8 AM ET.

Why this phase matters:

- A good artifact only matters if the team sees it, trusts it, and acts on it.

## Non-Goals For The Product

VC Signals should not become:

- A generic startup database.
- A generic trend newsletter.
- A Reddit/HN sentiment tracker.
- A source dump.
- A fake investment committee.
- A hallucinated AI analyst.

It should help Marathon make sharper, faster decisions about which companies/projects and market movements deserve attention this week.

## Current Recommendation

Do Phase 1 next, but design it with the full product model in mind.

Specifically:

- Build `weekly-focus.md` and `weekly-focus.json` from current artifacts.
- Use top 10-15 Partner Focus, not 15-30.
- Put additional rows in Extended Watchlist.
- Introduce the data models and scoring fields even if some values are initially derived heuristically.
- Do not block on new sources.
- Do not pretend Phase 1 is the full edge.

Phase 1 is the bridge. The destination is market movement intelligence with source role normalization, movement time-series, company discovery, Attio overlay, and Alex feedback.
