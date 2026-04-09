# VC Signals

> **AI-Powered Investment Theme Discovery for Venture Capital**

A Claude Code skill that turns noisy public internet chatter into ranked, investor-oriented briefs. Run one command per week — get the top emerging themes in **devtools**, **cybersecurity**, and **AI infrastructure** with company mapping, momentum scoring, and a blunt hype-vs-durable verdict.

---

## What is this?

VC Signals is a skill (plugin) for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that acts as your weekly research analyst. It scans Hacker News, Reddit, X/Twitter, GitHub, blogs, and other sources — then synthesizes what it finds into a structured investor brief.

For each emerging theme, you get:

- **Why it's rising** — with evidence and citations
- **Momentum score (1-10)** — how fast is this growing?
- **Confidence rating** — how sure are we this is real?
- **Investment timing** — early, mid, or late?
- **Hype vs durable** — blunt, one-sentence assessment
- **Company mapping** — who's solving this, who benefits, with confidence tags

---

## Installation

### Prerequisites

Before you start, make sure you have:

- **Claude Code** — Anthropic's CLI for Claude. If you don't have it yet:
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```
  Then run `claude` once to authenticate with your Anthropic account.

- **Python 3.12 or newer** — Check with:
  ```bash
  python3 --version
  ```
  If you need to install it (Mac):
  ```bash
  brew install python@3.13
  ```

- **Git** — to clone this repo

### Step 1: Clone the Repository

```bash
git clone https://github.com/abhishek255/vc-signals.git
cd vc-signals
```

### Step 2: Install Python Dependencies

```bash
pip install requests
```

That's it — just one library (for GitHub API calls).

### Step 3: Open Claude Code in the Project

```bash
claude
```

Make sure you're inside the `vc-signals/` directory when you launch Claude Code. The skill is automatically detected from the `.claude/skills/` folder — no extra configuration needed.

### Step 4: Verify it Works

Once inside Claude Code, type:

```
/vc-signals weekly devtools
```

Claude will start running web searches and produce your first investor brief. No API keys needed for the basic version.

---

## Optional: Enhanced Setup

The basic version uses Claude's built-in web search. For **much better results** — with independent Reddit, Hacker News, X/Twitter, and YouTube searches — run the setup wizard:

```
/vc-signals setup
```

The wizard walks you through each API key one at a time. Here's what's available:

| API Key | What it Unlocks | Cost | Required? |
|---------|----------------|------|-----------|
| **GitHub PAT** | Trending repos by star velocity | Free | Recommended |
| **Brave Search** | Broader web search coverage | Free (2,000/month) | Optional |
| **ScrapeCreators** | TikTok, Instagram, YouTube search | ~$29/month | Optional |
| **OpenAI or Gemini** | Query planning for last30days engine | Pay-per-use / Free | Optional |
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

Free tier gives you 2,000 queries/month — more than enough for weekly scans.

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

---

## How It Differs from last30days

| | last30days | vc-signals |
|---|-----------|------------|
| **Purpose** | General research on any topic | VC-specific theme discovery |
| **Output** | Evidence clusters with citations | Investor brief with scoring |
| **Company mapping** | None | Theme → company mapping with roles |
| **Momentum scoring** | None | 1-10 score with transparent factors |
| **Persistence** | Optional save | Week-over-week comparison |
| **GitHub trending** | Basic search | Star velocity + commercial entity mapping |

vc-signals uses last30days as an optional retrieval engine and adds the VC intelligence layer on top.

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

## What's Next

1. **Automated weekly scheduling** — cron or Claude remote triggers
2. **Google Docs export** — save briefings directly to Google Drive
3. **Richer GitHub signals** — contributor velocity, issue activity, fork growth
4. **Slack/email delivery** — weekly briefs pushed to you
5. **Historical trend charts** — visualize theme momentum over time

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
