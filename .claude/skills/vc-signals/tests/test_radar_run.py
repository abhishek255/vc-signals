"""Tests for the weekly radar run orchestration helpers."""

from __future__ import annotations

import json
from pathlib import Path


def test_filter_repo_rejects_bot_digests_and_tutorials():
    from radar_run import is_repo_noise

    assert is_repo_noise({"full_name": "duanyytop/agents-radar", "description": "Daily AI ecosystem digest from 10 sources"})
    assert is_repo_noise({"full_name": "learn/course", "description": "Companion repo for beginner to pro course"})
    assert is_repo_noise({"full_name": "cfg/yamls", "description": "Mihomo clash yaml config files"})
    assert is_repo_noise({"full_name": "ChrisWiles/claude-code-showcase", "description": "Comprehensive Claude Code project configuration example"})
    assert is_repo_noise({"full_name": "anthropics/claude-code-security-review", "description": "AI-powered security review GitHub Action"})
    assert is_repo_noise({"full_name": "LongQT-sea/macos-iso-builder", "description": "Generate bootable macOS installer ISO"})
    assert is_repo_noise({"full_name": "ziwenhahaha/daily-paper-reader", "description": "daily arXiv paper recommendation platform"})
    assert is_repo_noise({"full_name": "google-github-actions/run-gemini-cli", "description": "A GitHub Action invoking the Gemini CLI"})
    assert is_repo_noise({"full_name": "github/ai-moderator", "description": "An AI-powered GitHub Action that detects and tags spam in your repository"})
    assert is_repo_noise({"full_name": "OndCo/Ond-ESG-Intelligence-Platform", "description": "ESG data with Azure Data Factory, Databricks, Azure ML, Power BI dashboards, and GitHub Actions CI/CD"})
    assert is_repo_noise({"full_name": "mohitmishra786/low-level-dev-skills", "description": "A curated suite of AI agent skills for systems and low-level programming"})


def test_filter_repo_keeps_investable_oss_signal():
    from radar_run import is_repo_noise

    assert not is_repo_noise({
        "full_name": "affaan-m/agentshield",
        "description": "AI agent security scanner for MCP servers and tool permissions",
        "topics": ["ai-agent", "security", "mcp"],
    })
    assert not is_repo_noise({
        "full_name": "praetorian-inc/augustus",
        "description": "LLM security testing framework for prompt injection and jailbreaks",
        "topics": ["ai-security"],
    })


def test_filter_evidence_rejects_social_noise():
    from radar_run import is_evidence_noise

    assert is_evidence_noise({"title": "Introducing Claude Opus 4.7, our most capable Opus model yet."})
    assert is_evidence_noise({"title": "[Hiring] Tech UGC creators for an AI workflow automation tool"})
    assert is_evidence_noise({"title": "AI Builders Digest — 2026-04-15"})
    assert is_evidence_noise({"title": "Daily Content Summary 2026-04-06", "author": "github-actions[bot]"})
    assert is_evidence_noise({"title": "UA-4544 Frontend", "snippet": "This is an auto-generated comment: summarize by coderabbit.ai"})
    assert is_evidence_noise({"title": "Market Research: AgentClash Competitive Landscape, Revenue Projections & Funding Playbook"})
    assert is_evidence_noise({"title": "📡 Tech & AI News — 05 April 2026"})
    assert is_evidence_noise({"title": "Deepseek V4 is a sign that the future world AI-OS may be open source"})
    assert is_evidence_noise({"title": "Salesforce launches Headless 360 to turn its entire platform into infrastructure for AI agents"})
    assert is_evidence_noise({"title": "A Complete Guide on How to Play Black Ops 3 in 2026"})
    assert is_evidence_noise({"title": "Refinement"})
    assert is_evidence_noise({"title": "Chemical Families"})
    assert is_evidence_noise({"title": "feat: Complete Statcast pitch-level data ingestion and comprehensive data acquisition"})
    assert is_evidence_noise({"title": "chore(data-warehouse): Moved source docs from .com to this repo"})
    assert is_evidence_noise({"title": "docs(architecture): amend ADR-042 to scope Python-first to internal automation"})
    assert is_evidence_noise({"title": "Eridu Emerges from Stealth with $200M+ Funding, Claims AI Networking Breakthrough (2026-04-20)"})
    assert not is_evidence_noise({"title": "Show HN: A security scanner for AI Agent Skills"})


