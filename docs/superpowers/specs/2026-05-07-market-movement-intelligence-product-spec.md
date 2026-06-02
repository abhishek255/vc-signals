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

- Marathon Management Partners partners.

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
8. **Feedback should teach Marathon taste.** Partner decisions should improve future ranking.

## Product Shape

The partner-facing weekly artifact should become:

```text
# Marathon Signal Radar: Weekly Focus

## 1. Partner Focus, Top 10-15
Rows a partner should actually inspect.

## 2. Market Movements, Top 3-6
Why those rows surfaced.

## 3. New To Marathon
Rows with `no_match`, `not_found`, or explicitly `new` Attio status.

## 4. Workflow View
Assign owner, research deeper, refresh Attio, take meeting, monitor only.

## 5. Extended Watchlist
Good but not top focus, up to 30 total rows across Focus + Watchlist.

## 6. Appendix
Needs more evidence, OSS watchlist, themes without companies, source gaps, noisy/ignore.
```

`weekly-focus.md` should be the new partner-facing artifact. `weekly-preview.md` remains the broader radar/audit artifact until the new artifact is validated.

Strict output limits:

- Partner Focus: maximum 15 rows.
- Market Movements: maximum 6.
- New To Marathon: maximum 10.
- Extended Watchlist: maximum 15.
- Appendix: compact, grouped, and skimmable.

The first screen should answer the top market movements, top companies/projects, and top actions.

## Current Implementation Status

As of May 7, 2026, Phases 1A, 1B, 2, 2.1, 2.2, and 2.3 are implemented on branch `codex/weekly-focus-market-movement`.

What works now:

- `weekly-focus.json` is generated first.
- `weekly-focus.md` renders from `weekly-focus.json`.
- `feedback.json` is scaffolded.
- `identity-resolution.json` is generated beside the weekly artifacts.
- `metadata-loss-report.json` is generated as a local run artifact for diagnosing whether identity-useful metadata disappeared upstream, in adapter normalization, in signal promotion, in candidate metadata, or in identity resolution.
- Partner Focus, Market Movements, New To Marathon, Workflow View, Extended Watchlist, and Appendix exist.
- Deterministic scoring, basis arrays, Partner Focus gates, and strict `Take meeting` gates exist.
- Company identity resolution now classifies launch/company/OSS rows as `verified_company`, `launch_style_needs_identity`, `oss_project_watch`, `oss_with_commercial_intent`, or `insufficient_identity`.
- Evidence metadata now carries compact source fields through candidate promotion.
- HN launch URL resolution now attempts stored metadata, local HN cache, HN Algolia lookup, HN page fallback, then fails closed with explicit reasons.
- Executive Snapshot now states when a run is a research queue rather than owner-ready leads.
- The artifact counts Partner Focus rows, OSS/project-only rows, company/launch-style rows, and rows by action.
- `Top identity-resolution target` is surfaced so associates know what to verify first.
- `weekly-preview.md` remains unchanged.

The real regenerated artifact currently proves the product shape, but also exposes the bottleneck:

- It is useful as research triage.
- It is not yet owner-ready sourcing.
- It is still OSS-heavy because the current pipeline finds projects more reliably than verified companies.
- The next product gap is controlled company discovery and stronger source-backed launch/company identity evidence, not more Markdown formatting or more scoring.

Important product interpretation:

- `New To Marathon` should mean the system has real Attio evidence that the row is not already known: `no_match`, `not_found`, or `new`.
- `attio_status="unknown"` means Attio was not checked, not configured, failed, or could not match cleanly. It must not be called new to Marathon.
- Stale, no-owner, passed, or active Attio records belong in Workflow View and future Marathon Context sections, not in New To Marathon.

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
    talker_type_confidence: str
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

`talker_type_confidence` should be `High`, `Medium`, or `Low`. The system must not overstate buyer, founder, or practitioner identity when actor evidence is weak.

Fallback classification rules:

- Known founder or company leadership match -> `founder`.
- GitHub repo owner/maintainer -> `oss_maintainer`.
- HN/Reddit technical community plus problem language -> `practitioner`.
- Attio/company profile leadership or buyer role -> `buyer` or `customer`, only when explicitly supported.
- High-follower generic social account -> `influencer`.
- Otherwise -> `unknown`.

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

