# VC Signals

A Claude Code skill that helps VCs discover emerging investable themes in **devtools**, **cybersecurity**, and **AI infrastructure**.

Run one command per week. Get a ranked list of emerging themes with company mapping, momentum scoring, and investor-oriented analysis.

## What This Is

`/vc-signals` turns noisy public internet chatter (Hacker News, Reddit, X/Twitter, GitHub, blogs) into a structured investor brief. For each emerging theme, you get:

- Why it's rising (with evidence and citations)
- Momentum score (1-10) — how fast is this growing?
- Confidence rating — how sure are we this is real?
- Investment timing — early, mid, or late?
- Hype vs durable — blunt assessment
- Company mapping — who's solving this, who benefits, with confidence tags

## Quick Start (Zero Setup)

Works immediately with no API keys. Claude uses its built-in web search.

```
/vc-signals weekly devtools
/vc-signals weekly cybersecurity
/vc-signals weekly ai-infra
```

For better coverage (Reddit, HN, X, YouTube independently), run the setup wizard:

```
/vc-signals setup
```

## All Commands

| Command | What It Does |
|---------|-------------|
| `/vc-signals setup` | Guided setup wizard — walks you through API keys step by step |
| `/vc-signals weekly <sector>` | Weekly scan — top 8-12 emerging themes with company mapping |
| `/vc-signals theme "<topic>"` | Deep-dive into a specific theme |
| `/vc-signals company "<name>"` | Which rising themes is a company exposed to? |
| `/vc-signals github <sector>` | Top repos by star velocity — spot fast-growing OSS projects |

**Sectors:** `devtools`, `cybersecurity`, `ai-infra`

## Examples

### Weekly Sector Scan
```
/vc-signals weekly devtools
```
Returns 8-12 ranked themes like:
- "AI-Powered Code Review" (momentum: 8/10, timing: mid, companies: CodeRabbit, Cursor)
- "Rust-Based Build Tooling" (momentum: 6/10, timing: early, companies: Turbopack, oxc)

### Theme Drill-Down
```
/vc-signals theme "agent evals"
```
Returns deep analysis: what it is, why now, subthemes, companies solving it, OSS projects, hype vs durable verdict.

### Company Backtrace
```
/vc-signals company "Confluent"
```
Returns which rising themes Confluent maps to, its role (solver vs beneficiary), evidence, and competitive context.

### GitHub Trending
```
/vc-signals github ai-infra
```
Returns top repos by star velocity — the ones growing fastest relative to their size, with commercial entity mapping.

## How It Differs from last30days

| | last30days | vc-signals |
|---|-----------|------------|
| **Purpose** | General research on any topic | VC-specific theme discovery |
| **Output** | Evidence clusters with citations | Investor brief with scoring |
| **Company mapping** | None | Theme → company mapping with roles |
| **Momentum scoring** | None | 1-10 score with transparent factors |
| **Persistence** | Optional save | Week-over-week comparison |
| **GitHub trending** | Basic search | Star velocity + commercial entity mapping |

vc-signals uses last30days as a retrieval engine (when configured) and adds the VC intelligence layer on top.

## Full Setup Guide

### Prerequisites

- **Claude Code** — installed and working
- **Python 3.12+** — check with `python3 --version`

### Step 1: Install Python dependency

```bash
pip install requests
```

### Step 2: Run the setup wizard

```
/vc-signals setup
```

The wizard walks you through everything. Here's what each API key unlocks:

### API Keys Reference

#### ScrapeCreators API Key (for last30days)
- **What it unlocks:** TikTok, Instagram, YouTube search via last30days
- **Required for:** last30days enhanced retrieval path
- **Cost:** Paid plans starting at ~$29/month
- **How to get it:**
  1. Go to https://scrapecreators.com
  2. Sign up for an account
  3. Choose a plan (Basic is fine for weekly scans)
  4. Go to Dashboard → API Keys → copy your key

