from __future__ import annotations

import json


def _candidate(**overrides):
    from radar_models import Candidate

    data = {
        "name": "Copperhelm",
        "sector": "Cybersecurity",
        "market_sector": "Cybersecurity",
        "theme": "Agentic cloud security",
        "source": "https://copperhelm.com/",
        "sources": ["https://copperhelm.com/"],
        "candidate_type": "company_web",
        "domain": "copperhelm.com",
        "identity_type": "verified_company",
        "attio_status": "no_match",
        "attio_safe_to_match": True,
        "attio_match_keys": ["domain:copperhelm.com"],
        "maturity_status": "seed_to_series_b",
        "maturity_basis": ["seed_or_pre_seed"],
        "maturity_evidence_urls": ["https://example.com/copperhelm-seed"],
        "lead_route": "sourcing_candidate",
        "why_on_radar": "Copperhelm emerged from stealth with $7M seed funding.",
        "evidence_confidence_score": 70,
    }
    data.update(overrides)
    return Candidate(**data)


def test_owner_evidence_checks_official_pages_and_extracts_founder_team(tmp_path):
    from owner_evidence import enrich_owner_evidence

    fetched_urls = []

    def fake_fetcher(url):
        fetched_urls.append(url)
        if url.endswith("/team"):
            return "<html><title>Team</title><body>Copperhelm was founded by Maya Rao and Luis Chen to secure agentic cloud workloads.</body></html>"
        return "<html><body>Copperhelm is an agentic cloud security company.</body></html>"

    enriched, report = enrich_owner_evidence(
        [_candidate(founder_profiles=[])],
        query_runner=None,
        page_fetcher=fake_fetcher,
        cache_dir=tmp_path,
    )

    candidate = enriched[0]
    item = report["items"][0]
    assert "https://copperhelm.com/team" in fetched_urls
    assert candidate.founder_team_evidence == ["https://copperhelm.com/team"]
    assert candidate.founder_profiles == [
        {"name": "Maya Rao", "role": "founder", "source": "https://copperhelm.com/team"},
        {"name": "Luis Chen", "role": "founder", "source": "https://copperhelm.com/team"},
    ]
    assert "founder_team_evidence" in candidate.owner_readiness_basis
    assert item["official_site_pages_checked"]
    assert item["founder_team_evidence"] == ["https://copperhelm.com/team"]
    assert item["founder_profiles"] == candidate.founder_profiles


def test_owner_evidence_does_not_count_generic_team_word_as_founder(tmp_path):
    from owner_evidence import enrich_owner_evidence

    def fake_fetcher(url):
        if url.endswith("/customers"):
            return "<html><body>Our customer success team supports enterprise security teams and design partners.</body></html>"
        if url.endswith("/pricing"):
            return "<html><body>Team pricing for security teams starts with a pilot.</body></html>"
        if url.endswith("/contact"):
            return "<html><body>Contact our team for a demo.</body></html>"
        return "<html><body>Copperhelm helps security teams protect cloud agents.</body></html>"

    enriched, report = enrich_owner_evidence(
        [_candidate(founder_profiles=[])],
        query_runner=None,
        page_fetcher=fake_fetcher,
        cache_dir=tmp_path,
    )

    assert enriched[0].founder_team_evidence == []
    assert report["items"][0]["founder_team_evidence"] == []
    assert "no founder/team evidence" in report["items"][0]["missing_owner_evidence"]
    assert report["items"][0]["customer_buyer_evidence"] == ["https://copperhelm.com/customers", "https://copperhelm.com/pricing"]


