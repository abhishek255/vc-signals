from __future__ import annotations


def test_x_credentials_require_xai_or_cookie_pair():
    from x_launches import x_credentials_available

    assert x_credentials_available({"XAI_API_KEY": "xai-key"}) is True
    assert x_credentials_available({"AUTH_TOKEN": "auth", "CT0": "ct0"}) is True
    assert x_credentials_available({"AUTH_TOKEN": "auth"}) is False
    assert x_credentials_available({}) is False


def test_run_x_launches_skips_with_source_health_when_credentials_missing():
    from x_launches import run_x_launches

    result = run_x_launches(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        env={},
        query_runner=lambda **_kwargs: {"items": [{"title": "should not run"}]},
    )

    assert result["launches"] == []
    assert result["status"] == "unavailable"
    assert "X launch lane skipped" in result["warnings"][0]


def test_run_x_launches_normalizes_company_launch_items_when_credentials_exist():
    from x_launches import run_x_launches

    calls = []

    def fake_query_runner(**kwargs):
        calls.append(kwargs)
        return {
            "items": [
                {
                    "source": "x",
                    "title": "Founder launches AgentForge for AI agent security teams",
                    "url": "https://x.com/founder/status/1",
                    "company_name": "AgentForge",
                    "website": "https://agentforge.dev",
                    "author": "Asha Rao",
                    "published_at": "2026-05-30T12:00:00Z",
                    "snippet": "We launched AgentForge for AI agent security teams.",
                }
            ]
        }

    result = run_x_launches(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=fake_query_runner,
        limit=5,
    )

    assert calls[0]["sources"] == "x"
    assert result["status"] == "complete"
    assert result["launches"][0]["source"] == "x"
    assert result["launches"][0]["source_lane"] == "X"
    assert result["launches"][0]["company_name"] == "AgentForge"
    assert result["launches"][0]["domain"] == "agentforge.dev"
    assert result["launches"][0]["action"] == "research deeper"
    assert result["launches"][0]["launch_intent_score"] >= 70
    assert result["launches"][0]["social_confidence_evidence"][0]["author"] == "Asha Rao"


def test_run_x_launches_resolves_missing_domain_via_web():
    from x_launches import run_x_launches

    calls = []

    def fake_query_runner(**kwargs):
        calls.append(kwargs)
        if kwargs["sources"] == "x":
            return {
                "items": [
                    {
                        "source": "x",
                        "title": "Founder launches AgentForge for AI agent security teams",
                        "url": "https://x.com/founder/status/1",
                        "company_name": "AgentForge",
                        "author": "Asha Rao",
                        "snippet": "We launched AgentForge for AI agent security teams.",
                    }
                ]
            }
        return {
            "items": [
                {
                    "title": "AgentForge official website",
                    "url": "https://agentforge.dev",
                    "snippet": "AgentForge is an AI agent security company.",
                }
            ]
        }

    result = run_x_launches(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=fake_query_runner,
        limit=5,
    )

    assert calls[0]["sources"] == "x"
    assert len([call for call in calls if call["sources"] == "web"]) == 1
    assert result["launches"][0]["domain"] == "agentforge.dev"
    assert result["launches"][0]["domain_resolution_source"] == "web_fallback"
    assert "official_domain_identity_not_confirmed" not in result["launches"][0]["missing_evidence"]


def test_run_x_launches_caps_movement_queries_and_web_timeout():
    from x_launches import DEFAULT_WEB_RESOLVER_TIMEOUT_SECONDS, run_x_launches

    calls = []

    def fake_query_runner(**kwargs):
        calls.append(kwargs)
        if kwargs["sources"] == "x":
            return {
                "items": [
                    {
                        "source": "x",
                        "title": "Founder launches AgentForge",
                        "url": "https://x.com/founder/status/1",
                        "company_name": "AgentForge",
                        "snippet": "We launched AgentForge.",
                    }
                ]
            }
        return {"items": []}

    result = run_x_launches(
        movements=[
            {"movement": "movement one", "market_sector": "Devtools"},
            {"movement": "movement two", "market_sector": "Devtools"},
            {"movement": "movement three", "market_sector": "Devtools"},
        ],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=fake_query_runner,
        domain_resolver=None,
        limit=5,
        max_queries=2,
    )

    assert len(result["queries"]) == 2
    assert len([call for call in calls if call["sources"] == "x"]) == 2

    calls.clear()
    run_x_launches(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=fake_query_runner,
        limit=5,
        timeout_seconds=60,
    )

    web_calls = [call for call in calls if call["sources"] == "web"]
    assert web_calls
    assert all(call["timeout_seconds"] == DEFAULT_WEB_RESOLVER_TIMEOUT_SECONDS for call in web_calls)


