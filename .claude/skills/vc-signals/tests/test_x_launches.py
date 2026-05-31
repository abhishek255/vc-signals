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

    assert [call["sources"] for call in calls] == ["x", "web"]
    assert result["launches"][0]["domain"] == "agentforge.dev"
    assert result["launches"][0]["domain_resolution_source"] == "web_fallback"
    assert "official_domain_identity_not_confirmed" not in result["launches"][0]["missing_evidence"]


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

    assert [call["sources"] for call in calls] == ["x"]
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