def test_owner_evidence_requires_named_leadership_pattern_for_ceo_signal(tmp_path):
    from owner_evidence import enrich_owner_evidence

    def fake_fetcher(url):
        if url.endswith("/about"):
            return "<html><body>Copperhelm was built for security teams. CEO dashboards help teams prioritize risk.</body></html>"
        if url.endswith("/team"):
            return "<html><body>Maya Rao, CEO and co-founder, leads Copperhelm with CTO Luis Chen.</body></html>"
        return ""

    enriched, report = enrich_owner_evidence(
        [_candidate(founder_profiles=[])],
        query_runner=None,
        page_fetcher=fake_fetcher,
        cache_dir=tmp_path,
    )

    assert enriched[0].founder_team_evidence == ["https://copperhelm.com/team"]
    assert enriched[0].founder_profiles == [
        {"name": "Maya Rao", "role": "co-founder", "source": "https://copperhelm.com/team"},
        {"name": "Luis Chen", "role": "CTO", "source": "https://copperhelm.com/team"},
    ]
    assert report["items"][0]["founder_team_evidence"] == ["https://copperhelm.com/team"]


def test_owner_evidence_converts_veris_official_page_to_named_founder_profiles(tmp_path):
    from owner_evidence import enrich_owner_evidence

    def fake_fetcher(url):
        if url.endswith("/blog"):
            return (
                "<html><body><h1>Introducing Veris AI</h1>"
                "<p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Veris customers use simulated environments for enterprise AI agents.</p></body></html>"
            )
        return "<html><body>Veris AI trains enterprise AI agents.</body></html>"

    enriched, report = enrich_owner_evidence(
        [
            _candidate(
                name="Veris",
                domain="veris.ai",
                founder_profiles=[],
                founder_team_evidence=[],
                stage_funding_evidence=[],
                customer_buyer_evidence=[],
                maturity_status="seed_to_series_b",
                maturity_basis=["owner_evidence_stage_funding_signal"],
                maturity_evidence_urls=[],
            )
        ],
        query_runner=None,
        page_fetcher=fake_fetcher,
        cache_dir=tmp_path,
    )

    candidate = enriched[0]
    item = report["items"][0]
    assert candidate.founder_profiles == [
        {"name": "Mehdi Jamei", "role": "co-founder", "source": "https://veris.ai/blog"}
    ]
    assert candidate.founder_team_evidence == ["https://veris.ai/blog"]
    assert "founder_team_evidence" in candidate.owner_readiness_basis
    assert "no founder/team evidence" not in candidate.missing_owner_evidence
    assert item["founder_profiles"] == candidate.founder_profiles


def test_customer_buyer_evidence_labels_separate_generic_copy_from_commercial_pull():
    from owner_evidence import classify_customer_buyer_evidence

    assert classify_customer_buyer_evidence("No actual customer data is required.") == ["generic_positioning"]

    labels = classify_customer_buyer_evidence(
        "Enterprise teams can book demo access to validate agents before regulators find policy gaps."
    )

    assert "commercial_intent_evidence" in labels
    assert "waitlist_or_demo_evidence" in labels
    assert "buyer_pain_evidence" in labels
    assert "named_customer_evidence" not in labels


def test_owner_evidence_does_not_count_generic_customer_copy_as_customer_pull(tmp_path):
    from owner_evidence import enrich_owner_evidence

    def fake_fetcher(url):
        if url.endswith("/team"):
            return "<html><body>Copperhelm was founded by Maya Rao and Luis Chen.</body></html>"
        if url.endswith("/blog"):
            return "<html><body>Copperhelm raised a seed round for cloud security.</body></html>"
        return "<html><body>Copperhelm runs without needing customer data.</body></html>"

    enriched, report = enrich_owner_evidence(
        [_candidate(founder_profiles=[])],
        query_runner=None,
        page_fetcher=fake_fetcher,
        cache_dir=tmp_path,
    )

    candidate = enriched[0]
    item = report["items"][0]
    assert candidate.customer_buyer_evidence == []
    assert item["customer_buyer_evidence"] == []
    assert item["customer_buyer_evidence_types"]
    assert all(
        entry["evidence_types"] == ["generic_positioning"]
        for entry in item["customer_buyer_evidence_types"]
    )
    assert "customer_buyer_pull_evidence" not in candidate.owner_readiness_basis
    assert "no customer/buyer pull evidence" in candidate.missing_owner_evidence


