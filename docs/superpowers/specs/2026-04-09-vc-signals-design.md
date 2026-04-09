# VC Signals — Design Spec

**Date:** 2026-04-09
**Status:** Approved
**Author:** Claude + Abhishek

## Overview

A Claude Code skill (`/vc-signals`) that helps a VC discover emerging investable themes in devtools, cybersecurity, and AI infrastructure. It turns noisy public internet chatter into ranked, investor-oriented theme briefs with company mapping.

This is NOT a generic research skill. It is a **signal-to-thesis** tool — purpose-built for a VC workflow.

## Key Decisions

- **Claude-orchestrated (Approach B: Dual-Path Retrieval):** `last30days` handles retrieval when configured; Claude's built-in WebSearch is the zero-config fallback. Claude does all theme extraction, clustering, scoring, company mapping, and investor framing.
- **Progressive enhancement:** Works day one with zero API keys. Progressively better as the user adds keys via setup wizard.
- **GitHub trending as standalone + integrated signal:** Available as its own mode (`/vc-signals github <sector>`) AND as a momentum signal within weekly sector scans.
- **Output:** Inline in conversation (always) + saved to local files (when possible). Inline-only fallback for environments without file access (e.g., Co-Work).
- **Setup wizard:** Guided, non-technical walkthrough for all API keys and dependencies.

## Architecture

### Three-Layer Design

```
+---------------------------------------------------+
|              SKILL.md (Orchestrator)               |
|  Parses args -> selects retrieval path ->          |
|  instructs Claude to extract themes, cluster,      |
|  score, map companies, frame for investors         |
+--------+--------------+--------------+-------------+
         |              |              |
    +----v----+   +-----v-----+  +----v------+
    |Retrieval|   | GitHub    |  |Persistence|
    |  Layer  |   | Trending  |  |  Layer    |
    +----+----+   +-----+-----+  +-----+----+
         |              |              |
   +-----v-----+  +-----v-----+ +-----v-----+
   |WebSearch   |  |gh CLI /   | |Python:    |
   |(built-in)  |  |GitHub API | |save/load/ |
   |     OR     |  |star data  | |diff JSON  |
   |last30days  |  +-----------+ +-----------+
   |(if config'd|
   +------------+
```

**Key principle:** Claude is the intelligence engine. Python scripts are I/O utilities. SKILL.md is the playbook.

### Retrieval Path Selection

1. Check if `last30days` is installed and configured (look for `~/.config/last30days/.env` with `SETUP_COMPLETE=true` and at least one reasoning provider key)
2. If yes: use `last30days_adapter.py` to run structured queries, get back JSON
3. If no: use Claude's WebSearch tool with sector-specific queries from taxonomy

If any command is run before setup: Claude detects missing config and says "I can still give you results using web search, but for better coverage run `/vc-signals setup` first. Want me to proceed anyway or set up first?"

## Modes & Command Grammar

### `/vc-signals setup`

Guided setup wizard. Walks user through one item at a time:

1. **Python check** — verify Python 3.12+ is available
2. **last30days installation** — clone repo, install deps
3. **API keys, one by one**, with plain-English explanations:
   - What each key unlocks, whether it's free or paid, signup URL, which plan to pick
   - User can skip any key — Claude notes what will be unavailable
4. **GitHub auth** — check if `gh` CLI works or PAT exists
5. **Save config** — writes to `~/.config/last30days/.env` and local config
6. **Verify** — runs a quick test query
7. **Summary** — what's active, what's skipped, re-run anytime

### `/vc-signals weekly <sector>`

Sectors: `devtools`, `cybersecurity`, `ai-infra`

Output: 8-12 ranked emerging themes, each with:
- Theme title
- Why it's rising (evidence-backed)
- Momentum score (1-10) with transparent derivation
- Confidence score (low / medium / high)
- Investment timing (early / mid / late)
- Hype vs durable assessment (blunt, one sentence)
- Mapped companies / OSS projects (with role: solver, beneficiary, adjacent)
- Key sources / citations

Also includes week-over-week comparison when prior data exists (new themes, fading themes, accelerating themes, persistent themes).

Saved to: `data/briefings/YYYY-MM-DD-<sector>.md` + `.json`

### `/vc-signals theme "<topic>"`

