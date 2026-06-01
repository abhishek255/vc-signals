# Source Yield Validation

- Goal reached: no
- Assign Owner rows: Voker
- Assign Owner bar preserved: yes
- Net-new credible Review-Worthy rows: 3 / 8
- Review-Worthy Market Signals: 5
- Evidence Gap Queue rows: 12

## Source-Yield Targets

| Metric | Count | Target | Status |
| --- | --- | --- | --- |
| Assign Owner | 1 | min 1, max 3 | met |
| Review Worthy Companies | 3 | min 8, max 15 | below_min |
| Review Worthy Market Signals | 5 | min 5, max 10 | met |
| Evidence Gap Queue | 12 | min 10, max 15 | met |
| Unsafe Promotions | 0 | max 0 | met |

## Review-Worthy Companies

| Company | Domain | Action | Stage | Raised | Headcount | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Superunit | superunit.com | research deeper | PRE_SEED | 500000 | 2 | YC Directory |
| Goldbridge | goldbridgebanking.com | research deeper | PRE_SEED | 500000 | 5 | YC Directory |
| Comfy Deploy | comfydeploy.com | research deeper | PRE_SEED | 500000 | 1 | YC Directory |

## Review-Worthy Market Signals

| Signal | Theme | Sector | Score | 30d Stars | Why It Matters | Next Search |
| --- | --- | --- | --- | --- | --- | --- |
| pullfrog/pullfrog | Devtools workflow automation | Devtools | 100 | 199 | Open-source model-agnostic BYOK GitHub bot that runs in GitHub Actions +199 stars in 30d. | Devtools workflow automation startups founder pricing customers funding |
| affaan-m/agentshield | AI agent security | Cybersecurity | 100 | 149 | AI agent security scanner. Detect vulnerabilities in agent configurations, MCP servers, and tool permissions. Available as CLI, GitHub Action, ECC plugin, and GitHub App integration. 🛡️ +149 stars in 30d. | AI agent security startups founder pricing customers funding |
| redwoodjs/agent-ci | Devtools workflow automation | Devtools | 100 | 77 | Agent-CI is local GitHub Actions for your agents. +77 stars in 30d. | Devtools workflow automation startups founder pricing customers funding |
| azat-io/actions-up | Devtools workflow automation | Devtools | 100 | 59 | 🌊 Interactive CLI tool to update GitHub Actions to latest versions with SHA pinning +59 stars in 30d. | Devtools workflow automation startups founder pricing customers funding |
| peakoss/anti-slop | Devtools workflow automation | Devtools | 100 | 59 | A GitHub action that detects and automatically closes low-quality and AI slop PRs. +59 stars in 30d. | Devtools workflow automation startups founder pricing customers funding |

## Evidence Gap Queue

| Row | Source | Missing Evidence | Next Step | Promotion Target |
| --- | --- | --- | --- | --- |
| affaan-m/agentshield | OSS | official_domain_missing, stage_funding_or_headcount_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company or supporting Market Signal |
| pullfrog/pullfrog | OSS | stage_funding_or_headcount_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing, pricing_docs_or_careers_missing | Find stage, funding, headcount, careers, or company profile evidence. | Review-Worthy Company or supporting Market Signal |
| azat-io/actions-up | OSS | official_domain_missing, stage_funding_or_headcount_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company or supporting Market Signal |
| boostsecurityio/smokedmeat | OSS | official_domain_missing, stage_funding_or_headcount_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company or supporting Market Signal |
| redwoodjs/agent-ci | OSS | stage_funding_or_headcount_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing, pricing_docs_or_careers_missing | Find stage, funding, headcount, careers, or company profile evidence. | Review-Worthy Company or supporting Market Signal |
| peakoss/anti-slop | OSS | official_domain_missing, stage_funding_or_headcount_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company or supporting Market Signal |
| leiting-eric/DailyBrief | OSS | official_domain_missing, stage_funding_or_headcount_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company or supporting Market Signal |
| spaceraccoon/vulnerability-spoiler-alert-action | OSS | official_domain_missing, stage_funding_or_headcount_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company or supporting Market Signal |
| rohitg00/awesome-claude-code-toolkit | OSS | official_domain_missing, founder_team_missing, stage_funding_or_headcount_missing, company_linkedin_or_social_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company or supporting Market Signal |
| jacobdjwilson/awesome-annual-security-reports | OSS | official_domain_missing, founder_team_missing, stage_funding_or_headcount_missing, company_linkedin_or_social_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company or supporting Market Signal |
| FinBot | X | official_domain_missing, founder_team_missing, stage_funding_or_headcount_missing, commercial_or_customer_signal_missing | Resolve official domain from launch text, project docs, founder profile, or web search. | Review-Worthy Company |
| Arize | Grounded web | founder_team_missing, company_linkedin_or_social_missing, commercial_or_customer_signal_missing, pricing_docs_or_careers_missing | Find founder or maintainer identity from website, GitHub org, LinkedIn, HN, or X. | Review-Worthy Company |

## Source Diversity

- Non-YC review-worthy rows: 1
- Review-worthy lanes: hn, yc_directory
- product_hunt: launches=20, resolved_domains=4, unresolved_domains=16
- x: launches=13, resolved_domains=4, unresolved_domains=9

## Structured Provider Decision

- Status: recommend_structured_provider_trial
- Best unlock: Coresignal or Crunchbase-style company metadata
- Reason: Review-Worthy Company target missed
- Reason: 25 Product Hunt/X launch domains still unresolved
- Trial: targets=4, hints=2, direct_access=none, manual_mode=Crunchbase, Coresignal, LinkedIn

## Source Health

- last30days:devtools: complete, fresh_items=50, duration_seconds=165.53
- last30days:cybersecurity: complete, fresh_items=73, duration_seconds=225.03
- last30days:ai-infra: degraded, fresh_items=45, duration_seconds=285.24
- last30days:vertical-ai: degraded, fresh_items=78, duration_seconds=341.28
- last30days:data-infra: degraded, fresh_items=61, duration_seconds=331.1
- last30days:oss: degraded, fresh_items=18, duration_seconds=148.89
- github: complete, fresh_items=25, duration_seconds=19.78
- product_hunt: complete, fresh_items=20, duration_seconds=184.85
- yc_directory: complete, fresh_items=55, duration_seconds=16.88
- x_launches: complete, fresh_items=13, duration_seconds=418.36
- hn_launch_trial: complete, fresh_items=5, duration_seconds=0

## Caveats

- last30days sector queries were degraded or errored, mostly from Safari cookie permissions and timeouts.
- Product Hunt API worked, but several launch redirects still needed fallback domain resolution or stayed unresolved.
- X worked as a launch signal, but evidence was thin and still needs domain enrichment for some rows.
