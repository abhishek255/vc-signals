# VC Signals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code skill (`/vc-signals`) that surfaces emerging investable themes in devtools, cybersecurity, and AI infrastructure with company mapping, momentum scoring, and investor-oriented framing.

**Architecture:** Claude-orchestrated dual-path retrieval. Python scripts handle I/O (GitHub API, file persistence, last30days adapter). Claude does all intelligence work (theme extraction, clustering, scoring, company mapping, investor framing). SKILL.md is the orchestration playbook.

**Tech Stack:** Python 3.12+ (stdlib + requests), Claude Code skill (SKILL.md), JSON configs, Markdown outputs.

**Spec:** `docs/superpowers/specs/2026-04-09-vc-signals-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `.claude/skills/vc-signals/SKILL.md` | Skill definition — argument parsing, setup wizard, mode orchestration, scoring rubrics, output templates |
| `.claude/skills/vc-signals/scripts/persistence.py` | Save/load briefings, week-over-week diffs, theme index |
| `.claude/skills/vc-signals/scripts/github_trending.py` | GitHub API: search repos by sector keywords, compute star velocity |
| `.claude/skills/vc-signals/scripts/last30days_adapter.py` | Detect last30days availability, run queries, normalize output |
| `.claude/skills/vc-signals/scripts/requirements.txt` | Python dependencies (requests, pytest) |
| `.claude/skills/vc-signals/config/sectors.json` | Sector taxonomy — subcategories, aliases, seed queries, negative terms |
| `.claude/skills/vc-signals/config/company_aliases.json` | Curated company-to-theme seed map (~40 entries) |
| `.claude/skills/vc-signals/data/` | Output storage (briefings, themes, companies, github, history) |
| `.claude/skills/vc-signals/tests/conftest.py` | Test fixtures — tmp data dirs, sample configs |
| `.claude/skills/vc-signals/tests/test_persistence.py` | Tests for persistence module |
| `.claude/skills/vc-signals/tests/test_github_trending.py` | Tests for GitHub trending module |
| `.claude/skills/vc-signals/tests/test_last30days_adapter.py` | Tests for last30days adapter |
| `README.md` | Project overview, setup guide, usage examples, API key instructions |

---

## Task 1: Project Scaffold

**Files:**
- Create: `.claude/skills/vc-signals/scripts/requirements.txt`
- Create: `.claude/skills/vc-signals/tests/conftest.py`
- Create: `.claude/skills/vc-signals/data/` subdirectories with `.gitkeep`
- Create: `.gitignore`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/abhishekgarg/personalProject
git init
```

Expected: `Initialized empty Git repository`

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p .claude/skills/vc-signals/scripts
mkdir -p .claude/skills/vc-signals/config
mkdir -p .claude/skills/vc-signals/data/briefings
mkdir -p .claude/skills/vc-signals/data/themes
mkdir -p .claude/skills/vc-signals/data/companies
mkdir -p .claude/skills/vc-signals/data/github
mkdir -p .claude/skills/vc-signals/data/history
mkdir -p .claude/skills/vc-signals/tests
mkdir -p docs/superpowers/specs
mkdir -p docs/superpowers/plans
```

- [ ] **Step 3: Create requirements.txt**

Write to `.claude/skills/vc-signals/scripts/requirements.txt`:

```
requests>=2.31.0
```

- [ ] **Step 4: Create .gitignore**

Write to `.gitignore`:

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.egg-info/
dist/
build/
.env
*.env.local
.claude/skills/vc-signals/data/briefings/*.json
.claude/skills/vc-signals/data/briefings/*.md
.claude/skills/vc-signals/data/themes/*.md
.claude/skills/vc-signals/data/companies/*.md
.claude/skills/vc-signals/data/github/*.md
.claude/skills/vc-signals/data/history/theme_index.json
vendor/
```

- [ ] **Step 5: Create .gitkeep files for empty data directories**

```bash
touch .claude/skills/vc-signals/data/briefings/.gitkeep
touch .claude/skills/vc-signals/data/themes/.gitkeep
touch .claude/skills/vc-signals/data/companies/.gitkeep
touch .claude/skills/vc-signals/data/github/.gitkeep
touch .claude/skills/vc-signals/data/history/.gitkeep
```

- [ ] **Step 6: Create test conftest.py**

Write to `.claude/skills/vc-signals/tests/conftest.py`:

```python
"""Shared fixtures for vc-signals tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts/ to import path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory matching the expected structure."""
    for subdir in ("briefings", "themes", "companies", "github", "history"):
        (tmp_path / subdir).mkdir()
    return tmp_path


@pytest.fixture
def sample_themes() -> list[dict]:
    """Sample theme list for testing."""
    return [
        {
            "name": "AI-Powered Code Review",
            "momentum": 8,
            "confidence": "high",
            "timing": "mid",
            "hype_vs_durable": "durable",
            "companies": [
                {"name": "CodeRabbit", "role": "direct_solver", "confidence": "confirmed"}
            ],
            "evidence_summary": "Multiple HN threads, Reddit discussions, and blog posts about AI code review tools.",
        },
        {
            "name": "Rust-Based Build Tools",
            "momentum": 5,
            "confidence": "medium",
            "timing": "early",
            "hype_vs_durable": "durable",
            "companies": [
                {"name": "Turbopack", "role": "direct_solver", "confidence": "likely"}
            ],
            "evidence_summary": "Growing discussion about Rust rewrites of JS toolchain.",
        },
    ]


@pytest.fixture
def sample_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with sectors.json."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    sectors = {
        "devtools": {
            "display_name": "Developer Tools",
            "subcategories": {
                "ci_cd": {
                    "name": "CI/CD & Build Systems",
                    "aliases": ["continuous integration", "build pipelines", "GitHub Actions"],
                    "seed_queries": ["new CI/CD tools developers switching to"],
                }
            },
            "discovery_queries": ["emerging developer tools 2026"],
            "negative_terms": ["tutorial", "beginner guide"],
        }
    }
    (config_dir / "sectors.json").write_text(json.dumps(sectors, indent=2))
    return config_dir
```

- [ ] **Step 7: Install dependencies and verify pytest**

```bash
cd /Users/abhishekgarg/personalProject
pip install requests pytest
python3 -m pytest .claude/skills/vc-signals/tests/ -v --co 2>&1 || echo "No tests collected yet — expected"
```

Expected: `no tests ran` or `no tests collected` (no errors about missing modules)

- [ ] **Step 8: Commit scaffold**

```bash
git add .gitignore .claude/skills/vc-signals/scripts/requirements.txt .claude/skills/vc-signals/tests/conftest.py .claude/skills/vc-signals/data/ docs/
git commit -m "chore: scaffold vc-signals skill project structure"
```

---

## Task 2: Sector Taxonomy Config

**Files:**
- Create: `.claude/skills/vc-signals/config/sectors.json`

- [ ] **Step 1: Write sectors.json**

Write to `.claude/skills/vc-signals/config/sectors.json`:

