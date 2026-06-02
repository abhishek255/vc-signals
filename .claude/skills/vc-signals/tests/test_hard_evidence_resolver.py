from __future__ import annotations


def test_resolver_uses_direct_provider_to_resolve_domain_and_commercial_evidence():
    from hard_evidence_resolver import build_hard_evidence_dossier

    queries = []

    def fake_search_runner(query, **kwargs):
        queries.append(query)
        return {
            "provider": "brave",
            "items": [
                {
                    "title": "Clipto AI - Local media search",
                    "url": "https://clipto.ai",
                    "snippet": "Clipto is a fully local natural language search product for media teams.",
                },
                {
                    "title": "Clipto Pricing",
                    "url": "https://clipto.ai/pricing",
                    "snippet": "Pricing plans for teams.",
                },
                {
                    "title": "Clipto Docs",
                    "url": "https://clipto.ai/docs",
                    "snippet": "Docs and API for Clipto.",
                },
                {
                    "title": "Clipto on Product Hunt",
                    "url": "https://www.producthunt.com/products/clipto-ai",
                    "snippet": "Clipto launched on Product Hunt.",
                },
            ],
        }

    dossier = build_hard_evidence_dossier(
        {
            "name": "Clipto AI",
            "tagline": "Fully local natural language search for your media",
            "product_hunt_url": "https://www.producthunt.com/products/clipto-ai",
            "maker_profiles": ["https://www.producthunt.com/@alex"],
        },
        source_lane="Product Hunt",
        search_runner=fake_search_runner,
        provider="brave",
    )

    assert queries
    assert dossier["provider"] == "brave"
    assert dossier["official_domain"] == "clipto.ai"
    assert dossier["official_url"] == "https://clipto.ai"
    assert "https://clipto.ai/pricing" in dossier["commercial_hints"]
    assert "https://clipto.ai/docs" in dossier["commercial_hints"]
    assert dossier["unsafe_domain_attempts_blocked"] >= 1


def test_apply_dossier_to_source_row_sets_domain_without_inventing_stage():
    from hard_evidence_resolver import apply_dossier_to_source_row

    row = {
        "name": "Clipto AI",
        "source_lane": "Product Hunt",
        "domain": "",
        "website": "",
        "maker_profiles": ["https://www.producthunt.com/@alex"],
        "missing_evidence": ["official_domain_identity_not_confirmed", "stage_funding_or_headcount_missing"],
    }
    dossier = {
        "official_domain": "clipto.ai",
        "official_url": "https://clipto.ai",
        "official_domain_confidence": 85,
        "founder_hints": ["https://clipto.ai/about"],
        "stage_hints": [],
        "commercial_hints": ["https://clipto.ai/pricing", "https://clipto.ai/docs"],
        "evidence_urls": ["https://clipto.ai", "https://clipto.ai/pricing", "https://clipto.ai/docs"],
        "unsafe_domain_attempts_blocked": 1,
    }

    enriched = apply_dossier_to_source_row(row, dossier)

    assert enriched["domain"] == "clipto.ai"
    assert enriched["website"] == "https://clipto.ai"
    assert enriched["domain_resolution_source"] == "hard_evidence"
    assert "official_domain_identity_not_confirmed" not in enriched["missing_evidence"]
    assert "https://clipto.ai/pricing" in enriched["pricing_evidence"]
    assert "https://clipto.ai/docs" in enriched["docs_evidence"]
    assert enriched["stage"] == ""
    assert enriched["headcount"] == ""
    assert enriched["hard_evidence_dossier"]["official_domain"] == "clipto.ai"