def test_merge_attio_context_preserves_action_when_no_client():
    from radar_run import merge_attio_context

    companies = [{"name": "Cascade", "domain": "runcascade.com", "action": "assign owner"}]
    result = merge_attio_context(companies, attio_client=None)
    assert result[0]["attio_status"] == "unknown"
    assert result[0]["action"] == "assign owner"


def test_merge_attio_context_overrides_action_with_attio_action():
    from radar_run import merge_attio_context

    class FakeAttio:
        def match_company(self, company):
            return {
                "attio_status": "no_owner",
                "attio_action": "assign owner",
                "attio_lists": ["Tier 1 Investors Deal Activity MASTER"],
            }

    companies = [{"name": "Cascade", "domain": "runcascade.com", "action": "monitor"}]
    result = merge_attio_context(companies, FakeAttio())
    assert result[0]["attio_status"] == "no_owner"
    assert result[0]["action"] == "assign owner"
    assert result[0]["attio_lists"] == ["Tier 1 Investors Deal Activity MASTER"]


def test_merge_attio_context_preserves_oss_action_vocabulary():
    from radar_run import merge_attio_context

    class FakeAttio:
        def match_company(self, company):
            return {"attio_status": "no_match", "attio_action": "assign owner"}

    companies = [{"name": "AgentShield", "sector": "OSS / Cybersecurity", "action": "contact maintainer"}]
    result = merge_attio_context(companies, FakeAttio())
    assert result[0]["attio_status"] == "no_match"
    assert result[0]["action"] == "contact maintainer"


def test_merge_attio_context_preserves_likely_too_late_label():
    from radar_run import merge_attio_context

    class FakeAttio:
        def match_company(self, company):
            return {"attio_status": "no_owner", "attio_action": "assign owner"}

    companies = [{"name": "Factory", "sector": "Devtools", "action": "likely too late"}]
    result = merge_attio_context(companies, FakeAttio())
    assert result[0]["attio_status"] == "no_owner"
    assert result[0]["action"] == "likely too late"


def test_render_partner_preview_groups_sections(tmp_path):
    from radar_run import render_partner_preview

    companies = [
        {
            "name": "Cascade",
            "sector": "AI Infra",
            "theme": "Agent reliability",
            "investment_interest": "High",
            "evidence_confidence": "High",
            "attio_status": "no_owner",
            "action": "assign owner",
            "why_on_radar": "YC W26 company adapting models to proprietary workflows.",
            "why_this_may_be_noise": "Positioning may be too broad.",
            "source": "https://www.ycombinator.com/companies/cascade",
            "company_linkedin": "https://www.linkedin.com/company/cascade-ai",
            "company_x": "https://x.com/cascade_ai",
            "founder_profiles": [
                {"name": "Asha Rao", "linkedin": "https://www.linkedin.com/in/asharao", "x": "https://x.com/asharao"}
            ],
        }
    ]
    markdown = render_partner_preview(companies, ["Agent reliability"], output_path=tmp_path / "brief.md")

    assert "## Marathon Partner Preview" in markdown
    assert "| Company | Sector | Theme | Interest | Evidence | Attio | Action | LinkedIn | Founders | X | Why On Radar | Why This May Be Noise | Source |" in markdown
    assert "| Cascade | AI Infra | Agent reliability | High | High | no_owner | assign owner | https://www.linkedin.com/company/cascade-ai | Asha Rao: https://www.linkedin.com/in/asharao, https://x.com/asharao | https://x.com/cascade_ai |" in markdown
    assert "### AI Infra" in markdown
    assert (tmp_path / "brief.md").exists()


