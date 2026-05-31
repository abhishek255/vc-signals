import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_build_target_queries_focuses_linkedin_and_funding_gaps():
    from targeted_manual_enrichment import build_target_queries

    queries = build_target_queries(
        {
            "name": "AgentFence",
            "domain": "agentfence.dev",
            "missing_evidence": ["company_linkedin_missing", "stage_or_funding_missing"],
        },
        queries_per_target=2,
    )

    assert len(queries) == 2
    assert "LinkedIn" in queries[0]["query"]
    assert "Crunchbase" in queries[1]["query"]
    assert '"AgentFence"' in queries[0]["query"]
    assert '"AgentFence" "agentfence.dev"' in queries[1]["query"]


def test_enrich_targets_reports_public_search_hints_without_scraping():
    from targeted_manual_enrichment import enrich_targets

    calls = []

    def fake_query_runner(topic, **kwargs):
        calls.append((topic, kwargs))
        return {
            "items": [
                {
                    "title": "AgentFence company profile",
                    "url": "https://www.linkedin.com/company/agentfence",
                    "domain": "linkedin.com",
                    "snippet": "AgentFence has 12 employees and is hiring.",
                },
                {
                    "title": "AgentFence funding profile",
                    "url": "https://www.crunchbase.com/organization/agentfence",
                    "domain": "crunchbase.com",
                    "snippet": "Seed funding profile.",
                },
            ]
        }

    report = enrich_targets(
        [
            {
                "name": "AgentFence",
                "domain": "agentfence.dev",
                "missing_evidence": ["company_linkedin_missing", "headcount_missing", "stage_or_funding_missing"],
            }
        ],
        limit=1,
        queries_per_target=2,
        timeout_seconds=10,
        query_runner=fake_query_runner,
    )

    assert report["summary"]["queries_run"] == 2
    assert calls[0][1]["sources"] == "web"
    assert calls[0][1]["lookback_days"] == 365
    hints = report["items"][0]["evidence_hints"]
    assert hints["company_linkedin_candidates"][0]["url"] == "https://www.linkedin.com/company/agentfence"
    assert hints["funding_metadata_candidates"][0]["url"] == "https://www.crunchbase.com/organization/agentfence"
    assert report["items"][0]["manual_policy"].startswith("Public web-search assist")
