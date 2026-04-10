---
name: vc-signals
description: "VC signal-to-thesis skill. Discover emerging investable themes in devtools, cybersecurity, and AI infrastructure. Weekly sector scans, theme drill-downs, company backtrace, and GitHub trending repos."
argument-hint: 'vc-signals weekly devtools, vc-signals theme "agent evals", vc-signals company "Confluent", vc-signals github ai-infra, vc-signals setup'
allowed-tools: Bash, Read, Write, WebSearch, AskUserQuestion
user-invocable: true
---

# VC Signals: Emerging Theme Discovery for Venture Capital

Turn noisy public internet chatter into ranked, investor-oriented theme briefs with company mapping.

**This is NOT a generic research tool.** It is a signal-to-thesis skill built for a VC workflow.

## Argument Parsing

Parse the user's input to determine the mode and arguments:

- `/vc-signals setup` → Setup wizard mode
- `/vc-signals weekly <sector>` → Weekly sector scan (sectors: `devtools`, `cybersecurity`, `ai-infra`)
- `/vc-signals theme "<topic>"` → Theme drill-down
- `/vc-signals company "<name>"` → Company backtrace
- `/vc-signals github <sector>` → GitHub trending repos (sectors: `devtools`, `cybersecurity`, `ai-infra`, `all`)
- `/vc-signals compare "<company1>" "<company2>"` → Head-to-head comparison (stretch)

If no arguments or unrecognized arguments, show this help and ask what they'd like to do.

## Script Paths

Before running any script, determine the skill directory. Check these locations in order:
1. `.claude/skills/vc-signals/` (relative to the current project root — check if it exists)
2. `~/.claude/skills/vc-signals/` (global installation for Co-Work)

Once found, use that path for all script commands. For example:
- If found at `.claude/skills/vc-signals/`, run: `python3 .claude/skills/vc-signals/scripts/<script>.py`
- If found at `~/.claude/skills/vc-signals/`, run: `python3 ~/.claude/skills/vc-signals/scripts/<script>.py`

Store the resolved path and reuse it for all script calls in this session.

Scripts:
- `<skill_dir>/scripts/persistence.py` — save/load briefings, diffs, theme index
- `<skill_dir>/scripts/github_trending.py` — GitHub star velocity search
- `<skill_dir>/scripts/last30days_adapter.py` — last30days integration

Config:
- `<skill_dir>/config/sectors.json` — sector taxonomy
- `<skill_dir>/config/company_aliases.json` — company seed map

---

## Mode: Setup Wizard

**Trigger:** `/vc-signals setup`

Walk the user through setup one step at a time. Use plain, non-technical language. Check what's already configured and skip completed steps.

### Step 1: Python Check

```bash
python3 --version
```

If Python 3.12+ is available, say: "Python is ready." and move on.
If not, say: "You need Python 3.12 or newer. Here's how to install it:" and provide instructions for macOS:
```
brew install python@3.13
```

### Step 2: Install Python Dependencies

```bash
pip install requests
```

Say: "Installed the one Python library we need (requests, for GitHub API calls)."

### Step 3: last30days Research Engine

Check availability:
```bash
python3 .claude/skills/vc-signals/scripts/last30days_adapter.py check
```

If not installed, tell the user:
> "The last30days research engine gives us much better results by searching Reddit, Hacker News, X/Twitter, and YouTube independently. Without it, we'll use web search which still works but gives less detailed results."
>
> "Want me to set it up? It takes about 5 minutes and requires a few API keys. Or we can skip this and use web search for now."

If they want to proceed:
```bash
git clone https://github.com/mvanhorn/last30days-skill.git vendor/last30days-skill
```

Then walk them through API keys one at a time:

**ScrapeCreators API Key (required for last30days):**
> "ScrapeCreators lets us search TikTok, Instagram, and YouTube. It's the one required key for last30days."
>
> "Here's how to get it:"
> 1. Go to https://scrapecreators.com
> 2. Sign up for an account
> 3. Go to your dashboard and copy your API key
> 4. Paste it here

