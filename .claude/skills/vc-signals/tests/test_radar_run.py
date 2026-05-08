"""Tests for the weekly radar run orchestration helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_live_attio(monkeypatch):
    import radar_run

    monkeypatch.setattr(radar_run, "_attio_client_from_env", lambda: None)
    monkeypatch.setattr(radar_run, "apply_identity_resolution", lambda candidates: (candidates, []))


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
    assert is_evidence_noise({
        "source": "grounding",
        "title": '"Can Only Imagine What FCC Has To Say": Open Source Military Radar Plans Appear Online | ZeroHedge',
        "url": "https://www.zerohedge.com/military/can-only-imagine-what-fcc-has-say-open-source-military-radar-plans-appear-online",
        "container": "www.zerohedge.com",
    })
    assert not is_evidence_noise({"title": "Show HN: A security scanner for AI Agent Skills"})


def test_merge_attio_context_preserves_action_when_no_client():
    from radar_run import merge_attio_context

    companies = [{"name": "Cascade", "domain": "runcascade.com", "action": "assign owner"}]
    result = merge_attio_context(companies, attio_client=None)
    assert result[0]["attio_status"] == "unknown"
    assert result[0]["action"] == "assign owner"


def test_candidate_from_signal_preserves_likely_too_late_action():
    import radar_run
    from radar_models import Signal

    signal = Signal(
        source="grounding",
        role="company_web",
        title="AgentSecure | AI Agent Security",
        url="https://agentsecure.ai/",
        sector="cybersecurity",
        text="AgentSecure protects AI agent permissions.",
        can_create_candidate=True,
        metadata={
            "source": "grounding",
            "title": "AgentSecure | AI Agent Security",
            "url": "https://agentsecure.ai/",
            "company_name": "AgentSecure",
            "domain": "agentsecure.ai",
            "action": "likely too late",
            "why_this_may_be_noise": "Likely too late: Cisco acquired the company.",
        },
    )

    candidate = radar_run._candidate_from_signal(signal)

    assert candidate.action == "likely too late"
    assert "Likely too late" in candidate.why_this_may_be_noise


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

    companies = [{"name": "AgentShield", "sector": "OSS / Cybersecurity", "domain": "agentshield.dev", "action": "contact maintainer"}]
    result = merge_attio_context(companies, FakeAttio())
    assert result[0]["attio_status"] == "no_match"
    assert result[0]["action"] == "contact maintainer"


def test_merge_attio_context_preserves_reclassified_oss_action(monkeypatch):
    import radar_run
    from radar_run import merge_attio_context

    class FakeAttio:
        def match_company(self, company):
            return {**company, "attio_status": "no_match", "attio_action": "assign owner"}

    def fake_enrich_companies(companies, attio_client):
        return [attio_client.match_company(company) for company in companies]

    monkeypatch.setattr(radar_run, "enrich_companies", fake_enrich_companies)

    companies = [
        {
            "name": "AgentShield",
            "sector": "Cybersecurity",
            "source_lane": "OSS",
            "evidence_role": "oss_project",
            "domain": "agentshield.dev",
            "action": "contact maintainer",
        }
    ]
    result = merge_attio_context(companies, FakeAttio())

    assert result[0]["attio_status"] == "no_match"
    assert result[0]["action"] == "contact maintainer"


def test_merge_attio_context_skips_domainless_oss_repo_names():
    from radar_run import merge_attio_context

    class FakeAttio:
        def match_company(self, company):
            raise AssertionError("domainless OSS repo should not be sent to Attio")

    companies = [{"name": "php-testo/testo", "sector": "OSS", "domain": "", "action": "watch"}]
    result = merge_attio_context(companies, FakeAttio())
    assert result[0]["attio_status"] == "no_match"
    assert result[0]["action"] == "watch"


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

    queries = build_sector_collection_queries("ai-infra", config, grounded_available=True, social_available=True, max_queries=3)

    assert len(queries) == 3
    assert queries[0]["kind"] == "reddit_pain"
    assert queries[0]["candidate_eligible"] is False
    assert any("site:ycombinator.com/companies" in query["topic"] for query in queries)
    assert any("Seed Series A Series B" in query["topic"] for query in queries)
    assert all(query["lookback_days"] == 30 for query in queries)
    assert queries[0]["sources"] == "reddit"
    assert queries[1]["sources"] == "grounding,hackernews,github,youtube"


def _multi_company_discovery_config():
    return {
        "cybersecurity": {
            "display_name": "Cybersecurity",
            "discovery_queries": ["generic AI security conversation"],
            "company_discovery_queries": {
                "yc_queries": [
                    "site:ycombinator.com/companies AI security startup first",
                    "site:ycombinator.com/companies AI security startup second",
                ],
                "funding_queries": [
                    "AI security startup raises seed first",
                    "AI security startup raises seed second",
                ],
                "company_launch_queries": [
                    "AI security startup launch first",
                    "AI security startup launch second",
                ],
                "founder_queries": [
                    "AI security startup founder blog first",
                    "AI security startup founder blog second",
                ],
                "technical_blog_queries": [
                    "AI security startup technical blog first",
                    "AI security startup technical blog second",
                ],
            },
        }
    }


def test_build_sector_collection_queries_uses_company_discovery_block_when_grounded(monkeypatch):
    import radar_run
    from radar_run import build_sector_collection_queries

    monkeypatch.setattr(radar_run, "load_reddit_sources_config", lambda: {})
    config = {
        "cybersecurity": {
            "display_name": "Cybersecurity",
            "discovery_queries": ["generic AI security conversation"],
            "company_discovery_queries": {
                "company_launch_queries": ["AI security startup launch"],
                "funding_queries": ["AI security startup raises seed"],
                "yc_queries": ["site:ycombinator.com/companies AI security startup"],
                "founder_queries": ["AI security startup founder blog"],
                "technical_blog_queries": ["AI security startup technical blog"],
            },
        }
    }

    queries = build_sector_collection_queries(
        "cybersecurity",
        config,
        grounded_available=True,
        social_available=False,
        max_queries=6,
    )

    assert [query["kind"] for query in queries[:3]] == ["yc_company", "funding_company", "company_launch"]
    topics = " ".join(query["topic"] for query in queries)
    assert "site:ycombinator.com/companies AI security startup" in topics
    assert "AI security startup raises seed" in topics
    assert "AI security startup launch" in topics
    assert queries[-1]["kind"] == "conversation"
    company_queries = [query for query in queries if query["kind"] != "conversation"]
    assert all(query["sources"] == "grounding,hackernews,github" for query in company_queries)
    assert all(query["web_backend"] == "auto" for query in company_queries)


def test_build_sector_collection_queries_can_emit_second_configured_company_queries(monkeypatch):
    import radar_run
    from radar_run import build_sector_collection_queries

    monkeypatch.setattr(radar_run, "load_reddit_sources_config", lambda: {})

    queries = build_sector_collection_queries(
        "cybersecurity",
        _multi_company_discovery_config(),
        grounded_available=True,
        social_available=False,
        max_queries=11,
    )

    assert [query["kind"] for query in queries] == [
        "yc_company",
        "yc_company",
        "funding_company",
        "funding_company",
        "company_launch",
        "company_launch",
        "founder_company",
        "founder_company",
        "technical_blog_company",
        "technical_blog_company",
        "conversation",
    ]
    topics = [query["topic"] for query in queries]
    assert "site:ycombinator.com/companies AI security startup second" in topics
    assert "AI security startup raises seed second" in topics
    assert "AI security startup launch second" in topics
    assert "AI security startup founder blog second" in topics
    assert "AI security startup technical blog second" in topics


def test_build_sector_collection_queries_respects_low_company_query_budget(monkeypatch):
    import radar_run
    from radar_run import build_sector_collection_queries

    monkeypatch.setattr(radar_run, "load_reddit_sources_config", lambda: {})

    queries = build_sector_collection_queries(
        "cybersecurity",
        _multi_company_discovery_config(),
        grounded_available=True,
        social_available=False,
        max_queries=4,
    )

    assert len(queries) == 4
    assert [query["kind"] for query in queries] == [
        "yc_company",
        "yc_company",
        "funding_company",
        "funding_company",
    ]
    assert [query["topic"] for query in queries] == [
        "site:ycombinator.com/companies AI security startup first",
        "site:ycombinator.com/companies AI security startup second",
        "AI security startup raises seed first",
        "AI security startup raises seed second",
    ]


def test_build_sector_collection_queries_adds_conversation_only_when_budget_remains(monkeypatch):
    import radar_run
    from radar_run import build_sector_collection_queries

    monkeypatch.setattr(radar_run, "load_reddit_sources_config", lambda: {})

    full_company_budget = build_sector_collection_queries(
        "cybersecurity",
        _multi_company_discovery_config(),
        grounded_available=True,
        social_available=False,
        max_queries=10,
    )
    with_conversation_budget = build_sector_collection_queries(
        "cybersecurity",
        _multi_company_discovery_config(),
        grounded_available=True,
        social_available=False,
        max_queries=11,
    )

    assert len(full_company_budget) == 10
    assert all(query["kind"] != "conversation" for query in full_company_budget)
    assert with_conversation_budget[-1]["kind"] == "conversation"


def test_build_sector_collection_queries_skips_company_discovery_block_without_grounding(monkeypatch):
    import radar_run
    from radar_run import build_sector_collection_queries

    monkeypatch.setattr(radar_run, "load_reddit_sources_config", lambda: {})
    config = {
        "cybersecurity": {
            "display_name": "Cybersecurity",
            "discovery_queries": ["generic AI security conversation"],
            "company_discovery_queries": {
                "company_launch_queries": ["AI security startup launch"],
                "funding_queries": ["AI security startup raises seed"],
                "yc_queries": ["site:ycombinator.com/companies AI security startup"],
                "founder_queries": ["AI security startup founder blog"],
                "technical_blog_queries": ["AI security startup technical blog"],
            },
        }
    }

    queries = build_sector_collection_queries(
        "cybersecurity",
        config,
        grounded_available=False,
        social_available=False,
        max_queries=3,
    )

    topics = " ".join(query["topic"] for query in queries)
    assert "AI security startup raises seed" not in topics
    assert "site:ycombinator.com/companies AI security startup" not in topics
    assert all("web_backend" not in query for query in queries)


def test_build_sector_collection_queries_uses_youtube_without_grounding_when_social_available():
    from radar_run import build_sector_collection_queries

    config = {"devtools": {"display_name": "Developer Tools", "discovery_queries": []}}

    queries = build_sector_collection_queries("devtools", config, grounded_available=False, social_available=True, max_queries=3)

    assert [query["kind"] for query in queries] == ["reddit_pain", "conversation", "hn_show"]
    assert "site:ycombinator.com/companies" not in queries[0]["topic"]
    assert queries[0]["sources"] == "reddit"
    assert queries[0]["candidate_eligible"] is False
    assert all(query["sources"] in {"reddit", "hackernews,github,youtube", "github,hackernews,youtube"} for query in queries)
    assert all("funding" not in query["topic"].lower() for query in queries)


def test_build_sector_collection_queries_keeps_strict_non_social_fallback():
    from radar_run import build_sector_collection_queries

    config = {"devtools": {"display_name": "Developer Tools", "discovery_queries": []}}

    queries = build_sector_collection_queries("devtools", config, grounded_available=False, social_available=False, max_queries=3)

    assert queries[0]["kind"] == "reddit_pain"
    assert queries[0]["sources"] == "reddit"
    assert all(query["sources"] in {"reddit", "hackernews,github", "github,hackernews"} for query in queries)


def test_curated_reddit_pain_queries_do_not_create_company_rows():
    from radar_run import build_sector_collection_queries

    config = {
        "devtools": {
            "display_name": "Developer Tools",
            "discovery_queries": ["developer tooling pain"],
            "reddit_pain_queries": ["platform engineering pain points"],
        }
    }

    queries = build_sector_collection_queries("devtools", config, grounded_available=False, social_available=False, max_queries=3)

    reddit_queries = [query for query in queries if query.get("kind") == "reddit_pain"]
    assert reddit_queries
    assert all(query["sources"] == "reddit" for query in reddit_queries)
    assert all(query.get("candidate_eligible") is False for query in reddit_queries)


def test_build_sector_collection_queries_uses_youtube_for_oss_fallback():
    from radar_run import build_sector_collection_queries

    config = {"oss": {"display_name": "Open Source Radar", "discovery_queries": []}}

    queries = build_sector_collection_queries("oss", config, grounded_available=False, social_available=True, max_queries=3)

    assert [query["kind"] for query in queries] == ["reddit_pain", "oss_show", "oss_github"]
    assert queries[0]["sources"] == "reddit"
    assert all("youtube" in query["sources"] for query in queries[1:])


def test_build_sector_collection_queries_uses_social_sources_for_vertical_ai():
    from radar_run import build_sector_collection_queries

    config = {"vertical-ai": {"display_name": "Vertical AI", "discovery_queries": ["vertical AI startups gaining traction"]}}

    queries = build_sector_collection_queries("vertical-ai", config, grounded_available=False, social_available=True, max_queries=3)

    assert queries[0]["kind"] == "reddit_pain"
    assert queries[1]["sources"] == "reddit,hackernews,youtube,tiktok,instagram,threads"
    assert "workflow demos" in queries[1]["topic"]
    assert all("tiktok" not in query["sources"] for query in build_sector_collection_queries("devtools", config, social_available=True))


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
        lambda: {"source_capabilities": {"grounded": ["web"], "social": ["youtube"]}},
    )

    evidence = radar_run.collect_live_evidence(sectors=("data-infra",), github_limit=0, max_queries_per_sector=2)

    assert len(calls) == 2
    assert any("site:ycombinator.com/companies" in topic for topic, _kwargs in calls)
    assert any("youtube" in kwargs["sources"] for _topic, kwargs in calls)
    assert evidence["last30days"]["data-infra"]["query_count"] == 2
    assert len(evidence["last30days"]["data-infra"]["items"]) == 1
    assert evidence["last30days"]["data-infra"]["items"][0]["company_name"] == "Corelayer"


def test_collect_live_evidence_passes_query_timeout_and_progress(monkeypatch, capsys):
    import radar_run

    calls = []

    def fake_run_query(topic, **kwargs):
        calls.append((topic, kwargs))
        return {"items": [], "clusters": [], "warnings": []}

    monkeypatch.setattr(radar_run, "run_query", fake_run_query)
    monkeypatch.setattr(radar_run, "run_trending", lambda sector, limit: {"repos": [], "warnings": []})
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: False)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)

    radar_run.collect_live_evidence(
        sectors=("devtools",),
        github_limit=0,
        max_queries_per_sector=1,
        query_timeout_seconds=45,
        progress=True,
    )

    assert calls[0][1]["timeout_seconds"] == 45
    stderr = capsys.readouterr().err
    assert "[vc-signals] devtools: query 1/1" in stderr
    assert "[vc-signals] github: collecting trending repos" in stderr


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


def test_candidate_promotion_sets_market_sector_and_source_lane_for_oss():
    from radar_run import build_signals_from_evidence, promote_signals_to_candidates

    evidence = {
        "last30days": {},
        "github": [
            {
                "full_name": "affaan-m/agentshield",
                "description": "AI agent security scanner for MCP server permissions and tool risk.",
                "url": "https://github.com/affaan-m/agentshield",
                "topics": ["ai-agent", "security", "mcp"],
            }
        ],
    }

    signals = build_signals_from_evidence(evidence)["signals"]
    result = promote_signals_to_candidates(signals)
    candidate = result["candidates"][0]

    assert candidate.name == "affaan-m/agentshield"
    assert candidate.source_lane == "OSS"
    assert candidate.market_sector == "Cybersecurity"
    assert candidate.sector == "Cybersecurity"
    assert candidate.evidence_role == "oss_project"
    assert candidate.sector_confidence == "High"


def test_candidate_promotion_preserves_compact_hn_evidence_metadata():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="cybersecurity",
        item={
            "source": "hackernews",
            "title": "Show HN: Burrow - Runtime Security for AI Agents",
            "url": "https://news.ycombinator.com/item?id=47761957",
            "author": "saranshrana",
            "published_at": "2026-04-14",
            "container": "Hacker News",
            "query_kind": "theme_company_search",
            "query_topic": "AI agent security startups Seed Series A founder launch",
            "outbound_url": "https://burrow.security",
            "domain": "burrow.security",
            "snippet": "Large snippet should stay out of compact evidence metadata.",
        },
    )

    candidate = promote_signals_to_candidates([signal])["candidates"][0]

    assert candidate.evidence_metadata
    metadata = candidate.evidence_metadata[0]
    assert metadata["source"] == "hackernews"
    assert metadata["author"] == "saranshrana"
    assert metadata["outbound_url"] == "https://burrow.security"
    assert metadata["domain"] == "burrow.security"
    assert "snippet" not in metadata


def test_candidate_promotion_preserves_compact_github_evidence_metadata():
    from radar_run import build_signals_from_evidence, promote_signals_to_candidates

    evidence = {
        "last30days": {},
        "github": [
            {
                "full_name": "slowql/slowql",
                "description": "SQL static analyzer for performance and compliance",
                "url": "https://github.com/slowql/slowql",
                "owner_name": "slowql",
                "owner_type": "Organization",
                "topics": ["sql", "security", "compliance"],
                "homepage": "https://slowql.dev",
            }
        ],
    }

    candidate = promote_signals_to_candidates(build_signals_from_evidence(evidence)["signals"])["candidates"][0]
    metadata = candidate.evidence_metadata[0]

    assert metadata["owner_name"] == "slowql"
    assert metadata["owner_type"] == "Organization"
    assert metadata["topics"] == ["sql", "security", "compliance"]
    assert metadata["description"] == "SQL static analyzer for performance and compliance"
    assert metadata["homepage"] == "https://slowql.dev"


def test_classified_domainless_oss_candidate_is_not_sent_to_attio(monkeypatch):
    import radar_run
    from radar_run import build_signals_from_evidence, merge_attio_context, promote_signals_to_candidates

    class FakeAttio:
        def match_company(self, company):
            raise AssertionError("classified domainless OSS repo should not be sent to Attio")

    def fake_enrich_companies(companies, attio_client):
        return [attio_client.match_company(company) for company in companies]

    monkeypatch.setattr(radar_run, "enrich_companies", fake_enrich_companies)

    evidence = {
        "last30days": {},
        "github": [
            {
                "full_name": "affaan-m/agentshield",
                "description": "AI agent security scanner for MCP server permissions and tool risk.",
                "url": "https://github.com/affaan-m/agentshield",
                "topics": ["ai-agent", "security", "mcp"],
            }
        ],
    }
    signals = build_signals_from_evidence(evidence)["signals"]
    candidate = promote_signals_to_candidates(signals)["candidates"][0]

    assert candidate.sector == "Cybersecurity"
    assert candidate.source_lane == "OSS"
    assert candidate.domain == ""

    result = merge_attio_context([candidate.to_dict()], FakeAttio())
    assert result[0]["attio_status"] == "unknown"
    assert result[0]["action"] == candidate.action


def test_social_product_demo_can_create_candidate_with_source_lane():
    from radar_run import build_signals_from_evidence, promote_signals_to_candidates

    evidence = {
        "last30days": {
            "vertical-ai": {
                "items": [
                    {
                        "source": "tiktok",
                        "title": "DentalDesk AI demo automates front desk intake for dental clinics",
                        "url": "https://www.tiktok.com/@dentaldesk/video/1",
                        "company_name": "DentalDesk AI",
                        "website": "https://dentaldesk.ai",
                    }
                ]
            }
        },
        "github": [],
    }

    signals = build_signals_from_evidence(evidence)["signals"]
    result = promote_signals_to_candidates(signals)
    candidate = result["candidates"][0]

    assert candidate.name == "DentalDesk AI"
    assert candidate.source_lane == "TikTok"
    assert candidate.evidence_role == "product_demo"
    assert candidate.market_sector == "Vertical AI"


def test_build_signals_from_evidence_preserves_sector_coverage():
    from radar_run import build_signals_from_evidence

    evidence = {
        "last30days": {
            "data-infra": {
                "items": [
                    {
                        "source": "reddit",
                        "title": "What are people using for data lineage now?",
                        "url": "https://reddit.com/r/dataengineering/example",
                    }
                ]
            },
            "oss": {
                "items": [
                    {
                        "source": "hackernews",
                        "title": "Show HN: MenteDB, an open-source memory database for AI agents",
                        "url": "https://news.ycombinator.com/item?id=2",
                    }
                ]
            },
        },
        "github": [],
    }

    result = build_signals_from_evidence(evidence)
    assert len(result["signals"]) == 2
    assert result["coverage"]["data-infra"].raw_signals == 1
    assert result["coverage"]["oss"].raw_signals == 1


def test_candidate_promotion_ignores_reddit_only_signal():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signals = [
        classify_source_item(
            sector="data-infra",
            item={"source": "reddit", "title": "What data quality tools are people using?", "url": "https://reddit.com/x"},
        )
    ]

    result = promote_signals_to_candidates(signals)
    assert result["candidates"] == []
    assert result["rejected"][0].reason == "source_not_candidate_eligible"


def test_candidate_promotion_allows_hn_launch():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signals = [
        classify_source_item(
            sector="cybersecurity",
            item={"source": "hackernews", "title": "Show HN: BeeSafe AI stops voice phishing for banks", "url": "https://news.ycombinator.com/item?id=1"},
        )
    ]

    result = promote_signals_to_candidates(signals)
    assert result["candidates"][0].name == "BeeSafe AI"


def test_candidate_promotion_keeps_full_github_repo_name():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signals = [
        classify_source_item(
            sector="oss",
            item={
                "source": "github",
                "title": "JoasASantos/NeuroSploit",
                "url": "https://github.com/JoasASantos/NeuroSploit",
                "description": "AI-powered penetration testing framework",
            },
        )
    ]

    result = promote_signals_to_candidates(signals)
    assert result["candidates"][0].name == "JoasASantos/NeuroSploit"


def test_candidate_promotion_adds_oss_action_reason():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signals = [
        classify_source_item(
            sector="oss",
            item={
                "source": "github",
                "title": "affaan-m/agentshield",
                "url": "https://github.com/affaan-m/agentshield",
                "description": "AI agent security scanner for MCP servers",
                "stars": 1200,
                "velocity": {"stars_last_30d": 187},
                "license": "Apache-2.0",
            },
        )
    ]

    candidate = promote_signals_to_candidates(signals)["candidates"][0]
    assert candidate.action == "track company formation"
    assert candidate.oss_company_formation_score >= 70
    assert candidate.oss_action_reason


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


def test_candidate_from_signal_applies_evidence_backed_source_enrichment():
    from radar_run import promote_signals_to_candidates
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="cybersecurity",
        item={
            "source": "web",
            "company_name": "BeeSafe AI",
            "title": "BeeSafe AI stops AI voice phishing for banks",
            "url": "https://beesafe.ai",
            "stage": "Seed",
            "raised": "$4M",
            "headcount": "12",
            "founders": ["Asha Rao"],
            "evidence": {
                "stage": "https://beesafe.ai/about",
                "raised": "https://beesafe.ai/blog/seed",
                "founders": "https://beesafe.ai/about",
            },
        },
    )

    candidate = promote_signals_to_candidates([signal])["candidates"][0]
    assert candidate.stage == "Seed"
    assert candidate.raised == "$4M"
    assert candidate.headcount == ""
    assert candidate.founders == ["Asha Rao"]
    assert "headcount" not in candidate.enrichment_evidence


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
    assert any(candidate["name"] == "BeeSafe AI" and candidate["attio_status"] == "no_owner" for candidate in candidates)
    assert any(candidate["name"] == "affaan-m/agentshield" and candidate["attio_status"] == "no_match" for candidate in candidates)


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
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    saved_history = {}
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: saved_history.update(history))
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: False)
    monkeypatch.setattr(radar_run, "run_query", None)

    result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        max_queries_per_sector=1,
        github_limit=0,
    )

    assert result["raw_evidence"].endswith("raw-evidence.json")
    assert result["signals"].endswith("signals.json")
    assert result["candidates"].endswith("candidates.json")
    assert result["metadata_loss_report"].endswith("metadata-loss-report.json")
    assert result["preview"].endswith("weekly-preview.md")
    assert result["companies"] == 1
    assert "BeeSafe AI" in (tmp_path / "weekly-preview.md").read_text()
    saved = json.loads((tmp_path / "candidates.json").read_text())
    assert saved[0]["stable_key"]
    assert saved[0]["weekly_tag"] == "NEW"
    assert (tmp_path / "metadata-loss-report.json").exists()
    assert saved_history


def test_run_weekly_artifacts_writes_weekly_focus_without_replacing_preview(tmp_path, monkeypatch):
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
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: False)
    monkeypatch.setattr(radar_run, "run_query", None)

    result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        max_queries_per_sector=1,
        github_limit=0,
    )

    assert result["weekly_focus_json"].endswith("weekly-focus.json")
    assert result["weekly_focus"].endswith("weekly-focus.md")
    assert result["feedback"].endswith("feedback.json")
    assert (tmp_path / "weekly-focus.json").exists()
    assert (tmp_path / "weekly-focus.md").exists()
    assert (tmp_path / "feedback.json").exists()
    assert "# Marathon Signal Radar: Weekly Focus" in (tmp_path / "weekly-focus.md").read_text()
    assert "# VC Signals Weekly Radar" in (tmp_path / "weekly-preview.md").read_text()


def test_run_weekly_artifacts_writes_identity_resolution_artifact(tmp_path, monkeypatch):
    import radar_run
    from radar_models import IdentityResolution

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "title": "Show HN: Burrow - Runtime Security for AI Agents",
                            "url": "https://news.ycombinator.com/item?id=47761957",
                            "source": "hackernews",
                        }
                    ]
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: False)
    monkeypatch.setattr(radar_run, "run_query", None)

    def fake_apply_identity_resolution(candidates):
        return candidates, [
            IdentityResolution(
                candidate_key="hn:47761957",
                original_name="Burrow",
                identity_type="launch_style_needs_identity",
                recommended_identity_action="Research deeper",
            )
        ]

    monkeypatch.setattr(radar_run, "apply_identity_resolution", fake_apply_identity_resolution)

    result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        max_queries_per_sector=1,
        github_limit=0,
    )

    identity_path = Path(result["identity_resolution_json"])
    assert identity_path.exists()
    payload = json.loads(identity_path.read_text())
    assert payload[0]["original_name"] == "Burrow"
    assert payload[0]["identity_type"] == "launch_style_needs_identity"
    assert Path(result["weekly_focus_json"]).exists()
    assert Path(result["weekly_focus"]).exists()


def test_identity_resolution_runs_before_attio_matching(monkeypatch):
    import radar_run

    calls = []

    def fake_apply_identity_resolution(candidates):
        for candidate in candidates:
            candidate.domain = "burrow.security"
            candidate.attio_safe_to_match = True
            candidate.attio_match_keys = ["burrow.security", "Burrow"]
        return candidates, []

    def fake_apply_attio(candidates, attio_client=None):
        calls.append([candidate.domain for candidate in candidates])
        return candidates

    monkeypatch.setattr(radar_run, "apply_identity_resolution", fake_apply_identity_resolution)
    monkeypatch.setattr(radar_run, "_apply_attio_to_candidates", fake_apply_attio)

    candidate = radar_run.Candidate(
        name="Burrow",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=47761957",
        candidate_type="company_web",
    )

    radar_run.prepare_candidates_for_weekly_focus([candidate], attio_client=None)

    assert calls == [["burrow.security"]]


def test_run_weekly_artifacts_saves_signals_candidates_and_sector_coverage(tmp_path, monkeypatch):
    import radar_run

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "data-infra": {
                    "items": [
                        {"source": "reddit", "title": "What lineage tools are people using?", "url": "https://reddit.com/x"}
                    ]
                },
                "oss": {
                    "items": [
                        {"source": "hackernews", "title": "Show HN: MenteDB, memory database for AI agents", "url": "https://news.ycombinator.com/item?id=1"}
                    ]
                },
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: False)
    monkeypatch.setattr(radar_run, "run_query", None)

    result = radar_run.run_weekly_artifacts(output_dir=tmp_path, sectors=("data-infra", "oss"), github_limit=0)
    assert (tmp_path / "signals.json").exists()
    assert (tmp_path / "candidates.json").exists()
    assert result["signals"].endswith("signals.json")
    preview = (tmp_path / "weekly-preview.md").read_text()
    assert "Sector Coverage" in preview
    assert "data-infra: no qualified candidates" in preview


def test_run_weekly_artifacts_writes_theme_and_sector_intelligence(tmp_path, monkeypatch):
    import radar_run

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "source": "reddit",
                            "title": "How are teams controlling AI agent permissions?",
                            "url": "https://reddit.com/1",
                        },
                        {
                            "source": "reddit",
                            "title": "MCP tools are creating security review headaches",
                            "url": "https://reddit.com/2",
                        },
                    ],
                    "errors": [],
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: False)
    monkeypatch.setattr(radar_run, "run_query", None)

    radar_run.run_weekly_artifacts(output_dir=tmp_path, sectors=("cybersecurity",), github_limit=0)

    assert (tmp_path / "theme-signals.json").exists()
    assert (tmp_path / "sector-intelligence.json").exists()
    themes = json.loads((tmp_path / "theme-signals.json").read_text())
    sectors = json.loads((tmp_path / "sector-intelligence.json").read_text())
    assert themes[0]["market_sector"] == "Cybersecurity"
    assert themes[0]["theme"] == "AI agent security"
    assert sectors[0]["status"] == "Pain signal, no company yet"


def test_run_weekly_artifacts_promotes_theme_company_discovery(tmp_path, monkeypatch):
    import radar_run

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "source": "reddit",
                            "title": "How are teams controlling AI agent permissions?",
                            "url": "https://reddit.com/1",
                            "snippet": "Teams need better controls for MCP permissions and autonomous agent security.",
                        },
                        {
                            "source": "hackernews",
                            "title": "MCP tools are creating security review headaches",
                            "url": "https://news.ycombinator.com/item?id=1",
                            "snippet": "MCP tool access creates new security review headaches.",
                        },
                    ],
                    "errors": [],
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)

    def fake_run_query(topic, **kwargs):
        if "AI agent security" not in topic:
            return {"items": []}
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev",
                    "snippet": "AgentFence helps teams control MCP tool permissions for AI agents.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                    "company_linkedin": "https://www.linkedin.com/company/agentfence",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_run_query)

    result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        github_limit=0,
        candidate_limit=50,
    )

    assert result["company_discovery"].endswith("company-discovery.json")
    discovery = json.loads((tmp_path / "company-discovery.json").read_text())
    assert discovery["items"][0]["company_name"] == "AgentFence"

    candidates = json.loads((tmp_path / "candidates.json").read_text())
    assert candidates[0]["name"] == "AgentFence"
    assert candidates[0]["domain"] == "agentfence.dev"
    assert candidates[0]["source_lane"] == "Grounded web"

    preview = (tmp_path / "weekly-preview.md").read_text()
    assert "## Company Discovery From Themes" in preview
    assert "AgentFence" in preview


def test_run_weekly_artifacts_writes_runtime_ledger_and_coverage_report(tmp_path, monkeypatch):
    import radar_run
    from radar_company_discovery import DiscoveryRunBudget
    from radar_models import ThemeSignal

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "source": "reddit",
                            "title": "How are teams controlling AI agent permissions?",
                            "url": "https://reddit.com/1",
                            "snippet": "Teams need better controls for MCP permissions and autonomous agent security.",
                        }
                    ],
                    "errors": [],
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [
            ThemeSignal(
                market_sector="Cybersecurity",
                theme="AI agent security",
                evidence_count=3,
                suggested_search="AI agent security startups Seed Series A founder launch",
                confidence="Medium",
            )
        ],
    )
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(radar_run, "run_query", lambda topic, **kwargs: {"items": [], "warnings": []})

    result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        github_limit=0,
        candidate_limit=10,
        discovery_budget=DiscoveryRunBudget.for_mode(
            "smoke",
            max_company_discovery_queries=1,
            max_maturity_queries=0,
            max_article_fetches=0,
        ),
    )

    ledger = json.loads((tmp_path / "runtime-ledger.json").read_text())
    coverage = json.loads((tmp_path / "coverage-report.json").read_text())
    discovery = json.loads((tmp_path / "company-discovery.json").read_text())

    assert result["runtime_ledger"].endswith("runtime-ledger.json")
    assert result["coverage_report"].endswith("coverage-report.json")
    assert ledger["completed_queries"] == 1
    assert discovery["summary"]["partial"] is True
    assert coverage["recommended_deep_dive"]


def test_run_weekly_artifacts_surfaces_category_context_leads_in_weekly_focus(tmp_path, monkeypatch):
    import radar_run
    from radar_models import ThemeSignal

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "source": "reddit",
                            "title": "How are teams controlling AI agent permissions?",
                            "url": "https://reddit.com/1",
                            "snippet": "Teams need better controls for MCP permissions and autonomous agent security.",
                        }
                    ],
                    "errors": [],
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [
            ThemeSignal(
                market_sector="Cybersecurity",
                theme="AI agent security",
                evidence_count=3,
                suggested_search="AI agent security startups Seed Series A founder launch",
                confidence="Medium",
            )
        ],
    )
    monkeypatch.setattr(
        radar_run,
        "collect_company_discovery",
        lambda *args, **kwargs: {
            "queries": [],
            "items": [],
            "accepted_leads": [
                {
                    "name": "7AI",
                    "movement": "AI agent security",
                    "market_sector": "Cybersecurity",
                    "source_url": "https://7ai.com/",
                    "source": "grounding",
                    "domain": "7ai.com",
                    "candidate_type": "verified_company",
                    "verification_status": "accepted",
                    "verification_basis": ["official_homepage_domain"],
                    "movement_assignment_basis": ["strong_movement_phrase:ai agent"],
                    "source_type": "official_company_page",
                    "why_on_radar": "AI SOC agents and agentic security platform.",
                    "why_this_may_be_noise": "Likely too late; use as market anchor.",
                    "maturity_status": "likely_too_late",
                    "maturity_basis": ["large_round_or_valuation"],
                    "maturity_evidence_urls": ["https://example.com/7ai-funding"],
                    "category_anchor": True,
                    "consensus_risk_reason": "Large funding/valuation signal.",
                    "lead_route": "category_context",
                }
            ],
            "rejected_leads": [],
            "warnings": [],
            "errors": [],
            "summary": {"accepted": 1, "rejected": 0, "queries_run": 0},
            "runtime_ledger": {},
            "coverage_report": {},
        },
    )

    radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        github_limit=0,
        candidate_limit=10,
    )

    focus = json.loads((tmp_path / "weekly-focus.json").read_text())
    category_context = focus["appendix"]["category_context"]
    assert category_context[0]["name"] == "7AI"
    assert category_context[0]["recommended_action"] == "Monitor only"
    assert "7AI" not in [row["name"] for row in focus["partner_focus"]]
    assert "7AI" not in [row["name"] for row in focus["new_to_marathon"]]
    assert "7AI" in (tmp_path / "weekly-focus.md").read_text()


def test_run_weekly_artifacts_feeds_verified_discovery_into_identity_resolution(tmp_path, monkeypatch):
    import json
    import radar_run
    from identity_resolution import apply_identity_resolution as real_identity_resolution
    from radar_models import ThemeSignal

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "source": "reddit",
                            "title": "How are teams controlling AI agent permissions?",
                            "url": "https://reddit.com/1",
                            "snippet": "Teams need better controls for MCP permissions and autonomous agent security.",
                        }
                    ],
                    "errors": [],
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "apply_identity_resolution", real_identity_resolution)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [
            ThemeSignal(
                market_sector="Cybersecurity",
                theme="AI agent security",
                evidence_count=2,
                evidence_summary="Teams are asking how to control MCP tool permissions.",
                why_it_matters="Agent tool access creates a new security surface.",
                why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
                suggested_search="AI agent security startups Seed Series A founder launch",
                confidence="Medium",
            )
        ],
    )

    def fake_run_query(topic, **kwargs):
        assert kwargs["sources"] == "grounding"
        assert "AI agent security" in topic
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev",
                    "snippet": "AgentFence helps security teams control AI agent tool permissions.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_run_query)

    result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        github_limit=0,
        candidate_limit=50,
    )

    discovery = json.loads((tmp_path / "company-discovery.json").read_text())
    assert discovery["summary"]["accepted"] == 1
    assert discovery["accepted_leads"][0]["name"] == "AgentFence"

    candidates = json.loads((tmp_path / "candidates.json").read_text())
    agentfence = next(candidate for candidate in candidates if candidate["name"] == "AgentFence")
    assert agentfence["domain"] == "agentfence.dev"
    assert agentfence["identity_type"] == "verified_company"
    assert agentfence["attio_safe_to_match"] is True
    assert result["weekly_focus"].endswith("weekly-focus.md")


def test_run_weekly_artifacts_does_not_promote_vibe_discovery_result(tmp_path, monkeypatch):
    import json
    import radar_run
    from radar_models import ThemeSignal

    monkeypatch.setattr(
        radar_run,
        "collect_live_evidence",
        lambda **kwargs: {
            "last30days": {
                "cybersecurity": {
                    "items": [
                        {
                            "source": "reddit",
                            "title": "How are teams controlling AI agent permissions?",
                            "url": "https://reddit.com/1",
                            "snippet": "Teams need better controls for MCP permissions and autonomous agent security.",
                        }
                    ],
                    "errors": [],
                }
            },
            "github": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: True)
    monkeypatch.setattr(radar_run, "_social_search_available", lambda: False)
    monkeypatch.setattr(
        radar_run,
        "build_theme_signals",
        lambda signals, sectors: [
            ThemeSignal(
                market_sector="Cybersecurity",
                theme="AI agent security",
                evidence_count=2,
                evidence_summary="Teams are asking how to control MCP tool permissions.",
                why_it_matters="Agent tool access creates a new security surface.",
                why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
                suggested_search="AI agent security startups Seed Series A founder launch",
                confidence="Medium",
            )
        ],
    )

    def fake_run_query(topic, **kwargs):
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Generic devtools company launches",
                    "url": "https://generic.dev",
                    "snippet": "A generic developer productivity platform.",
                    "company_name": "GenericDev",
                    "domain": "generic.dev",
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(radar_run, "run_query", fake_run_query)

    radar_run.run_weekly_artifacts(
        output_dir=tmp_path,
        sectors=("cybersecurity",),
        github_limit=0,
        candidate_limit=50,
    )

    discovery = json.loads((tmp_path / "company-discovery.json").read_text())
    assert discovery["summary"]["accepted"] == 0
    assert discovery["summary"]["rejected"] >= 1

    candidates = json.loads((tmp_path / "candidates.json").read_text())
    assert all(candidate["name"] != "GenericDev" for candidate in candidates)


def test_promote_signals_merges_discovery_lead_with_existing_candidate_domain():
    from radar_models import Signal
    from radar_run import promote_signals_to_candidates

    original = Signal(
        source="grounding",
        role="launch",
        title="AgentFence launches AI agent permission firewall",
        url="https://agentfence.dev/blog/agent-security",
        sector="cybersecurity",
        theme="AI agent security",
        text="AgentFence helps security teams control AI agent permissions.",
        can_create_candidate=True,
        evidence_strength=70,
        metadata={
            "company_name": "AgentFence",
            "domain": "agentfence.dev",
            "source_lane": "Grounded web",
        },
    )
    discovery = Signal(
        source="grounding",
        role="launch",
        title="AgentFence company page",
        url="https://agentfence.dev",
        sector="cybersecurity",
        theme="AI agent security",
        text="AgentFence helps teams control MCP tool permissions for AI agents.",
        can_create_candidate=True,
        evidence_strength=75,
        metadata={
            "company_name": "AgentFence",
            "domain": "agentfence.dev",
            "source_lane": "Grounded web",
            "discovery_lane": "controlled_company_discovery",
            "discovery_verification_status": "accepted",
        },
    )

    result = promote_signals_to_candidates([original, discovery])

    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate.name == "AgentFence"
    assert candidate.domain == "agentfence.dev"
    assert sorted(candidate.sources) == [
        "https://agentfence.dev",
        "https://agentfence.dev/blog/agent-security",
    ]


def test_company_discovery_keeps_structured_company_page_with_short_title():
    from radar_run import build_signals_from_evidence

    evidence = {
        "last30days": {},
        "github": [],
        "company_discovery": {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence",
                    "url": "https://agentfence.dev",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                    "market_sector": "Cybersecurity",
                    "query_theme": "AI agent security",
                }
            ],
        },
    }

    result = build_signals_from_evidence(evidence)

    assert len(result["signals"]) == 1
    assert result["signals"][0].title == "AgentFence"
    assert result["signals"][0].can_create_candidate is True


def test_run_weekly_artifacts_writes_synthesis_only_when_enabled(tmp_path, monkeypatch):
    import sys
    import radar_run
    from radar_models import SynthesisResult

    sys.modules.pop("radar_synthesis", None)
    evidence = {
        "last30days": {
            "cybersecurity": {
                "items": [
                    {
                        "source": "hackernews",
                        "title": "Show HN: BeeSafe AI stops voice phishing for banks",
                        "url": "https://news.ycombinator.com/item?id=1",
                    }
                ],
                "errors": [],
            }
        },
        "github": [],
        "warnings": [],
    }
    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: evidence)
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)
    monkeypatch.setattr(radar_run, "_grounded_search_available", lambda: False)

    default_result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path / "default",
        sectors=("cybersecurity",),
        github_limit=0,
    )

    assert "synthesis" not in default_result
    assert not (tmp_path / "default" / "synthesis.json").exists()
    assert "radar_synthesis" not in sys.modules
    assert "LLM Synthesis Notes" not in (tmp_path / "default" / "weekly-preview.md").read_text()

    monkeypatch.setattr(
        radar_run,
        "run_synthesis",
        lambda **kwargs: SynthesisResult(
            enabled=True,
            model="fake-synthesis",
            partner_notes=["Synthesis enabled for test."],
        ),
    )

    enabled_result = radar_run.run_weekly_artifacts(
        output_dir=tmp_path / "enabled",
        sectors=("cybersecurity",),
        github_limit=0,
        with_synthesis=True,
    )

    synthesis_path = tmp_path / "enabled" / "synthesis.json"
    assert synthesis_path.exists()
    assert json.loads(synthesis_path.read_text())["enabled"] is True
    assert enabled_result["synthesis"] == str(synthesis_path)
    assert "LLM Synthesis Notes" in (tmp_path / "enabled" / "weekly-preview.md").read_text()


def test_weekly_radar_keeps_up_to_50_not_just_top_15(tmp_path, monkeypatch):
    import json
    import radar_run
    from radar_models import Candidate

    candidates = [
        Candidate(
            name=f"Company {i}",
            sector="AI Infra",
            theme="Agent runtime",
            source=f"https://example.com/{i}",
            candidate_type="company_web",
            tier="Watchlist",
            investment_interest="Medium",
            evidence_confidence="Medium",
            investment_interest_score=60 - (i % 10),
            evidence_confidence_score=50,
        )
        for i in range(60)
    ]

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "build_signals_from_evidence", lambda evidence: {"signals": [], "coverage": {}})
    monkeypatch.setattr(radar_run, "promote_signals_to_candidates", lambda signals: {"candidates": candidates, "rejected": []})
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)

    radar_run.run_weekly_artifacts(output_dir=tmp_path, candidate_limit=50)
    saved = json.loads((tmp_path / "candidates.json").read_text())
    assert len(saved) == 50


def test_weekly_radar_passes_partner_review_selection_to_renderer(tmp_path, monkeypatch):
    import radar_run
    from radar_models import Candidate

    candidates = [
        Candidate(
            name=f"Company {i}",
            sector="AI Infra",
            market_sector="AI Infra",
            source_lane="Grounded web",
            theme="Agent runtime",
            source=f"https://example.com/{i}",
            candidate_type="company_web",
            tier="Watchlist",
            investment_interest="Medium",
            evidence_confidence="Medium",
            investment_interest_score=50,
            evidence_confidence_score=50,
        )
        for i in range(12)
    ]
    selected = candidates[:10]
    rendered = {}

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "build_signals_from_evidence", lambda evidence: {"signals": [], "coverage": {}})
    monkeypatch.setattr(radar_run, "promote_signals_to_candidates", lambda signals: {"candidates": candidates, "rejected": []})
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda rows: rows)
    monkeypatch.setattr(radar_run, "select_partner_review", lambda rows: selected)

    def fake_render(candidates, coverage, rejected, **kwargs):
        rendered.update(kwargs)
        return "# preview\n"

    monkeypatch.setattr(radar_run, "render_weekly_brief", fake_render)

    radar_run.run_weekly_artifacts(output_dir=tmp_path, candidate_limit=50)

    assert rendered["partner_review"] == selected


def test_weekly_radar_does_not_pad_to_50(tmp_path, monkeypatch):
    import json
    import radar_run
    from radar_models import Candidate

    candidates = [
        Candidate(
            name=f"Company {i}",
            sector="AI Infra",
            theme="Agent runtime",
            source=f"https://example.com/{i}",
            candidate_type="company_web",
            tier="Watchlist",
            investment_interest="Medium",
            evidence_confidence="Medium",
            investment_interest_score=50,
            evidence_confidence_score=50,
        )
        for i in range(7)
    ]

    monkeypatch.setattr(radar_run, "collect_live_evidence", lambda **kwargs: {"last30days": {}, "github": [], "warnings": []})
    monkeypatch.setattr(radar_run, "build_signals_from_evidence", lambda evidence: {"signals": [], "coverage": {}})
    monkeypatch.setattr(radar_run, "promote_signals_to_candidates", lambda signals: {"candidates": candidates, "rejected": []})
    monkeypatch.setattr(radar_run, "load_candidate_history", lambda: {})
    monkeypatch.setattr(radar_run, "save_candidate_history", lambda history: None)
    monkeypatch.setattr(radar_run, "apply_candidate_enrichment", lambda candidates: candidates)

    radar_run.run_weekly_artifacts(output_dir=tmp_path, candidate_limit=50)
    saved = json.loads((tmp_path / "candidates.json").read_text())
    assert len(saved) == 7


def test_cli_weekly_runs_collect_and_preview(tmp_path, monkeypatch, capsys):
    import radar_run

    seen = {}

    def fake_run_weekly_artifacts(**kwargs):
        seen.update(kwargs)
        return {"raw_evidence": str(tmp_path / "raw.json"), "preview": str(tmp_path / "preview.md"), "companies": 0}

    monkeypatch.setattr(
        radar_run,
        "run_weekly_artifacts",
        fake_run_weekly_artifacts,
    )
    monkeypatch.setattr("sys.argv", ["radar_run.py", "weekly", "--output-dir", str(tmp_path), "--sectors", "oss"])

    radar_run._cli_main()
    result = json.loads(capsys.readouterr().out)
    assert result["preview"] == str(tmp_path / "preview.md")
    assert seen["max_queries_per_sector"] == 3
    assert seen["query_timeout_seconds"] is None


def test_cli_weekly_first_pass_uses_fast_trial_defaults(tmp_path, monkeypatch):
    import radar_run

    seen = {}

    def fake_run_weekly_artifacts(**kwargs):
        seen.update(kwargs)
        return {"raw_evidence": str(tmp_path / "raw.json"), "preview": str(tmp_path / "preview.md"), "companies": 0}

    monkeypatch.setattr(radar_run, "run_weekly_artifacts", fake_run_weekly_artifacts)
    monkeypatch.setattr("sys.argv", ["radar_run.py", "weekly", "--output-dir", str(tmp_path), "--firstPass"])

    radar_run._cli_main()

    assert seen["max_queries_per_sector"] == 1
    assert seen["query_timeout_seconds"] == 45


def test_cli_weekly_first_pass_respects_explicit_quality_overrides(tmp_path, monkeypatch):
    import radar_run

    seen = {}

    def fake_run_weekly_artifacts(**kwargs):
        seen.update(kwargs)
        return {"raw_evidence": str(tmp_path / "raw.json"), "preview": str(tmp_path / "preview.md"), "companies": 0}

    monkeypatch.setattr(radar_run, "run_weekly_artifacts", fake_run_weekly_artifacts)
    monkeypatch.setattr(
        "sys.argv",
        [
            "radar_run.py",
            "weekly",
            "--output-dir",
            str(tmp_path),
            "--first-pass",
            "--max-queries-per-sector",
            "2",
            "--query-timeout",
            "90",
        ],
    )

    radar_run._cli_main()

    assert seen["max_queries_per_sector"] == 2
    assert seen["query_timeout_seconds"] == 90


def test_cli_weekly_parses_with_synthesis_flag(tmp_path, monkeypatch):
    import radar_run

    seen = {}

    def fake_run_weekly_artifacts(**kwargs):
        seen.update(kwargs)
        return {"raw_evidence": str(tmp_path / "raw.json"), "preview": str(tmp_path / "preview.md"), "companies": 0}

    monkeypatch.setattr(radar_run, "run_weekly_artifacts", fake_run_weekly_artifacts)
    monkeypatch.setattr("sys.argv", ["radar_run.py", "weekly", "--output-dir", str(tmp_path), "--with-synthesis"])

    radar_run._cli_main()

    assert seen["with_synthesis"] is True


def test_cli_workbench_writes_agent_native_artifacts(tmp_path, monkeypatch, capsys):
    import radar_run

    seen = {}

    def fake_write_workbench_artifacts(**kwargs):
        seen.update(kwargs)
        return {
            "package": str(tmp_path / "research-workbench-input.json"),
            "prompt": str(tmp_path / "research-workbench-prompt.md"),
        }

    monkeypatch.setattr(radar_run, "write_workbench_artifacts", fake_write_workbench_artifacts)
    monkeypatch.setattr(
        "sys.argv",
        ["radar_run.py", "workbench", "--from-run", str(tmp_path / "run"), "--output-dir", str(tmp_path / "out")],
    )

    radar_run._cli_main()

    result = json.loads(capsys.readouterr().out)
    assert result["prompt"].endswith("research-workbench-prompt.md")
    assert seen["run_dir"] == tmp_path / "run"
    assert seen["output_dir"] == tmp_path / "out"