def test_owner_evidence_runs_exact_funding_and_customer_queries_and_caches(tmp_path):
    from owner_evidence import enrich_owner_evidence

    calls = []

    def fake_query(topic, **kwargs):
        calls.append(topic)
        if "funding seed" in topic:
            return {
                "items": [
                    {
                        "title": "Copperhelm emerges from stealth with seed funding",
                        "url": "https://example.com/copperhelm-seed",
                        "snippet": "Copperhelm raised a $7M seed round for agentic cloud security.",
                    }
                ]
            }
        return {
            "items": [
                {
                    "title": "Copperhelm customer pilots",
                    "url": "https://example.com/copperhelm-pilots",
                    "snippet": "Enterprise security teams are using Copperhelm in design partner pilots.",
                }
            ]
        }

    first, first_report = enrich_owner_evidence(
        [_candidate(founder_profiles=[{"name": "Maya Rao"}])],
        query_runner=fake_query,
        page_fetcher=lambda url: "",
        cache_dir=tmp_path,
    )
    second, second_report = enrich_owner_evidence(
        [_candidate(founder_profiles=[{"name": "Maya Rao"}])],
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("query should be cached")),
        page_fetcher=lambda url: "",
        cache_dir=tmp_path,
    )

    assert calls == [
        '"Copperhelm" "copperhelm.com" funding seed series A series B',
        '"Copperhelm" "copperhelm.com" customers users case study enterprise',
    ]
    assert first_report["summary"]["queries_run"] == 2
    assert second_report["summary"]["query_cache_hits"] == 2
    assert first[0].stage_funding_evidence == ["https://example.com/copperhelm-seed"]
    assert first[0].customer_buyer_evidence == ["https://example.com/copperhelm-pilots"]
    assert second[0].stage_funding_evidence == ["https://example.com/copperhelm-seed"]
    assert second[0].customer_buyer_evidence == ["https://example.com/copperhelm-pilots"]


def test_owner_evidence_skips_category_context_and_oss_only_rows(tmp_path):
    from owner_evidence import enrich_owner_evidence

    calls = []

    def fake_query(topic, **kwargs):  # pragma: no cover - should not run
        calls.append(topic)
        return {"items": []}

    enriched, report = enrich_owner_evidence(
        [
            _candidate(name="n8n", domain="n8n.io", maturity_status="likely_too_late", category_anchor=True, lead_route="category_context"),
            _candidate(name="redwoodjs/agent-ci", candidate_type="oss_project", identity_type="oss_with_commercial_intent", domain="agent-ci.dev"),
        ],
        query_runner=fake_query,
        page_fetcher=lambda url: (_ for _ in ()).throw(AssertionError("fetch should not run")),
        cache_dir=tmp_path,
    )

    assert calls == []
    assert report["summary"]["eligible"] == 0
    assert report["summary"]["skipped"] == 2
    assert enriched[0].owner_evidence_status == "skipped"
    assert enriched[1].owner_evidence_status == "skipped"


def test_owner_evidence_attio_confidence_blocks_assign_owner(tmp_path):
    from owner_evidence import enrich_owner_evidence
    from radar_focus import ACTION_RESEARCH_DEEPER, build_focus_item

    enriched, report = enrich_owner_evidence(
        [
            _candidate(
                attio_status="unknown",
                attio_safe_to_match=True,
                founder_profiles=[{"name": "Maya Rao"}],
            )
        ],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Copperhelm seed funding and enterprise pilots",
                    "url": "https://example.com/copperhelm",
                    "snippet": "Copperhelm raised seed funding and is used by enterprise security teams.",
                }
            ]
        },
        page_fetcher=lambda url: "",
        cache_dir=tmp_path,
    )

    item = build_focus_item(enriched[0])
    assert report["items"][0]["attio_confidence"] == "Low"
    assert "attio_unknown" in report["items"][0]["attio_confidence_basis"]
    assert item.recommended_action == ACTION_RESEARCH_DEEPER
    assert "Attio status unknown" in item.missing_owner_evidence


