# VC Signals Radar: All Sectors

**Run date:** 2026-05-04
**Cadence:** Weekly, Monday 8:00 AM ET target
**Audience:** Marathon Management Partners
**Mode:** `/vc-signals radar all`
**Data path used:** last30days free sources plus web search

## Operator Note

This is a real first run, but not yet a partner-ready Marathon artifact. It proves the workflow shape and surfaces a few interesting companies/projects, but the current setup is missing two things needed for a high-confidence weekly brief:

- Optional last30days keys for grounded web/X/YouTube/social source coverage.
- Better ranking filters to suppress low-quality GitHub/reddit noise.

Attio matching was added after the first draft of this run. The table below now reflects a first pass against Marathon's Attio workspace where domains were available.

The strongest signal in this run is not "these exact 20 are the list." The strongest signal is that the market clusters are directionally right: agent reliability, AI SRE, agent security, workflow automation in Slack, vertical/regulated data operations, and OSS security for AI coding agents.

## What's Moving

1. **Agent reliability and eval infrastructure**
   - Why now: YC W26 companies are converging around agents failing in production: reliability, safety, long-horizon simulation, and proprietary workflow adaptation.
   - Representative companies: Cascade, Polymath, Corelayer, IncidentFox.

2. **AI SRE and data-heavy incident response**
   - Why now: regulated industries have a sharper pain point than generic DevOps: production incidents require sensitive data inspection.
   - Representative companies: Corelayer, IncidentFox.

3. **AI agent security**
   - Why now: HN and GitHub are showing practical agent-security projects: runtime monitors, skill scanners, sandbox critiques, agent identity risk.
   - Representative companies/projects: BeeSafe AI, AgentShield, SkillWard, Forgeterm, Burrow, Watchtower, Augustus.

4. **Vertical AI operations inside Slack and back-office systems**
   - Why now: workflow automation posts are noisy, but YC companies are moving toward deployable ops agents with observability and tool execution.
   - Representative companies: Bubble Lab, Pillar, Corelayer.

5. **OSS-native security and agent tooling**
   - Why now: GitHub star velocity is concentrated around AI-code/security tools, but many repos are not investable companies yet.
   - Representative projects: AgentShield, SmokedMeat, eforge, Agent-CI, anti-slop, NeuroSploit.

## Top Cross-Sector Candidates

