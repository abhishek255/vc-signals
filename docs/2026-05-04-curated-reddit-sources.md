# Curated Reddit Sources For Marathon Radar

Date: 2026-05-04

## Recommendation

Use Reddit as a weekly practitioner-pain and workflow-change source, not as a direct company discovery source. A Reddit thread can promote a theme, explain why a workflow is broken, increase or decrease evidence confidence, and create a "Needs More Evidence" row. It should not create an investable company row unless another source verifies a company, project, founder, domain, or launch.

The best use of `last30days` is to pass both curated subreddits and `--auto-resolve`: curated lists guarantee sector coverage, while auto-resolve can still discover new communities, handles, repos, and hashtags. Last30days is a strong fit because Reddit, Hacker News, Polymarket, and GitHub work without extra keys, while X/YouTube/social/grounded web can be unlocked when configured.

## Source Quality Rules

- Treat Reddit posts as pain evidence when they show tool frustration, migration intent, budget/workflow pressure, or repeated practitioner complaints.
- Treat high-quality comments as stronger than titles alone, especially when comments name alternatives, buying criteria, or failed tools.
- Down-rank career-only, beginner-help, tutorial, generic news, and self-promotion posts.
- Do not let one subreddit dominate a sector. Cap per-subreddit contribution before scoring.
- Require corroboration from HN, GitHub, web, Attio, LinkedIn, X, YouTube, or company pages before marking a company as Watchlist or Partner Review.

## Recommended Subreddit Map

| Sector | Primary Subreddits | Secondary Subreddits | Why These Matter |
| --- | --- | --- | --- |
| Devtools | `r/devops`, `r/sre`, `r/platformengineering`, `r/ExperiencedDevs`, `r/programming` | `r/kubernetes`, `r/terraform`, `r/cicd`, `r/softwareengineering`, `r/webdev`, `r/selfhosted` | Captures CI/CD, platform engineering, SRE, DX, deployment, observability, and internal-tool pain. |
| Cybersecurity | `r/netsec`, `r/cybersecurity`, `r/blueteamsec`, `r/AskNetsec`, `r/AppSec` | `r/devsecops`, `r/cloudsecurity`, `r/ReverseEngineering`, `r/Malware`, `r/osint`, `r/privacytoolsIO` | Separates advanced threat/tool chatter from defensive SOC/AppSec/cloud-security pain. |
| AI Infra | `r/LocalLLaMA`, `r/MachineLearning`, `r/mlops`, `r/LangChain`, `r/LLMDevs` | `r/OpenAI`, `r/ChatGPTCoding`, `r/artificial`, `r/datascience`, `r/DataEngineering` | Catches LLMOps, inference cost, local model deployment, agent framework, eval, and RAG pain. |
| Vertical AI | `r/SaaS`, `r/startups`, `r/sales`, `r/CustomerSuccess`, `r/healthIT`, `r/legaltech`, `r/Accounting` | `r/smallbusiness`, `r/Entrepreneur`, `r/edtech`, `r/recruiting`, `r/HumanResources`, `r/insurance` | Surfaces workflow pain from buyers/users rather than only AI builders. |
| Data Infra | `r/dataengineering`, `r/analyticsengineering`, `r/dbt`, `r/snowflake`, `r/databricks` | `r/Database`, `r/bigdata`, `r/SQL`, `r/dataops`, `r/ETL`, `r/aws`, `r/cloudcomputing` | Strong for lineage, quality, testing, orchestration, warehouse cost, and vendor migration chatter. |
| OSS | `r/opensource`, `r/github`, `r/selfhosted`, `r/programming`, `r/LocalLLaMA` | `r/MachineLearning`, `r/mcp`, `r/ClaudeCode`, `r/dataengineering`, `r/cybersecurity`, `r/devops` | Finds adoption pain, maintainer momentum, production usage, alternatives, and early ecosystem formation. |

## Query Patterns To Add

| Sector | Pain Queries |
| --- | --- |
| Devtools | `developer productivity pain`, `CI/CD frustration`, `platform engineering bottleneck`, `observability debugging pain`, `AI coding workflow failure` |
| Cybersecurity | `security operations pain`, `application security backlog`, `cloud security false positives`, `AI security prompt injection`, `SOC alert fatigue` |
| AI Infra | `LLMOps pain`, `LLM inference cost`, `agent evaluation failure`, `RAG quality problem`, `model deployment monitoring` |
| Vertical AI | `manual workflow pain`, `AI agent for operations`, `AI SDR frustration`, `healthcare admin automation`, `legal document automation` |
| Data Infra | `data pipeline testing pain`, `data lineage pain`, `data quality incident`, `warehouse cost pain`, `Airflow orchestration frustration` |
| OSS | `open source tool adoption`, `GitHub repo production use`, `maintainer burnout`, `open source alternative`, `MCP open source` |

## Evidence Interpretation

For Marathon, Reddit should influence two scores differently:

- Investment Interest goes up when many practitioners complain about the same workflow, mention budget pain, compare tools, or show urgency.
- Evidence Confidence stays low until the system finds a candidate-eligible source. Reddit-only themes should normally become `Needs More Evidence`.

Example:

- Five high-engagement `r/dataengineering` threads about lineage and testing pain create a Data Infra theme.
- A GitHub repo, HN launch, company page, or Attio stale company mapped to that theme can become a candidate.
- If no company is verified, the brief should still show the theme under "Needs More Evidence" so partners see the market pull without being tricked into thinking there is a qualified company.

## Implementation Notes

- Create `.claude/skills/vc-signals/config/reddit_sources.json`.
- Add a `reddit_pain` query kind in `build_sector_collection_queries`.
- Pass curated subreddits into `last30days_adapter.py query --subreddits`.
- Preserve `--auto-resolve` so last30days can discover adjacent subreddits and handles.
- Mark Reddit pain queries as `candidate_eligible=false`.
- Render sector-level Reddit findings even when no companies qualify.

## Research Notes

- Last30days supports Reddit comments, HN, Polymarket, and GitHub with no extra key, and can unlock X, YouTube, TikTok, Instagram, Threads, Pinterest, and web search with optional setup: https://github.com/mvanhorn/last30days-skill
- Last30days specifically emphasizes top comments and engagement-weighted community signal, which makes it useful for pain discovery rather than SEO-style search: https://github.com/mvanhorn/last30days-skill
- Cybersecurity research sources consistently point to `r/cybersecurity`, `r/netsec`, `r/blueteamsec`, `r/AskNetsec`, and malware/security niche communities for professional security discussion: https://www.microcybersec.com/post/best-subreddits-for-it-cybersecurity-pros
- SRE/platform/devops sources point to `r/sre`, `r/devops`, and tool-specific communities like Kubernetes/Terraform/AWS for operational and platform-engineering pain: https://painonsocial.com/subreddits/site-reliability-engineers and https://www.terraformacademy.com/sre-pro-tips/c/0/i/89123548/building-your-support-network-top-reddit-and-facebook-communities-sres-and-devops
- Data engineering sources point to `r/dataengineering` as the core community, with adjacent value in `r/bigdata`, `r/SQL`, `r/dataops`, and cloud/tool-specific communities: https://painonsocial.com/subreddits/data-engineers
- ML/AI infrastructure sources support `r/MachineLearning`, `r/mlops`, `r/DataEngineering`, and related ML production communities; direct Reddit examples show LLMOps pain around latency, GPU requirements, inference, and observability: https://painonsocial.com/subreddits/machine-learning-engineers and https://www.reddit.com/r/mlops/comments/17ab33d/does_llmops_differ_from_more_traditional_mlops_if/