def test_apply_dossier_keeps_ambiguous_domain_in_evidence_gap():
    from hard_evidence_resolver import apply_dossier_to_source_row

    row = {
        "name": "Sentinel",
        "source_lane": "Product Hunt",
        "domain": "",
        "website": "",
        "maker_profiles": ["https://www.producthunt.com/@maker"],
        "missing_evidence": ["official_domain_identity_not_confirmed"],
    }
    dossier = {
        "official_domain": "sentinelone.com",
        "official_url": "https://www.sentinelone.com/lp/threat-hunting-championship/",
        "official_domain_confidence": 85,
        "identity_risk_flags": ["domain_context_mismatch"],
        "founder_hints": [],
        "commercial_hints": [],
        "evidence_urls": ["https://www.sentinelone.com/lp/threat-hunting-championship/"],
        "url_roles": [
            {
                "url": "https://www.sentinelone.com/lp/threat-hunting-championship/",
                "domain": "sentinelone.com",
                "role": "official_site",
                "official_eligible": True,
            }
        ],
    }

    enriched = apply_dossier_to_source_row(row, dossier)

    assert enriched["domain"] == ""
    assert enriched["website"] == ""
    assert "official_domain_identity_not_confirmed" in enriched["missing_evidence"]
    assert "official_domain_identity_ambiguous" in enriched["missing_evidence"]


def test_apply_dossier_clears_web_fallback_domain_when_hard_evidence_is_ambiguous():
    from hard_evidence_resolver import apply_dossier_to_source_row

    row = {
        "name": "Sentinel",
        "source_lane": "Product Hunt",
        "domain": "sentinelmarine.net",
        "website": "https://www.sentinelmarine.net/api",
        "domain_resolution_source": "web_fallback",
        "domain_resolution_status": "resolved",
        "missing_evidence": [],
    }
    dossier = {
        "official_domain": "",
        "official_url": "",
        "official_domain_confidence": 0,
        "identity_risk_flags": ["ambiguous_official_domain_candidates"],
        "commercial_hints": [],
        "evidence_urls": [
            "https://docs.sentinel.co/apis",
            "https://www.sentinelmarine.net/api",
        ],
        "url_roles": [],
    }

    enriched = apply_dossier_to_source_row(row, dossier)

    assert enriched["domain"] == ""
    assert enriched["website"] == ""
    assert enriched["domain_resolution_status"] == "ambiguous"
    assert "official_domain_identity_ambiguous" in enriched["missing_evidence"]


def test_apply_dossier_counts_commercial_evidence_only_on_selected_domain():
    from hard_evidence_resolver import apply_dossier_to_source_row

    row = {
        "name": "Open Caffeine",
        "source_lane": "Product Hunt",
        "domain": "",
        "website": "",
        "maker_profiles": ["https://www.producthunt.com/@maker"],
        "missing_evidence": ["commercial_or_customer_signal_missing"],
    }
    dossier = {
        "official_domain": "caffeine-app.net",
        "official_url": "https://www.caffeine-app.net/en/",
        "official_domain_confidence": 85,
        "founder_hints": [],
        "commercial_hints": ["https://openstage.live/fanbase-api", "https://www.caffeine-app.net/docs"],
        "evidence_urls": ["https://www.caffeine-app.net/en/", "https://openstage.live/fanbase-api"],
        "url_roles": [
            {
                "url": "https://www.caffeine-app.net/en/",
                "domain": "caffeine-app.net",
                "role": "official_site",
                "official_eligible": True,
            }
        ],
    }

    enriched = apply_dossier_to_source_row(row, dossier)

    assert "https://www.caffeine-app.net/docs" in enriched["docs_evidence"]
    assert "https://openstage.live/fanbase-api" not in enriched.get("customer_buyer_evidence", [])
    assert "commercial_or_customer_signal_missing" not in enriched["missing_evidence"]


def test_apply_dossier_does_not_count_plain_homepage_as_commercial_evidence():
    from hard_evidence_resolver import apply_dossier_to_source_row

    row = {
        "name": "Stella",
        "source_lane": "Product Hunt",
        "domain": "",
        "website": "",
        "maker_profiles": ["https://www.producthunt.com/@maker"],
        "missing_evidence": ["commercial_or_customer_signal_missing"],
    }
    dossier = {
        "official_domain": "stella.expert",
        "official_url": "https://stella.expert/",
        "official_domain_confidence": 85,
        "founder_hints": [],
        "commercial_hints": ["https://stella.expert/"],
        "evidence_urls": ["https://stella.expert/"],
        "url_roles": [
            {
                "url": "https://stella.expert/",
                "domain": "stella.expert",
                "role": "official_site",
                "official_eligible": True,
            }
        ],
    }

    enriched = apply_dossier_to_source_row(row, dossier)

    assert enriched["domain"] == "stella.expert"
    assert "customer_buyer_evidence" not in enriched
    assert "commercial_or_customer_signal_missing" in enriched["missing_evidence"]