Input: any theme string (doesn't need to match taxonomy)

Output:
- Deep analysis of the theme
- Why now — what changed recently
- Key subthemes
- Evidence from recent sources
- Adjacent categories
- Companies solving the problem (with confidence)
- Companies benefiting from the trend
- Relevant OSS projects
- Founders / commercial entities if inferable
- Durable vs hype verdict

Saved to: `data/themes/YYYY-MM-DD-<slug>.md`

### `/vc-signals company "<name>"`

Output:
- Which rising themes the company maps to
- Role classification (direct solver, beneficiary, adjacent, unclear)
- Evidence for each mapping
- Confidence rating per theme
- Related OSS / ecosystem signals
- Brief competitive context if apparent

Saved to: `data/companies/YYYY-MM-DD-<slug>.md`

### `/vc-signals github <sector>`

Sectors: `devtools`, `cybersecurity`, `ai-infra`, or `all`

Output:
- Top 10-15 repos by star velocity (recent growth rate, not absolute count)
- For each repo: name, description, stars, star growth (weekly/monthly), primary language, last commit
- Commercial entity mapping (who's behind it, is there a company, is it monetized)
- Which sector themes it maps to
- Rate-of-change emphasis — flag repos with unusual acceleration

Saved to: `data/github/YYYY-MM-DD-<sector>.md`

### `/vc-signals compare "<company1>" "<company2>"` (optional MVP stretch)

Only built if core modes are solid. Side-by-side theme exposure, evidence comparison, differentiation.

## Retrieval Strategy

### WebSearch Path (zero-config default)

For each mode, Claude runs ~8-12 structured WebSearch queries derived from the sector taxonomy. Multiple targeted queries beat one broad query:
- "emerging devtools trends 2026"
- "developer tools gaining traction site:news.ycombinator.com"
- "new CI/CD tools developers switching to 2026"
- "devtools startups funding 2026"
- Queries generated from taxonomy seed terms

Claude collects all results, then synthesizes themes across them.

### last30days Path (enhanced, after setup)

`last30days_adapter.py` runs `pipeline.run()` with structured queries. Advantages:
- Source-level isolation (Reddit vs HN vs X)
- Engagement data (upvotes, likes, comment counts)
- Structured output (schema.Report with clusters, candidates, scores)
- More sources searched independently

Adapter runs 3-5 queries per sector scan, returns merged JSON.

### GitHub Trending (both paths)

`github_trending.py` uses GitHub Search API (PAT or `gh` CLI):
1. Searches repos matching taxonomy keywords per sector
2. Queries star history (stars gained in last 7 and 30 days)
3. Calculates velocity: `stars_gained_last_7d / total_stars` as acceleration ratio
4. Returns structured JSON

**Star velocity measurement:** GitHub API doesn't expose "stars gained last week" directly. The script uses the Stargazers API with `Accept: application/vnd.github.v3.star+json` header to get timestamped star events, then counts recent ones. This is paginated — for repos with many stars, the script samples the most recent pages rather than paginating through all history. For repos where this is too slow or rate-limited, the script falls back to total star count + repo creation date to estimate average growth rate (less accurate but always available).

Rate limit awareness: GitHub API has 30 search requests/min and 5000 requests/hour for authenticated users. The script batches queries, respects limits, and returns partial results with a warning if rate-limited.

### Query Generation

Queries generated from sector taxonomy config, not hardcoded. For each sector the taxonomy defines:
- Subcategories with aliases
- Seed queries per subcategory
- Discovery queries (broad, for catching themes outside known subcategories)
- Negative terms (filter out noise)

Claude adapts queries based on early results (e.g., if first-pass mentions "AI code review," Claude adds a follow-up query).

## Theme Extraction, Clustering & Scoring

All done by Claude's reasoning — no ML, no embeddings.

### Theme Extraction

Claude reads all evidence, identifies recurring topics/problems/shifts across sources, names each candidate theme concisely, tags with sector and subcategory.

### Clustering / Deduplication

Claude merges near-duplicate themes using judgment:
- "AI code review tools" + "LLM-powered code review" + "automated PR review" -> "AI-Powered Code Review"
- Canonical name: specific enough to be useful, generic enough to cover the cluster

### Momentum Scoring (1-10)

Transparent — Claude explains derivation. Factors:

| Factor | Weight | Signal |
|--------|--------|--------|
| Recency | High | Discussions from last 1-2 weeks vs older |
| Source diversity | High | Multiple independent sources |
| Repetition density | Medium | Many distinct mentions vs one viral post |
| Engagement signals | Medium | High upvotes/comments/stars |
| Novelty | Medium | New conversation vs evergreen chatter |
| Technical specificity | Low | Specific tools/approaches vs vague |
| GitHub velocity | Low | Related repos showing star acceleration |

Rubric:
- **8-10:** Breakout — multiple sources, very recent, specific, high engagement, new
- **5-7:** Rising — clear signal but fewer sources or overlaps with known trends
- **3-4:** Ambient — mentioned but not clearly accelerating
- **1-2:** Faint — single source, low engagement, possibly stale

### Confidence Rating

Separate from momentum. How sure Claude is the theme is real:
- **High:** Multiple independent sources, specific evidence, corroborated
- **Medium:** Clear signal but limited sources or partially inferred
- **Low:** Thin evidence, single source, or extrapolated

### Investment Timing

- **Early:** Problem discussed, OSS emerging, no clear commercial winners
- **Mid:** Commercial players exist, some funding, category forming
- **Late:** Well-known category, established players, late-stage rounds

## Company Mapping

Three layers, most to least reliable:

### Layer 1: Curated Seed Map (`company_aliases.json`)

~30-50 seed entries across three sectors. Hand-maintained, high confidence. Structure:

```json
{
  "Confluent": {
    "aliases": ["confluent", "confluent.io"],
    "oss_projects": ["Apache Kafka"],
    "sectors": ["devtools", "ai-infra"],
    "themes": ["streaming data infrastructure"]
  }
}
```

Users can edit directly.

### Layer 2: Evidence-Based Extraction

Claude identifies company/project mentions in search results. For each:
- Company/project name
- Context (what was said)
- Source URL
- Role: direct solver, beneficiary, adjacent/ecosystem, unclear

### Layer 3: GitHub -> Commercial Entity Mapping

For GitHub trending mode. Claude checks:
- Repo org/owner (company GitHub org?)
- README links (commercial website?)
- "Enterprise" or "pricing" pages
- Claude's knowledge + search for company behind project

### Confidence Tags

Every company mapping gets:
- **Confirmed:** In seed map or multiple sources corroborate
- **Likely:** Strong contextual evidence, one clear source
- **Inferred:** Claude's judgment on limited evidence
- **Speculative:** Thin signal, flagged as such

### Principles

Claude does NOT:
- Pretend to know things it doesn't
- State funding amounts without sourced evidence
- Claim "leading" without backing
- Map company to theme just because names sound related

## Persistence & Week-over-Week Comparison

### Directory Structure

```
.claude/skills/vc-signals/data/
+-- briefings/          # weekly scan outputs (.md + .json)
+-- themes/             # theme drill-down outputs
+-- companies/          # company backtrace outputs
+-- github/             # GitHub trending outputs
+-- history/
    +-- theme_index.json  # running theme ledger
```

### Briefing JSON Structure

```json
{
  "date": "2026-04-09",
  "sector": "devtools",
  "retrieval_path": "websearch",
  "themes": [
    {
      "name": "AI-Powered Code Review",
      "momentum": 8,
      "confidence": "high",
      "timing": "mid",
      "hype_vs_durable": "durable",
      "companies": [
        {"name": "CodeRabbit", "role": "direct_solver", "confidence": "confirmed"}
      ],
      "evidence_summary": "..."
    }
  ]
}
```

### Theme Index (`history/theme_index.json`)

Running ledger tracking every theme ever seen:

```json
{
  "AI-Powered Code Review": {
    "first_seen": "2026-03-15",
    "last_seen": "2026-04-09",
    "appearances": 4,
    "sectors": ["devtools"],
    "momentum_history": [6, 7, 7, 8],
    "peak_momentum": 8
  }
}
```

### Week-over-Week Diff

`persistence.py` computes from current + previous briefing JSON:
- **New this week:** themes present now but not last scan
- **Fading:** themes that dropped out or lost 3+ momentum points
- **Accelerating:** themes that gained 2+ momentum points
- **Persistent:** themes appearing 3+ consecutive weeks

Included at top of each weekly briefing when prior data exists.

### Graceful Degradation

If file writes fail (Co-Work, permissions):
- Full briefing still printed inline
- Warning: "I couldn't save this briefing locally. Run `/vc-signals setup` to configure local storage."
- No crash

## Sector Taxonomy

Single `config/sectors.json` file defining three sectors with:
- Display name
- Subcategories (each with name, aliases, seed queries)
- Discovery queries (broad, for catching themes outside known subcategories)
- Negative terms (filter noise)

Sectors: devtools (6 subcategories), cybersecurity (6 subcategories), ai-infra (6 subcategories).

Users can edit to add subcategories, queries, or entirely new sectors.

## File Structure

```
/Users/abhishekgarg/personalProject/
+-- README.md
+-- vendor/
|   +-- last30days-skill/
+-- .claude/
    +-- skills/
        +-- vc-signals/
            +-- SKILL.md
            +-- scripts/
            |   +-- requirements.txt     # requests only
            |   +-- github_trending.py
            |   +-- persistence.py
            |   +-- last30days_adapter.py
            +-- config/
            |   +-- sectors.json
            |   +-- company_aliases.json
            +-- data/
                +-- briefings/
                +-- themes/
                +-- companies/
                +-- github/
                +-- history/
                    +-- theme_index.json
```

### Script Responsibilities

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `github_trending.py` | GitHub API queries for repos, compute star velocity | sector, config path | JSON: repos with stars, velocity, owner |
| `persistence.py` | Save/load briefings, compute week-over-week diffs | mode, paths, JSON data | Saved files or diff JSON |
| `last30days_adapter.py` | Detect last30days, run queries through pipeline, normalize | query, config | JSON: normalized evidence items |

### Dependencies

- Python 3.12+ (stdlib only, except `requests`)
- `requests` — GitHub API calls
- `last30days` pipeline — optional, imported from vendored path when available

## Known Limitations (MVP)

- WebSearch path gives less structured data than last30days (no per-source isolation)
- GitHub star velocity approximated from API data (no historical star-count time series without third-party service)
- Company seed map starts with ~30-50 entries — coverage improves over time
- No automated scheduling — user runs manually each week
- Compare mode is a stretch goal, may not ship in MVP
- Momentum scoring is heuristic, not statistically rigorous

## Next Steps After MVP

1. Automated weekly scheduling (cron or Claude remote triggers)
2. Google Docs export for briefings
3. Richer GitHub data (contributor velocity, issue activity, fork growth)
4. Slack/email delivery of weekly briefs
5. Fourth sector support (user-defined)
6. Compare mode if not built in MVP
7. Historical trend visualization (simple charts)
