# VC Signals Radar

**Run date:** 2026-05-04
**Artifact:** Marathon Partner Preview

## Marathon Partner Preview

### Themes
- **Agent reliability and eval infrastructure**
- **AI SRE and data-heavy incident response**
- **AI agent security**
- **Vertical AI operations inside Slack and back-office systems**
- **OSS-native security and agent tooling**

### Top Candidates

| Company | Sector | Theme | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise | Source |
|---|---|---|---|---|---|---|---|---|---|
| Cascade | AI Infra | Agent reliability | High | High | no_owner | assign owner | YC W26 company adapting models to proprietary enterprise workflows; Attio already has pre-seed context. | Positioning may be too broad unless the wedge is a painful proprietary-data workflow. | https://www.ycombinator.com/companies/cascade |
| Corelayer | Data Infra | AI on-call for regulated data systems | High | High | no_owner | assign owner | YC W26 company for AI on-call in finance, healthcare, and insurance with on-prem/confidential-compute posture. | Could become a narrow observability feature unless it owns regulated data incident response. | https://www.ycombinator.com/companies/corelayer |
| IncidentFox | Devtools | AI SRE agent | High | High | no_match | assign owner | YC W26 AI SRE agent that learns customer systems and handles on-call triage/fix workflows. | AI SRE is already crowded; must prove production depth and workflow ownership. | https://www.ycombinator.com/companies/brownie |
| BeeSafe AI | Cybersecurity | AI social engineering defense | High | High | no_owner | assign owner | YC W26 company engaging scammers directly to uncover infrastructure and build attacker-behavior data. | Fraud/security sales cycles may be long, and evidence still needs customer validation. | https://www.ycombinator.com/companies/beesafe-ai |
| Polymath | AI Infra | Simulation for long-horizon agents | High | High | no_match | assign owner | YC W26 company building simulated worlds for training and evaluating long-horizon agents. | May be ahead of enterprise budget unless tied to concrete agent deployment use cases. | https://www.ycombinator.com/companies/polymath |
| Bubble Lab | Vertical AI | Slack-native ops automation | Medium | High | no_owner | assign owner | YC W26 company turning natural language into production workflows with logs, traces, and Slack deployment. | Horizontal workflow automation is crowded; needs a vertical beachhead. | https://www.ycombinator.com/companies/bubble-lab |
| Pillar | Vertical AI | Autonomous commodity risk management | Medium | High | no_match | assign owner | Raised $20M seed led by a16z to automate commodity risk workflows across contracts, ERP, spreadsheets, and messaging. | May sit outside Marathon core unless industrial AI-finance is in scope. | https://techcrunch.com/2026/04/14/financial-risk-management-platform-pillar-raises-20m-seed-in-round-led-by-a16z/ |
| Factory | Devtools | Enterprise AI coding agents | Low | High | no_owner | likely too late | Raised $150M at a $1.5B valuation and validates enterprise AI coding-agent demand. | Already consensus and likely too late for Marathon entry. | https://techcrunch.com/2026/04/16/factory-hits-1-5b-valuation-to-build-ai-coding-for-enterprises/ |
| AgentShield | OSS / Cybersecurity | Agent security scanner | High | Medium | no_match | contact maintainer | GitHub project scans agent configs, MCP servers, and tool permissions; +184 stars in 30d in the earlier OSS pull. | Needs maintainer/company verification and proof of real user adoption. | https://github.com/affaan-m/agentshield |
| SmokedMeat | OSS / Cybersecurity | CI/CD red-team framework | Medium | Medium | active | map ecosystem | Boost Security OSS framework focused on build-pipeline security risks; +152 stars in 30d in the earlier OSS pull. | Company-backed OSS by an existing vendor, likely ecosystem signal rather than new investment target. | https://github.com/boostsecurityio/smokedmeat |
| eforge | OSS / Devtools | Agentic build system | Medium | Low | no_match | track company formation | Open-source agentic build system with adversarial review; early repo but directly aligned with AI-era build verification. | Low total stars and limited external evidence; could be too early. | https://github.com/eforge-build/eforge |
| anti-slop | OSS / Devtools | AI slop PR filtering | Medium | Medium | no_match | watch | GitHub Action for detecting and closing low-quality AI-generated PRs; strong fit with agent-era maintainer pain. | May be too narrow and absorbable by GitHub/code-review incumbents. | https://github.com/peakoss/anti-slop |

## Sector Notes

### AI Infra
- **Cascade**: YC W26 company adapting models to proprietary enterprise workflows; Attio already has pre-seed context.
- **Polymath**: YC W26 company building simulated worlds for training and evaluating long-horizon agents.

### Data Infra
- **Corelayer**: YC W26 company for AI on-call in finance, healthcare, and insurance with on-prem/confidential-compute posture.

### Devtools
- **IncidentFox**: YC W26 AI SRE agent that learns customer systems and handles on-call triage/fix workflows.
- **Factory**: Raised $150M at a $1.5B valuation and validates enterprise AI coding-agent demand.

### Cybersecurity
- **BeeSafe AI**: YC W26 company engaging scammers directly to uncover infrastructure and build attacker-behavior data.

### Vertical AI
- **Bubble Lab**: YC W26 company turning natural language into production workflows with logs, traces, and Slack deployment.
- **Pillar**: Raised $20M seed led by a16z to automate commodity risk workflows across contracts, ERP, spreadsheets, and messaging.

### OSS / Cybersecurity
- **AgentShield**: GitHub project scans agent configs, MCP servers, and tool permissions; +184 stars in 30d in the earlier OSS pull.
- **SmokedMeat**: Boost Security OSS framework focused on build-pipeline security risks; +152 stars in 30d in the earlier OSS pull.

### OSS / Devtools
- **eforge**: Open-source agentic build system with adversarial review; early repo but directly aligned with AI-era build verification.
- **anti-slop**: GitHub Action for detecting and closing low-quality AI-generated PRs; strong fit with agent-era maintainer pain.
