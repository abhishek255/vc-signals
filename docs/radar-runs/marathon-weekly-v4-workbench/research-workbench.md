# VC Signals Research Workbench

## Partner Notes

- This run is useful as an OSS-heavy discovery pass, not as a complete all-sector company radar.
- The strongest theme is AI-assisted security testing, especially agent/MCP permission security, prompt-injection testing, API authorization testing, and autonomous pentest workflows.
- Devtools signal is present, but much of it is test automation, CI for agents, or code-generation workflow infrastructure rather than clearly formed companies.
- Evidence confidence is limited because every qualified row came from OSS. No company-discovery rows were available in this run.

## Source Gap Diagnosis

- Grounded company discovery was not available, so the run could not reliably find company websites, funding pages, founder pages, or LinkedIn-style company evidence.
- Devtools last30days timed out, which likely suppressed non-OSS devtools chatter and company launches.
- Vertical AI last30days failed, so the absence of vertical-AI company rows should not be interpreted as a quiet market.
- `company-discovery.json` had no items for this run, so there was no second-pass promotion from pain/theme evidence into verified company candidates.

## Theme Hypotheses

### 1. AI agent security is becoming a real security workflow category

Evidence:
- `affaan-m/agentshield`: AI agent security scanner for agent configs, MCP servers, and tool permissions, with strong 30-day star growth.
- `praetorian-inc/augustus`: LLM security testing framework for prompt injection, jailbreaks, and adversarial attacks.
- `praetorian-inc/hadrian`: API security testing framework for authorization logic.
- `Hellsender01/LLMMap`: prompt-injection testing framework for LLM-integrated applications.

Why it matters:
Agentic software introduces new security surfaces: tool permissions, prompt injection, API authorization, MCP server exposure, and AI-controlled CI/CD actions. This is aligned with Marathon’s interest in catching technical markets before consensus.

Why this may be noise:
The evidence is mostly OSS. Several repos may be demos, tools, or community projects rather than companies with buyer pull.

### 2. AI-powered pentest automation is noisy but worth watching

Evidence:
- `fzn0x/watchtower`: AI-powered penetration testing automation CLI.
- `JoasASantos/NeuroSploit`: AI-powered penetration testing framework.
- `yohannesgk/blacksmith`: multi-agent AI pentesting framework.
- `zakirkun/guardian-cli`: AI-powered pentesting automation CLI.
- `Yenn503/Hexstrike-redteam`: MCP penetration testing framework with autonomous agents.

Why it matters:
The density of similar repos suggests a developer/security community trying to automate offensive security workflows with agents.

Why this may be noise:
This lane is crowded with hobbyist/security-demo style repos. It needs founder/company/customer verification before it becomes investable.

### 3. Agent-native testing and CI is emerging inside devtools

Evidence:
- `redwoodjs/agent-ci`: local GitHub Actions for agents.
- `LambdaTest/agent-skills`: agent skills for test automation.
- `MGdaasLab/WHartTest`: AI-driven test automation platform.
- `eforge-build/eforge`: agentic build system with adversarial review.
- `BANANASJIM/rdc-cli`: CLI for RenderDoc captures in terminal, CI, and AI-agent workflows.

Why it matters:
As AI agents write and modify code, teams need ways to run tests, simulate CI, review outputs, and validate generated work locally.

Why this may be noise:
The evidence is split across OSS utilities, QA prompt libraries, and CI helpers. It is not yet clear which projects map to companies or budgets.

## Possible Companies Requiring Verification

These are not canonical candidate rows. They should be verified through grounded web/company search before promotion.

| Lead | Why It Is Interesting | Evidence | Verification Needed | Suggested Action |
|---|---|---|---|---|
| AgentShield / agentshield | Strongest single OSS signal for AI agent security and MCP/tool-permission scanning. | https://github.com/affaan-m/agentshield | Confirm whether there is a company, maintainer identity, website, pricing, customers, or funding. | Track company formation; search founder and domain. |
| Praetorian AI security tooling | `augustus` and `hadrian` indicate credible security vendor activity around LLM/API testing. | https://github.com/praetorian-inc/augustus, https://github.com/praetorian-inc/hadrian | Determine whether this is a startup opportunity, incumbent feature expansion, or ecosystem signal around a broader category. | Map competitors and adjacent startups. |
| Watchtower / Guardian / Blacksmith cluster | Multiple repos point to AI-powered pentest automation demand. | https://github.com/fzn0x/watchtower, https://github.com/zakirkun/guardian-cli, https://github.com/yohannesgk/blacksmith | Identify whether any maintainers are forming companies or getting user pull. | Contact/track maintainers only after founder/company verification. |
| Redwood agent-ci | Clean devtools concept: local CI for coding agents. | https://github.com/redwoodjs/agent-ci | Check whether this is a Redwood ecosystem feature, standalone company opportunity, or broader category signal. | Map agent-CI ecosystem and search for funded startups. |
| eforge-build/eforge | Agentic build system with adversarial review is close to AI-era software delivery. | https://github.com/eforge-build/eforge | Verify company formation, maintainer background, product maturity, and buyer. | Watch closely; run founder/domain search. |
| LambdaTest agent-skills | Existing company signal around agent skills for test automation. | https://github.com/LambdaTest/agent-skills | Since LambdaTest is likely not Seed-Series B, treat as market validation rather than a direct investment lead. | Use as category evidence, not primary target. |

## Recommended Next Searches

Run these once grounded web search is available:

- `AI agent security startups MCP permissions Seed Series A founder launch`
- `MCP security startup tool permissions AI agents funding`
- `agent CI startup local GitHub Actions for AI coding agents`
- `AI pentest automation startup autonomous security agents funding`
- `prompt injection testing startup LLM application security Seed`
- `agentic build system startup adversarial review verified source code`
- `AI test automation agents startup Seed Series A`
- `OSS maintainer affaan-m agentshield company founder`
- `eforge build agentic build system startup founder`
- `redwood agent-ci company startup local CI agents`

## What Would Promote A Lead

A possible lead should move into `candidates.json` only when at least one credible source provides:

- company/product identity,
- domain or product page,
- founder or maintainer identity,
- source URL,
- and a clear link to the theme.

Funding, headcount, customer, stage, founder background, and LinkedIn fields should remain blank unless directly evidenced by source data, enrichment cache, or read-only Attio context.