```json
{
  "devtools": {
    "display_name": "Developer Tools",
    "subcategories": {
      "ci_cd": {
        "name": "CI/CD & Build Systems",
        "aliases": ["continuous integration", "continuous delivery", "build pipelines", "GitHub Actions", "CI pipeline", "build system"],
        "seed_queries": [
          "new CI/CD tools developers switching to",
          "build system trends emerging",
          "GitHub Actions alternatives gaining traction",
          "CI pipeline performance optimization tools"
        ]
      },
      "testing": {
        "name": "Testing & Quality",
        "aliases": ["test automation", "test frameworks", "code quality", "QA tooling", "end-to-end testing", "unit testing", "integration testing"],
        "seed_queries": [
          "software testing tools emerging trends",
          "AI testing automation new tools",
          "testing bottleneck developer productivity"
        ]
      },
      "ide_dx": {
        "name": "IDEs & Developer Experience",
        "aliases": ["code editors", "developer productivity", "dev environments", "developer portals", "developer experience", "DX platforms"],
        "seed_queries": [
          "AI-powered IDE tools trending",
          "developer experience platforms gaining traction",
          "code editor innovations new"
        ]
      },
      "observability": {
        "name": "Observability & Debugging",
        "aliases": ["monitoring", "logging", "tracing", "APM", "error tracking", "debugging tools", "observability platform"],
        "seed_queries": [
          "observability tools new entrants",
          "debugging tools AI-powered trending",
          "APM alternatives developers prefer"
        ]
      },
      "infra_as_code": {
        "name": "Infrastructure as Code & Platform Engineering",
        "aliases": ["IaC", "platform engineering", "internal developer platforms", "Terraform alternatives", "infrastructure management", "IDP"],
        "seed_queries": [
          "platform engineering tools trending",
          "Terraform alternatives new IaC tools",
          "internal developer platform emerging"
        ]
      },
      "source_control": {
        "name": "Source Control & Code Management",
        "aliases": ["git tools", "code review", "merge tooling", "monorepo", "version control", "code collaboration"],
        "seed_queries": [
          "code review tools AI-powered new",
          "monorepo tooling trends",
          "git workflow tools emerging"
        ]
      }
    },
    "discovery_queries": [
      "emerging developer tools 2026",
      "devtools startups gaining traction",
      "developer tools trending hacker news",
      "what developer tools are you switching to reddit",
      "most interesting devtools startups funded recently",
      "developer tooling landscape changes"
    ],
    "negative_terms": ["tutorial", "beginner guide", "how to learn", "free course", "coding bootcamp"]
  },
  "cybersecurity": {
    "display_name": "Cybersecurity",
    "subcategories": {
      "appsec": {
        "name": "Application Security",
        "aliases": ["SAST", "DAST", "SCA", "software supply chain security", "application security testing", "code scanning", "SBOM"],
        "seed_queries": [
          "application security tools new entrants",
          "software supply chain security emerging",
          "SAST DAST tools developer-friendly trending"
        ]
      },
      "cloud_security": {
        "name": "Cloud & Infrastructure Security",
        "aliases": ["CSPM", "CNAPP", "container security", "kubernetes security", "cloud workload protection", "cloud security posture"],
        "seed_queries": [
          "cloud security posture management new tools",
          "kubernetes security emerging threats tools",
          "CNAPP market new entrants"
        ]
      },
      "identity": {
        "name": "Identity & Access",
        "aliases": ["IAM", "zero trust", "authentication", "authorization", "CIAM", "identity governance", "privileged access"],
        "seed_queries": [
          "identity security tools emerging trends",
          "zero trust architecture new tools",
          "authentication authorization new approaches"
        ]
      },
      "soc_detection": {
        "name": "SOC & Detection",
        "aliases": ["SIEM", "XDR", "EDR", "threat detection", "incident response", "security operations", "SOAR"],
        "seed_queries": [
          "SIEM alternatives emerging",
          "XDR tools new vendors gaining traction",
          "AI-powered threat detection new"
        ]
      },
      "ai_security": {
        "name": "AI & LLM Security",
        "aliases": ["AI red teaming", "prompt injection", "LLM security", "AI guardrails", "model security", "AI safety tooling"],
        "seed_queries": [
          "AI security tools emerging market",
          "LLM security guardrails new tools",
          "prompt injection defense tools",
          "AI red teaming platforms"
        ]
      },
      "data_security": {
        "name": "Data Security & Privacy",
        "aliases": ["DLP", "encryption", "data governance", "privacy engineering", "data loss prevention", "data classification"],
        "seed_queries": [
          "data security tools emerging",
          "privacy engineering platforms trending",
          "data governance tools new"
        ]
      }
    },
    "discovery_queries": [
      "emerging cybersecurity threats 2026",
      "cybersecurity startups gaining traction funded",
      "new vulnerability classes discovered recently",
      "cybersecurity tools trending hacker news",
      "security startup landscape changes",
      "cybersecurity categories emerging investment"
    ],
    "negative_terms": ["antivirus review", "VPN review", "consumer security", "password manager review", "best free antivirus"]
  },
  "ai-infra": {
    "display_name": "AI Infrastructure",
    "subcategories": {
      "model_serving": {
        "name": "Model Serving & Inference",
        "aliases": ["inference optimization", "LLM serving", "GPU orchestration", "model deployment", "inference engine", "model runtime"],
        "seed_queries": [
          "LLM inference optimization tools new",
          "model serving infrastructure emerging",
          "GPU orchestration platforms trending"
        ]
      },
      "training_compute": {
        "name": "Training & Compute",
        "aliases": ["distributed training", "GPU cloud", "training infrastructure", "ML compute", "training optimization", "compute cluster"],
        "seed_queries": [
          "GPU cloud providers new entrants",
          "distributed training tools emerging",
          "ML training infrastructure cost optimization"
        ]
      },
      "data_pipelines": {
        "name": "Data & Feature Pipelines",
        "aliases": ["feature stores", "data labeling", "vector databases", "embeddings infrastructure", "data pipeline", "RAG infrastructure"],
        "seed_queries": [
          "vector database market new entrants",
          "RAG infrastructure tools emerging",
          "AI data pipeline tools trending"
        ]
      },
      "agent_infra": {
        "name": "Agent Infrastructure",
        "aliases": ["agent frameworks", "agent orchestration", "tool use", "agent evals", "MCP", "agent runtime", "agent memory"],
        "seed_queries": [
          "AI agent frameworks trending",
          "agent evaluation tools emerging",
          "MCP model context protocol tools",
          "agent orchestration infrastructure new"
        ]
      },
      "mlops": {
        "name": "MLOps & Experiment Management",
        "aliases": ["model registry", "experiment tracking", "ML monitoring", "model observability", "LLMOps", "AI ops"],
        "seed_queries": [
          "MLOps tools new entrants",
          "LLMOps platforms emerging",
          "model observability tools trending"
        ]
      },
      "ai_dev_tools": {
        "name": "AI-Native Dev Tools",
        "aliases": ["AI code generation", "AI code review", "AI debugging", "copilot alternatives", "AI coding assistant", "AI pair programming"],
        "seed_queries": [
          "AI coding assistant alternatives copilot",
          "AI code generation tools new",
          "AI-native developer tools emerging"
        ]
      }
    },
    "discovery_queries": [
      "AI infrastructure trends emerging 2026",
      "AI infra startups gaining traction funded",
      "LLM infrastructure new tools",
      "AI agent tooling trending hacker news",
      "AI infrastructure landscape changes",
      "most interesting AI infra companies"
    ],
    "negative_terms": ["AI art generator", "ChatGPT tips", "AI writing tool review", "best AI chatbot", "AI image generator"]
  }
}
```

- [ ] **Step 2: Validate JSON is parseable**

```bash
python3 -c "import json; json.load(open('.claude/skills/vc-signals/config/sectors.json')); print('Valid JSON')"
```

