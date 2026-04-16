# VC Signals — Product Context & Roadmap

**Last updated:** 2026-04-16
**Status:** Pivoting from trend newsletter to company radar

---

## The Product

VC Signals is a Claude Code skill (`/vc-signals`) that helps VCs and angel investors discover emerging investable themes and companies in devtools, cybersecurity, and AI infrastructure.

**Repo:** https://github.com/abhishek255/vc-signals
**Primary user:** Alex (VC at a fund), uses Claude Code locally
**Secondary users:** Other VCs/angels, some on Claude Co-Work (web)

---

## The Pivot: Trend Newsletter → Company Radar

### What we built (v1)
A weekly trend scanner that outputs 8-12 themes per sector with company mapping as a secondary feature. Themes are the centerpiece, companies are accessories.

### What we learned
1. **Alex's feedback (April 14, 2026):** Every piece of feedback was about companies, not themes — more companies (10-15 not 5-6), company enrichment (funding, headcount from Attio CRM), company filtering (founded since 2022, raised <$100M), deeper theme analysis, persistence over time, and Slack delivery.

2. **Showrun competitive analysis (April 15, 2026):** Showrun is a competing Claude Code skill (`cdp_taskpacks` by dev/karacasoft) that takes a natural language VC thesis and finds matching companies. It uses PitchBook for funding data, LinkedIn Sales Navigator for founder/headcount verification, and GitHub for OSS validation. Its output is a pure company table — no themes at all. Takes ~20 minutes to run but produces deeply enriched company data.

### The core insight
**VCs don't invest in trends. They invest in companies.** Themes are useful context but companies are the product. Our output should flip from "themes with companies attached" to "companies organized by themes."

---

## Alex's Feedback (verbatim, April 14, 2026)

### Data Sources
- Why list Reddit/HN separately from web search if they're publicly available?
- Should we list specific sources (e.g., PYMNTS.com)?
- What is excluded from web search?
- **Answer we gave:** Reddit/HN are searched via APIs with engagement data (upvotes, comments) — that's what powers momentum scoring. Web search returns whatever Google ranks, no engagement signal.

### Integrations
- Can we integrate Attio (their CRM)?
- Pull funding data, headcount data to enrich companies
- Use headcount/funding to filter (only show companies founded since 2022, raised <$100M)
- **Answer we gave:** Yes, Attio has an API and MCP server. Can build enrichment + filtering.

### Trends
- Good and directionally right, but wants to go deeper
- "OpenTelemetry-Native Observability has been around for a while — what's the sub-item really being discussed?"
- Wants to guide scope (focus on payments within fintech)
- Wants persistence — how often discussed? New this week or around for months?
- **Answer we gave:** Theme drill-down exists (`/vc-signals theme "X"`). Can add `--focus` parameter. Persistence data exists in theme_index.json but isn't surfaced well enough.

### Companies
- Shows ~5-6 per trend, wants 10-15
- What's the logic for which companies show up?
- **Answer we gave:** 3 layers (seed map, evidence extraction, GitHub). Can bump to 10-15.

### UI/Display
- Toggle industry with dropdown? (Not possible in CLI)
- Outputs to Slack on a regular cadence (Monday AM at noon)?
- **Answer we gave:** Can do via `/schedule` and Slack MCP connector.

---

## Showrun Competitive Analysis (April 15, 2026)

### What Showrun is
A Claude Code skill by dev/karacasoft that finds specific companies matching a VC thesis. User types natural language like: "Dev tools startups, pre-series B, where the founding CTO previously shipped a widely-used open source project (10k+ stars on github). Check LinkedIn to confirm the CTO is still actively at the company and pull their team's recent hires."

### How it works
1. Plans a multi-step research pipeline
2. Runs PitchBook advanced search for company screening
3. Runs GitHub API for OSS star verification
4. Scrapes LinkedIn Sales Navigator via Chrome CDP for founder/headcount
5. Takes ~20 minutes
6. Outputs a structured table: Company, GitHub URL, SaaS description, Last Round, Headcount, Latest Investor, Headcount Class

### Where Showrun is better
- Real funding data (PitchBook)
- Real headcount (LinkedIn)
- Founder verification (confirms CTO is still at company)
- Natural language query — any criteria, any filter
- Investor names and round details
- Company-centric output

### Where we're better
- Speed (3-5 min vs 20 min)
- Theme discovery (they require you to already have a thesis)
- Breadth (8-12 themes per sector vs 10 companies per query)
- Week-over-week persistence
- Zero-setup (works without PitchBook/LinkedIn licenses)
- Source diversity (Reddit, HN, X, YouTube, GitHub, web)
- Accessibility (non-technical VC can use it)

### Key takeaway
Showrun = "I have a thesis, find matching companies." VC Signals = "I don't know what to look for, show me what's emerging." They're complementary. Ideal workflow: VC Signals surfaces themes → VC picks one → runs Showrun-style query.

