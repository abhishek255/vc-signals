# VC Signals

> **AI-Powered Company Radar for Venture Capital**

A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Claude Co-Work](https://claude.com/product/cowork) that turns noisy public internet chatter into a weekly Marathon-style radar: up to 50 qualified companies and OSS projects organized by sector, theme, evidence quality, and next action.

**[See how it works (visual guide)](https://abhishek255.github.io/vc-signals/)**

---

> **Current state (May 2026):** VC Signals is a weekly company/project radar for Marathon-style deal discovery. It separates practitioner pain from candidate evidence, scores Investment Interest and Evidence Confidence separately, and explains when a sector has signal but no qualified companies yet.

---

## The Problem

Every week, thousands of signals about emerging technology trends are scattered across Hacker News, Reddit, X/Twitter, GitHub, blogs, and funding announcements. As a VC, you need to:

- Spot trends **before** they become consensus
- Separate **real signal** from hype
- Find **investable companies** you'd never search for directly
- Track which themes are **accelerating** vs fading
- Do all of this in **under an hour**, not a full day of research

VC Signals does this in one command.

---

## What You Get

```
/vc-signals radar all
```

In a few minutes, you get a weekly all-sector radar like this:

```markdown
# VC Signals Weekly Radar

## Run Summary

This run produced 50 qualified rows across 4 market sectors.
Source mix: 18 Grounded web, 16 OSS, 9 Hacker News, 7 Attio-aware.

## Partner Review

| Company / Project | Market Sector | Source Lane | Theme | Tag | Tier | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AgentFence | Cybersecurity | Grounded web | AI agent security | NEW | Partner Review | High | Medium | no_match | take meeting / assign owner | New company evidence tied to repeated MCP permission and agent-security pain. | Could be a narrow feature unless customer urgency and founder depth check out. |
| affaan-m/agentshield | Cybersecurity | OSS | AI agent security | RETURNING | Partner Review | High | Medium | no_match | track company formation | Fast-growing OSS scanner for agent configs, MCP servers, and tool permissions. | Repo traction may not map to company formation or buyer urgency. |
| RuntimeOps AI | Devtools | Hacker News | Agent runtime infrastructure | NEW | Watchlist | Medium | Medium | stale/no owner | refresh owner | HN launch and developer chatter around production agent runtime reliability. | Launch interest may fade unless there is real usage beyond early adopters. |

## Full Radar

Up to 50 qualified companies/projects. No filler rows. Full Radar keeps expanded fields like Stage, Raised, Headcount, Founders, LinkedIn, X, Attio URL, OSS Score, and Best Source when evidence supports them.

## Sector Intelligence

### Cybersecurity
Status: Company and OSS/project candidates found
Why no more companies: several pain signals were promoted through grounded company discovery; remaining Reddit/HN chatter did not include enough company identity evidence.
Next hunt: AI agent security startups Seed Series A founder launch

## Themes With No Company Yet

| Market Sector | Theme | Evidence | Why It Matters | Why No Company Yet | Suggested Search |
|---|---|---|---|---|---|
| Data Infra | Emerging technical signal | HTTP/3, storage cleanup, and infrastructure chatter | Repeated non-company signal suggests operator pain. | No verified company/domain/founder evidence appeared in this run. | Data infra startups Seed Series A founder launch |

## Company Discovery From Themes

| Company | Market Sector | Theme | Source | Evidence URL | Query |
|---|---|---|---|---|---|
| AgentFence | Cybersecurity | AI agent security | grounding | https://agentfence.dev | AI agent security startups Seed Series A founder launch |

## Weak Evidence / Rejected Summary

- source_not_candidate_eligible: 44
```

Each company or project gets a specific **Why On Radar**, separate **Investment Interest** and **Evidence Confidence** scores, a skeptical **Why This May Be Noise**, and an action label.

**Market Sector vs Source Lane:** Market Sector is the investment category, such as Cybersecurity or AI Infra. Source Lane is where the evidence came from, such as OSS, Reddit, HN, Grounded Web, or TikTok. An OSS repo can therefore be `Market Sector = Cybersecurity` and `Source Lane = OSS`.

The generated partner preview also includes **Tag**, **Stage**, **Raised**, **Headcount**, **Founders**, **LinkedIn**, **X**, **Attio Owner**, **Attio URL**, and **Staleness** columns. These fields are evidence-backed: if the cache, source evidence, or Attio does not provide a trusted value, the cell stays blank instead of being guessed.

---

## What is this?

VC Signals is a skill (plugin) for Claude that acts as your weekly research analyst — focused on producing an actionable company and OSS list, not just a trend brief. It scans Hacker News, Reddit, X/Twitter, GitHub, blogs, and other sources — then synthesizes what it finds into a structured investor brief.

**Works with:**
- **Claude Code** — CLI, desktop app, VS Code, JetBrains
- **Claude Co-Work** — Anthropic's desktop app for knowledge work

For each company or project on the radar, you get:
- **Theme it's riding** — which emerging trend places it on the radar
- **Why On Radar** — one specific sentence: launch, traction, OSS momentum, founder/product moment, or market pain
- **Investment Interest + Evidence Confidence** — separate scores so a fascinating weak-signal company is not confused with a well-verified obvious one
- **Week-over-week tag** — NEW, RETURNING, PERSISTENT, or FADED based on stable company/project history
- **Attio status + action** — no match, active, passed, stale/no owner; with owner, last touch, staleness, and a direct record URL when available
- **OSS action reason** — watch, contact maintainer, map ecosystem, track company formation, or ignore, with the score rationale
- **Why This May Be Noise** — the default skeptical read
- **Needs More Evidence** — useful pain/theme signal that is not verified enough yet for Watchlist or Partner Review

---

## Installation

Pick your setup based on how you use Claude:

### Claude.ai / Co-Work (web)

Works out of the box — just paste the SKILL.md content into your conversation, or upload the skill ZIP.

1. **[Download vc-signals.zip](https://github.com/abhishek255/vc-signals/releases/latest/download/vc-signals.zip)**
2. Open Claude Co-Work → click **Customize** → **Skills** → **Upload**
3. Select the downloaded `vc-signals.zip`
4. Type `/vc-signals radar all` to start

> **Note:** The web version uses Claude's built-in web search only. External APIs (Reddit, HN, X, GitHub trending) are blocked by the web sandbox. You still get a full investor brief — just without per-source engagement data. For full source coverage, use Claude Code locally (see below).

### Claude Co-Work Desktop (with terminal access)

If you have the Claude desktop app with terminal access, you get full functionality. Paste this in Terminal:

```bash
git clone https://github.com/abhishek255/vc-signals.git /tmp/vc-signals && mkdir -p ~/.claude/skills && cp -r /tmp/vc-signals/.claude/skills/vc-signals ~/.claude/skills/vc-signals && rm -rf /tmp/vc-signals && echo "Done! Restart Claude and type: /vc-signals radar all"
```

Then **close and reopen Claude Co-Work**. Type `/vc-signals radar all` to start. Run `/vc-signals setup` to configure API keys for Reddit, HN, X, GitHub, and Perplexity.

### Claude Code (CLI, VS Code, JetBrains)

**Option A: Plugin install** (inside Claude Code):
```
/plugin marketplace add https://github.com/abhishek255/vc-signals
```

**Option B: Clone and open** (for developers):
```bash
git clone https://github.com/abhishek255/vc-signals.git
cd vc-signals
claude
```

The skill is auto-detected. Type `/vc-signals radar all` to start.

### What Happens on First Run

No matter which install method you use, on your first run the skill:

1. **Detects it's your first time** and asks if you want to run setup (2 minutes) or jump straight in with basic web search
2. **If you choose setup:** Claude installs the research engine, then asks for API keys one at a time — in plain English, with links. You paste each key or say "skip"
3. **If you skip setup:** You get results immediately via web search. Run `/vc-signals setup` anytime later to unlock more sources

**Prerequisites:** Python 3.12+ (`brew install python@3.13` on Mac if needed). Everything else is handled by the skill.

---

## Optional API Keys

The setup wizard handles all of this for you. But if you want to know what each key does:

| API Key | What it Unlocks | Cost | Required? |
|---------|----------------|------|-----------|
| **GitHub PAT** | Trending repos by star velocity | Free | Recommended |
| **Brave Search** | Broader web search coverage | $5/1K queries ($5 free credit/month) | Optional |
| **ScrapeCreators** | TikTok, Instagram, YouTube search | ~$29/month | Optional |
| **OpenAI or Gemini** | Smarter query planning and ranking | Pay-per-use / Free | Optional |
| **OpenRouter** | Deep research with Perplexity (50+ citation synthesis for theme drill-downs) | ~$0.90/query | Optional |
| **X/Twitter tokens** | X/Twitter developer discussions | Free (your account) | Optional |
| **Attio token** | CRM match, stale/no-owner status, passed-company flags | Existing workspace | Recommended for Marathon |

**You can skip any key** — the skill works with whatever you have and tells you what you're missing. If Brave/Parallel/Serper/Exa is missing, the weekly radar automatically uses a stricter non-grounded HN/GitHub fallback instead of broad noisy web discovery.

### How to Get Each API Key

<details>
<summary><strong>GitHub Personal Access Token (recommended)</strong></summary>

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Name: `vc-signals`
4. Expiration: 90 days (or your preference)
5. Scopes: check **`public_repo`** only
6. Click **"Generate token"** and copy it

</details>

<details>
<summary><strong>Brave Search API Key</strong></summary>

1. Go to https://brave.com/search/api/
2. Click **"Get Started for Free"**
3. Create an account
4. Go to **API Keys** → copy your key

You get $5 in free credits each month (~1,000 queries) — more than enough for weekly scans.

</details>

<details>
<summary><strong>ScrapeCreators API Key</strong></summary>

1. Go to https://scrapecreators.com
2. Sign up for an account
3. Choose a plan (Basic is fine for weekly scans)
4. Go to **Dashboard** → **API Keys** → copy your key

This enables TikTok, Instagram, and YouTube searches via the last30days engine.

</details>

<details>
<summary><strong>OpenAI API Key (or Gemini as a free alternative)</strong></summary>

**OpenAI:**
1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Click **"Create new secret key"**
4. Copy the key (starts with `sk-`)
5. Add a payment method under **Billing** (usage is typically $0.01-0.05 per scan)

**Gemini (free):**
1. Go to https://aistudio.google.com/apikey
2. Click **"Create API key"**
3. Copy the key

</details>

<details>
<summary><strong>OpenRouter API Key (for deep research)</strong></summary>

1. Go to https://openrouter.ai/keys
2. Sign up or log in
3. Click **"Create Key"**
4. Copy the key (starts with `sk-or-`)
5. Add credits under **Billing** (~$0.90 per deep research query)

This enables Perplexity Sonar Pro synthesis for theme drill-downs — 50+ citations per query. Optional but significantly improves theme analysis quality.

</details>

<details>
<summary><strong>X/Twitter Auth Tokens</strong></summary>

1. Log into X/Twitter in your browser (Chrome or Firefox)
2. Open Developer Tools: **Cmd+Option+I** (Mac) or **Ctrl+Shift+I** (Windows)
3. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
4. Click **Cookies** → **twitter.com** (or **x.com**)
5. Find `auth_token` — copy its **Value**
6. Find `ct0` — copy its **Value**

These expire periodically — you'll need to re-extract them every few weeks.

</details>

---

## Usage

### Fastest Reliable Path

For the local Marathon-style workflow, use this path:

```bash
git clone https://github.com/abhishek255/vc-signals.git
cd vc-signals
python3 --version
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/current --limit 50
```

Then open:

```text
docs/radar-runs/current/weekly-preview.md
```

That Markdown file is the partner-readable artifact. The same folder also contains:

- `raw-evidence.json` or `<date>-raw-evidence.json`: source evidence from collection.
- `signals.json`: normalized Reddit/HN/GitHub/web/social signals.
- `candidates.json`: scored candidate companies/projects, including weaker "Needs More Evidence" rows.
- `sector-intelligence.json`: per-sector status, source gaps, rejected counts, and next-hunt prompts.
- `theme-signals.json`: useful non-company signal that should guide research but should not become a fake company row.
- `company-discovery.json`: targeted company-search evidence generated from theme/pain signals, used to reduce OSS-only output when grounded company evidence is available.
- `synthesis.json`: optional LLM synthesis notes when `--with-synthesis` is used.
- `research-workbench-input.json` and `research-workbench-prompt.md`: optional Codex/Claude workbench pack for weak-signal reasoning without promoting unverified leads.

If the output is thin, that does not necessarily mean the sector is dead. It means the current run found pain or chatter but not enough candidate-quality company/project evidence. Check `Sector Intelligence`, `Themes With No Company Yet`, `Company Discovery From Themes`, and `Weak Evidence / Rejected Summary` before deciding whether to rerun with better keys or do a manual deep dive.

### All Commands

| Command | What It Does |
|---------|-------------|
| `/vc-signals setup` | Guided setup wizard — walks you through API keys step by step |
| `/vc-signals radar <sector\|all> [time]` | **Weekly company/project radar — up to 50 qualified rows organized by sector, theme, and evidence quality** |
| `/vc-signals weekly <sector> [time]` | Alias for radar (kept for backward compatibility) |
| `python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/current --limit 50` | Deterministic local weekly run: saves raw evidence, normalized signals, scored candidates, and a partner preview |
| `/vc-signals theme "<topic>" [time]` | Deep-dive into a specific theme |
| `/vc-signals company "<name>" [time]` | Which rising themes is a company exposed to? |
| `/vc-signals oss <sector> [time]` | OSS radar — fast-growing repos, maintainers, ecosystem maps, and company-formation signals |
| `/vc-signals github <sector>` | Top repos by star velocity — spot fast-growing OSS projects |
| `/vc-signals add-sector <name>` | Add a new sector with guided taxonomy generation |
| `python3 .claude/skills/vc-signals/scripts/radar_run.py workbench --from-run docs/radar-runs/current --output-dir docs/radar-runs/current-workbench` | Agent-native research workbench: creates a Codex/Claude prompt and evidence pack for possible leads requiring verification |

**Sectors:** `devtools`, `cybersecurity`, `ai-infra`, `vertical-ai`, `data-infra`, `oss`, or `all` (add your own with `add-sector`)

**Time window:** Append `7d`, `14d`, `30d`, `60d`, or `90d` to control how far back to search. Defaults: weekly = 14 days, theme/company = 30 days.

### Weekly Partner Artifact

The local partner command is:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/current --limit 50
```

The artifact contains:

- Partner Review: top 10-15 ranked candidates.
- Full Radar: up to 50 qualified companies/projects, with no filler rows.
- Tag and Faded Off Radar: week-over-week status for current and recently disappeared companies/projects.
- Evidence-backed enrichment: stage, raised, headcount, founders, Attio owner/staleness, Attio URL, and OSS formation score when trusted evidence exists.
- Run Summary: candidate count, market-sector coverage, source mix, and an OSS-heavy warning when all qualified rows came from OSS.
- Sector Intelligence: every requested priority sector, including whether it produced company candidates, OSS/project candidates, pain with no company yet, no meaningful signal, or source failures.
- Themes With No Company Yet: bounded hunt prompts from non-company evidence, not fake company rows.
- Company Discovery From Themes: the second-pass company searches triggered by those theme prompts, with evidence rows that can be promoted into the full radar when they include a company/product identity and credible source URL.
- Weak Evidence Summary: what was filtered out and why, plus "Needs More Evidence" items when there is useful pain/theme signal without enough company verification.
- Optional `synthesis.json`: advisory LLM notes, source-gap diagnoses, theme hypotheses, and possible leads when `--with-synthesis` is used.
- Optional Research Workbench: a self-contained Codex/Claude prompt and evidence pack for source gaps, theme hypotheses, possible companies requiring verification, and next searches. It does not write to `candidates.json`.

Market Sector is the investment category, such as Cybersecurity or AI Infra. Source Lane is where the evidence came from, such as OSS, Reddit, HN, Grounded Web, or TikTok. An OSS repo can therefore be `Market Sector = Cybersecurity` and `Source Lane = OSS`.

Reddit is used primarily for curated pain discovery across devtools, cybersecurity, AI infra, vertical AI, data infra, and OSS. It rarely creates company rows directly. HN Show/Launch, GitHub repos, grounded web/company pages, Attio seeds, and user-provided companies are candidate-eligible sources.

YouTube, TikTok, Instagram, and Threads are supporting source lanes through ScrapeCreators/last30days. They can create a candidate only when the company/product identity is clear and corroborated by a founder/company account, demo, website, waitlist, or another source.

### Optional LLM Synthesis

Add `--with-synthesis` to write `synthesis.json` and render an `LLM Synthesis Notes` section in the weekly preview:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py weekly --sectors all --output-dir docs/radar-runs/current --limit 50 --with-synthesis
```

Synthesis is opt-in and advisory. It can summarize source gaps, suggest next hunts, and list possible leads for verification, but it cannot add uncited facts to `candidates.json`; unsupported claims are dropped before canonical candidate rows are written.

Provider behavior:

- By default, synthesis uses `GEMINI_API_KEY` or `GOOGLE_API_KEY` from the current shell or `~/.config/last30days/.env`.
- If Gemini is unavailable, it falls back to `OPENAI_API_KEY`.
- Set `VC_SIGNALS_SYNTHESIS_PROVIDER=openai` or `VC_SIGNALS_SYNTHESIS_PROVIDER=gemini` to force a provider.
- Set `VC_SIGNALS_SYNTHESIS_MODEL` to override the default model.

### Agent-Native Research Workbench

If grounded web search is missing or the weekly radar is still OSS-heavy, create a workbench pack:

```bash
python3 .claude/skills/vc-signals/scripts/radar_run.py workbench --from-run docs/radar-runs/current --output-dir docs/radar-runs/current-workbench
```

This writes:

- `research-workbench-input.json`: the evidence pack.
- `research-workbench-prompt.md`: the prompt for Codex/Claude.

Use this when you want the current agent's own LLM judgment to synthesize source gaps, theme hypotheses, possible companies to verify, and next searches. It is deliberately not grounding. It cannot add rows to `candidates.json`, and possible company leads must remain "requiring verification" until a real source URL supports them.

### Examples

**Company Radar:**
```
/vc-signals radar all
```
Returns up to 50 qualified companies/projects across the configured sectors. If a sector has signal but no qualified companies, the artifact says so explicitly instead of silently hiding the sector.

**Theme Drill-Down:**
```
/vc-signals theme "agent evals"
```
Deep analysis: what it is, why now, subthemes, companies solving it, OSS projects, hype vs durable verdict. Uses Perplexity deep research (50+ citations) when available.

**Company Backtrace:**
```
/vc-signals company "Confluent"
```
Which rising themes Confluent maps to, its role (solver vs beneficiary), evidence, and competitive context. Searches the company's GitHub repos, founder activity, and X/Twitter presence when available.

**GitHub Trending:**
```
/vc-signals github ai-infra
```
Top repos by star velocity — the ones growing fastest relative to their size, with commercial entity mapping.

**OSS Radar:**
```
/vc-signals oss ai-infra
```
Returns fast-growing open-source projects with star velocity, community discussion, likely company mapping, founder/contributor profiles, and an action: watch, contact maintainer, map ecosystem, track company formation, or ignore.

---

## How It Works

```
You type: /vc-signals radar all
                    │
                    ▼
        ┌────────────────────────────┐
        │ Weekly Radar Orchestrator  │
        │ sectors + sources + setup  │
        └──────────────┬─────────────┘
                    │
        ┌──────────────▼─────────────┐
        │ Source Collection          │
        │ Reddit/HN/GitHub/social    │
        │ grounded web if configured │
        └──────────────┬─────────────┘
                    │
        ┌──────────────▼─────────────┐
        │ Signal Classification      │
        │ pain vs launch vs OSS      │
        │ vs company web evidence    │
        └───────┬──────────────┬─────┘
                │              │
                │              ▼
                │    ┌──────────────────────┐
                │    │ Themes With No       │
                │    │ Company Yet          │
                │    └──────────┬───────────┘
                │               │
                │               ▼
                │    ┌──────────────────────┐
                │    │ Company Discovery    │
                │    │ From Themes          │
                │    └──────────┬───────────┘
                │               │
                └───────────────┘
                    │
        ┌──────────────▼─────────────┐
        │ Candidate Ranking          │
        │ interest + evidence +      │
        │ skeptical noise check      │
        └──────────────┬─────────────┘
                       │
        ┌──────────────▼─────────────┐
        │ Read-only Attio Awareness  │
        │ match, stale/no owner,     │
        │ passed-company flags       │
        └──────────────┬─────────────┘
                    │
                    ▼
          Weekly Partner Brief
          Partner Review + Full Radar
          Sector Intelligence + audit files
```

The pipeline first separates **pain/theme evidence** from **candidate evidence**. Reddit pain can create a theme, but not a company row by itself. If a theme looks real, the system runs a second-pass company search and only promotes a company when it finds a credible company/product identity and source URL. Attio is read-only context: it helps the brief say whether Marathon already knows the company, whether it is stale/no-owner, or whether it was previously passed.

If grounded web search is not configured, the run can become OSS-heavy. That is expected: GitHub repos and HN launches are easier to verify without broad web/company search. The brief labels that limitation instead of filling the radar with weak company guesses.

**Want the full picture?** Open the **[visual explainer](https://abhishek255.github.io/vc-signals/)** — covers architecture, scoring rubric, company mapping layers, persistence, and graceful degradation with diagrams.

---

## Customization

### Add a Company to the Seed Map

Edit `.claude/skills/vc-signals/config/company_aliases.json`:

```json
"New Company": {
  "aliases": ["newco", "newcompany.io"],
  "oss_projects": ["their-oss-project"],
  "sectors": ["devtools"],
  "themes": ["relevant theme"]
}
```

### Add a Sector Subcategory

Edit `.claude/skills/vc-signals/config/sectors.json` — add a new entry under a sector's `subcategories`.

### Add a New Sector

```
/vc-signals add-sector fintech
```

Claude will propose subcategories, generate search queries, subreddits, and negative terms — then save it to the config. No JSON editing needed.

You can also manually add a sector by editing `sectors.json` following the existing structure.

---

## Known Limitations

- **WebSearch path** gives less structured data than last30days (no per-source isolation)
- **Grounded company discovery** depends on a configured web search key. Without it, the run still uses OSS/HN/available sources, but non-OSS company discovery is intentionally limited and labeled.
- **GitHub star velocity** is approximated — no historical time series without a third-party service
- **Company seed map** starts with ~40 entries — coverage improves as you add companies
- **Scheduling** requires manual setup via `/schedule` — the skill guides you through it but can't auto-schedule itself
- **Momentum scoring** is heuristic, not statistically rigorous — transparency over precision
- **Funding, headcount, founder, stage, and lead-investor fields** are evidence-backed when available, not guaranteed. Blank cells mean no trusted source, cache, or Attio value was found.
- **Attio integration is read/match context only** — it matches and enriches records but does not write notes, assign owners, update CRM fields, or create list entries unless a later writeback workflow is built.
- **Social/video evidence is supporting evidence** — YouTube, TikTok, Instagram, and Threads need clear company/product identity plus corroboration before creating candidate rows.
- **Slack destination is still open/configurable** — weekly delivery can later target a configurable channel, but the current artifact is generated locally as Markdown/JSON.
- **LLM synthesis is opt-in and advisory** — unsupported claims are dropped, possible leads from synthesis require verification before they can be treated as canonical candidates, and the selected LLM provider must have working quota/billing.
- **Agent-native research workbench is not grounding** — it helps Codex/Claude reason over collected evidence and propose verification leads, but it does not turn unsourced ideas into canonical candidates.
- **Deep research** requires OpenRouter API key and costs ~$0.90 per query

## Why This Exists

VCs spend hours each week reading Hacker News, scrolling X, checking GitHub trending, and scanning funding announcements — trying to spot the next wave before it becomes consensus.

Most of that time is spent on **retrieval**, not **thinking**. VC Signals flips that ratio: automated retrieval, human judgment on the output.

The result: a weekly forcing function to explore categories you might not have found on your own, with enough evidence and company mapping to decide in 5 minutes whether something is worth a deeper look.

---

## What's New

**May 2026: Theme-driven company discovery.** The weekly command now uses useful pain/theme evidence to run a second-pass company search, writes `company-discovery.json`, and renders "Company Discovery From Themes" in the partner brief.

**May 2026: Radar V3 sector-balanced artifact.** The weekly command now separates `Market Sector` from `Source Lane`, reclassifies OSS projects into investment categories, renders a top Run Summary, adds Sector Intelligence for every priority sector, and turns non-company signal into "Themes With No Company Yet" hunt prompts.

**May 2026: Radar V2 reliability layer.** The weekly command creates auditable raw evidence, normalized signals, scored candidates, week-over-week tags, faded candidates/projects, evidence-backed enrichment fields, OSS formation scoring, and richer read-only Attio context.

**May 2026: Radar V2 signal pipeline.** The weekly command creates auditable raw evidence, normalized signals, scored candidates, and a partner-readable brief. It separates practitioner pain from candidate-eligible evidence, keeps up to 50 qualified rows with no filler, and renders sector coverage notes when a sector has weak signal or no qualified companies.

**April 2026: Company-first radar.** The previous output was a theme newsletter — 8-12 themes with companies as a sub-table inside each. Real-user feedback (April 14) made it clear the company table was the actual product; themes are the discovery mechanism, not the deliverable.

**What flipped:**
- Themes are context; company/project rows are the review surface
- The weekly artifact starts with Run Summary and Partner Review, then Full Radar, Sector Intelligence, Themes With No Company Yet, Company Discovery From Themes, and Weak Evidence
- Company/project rows became the primary object of review
- Weak signal is preserved as "Needs More Evidence" instead of being turned into a fake company row
- OSS is a source lane, not a default market sector; a security repo can be `Market Sector = Cybersecurity` and `Source Lane = OSS`
- Schema additions: companies/projects are first-class entities with stable history (`candidate_history.json`) and evidence-backed enrichment fields for stage, raised, headcount, founders, Attio context, and OSS formation scoring

The previous `/vc-signals weekly` command still works as an alias for `/vc-signals radar`. Existing briefings remain readable; week-over-week diffs gracefully degrade for the one-week schema transition.

---

## Roadmap

1. ✅ **Company-first weekly radar** — output flipped from theme-centric to company/project-centric.
2. ✅ **Radar V2 signal pipeline** — raw evidence, normalized signals, scored candidates, sector coverage, and weak-evidence summary.
3. ✅ **Curated Reddit pain discovery** — Reddit supports themes and "Needs More Evidence" but does not directly create company rows.
4. ✅ **Week-over-week persistence** — NEW / RETURNING / PERSISTENT / FADED tags on companies and projects, based on stable candidate history.
5. ✅ **OSS radar semantics** — GitHub velocity, OSS project rows, maintainer profiles, license preservation, company-formation score, action vocabulary, and action rationale.
6. ✅ **Read-only Attio CRM context** — domain/name matching, status labels, stale/no-owner resurfacing, passed-company quiet flags, owner, last touch, staleness reason, CRM URL, and mapped stage/raised/headcount fields.
7. ✅ **Evidence-backed company enrichment** — stage, raised, headcount, founders, founding year, and lead investor can be merged from fresh cache/source evidence/Attio; blank means no trusted evidence.
8. ✅ **Radar V3 sector-balanced artifact** — Market Sector and Source Lane are separate, Partner Review is priority-ranked, Sector Intelligence explains quiet sectors, and Themes With No Company Yet preserve non-company signal.
9. ✅ **Theme-driven company discovery lane** — non-company pain/themes generate targeted company searches, write `company-discovery.json`, and can promote verified company evidence into the radar.
10. ◐ **Grounded company discovery depth** — the lane is implemented, but broad web/company discovery still depends on configured web keys and better corroboration sources.
11. ✅ **Agent-native research workbench** — creates a Codex/Claude evidence pack and prompt for weak-signal synthesis without writing unverified leads into `candidates.json`.
12. ◐ **Ecosystem and contact depth** — still needs richer maintainer contact enrichment, founder background synthesis, and OSS ecosystem map generation.
13. **Weekly delivery** — Monday 8:00 AM ET Slack teaser with an open/configurable destination and link or artifact for the full radar.
14. **Theme depth** — drill-down surfaces actual sub-debates and company positioning, not just summaries.

---

## Project Structure

```
vc-signals/
├── README.md
├── vendor/
│   └── last30days-skill/          # research engine (cloned during setup)
├── docs/
│   └── superpowers/
│       ├── specs/                 # design spec
│       └── plans/                 # implementation plan
└── .claude/
    └── skills/
        └── vc-signals/
            ├── SKILL.md           # the skill definition
            ├── scripts/
            │   ├── persistence.py
            │   ├── github_trending.py
            │   ├── attio.py
            │   ├── radar_run.py
            │   ├── radar_models.py
            │   ├── radar_sources.py
            │   ├── radar_scoring.py
            │   ├── radar_company_discovery.py
            │   ├── radar_history.py
            │   ├── radar_enrichment.py
            │   ├── radar_oss.py
            │   ├── radar_render.py
            │   ├── radar_synthesis.py
            │   ├── radar_workbench.py
            │   └── last30days_adapter.py
            ├── config/
            │   ├── sectors.json
            │   ├── reddit_sources.json
            │   └── company_aliases.json
            ├── tests/
            └── data/
                ├── briefings/     # weekly scan outputs (markdown + JSON)
                ├── themes/        # theme drill-down outputs
                ├── companies/     # candidate_history.json + enrichment_cache.json
                ├── github/        # GitHub trending outputs
                └── history/       # theme_index.json for week-over-week
```

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b my-feature`
3. Make your changes
4. Run tests: `python3 -m pytest .claude/skills/vc-signals/tests/ -v`
5. Commit and push
6. Open a PR

---

## License

MIT
