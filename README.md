# VC Signals

> **AI-Powered Company Radar for Venture Capital**

A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Claude Co-Work](https://claude.com/product/cowork) that turns noisy public internet chatter into a weekly company radar — 30-50 investable companies organized by emerging theme, in devtools, cybersecurity, and AI infrastructure.

**[See how it works (visual guide)](https://abhishek255.github.io/vc-signals/)**

---

> **Phase 1 (April 2026):** Output flipped from theme-centric briefs to a company-first radar. See [Phase 1 changes](#whats-new-april-2026) below.

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
/vc-signals radar devtools
```

In 3-5 minutes, you get a company radar like this:

```markdown
## VC Radar: Developer Tools — Week of 2026-04-16

### What's Moving
- **MCP Agent Infrastructure** — NEW. 97M monthly SDK downloads, Gartner says 75% of API gateways will adopt MCP.
  Companies riding this: 6
- **AI Coding IDEs & Agents** — NEW. $7B market; Anysphere in talks for $5B at $60B; Cognition+Windsurf consolidation.
  Companies riding this: 4
- **AI-Powered Code Review** — NEW. $1.2B raised category-wide 2024-25; depth-vs-speed shakeout.
  Companies riding this: 4
[+3 more themes]

### Company Radar (30 companies)

| Company | Theme | Tag | Why On Radar |
|---------|-------|-----|--------------|
| Anysphere (Cursor) | AI Coding IDEs | NEW | $2.3B Series D Nov 2025 at $29.3B; in talks for $5B at $60B |
| Runlayer | MCP Agent Infra | NEW | $11M seed Khosla/Felicis Nov 2025; 8 unicorns as launch customers |
| ToolHive | MCP Agent Infra | NEW | Led by K8s creator Craig McLuckie; managing MCP servers as K8s resources |
| Greptile | AI Code Review | NEW | 82% bug catch rate vs CodeRabbit's 44%; full-codebase indexing |
| QA Wolf | AI Testing | NEW | $56.1M total; Peter Thiel angel; 130+ enterprise customers |
| Arize AI | AI Observability | NEW | $70M Series C; Uber/PepsiCo/Tripadvisor as customers |
| [+24 more rows]

### New To Radar This Week
- Anysphere — AI Coding IDEs. $2.3B Series D, in talks for $5B at $60B.
- Runlayer — MCP Infra. $11M seed, 8 unicorns as customers.
- [+8 more]

### Faded Off Radar
(First scan — no prior radar to compare against.)
```

Each company gets a one-sentence **Why On Radar** specific signal — funding, traction, founder background, or product moment. Tags update week-over-week: NEW for first sightings, RETURNING for ones that disappeared and came back, PERSISTENT for 3+ consecutive weeks.

---

## What is this?

VC Signals is a skill (plugin) for Claude that acts as your weekly research analyst — focused on producing an actionable company list, not just a trend brief. It scans Hacker News, Reddit, X/Twitter, GitHub, blogs, and other sources — then synthesizes what it finds into a structured investor brief.

**Works with:**
- **Claude Code** — CLI, desktop app, VS Code, JetBrains
- **Claude Co-Work** — Anthropic's desktop app for knowledge work

For each company on the radar, you get:
- **Theme it's riding** — which emerging trend places it on the radar
- **Tag** — NEW (first sighting), RETURNING (came back after 2+ weeks gone), PERSISTENT (3+ consecutive weeks), or empty
- **Why On Radar** — one specific sentence: funding, traction, founder, product moment
- **Confidence + role** — confirmed/likely/inferred and direct_solver/beneficiary/adjacent
- **Phase 2 (coming):** funding stage, headcount, founders, evidence URLs

---

## Installation

Pick your setup based on how you use Claude:

### Claude.ai / Co-Work (web)

Works out of the box — just paste the SKILL.md content into your conversation, or upload the skill ZIP.

1. **[Download vc-signals.zip](https://github.com/abhishek255/vc-signals/releases/latest/download/vc-signals.zip)**
2. Open Claude Co-Work → click **Customize** → **Skills** → **Upload**
3. Select the downloaded `vc-signals.zip`
4. Type `/vc-signals radar devtools` to start

> **Note:** The web version uses Claude's built-in web search only. External APIs (Reddit, HN, X, GitHub trending) are blocked by the web sandbox. You still get a full investor brief — just without per-source engagement data. For full source coverage, use Claude Code locally (see below).

### Claude Co-Work Desktop (with terminal access)

If you have the Claude desktop app with terminal access, you get full functionality. Paste this in Terminal:

```bash
git clone https://github.com/abhishek255/vc-signals.git /tmp/vc-signals && mkdir -p ~/.claude/skills && cp -r /tmp/vc-signals/.claude/skills/vc-signals ~/.claude/skills/vc-signals && rm -rf /tmp/vc-signals && echo "Done! Restart Claude and type: /vc-signals radar devtools"
```

Then **close and reopen Claude Co-Work**. Type `/vc-signals radar devtools` to start. Run `/vc-signals setup` to configure API keys for Reddit, HN, X, GitHub, and Perplexity.

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

The skill is auto-detected. Type `/vc-signals radar devtools` to start.

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

**You can skip any key** — the skill works with whatever you have and tells you what you're missing.

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

### All Commands

| Command | What It Does |
|---------|-------------|
| `/vc-signals setup` | Guided setup wizard — walks you through API keys step by step |
| `/vc-signals radar <sector> [time]` | **Company radar — 30-50 investable companies organized by emerging theme** (Phase 1 default) |
| `/vc-signals weekly <sector> [time]` | Alias for radar (kept for backward compatibility) |
| `/vc-signals theme "<topic>" [time]` | Deep-dive into a specific theme |
| `/vc-signals company "<name>" [time]` | Which rising themes is a company exposed to? |
| `/vc-signals github <sector>` | Top repos by star velocity — spot fast-growing OSS projects |
| `/vc-signals add-sector <name>` | Add a new sector with guided taxonomy generation |

**Sectors:** `devtools`, `cybersecurity`, `ai-infra` (add your own with `add-sector`)

**Time window:** Append `7d`, `14d`, `30d`, `60d`, or `90d` to control how far back to search. Defaults: weekly = 14 days, theme/company = 30 days.

### Examples

**Company Radar:**
```
/vc-signals radar devtools
```
Returns 30-50 investable companies organized by 6-8 themes, with tags showing what's NEW vs PERSISTENT vs ACCELERATING. Themes that produce fewer than 3 mappable companies are dropped — the radar prioritizes investable depth over thematic breadth.

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

---

## How It Works

```
You type: /vc-signals radar devtools
                    │
                    ▼
        ┌───────────────────────┐
        │      SKILL.md         │  ← Claude reads this as instructions
        │   (orchestrator)      │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │   Retrieval Layer     │  ← Goes and finds recent chatter
        │  WebSearch (default)  │
        │  or last30days        │
        │  (Reddit, HN, X...)  │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │   GitHub Trending     │  ← Finds fast-growing repos
        │  (star velocity API)  │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │   Claude's Brain      │  ← The magic part
        │  • Spots patterns     │
        │  • Clusters themes    │
        │  • Scores momentum    │
        │  • Maps companies     │
        │  • Investor framing   │
        └───────────┬───────────┘
                    │
                    ▼
          Company Radar (30-50 cos)
          (printed + saved)
```

**Claude is the intelligence engine.** The Python scripts just handle API calls and file storage. Claude does all the thinking.

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
- **GitHub star velocity** is approximated — no historical time series without a third-party service
- **Company seed map** starts with ~40 entries — coverage improves as you add companies
- **Scheduling** requires manual setup via `/schedule` — the skill guides you through it but can't auto-schedule itself
- **Momentum scoring** is heuristic, not statistically rigorous — transparency over precision
- **Deep research** requires OpenRouter API key and costs ~$0.90 per query

## Why This Exists

VCs spend hours each week reading Hacker News, scrolling X, checking GitHub trending, and scanning funding announcements — trying to spot the next wave before it becomes consensus.

Most of that time is spent on **retrieval**, not **thinking**. VC Signals flips that ratio: automated retrieval, human judgment on the output.

The result: a weekly forcing function to explore categories you might not have found on your own, with enough evidence and company mapping to decide in 5 minutes whether something is worth a deeper look.

---

## What's New (April 2026)

**Phase 1: Company-first radar.** The previous output was a theme newsletter — 8-12 themes with companies as a sub-table inside each. Real-user feedback (April 14) made it clear the company table was the actual product; themes are the discovery mechanism, not the deliverable.

**What flipped:**
- Themes → 3-line headers (was 30+ lines per theme)
- Companies → top-level deduplicated table (was buried in per-theme sections)
- Tags moved from themes to companies (NEW / RETURNING / PERSISTENT)
- Themes that surface fewer than 3 mappable companies get dropped before scoring
- Schema additions: companies are first-class entities with stable history (`company_index.json`), Phase 2-ready null slots for funding/headcount/founders

The previous `/vc-signals weekly` command still works as an alias for `/vc-signals radar`. Existing briefings remain readable; week-over-week diffs gracefully degrade for the one-week schema transition.

---

## Roadmap

1. ✅ **Phase 1: Company-first radar** (April 2026) — output flipped from theme-centric to company-centric; companies are first-class with tagging and persistence
2. **Phase 2: Company enrichment** — funding, headcount, founders pulled in via WebSearch + free APIs (Apollo.io tier)
3. **Phase 3: Slack delivery** — weekly radar pushed to a channel, Monday 9 AM
4. **Phase 4: Attio CRM integration** — "In Pipeline?" column, filter to show only NEW companies
5. **Phase 5: Theme depth** — drill-down surfaces actual sub-debates and company positioning, not just summaries

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
            │   └── last30days_adapter.py
            ├── config/
            │   ├── sectors.json
            │   └── company_aliases.json
            ├── tests/
            └── data/
                ├── briefings/     # weekly scan outputs (markdown + JSON)
                ├── themes/        # theme drill-down outputs
                ├── companies/     # company_index.json + per-company outputs
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