---

## New Product Vision

### Output hierarchy (new)
```
Themes (3 lines each, brief context)
    → COMPANY RADAR (30-50 companies, THE main output)
        → Deep dives on demand (any company or theme)
```

### Three modes (new)

**1. Weekly Radar** (restructured weekly scan)
```
/vc-signals radar devtools
```
- Themes as brief headers (3 lines, not 30)
- Company table as centerpiece (30-50 companies, not 5-6 per theme)
- Columns: Company, Theme, Stage, Raised, Headcount, Traction Signal, In Pipeline?
- New/Accelerating/Faded tags on COMPANIES, not just themes
- Trend age on theme headers

**2. Thesis Search** (new, inspired by Showrun)
```
"Find me AI security startups, seed to Series A, with OSS projects, founded since 2023"
```
- Natural language, no slash command required
- Claude interprets thesis, searches for matching companies
- Returns enriched company table
- Works with whatever data sources are available

**3. Deep Dive** (existing theme + company modes, unified)
```
/vc-signals deep "MintMCP"
/vc-signals deep "MCP Agent Infrastructure"
```
- Works for both companies AND themes
- Company: founder background, funding history, product, competition
- Theme: subthemes, why now, full company landscape

### Ideal weekly output format
```
## VC Radar: Devtools — Week of April 14

### What's Moving (3 lines per theme)
- MCP Agent Infrastructure — NEW. 97M SDK downloads, every AI vendor adopted.
- AI Testing Automation — UP (6→8). Testing bottleneck worsening.
- Supply Chain Attacks — PERSISTENT (6 weeks). LiteLLM fallout continues.

### Company Radar (38 companies across 8 themes)

| Company | Theme | Stage | Raised | Headcount | Traction Signal | In Pipeline? |
|---------|-------|-------|--------|-----------|----------------|--------------|
| MintMCP | MCP Infra | Seed | $4M | 12 | First SOC2 MCP gateway | No |
| CodeRabbit | AI Review | Series A | $15M | 45 | 2M repos, 13M PRs | Met 3/15 |
| BaseRock.ai | AI Testing | Pre-seed | $2M | 8 | Launched 2 weeks ago | No |

### New to Radar
- MintMCP: MCP gateway — enterprise auth/governance for AI agents
- BaseRock.ai: AI-native test generation — founded 6 months ago

### Faded Off
- OldCo: was in "WebAssembly Runtimes" — theme itself faded
```

---

## Implementation Phases

### Phase 1: Flip the output (1-2 days)
- Restructure weekly scan: themes become brief headers, company table becomes centerpiece
- Increase company count to 15-20 per sector across all themes
- Add consolidated company table at the bottom
- Add NEW/Accelerating/Faded tags on companies
- Add trend age to theme headers

### Phase 2: Company enrichment via WebSearch (3-5 days)
- For each company found, run targeted WebSearch queries:
  - `"company name" crunchbase funding` → extract funding data
  - `"company name" linkedin headcount` → extract headcount signals
  - `"company name" founded year` → founding date
  - `"company name" founder CTO` → founder names
- No API keys needed — just smarter search queries
- This closes the biggest gap vs Showrun without requiring PitchBook

### Phase 3: Natural language thesis search (1-2 days)
- Detect when user types a thesis instead of a slash command
- Parse criteria (stage, sector, founding date, OSS traction)
- Run targeted searches, return company table
- Example: "Find me cybersecurity startups focused on AI agent security, pre-series B"

### Phase 4: Attio CRM integration (3-5 days)
- Connect via Attio MCP server
- "In Your Pipeline?" column in company radar
- Filter: "only show companies NOT in my pipeline"
- Enrich with Attio data when available (funding, headcount, deal stage, notes)
- This is the lock-in feature — connects discovery to deal flow

### Phase 5: Slack delivery (1-2 days)
- Schedule weekly radar via `/schedule`
- Post summary + full brief to Slack channel
- Monday AM delivery

---

## What to Kill in the Pivot

1. **Detailed per-theme evidence/citation sections in weekly scans** — VCs skim. Keep evidence in deep dives only.
2. **Momentum scoring as primary metric** — Replace with company-level signals (funding, headcount, stars, buzz). Theme momentum becomes secondary.
3. **Rigid slash command modes as the only input** — Support natural language alongside commands.
4. **The 650+ line SKILL.md with step-by-step orchestration** — Shorter, more flexible SKILL.md that focuses on output quality over process rigidity.

---

## Technical Debt to Fix (from audits)

### Critical/Security
1. Path traversal via `--date` parameter — no validation in persistence.py
2. Real data files committed to git (2026-04-10-devtools.json, theme_index.json)