#### Brave Search API Key
- **What it unlocks:** Broad web search coverage
- **Required for:** last30days web search (or use Exa/Serper as alternatives)
- **Cost:** Free tier — 2,000 queries/month (plenty for weekly scans)
- **How to get it:**
  1. Go to https://brave.com/search/api/
  2. Click "Get Started for Free"
  3. Create an account
  4. Go to API Keys → copy your key

#### OpenAI API Key (or Gemini)
- **What it unlocks:** Query planning and result ranking in last30days
- **Required for:** last30days enhanced retrieval path
- **Cost:** Usage-based — typically $0.01-0.05 per weekly scan
- **How to get it (OpenAI):**
  1. Go to https://platform.openai.com/api-keys
  2. Sign up or log in
  3. Click "Create new secret key"
  4. Copy the key (starts with `sk-`)
  5. Add a payment method under Billing
- **How to get it (Gemini — free alternative):**
  1. Go to https://aistudio.google.com/apikey
  2. Click "Create API key"
  3. Copy the key

#### GitHub Personal Access Token
- **What it unlocks:** GitHub trending repos — star velocity, repo search
- **Required for:** `/vc-signals github` mode
- **Cost:** Free
- **How to get it:**
  1. Go to https://github.com/settings/tokens
  2. Click "Generate new token" → "Generate new token (classic)"
  3. Name: "vc-signals"
  4. Expiration: 90 days (or your preference)
  5. Scopes: check `public_repo` only
  6. Click "Generate token" and copy it

#### X/Twitter Auth Tokens (optional)
- **What it unlocks:** X/Twitter search for developer discussions
- **Required for:** last30days X/Twitter source
- **Cost:** Free (uses your existing X account)
- **How to get them:**
  1. Log into X/Twitter in your browser (Chrome/Firefox)
  2. Open Developer Tools: `Cmd+Option+I` (Mac) or `Ctrl+Shift+I` (Windows)
  3. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
  4. Click **Cookies** → **twitter.com** (or **x.com**)
  5. Find `auth_token` — copy its Value
  6. Find `ct0` — copy its Value
  7. These expire periodically — you'll need to re-extract them

### What Works Without Any API Keys

The zero-config path uses Claude's built-in WebSearch. You get:
- Weekly sector scans (slightly less source diversity)
- Theme drill-downs
- Company backtrace
- GitHub trending (if you have a GitHub token or `gh` CLI)

## Architecture

```
SKILL.md (orchestrator)
    │
    ├── Retrieval Layer
    │   ├── WebSearch (built-in, zero-config)
    │   └── last30days (enhanced, after setup)
    │
    ├── GitHub Trending
    │   └── github_trending.py (star velocity via API)
    │
    ├── Intelligence Layer (Claude)
    │   ├── Theme extraction & clustering
    │   ├── Momentum scoring
    │   ├── Company mapping
    │   └── Investor framing
    │
    └── Persistence Layer
        └── persistence.py (save/load/diff briefings)
```

**Claude is the intelligence engine.** Python scripts handle I/O only (API calls, file storage). The SKILL.md orchestrates everything.

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

Add a new top-level key to `sectors.json` following the existing structure.

## Known Limitations

- **WebSearch path** gives less structured data than last30days (no per-source isolation)
- **GitHub star velocity** is approximated — no historical time series without a third-party service
- **Company seed map** starts with ~40 entries — coverage improves as you add companies
- **No automated scheduling** — you run scans manually each week
- **Momentum scoring** is heuristic, not statistically rigorous — transparency over precision

## What's Next

1. **Automated weekly scheduling** — cron or Claude remote triggers
2. **Google Docs export** — save briefings directly to Google Drive
3. **Richer GitHub signals** — contributor velocity, issue activity, fork growth
4. **Slack/email delivery** — weekly briefs pushed to you
5. **Historical trend charts** — visualize theme momentum over time

## Project Structure

```
.
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
            ├── SKILL.md           # skill definition
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
