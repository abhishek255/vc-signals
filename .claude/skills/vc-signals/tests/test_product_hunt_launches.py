from __future__ import annotations


def test_parse_atom_feed_extracts_launch_identity_and_links():
    from product_hunt_launches import parse_product_hunt_feed

    feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>AgentFence by Ada Rao</title>
    <published>2026-05-25T07:15:00-07:00</published>
    <updated>2026-05-25T08:00:00-07:00</updated>
    <link rel="alternate" type="text/html" href="https://www.producthunt.com/products/agentfence"/>
    <content type="html">
      &lt;p&gt; Permission firewall for AI agents &lt;/p&gt;
      &lt;p&gt;
        &lt;a href="https://www.producthunt.com/products/agentfence"&gt;Discussion&lt;/a&gt; |
        &lt;a href="https://www.producthunt.com/r/p/123?app_id=339"&gt;Link&lt;/a&gt;
      &lt;/p&gt;
    </content>
  </entry>
</feed>
"""

    launches = parse_product_hunt_feed(feed, limit=5)

    assert launches == [
        {
            "source": "producthunt",
            "source_lane": "Product Hunt",
            "name": "AgentFence",
            "company_name": "AgentFence",
            "maker_name": "Ada Rao",
            "title": "AgentFence by Ada Rao",
            "tagline": "Permission firewall for AI agents",
            "description": "Permission firewall for AI agents",
            "published_at": "2026-05-25T07:15:00-07:00",
            "launch_date": "2026-05-25",
            "url": "https://www.producthunt.com/products/agentfence",
            "product_hunt_url": "https://www.producthunt.com/products/agentfence",
            "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
            "domain": "",
            "website": "",
            "action": "research deeper",
            "lead_route": "research_deeper",
            "missing_evidence": ["official_domain_identity_not_confirmed"],
            "why_this_may_be_noise": "Product Hunt launch feed row; needs official domain, founder/team, stage, and customer evidence before owner routing.",
        }
    ]


def test_resolve_product_hunt_redirect_adds_domain_when_available():
    from product_hunt_launches import enrich_launch_domains

    launches = [
        {
            "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
            "missing_evidence": ["official_domain_identity_not_confirmed"],
        }
    ]

    def fake_resolver(url: str) -> tuple[str, str]:
        assert url == "https://www.producthunt.com/r/p/123?app_id=339"
        return "https://agentfence.dev", ""

    enriched = enrich_launch_domains(launches, resolver=fake_resolver)

    assert enriched[0]["website"] == "https://agentfence.dev"
    assert enriched[0]["domain"] == "agentfence.dev"
    assert enriched[0]["missing_evidence"] == []
    assert enriched[0]["domain_resolution_status"] == "resolved"


def test_direct_external_product_hunt_link_sets_domain_without_redirect_call():
    from product_hunt_launches import enrich_launch_domains

    launches = [
        {
            "outbound_url": "https://agentfence.dev",
            "missing_evidence": ["official_domain_identity_not_confirmed"],
        }
    ]

    def fake_resolver(_url: str) -> tuple[str, str]:
        raise AssertionError("direct external URLs should not go through Product Hunt redirect resolver")

    enriched = enrich_launch_domains(launches, resolver=fake_resolver)

    assert enriched[0]["website"] == "https://agentfence.dev"
    assert enriched[0]["domain"] == "agentfence.dev"
    assert enriched[0]["missing_evidence"] == []
    assert enriched[0]["domain_resolution_status"] == "resolved"


def test_unresolved_product_hunt_redirect_keeps_identity_gap():
    from product_hunt_launches import enrich_launch_domains

    launches = [
        {
            "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
            "missing_evidence": ["official_domain_identity_not_confirmed"],
        }
    ]

    enriched = enrich_launch_domains(launches, resolver=lambda _url: ("", "403 Cloudflare challenge"))

    assert enriched[0]["domain"] == ""
    assert enriched[0]["website"] == ""
    assert enriched[0]["missing_evidence"] == ["official_domain_identity_not_confirmed"]
    assert enriched[0]["domain_resolution_status"] == "unresolved"
    assert enriched[0]["domain_resolution_warning"] == "403 Cloudflare challenge"


def test_product_hunt_web_fallback_resolves_domain_after_redirect_block():
    from product_hunt_launches import enrich_launch_domains

    launches = [
        {
            "name": "AgentFence",
            "tagline": "Permission firewall for AI agents",
            "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
            "missing_evidence": ["official_domain_identity_not_confirmed"],
        }
    ]

    def fake_fallback(launch: dict, timeout_seconds=None) -> dict:
        assert launch["name"] == "AgentFence"
        assert timeout_seconds == 7
        return {
            "url": "https://agentfence.dev",
            "evidence": {
                "source": "web_fallback",
                "verification": ["search_result_mentions_product_name"],
            },
        }

    enriched = enrich_launch_domains(
        launches,
        resolver=lambda _url: ("", "403 Forbidden"),
        fallback_resolver=fake_fallback,
        timeout_seconds=7,
    )

    assert enriched[0]["website"] == "https://agentfence.dev"
    assert enriched[0]["domain"] == "agentfence.dev"
    assert enriched[0]["domain_resolution_source"] == "web_fallback"
    assert enriched[0]["product_hunt_redirect_warning"] == "403 Forbidden"
    assert enriched[0]["missing_evidence"] == []


def test_product_hunt_web_fallback_rejects_unverified_social_domains():
    from product_hunt_launches import resolve_launch_domain_via_web

    def fake_query_runner(**_kwargs):
        return {
            "items": [
                {
                    "title": "AgentFence on X",
                    "url": "https://x.com/agentfence",
                    "snippet": "AgentFence launch updates",
                },
                {
                    "title": "AgentFence",
                    "url": "https://agentfence.dev",
                    "snippet": "Permission firewall for AI agents",
                },
            ]
        }

    result = resolve_launch_domain_via_web(
        {"name": "AgentFence", "tagline": "Permission firewall for AI agents"},
        query_runner=fake_query_runner,
    )

    assert result["url"] == "https://agentfence.dev"
    assert result["evidence"]["domain"] == "agentfence.dev"


def test_product_hunt_web_fallback_does_not_treat_third_party_profiles_as_official():
    from product_hunt_launches import resolve_launch_domain_via_web

    def fake_query_runner(**_kwargs):
        return {
            "items": [
                {
                    "title": "Clipto - 2026 Company Profile, Team & Funding - Tracxn",
                    "url": "https://tracxn.com/d/companies/clipto/profile",
                    "snippet": "Developer of on-device AI software for media transcription.",
                },
                {
                    "title": "Oura launches Ring 5 as it heads towards IPO",
                    "url": "https://www.theguardian.com/technology/oura-ring-5",
                    "snippet": "Oura Ring 5 is the world's smallest smart ring.",
                },
            ]
        }

    result = resolve_launch_domain_via_web(
        {"name": "Clipto", "tagline": "Fully local, natural language search over terabytes of media"},
        query_runner=fake_query_runner,
    )

    assert result["url"] == ""
    assert "no verified official domain" in result["warning"]


def test_product_hunt_web_fallback_rejects_app_directory_subdomains():
    from product_hunt_launches import resolve_launch_domain_via_web

    def fake_query_runner(**_kwargs):
        return {
            "items": [
                {
                    "title": "ChartBuilder for Android - Download the APK from Uptodown",
                    "url": "https://chartbuilder.en.uptodown.com/android",
                    "snippet": "Customizable chart creation app.",
                }
            ]
        }

    result = resolve_launch_domain_via_web(
        {"name": "Chartbuilder", "tagline": "Turn raw data into export-ready charts with AI"},
        query_runner=fake_query_runner,
    )

    assert result["url"] == ""
    assert "no verified official domain" in result["warning"]


def test_parse_product_hunt_api_posts_preserves_makers_and_launch_metrics():
    from product_hunt_launches import parse_product_hunt_api_posts

    launches = parse_product_hunt_api_posts(
        [
            {
                "name": "AgentFence",
                "tagline": "Permission firewall for AI agents",
                "url": "https://www.producthunt.com/products/agentfence",
                "website": "https://www.producthunt.com/r/abc",
                "votesCount": 321,
                "commentsCount": 42,
                "createdAt": "2026-05-31T07:01:00Z",
                "featuredAt": "2026-05-31T08:01:00Z",
                "dailyRank": 3,
                "makers": [
                    {
                        "name": "Ada Rao",
                        "username": "adarao",
                        "url": "https://www.producthunt.com/@adarao",
                    }
                ],
                "productLinks": [{"type": "Website", "url": "https://agentfence.dev"}],
            }
        ]
    )

    assert launches[0]["source_detail"] == "api"
    assert launches[0]["maker_name"] == "Ada Rao"
    assert launches[0]["maker_profiles"] == [
        {
            "name": "Ada Rao",
            "username": "adarao",
            "product_hunt_url": "https://www.producthunt.com/@adarao",
        }
    ]
    assert launches[0]["votes_count"] == 321
    assert launches[0]["comments_count"] == 42
    assert launches[0]["daily_rank"] == 3
    assert launches[0]["outbound_url"] == "https://agentfence.dev"
    assert launches[0]["launch_evidence"]["votes_count"] == 321
    assert launches[0]["launch_evidence"]["comments_count"] == 42
    assert launches[0]["founder_team_evidence"] == ["https://www.producthunt.com/@adarao"]
    assert "founder_team_missing" not in launches[0]["missing_evidence"]


def test_product_hunt_launch_conversion_status_tracks_domain_and_manual_gaps():
    from product_hunt_launches import enrich_launch_domains, normalize_product_hunt_api_post

    launch = normalize_product_hunt_api_post(
        {
            "name": "AgentFence",
            "tagline": "Permission firewall for AI agents",
            "url": "https://www.producthunt.com/products/agentfence",
            "website": "https://www.producthunt.com/r/abc",
            "votesCount": 100,
            "commentsCount": 10,
            "makers": [{"name": "Ada Rao", "username": "adarao", "url": "https://www.producthunt.com/@adarao"}],
        }
    )

    enriched = enrich_launch_domains(
        [launch],
        resolver=lambda _url: ("", "403 Forbidden"),
        fallback_resolver=lambda *_args, **_kwargs: {"url": "https://agentfence.dev"},
    )

    assert enriched[0]["domain"] == "agentfence.dev"
    assert enriched[0]["product_hunt_conversion_status"] == "domain_resolved_needs_company_evidence"
    assert enriched[0]["missing_evidence"] == [
        "stage_funding_or_headcount_missing",
        "commercial_or_customer_signal_missing",
        "pricing_docs_or_careers_missing",
        "company_linkedin_or_social_missing",
    ]


def test_run_product_hunt_launches_uses_api_when_token_exists(monkeypatch):
    import product_hunt_launches

    monkeypatch.setattr(product_hunt_launches, "product_hunt_token", lambda: "ph-token")
    monkeypatch.setattr(
        product_hunt_launches,
        "fetch_product_hunt_api_posts",
        lambda **_kwargs: [
            {
                "name": "AgentFence",
                "tagline": "Permission firewall for AI agents",
                "url": "https://www.producthunt.com/products/agentfence",
                "website": "https://agentfence.dev",
                "makers": [{"name": "Ada Rao"}],
            }
        ],
    )

    result = product_hunt_launches.run_product_hunt_launches(limit=1)

    assert result["source_mode"] == "api"
    assert result["launches"][0]["source_detail"] == "api"
    assert result["launches"][0]["domain"] == "agentfence.dev"


def test_product_hunt_api_prefers_direct_website_over_redirect():
    from product_hunt_launches import normalize_product_hunt_api_post

    launch = normalize_product_hunt_api_post(
        {
            "name": "AgentFence",
            "tagline": "Permission firewall for AI agents",
            "url": "https://www.producthunt.com/products/agentfence",
            "website": "https://agentfence.dev",
            "productLinks": [{"type": "website", "url": "https://www.producthunt.com/r/abc123"}],
        }
    )

    assert launch["outbound_url"] == "https://agentfence.dev"


def test_product_hunt_web_fallback_checks_link_lists_for_official_domain():
    from product_hunt_launches import resolve_launch_domain_via_web

    def fake_query_runner(**_kwargs):
        return {
            "items": [
                {
                    "title": "AgentFence launches on Product Hunt",
                    "url": "https://news.example.com/agentfence",
                    "snippet": "AgentFence is a permission firewall for AI agents.",
                    "links": [{"href": "https://agentfence.dev"}],
                }
            ]
        }

    result = resolve_launch_domain_via_web(
        {"name": "AgentFence", "tagline": "Permission firewall for AI agents"},
        query_runner=fake_query_runner,
    )

    assert result["url"] == "https://agentfence.dev"
    assert result["evidence"]["domain"] == "agentfence.dev"


def test_product_hunt_web_fallback_checks_urls_embedded_in_snippets():
    from product_hunt_launches import resolve_launch_domain_via_web

    def fake_query_runner(**_kwargs):
        return {
            "items": [
                {
                    "title": "AgentFence launches on Product Hunt",
                    "url": "https://news.example.com/agentfence",
                    "snippet": "AgentFence is a permission firewall for AI agents. Official site: https://agentfence.dev",
                }
            ]
        }

    result = resolve_launch_domain_via_web(
        {"name": "AgentFence", "tagline": "Permission firewall for AI agents"},
        query_runner=fake_query_runner,
    )

    assert result["url"] == "https://agentfence.dev"
    assert result["evidence"]["domain"] == "agentfence.dev"
    assert "url_extracted_from_text" in result["evidence"]["verification"]


def test_run_product_hunt_launches_falls_back_to_feed_when_api_fails(monkeypatch):
    import product_hunt_launches

    monkeypatch.setattr(product_hunt_launches, "product_hunt_token", lambda: "ph-token")
    monkeypatch.setattr(
        product_hunt_launches,
        "fetch_product_hunt_api_posts",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("api down")),
    )
    monkeypatch.setattr(
        product_hunt_launches,
        "fetch_product_hunt_feed",
        lambda **_kwargs: """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>AgentFence by Ada Rao</title>
    <published>2026-05-25T07:15:00-07:00</published>
    <link rel="alternate" type="text/html" href="https://www.producthunt.com/products/agentfence"/>
    <content type="html">&lt;p&gt;Permission firewall&lt;/p&gt;</content>
  </entry>
</feed>
""",
    )
    monkeypatch.setattr(
        product_hunt_launches,
        "resolve_launch_domain_via_web",
        lambda *_args, **_kwargs: {"url": "", "warning": "web fallback skipped in test"},
    )

    result = product_hunt_launches.run_product_hunt_launches(limit=1)

    assert result["source_mode"] == "feed_fallback"
    assert result["launches"][0]["name"] == "AgentFence"
    assert any("Product Hunt API unavailable" in warning for warning in result["warnings"])