def test_owner_evidence_does_not_turn_late_funding_text_into_seed_stage(tmp_path):
    from owner_evidence import enrich_owner_evidence

    enriched, report = enrich_owner_evidence(
        [
            _candidate(
                name="MatureCo",
                domain="matureco.com",
                maturity_status="unknown",
                maturity_basis=[],
                lead_route="research_deeper",
                founder_profiles=[{"name": "Ada Founder"}],
            )
        ],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "MatureCo raises Series C financing",
                    "url": "https://example.com/matureco-series-c",
                    "snippet": "MatureCo raised a Series C round for its enterprise security platform.",
                }
            ]
        },
        page_fetcher=lambda url: "",
        cache_dir=tmp_path,
    )

    assert enriched[0].maturity_status == "unknown"
    assert enriched[0].lead_route == "research_deeper"
    assert report["items"][0]["stage_funding_evidence"] == ["https://example.com/matureco-series-c"]


def test_owner_evidence_does_not_count_generic_funding_word_as_stage(tmp_path):
    from owner_evidence import enrich_owner_evidence

    enriched, report = enrich_owner_evidence(
        [
            _candidate(
                maturity_status="unknown",
                maturity_basis=[],
                maturity_evidence_urls=[],
                lead_route="research_deeper",
                founder_profiles=[{"name": "Maya Rao"}],
            )
        ],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Copperhelm security funding workflow",
                    "url": "https://example.com/funding-workflow",
                    "snippet": "Copperhelm helps security teams manage cloud funding approval workflows.",
                }
            ]
        },
        page_fetcher=lambda url: "",
        cache_dir=tmp_path,
    )

    assert enriched[0].stage_funding_evidence == []
    assert enriched[0].maturity_status == "unknown"
    assert report["items"][0]["stage_funding_evidence"] == []


def test_owner_evidence_counts_raised_amount_as_stage_signal(tmp_path):
    from owner_evidence import enrich_owner_evidence

    enriched, report = enrich_owner_evidence(
        [
            _candidate(
                maturity_status="unknown",
                maturity_basis=[],
                maturity_evidence_urls=[],
                lead_route="research_deeper",
                founder_profiles=[{"name": "Maya Rao"}],
            )
        ],
        query_runner=lambda topic, **kwargs: {
            "items": [
                {
                    "title": "Copperhelm raises $7M",
                    "url": "https://example.com/copperhelm-raises",
                    "snippet": "Copperhelm raised $7M to build agentic cloud security.",
                }
            ]
        },
        page_fetcher=lambda url: "",
        cache_dir=tmp_path,
    )

    assert enriched[0].stage_funding_evidence == ["https://example.com/copperhelm-raises"]
    assert report["items"][0]["stage_funding_evidence"] == ["https://example.com/copperhelm-raises"]


def test_owner_evidence_carries_existing_maturity_urls_into_stage_evidence(tmp_path):
    from owner_evidence import enrich_owner_evidence

    enriched, report = enrich_owner_evidence(
        [_candidate(stage_funding_evidence=[])],
        query_runner=None,
        page_fetcher=lambda url: "",
        cache_dir=tmp_path,
    )

    assert enriched[0].stage_funding_evidence == ["https://example.com/copperhelm-seed"]
    assert report["items"][0]["stage_funding_evidence"] == ["https://example.com/copperhelm-seed"]


def test_write_owner_evidence_artifact(tmp_path):
    from owner_evidence import enrich_owner_evidence, write_owner_evidence_json

    _, report = enrich_owner_evidence(
        [_candidate()],
        query_runner=None,
        page_fetcher=lambda url: "",
        cache_dir=tmp_path,
    )
    path = write_owner_evidence_json(report, tmp_path / "owner-evidence.json")
    payload = json.loads(path.read_text())

    assert path.name == "owner-evidence.json"
    assert payload["summary"]["eligible"] == 1
    assert payload["items"][0]["name"] == "Copperhelm"