**Web Search API Key (pick one -- Brave recommended):**
> "We need a web search API for broader coverage. Brave Search is the easiest -- it has a free tier with 2,000 searches/month."
>
> 1. Go to https://brave.com/search/api/
> 2. Click "Get Started for Free"
> 3. Create an account and get your API key
> 4. Paste it here (or type 'skip' to skip this)

**Reasoning Provider (pick one -- OpenAI or Gemini):**
> "last30days needs an AI provider for query planning and ranking. Either OpenAI or Gemini works."
>
> **OpenAI:**
> 1. Go to https://platform.openai.com/api-keys
> 2. Create a new API key
> 3. You'll need a paid account (usage-based, typically a few cents per query)
>
> **Gemini:**
> 1. Go to https://aistudio.google.com/apikey
> 2. Create a new API key
> 3. Free tier available
>
> "Paste your key here, or type 'skip' to skip (web search mode only)."

**X/Twitter Auth Tokens (optional):**
> "To search X/Twitter for trending developer discussions, we need your browser auth tokens."
>
> 1. Open X/Twitter in your browser and log in
> 2. Open Developer Tools (Cmd+Option+I on Mac)
> 3. Go to Application tab -> Cookies -> twitter.com
> 4. Find the cookie named `auth_token` -- copy its value
> 5. Find the cookie named `ct0` -- copy its value
>
> "This is optional. Skip if you don't use X/Twitter."

### Step 4: GitHub Authentication

Check if `gh` CLI is authenticated:
```bash
gh auth status 2>&1
```

If not, check for GITHUB_TOKEN env var. If neither works:
> "For GitHub trending repos, we need a GitHub Personal Access Token."
>
> 1. Go to https://github.com/settings/tokens
> 2. Click "Generate new token (classic)"
> 3. Give it a name like "vc-signals"
> 4. Select scopes: just `public_repo` is enough
> 5. Generate and copy the token

### Step 5: Save Configuration

Save all collected keys to `~/.config/last30days/.env`:
```bash
mkdir -p ~/.config/last30days
```

Write the .env file with all provided keys. Also save GITHUB_TOKEN to a local config if provided.

Add `SETUP_COMPLETE=true` at the end.

### Step 6: Verify

Run a quick test:
```bash
python3 .claude/skills/vc-signals/scripts/last30days_adapter.py check
```

### Step 7: Summary

Print what's configured and what each unlocks:

> **Setup complete. Here's what's active:**
> - [x] Web search (Brave) -- broad internet coverage
> - [x] GitHub API -- trending repo discovery
> - [ ] last30days (skipped) -- Reddit, HN, X/Twitter, YouTube
>
> **You can run `/vc-signals setup` again anytime to add more capabilities.**
> **Try it out: `/vc-signals weekly devtools`**

---

## Mode: Weekly Sector Scan

**Trigger:** `/vc-signals weekly <sector>`

**Sectors:** `devtools`, `cybersecurity`, `ai-infra`

If sector is not recognized, say so and list valid sectors.

### Step 1: Load Configuration

Read the sector taxonomy:
```bash
cat .claude/skills/vc-signals/config/sectors.json
```

Read the company alias map:
```bash
cat .claude/skills/vc-signals/config/company_aliases.json
```

### Step 2: Check for Previous Briefing (Week-over-Week)

```bash
python3 .claude/skills/vc-signals/scripts/persistence.py load-previous --sector <SECTOR> --before $(date +%Y-%m-%d)
```

If a previous briefing exists, save it for comparison in Step 7.

Also load the theme index to check for durable themes:
```bash
cat <skill_dir>/data/history/theme_index.json 2>/dev/null || echo "{}"
```

Use this to identify themes that have appeared in 3+ consecutive scans — these are candidates for the "Durable" section of the week-over-week comparison.