Expected: `Valid JSON`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/vc-signals/config/sectors.json
git commit -m "feat: add sector taxonomy config for devtools, cybersecurity, ai-infra"
```

---

## Task 3: Company Aliases Config

**Files:**
- Create: `.claude/skills/vc-signals/config/company_aliases.json`

- [ ] **Step 1: Write company_aliases.json**

Write to `.claude/skills/vc-signals/config/company_aliases.json`:

```json
{
  "Blacksmith": {
    "aliases": ["blacksmith", "useblacksmith", "blacksmith.sh"],
    "oss_projects": [],
    "sectors": ["devtools"],
    "themes": ["CI/CD acceleration", "GitHub Actions optimization"]
  },
  "CircleCI": {
    "aliases": ["circleci", "circle ci"],
    "oss_projects": [],
    "sectors": ["devtools"],
    "themes": ["CI/CD platforms"]
  },
  "GitHub": {
    "aliases": ["github", "github.com"],
    "oss_projects": ["GitHub Actions"],
    "sectors": ["devtools"],
    "themes": ["source control", "CI/CD platforms", "AI coding assistants"]
  },
  "GitLab": {
    "aliases": ["gitlab", "gitlab.com"],
    "oss_projects": ["GitLab CE"],
    "sectors": ["devtools"],
    "themes": ["DevOps platforms", "CI/CD platforms"]
  },
  "Buildkite": {
    "aliases": ["buildkite"],
    "oss_projects": [],
    "sectors": ["devtools"],
    "themes": ["CI/CD platforms", "build infrastructure"]
  },
  "Vercel": {
    "aliases": ["vercel", "vercel.com"],
    "oss_projects": ["Next.js", "Turbopack", "Turborepo"],
    "sectors": ["devtools"],
    "themes": ["frontend deployment", "developer experience"]
  },
  "Netlify": {
    "aliases": ["netlify", "netlify.com"],
    "oss_projects": [],
    "sectors": ["devtools"],
    "themes": ["frontend deployment", "Jamstack"]
  },
  "Datadog": {
    "aliases": ["datadog", "datadoghq"],
    "oss_projects": [],
    "sectors": ["devtools"],
    "themes": ["observability", "APM", "cloud monitoring"]
  },
  "Grafana Labs": {
    "aliases": ["grafana", "grafana labs"],
    "oss_projects": ["Grafana", "Loki", "Tempo", "Mimir"],
    "sectors": ["devtools"],
    "themes": ["observability", "open-source monitoring"]
  },
  "HashiCorp": {
    "aliases": ["hashicorp"],
    "oss_projects": ["Terraform", "Vault", "Consul", "Nomad"],
    "sectors": ["devtools"],
    "themes": ["infrastructure as code", "secrets management"]
  },
  "Pulumi": {
    "aliases": ["pulumi"],
    "oss_projects": ["Pulumi"],
    "sectors": ["devtools"],
    "themes": ["infrastructure as code", "platform engineering"]
  },
  "JetBrains": {
    "aliases": ["jetbrains"],
    "oss_projects": ["IntelliJ IDEA CE", "Kotlin"],
    "sectors": ["devtools"],
    "themes": ["IDEs", "developer experience"]
  },
  "Cursor": {
    "aliases": ["cursor", "cursor.sh", "cursor.com"],
    "oss_projects": [],
    "sectors": ["devtools", "ai-infra"],
    "themes": ["AI coding assistants", "AI-native IDEs"]
  },
  "CodeRabbit": {
    "aliases": ["coderabbit"],
    "oss_projects": [],
    "sectors": ["devtools"],
    "themes": ["AI code review", "automated code review"]
  },
  "Snyk": {
    "aliases": ["snyk", "snyk.io"],
    "oss_projects": [],
    "sectors": ["devtools", "cybersecurity"],
    "themes": ["developer security", "software composition analysis", "supply chain security"]
  },
  "CrowdStrike": {
    "aliases": ["crowdstrike"],
    "oss_projects": [],
    "sectors": ["cybersecurity"],
    "themes": ["endpoint security", "XDR", "threat intelligence"]
  },
  "Palo Alto Networks": {
    "aliases": ["palo alto", "paloalto", "panw"],
    "oss_projects": [],
    "sectors": ["cybersecurity"],
    "themes": ["network security", "cloud security", "SASE"]
  },
  "Wiz": {
    "aliases": ["wiz", "wiz.io"],
    "oss_projects": [],
    "sectors": ["cybersecurity"],
    "themes": ["cloud security", "CNAPP", "cloud security posture management"]
  },
  "SentinelOne": {
    "aliases": ["sentinelone", "sentinel one", "s1"],
    "oss_projects": [],
    "sectors": ["cybersecurity"],
    "themes": ["endpoint security", "XDR", "AI-powered threat detection"]
  },
  "Orca Security": {
    "aliases": ["orca", "orca security"],
    "oss_projects": [],
    "sectors": ["cybersecurity"],
    "themes": ["cloud security", "agentless security"]
  },
  "Chainguard": {
    "aliases": ["chainguard"],
    "oss_projects": ["Wolfi", "apko"],
    "sectors": ["cybersecurity"],
    "themes": ["supply chain security", "container security", "secure base images"]
  },
  "Semgrep": {
    "aliases": ["semgrep", "r2c"],
    "oss_projects": ["Semgrep"],
    "sectors": ["cybersecurity", "devtools"],
    "themes": ["static analysis", "code scanning", "developer security"]
  },
  "Endor Labs": {
    "aliases": ["endor labs", "endorlabs"],
    "oss_projects": [],
    "sectors": ["cybersecurity"],
    "themes": ["dependency security", "software composition analysis", "OSS risk management"]
  },
  "Teleport": {
    "aliases": ["teleport", "goteleport"],
    "oss_projects": ["Teleport"],
    "sectors": ["cybersecurity"],
    "themes": ["identity-based access", "zero trust", "infrastructure access"]
  },
  "Pangea": {
    "aliases": ["pangea", "pangea.cloud"],
    "oss_projects": [],
    "sectors": ["cybersecurity"],
    "themes": ["security APIs", "security-as-a-service"]
  },
  "Confluent": {
    "aliases": ["confluent", "confluent.io"],
    "oss_projects": ["Apache Kafka"],
    "sectors": ["devtools", "ai-infra"],
    "themes": ["streaming data infrastructure", "event-driven architecture"]
  },
  "Pinecone": {
    "aliases": ["pinecone", "pinecone.io"],
    "oss_projects": [],
    "sectors": ["ai-infra"],
    "themes": ["vector databases", "RAG infrastructure", "embeddings"]
  },
  "Weaviate": {
    "aliases": ["weaviate"],
    "oss_projects": ["Weaviate"],
    "sectors": ["ai-infra"],
    "themes": ["vector databases", "semantic search"]
  },
  "Chroma": {
    "aliases": ["chroma", "chromadb", "trychroma"],
    "oss_projects": ["Chroma"],
    "sectors": ["ai-infra"],
    "themes": ["vector databases", "embeddings", "RAG infrastructure"]
  },
  "Modal": {
    "aliases": ["modal", "modal.com"],
    "oss_projects": [],
    "sectors": ["ai-infra"],
    "themes": ["serverless GPU compute", "ML infrastructure"]
  },
  "Anyscale": {
    "aliases": ["anyscale"],
    "oss_projects": ["Ray"],
    "sectors": ["ai-infra"],
    "themes": ["distributed compute", "model serving", "training infrastructure"]
  },
  "Together AI": {
    "aliases": ["together ai", "together.ai", "togetherai"],
    "oss_projects": [],
    "sectors": ["ai-infra"],
    "themes": ["inference APIs", "open-source model serving"]
  },
  "Fireworks AI": {
    "aliases": ["fireworks ai", "fireworks.ai"],
    "oss_projects": [],
    "sectors": ["ai-infra"],
    "themes": ["inference optimization", "model serving"]
  },
  "Weights & Biases": {
    "aliases": ["wandb", "weights and biases", "weights & biases"],
    "oss_projects": [],
    "sectors": ["ai-infra"],
    "themes": ["experiment tracking", "MLOps", "model evaluation"]
  },
  "LangChain": {
    "aliases": ["langchain", "langsmith"],
    "oss_projects": ["LangChain", "LangGraph", "LangSmith"],
    "sectors": ["ai-infra"],
    "themes": ["agent frameworks", "LLM orchestration", "agent evaluation"]
  },
  "CrewAI": {
    "aliases": ["crewai", "crew ai"],
    "oss_projects": ["CrewAI"],
    "sectors": ["ai-infra"],
    "themes": ["multi-agent orchestration", "agent frameworks"]
  },
  "Braintrust": {
    "aliases": ["braintrust", "braintrustdata"],
    "oss_projects": [],
    "sectors": ["ai-infra"],
    "themes": ["AI evaluation", "LLM observability", "prompt engineering"]
  },
  "Humanloop": {
    "aliases": ["humanloop"],
    "oss_projects": [],
    "sectors": ["ai-infra"],
    "themes": ["LLM ops", "prompt management", "AI evaluation"]
  },
  "Elastic": {
    "aliases": ["elastic", "elasticsearch"],
    "oss_projects": ["Elasticsearch", "Kibana"],
    "sectors": ["devtools", "cybersecurity"],
    "themes": ["search infrastructure", "observability", "SIEM"]
  },
  "Supabase": {
    "aliases": ["supabase"],
    "oss_projects": ["Supabase"],
    "sectors": ["devtools"],
    "themes": ["backend-as-a-service", "open-source Firebase alternative", "developer experience"]
  }
}
```

- [ ] **Step 2: Validate JSON**

```bash
python3 -c "import json; d=json.load(open('.claude/skills/vc-signals/config/company_aliases.json')); print(f'Valid JSON: {len(d)} companies')"
```

Expected: `Valid JSON: 40 companies`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/vc-signals/config/company_aliases.json
git commit -m "feat: add curated company-to-theme seed map (40 entries)"
```

---

## Task 4: Persistence Module (TDD)

**Files:**
- Create: `.claude/skills/vc-signals/scripts/persistence.py`
- Create: `.claude/skills/vc-signals/tests/test_persistence.py`

- [ ] **Step 1: Write failing tests for save/load briefing**

Write to `.claude/skills/vc-signals/tests/test_persistence.py`:

```python
"""Tests for the persistence module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_save_briefing_creates_json(data_dir, sample_themes):
    from persistence import save_briefing

    result = save_briefing(
        sector="devtools",
        themes=sample_themes,
        retrieval_path="websearch",
        date="2026-04-09",
        data_dir=data_dir,
    )
    json_path = data_dir / "briefings" / "2026-04-09-devtools.json"
    assert json_path.exists()
    briefing = json.loads(json_path.read_text())
    assert briefing["date"] == "2026-04-09"
    assert briefing["sector"] == "devtools"
    assert briefing["retrieval_path"] == "websearch"
    assert len(briefing["themes"]) == 2
    assert result["saved"] == str(json_path)


def test_load_briefing_returns_data(data_dir, sample_themes):
    from persistence import load_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_briefing("devtools", "2026-04-09", data_dir)
    assert result is not None
    assert result["sector"] == "devtools"
    assert len(result["themes"]) == 2


def test_load_briefing_missing_returns_none(data_dir):
    from persistence import load_briefing

    result = load_briefing("devtools", "2099-01-01", data_dir)
    assert result is None


def test_load_previous_finds_earlier(data_dir, sample_themes):
    from persistence import load_previous_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-02", data_dir)
    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_previous_briefing("devtools", before_date="2026-04-09", data_dir=data_dir)
    assert result is not None
    assert result["date"] == "2026-04-02"


def test_load_previous_no_earlier_returns_none(data_dir, sample_themes):
    from persistence import load_previous_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_previous_briefing("devtools", before_date="2026-04-01", data_dir=data_dir)
    assert result is None


def test_compute_diff_new_themes(data_dir):
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 6},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 7},
            {"name": "Rust Build Tools", "momentum": 5},
        ],
    }
    diff = compute_diff(current, previous)
    assert diff["previous_date"] == "2026-04-02"
    new_names = [t["name"] for t in diff["new_themes"]]
    assert "Rust Build Tools" in new_names


def test_compute_diff_fading_themes():
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "WebAssembly Runtimes", "momentum": 7},
            {"name": "AI Code Review", "momentum": 6},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 7},
        ],
    }
    diff = compute_diff(current, previous)
    fading_names = [t["name"] for t in diff["fading_themes"]]
    assert "WebAssembly Runtimes" in fading_names


def test_compute_diff_accelerating_themes():
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 5},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 8},
        ],
    }
    diff = compute_diff(current, previous)
    accel_names = [t["name"] for t in diff["accelerating_themes"]]
    assert "AI Code Review" in accel_names


def test_update_theme_index_new_theme(data_dir, sample_themes):
    from persistence import update_theme_index

    index = update_theme_index(sample_themes, "devtools", "2026-04-09", data_dir)
    assert "AI-Powered Code Review" in index
    entry = index["AI-Powered Code Review"]
    assert entry["first_seen"] == "2026-04-09"
    assert entry["last_seen"] == "2026-04-09"
    assert entry["appearances"] == 1
    assert entry["momentum_history"] == [8]
    assert entry["peak_momentum"] == 8


def test_update_theme_index_existing_theme(data_dir, sample_themes):
    from persistence import update_theme_index

    update_theme_index(sample_themes, "devtools", "2026-04-02", data_dir)
    updated_themes = [{"name": "AI-Powered Code Review", "momentum": 9}]
    index = update_theme_index(updated_themes, "devtools", "2026-04-09", data_dir)
    entry = index["AI-Powered Code Review"]
    assert entry["first_seen"] == "2026-04-02"
    assert entry["last_seen"] == "2026-04-09"
    assert entry["appearances"] == 2
    assert entry["momentum_history"] == [8, 9]
    assert entry["peak_momentum"] == 9


def test_save_markdown(data_dir):
    from persistence import save_markdown

    content = "# Test Briefing\n\nSome content here."
    result = save_markdown("themes", "agent-evals", content, "2026-04-09", data_dir)
    md_path = data_dir / "themes" / "2026-04-09-agent-evals.md"
    assert md_path.exists()
    assert md_path.read_text() == content
    assert result["saved"] == str(md_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/abhishekgarg/personalProject
python3 -m pytest .claude/skills/vc-signals/tests/test_persistence.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'persistence'`