def test_save_raw_evidence_writes_json(tmp_path):
    from radar_run import save_raw_evidence

    path = save_raw_evidence({"github": [{"full_name": "x/y"}]}, output_dir=tmp_path, run_date="2026-05-04")
    assert path.name == "2026-05-04-raw-evidence.json"
    assert json.loads(path.read_text())["github"][0]["full_name"] == "x/y"


def test_build_sector_collection_queries_adds_grounded_company_discovery():
    from radar_run import build_sector_collection_queries

    config = {
        "ai-infra": {
            "display_name": "AI Infrastructure",
            "discovery_queries": ["AI infra startups gaining traction"],
            "subcategories": {
                "agent_infra": {
                    "seed_queries": ["agent infrastructure startups emerging"],
                }
            },
        }
    }

    queries = build_sector_collection_queries("ai-infra", config, grounded_available=True, max_queries=3)

    assert len(queries) == 3
    assert queries[0]["kind"] == "conversation"
    assert queries[0]["sources"] == "reddit,hackernews,github"
    assert any("site:ycombinator.com/companies" in query["topic"] for query in queries)
    assert any("Seed Series A Series B" in query["topic"] for query in queries)
    assert all(query["lookback_days"] == 30 for query in queries)


def test_build_sector_collection_queries_skips_yc_when_grounding_unavailable():
    from radar_run import build_sector_collection_queries

    config = {"devtools": {"display_name": "Developer Tools", "discovery_queries": []}}

    queries = build_sector_collection_queries("devtools", config, grounded_available=False, max_queries=3)

    assert [query["kind"] for query in queries] == ["conversation", "hn_show", "github_signal"]
    assert "site:ycombinator.com/companies" not in queries[0]["topic"]
    assert all(query["sources"] in {"hackernews,github", "github,hackernews"} for query in queries)
    assert all("reddit" not in query["sources"] for query in queries)
    assert all("funding" not in query["topic"].lower() for query in queries)


def test_build_sector_collection_queries_uses_stricter_oss_fallback_without_grounding():
    from radar_run import build_sector_collection_queries

    config = {"oss": {"display_name": "Open Source Radar", "discovery_queries": []}}

    queries = build_sector_collection_queries("oss", config, grounded_available=False, max_queries=3)

    assert [query["kind"] for query in queries] == ["oss_show", "oss_github", "oss_security"]
    assert all("reddit" not in query["sources"] for query in queries)


def test_collect_live_evidence_aggregates_targeted_sector_queries(monkeypatch):
    import radar_run

    calls = []

    def fake_run_query(topic, **kwargs):
        calls.append((topic, kwargs))
        return {
            "items": [
                {
                    "company_name": "Corelayer",
                    "title": "Corelayer is AI on-call for regulated data systems",
                    "url": "https://www.ycombinator.com/companies/corelayer",
                    "source": "grounding",
                }
            ],
            "clusters": [{"title": topic}],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_run_query)
    monkeypatch.setattr(radar_run, "run_trending", lambda sector, limit: {"repos": [], "warnings": []})
    monkeypatch.setattr(
        radar_run,
        "check_last30days_availability",
        lambda: {"source_capabilities": {"grounded": ["web"]}},
    )

    evidence = radar_run.collect_live_evidence(sectors=("data-infra",), github_limit=0, max_queries_per_sector=2)

    assert len(calls) == 2
    assert any("site:ycombinator.com/companies" in topic for topic, _kwargs in calls)
    assert evidence["last30days"]["data-infra"]["query_count"] == 2
    assert len(evidence["last30days"]["data-infra"]["items"]) == 1
    assert evidence["last30days"]["data-infra"]["items"][0]["company_name"] == "Corelayer"