### Step 3: Select Retrieval Path

```bash
python3 .claude/skills/vc-signals/scripts/last30days_adapter.py check
```

If `installed` AND `configured` are both true -> use **last30days path**.
Otherwise -> use **WebSearch path**.

Tell the user which path you're using:
- "Using last30days for deep multi-source research (Reddit, HN, X, YouTube, web)."
- "Using web search for research. For deeper coverage across Reddit, HN, X, and YouTube, run `/vc-signals setup`."

### Step 4: Retrieve Evidence

**WebSearch path:**

Generate 8-12 search queries from the taxonomy. Use the sector's `discovery_queries` plus queries built from `subcategories` seed_queries. Run each query using the WebSearch tool. Collect all results.

Example query generation for devtools:
1. Use the sector's `discovery_queries` directly (6 queries)
2. Pick the most important seed query from each subcategory (6 queries)
3. Total: ~12 queries

For each query, use WebSearch. Collect titles, URLs, snippets.

**Filtering noise:** Check the sector's `negative_terms` list from the taxonomy config. Skip or deprioritize results that are clearly tutorial content, beginner guides, or consumer product reviews. These terms exist to reduce noise — use them when evaluating search results.

**last30days path:**

Run 3-5 queries through the adapter. Include `x` (X/Twitter) in sources if configured:
```bash
python3 <skill_dir>/scripts/last30days_adapter.py query --topic "<query>" --sources "reddit,hackernews,x,grounding"
```

Use the sector's discovery_queries as topics. For Reddit, target specific subreddits by adding relevant ones to the query (e.g., "CI/CD testing site:reddit.com/r/programming OR site:reddit.com/r/devops"). Collect the normalized items.

**Improving Reddit quality:** If Reddit results are noisy (generic posts, spam), try these approaches:
1. Use more specific topic queries rather than broad sector queries
2. Add the `--subreddits` flag for targeted subreddit search: `--subreddits "programming,devops,ExperiencedDevs,golang,rust,node"`
3. Filter results by engagement — prioritize items with score > 10 or num_comments > 5
4. Fall back to WebSearch with `site:reddit.com/r/programming` for specific subreddit targeting

### Step 5: Retrieve GitHub Trending Data

```bash
python3 .claude/skills/vc-signals/scripts/github_trending.py --sector <SECTOR> --limit 15
```

This runs in addition to the general retrieval. GitHub data feeds into momentum scoring and company mapping.

### Step 6: Synthesize Themes

Now you have all the evidence. This is where your reasoning does the heavy work.

**Extract candidate themes:**
- Read through ALL retrieved evidence (search results, last30days items, GitHub repos)
- Identify recurring topics, problems, technologies, or shifts mentioned across multiple sources
- Name each candidate theme concisely (e.g., "AI-Powered Code Review", "Browser Sandboxing for AI Agents")
- Tag each with the relevant subcategory from the taxonomy

**Cluster and deduplicate:**
- Merge near-duplicate themes. Examples:
  - "AI code review" + "LLM-powered code review" + "automated PR review" -> "AI-Powered Code Review"
  - "shift-left security" + "developer-first security" -> "Developer-First Security Tooling"
- Pick canonical names that are specific enough to be useful, generic enough to cover the cluster

**Score each theme -- Momentum (1-10):**

Assign a transparent momentum score. For each theme, weigh these factors:

| Factor | Weight | What to look for |
|--------|--------|-----------------|
| Recency | High | Are discussions from the last 1-2 weeks? |
| Source diversity | High | Does it appear across multiple independent sources? |
| Repetition density | Medium | How many distinct mentions vs one viral post? |
| Engagement signals | Medium | High upvotes/comments/stars on related content? |
| Novelty | Medium | Is this a NEW conversation or evergreen background chatter? |
| Technical specificity | Low | Specific tools/approaches mentioned vs vague hand-waving? |
| GitHub velocity | Low | Are related repos showing star acceleration? |