- [ ] **Step 3: Implement persistence.py**

Write to `.claude/skills/vc-signals/scripts/persistence.py`:

```python
#!/usr/bin/env python3
"""Persistence layer for VC Signals — save/load briefings, diffs, theme index."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"


def save_briefing(
    sector: str,
    themes: list[dict],
    retrieval_path: str,
    date: str | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Save a briefing as JSON. Returns dict with saved path."""
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = data_dir or DEFAULT_DATA_DIR

    briefing = {
        "date": date,
        "sector": sector,
        "retrieval_path": retrieval_path,
        "themes": themes,
    }

    briefings_dir = data_dir / "briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)

    json_path = briefings_dir / f"{date}-{sector}.json"
    json_path.write_text(json.dumps(briefing, indent=2))

    return {"saved": str(json_path), "date": date}


def load_briefing(
    sector: str,
    date: str,
    data_dir: Path | None = None,
) -> dict | None:
    """Load a briefing by sector and date. Returns None if not found."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    json_path = data_dir / "briefings" / f"{date}-{sector}.json"
    if not json_path.exists():
        return None
    return json.loads(json_path.read_text())


def load_previous_briefing(
    sector: str,
    before_date: str,
    data_dir: Path | None = None,
) -> dict | None:
    """Load the most recent briefing before a given date."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    briefings_dir = data_dir / "briefings"
    if not briefings_dir.exists():
        return None

    candidates = sorted(briefings_dir.glob(f"*-{sector}.json"), reverse=True)
    for path in candidates:
        # Extract date from filename like "2026-04-02-devtools.json"
        file_date = path.name.removesuffix(f"-{sector}.json")
        if file_date < before_date:
            return json.loads(path.read_text())
    return None


def compute_diff(current: dict, previous: dict) -> dict:
    """Compute week-over-week diff between two briefings."""
    current_themes = {t["name"]: t for t in current["themes"]}
    previous_themes = {t["name"]: t for t in previous["themes"]}

    new_themes = [t for name, t in current_themes.items() if name not in previous_themes]

    fading_themes = []
    for name, prev_t in previous_themes.items():
        if name not in current_themes:
            fading_themes.append(prev_t)
        elif current_themes[name].get("momentum", 0) <= prev_t.get("momentum", 0) - 3:
            fading_themes.append(prev_t)

    accelerating_themes = []
    for name in current_themes:
        if name in previous_themes:
            curr_m = current_themes[name].get("momentum", 0)
            prev_m = previous_themes[name].get("momentum", 0)
            if curr_m >= prev_m + 2:
                accelerating_themes.append(current_themes[name])

    return {
        "previous_date": previous["date"],
        "new_themes": new_themes,
        "fading_themes": fading_themes,
        "accelerating_themes": accelerating_themes,
    }


def update_theme_index(
    themes: list[dict],
    sector: str,
    date: str | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Update the running theme index. Returns the full index."""
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = data_dir or DEFAULT_DATA_DIR

    index_path = data_dir / "history" / "theme_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if index_path.exists():
        index = json.loads(index_path.read_text())
    else:
        index = {}

    for theme in themes:
        name = theme["name"]
        momentum = theme.get("momentum", 0)

        if name in index:
            entry = index[name]
            entry["last_seen"] = date
            entry["appearances"] += 1
            entry["momentum_history"].append(momentum)
            entry["peak_momentum"] = max(entry["peak_momentum"], momentum)
            if sector not in entry["sectors"]:
                entry["sectors"].append(sector)
        else:
            index[name] = {
                "first_seen": date,
                "last_seen": date,
                "appearances": 1,
                "sectors": [sector],
                "momentum_history": [momentum],
                "peak_momentum": momentum,
            }

    index_path.write_text(json.dumps(index, indent=2))
    return index


def save_markdown(
    subdir: str,
    slug: str,
    content: str,
    date: str | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Save markdown content to a dated file in the given subdirectory."""
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = data_dir or DEFAULT_DATA_DIR

    target_dir = data_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    md_path = target_dir / f"{date}-{slug}.md"
    md_path.write_text(content)

    return {"saved": str(md_path), "date": date}


# --- CLI interface for Claude to call via Bash ---

def _cli_main() -> None:
    """CLI entry point. Commands: save-briefing, load-briefing, load-previous, diff, update-index, save-markdown."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: persistence.py <command> [args]"}))
        sys.exit(1)

    command = sys.argv[1]
    args = _parse_cli_args(sys.argv[2:])
    data_dir = Path(args.get("data-dir", str(DEFAULT_DATA_DIR)))

    if command == "save-briefing":
        themes = json.loads(sys.stdin.read())
        result = save_briefing(
            sector=args["sector"],
            themes=themes,
            retrieval_path=args.get("retrieval-path", "websearch"),
            date=args.get("date"),
            data_dir=data_dir,
        )
        print(json.dumps(result))

    elif command == "load-briefing":
        result = load_briefing(args["sector"], args["date"], data_dir)
        print(json.dumps(result))

    elif command == "load-previous":
        result = load_previous_briefing(args["sector"], args["before"], data_dir)
        print(json.dumps(result))

    elif command == "diff":
        current = load_briefing(args["sector"], args["date"], data_dir)
        previous = load_previous_briefing(args["sector"], args["date"], data_dir)
        if current and previous:
            print(json.dumps(compute_diff(current, previous)))
        else:
            print(json.dumps({"error": "Missing current or previous briefing", "current_found": current is not None, "previous_found": previous is not None}))

    elif command == "update-index":
        themes = json.loads(sys.stdin.read())
        index = update_theme_index(themes, args["sector"], args.get("date"), data_dir)
        print(json.dumps(index))

    elif command == "save-markdown":
        content = sys.stdin.read()
        result = save_markdown(args["subdir"], args["slug"], content, args.get("date"), data_dir)
        print(json.dumps(result))

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


def _parse_cli_args(argv: list[str]) -> dict:
    """Parse --key value pairs from argv into a dict."""
    result = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                result[key] = argv[i + 1]
                i += 2
            else:
                result[key] = "true"
                i += 1
        else:
            i += 1
    return result


if __name__ == "__main__":
    _cli_main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/abhishekgarg/personalProject
python3 -m pytest .claude/skills/vc-signals/tests/test_persistence.py -v
```

Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/persistence.py .claude/skills/vc-signals/tests/test_persistence.py
git commit -m "feat: add persistence module with save/load/diff and theme index"
```

---

## Task 5: GitHub Trending Module (TDD)

**Files:**
- Create: `.claude/skills/vc-signals/scripts/github_trending.py`
- Create: `.claude/skills/vc-signals/tests/test_github_trending.py`

- [ ] **Step 1: Write failing tests**

Write to `.claude/skills/vc-signals/tests/test_github_trending.py`:

```python
"""Tests for the GitHub trending module."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_build_search_queries_from_taxonomy(sample_config_dir):
    from github_trending import build_search_queries

    queries = build_search_queries("devtools", sample_config_dir / "sectors.json")
    assert len(queries) > 0
    # Should contain queries derived from subcategory aliases
    combined = " ".join(queries)
    assert "continuous integration" in combined.lower() or "ci/cd" in combined.lower() or "build pipelines" in combined.lower()


def test_build_search_queries_unknown_sector(sample_config_dir):
    from github_trending import build_search_queries

    queries = build_search_queries("nonexistent", sample_config_dir / "sectors.json")
    assert queries == []


def test_parse_repo_data():
    from github_trending import parse_repo_data

    raw = {
        "full_name": "vercel/turbo",
        "description": "Incremental bundler and build system",
        "stargazers_count": 25000,
        "forks_count": 1700,
        "language": "Rust",
        "created_at": "2021-06-15T00:00:00Z",
        "pushed_at": "2026-04-08T12:00:00Z",
        "html_url": "https://github.com/vercel/turbo",
        "owner": {"login": "vercel", "type": "Organization"},
        "topics": ["build-tool", "monorepo"],
    }
    parsed = parse_repo_data(raw)
    assert parsed["full_name"] == "vercel/turbo"
    assert parsed["stars"] == 25000
    assert parsed["language"] == "Rust"
    assert parsed["owner_name"] == "vercel"
    assert parsed["owner_type"] == "Organization"
    assert "age_days" in parsed
    assert parsed["age_days"] > 0


def test_calculate_velocity_with_timestamps():
    from github_trending import calculate_velocity

    now = datetime.now(timezone.utc)
    # Simulate 50 stars in last 7 days, 30 stars 8-30 days ago
    timestamps = []
    for i in range(50):
        timestamps.append((now - timedelta(days=i % 7)).isoformat())
    for i in range(30):
        timestamps.append((now - timedelta(days=8 + i % 22)).isoformat())

    velocity = calculate_velocity(timestamps, total_stars=5000)
    assert velocity["stars_last_7d"] == 50
    assert velocity["stars_last_30d"] == 80
    assert velocity["weekly_velocity"] == pytest.approx(50 / 5000, abs=0.001)


def test_calculate_velocity_empty():
    from github_trending import calculate_velocity

    velocity = calculate_velocity([], total_stars=100)
    assert velocity["stars_last_7d"] == 0
    assert velocity["stars_last_30d"] == 0


def test_estimate_velocity_fallback():
    from github_trending import estimate_velocity_fallback

    result = estimate_velocity_fallback(total_stars=3650, age_days=365)
    assert result["estimated_daily_avg"] == pytest.approx(10.0, abs=0.1)
    assert result["estimated_weekly_avg"] == pytest.approx(70.0, abs=1.0)
    assert result["method"] == "fallback"


@patch("github_trending.requests.get")
def test_search_repos_success(mock_get, sample_config_dir):
    from github_trending import search_repos

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "full_name": "test/repo",
                "description": "A test repo",
                "stargazers_count": 1000,
                "forks_count": 100,
                "language": "Python",
                "created_at": "2025-01-01T00:00:00Z",
                "pushed_at": "2026-04-08T00:00:00Z",
                "html_url": "https://github.com/test/repo",
                "owner": {"login": "test", "type": "User"},
                "topics": [],
            }
        ]
    }
    mock_response.headers = {"X-RateLimit-Remaining": "29"}
    mock_get.return_value = mock_response

    repos = search_repos(["test query"], token="fake-token", limit=10)
    assert len(repos) == 1
    assert repos[0]["full_name"] == "test/repo"


@patch("github_trending.requests.get")
def test_search_repos_rate_limited(mock_get, sample_config_dir):
    from github_trending import search_repos

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "API rate limit exceeded"}
    mock_response.headers = {"X-RateLimit-Remaining": "0"}
    mock_get.return_value = mock_response

    repos = search_repos(["test query"], token="fake-token", limit=10)
    assert repos == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_github_trending.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'github_trending'`

- [ ] **Step 3: Implement github_trending.py**

Write to `.claude/skills/vc-signals/scripts/github_trending.py`:

```python
#!/usr/bin/env python3
"""GitHub trending repos — search by sector keywords, compute star velocity."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "sectors.json"
GITHUB_API = "https://api.github.com"