Each assignment should store:

```python
movement_assignment_method: str
movement_assignment_confidence: str
movement_assignment_evidence_url: str
```

Allowed assignment methods:

- `direct_match`: company/product text includes the movement's core problem terms.
- `co_occurrence`: company appears in the same source event as the movement.
- `backtrace`: company was discovered through a movement-specific search query and evidence matches the movement.
- `manual`: user or Attio-provided context explicitly links the company to the movement.

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
    talker_type_confidence: str
    evidence_snapshot: list[str]
    evidence_urls: list[str]
    missing_evidence: list[str]
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
    company_identity_quality_basis: list[str]
    focus_priority_basis: list[str]
    actionability_basis: list[str]
    freshness_basis: list[str]
    market_movement_basis: list[str]
    marathon_fit_basis: list[str]
    noise_risk_basis: list[str]
    consensus_risk_basis: list[str]
    movement_assignment_method: str
    movement_assignment_confidence: str
    movement_assignment_evidence_url: str
    first_seen_at: str
    last_seen_at: str
    seen_in_prior_runs: bool
    weekly_tag: str
    new_evidence_this_week: list[str]
    why_this_may_be_noise: str
    skepticism_events: list[str]
```

Every heuristic score must include a basis list. This prevents fake precision in Phase 1, when many values are derived from incomplete artifacts.

`missing_evidence` should disclose row-level gaps, such as:

- no verified company domain
- no buyer/practitioner evidence
- no founder identity
- no Attio match
- adoption is only GitHub stars
- chatter is founder-led only

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

The score must include `company_identity_quality_basis`, such as:

- `verified_domain_present`
- `launch_source_present`
- `attio_match_present`
- `maintainer_identity_present`
- `commercial_intent_unclear`
- `inferred_name_only`

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

Actionability must include `actionability_basis`, such as:

- `new_to_attio`
- `attio_stale_with_new_signal`
- `attio_no_owner`
- `passed_with_new_signal`
- `clear_founder_to_investigate`
- `no_company_identity`
- `no_clear_action`

### Consensus Risk Guidance

Consensus risk should be explicit, not a blunt penalty.

Consensus risk signals:

- late-stage funding
- large reported funding total
- Series C or later
- large headcount
- top-tier investor pile-on
- high volume of investor chatter
- major press coverage
- many same-category startups
- incumbent feature launch
- already active or passed in Attio

Consensus risk can mean:

- `high_but_actionable`: high consensus, but Attio is stale or no owner exists.
- `high_monitor_only`: high consensus and little Marathon actionability.
- `medium_category_forming`: visible category formation, but not yet fully crowded.

The output should explain the interpretation instead of blindly penalizing all consensus.

## Recommended Actions

The action vocabulary:

- `Assign owner`: clear enough that someone should own next steps.
- `Research deeper`: interesting, but needs associate validation before partner action.
- `Refresh Attio`: already known, but stale or newly relevant.
- `Take meeting`: rare, high-confidence, actionable company.
- `Monitor only`: relevant but too early, too late, consensus, or noisy.

Rules:

- `Take meeting` should require `evidence_confidence_score >= 75`, `company_identity_quality_score >= 80`, `actionability_score >= 75`, `noise_risk_score <= 40`, and no active Attio owner already handling the company.
- `Assign owner` is the main success path for new credible rows.
- `Refresh Attio` is the main success path for known/stale rows.
- `Research deeper` is the right action for high-interest but medium/low evidence rows.
- `Monitor only` is appropriate for likely-too-late or strategically relevant but low-actionability rows.

If a row does not clear the `Take meeting` gate, prefer `Assign owner` or `Research deeper`.

## Partner Focus Gates

A row can enter Partner Focus only if:

- `company_identity_quality_score >= 60`
- it has at least one `evidence_url`
- it is not purely inferred from LLM synthesis
- `noise_risk_score < 70`
- it has a clear recommended action
- it has either company/project evidence or Attio relevance

Rows that fail these gates should go to Extended Watchlist or Appendix.

`Monitor only` rows should generally stay out of Partner Focus unless strategically important and explicitly justified.

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

## Partner Feedback Loop

Feedback should become a future scoring input.

```python
@dataclass
class PartnerFeedback:
    run_id: str
    focus_item_id: str
    partner_rating: str
    notes: str
    created_at: str