def test_parse_sectors_arg_supports_all_and_commas():
    from radar_run import parse_sectors_arg

    assert parse_sectors_arg(None) == ("devtools", "cybersecurity", "ai-infra", "vertical-ai", "data-infra", "oss")
    assert parse_sectors_arg("all") == ("devtools", "cybersecurity", "ai-infra", "vertical-ai", "data-infra", "oss")
    assert parse_sectors_arg("ai-infra,data-infra") == ("ai-infra", "data-infra")


def test_build_partner_candidates_from_seed_filters_repo_noise():
    from radar_run import build_partner_candidates

    candidates = build_partner_candidates(
        company_seeds=[{"name": "Cascade", "sector": "AI Infra", "theme": "Agent reliability"}],
        repos=[
            {"full_name": "duanyytop/agents-radar", "description": "Daily AI ecosystem digest"},
            {"full_name": "affaan-m/agentshield", "description": "AI agent security scanner", "url": "https://github.com/affaan-m/agentshield"},
        ],
    )

    names = [candidate["name"] for candidate in candidates]
    assert "Cascade" in names
    assert "affaan-m/agentshield" in names
    assert "duanyytop/agents-radar" not in names


def test_extract_company_candidates_from_evidence_items():
    from radar_run import extract_company_candidates

    evidence = {
        "last30days": {
            "cybersecurity": {
                "items": [
                    {
                        "title": "Show HN: BeeSafe AI stops AI voice phishing for banks",
                        "url": "https://news.ycombinator.com/item?id=1",
                        "source": "hackernews",
                        "engagement": {"points": 42, "comments": 8},
                    }
                ]
            }
        },
        "github": [],
    }

    candidates = extract_company_candidates(evidence)
    assert candidates[0]["name"] == "BeeSafe AI"
    assert candidates[0]["sector"] == "Cybersecurity"
    assert candidates[0]["source"] == "https://news.ycombinator.com/item?id=1"


def test_extract_company_candidates_rejects_generic_names():
    from radar_run import extract_company_candidates

    evidence = {
        "last30days": {
            "devtools": {
                "items": [
                    {"title": "I built an open-source competitor to Delve"},
                    {"title": "Market Research: AgentClash Competitive Landscape"},
                    {"title": "📡 Tech & AI News — 05 April 2026"},
                    {"title": "Mozilla Announces \"Thunderbolt\" as an Open-Source, Enterprise AI Client"},
                    {"title": "Open Source AI Infrastructure"},
                    {"title": "Asserting American Leadership in Open Source AI"},
                    {"title": "Free open source AI Editor"},
                ]
            }
        },
        "github": [],
    }

    assert extract_company_candidates(evidence) == []


def test_extract_company_candidates_skips_oss_github_issue_noise():
    from radar_run import extract_company_candidates

    evidence = {
        "last30days": {
            "oss": {
                "items": [
                    {
                        "title": "[BOUNTY: 25 RTC] Build an MCP Server That Connects Any AI Agent to RustChain",
                        "url": "https://github.com/Scottcjn/rustchain-bounties/issues/2859",
                        "source": "github",
                    },
                    {
                        "title": "Add official MCP servers to agents",
                        "url": "https://github.com/Ven0m0/.github/pull/186",
                        "source": "github",
                    },
                ]
            }
        },
        "github": [],
    }

    assert extract_company_candidates(evidence) == []


def test_extract_company_candidates_prefers_structured_company_name_and_domain():
    from radar_run import extract_company_candidates

    evidence = {
        "last30days": {
            "ai-infra": {
                "items": [
                    {
                        "company_name": "Cascade",
                        "title": "Cascade helps enterprises adapt models to proprietary workflows",
                        "url": "https://runcascade.com",
                        "source": "web",
                        "linkedin_url": "https://www.linkedin.com/company/cascade-ai",
                        "x_url": "https://x.com/cascade_ai",
                        "founders": [
                            {
                                "name": "Asha Rao",
                                "linkedin": "https://www.linkedin.com/in/asharao",
                                "x": "https://x.com/asharao",
                            }
                        ],
                    }
                ]
            }
        },
        "github": [],
    }

    candidates = extract_company_candidates(evidence)
    assert candidates[0]["name"] == "Cascade"
    assert candidates[0]["domain"] == "runcascade.com"
    assert candidates[0]["sector"] == "AI Infra"
    assert candidates[0]["company_linkedin"] == "https://www.linkedin.com/company/cascade-ai"
    assert candidates[0]["company_x"] == "https://x.com/cascade_ai"
    assert candidates[0]["founder_profiles"][0]["linkedin"] == "https://www.linkedin.com/in/asharao"