def test_resolver_rejects_social_directory_and_repo_as_official_domains():
    from hard_evidence_resolver import build_hard_evidence_dossier

    def fake_search_runner(query, **kwargs):
        return {
            "items": [
                {"title": "Nova Launch on Product Hunt", "url": "https://www.producthunt.com/products/nova", "snippet": ""},
                {"title": "Nova on X", "url": "https://x.com/nova/status/1", "snippet": ""},
                {"title": "Nova GitHub", "url": "https://github.com/nova/tool", "snippet": ""},
            ]
        }

    dossier = build_hard_evidence_dossier(
        {"name": "Nova", "tagline": "Launch signal"},
        source_lane="X",
        search_runner=fake_search_runner,
    )

    assert dossier["official_domain"] == ""
    assert dossier["official_url"] == ""
    assert dossier["unsafe_domain_attempts_blocked"] >= 3


def test_default_search_runner_tries_exa_before_brave(monkeypatch):
    import hard_evidence_resolver

    monkeypatch.setattr(hard_evidence_resolver, "load_provider_env_files", lambda: {})
    monkeypatch.setattr(hard_evidence_resolver, "provider_available", lambda provider: provider in {"exa", "brave"})

    calls = []

    def fake_run_provider_query(provider, query, **kwargs):
        calls.append(provider)
        if provider == "exa":
            return {"provider": "exa", "query": query["query"], "items": []}
        return {
            "provider": "brave",
            "query": query["query"],
            "items": [{"title": "AgentFence", "url": "https://agentfence.dev", "snippet": ""}],
        }

    monkeypatch.setattr(hard_evidence_resolver, "run_provider_query", fake_run_provider_query)

    result = hard_evidence_resolver._default_search_runner("AgentFence official website", provider="exa,brave")

    assert calls == ["exa", "brave"]
    assert result["provider"] == "brave"
    assert result["items"][0]["url"] == "https://agentfence.dev"


def test_official_site_crawler_classifies_about_pricing_docs_customers_and_careers():
    from hard_evidence_resolver import crawl_official_site_evidence

    pages = {
        "https://agentfence.dev/about": "About AgentFence. Built by founder Ada Rao for AI agent security teams.",
        "https://agentfence.dev/pricing": "Pricing plans for teams and startups.",
        "https://agentfence.dev/docs": "Developer docs and API reference.",
        "https://agentfence.dev/customers": "Trusted by platform engineering customers.",
        "https://agentfence.dev/careers": "We are hiring engineers.",
        "https://agentfence.dev/blog": "Launch notes and product updates.",
    }

    def fake_fetcher(url, **_kwargs):
        if url not in pages:
            return {"url": url, "status_code": 404, "text": ""}
        return {"url": url, "status_code": 200, "text": pages[url]}

    evidence = crawl_official_site_evidence(
        "https://agentfence.dev",
        page_fetcher=fake_fetcher,
        paths=("/about", "/pricing", "/docs", "/customers", "/careers", "/blog"),
    )

    assert evidence["official_domain"] == "agentfence.dev"
    assert "https://agentfence.dev/about" in evidence["founder_team_evidence"]
    assert "https://agentfence.dev/pricing" in evidence["pricing_evidence"]
    assert "https://agentfence.dev/docs" in evidence["docs_evidence"]
    assert "https://agentfence.dev/customers" in evidence["customer_buyer_evidence"]
    assert "https://agentfence.dev/careers" in evidence["careers_evidence"]
    assert "https://agentfence.dev/blog" in evidence["product_evidence"]