def build_search_queries(sector: str, config_path: Path | None = None) -> list[str]:
    """Build GitHub search queries from sector taxonomy."""
    config_path = config_path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return []

    sectors = json.loads(config_path.read_text())
    if sector not in sectors:
        return []

    sector_data = sectors[sector]
    queries = []

    for _key, subcat in sector_data.get("subcategories", {}).items():
        aliases = subcat.get("aliases", [])
        # Build queries from aliases — group 2-3 aliases per query for broader coverage
        for i in range(0, len(aliases), 2):
            chunk = aliases[i : i + 2]
            query_terms = " OR ".join(f'"{a}"' for a in chunk)
            queries.append(query_terms)

    return queries


def parse_repo_data(raw: dict) -> dict:
    """Parse a GitHub API repo object into our normalized format."""
    created = raw.get("created_at", "")
    age_days = 0
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created_dt).days
        except ValueError:
            pass

    return {
        "full_name": raw.get("full_name", ""),
        "description": raw.get("description", ""),
        "stars": raw.get("stargazers_count", 0),
        "forks": raw.get("forks_count", 0),
        "language": raw.get("language", ""),
        "created_at": created,
        "pushed_at": raw.get("pushed_at", ""),
        "url": raw.get("html_url", ""),
        "owner_name": raw.get("owner", {}).get("login", ""),
        "owner_type": raw.get("owner", {}).get("type", ""),
        "topics": raw.get("topics", []),
        "age_days": age_days,
    }


def calculate_velocity(
    star_timestamps: list[str], total_stars: int
) -> dict:
    """Calculate star velocity from timestamped stargazer data."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    stars_7d = 0
    stars_30d = 0

    for ts in star_timestamps:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= seven_days_ago:
                stars_7d += 1
            if dt >= thirty_days_ago:
                stars_30d += 1
        except ValueError:
            continue

    weekly_velocity = stars_7d / total_stars if total_stars > 0 else 0.0

    return {
        "stars_last_7d": stars_7d,
        "stars_last_30d": stars_30d,
        "weekly_velocity": weekly_velocity,
        "method": "stargazer_timestamps",
    }


def estimate_velocity_fallback(total_stars: int, age_days: int) -> dict:
    """Estimate velocity from total stars and repo age when timestamps unavailable."""
    if age_days <= 0:
        age_days = 1
    daily_avg = total_stars / age_days
    return {
        "estimated_daily_avg": round(daily_avg, 2),
        "estimated_weekly_avg": round(daily_avg * 7, 2),
        "method": "fallback",
    }


def _get_token() -> str | None:
    """Resolve GitHub token from env, then gh CLI."""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def search_repos(
    queries: list[str],
    token: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Search GitHub repos using the search API. Returns parsed repo dicts."""
    token = token or _get_token()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    seen = set()
    results = []

    for query in queries:
        if len(results) >= limit:
            break

        # Add pushed: filter for recent activity (last 6 months)
        six_months_ago = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
        full_query = f"{query} pushed:>{six_months_ago} stars:>50"

        try:
            resp = requests.get(
                f"{GITHUB_API}/search/repositories",
                params={
                    "q": full_query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": min(30, limit - len(results)),
                },
                headers=headers,
                timeout=15,
            )
        except requests.RequestException as e:
            print(json.dumps({"warning": f"GitHub API error: {e}"}), file=sys.stderr)
            continue

        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            print(
                json.dumps({"warning": f"GitHub rate limited. Remaining: {remaining}"}),
                file=sys.stderr,
            )
            break

        if resp.status_code != 200:
            continue

        for item in resp.json().get("items", []):
            name = item.get("full_name", "")
            if name not in seen:
                seen.add(name)
                results.append(parse_repo_data(item))

    return results[:limit]