Rubric:
- **8-10:** Breakout -- multiple sources, very recent, specific tools named, high engagement, new conversation
- **5-7:** Rising -- clear signal but fewer sources, or overlaps with existing known trends
- **3-4:** Ambient -- mentioned but not clearly accelerating, could be background noise
- **1-2:** Faint -- single source, low engagement, or possibly stale

You MUST explain how you arrived at each score in 1-2 sentences.

**Rate confidence (low / medium / high):**
- **High:** Multiple independent sources, specific evidence, corroborated
- **Medium:** Clear signal but limited sources or partially inferred
- **Low:** Thin evidence, single source, or extrapolated

**Assess investment timing (early / mid / late):**
- **Early:** Problem is being discussed, OSS projects emerging, no clear commercial winners
- **Mid:** Commercial players exist, some funding, category is forming
- **Late:** Well-known category, established players, late-stage rounds

**Hype vs Durable verdict:**
One blunt sentence. Example: "Durable -- real pain point with multiple well-funded solutions." or "Likely hype -- single viral post driving most of the signal, unclear staying power."

### Step 7: Map Companies

For each theme, identify relevant companies using three sources:

1. **Seed map:** Check `company_aliases.json` -- does any known company map to this theme?
2. **Evidence:** Were any companies/projects mentioned in the search results for this theme?
3. **GitHub data:** Do any trending repos from Step 5 relate to this theme?

For each company, classify its role:
- **Direct solver** -- building a product that addresses the theme head-on
- **Beneficiary** -- existing company that gains from the trend
- **Adjacent/ecosystem** -- related but not core
- **Unclear** -- mentioned but relationship is ambiguous

Tag confidence:
- **Confirmed** -- in seed map or multiple sources corroborate
- **Likely** -- strong contextual evidence
- **Inferred** -- your judgment on limited evidence
- **Speculative** -- thin signal, flag as such

**Do NOT:**
- Pretend to know things you don't
- State funding amounts without sourced evidence
- Claim a company is "leading" without backing
- Map a company to a theme just because the names sound related

### Step 8: Format Output

Rank themes by momentum score (descending). Output the top 8-12 themes.

**If previous briefing exists, start with the week-over-week comparison:**

```markdown
## What Changed Since Last Week (YYYY-MM-DD)

**New signals:**
- "Theme Name" (momentum: X) -- not seen before

**Gaining steam:**
- "Theme Name" -- momentum X -> Y

**Fading:**
- "Theme Name" -- momentum X -> Y (or dropped out)

**Durable (3+ weeks):**
- "Theme Name" -- Nth consecutive week, steady at X-Y
```

**Then output each theme:**

```markdown
## Weekly VC Signal Brief: [Sector] -- YYYY-MM-DD

### 1. [Theme Title]

**Momentum: X/10** | **Confidence: High/Medium/Low** | **Timing: Early/Mid/Late**

**Why it's rising:** [2-3 sentences with specific evidence. What changed? Why now?]

**Evidence:**
- [Source 1: title, URL, key quote or data point]
- [Source 2: title, URL, key quote or data point]
- [Source 3 if available]

**Why investors should care:** [1-2 sentences -- what's the opportunity?]

**Hype vs Durable:** [One blunt sentence]

**Companies & Projects:**
| Name | Role | Confidence | Notes |
|------|------|------------|-------|
| Company A | Direct solver | Confirmed | Brief note |
| Company B | Beneficiary | Likely | Brief note |
| OSS Project C | Adjacent | Inferred | Brief note |

---
```

### Step 9: Persist Results

Save the briefing:

Prepare a JSON array of theme objects with all scores and company mappings. Write it to a temp file, then pipe it:

```bash
cat <<'THEMES_EOF' | python3 <skill_dir>/scripts/persistence.py save-briefing --sector <SECTOR> --retrieval-path <websearch|last30days> --date $(date +%Y-%m-%d)
[the JSON themes array goes here]
THEMES_EOF
```