### High
3. `<LOOKBACK>` is a literal placeholder in SKILL.md — should be actual numbers
4. Hardcoded `.claude/skills/vc-signals/` paths — breaks Co-Work global installs
5. `--sector all` not handled by github_trending.py
6. GITHUB_TOKEN from .env not loaded by github_trending.py
7. No slugify instruction in SKILL.md
8. HTML explainer says "Five Modes" but shows six
9. `github_topics` dead schema field — referenced in add-sector but never implemented
10. ~15 companies from our own briefing missing from seed map

### Medium
11. Curated subreddits never passed alongside auto-resolve
12. No "durable" themes computation in compute_diff
13. Case-sensitive theme matching in compute_diff
14. No JSON error handling on stdin.read()
15. install.sh has no git check, no trap for cleanup
16. README says "interactive diagrams" — HTML has no JS

### Test Coverage Gaps
- No CLI tests for any script
- No tests for _validate_slug, _require_args, _parse_cli_args
- No test for run_query in adapter
- No test for fetch_star_timestamps
- 1 tautological test (test_run_query_returns_structure)

---

## Environment Constraints

### Claude.ai / Co-Work Web
- Python scripts blocked by sandbox proxy (403 Forbidden on all outbound HTTP)
- Only WebSearch works — no last30days, no GitHub trending, no Perplexity
- Skill should detect web sandbox and skip all Python scripts
- Still produces useful output via WebSearch-only path

### Claude Code (local)
- Full access — all scripts, all APIs, all persistence
- This is the primary target environment

### Co-Work Desktop (with terminal)
- Full access like Claude Code
- Skills installed at `~/.claude/skills/vc-signals/`
- Vendor (last30days) at `~/.claude/vendor/last30days-skill/`

---

## Key Files

| File | Purpose |
|------|---------|
| `.claude/skills/vc-signals/SKILL.md` | Skill definition — orchestration, modes, output templates |
| `.claude/skills/vc-signals/scripts/persistence.py` | Save/load briefings, week-over-week diffs, theme index |
| `.claude/skills/vc-signals/scripts/github_trending.py` | GitHub star velocity search |
| `.claude/skills/vc-signals/scripts/last30days_adapter.py` | Bridge to last30days research engine |
| `.claude/skills/vc-signals/config/sectors.json` | Sector taxonomy (3 sectors, 18 subcategories) |
| `.claude/skills/vc-signals/config/company_aliases.json` | Curated company seed map (40 entries) |
| `vendor/last30days-skill/` | Research engine (Reddit, HN, X, YouTube, web) |
| `docs/vc-signals-explainer.html` | Visual explainer (GitHub Pages) |
| `install.sh` | One-line installer for Co-Work |
| `.claude-plugin/` | Plugin format for Claude Code marketplace |

---

## last30days Capabilities We're Using vs Not Using

### Currently using
- `--sources` (via `--search` bridge)
- `--subreddits`
- `--lookback-days`
- `--quick`
- `--auto-resolve`
- `--deep-research`
- `--github-user` / `--github-repo`
- `--x-handle`
- `--emit json`

### Not using (future potential)
- `--store` — SQLite persistence with URL dedup, cost tracking
- `--plan` — custom JSON query plans (could optimize for VC-specific research)
- Watchlist system (`watchlist.py`) — scheduled topic monitoring
- Briefing system (`briefing.py`) — daily/weekly digest generation
- `--agent` mode — skip UI, save output (useful for scheduled runs)
- Polymarket odds — prediction market data as signal
- Bluesky, Threads, Pinterest, TikTok — additional social platforms

---

## Competitive Landscape

| Product | Approach | Strengths | Weaknesses |
|---------|----------|-----------|------------|
| **VC Signals (us)** | Theme discovery → company mapping | Breadth, speed, zero-setup, persistence | Shallow company data, no funding/headcount |
| **Showrun** | Thesis → company search | Deep company data (PitchBook, LinkedIn) | Requires expensive tools, slow (20 min), no theme discovery |
| **Tegus/AlphaSense** | Document search | Massive data corpus | Expensive ($50K+/yr), not trend-focused |
| **CB Insights** | Platform | Comprehensive company data | Expensive, not AI-native |
| **PitchBook** | Database | Gold standard for funding data | $25K+/yr, manual research |

**Our positioning:** The free, AI-native entry point for VC trend discovery that progressively enriches with data as you add integrations.

---

## API Keys & Services

### Currently configured (Alex's setup)
- ScrapeCreators (TikTok, Instagram, YouTube)
- Google/Gemini (query planning for last30days)
- X/Twitter auth tokens (browser cookies)
- GitHub PAT

### Configured but not working in web sandbox
- All of the above — blocked by 403 proxy

### Not configured
- OpenRouter (for Perplexity deep research)
- Brave Search (broader web coverage)
- Attio CRM (not yet integrated)

### Note on security
All API keys stored in `~/.config/last30days/.env` (chmod 600). GitHub PAT was previously in git remote URL — removed. Alex should rotate all keys as they were shared in conversation context.