```

`partner_rating` should include:

- `good_lead`
- `too_late`
- `noisy`
- `already_known`
- `take_meeting`
- `not_fit`
- `research_more`

Future ranking should learn from this feedback. In the first implementation, this can be a local JSON artifact or manually editable file. It does not need a UI.

Phase 1A should scaffold feedback capture immediately, even if ranking calibration waits until later.

Suggested file:

```json
{
  "run_id": "2026-05-11",
  "feedback": [
    {
      "focus_item_id": "agent-permissioning_agentshield",
      "rating": "research_more",
      "notes": "Interesting but verify if commercial company exists."
    }
  ]
}
```

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

Given `weekly-focus.md`, a partner should be able to answer in under five minutes:

1. What are the top 3 market movements?
2. Which 5 companies/projects should someone inspect first?
3. Which are new to Marathon?
4. Which Attio records need refresh?
5. Which rows are weak/noisy but worth watching?

If the artifact does not pass this test, the renderer failed even if the Markdown is technically valid.

## Quality Metrics

Track these metrics over time:

- `precision_at_10`: human-marked `good_lead` or `research_more` among top 10.
- `unsupported_claim_rate`: claims in focus rows without evidence support.
- `no_evidence_focus_row_rate`: Partner Focus rows with no evidence URL. Target: 0.
- `duplicate_company_rate`: duplicated company/domain rows in Focus + Watchlist.
- `wrong_attio_action_rate`: rows where Attio status/action is wrong.
- `oss_project_only_pollution_rate`: project-only rows promoted without clear company-formation or strategic rationale.
- `too_late_promoted_rate`: likely-too-late rows promoted to Partner Focus without a clear action.
- `clear_action_rate`: rows with a non-empty recommended action.
- `missing_evidence_disclosed_rate`: rows with material evidence gaps that disclose them.

These are product quality metrics, not vanity usage metrics.

## Phased Delivery Plan

### Phase 1A: Partner Focus Artifact

Status: implemented on branch `codex/weekly-focus-market-movement`.

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
- Score basis fields for every heuristic score.
- Partner Focus gates.
- Row-level `missing_evidence`.
- Strict `Take meeting` gate.
- Feedback file scaffold.
- Basic `SignalEvent`, `FocusItem`, and `MarketMovement` models derived from existing artifacts.

Does not include:

- New external sources.
- Full time-series movement model.
- partner feedback loop beyond model/file scaffolding.
- Slack delivery.

Why this phase matters:

- It immediately gives partners a clearer artifact.
- It prevents the current radar from staying a broad table.
- It establishes the output contract that future intelligence layers must satisfy.

### Phase 1B: Company Identity Quality And Attio Action Overlay

Status: implemented as a first deterministic overlay on branch `codex/weekly-focus-market-movement`.

Goal:

- Make the first artifact meaningfully actionable for partner review by improving company identity and Attio-driven actions before broader source expansion.

Includes:

- Stronger company identity quality scoring and basis.
- Domain-based matching where available.
- New to Attio.
- In Attio, no owner.
- In Attio, stale.
- In Attio, active deal.
- Passed with new signal.
- Likely too late.
- Recommended action logic based on Attio state.
- Read-only Attio behavior.

Why this phase matters:

- Attio is the edge layer. It should affect the product early, even if writeback is much later.
- A partner should be able to hand the artifact to an associate and know what to update or investigate.

### Phase 2: Company Identity Resolution And Launch Verification

Status: implemented on branch `codex/weekly-focus-market-movement`.

Goal:

- Convert promising OSS/project/launch-style rows into verified company or project records that Marathon can act on.

Includes:

- Domain discovery for launch-style and OSS-derived leads.
- Founder identity discovery from source-backed pages.
- Company vs OSS project classification.
- Maintainer-to-founder or maintainer-to-company mapping where evidence supports it.
- Launch-source enrichment for HN/Show HN, YC/company pages, blogs, and company websites already present in current evidence.
- Attio-safe matching based on normalized domain/company identity.
- Identity-resolution confidence and basis fields.
- Clear output labels:
  - `verified_company`
  - `launch_style_needs_identity`
  - `oss_project_watch`
  - `oss_with_commercial_intent`
  - `insufficient_identity`
- A focused identity-resolution queue, starting with the top identity-resolution target in the Executive Snapshot.

Does not include:

- New social/source adapters.
- Attio writeback.
- Slack delivery.
- Broad market time-series.

Why this phase matters:

- This is the immediate bottleneck shown by the real Phase 1A/1B artifact.
- A partner does not only need interesting projects; they need to know which ones map to real companies, founders, and Marathon workflow actions.
- Better identity resolution should turn some rows from `Research deeper` into `Assign owner` or `Refresh Attio`.

Current result:

- The identity/action guardrails are working conservatively.
- Weak OSS/project rows are demoted or kept out of Partner Focus when identity/commercial intent is weak.
- Launch-style rows without verified domain/founder evidence remain `Research deeper`.
- The real current artifact still does not produce owner-ready sourcing rows because the collected evidence often lacks outbound company URLs, founder identity, or homepage/domain metadata.

### Phase 2.1: Evidence Metadata Preservation And Controlled Verification

Status: implemented on branch `codex/weekly-focus-market-movement`.

Goal:

- Preserve compact identity-useful metadata from existing evidence and make identity resolution consume stored metadata before live fetching evidence URLs.

Includes:

- `EvidenceMetadata` model.
- `Candidate.evidence_metadata`.
- HN/GitHub compact metadata preserved during candidate promotion.
- Metadata-first identity resolution.
- GitHub project identity from repo URLs.
- GitHub homepage as a domain candidate when upstream evidence provides it.
- Stored HN outbound URL/domain resolving identity without live fetch.

Does not include:

- New sources.
- Web search.
- Domain guessing.
- Attio writeback.

Current result:

- The pipeline can now use identity-useful metadata when it exists.
- The saved Burrow evidence did not include outbound URL/domain, so Burrow correctly remained `Research deeper`.

### Phase 2.2: Source Metadata Audit And Adapter Upgrade

Status: implemented on branch `codex/weekly-focus-market-movement`.

Goal:

- Determine whether identity-useful fields are missing upstream or dropped by the pipeline, then preserve fields that upstream already provides.

Includes:

- `metadata-loss-report.json` generated as a local run artifact.
- Loss points:
  - `upstream_missing`
  - `adapter_dropped`
  - `signal_dropped`
  - `candidate_dropped`
  - `identity_ignored`
  - `preserved`
- last30days normalization preserves identity-useful fields when present:
  - `outbound_url`
  - `resolved_url`
  - `story_url`
  - `domain`
  - `homepage`
  - `owner_name`
  - `owner_type`
  - `topics`
  - `description`
- GitHub repo parsing preserves `homepage` and identity field provenance.

Does not include:

- New broad source adapters.
- X, LinkedIn, Product Hunt, package registries.
- Attio writeback.

Current result:

- Burrow's saved evidence was diagnosed as `upstream_missing` for outbound URL/domain/homepage.
- GitHub rows such as AgentShield preserve repo owner/type/topics/description; homepage/domain were not present in that saved upstream evidence.

### Phase 2.3: HN Launch URL Resolution

Status: implemented on branch `codex/weekly-focus-market-movement`.

Goal:

- Given an already-captured `news.ycombinator.com/item?id=...` URL, resolve the outbound launch URL/domain if HN exposes one. Cache the result and fail closed.

Resolution order:

1. Stored metadata.
2. Local HN enrichment cache.
3. HN Algolia item lookup.
4. HN page fetch fallback.
5. Fail closed.

Includes:

- HN item ID parsing.
- HN Algolia lookup by item ID.
- HN page fallback parsing.
- Local HN enrichment cache.
- Explicit failure reasons such as `hn_no_outbound_url`, `hn_fetch_429`, `hn_algolia_not_found`, and `hn_internal_url_only`.
- Guardrails so HN/GitHub/social/content domains are not treated as verified company domains.

Does not include:

- Broad web search.
- Domain guessing.
- X, LinkedIn, Product Hunt, package registries.
- Attio writeback.

Current result:

- In test fixtures, HN Algolia/page resolution can populate a source-backed outbound domain.
- In the current saved run, Burrow still remained `Research deeper` because HN lookup/page fetch failed in the local environment and the resolver failed closed as intended.

### Phase 3: Signal Role Normalization And Source Adapter Contract

Goal:

- Turn raw evidence into durable `SignalEvent` records with source roles and actor classification.

Includes:

- Persist signal role, talker type, talker type confidence, talker quality, source URL, observed/captured dates.
- Normalize current artifacts into `SignalEvent`.
- Add source adapter contract.
- Better "who is talking" summaries from actor types, not platform names.

Why this phase matters:

- Source semantics stop being arbitrary JSON.
- The system can distinguish pain, launch, chatter, adoption, funding, CRM, and skepticism.

### Phase 4: Company Discovery Around Market Movements

Goal:

- Improve company/project discovery around market movements after identity quality is reliable.

Includes:

- Company discovery searches generated from market movements.
- Movement assignment metadata.
- Company identity quality scoring.
- Domain-based dedupe.
- OSS project to company/founder mapping using the Phase 2 identity-resolution model.
- Better founder/company/launch evidence handling.
- Stronger filters so inferred names do not pollute Partner Focus.

Why this phase matters:

- This is where the product moves beyond a better renderer and starts solving the partner company discovery problem.

### Phase 5: Movement Memory And Time Series

Goal:

- Track market movements over time.

Includes:

- Movement time-series fields.
- Weekly tags for focus items.
- New/changing/fading movement logic.
- `skepticism_events` and `why_not_now`.

Why this phase matters:

- Static reports become movement intelligence.
- Partners see what changed, not just what exists.

### Phase 6: Source Expansion

Goal:

- Add high-value source adapters behind the common `SignalEvent` contract.

Priority source order:

- GitHub issues/discussions, not just repos.
- X for founder/company chatter and launch threads.
- YC, Launch HN, and Product Hunt for company formation.
- Package registries such as npm, PyPI, crates, Docker Hub, and Libraries.io.
- Hiring/job-post signals.
- Funding/company pages and investor portfolio pages.
- Stack Exchange or practitioner Q&A where sector-relevant.
- LinkedIn for company/founder/headcount context where accessible, but it should not be foundational because access and automation constraints are painful.

Why this phase matters:

- A partner needs chatter, launch, adoption, company formation, and buyer-pain signals in one product.

### Phase 7: Partner Feedback And Ranking Calibration

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

### Phase 8: Delivery And Operating Workflow

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

The branch should be evaluated with a fresh real weekly run before merging.

Do not treat the current branch as the full product. Treat it as the new product shell plus identity reliability stack:

- It makes the weekly output easier for partner review to read.
- It shows the top market movements and focus rows.
- It is honest when the run is a research queue.
- It exposes source gaps and missing evidence.
- It gives associates a first action view.
- It diagnoses when candidate identity is missing because upstream source evidence lacks outbound URLs/domains.
- It refuses to manufacture owner-ready leads from weak evidence.

The next implementation should be controlled company discovery and source-backed company identity evidence around market movements.

Specifically, build the ability to produce more rows where the system can answer:

- What is the actual company or project?
- What is the verified domain?
- Who are the founders or maintainers?
- Is there evidence of commercial intent?
- Is it already in Attio under another name/domain?
- Should Marathon assign an owner, refresh Attio, research deeper, or monitor?

Do not jump straight to X, LinkedIn, Product Hunt, or package registries. Broader sources will help later, but the artifact still shows the first bottleneck: the system needs more source-backed company/project identity evidence from already relevant launch/company contexts.

Near-term order:

1. Run a fresh real weekly artifact on `codex/weekly-focus-market-movement`.
2. Inspect whether HN launch rows resolve outbound domains and whether any rows become credible `Assign owner` or `Refresh Attio`.
3. Merge the branch if tests pass and the fresh artifact remains honest.
4. Build controlled company discovery around market movements.
5. Then add source-role normalization and broader source adapters.
