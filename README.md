# VC Signals

> **AI-Powered Investment Theme Discovery for Venture Capital**

A skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Claude Co-Work](https://claude.com/product/cowork) that turns noisy public internet chatter into ranked, investor-oriented briefs. Run one command per week — get the top emerging themes in **devtools**, **cybersecurity**, and **AI infrastructure** with company mapping, momentum scoring, and a blunt hype-vs-durable verdict.

**[See how it works (interactive visual guide)](https://htmlpreview.github.io/?https://github.com/abhishek255/vc-signals/blob/main/docs/vc-signals-explainer.html)**

---

## The Problem

Every week, thousands of signals about emerging technology trends are scattered across Hacker News, Reddit, X/Twitter, GitHub, blogs, and funding announcements. As a VC, you need to:

- Spot trends **before** they become consensus
- Separate **real signal** from hype
- Map trends to **investable companies**
- Track which themes are **accelerating** vs fading
- Do all of this in **under an hour**, not a full day of research

VC Signals does this in one command.

---

## What You Get

```
/vc-signals weekly devtools
```

In 3-5 minutes, you get a ranked brief like this:

| # | Theme | Momentum | Timing | Key Companies |
|---|-------|----------|--------|---------------|
| 1 | MCP Protocol & Agent Infra | 9/10 | Early-Mid | MintMCP, Anthropic, Perforce |
| 2 | Agentic Coding Race | 9/10 | Mid | Cursor ($29.3B), Windsurf, Claude Code |
| 3 | AI Code Review | 8/10 | Mid | CodeRabbit (2M repos), Qodo, Greptile |
| 4 | Supply Chain Attacks on Dev Tools | 8/10 | Early | Snyk, Socket, Chainguard |
| 5 | AI Testing Automation | 8/10 | Early-Mid | Playwright, Applitools, BaseRock |
| ... | *8-12 themes total* | | | |

Each theme includes **why it's rising** (with citations), **confidence rating**, **hype vs durable verdict**, and **company mapping with roles** (solver, beneficiary, adjacent).

Run it again next week and you see what's **new**, what's **accelerating**, and what's **fading**.

---

## What is this?

VC Signals is a skill (plugin) for Claude that acts as your weekly research analyst. It scans Hacker News, Reddit, X/Twitter, GitHub, blogs, and other sources — then synthesizes what it finds into a structured investor brief.

**Works with:**
- **Claude Code** — CLI, desktop app, VS Code, JetBrains
- **Claude Co-Work** — Anthropic's desktop app for knowledge work

For each emerging theme, you get:

- **Why it's rising** — with evidence and citations
- **Momentum score (1-10)** — how fast is this growing?
- **Confidence rating** — how sure are we this is real?
- **Investment timing** — early, mid, or late?
- **Hype vs durable** — blunt, one-sentence assessment
- **Company mapping** — who's solving this, who benefits, with confidence tags

<details>
<summary><strong>See a real output example (from a live scan on April 10, 2026)</strong></summary>

---

### 1. MCP Protocol & Agent Infrastructure

**Momentum: 9/10** | **Confidence: High** | **Timing: Early-Mid**

**Why it's rising:** MCP (Model Context Protocol) crossed 97 million monthly SDK downloads and has been adopted by every major AI provider — Anthropic, OpenAI, Google, Microsoft, Amazon. 50+ official servers and 150+ community implementations. The protocol just crossed from developer tooling into consumer hardware: Elgato's Stream Deck shipped with native MCP support. MCP Gateways are emerging as a new infrastructure category.

**Why investors should care:** MCP is becoming the TCP/IP of AI agents — the universal protocol layer. The gateway/proxy category is the enterprise play: auth, governance, audit trails.

**Hype vs Durable:** Durable — protocol adoption at 97M/month with every major vendor onboard is past the hype phase.

| Name | Role | Confidence | Notes |
|------|------|------------|-------|
| Anthropic | Beneficiary | Confirmed | Created MCP, driving adoption |
| MintMCP | Direct solver | Likely | First SOC 2 Type II certified MCP gateway |

---

### 2. Agentic Coding Race

**Momentum: 9/10** | **Confidence: High** | **Timing: Mid**

**Why it's rising:** Every IDE is racing to become "agentic." Cursor reached $29.3B valuation with 50% Fortune 500 adoption. Claude Code overtook traditional leaders. Windsurf hit 1M+ users. Google Antigravity launched with multi-agent orchestration. 55% of developers now use autonomous agents for bug fixing and PR generation.

**Why investors should care:** Largest TAM shift in developer tools in a decade. Second-order bets on inference infrastructure, eval frameworks, and context management systems.

**Hype vs Durable:** Durable but competitive — the question is who captures margin vs. who races to the bottom.

| Name | Role | Confidence | Notes |
|------|------|------------|-------|
| Anysphere (Cursor) | Direct solver | Confirmed | $29.3B valuation |
| Windsurf | Direct solver | Confirmed | 1M+ users |
| Claude Code (Anthropic) | Direct solver | Confirmed | Most-used by engineers |
| Google Antigravity | Direct solver | Confirmed | Multi-agent, new entrant |

---

### 3. AI Developer Tool Supply Chain Attacks

**Momentum: 8/10** | **Confidence: High** | **Timing: Early**

**Why it's rising:** The LiteLLM supply chain attack (March 24, 2026) was a watershed. Attackers compromised Trivy (a security scanner), exfiltrated PyPI tokens, and pushed malicious packages. LiteLLM gets 3.4M downloads/day. Simultaneously, North Korean operators disguising RATs as developer tools across npm, PyPI, Go, and crates.io.

**Why investors should care:** This is the "SolarWinds moment" for developer tools. Every company running AI agents now has a new class of supply chain risk.

**Hype vs Durable:** Durable — structural and worsening. AI tool adoption = more attack surface.

| Name | Role | Confidence | Notes |
|------|------|------------|-------|
| Snyk | Direct solver | Confirmed | Published LiteLLM analysis |
| Socket | Direct solver | Likely | Package analysis |
| Chainguard | Direct solver | Confirmed | Secure base images |

---

*...5 more themes in the full brief (AI Code Review, AI Testing, Secrets Management, AI Observability, Platform Engineering)...*

</details>

---

## Installation

Three ways to install, from easiest to most manual:

### Option A: One-Command Plugin Install (recommended)

If you already have Claude Code or Co-Work, just run this inside Claude:

```
/plugin marketplace add https://github.com/abhishek255/vc-signals
```

Done. Type `/vc-signals weekly devtools` to start. On first run, the skill auto-detects that it's your first time and walks you through a 2-minute setup.

### Option B: One-Line Terminal Install

If you prefer a terminal command (works for both Claude Code and Co-Work):

```bash
curl -sL https://raw.githubusercontent.com/abhishek255/vc-signals/main/install.sh | bash
```

This installs the skill globally. Open Claude Code or Co-Work and type `/vc-signals weekly devtools`.

### Option C: Clone the Repo

For developers who want to inspect the code or contribute:

```bash
git clone https://github.com/abhishek255/vc-signals.git
cd vc-signals
claude
```

The skill is auto-detected from `.claude/skills/`. Type `/vc-signals weekly devtools` to start.

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
| `/vc-signals weekly <sector>` | Weekly scan — top 8-12 emerging themes with company mapping |
| `/vc-signals theme "<topic>"` | Deep-dive into a specific theme |
| `/vc-signals company "<name>"` | Which rising themes is a company exposed to? |
| `/vc-signals github <sector>` | Top repos by star velocity — spot fast-growing OSS projects |

**Sectors:** `devtools`, `cybersecurity`, `ai-infra`

### Examples

**Weekly Sector Scan:**
```
/vc-signals weekly devtools
```
Returns 8-12 ranked themes like:
- "AI-Powered Code Review" (momentum: 8/10, timing: mid, companies: CodeRabbit, Cursor)
- "Rust-Based Build Tooling" (momentum: 6/10, timing: early, companies: Turbopack, oxc)

**Theme Drill-Down:**
```
/vc-signals theme "agent evals"
```
Deep analysis: what it is, why now, subthemes, companies solving it, OSS projects, hype vs durable verdict.

**Company Backtrace:**
```
/vc-signals company "Confluent"
```
Which rising themes Confluent maps to, its role (solver vs beneficiary), evidence, and competitive context.

**GitHub Trending:**
```
/vc-signals github ai-infra
```
Top repos by star velocity — the ones growing fastest relative to their size, with commercial entity mapping.

---

## How It Works

```
You type: /vc-signals weekly devtools
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
          Investor Brief
          (printed + saved)
```

**Claude is the intelligence engine.** The Python scripts just handle API calls and file storage. Claude does all the thinking.

**Want the full picture?** Open the **[interactive visual explainer](https://htmlpreview.github.io/?https://github.com/abhishek255/vc-signals/blob/main/docs/vc-signals-explainer.html)** — covers architecture, scoring rubric, company mapping layers, persistence, and graceful degradation with interactive diagrams.

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

Add a new top-level key to `sectors.json` following the existing structure (display_name, subcategories, discovery_queries, negative_terms).

---

## Known Limitations

- **WebSearch path** gives less structured data than last30days (no per-source isolation)
- **GitHub star velocity** is approximated — no historical time series without a third-party service
- **Company seed map** starts with ~40 entries — coverage improves as you add companies
- **No automated scheduling** — you run scans manually each week
- **Momentum scoring** is heuristic, not statistically rigorous — transparency over precision

## Why This Exists

VCs spend hours each week reading Hacker News, scrolling X, checking GitHub trending, and scanning funding announcements — trying to spot the next wave before it becomes consensus.

Most of that time is spent on **retrieval**, not **thinking**. VC Signals flips that ratio: automated retrieval, human judgment on the output.

The result: a weekly forcing function to explore categories you might not have found on your own, with enough evidence and company mapping to decide in 5 minutes whether something is worth a deeper look.

---

## Roadmap

1. **Automated weekly scheduling** — cron or Claude remote triggers, so the brief lands in your inbox every Monday
2. **Google Docs export** — save briefings directly to Google Drive for sharing with partners
3. **Richer GitHub signals** — contributor velocity, issue activity, fork growth
4. **Slack delivery** — weekly briefs pushed to a channel
5. **Historical trend charts** — visualize theme momentum over time
6. **Custom sectors** — add your own focus areas (fintech, healthtech, etc.)

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
                ├── briefings/     # weekly scan outputs
                ├── themes/        # theme drill-down outputs
                ├── companies/     # company backtrace outputs
                ├── github/        # GitHub trending outputs
                └── history/       # theme index for week-over-week
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