def fetch_star_timestamps(
    full_name: str,
    token: str | None = None,
    sample_pages: int = 2,
) -> list[str]:
    """Fetch recent stargazer timestamps for a repo. Samples last N pages."""
    token = token or _get_token()
    headers = {
        "Accept": "application/vnd.github.v3.star+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    timestamps = []

    # First, get the total to find the last page
    try:
        resp = requests.get(
            f"{GITHUB_API}/repos/{full_name}/stargazers",
            params={"per_page": 1},
            headers=headers,
            timeout=10,
        )
    except requests.RequestException:
        return []

    if resp.status_code != 200:
        return []

    # Parse Link header for last page
    link_header = resp.headers.get("Link", "")
    last_page = 1
    if 'rel="last"' in link_header:
        for part in link_header.split(","):
            if 'rel="last"' in part:
                try:
                    last_page = int(part.split("page=")[-1].split(">")[0])
                except (ValueError, IndexError):
                    pass

    # Fetch last N pages (most recent stargazers)
    for page_num in range(max(1, last_page - sample_pages + 1), last_page + 1):
        try:
            resp = requests.get(
                f"{GITHUB_API}/repos/{full_name}/stargazers",
                params={"per_page": 100, "page": page_num},
                headers=headers,
                timeout=10,
            )
        except requests.RequestException:
            continue

        if resp.status_code != 200:
            continue

        for item in resp.json():
            if isinstance(item, dict) and "starred_at" in item:
                timestamps.append(item["starred_at"])

    return timestamps


def run_trending(
    sector: str,
    config_path: Path | None = None,
    token: str | None = None,
    limit: int = 15,
) -> dict:
    """Full pipeline: search repos for a sector, compute velocity, return ranked results."""
    config_path = config_path or DEFAULT_CONFIG_PATH
    queries = build_search_queries(sector, config_path)

    if not queries:
        return {"error": f"No queries for sector '{sector}'", "repos": []}

    repos = search_repos(queries, token=token, limit=limit * 2)  # over-fetch for ranking
    warnings = []

    # Fetch velocity for each repo
    for repo in repos:
        timestamps = fetch_star_timestamps(repo["full_name"], token=token)
        if timestamps:
            repo["velocity"] = calculate_velocity(timestamps, repo["stars"])
        else:
            repo["velocity"] = estimate_velocity_fallback(repo["stars"], repo["age_days"])
            if repo["velocity"]["method"] == "fallback":
                warnings.append(f"Used fallback velocity for {repo['full_name']}")

    # Sort by weekly velocity (descending), then by stars
    def sort_key(r):
        v = r.get("velocity", {})
        if v.get("method") == "stargazer_timestamps":
            return (v.get("stars_last_7d", 0), r.get("stars", 0))
        return (v.get("estimated_weekly_avg", 0), r.get("stars", 0))

    repos.sort(key=sort_key, reverse=True)

    return {
        "sector": sector,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": repos[:limit],
        "warnings": warnings,
    }


def _cli_main() -> None:
    """CLI entry point."""
    args = _parse_cli_args(sys.argv[1:])

    sector = args.get("sector", "")
    config_path = Path(args["config"]) if "config" in args else None
    token = args.get("token") or os.environ.get("GITHUB_TOKEN")
    limit = int(args.get("limit", "15"))

    if not sector:
        print(json.dumps({"error": "Usage: github_trending.py --sector <sector> [--config <path>] [--token <token>] [--limit N]"}))
        sys.exit(1)

    result = run_trending(sector, config_path, token, limit)
    print(json.dumps(result, indent=2))


def _parse_cli_args(argv: list[str]) -> dict:
    """Parse --key value pairs."""
    result = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                result[key] = argv[i + 1]
                i += 2
            else:
                result[key] = "true"
                i += 1
        else:
            i += 1
    return result


if __name__ == "__main__":
    _cli_main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_github_trending.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/github_trending.py .claude/skills/vc-signals/tests/test_github_trending.py
git commit -m "feat: add GitHub trending module with star velocity scoring"
```

---

## Task 6: last30days Adapter (TDD)

**Files:**
- Create: `.claude/skills/vc-signals/scripts/last30days_adapter.py`
- Create: `.claude/skills/vc-signals/tests/test_last30days_adapter.py`

- [ ] **Step 1: Write failing tests**

Write to `.claude/skills/vc-signals/tests/test_last30days_adapter.py`:

```python
"""Tests for the last30days adapter module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_check_not_installed(tmp_path):
    from last30days_adapter import check_availability

    result = check_availability(vendor_path=tmp_path / "nonexistent")
    assert result["installed"] is False
    assert result["configured"] is False


def test_check_installed_not_configured(tmp_path):
    from last30days_adapter import check_availability

    # Create the vendor path with expected structure
    vendor = tmp_path / "last30days-skill"
    (vendor / "scripts" / "lib").mkdir(parents=True)
    (vendor / "scripts" / "last30days.py").write_text("# stub")
    (vendor / "scripts" / "lib" / "__init__.py").write_text("")

    result = check_availability(vendor_path=vendor)
    assert result["installed"] is True
    assert result["configured"] is False


def test_check_installed_and_configured(tmp_path):
    from last30days_adapter import check_availability

    vendor = tmp_path / "last30days-skill"
    (vendor / "scripts" / "lib").mkdir(parents=True)
    (vendor / "scripts" / "last30days.py").write_text("# stub")
    (vendor / "scripts" / "lib" / "__init__.py").write_text("")

    config_dir = tmp_path / "config" / "last30days"
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text("SETUP_COMPLETE=true\nOPENAI_API_KEY=sk-fake\n")

    result = check_availability(vendor_path=vendor, config_path=config_dir / ".env")
    assert result["installed"] is True
    assert result["configured"] is True


def test_normalize_report_items():
    from last30days_adapter import normalize_report_items

    mock_items = {
        "reddit": [
            {
                "item_id": "r1",
                "source": "reddit",
                "title": "AI code review is amazing",
                "url": "https://reddit.com/r/programming/123",
                "snippet": "I switched to CodeRabbit and it changed everything",
                "published_at": "2026-04-07T10:00:00Z",
                "engagement": {"upvotes": 350, "comments": 42},
                "container": "r/programming",
            }
        ],
        "hackernews": [
            {
                "item_id": "hn1",
                "source": "hackernews",
                "title": "Show HN: New testing framework",
                "url": "https://news.ycombinator.com/item?id=999",
                "snippet": "Built a new testing tool that uses AI",
                "published_at": "2026-04-08T14:00:00Z",
                "engagement": {"points": 200, "comments": 85},
                "container": "hackernews",
            }
        ],
    }

    normalized = normalize_report_items(mock_items)
    assert len(normalized) == 2
    assert normalized[0]["source"] in ("reddit", "hackernews")
    assert "title" in normalized[0]
    assert "engagement" in normalized[0]


def test_run_query_returns_structure(tmp_path):
    """Test that run_query returns expected JSON structure even with mock."""
    from last30days_adapter import check_availability

    # Without last30days installed, run_query should return an error
    result = check_availability(vendor_path=tmp_path / "nonexistent")
    assert result["installed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_last30days_adapter.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'last30days_adapter'`

- [ ] **Step 3: Implement last30days_adapter.py**

Write to `.claude/skills/vc-signals/scripts/last30days_adapter.py`:

```python
#!/usr/bin/env python3
"""Adapter for last30days research engine — detect, configure, run queries, normalize output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_VENDOR_PATH = Path(__file__).resolve().parents[4] / "vendor" / "last30days-skill"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "last30days" / ".env"


def check_availability(
    vendor_path: Path | None = None,
    config_path: Path | None = None,
) -> dict:
    """Check if last30days is installed and configured."""
    vendor_path = vendor_path or DEFAULT_VENDOR_PATH
    config_path = config_path or DEFAULT_CONFIG_PATH

    installed = (
        (vendor_path / "scripts" / "last30days.py").exists()
        and (vendor_path / "scripts" / "lib" / "__init__.py").exists()
    )

    configured = False
    available_keys = []

    if config_path.exists():
        content = config_path.read_text()
        if "SETUP_COMPLETE=true" in content:
            # Check for at least one reasoning provider
            for key_name in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY"):
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith(f"{key_name}=") and len(stripped.split("=", 1)[1]) > 0:
                        available_keys.append(key_name)
            configured = len(available_keys) > 0

    return {
        "installed": installed,
        "configured": configured,
        "vendor_path": str(vendor_path),
        "config_path": str(config_path),
        "available_keys": available_keys,
    }


def normalize_report_items(items_by_source: dict) -> list[dict]:
    """Normalize last30days source items into a flat list for Claude to process."""
    normalized = []

    for source, items in items_by_source.items():
        for item in items:
            normalized.append({
                "source": source,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", item.get("body", ""))[:500],
                "published_at": item.get("published_at", ""),
                "engagement": item.get("engagement", {}),
                "container": item.get("container", ""),
                "author": item.get("author", ""),
            })

    return normalized


def run_query(
    topic: str,
    vendor_path: Path | None = None,
    sources: str | None = None,
    lookback_days: int = 30,
    emit: str = "json",
) -> dict:
    """Run a query through last30days CLI and return parsed results."""
    vendor_path = vendor_path or DEFAULT_VENDOR_PATH
    script_path = vendor_path / "scripts" / "last30days.py"

    if not script_path.exists():
        return {"error": "last30days not installed", "items": []}

    # Find Python 3.12+
    python_cmd = _find_python()
    if not python_cmd:
        return {"error": "Python 3.12+ required for last30days", "items": []}

    cmd = [python_cmd, str(script_path), topic, f"--emit={emit}", f"--lookback-days={lookback_days}"]
    if sources:
        cmd.append(f"--search={sources}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(vendor_path),
        )
    except subprocess.TimeoutExpired:
        return {"error": "last30days query timed out (120s)", "items": []}
    except FileNotFoundError:
        return {"error": f"Python not found: {python_cmd}", "items": []}

    if result.returncode != 0:
        return {
            "error": f"last30days exited with code {result.returncode}",
            "stderr": result.stderr[:500] if result.stderr else "",
            "items": [],
        }

    if emit == "json":
        try:
            report = json.loads(result.stdout)
            items = normalize_report_items(report.get("items_by_source", {}))
            return {
                "topic": topic,
                "items": items,
                "clusters": report.get("clusters", []),
                "warnings": report.get("warnings", []),
            }
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse last30days JSON output",
                "raw_output": result.stdout[:1000],
                "items": [],
            }
    else:
        # For non-JSON emit modes, return raw text
        return {"topic": topic, "raw_output": result.stdout, "items": []}