Save the markdown output:
```bash
cat <<'MD_EOF' | python3 <skill_dir>/scripts/persistence.py save-markdown --subdir briefings --slug <SECTOR> --date $(date +%Y-%m-%d)
[the markdown content goes here]
MD_EOF
```

Update the theme index:
```bash
cat <<'THEMES_EOF' | python3 <skill_dir>/scripts/persistence.py update-index --sector <SECTOR> --date $(date +%Y-%m-%d)
[the JSON themes array goes here]
THEMES_EOF
```

If any persistence step fails, warn the user but still display the full briefing inline. Do not crash.

---

## Mode: Theme Drill-Down

**Trigger:** `/vc-signals theme "<topic>"`

### Step 1: Load Config

Read `sectors.json` and `company_aliases.json`.

Check if the topic maps to a known subcategory. If yes, use its seed_queries as starting points. If no, generate queries from scratch.

### Step 2: Retrieve Evidence

Use the same retrieval path selection as weekly scan (check last30days availability).

Run 5-8 targeted queries about the specific theme. Include:
- "[topic] trends emerging"
- "[topic] startups companies"
- "[topic] open source projects github"
- "[topic] hacker news discussion"
- "[topic] why now 2026"
- "[topic] problems challenges"

Also run GitHub trending for related keywords:
```bash
python3 .claude/skills/vc-signals/scripts/github_trending.py --sector all --limit 10
```
(Filter results to those matching the theme in post-processing.)

### Step 3: Synthesize and Output

```markdown
## Theme Deep-Dive: [Topic]

### What Is This?
[2-3 sentence explanation of the theme for someone unfamiliar]

### Why Now?
[What changed recently that made this theme emerge? Be specific -- new tech, new problem, regulatory shift, etc.]

### Key Subthemes
- **Subtheme A:** [1-2 sentences]
- **Subtheme B:** [1-2 sentences]
- **Subtheme C:** [1-2 sentences]

### Evidence
- [Source 1: title, URL, key insight]
- [Source 2: title, URL, key insight]
- [Source 3+]

### Adjacent Categories
- [Related theme 1 -- how it connects]
- [Related theme 2 -- how it connects]

### Companies Solving the Problem
| Name | What They Do | Confidence | Source |
|------|-------------|------------|--------|

### Companies Benefiting From the Trend
| Name | How They Benefit | Confidence |
|------|-----------------|------------|

### Relevant OSS Projects
| Project | Stars | Velocity | Commercial Entity |
|---------|-------|----------|------------------|

### Durable vs Hype
[Blunt, honest assessment. 2-3 sentences. What could make this fade? What would confirm it's real?]

### Investment Implications
- **Timing:** Early/Mid/Late
- **What to watch for:** [Specific signals that would confirm or invalidate this theme]
- **Biggest risk:** [One sentence]
```

### Step 4: Persist

```bash
cat <<'MD_EOF' | python3 <skill_dir>/scripts/persistence.py save-markdown --subdir themes --slug <SLUGIFIED_TOPIC> --date $(date +%Y-%m-%d)
[the markdown content goes here]
MD_EOF
```

---

## Mode: Company Backtrace

**Trigger:** `/vc-signals company "<name>"`

### Step 1: Check Seed Map

Read `company_aliases.json`. Check if the company exists. If yes, note its known themes, sectors, and OSS projects.

### Step 2: Retrieve Evidence

Run 4-6 queries:
- "[company name] trends news"
- "[company name] product updates"
- "[company name] competitors market"
- "[company name] open source projects"
- "[company name] funding investment"

If the company has known OSS projects from the seed map, also search for those.

Check GitHub:
```bash
python3 .claude/skills/vc-signals/scripts/github_trending.py --sector all --limit 30
```
Filter for repos owned by or related to the company.

### Step 3: Map to Rising Themes

