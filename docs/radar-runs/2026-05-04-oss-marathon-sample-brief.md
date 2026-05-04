# OSS Radar Sample Brief

**Run date:** 2026-05-04  
**Audience:** Marathon Management Partners  
**Mode:** OSS-first weekly radar without grounded web key

## Executive Summary

This run is useful as an OSS signal demo, not yet a full company-discovery brief. Attio matching is live and every surfaced project currently appears as `no_match`, which makes these reasonable watchlist candidates rather than known Marathon pipeline items.

The strongest pattern is tooling for AI agents entering production workflows: agent security, local/CI execution, build automation, and memory/state infrastructure. The evidence base is mostly GitHub velocity, so evidence confidence is intentionally low to medium. The right next action is not "take the meeting" yet; it is "watch, map maintainers, and verify whether there is a company or founder behind the repo."

LinkedIn and X fields are blank unless evidence provides them. This is intentional. Without a grounded web key or LinkedIn-capable source, the system should not invent company or founder profiles.

## Top Watchlist

| Project | Theme | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise |
|---|---|---|---|---|---|---|---|
| affaan-m/agentshield | AI agent security | Medium | Low | no_match | watch | AI agent security scanner for MCP servers and tool permissions; +184 stars in 30d. | Repo traction may not map to company formation or buyer urgency. |
| boostsecurityio/smokedmeat | CI/CD security | Medium | Low | no_match | watch | CI/CD red-team framework for build pipeline risk; +152 stars in 30d. | Could be practitioner/security-lab tooling rather than venture-scale company. |
| redwoodjs/agent-ci | Agentic dev workflows | Medium | Low | no_match | watch | Local GitHub Actions for agents; +123 stars in 30d. | May remain ecosystem tooling inside an existing OSS community. |
| eforge-build/eforge | Agentic build systems | Medium | Low | no_match | watch | Agentic build system with adversarial review loop; +47 stars in 30d. | Need verify maintainer quality, adoption, and whether it solves a budgeted workflow. |
| peakoss/anti-slop | AI code quality | Medium | Low | no_match | watch | GitHub Action for detecting and closing low-quality AI-generated PRs; +34 stars in 30d. | Narrow feature risk; buyer urgency needs validation. |
| MenteDB | AI memory/data infra | Medium | Low | no_match | assign owner | Open-source memory database for AI agents in Rust. | Could be early technical artifact without commercial pull. |
| Frontman | Browser-based coding agent | Medium | Low | no_match | assign owner | Open-source AI coding agent that lives in the browser. | Crowded category; need differentiation versus Cursor/Claude Code/Windsurf. |

## Partner Read

The most investable wedge from this run is not "OSS AI" broadly. It is agent operations infrastructure: security checks, CI/runtime control, build/test automation, memory/state, and anti-slop quality gates. These are closer to budgeted developer/security workflows than generic agent demos.

The best near-term Marathon workflow is to put the top 5 into an OSS watchlist, then enrich maintainers manually or via grounded web once available:

- Company/maintainer LinkedIn
- Founder X/GitHub activity
- License and commercialization posture
- Star authenticity and contributor concentration
- Evidence of enterprise users or serious security/devtools teams

## Demo Caveat

This sample shows the system behaving conservatively without a grounded web key. It surfaces repo-led OSS signals and avoids broad Reddit/HN noise, but it does not yet produce the full "company plus founders plus LinkedIn" experience. Adding Brave/Parallel/Serper/Exa should unlock richer company discovery and profile enrichment.