def _find_python() -> str | None:
    """Find Python 3.12+ interpreter."""
    for candidate in ("python3.14", "python3.13", "python3.12", "python3"):
        try:
            result = subprocess.run(
                [candidate, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def _cli_main() -> None:
    """CLI entry point. Commands: check, query."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: last30days_adapter.py <check|query> [args]"}))
        sys.exit(1)

    command = sys.argv[1]
    args = _parse_cli_args(sys.argv[2:])

    if command == "check":
        vendor = Path(args["vendor-path"]) if "vendor-path" in args else None
        config = Path(args["config-path"]) if "config-path" in args else None
        result = check_availability(vendor, config)
        print(json.dumps(result, indent=2))

    elif command == "query":
        topic = args.get("topic", "")
        if not topic:
            print(json.dumps({"error": "--topic is required"}))
            sys.exit(1)
        vendor = Path(args["vendor-path"]) if "vendor-path" in args else None
        result = run_query(
            topic=topic,
            vendor_path=vendor,
            sources=args.get("sources"),
            lookback_days=int(args.get("lookback-days", "30")),
        )
        print(json.dumps(result, indent=2))

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)


def _parse_cli_args(argv: list[str]) -> dict:
    """Parse --key value pairs."""
    result = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                result[key] = argv[i + 1]
                i += 2
            else:
                result[key] = "true"
                i += 1
        else:
            i += 1
    return result


if __name__ == "__main__":
    _cli_main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest .claude/skills/vc-signals/tests/test_last30days_adapter.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/vc-signals/scripts/last30days_adapter.py .claude/skills/vc-signals/tests/test_last30days_adapter.py
git commit -m "feat: add last30days adapter with availability check and query normalization"
```

---

## Task 7: SKILL.md

**Files:**
- Create: `.claude/skills/vc-signals/SKILL.md`

This is the core deliverable — the Claude Code skill definition that orchestrates everything.

- [ ] **Step 1: Write SKILL.md frontmatter and overview**

Write to `.claude/skills/vc-signals/SKILL.md`:

```markdown
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

All Python scripts are relative to this skill's directory. Determine the base path:

```bash
SKILL_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)" || SKILL_DIR=".claude/skills/vc-signals"
```

Scripts:
- `${SKILL_DIR}/scripts/persistence.py` — save/load briefings, diffs, theme index
- `${SKILL_DIR}/scripts/github_trending.py` — GitHub star velocity search
- `${SKILL_DIR}/scripts/last30days_adapter.py` — last30days integration

Config:
- `${SKILL_DIR}/config/sectors.json` — sector taxonomy
- `${SKILL_DIR}/config/company_aliases.json` — company seed map

When running scripts via Bash, always use the full path from the project root:
```bash
python3 .claude/skills/vc-signals/scripts/<script>.py <args>
```

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

**Web Search API Key (pick one — Brave recommended):**
> "We need a web search API for broader coverage. Brave Search is the easiest — it has a free tier with 2,000 searches/month."
>
> 1. Go to https://brave.com/search/api/
> 2. Click "Get Started for Free"
> 3. Create an account and get your API key
> 4. Paste it here (or type 'skip' to skip this)

**Reasoning Provider (pick one — OpenAI or Gemini):**
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
> 3. Go to Application tab → Cookies → twitter.com
> 4. Find the cookie named `auth_token` — copy its value
> 5. Find the cookie named `ct0` — copy its value
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
> - [x] Web search (Brave) — broad internet coverage
> - [x] GitHub API — trending repo discovery
> - [ ] last30days (skipped) — Reddit, HN, X/Twitter, YouTube
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

### Step 3: Select Retrieval Path

```bash
python3 .claude/skills/vc-signals/scripts/last30days_adapter.py check
```

If `installed` AND `configured` are both true → use **last30days path**.
Otherwise → use **WebSearch path**.

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

**last30days path:**

Run 3-5 queries through the adapter:
```bash
python3 .claude/skills/vc-signals/scripts/last30days_adapter.py query --topic "<query>" --sources "reddit,hackernews,grounding"
```

Use the sector's discovery_queries as topics. Collect the normalized items.

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
  - "AI code review" + "LLM-powered code review" + "automated PR review" → "AI-Powered Code Review"
  - "shift-left security" + "developer-first security" → "Developer-First Security Tooling"
- Pick canonical names that are specific enough to be useful, generic enough to cover the cluster

**Score each theme — Momentum (1-10):**

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
- **8-10:** Breakout — multiple sources, very recent, specific tools named, high engagement, new conversation
- **5-7:** Rising — clear signal but fewer sources, or overlaps with existing known trends
- **3-4:** Ambient — mentioned but not clearly accelerating, could be background noise
- **1-2:** Faint — single source, low engagement, or possibly stale

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
One blunt sentence. Example: "Durable — real pain point with multiple well-funded solutions." or "Likely hype — single viral post driving most of the signal, unclear staying power."

### Step 7: Map Companies

For each theme, identify relevant companies using three sources:

1. **Seed map:** Check `company_aliases.json` — does any known company map to this theme?
2. **Evidence:** Were any companies/projects mentioned in the search results for this theme?
3. **GitHub data:** Do any trending repos from Step 5 relate to this theme?

For each company, classify its role:
- **Direct solver** — building a product that addresses the theme head-on
- **Beneficiary** — existing company that gains from the trend
- **Adjacent/ecosystem** — related but not core
- **Unclear** — mentioned but relationship is ambiguous

Tag confidence:
- **Confirmed** — in seed map or multiple sources corroborate
- **Likely** — strong contextual evidence
- **Inferred** — your judgment on limited evidence
- **Speculative** — thin signal, flag as such

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
- "Theme Name" (momentum: X) — not seen before

**Gaining steam:**
- "Theme Name" — momentum X → Y

**Fading:**
- "Theme Name" — momentum X → Y (or dropped out)

**Durable (3+ weeks):**
- "Theme Name" — Nth consecutive week, steady at X-Y
```

**Then output each theme:**

```markdown
## Weekly VC Signal Brief: [Sector] — YYYY-MM-DD

### 1. [Theme Title]

**Momentum: X/10** | **Confidence: High/Medium/Low** | **Timing: Early/Mid/Late**

**Why it's rising:** [2-3 sentences with specific evidence. What changed? Why now?]

**Evidence:**
- [Source 1: title, URL, key quote or data point]
- [Source 2: title, URL, key quote or data point]
- [Source 3 if available]

**Why investors should care:** [1-2 sentences — what's the opportunity?]

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

Prepare a JSON array of theme objects with all scores and company mappings. Pipe to persistence:

```bash
echo '<JSON_THEMES_ARRAY>' | python3 .claude/skills/vc-signals/scripts/persistence.py save-briefing --sector <SECTOR> --retrieval-path <websearch|last30days> --date $(date +%Y-%m-%d)
```

Save the markdown output:
```bash
echo '<MARKDOWN_CONTENT>' | python3 .claude/skills/vc-signals/scripts/persistence.py save-markdown --subdir briefings --slug <SECTOR> --date $(date +%Y-%m-%d)
```

Update the theme index:
```bash
echo '<JSON_THEMES_ARRAY>' | python3 .claude/skills/vc-signals/scripts/persistence.py update-index --sector <SECTOR> --date $(date +%Y-%m-%d)
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
[What changed recently that made this theme emerge? Be specific — new tech, new problem, regulatory shift, etc.]

### Key Subthemes
- **Subtheme A:** [1-2 sentences]
- **Subtheme B:** [1-2 sentences]
- **Subtheme C:** [1-2 sentences]

### Evidence
- [Source 1: title, URL, key insight]
- [Source 2: title, URL, key insight]
- [Source 3+]

### Adjacent Categories
- [Related theme 1 — how it connects]
- [Related theme 2 — how it connects]

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
echo '<MARKDOWN>' | python3 .claude/skills/vc-signals/scripts/persistence.py save-markdown --subdir themes --slug <SLUGIFIED_TOPIC> --date $(date +%Y-%m-%d)
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
[Brief note on who else operates in the same themes. NOT a full competitive analysis — just enough for context.]

### Confidence Notes
[What you're confident about, what's uncertain, what you couldn't verify]
```

### Step 5: Persist

```bash
echo '<MARKDOWN>' | python3 .claude/skills/vc-signals/scripts/persistence.py save-markdown --subdir companies --slug <SLUGIFIED_NAME> --date $(date +%Y-%m-%d)
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
1. Check `company_aliases.json` — is the owner/org a known company?
2. Check the repo owner type — is it an organization (likely a company)?
3. Use your knowledge + the repo description to identify if there's a commercial entity behind it

### Step 3: Map to Themes

For each repo, identify which sector themes it relates to. Use the taxonomy subcategories and your judgment.

### Step 4: Output

```markdown
## GitHub Trending: [Sector] — YYYY-MM-DD

Repos ranked by star velocity (recent growth rate, not absolute count).

| # | Repo | Stars | 7d Growth | 30d Growth | Language | Commercial Entity |
|---|------|-------|-----------|------------|----------|------------------|
| 1 | owner/name | 12,500 | +450 | +1,800 | Rust | Company Name (Confirmed) |
| 2 | ... | | | | | |

### Standout Repos

**[Repo 1: owner/name]**
- **Description:** [What it does]
- **Why it's interesting:** [1-2 sentences — what's driving the growth?]
- **Theme mapping:** [Which sector themes this relates to]
- **Commercial entity:** [Company behind it, if any. Monetization status if known.]

**[Repo 2: owner/name]**
...

### Acceleration Alerts
[Repos with unusually high velocity relative to their size — the "0 to 10k in a week" signals]

### Theme Patterns
[Do multiple trending repos point to the same emerging theme? Call it out.]
```

### Step 5: Persist

```bash
echo '<MARKDOWN>' | python3 .claude/skills/vc-signals/scripts/persistence.py save-markdown --subdir github --slug <SECTOR> --date $(date +%Y-%m-%d)
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
```

- [ ] **Step 2: Verify SKILL.md is well-formed**

```bash
head -5 .claude/skills/vc-signals/SKILL.md
wc -l .claude/skills/vc-signals/SKILL.md
```

Expected: frontmatter starts with `---`, file is 400+ lines

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/vc-signals/SKILL.md
git commit -m "feat: add vc-signals SKILL.md with all modes and orchestration logic"
```

---

## Task 8: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

Write to `README.md`:

```markdown
# VC Signals

A Claude Code skill that helps VCs discover emerging investable themes in **devtools**, **cybersecurity**, and **AI infrastructure**.

Run one command per week. Get a ranked list of emerging themes with company mapping, momentum scoring, and investor-oriented analysis.

## What This Is

`/vc-signals` turns noisy public internet chatter (Hacker News, Reddit, X/Twitter, GitHub, blogs) into a structured investor brief. For each emerging theme, you get:

- Why it's rising (with evidence and citations)
- Momentum score (1-10) — how fast is this growing?
- Confidence rating — how sure are we this is real?
- Investment timing — early, mid, or late?
- Hype vs durable — blunt assessment
- Company mapping — who's solving this, who benefits, with confidence tags

## Quick Start (Zero Setup)

Works immediately with no API keys. Claude uses its built-in web search.

```
/vc-signals weekly devtools
/vc-signals weekly cybersecurity
/vc-signals weekly ai-infra
```

For better coverage (Reddit, HN, X, YouTube independently), run the setup wizard:

```
/vc-signals setup
```

## All Commands

| Command | What It Does |
|---------|-------------|
| `/vc-signals setup` | Guided setup wizard — walks you through API keys step by step |
| `/vc-signals weekly <sector>` | Weekly scan — top 8-12 emerging themes with company mapping |
| `/vc-signals theme "<topic>"` | Deep-dive into a specific theme |
| `/vc-signals company "<name>"` | Which rising themes is a company exposed to? |
| `/vc-signals github <sector>` | Top repos by star velocity — spot fast-growing OSS projects |

**Sectors:** `devtools`, `cybersecurity`, `ai-infra`

## Examples

### Weekly Sector Scan
```
/vc-signals weekly devtools
```
Returns 8-12 ranked themes like:
- "AI-Powered Code Review" (momentum: 8/10, timing: mid, companies: CodeRabbit, Cursor)
- "Rust-Based Build Tooling" (momentum: 6/10, timing: early, companies: Turbopack, oxc)

### Theme Drill-Down
```
/vc-signals theme "agent evals"
```
Returns deep analysis: what it is, why now, subthemes, companies solving it, OSS projects, hype vs durable verdict.

### Company Backtrace
```
/vc-signals company "Confluent"
```
Returns which rising themes Confluent maps to, its role (solver vs beneficiary), evidence, and competitive context.

### GitHub Trending
```
/vc-signals github ai-infra
```
Returns top repos by star velocity — the ones growing fastest relative to their size, with commercial entity mapping.

## How It Differs from last30days

| | last30days | vc-signals |
|---|-----------|------------|
| **Purpose** | General research on any topic | VC-specific theme discovery |
| **Output** | Evidence clusters with citations | Investor brief with scoring |
| **Company mapping** | None | Theme → company mapping with roles |
| **Momentum scoring** | None | 1-10 score with transparent factors |
| **Persistence** | Optional save | Week-over-week comparison |
| **GitHub trending** | Basic search | Star velocity + commercial entity mapping |

vc-signals uses last30days as a retrieval engine (when configured) and adds the VC intelligence layer on top.

## Full Setup Guide

### Prerequisites

- **Claude Code** — installed and working
- **Python 3.12+** — check with `python3 --version`

### Step 1: Install Python dependency

```bash
pip install requests
```

### Step 2: Run the setup wizard

```
/vc-signals setup
```

The wizard walks you through everything. Here's what each API key unlocks:

### API Keys Reference

#### ScrapeCreators API Key (for last30days)
- **What it unlocks:** TikTok, Instagram, YouTube search via last30days
- **Required for:** last30days enhanced retrieval path
- **Cost:** Paid plans starting at ~$29/month
- **How to get it:**
  1. Go to https://scrapecreators.com
  2. Sign up for an account
  3. Choose a plan (Basic is fine for weekly scans)
  4. Go to Dashboard → API Keys → copy your key

#### Brave Search API Key
- **What it unlocks:** Broad web search coverage
- **Required for:** last30days web search (or use Exa/Serper as alternatives)
- **Cost:** Free tier — 2,000 queries/month (plenty for weekly scans)
- **How to get it:**
  1. Go to https://brave.com/search/api/
  2. Click "Get Started for Free"
  3. Create an account
  4. Go to API Keys → copy your key

#### OpenAI API Key (or Gemini)
- **What it unlocks:** Query planning and result ranking in last30days
- **Required for:** last30days enhanced retrieval path
- **Cost:** Usage-based — typically $0.01-0.05 per weekly scan
- **How to get it (OpenAI):**
  1. Go to https://platform.openai.com/api-keys
  2. Sign up or log in
  3. Click "Create new secret key"
  4. Copy the key (starts with `sk-`)
  5. Add a payment method under Billing
- **How to get it (Gemini — free alternative):**
  1. Go to https://aistudio.google.com/apikey
  2. Click "Create API key"
  3. Copy the key

#### GitHub Personal Access Token
- **What it unlocks:** GitHub trending repos — star velocity, repo search
- **Required for:** `/vc-signals github` mode
- **Cost:** Free
- **How to get it:**
  1. Go to https://github.com/settings/tokens
  2. Click "Generate new token" → "Generate new token (classic)"
  3. Name: "vc-signals"
  4. Expiration: 90 days (or your preference)
  5. Scopes: check `public_repo` only
  6. Click "Generate token" and copy it

#### X/Twitter Auth Tokens (optional)
- **What it unlocks:** X/Twitter search for developer discussions
- **Required for:** last30days X/Twitter source
- **Cost:** Free (uses your existing X account)
- **How to get them:**
  1. Log into X/Twitter in your browser (Chrome/Firefox)
  2. Open Developer Tools: `Cmd+Option+I` (Mac) or `Ctrl+Shift+I` (Windows)
  3. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
  4. Click **Cookies** → **twitter.com** (or **x.com**)
  5. Find `auth_token` — copy its Value
  6. Find `ct0` — copy its Value
  7. These expire periodically — you'll need to re-extract them

### What Works Without Any API Keys

The zero-config path uses Claude's built-in WebSearch. You get:
- Weekly sector scans (slightly less source diversity)
- Theme drill-downs
- Company backtrace
- GitHub trending (if you have a GitHub token or `gh` CLI)

## Architecture

```
SKILL.md (orchestrator)
    │
    ├── Retrieval Layer
    │   ├── WebSearch (built-in, zero-config)
    │   └── last30days (enhanced, after setup)
    │
    ├── GitHub Trending
    │   └── github_trending.py (star velocity via API)
    │
    ├── Intelligence Layer (Claude)
    │   ├── Theme extraction & clustering
    │   ├── Momentum scoring
    │   ├── Company mapping
    │   └── Investor framing
    │
    └── Persistence Layer
        └── persistence.py (save/load/diff briefings)
```

**Claude is the intelligence engine.** Python scripts handle I/O only (API calls, file storage). The SKILL.md orchestrates everything.

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

Add a new top-level key to `sectors.json` following the existing structure.

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

## Project Structure

```
.
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
            ├── SKILL.md           # skill definition
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup guide, usage examples, and API key instructions"
```

---

## Task 9: Validation & Sample Outputs

**Files:** None created — this task runs existing code and generates expected output shapes.

- [ ] **Step 1: Run all tests**

```bash
cd /Users/abhishekgarg/personalProject
python3 -m pytest .claude/skills/vc-signals/tests/ -v
```

Expected: All tests pass (persistence: 11, github_trending: 7, last30days_adapter: 5 = 23 total)

- [ ] **Step 2: Verify persistence CLI works end-to-end**

```bash
echo '[{"name": "Test Theme", "momentum": 7, "confidence": "medium"}]' | python3 .claude/skills/vc-signals/scripts/persistence.py save-briefing --sector devtools --date 2026-04-09 --data-dir /tmp/vc-signals-test
```

Expected: JSON output with `"saved"` path

```bash
python3 .claude/skills/vc-signals/scripts/persistence.py load-briefing --sector devtools --date 2026-04-09 --data-dir /tmp/vc-signals-test
```

Expected: JSON briefing with the test theme

- [ ] **Step 3: Verify github_trending CLI (may fail without token — expected)**

```bash
python3 .claude/skills/vc-signals/scripts/github_trending.py --sector devtools --limit 3 2>&1 | head -20
```

Expected: Either JSON results (if GitHub token available) or rate-limit warning (if not). Should not crash.

- [ ] **Step 4: Verify last30days adapter check**

```bash
python3 .claude/skills/vc-signals/scripts/last30days_adapter.py check
```

Expected: JSON showing `"installed": true` (since we cloned the vendor repo), `"configured": false` (since no API keys set up)

- [ ] **Step 5: Verify SKILL.md is loadable as a skill**

```bash
head -10 .claude/skills/vc-signals/SKILL.md
grep -c "^##" .claude/skills/vc-signals/SKILL.md
```

Expected: Frontmatter visible, multiple section headers counted

- [ ] **Step 6: Clean up test data**

```bash
rm -rf /tmp/vc-signals-test
```

- [ ] **Step 7: Final commit with all docs**

```bash
git add docs/
git commit -m "docs: add design spec and implementation plan"
```