def test_extract_company_candidates_from_yc_url_slug():
    from radar_run import extract_company_candidates

    evidence = {
        "last30days": {
            "data-infra": {
                "items": [
                    {
                        "title": "YC W26: Corelayer is AI on-call for regulated data systems",
                        "url": "https://www.ycombinator.com/companies/corelayer",
                        "source": "web",
                    }
                ]
            }
        },
        "github": [],
    }

    candidates = extract_company_candidates(evidence)
    assert candidates[0]["name"] == "Corelayer"
    assert candidates[0]["domain"] == "corelayer.com"
    assert candidates[0]["theme"] == "AI SRE"


def test_extract_company_candidates_aggregates_duplicate_mentions():
    from radar_run import extract_company_candidates

    evidence = {
        "last30days": {
            "cybersecurity": {
                "items": [
                    {
                        "title": "Show HN: BeeSafe AI stops AI voice phishing for banks",
                        "url": "https://news.ycombinator.com/item?id=1",
                        "source": "hackernews",
                        "engagement": {"points": 20},
                    },
                    {
                        "title": "BeeSafe AI raises seed for financial fraud defense",
                        "url": "https://example.com/beesafe",
                        "source": "web",
                        "engagement": {"comments": 5},
                        "linkedin_url": "https://www.linkedin.com/company/beesafe-ai",
                    },
                ]
            }
        },
        "github": [],
    }

    candidates = extract_company_candidates(evidence)
    assert len(candidates) == 1
    assert candidates[0]["name"] == "BeeSafe AI"
    assert candidates[0]["source_count"] == 2
    assert len(candidates[0]["sources"]) == 2
    assert candidates[0]["company_linkedin"] == "https://www.linkedin.com/company/beesafe-ai"


def test_score_candidate_separates_interest_and_confidence():
    from radar_run import score_candidate

    candidate = {
        "name": "AgentShield",
        "sector": "OSS / Cybersecurity",
        "theme": "AI agent security",
        "why_on_radar": "AI agent security scanner for MCP servers with strong GitHub velocity.",
        "source_count": 2,
        "github_stars_30d": 184,
        "attio_status": "no_match",
    }

    scored = score_candidate(candidate)
    assert scored["investment_interest_score"] >= 70
    assert scored["evidence_confidence_score"] >= 50
    assert scored["investment_interest"] == "High"
    assert scored["evidence_confidence"] in {"Medium", "High"}


def test_rank_candidates_orders_by_interest_then_confidence():
    from radar_run import rank_candidates

    ranked = rank_candidates([
        {"name": "Low", "investment_interest_score": 40, "evidence_confidence_score": 90},
        {"name": "High", "investment_interest_score": 80, "evidence_confidence_score": 40},
    ])
    assert [candidate["name"] for candidate in ranked] == ["High", "Low"]


def test_build_scored_preview_from_evidence_merges_attio():
    from radar_run import build_scored_preview_from_evidence

    class FakeAttio:
        def match_company(self, company):
            return {"attio_status": "no_owner", "attio_action": "assign owner"}

    evidence = {
        "last30days": {
            "cybersecurity": {
                "items": [
                    {
                        "title": "Show HN: BeeSafe AI stops AI voice phishing for banks",
                        "url": "https://news.ycombinator.com/item?id=1",
                        "source": "hackernews",
                        "engagement": {"points": 42, "comments": 8},
                    }
                ]
            }
        },
        "github": [
            {
                "full_name": "affaan-m/agentshield",
                "description": "AI agent security scanner for MCP servers",
                "url": "https://github.com/affaan-m/agentshield",
                "velocity": {"stars_last_30d": 184},
            }
        ],
    }

    candidates = build_scored_preview_from_evidence(evidence, attio_client=FakeAttio(), limit=2)
    assert len(candidates) == 2
    assert all(candidate.get("investment_interest") for candidate in candidates)
    assert candidates[0]["attio_status"] == "no_owner"