Cross-reference the evidence against:
1. Known themes from previous weekly scans (load recent briefings)
2. Themes apparent from current evidence
3. Seed map themes

### Step 4: Output

```markdown
## Company Backtrace: [Company Name]

### Overview
[What the company does, 2-3 sentences]

### Theme Exposure
| Rising Theme | Role | Confidence | Evidence |
|-------------|------|------------|----------|
| Theme A | Direct solver | Confirmed | [Brief evidence] |
| Theme B | Beneficiary | Likely | [Brief evidence] |

### OSS / Ecosystem Signals
- [Project 1: stars, velocity, relevance]
- [Project 2 if applicable]

### Competitive Context
[Brief note on who else operates in the same themes. NOT a full competitive analysis -- just enough for context.]

### Confidence Notes
[What you're confident about, what's uncertain, what you couldn't verify]
```

### Step 5: Persist

```bash
cat <<'MD_EOF' | python3 <skill_dir>/scripts/persistence.py save-markdown --subdir companies --slug <SLUGIFIED_NAME> --date $(date +%Y-%m-%d)
[the markdown content goes here]
MD_EOF
```

---

## Mode: GitHub Trending

**Trigger:** `/vc-signals github <sector>`

### Step 1: Run GitHub Trending Script

```bash
python3 .claude/skills/vc-signals/scripts/github_trending.py --sector <SECTOR> --limit 15
```

If `sector` is `all`, run for each sector and merge results.

### Step 2: Enrich with Company Mapping

For each repo in the results:
1. Check `company_aliases.json` -- is the owner/org a known company?
2. Check the repo owner type -- is it an organization (likely a company)?
3. Use your knowledge + the repo description to identify if there's a commercial entity behind it

### Step 3: Map to Themes

For each repo, identify which sector themes it relates to. Use the taxonomy subcategories and your judgment.

### Step 4: Output

```markdown
## GitHub Trending: [Sector] -- YYYY-MM-DD

Repos ranked by star velocity (recent growth rate, not absolute count).

| # | Repo | Stars | 7d Growth | 30d Growth | Language | Commercial Entity |
|---|------|-------|-----------|------------|----------|------------------|
| 1 | owner/name | 12,500 | +450 | +1,800 | Rust | Company Name (Confirmed) |
| 2 | ... | | | | | |

### Standout Repos

**[Repo 1: owner/name]**
- **Description:** [What it does]
- **Why it's interesting:** [1-2 sentences -- what's driving the growth?]
- **Theme mapping:** [Which sector themes this relates to]
- **Commercial entity:** [Company behind it, if any. Monetization status if known.]

**[Repo 2: owner/name]**
...

### Acceleration Alerts
[Repos with unusually high velocity relative to their size -- the "0 to 10k in a week" signals]

### Theme Patterns
[Do multiple trending repos point to the same emerging theme? Call it out.]
```

### Step 5: Persist

```bash
cat <<'MD_EOF' | python3 <skill_dir>/scripts/persistence.py save-markdown --subdir github --slug <SECTOR> --date $(date +%Y-%m-%d)
[the markdown content goes here]
MD_EOF
```

---

## Graceful Degradation

At every step, handle failures gracefully:

1. **last30days not available:** Use WebSearch. Say so. Still produce useful output.
2. **GitHub API rate limited:** Use partial results. Warn the user. Suggest running again later.
3. **GitHub token missing:** Say "GitHub trending requires a token. Run `/vc-signals setup` to configure one." Still run the rest of the scan.
4. **Persistence fails:** Display full output inline. Warn that it wasn't saved. Do not crash.
5. **WebSearch returns thin results:** Note limited coverage. Still extract what themes you can. Be honest about confidence.
6. **Unknown sector:** List valid sectors. Don't guess.
7. **No previous briefing for comparison:** Skip the week-over-week section. Say "This is your first scan for [sector]. Future scans will include week-over-week comparisons."

**Never crash. Never pretend you have data you don't. Always tell the user what worked and what didn't.**