def test_run_x_launches_caps_domain_resolution_attempts():
    from x_launches import run_x_launches

    resolver_calls = []

    def fake_query_runner(**kwargs):
        return {
            "items": [
                {
                    "source": "x",
                    "title": f"Founder launches AgentForge {index}",
                    "url": f"https://x.com/founder/status/{index}",
                    "company_name": f"AgentForge{index}",
                    "snippet": "We launched AgentForge for developer teams.",
                }
                for index in range(5)
            ]
        }

    def fake_resolver(launch, **_kwargs):
        resolver_calls.append(launch["company_name"])
        return {"url": "", "warning": "no verified official domain"}

    result = run_x_launches(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=fake_query_runner,
        domain_resolver=fake_resolver,
        limit=5,
        max_domain_resolutions=2,
    )

    assert resolver_calls == ["AgentForge0", "AgentForge1"]
    assert "X domain resolver capped after 2 attempts" in result["warnings"]


def test_run_x_launches_resolves_official_url_embedded_in_x_snippet_without_web_fallback():
    from x_launches import run_x_launches

    def forbidden_resolver(*_args, **_kwargs):
        raise AssertionError("embedded official URLs should resolve before web fallback")

    result = run_x_launches(
        movements=[{"movement": "Devtools product launch", "market_sector": "Devtools"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=lambda **_kwargs: {
            "items": [
                {
                    "source": "x",
                    "title": "Just launched Xell, an open-source SSH workspace",
                    "url": "https://x.com/founder/status/1",
                    "company_name": "Xell",
                    "author": "Ildy Silva",
                    "snippet": "Just launched Xell for developers. Try it at https://xell.pro #OpenSource #DevTools",
                }
            ]
        },
        domain_resolver=forbidden_resolver,
        limit=5,
    )

    assert result["launches"][0]["website"] == "https://xell.pro"
    assert result["launches"][0]["domain"] == "xell.pro"
    assert result["launches"][0]["domain_resolution_source"] == "embedded_launch_text_url"
    assert "official_domain_identity_not_confirmed" not in result["launches"][0]["missing_evidence"]


def test_run_x_launches_resolves_structured_link_url_without_web_fallback():
    from x_launches import run_x_launches

    def forbidden_resolver(*_args, **_kwargs):
        raise AssertionError("structured official links should resolve before web fallback")

    result = run_x_launches(
        movements=[{"movement": "Devtools product launch", "market_sector": "Devtools"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=lambda **_kwargs: {
            "items": [
                {
                    "source": "x",
                    "title": "Just launched BuildGraph for developer workflows",
                    "url": "https://x.com/founder/status/1",
                    "company_name": "BuildGraph",
                    "author": "Ira Shah",
                    "snippet": "Just launched BuildGraph for developer teams.",
                    "links": [{"url": "https://buildgraph.dev"}],
                }
            ]
        },
        domain_resolver=forbidden_resolver,
        limit=5,
    )

    assert result["launches"][0]["website"] == "https://buildgraph.dev"
    assert result["launches"][0]["domain"] == "buildgraph.dev"
    assert result["launches"][0]["domain_resolution_source"] == "embedded_launch_link_url"
    assert "official_domain_identity_not_confirmed" not in result["launches"][0]["missing_evidence"]


def test_build_x_launch_queries_emits_multiple_launch_intent_variants():
    from x_launches import build_x_launch_queries

    queries = build_x_launch_queries(
        [{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        lookback_days=7,
    )

    assert len(queries) >= 3
    assert all(query["sources"] == "x" for query in queries)
    assert all(query["lookback_days"] == 7 for query in queries)
    topics = " ".join(query["topic"] for query in queries)
    assert "we launched" in topics
    assert "public beta" in topics
    assert "waitlist" in topics


def test_run_x_launches_resolves_bare_domain_embedded_in_x_snippet():
    from x_launches import run_x_launches

    def forbidden_resolver(*_args, **_kwargs):
        raise AssertionError("bare embedded official domains should resolve before web fallback")

    result = run_x_launches(
        movements=[{"movement": "Devtools product launch", "market_sector": "Devtools"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=lambda **_kwargs: {
            "items": [
                {
                    "source": "x",
                    "title": "Just launched BuildGraph for developer workflows",
                    "url": "https://x.com/founder/status/1",
                    "company_name": "BuildGraph",
                    "author": "Ira Shah",
                    "snippet": "Just launched BuildGraph for developer teams. Try it at buildgraph.dev",
                }
            ]
        },
        domain_resolver=forbidden_resolver,
        limit=5,
    )

    assert result["launches"][0]["website"] == "https://buildgraph.dev"
    assert result["launches"][0]["domain"] == "buildgraph.dev"
    assert result["launches"][0]["domain_resolution_source"] == "embedded_launch_text_url"
    assert "official_domain_identity_not_confirmed" not in result["launches"][0]["missing_evidence"]


def test_run_x_launches_infers_company_name_from_embedded_official_domain_when_launch_intent_is_clear():
    from x_launches import run_x_launches

    result = run_x_launches(
        movements=[{"movement": "Devtools product launch", "market_sector": "Devtools"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=lambda **_kwargs: {
            "items": [
                {
                    "source": "x",
                    "title": "Just launched the workflow graph we built for developer teams",
                    "url": "https://x.com/founder/status/1",
                    "author": "Ira Shah",
                    "snippet": "We launched our public beta today at https://buildgraph.dev",
                }
            ]
        },
        domain_resolver=None,
        limit=5,
    )

    assert result["launches"][0]["company_name"] == "Buildgraph"
    assert result["launches"][0]["domain"] == "buildgraph.dev"
    assert result["launches"][0]["domain_resolution_source"] == "embedded_launch_text_url"


def test_run_x_launches_drops_generic_company_names_without_domains():
    from x_launches import run_x_launches

    calls = []

    def fake_query_runner(**kwargs):
        calls.append(kwargs)
        return {
            "items": [
                {
                    "source": "x",
                    "title": "Launching MCP for devtools",
                    "url": "https://x.com/founder/status/1",
                    "company_name": "MCP",
                    "snippet": "Launching MCP for devtools.",
                }
            ]
        }

    result = run_x_launches(
        movements=[{"movement": "devtools workflow automation", "market_sector": "Devtools"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=fake_query_runner,
        limit=5,
    )

    assert all(call["sources"] == "x" for call in calls)
    assert len(calls) == 4
    assert result["launches"] == []
    assert "company name is too generic" in result["warnings"][0]


def test_x_launch_preserves_lower_confidence_chatter_as_watch_when_identity_exists():
    from x_launches import run_x_launches

    result = run_x_launches(
        movements=[{"movement": "devtools workflow automation", "market_sector": "Devtools"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=lambda **_kwargs: {
            "items": [
                {
                    "source": "x",
                    "title": "Quiet beta notes from BuildGraph",
                    "url": "https://x.com/founder/status/1",
                    "company_name": "BuildGraph",
                    "website": "https://buildgraph.dev",
                    "author": "Ira Shah",
                    "snippet": "Testing an early workflow graph for developer teams.",
                }
            ]
        },
        limit=5,
    )

    assert result["launches"][0]["company_name"] == "BuildGraph"
    assert result["launches"][0]["action"] == "watch"
    assert result["launches"][0]["lead_route"] == "watch"
    assert result["launches"][0]["launch_intent_score"] < 60
    assert "launch_intent_low" in result["launches"][0]["missing_evidence"]


def test_run_x_launches_does_not_treat_x_domain_as_official_identity():
    from x_launches import run_x_launches

    result = run_x_launches(
        movements=[{"movement": "devtools workflow automation", "market_sector": "Devtools"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=lambda **_kwargs: {
            "items": [
                {
                    "source": "x",
                    "title": "Just launched Xell, an open-source SSH workspace",
                    "url": "https://x.com/founder/status/1",
                    "company_name": "Xell",
                    "domain": "x.com",
                    "snippet": "Just launched Xell for developers.",
                }
            ]
        },
        domain_resolver=lambda *_args, **_kwargs: {"url": "", "warning": "no verified official domain"},
        limit=5,
    )

    assert result["launches"][0]["domain"] == ""
    assert result["launches"][0]["website"] == ""
    assert "official_domain_identity_not_confirmed" in result["launches"][0]["missing_evidence"]


def test_run_x_launches_keeps_article_url_as_evidence_not_official_domain():
    from x_launches import run_x_launches

    result = run_x_launches(
        movements=[{"movement": "Cybersecurity product launch", "market_sector": "Cybersecurity"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=lambda **_kwargs: {
            "items": [
                {
                    "source": "x",
                    "title": "The Nuclear Company has launched NOS Security",
                    "url": "https://x.com/news/status/1",
                    "company_name": "NOS Security",
                    "website": "https://securityjournalamericas.com/the-nuclear-company-launches-integrated-cyber-physical-security-platform/",
                    "snippet": "The Nuclear Company has launched NOS Security for nuclear infrastructure protection.",
                }
            ]
        },
        domain_resolver=lambda *_args, **_kwargs: {"url": "", "warning": "no verified official domain"},
        limit=5,
    )

    launch = result["launches"][0]
    assert launch["domain"] == ""
    assert launch["website"] == ""
    assert "official_domain_identity_not_confirmed" in launch["missing_evidence"]
    assert launch["article_evidence_urls"] == [
        "https://securityjournalamericas.com/the-nuclear-company-launches-integrated-cyber-physical-security-platform/"
    ]


def test_run_x_launches_surfaces_backend_forbidden_as_unavailable():
    from x_launches import run_x_launches

    result = run_x_launches(
        movements=[{"movement": "AI agent security", "market_sector": "Cybersecurity"}],
        env={"XAI_API_KEY": "xai-key"},
        query_runner=lambda **_kwargs: {
            "items": [],
            "warnings": ["Some sources failed: x"],
            "errors_by_source": {"x": "HTTP 403: Forbidden"},
        },
        limit=5,
    )

    assert result["launches"] == []
    assert result["status"] == "unavailable"
    assert "x: HTTP 403: Forbidden" in result["warnings"]