| Company / Project | Sector | Theme | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise | Sources |
|---|---|---|---|---|---|---|---|---|---|
| Cascade | AI Infra | Proprietary intelligence / agent reliability | High | High | no_owner | Assign owner | YC W26 company helping enterprises adapt models to proprietary data and workflows; Attio shows pre-seed context and no MMP owner in the master activity list. | Positioning may be too broad unless customer wedge is specific. | [YC](https://www.ycombinator.com/companies/cascade) |
| Corelayer | Data Infra | AI on-call for regulated data systems | High | High | no_owner | Assign owner | YC W26 company for AI on-call in finance, healthcare, insurance; Attio has Corelayer (YC W26) in the master activity list with no MMP owner. | Could collapse into Datadog/Monte Carlo/Bigeye adjacency if not narrow enough. | [YC](https://www.ycombinator.com/companies/corelayer) |
| IncidentFox | Devtools | AI SRE agent | High | High | unknown | Assign owner | YC W26 company building AI SRE agents that learn customer systems; founders have Roblox/FAIR and distributed systems background. | AI SRE is becoming crowded; need proof of production depth. | [YC](https://www.ycombinator.com/companies/brownie) |
| BeeSafe AI | Cybersecurity | AI social engineering defense | High | High | unknown | Assign owner | YC W26 security company engaging attackers directly to expose infrastructure and build attacker-behavior data. | Financial-crime wedge is compelling, but sales motion may be long and regulated. | [YC](https://www.ycombinator.com/companies/beesafe-ai) |
| Polymath | AI Infra | Simulation for long-horizon agents | High | High | unknown | Assign owner | YC W26 company building simulated worlds for training/evaluating long-horizon agents; team from UC Berkeley, Hume AI, Plaid, Amazon. | Platform may be ahead of customer budget unless tied to concrete enterprise workflows. | [YC](https://www.ycombinator.com/companies/polymath) |
| Bubble Lab | Vertical AI | Slack-native ops automation | Medium | High | unknown | Monitor | YC W26 company turns natural language into production workflows with logs, traces, and Slack deployment. | Horizontal ops automation is brutally crowded; needs vertical beachhead. | [YC](https://www.ycombinator.com/companies/bubble-lab) |
| Pillar | Vertical AI / Fintech | Autonomous commodity risk management | Medium | High | no_match | Assign owner | Raised $20M seed led by a16z; domain-verified Attio matching found no company record for `pillarhq.com`. | Likely more fintech/vertical SaaS than Marathon core unless the thesis includes AI for industrial finance. | [TechCrunch](https://techcrunch.com/2026/04/14/financial-risk-management-platform-pillar-raises-20m-seed-in-round-led-by-a16z/) |
| Factory | Devtools | Enterprise AI coding agents | Low | High | no_owner | Likely too late | Attio has Factory in Angel Portfolio and the master activity list; public signal shows a $150M round and $1.5B valuation. | Already consensus and probably too late for Marathon entry. | [TechCrunch](https://techcrunch.com/2026/04/16/factory-hits-1-5b-valuation-to-build-ai-coding-for-enterprises/) |
| anthropics/claude-code-security-review | OSS | AI code security review | Low | High | unknown | Map ecosystem | 4,483 stars; +183 stars in 30d; validates demand for AI-assisted security review in code workflows. | Anthropic-owned, not a startup target; useful as ecosystem signal only. | [GitHub](https://github.com/anthropics/claude-code-security-review) |
| AgentShield | OSS / Cybersecurity | Agent security scanner | High | Medium | unknown | Contact maintainer | 584 stars; +184 stars in 30d; scans agent configs, MCP servers, and tool permissions. | Needs company/founder verification and actual user evidence beyond GitHub. | [GitHub](https://github.com/affaan-m/agentshield) |
| SmokedMeat | Cybersecurity / OSS | CI/CD red-team framework | Medium | Medium | unknown | Map ecosystem | 252 stars; +152 stars in 30d; from Boost Security org, focused on build pipeline security risks. | Company-backed OSS by an existing security vendor; may be ecosystem signal, not new company. | [GitHub](https://github.com/boostsecurityio/smokedmeat) |
| Watchtower | Cybersecurity / OSS | AI pentest automation | Medium | Medium | unknown | Watch | New repo with high acceleration ratio; agentic pentest CLI using LLMs/LangGraph. | Offensive security OSS is often demo-heavy; verify maintainer and product seriousness. | [GitHub](https://github.com/fzn0x/watchtower) |
| Augustus | Cybersecurity / OSS | LLM security testing | Medium | Medium | unknown | Map ecosystem | Praetorian repo for LLM security testing with 190+ probes and 28 providers; +27 stars in 30d. | Praetorian-backed, likely not standalone investable but valuable landscape signal. | [GitHub](https://github.com/praetorian-inc/augustus) |
| Agent-CI | Devtools / OSS | Local GitHub Actions for agents | Medium | Medium | unknown | Watch | RedwoodJS org repo; 623 stars, +123 in 30d; local CI for agents is a plausible dev workflow wedge. | Existing org/project context unclear; may be devtool utility rather than startup. | [GitHub](https://github.com/redwoodjs/agent-ci) |
| eforge | Devtools / OSS | Agentic build system | Medium | Low | unknown | Track company formation | Newer org repo, open-source agentic build system with adversarial review; +47 stars in 30d. | Low total stars and limited external evidence; could be too early. | [GitHub](https://github.com/eforge-build/eforge) |
| anti-slop | Devtools / OSS | AI slop PR filtering | Medium | Medium | unknown | Watch | 625 stars; GitHub action for detecting and closing low-quality AI-generated PRs. | Narrow feature risk; could be absorbed by GitHub/code review incumbents. | [GitHub](https://github.com/peakoss/anti-slop) |
| NeuroSploit | Cybersecurity / OSS | AI pentest framework | Low | Medium | unknown | Watch | 1,064 stars, +81 in 30d; AI-agent pentesting framework. | High-risk category with many toy repos; verify real usage before outreach. | [GitHub](https://github.com/JoasASantos/NeuroSploit) |
| SkillWard | Cybersecurity / OSS | Scanner for AI agent skills | Medium | Low | unknown | Track company formation | HN surfaced it as a security scanner for AI Agent Skills. | Very weak evidence so far: HN points but no company data. | [HN/GitHub](https://github.com/Fangcun-AI/SkillWard/tree/main) |
| Forgeterm | Cybersecurity / OSS | Runtime monitor for coding agents | Medium | Low | unknown | Track company formation | HN surfaced runtime security monitoring for AI coding agents. | Early repo signal only; needs maintainer and usage validation. | [HN/GitHub](https://github.com/diemoeve/forgeterm) |
| Burrow | Cybersecurity / OSS | Runtime security for AI agents | Medium | Low | unknown | Track company formation | HN surfaced a runtime-security product for AI agents. | Evidence is weak until repo/company/founder are verified. | [HN](https://news.ycombinator.com/item?id=47761957) |

## Sector Sections

### AI Infra

- **Cascade**: Highest-interest AI infra company in this run because it sits at the intersection of proprietary data, workflow adaptation, and agent reliability.
- **Polymath**: High-interest if simulation for agents becomes an evaluation/procurement layer, not just a research tool.
- **The Token Company**: Candidate to investigate next; YC W26 context-compression middleware for lower LLM cost/latency. Not included in top table because I did not verify enough fresh signal in this run.

### Devtools

- **IncidentFox**: Best devtools company candidate. The pitch is specific, urgent, and measurable: on-call triage and fix workflows.
- **Factory**: Include but label likely too late. Useful as category validation, not likely actionable.
- **Agent-CI / eforge / anti-slop**: OSS watchlist around agent-era CI, build verification, and AI-generated PR quality control.

### Cybersecurity

- **BeeSafe AI**: Best company candidate. Differentiated because it is about AI-enabled social engineering and attacker-in-the-loop data, not another scanner.
- **AgentShield / SkillWard / Forgeterm / Burrow**: Coherent emerging cluster around AI agent/MCP/skills runtime security.
- **Watchtower / NeuroSploit / Augustus**: Pentest/LLM-security cluster, but likely noisy until company formation and usage are verified.

### Vertical AI

- **Bubble Lab**: Slack-native ops automation could matter if it finds a strong vertical beachhead.
- **Pillar**: Strong vertical-fintech example, probably outside core unless Marathon wants AI-for-industrial-risk exposure.
- Reddit workflow-automation chatter was very noisy and agency-heavy; this source needs better filtering.

### Data Infra

- **Corelayer**: Best data infra candidate. It is not generic observability; the wedge is regulated, data-heavy production debugging.
- Broader data-infra signal in this run was weaker than expected; the next run should add more targeted queries for data quality, lineage, semantic layers, and AI data monitoring.

### OSS

- **AgentShield** and **SmokedMeat** are the strongest OSS signals from this run.
- **eforge** is the best "track company formation" candidate.
- **anti-slop** is a surprisingly clean product idea, but may be too narrow.

## Quality Verdict

Would I send this exact artifact to Marathon partners? **No.**

Would I use it as the raw material for a better Monday brief? **Yes.**

What is good:
- It found a real, coherent cluster: AI agents create reliability, security, data, and ops problems.
- It found multiple actionable YC W26 companies.
- It found OSS projects that map to the same thesis.

What is not good enough yet:
- Too many GitHub results are generic repos, bot-generated issue summaries, or ecosystem noise.
- Attio status now works for domain-known companies, but owner/stale logic needs broader calibration against Marathon's actual workflow.
- No headcount/funding enrichment except where public sources made it obvious.
- No source diversity from X, YouTube, grounded web, or Slack/internal notes.

## Recommended Next Action

Use this as the seed for a tighter Marathon-facing brief with 12-15 top companies, then connect Attio before expanding back to 30-50 rows. The next engineering task should be:

1. Add a `radar-run` script that orchestrates sector queries with the bundled Python 3.12 path.
2. Persist raw source evidence per run.
3. Add first-pass Attio domain matching.
4. Add a quality filter for GitHub results: exclude bot digests, issue-only noise, tutorials, config repos, and non-company repos unless OSS mode explicitly wants them.