def test_build_scored_preview_excludes_low_interest_extractions():
    from radar_run import build_scored_preview_from_evidence

    evidence = {
        "last30days": {
            "devtools": {
                "items": [
                    {
                        "title": "An actress released a free open-source AI memory system",
                        "url": "https://reddit.com/noise",
                        "source": "reddit",
                    }
                ]
            }
        },
        "github": [],
    }

    assert build_scored_preview_from_evidence(evidence) == []


def test_cli_preview_can_build_from_raw_evidence(tmp_path, monkeypatch, capsys):
    import radar_run

    evidence_path = tmp_path / "raw.json"
    evidence_path.write_text(json.dumps({
        "last30days": {
            "cybersecurity": {
                "items": [
                    {
                        "title": "Show HN: BeeSafe AI stops AI voice phishing for banks",
                        "url": "https://news.ycombinator.com/item?id=1",
                        "source": "hackernews",
                    }
                ]
            }
        },
        "github": [],
    }))
    out = tmp_path / "preview.md"

    monkeypatch.setattr("sys.argv", [
        "radar_run.py",
        "preview",
        "--from-evidence",
        str(evidence_path),
        "--output",
        str(out),
    ])
    monkeypatch.setattr("sys.stdin", type("Stdin", (), {"read": lambda self: ""})())

    radar_run._cli_main()
    result = json.loads(capsys.readouterr().out)
    assert result["saved"] == str(out)
    assert "BeeSafe AI" in out.read_text()


def test_cli_preview_uses_input_json(tmp_path, monkeypatch, capsys):
    import radar_run

    payload = {
        "companies": [{"name": "Cascade", "sector": "AI Infra", "theme": "Agent reliability"}],
        "themes": ["Agent reliability"],
    }
    out = tmp_path / "preview.md"
    monkeypatch.setattr("sys.argv", ["radar_run.py", "preview", "--output", str(out)])
    monkeypatch.setattr("sys.stdin", type("Stdin", (), {"read": lambda self: json.dumps(payload)})())

    radar_run._cli_main()
    result = json.loads(capsys.readouterr().out)
    assert result["saved"] == str(out)
    assert out.exists()


def test_run_weekly_artifacts_saves_raw_and_preview(tmp_path, monkeypatch):
    import radar_run

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "title": "Show HN: BeeSafe AI stops AI voice phishing for banks",
                            "url": "https://news.ycombinator.com/item?id=1",
                            "source": "hackernews",
                        }
                    ]
                }
            },
            "github": [],
            "warnings": [],
        },
    )

    result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        max_queries_per_sector=1,
        github_limit=0,
    )

    assert result["raw_evidence"].endswith("raw-evidence.json")
    assert result["preview"].endswith("weekly-preview.md")
    assert result["companies"] == 1
    assert "BeeSafe AI" in (tmp_path / "weekly-preview.md").read_text()


def test_cli_weekly_runs_collect_and_preview(tmp_path, monkeypatch, capsys):
    import radar_run

    monkeypatch.setattr(
        radar_run,
        "run_weekly_artifacts",
        lambda **kwargs: {"raw_evidence": str(tmp_path / "raw.json"), "preview": str(tmp_path / "preview.md"), "companies": 0},
    )
    monkeypatch.setattr("sys.argv", ["radar_run.py", "weekly", "--output-dir", str(tmp_path), "--sectors", "oss"])

    radar_run._cli_main()
    result = json.loads(capsys.readouterr().out)
    assert result["preview"] == str(tmp_path / "preview.md")
