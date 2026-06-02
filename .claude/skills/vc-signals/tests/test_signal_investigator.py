from __future__ import annotations

from radar_models import Candidate


def _candidate(**overrides) -> Candidate:
    payload = {
        "name": "Envio",
        "sector": "Devtools",
        "theme": "Devtools product launch",
        "source": "https://x.com/anton__dev/status/1",
        "sources": ["https://x.com/anton__dev/status/1"],
        "candidate_type": "social_launch",
        "source_lane": "X",
        "why_on_radar": "Just launched Envio on Product Hunt, a macOS menu bar app to manage .env files.",
        "why_this_may_be_noise": "Needs official identity evidence.",
        "missing_identity_evidence": ["no verified domain", "no founder or maintainer identity"],
    }
    payload.update(overrides)
    return Candidate(**payload)


def test_classify_url_role_separates_official_article_social_and_repo_urls():
    from signal_investigator import classify_url_role

    assert classify_url_role("https://envio.app/pricing")["role"] == "pricing"
    assert classify_url_role("https://docs.envio.app/start")["role"] == "docs"
    assert classify_url_role("http://localhost:8080/docs")["official_eligible"] is False
    assert classify_url_role("https://learn.microsoft.com/en-us/azure/sentinel/hunts")["official_eligible"] is False
    assert classify_url_role("https://management.azure.com/subscriptions/123")["official_eligible"] is False
    assert classify_url_role("https://securityjournalamericas.com/the-nuclear-company-launches")["role"] == "article"
    assert classify_url_role("https://x.com/anton__dev/status/1")["role"] == "social"
    assert classify_url_role("https://github.com/anton/envio")["role"] == "repo"
    assert classify_url_role("https://www.producthunt.com/products/envio-env-manager")["role"] == "product_hunt"
    assert classify_url_role("https://betalist.com/startups/marqly")["role"] == "directory"
    assert classify_url_role("https://crx4chrome.com/extensions/notebooklm-web-clipper")["role"] == "directory"
    assert classify_url_role("https://jeltedeproft.itch.io/colorcraft")["role"] == "directory"
    assert classify_url_role("https://filecr.com/windows/colorcraft")["role"] == "directory"
    assert classify_url_role("https://rocketreach.co/coffeepomodoro")["role"] == "directory"
    assert classify_url_role("https://cbinsights.com/company/hum")["role"] == "directory"
    assert classify_url_role("https://thenextweb.com/news/harness-starter-kit")["role"] == "article"
    assert classify_url_role("https://figma.com/community/plugin/123")["role"] == "directory"


def test_reconcile_blocks_directory_domains_and_short_partial_domain_matches():
    from signal_investigator import build_investigation_packet, reconcile_search_evidence

    marqly = reconcile_search_evidence(
        build_investigation_packet({"name": "Marqly 5.0"}),
        [{"title": "Marqly 5.0 on BetaList", "url": "https://betalist.com/startups/marqly", "snippet": "BetaList launch page."}],
    )
    pogkit = reconcile_search_evidence(
        build_investigation_packet({"name": "PogKit"}),
        [{"title": "PogKit", "url": "https://pog.com", "snippet": "PogKit screenshots."}],
    )
    drop = reconcile_search_evidence(
        build_investigation_packet({"name": "DROP"}),
        [{"title": "DROP launch", "url": "https://dropbox.com", "snippet": "DROP launched a new dropshipping app."}],
    )
    harness = reconcile_search_evidence(
        build_investigation_packet({"name": "Harness Starter Kit"}),
        [{"title": "Harness Starter Kit", "url": "https://thenextweb.com/news/harness-starter-kit", "snippet": "Coverage of the launch."}],
    )

    assert marqly["official_domain"] == ""
    assert marqly["unsafe_domain_attempts_blocked"] >= 1
    assert pogkit["official_domain"] == ""
    assert drop["official_domain"] == ""
    assert harness["official_domain"] == ""


def test_investigator_uses_llm_provider_search_plan_when_available():
    from signal_investigator import build_investigation_packet, build_search_plan

    calls = []

    def fake_provider(payload: dict) -> dict:
        calls.append(payload)
        return {
            "signal_type": "product_launch",
            "company_hypotheses": ["Envio", "Envio Env Manager"],
            "domain_hypotheses": ["envio.app", "getenvio.app"],
            "search_plan": [
                {
                    "query": '"Envio Env Manager" "anton__dev" official website',
                    "purpose": "official_domain",
                    "sources": "grounding",
                }
            ],
            "evidence_needed": ["official_domain", "founder"],
            "risk_flags": ["product_hunt_redirect_blocked"],
        }

    packet = build_investigation_packet(_candidate())
    plan = build_search_plan(packet, provider=fake_provider)

    assert calls
    assert plan["mode"] == "llm"
    assert plan["search_plan"][0]["query"] == '"Envio Env Manager" "anton__dev" official website'
    assert plan["company_hypotheses"] == ["Envio", "Envio Env Manager"]


def test_default_provider_uses_xai_when_live_and_configured(monkeypatch):
    import signal_investigator
    from signal_investigator import default_llm_provider

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"signal_type":"product_launch","company_hypotheses":["Envio"],'
                                '"domain_hypotheses":["envio.app"],'
                                '"search_plan":[{"query":"Envio official website","purpose":"official_domain","sources":"grounding"}],'
                                '"evidence_needed":["founder_team"],"risk_flags":[]}'
                            )
                        }
                    }
                ]
            }

    def fake_post(url, *, json, headers, timeout, params=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout, "params": params})
        return FakeResponse()

    monkeypatch.setattr(
        signal_investigator,
        "_merged_env",
        lambda: {"VC_SIGNALS_INVESTIGATOR_ENABLE_LIVE": "1", "XAI_API_KEY": "xai-secret"},
    )
    monkeypatch.setattr(signal_investigator.requests, "post", fake_post)

    result = default_llm_provider({"name": "Envio", "source_lane": "X", "candidate_type": "social_launch"})

    assert calls[0]["url"] == signal_investigator.XAI_CHAT_COMPLETIONS_URL
    assert calls[0]["json"]["model"] == signal_investigator.XAI_MODEL
    assert result["search_plan"][0]["query"] == "Envio official website"


def test_provider_error_redacts_secret_query_params():
    from signal_investigator import build_search_plan

    def failing_provider(_packet: dict) -> dict:
        raise RuntimeError("429 for https://example.com/model?key=super-secret-token")

    plan = build_search_plan({"name": "Envio"}, provider=failing_provider)

    assert plan["mode"] == "heuristic_fallback"
    assert "super-secret-token" not in plan["provider_error"]
    assert "key=<redacted>" in plan["provider_error"]


def test_investigator_fallback_generates_specific_queries_for_oss_repo():
    from signal_investigator import build_investigation_packet, build_search_plan

    packet = build_investigation_packet(
        _candidate(
            name="pullfrog/pullfrog",
            source="https://github.com/pullfrog/pullfrog",
            sources=["https://github.com/pullfrog/pullfrog"],
            candidate_type="oss_project",
            source_lane="OSS",
            why_on_radar="Open-source BYOK GitHub bot that runs in GitHub Actions.",
        )
    )

    plan = build_search_plan(packet)
    queries = [item["query"] for item in plan["search_plan"]]

    assert plan["mode"] == "heuristic_fallback"
    assert '"pullfrog" "pullfrog/pullfrog" official website founder company' in queries
    assert any("pricing docs customers careers" in query for query in queries)


def test_reconcile_search_evidence_keeps_article_as_evidence_not_domain():
    from signal_investigator import build_investigation_packet, reconcile_search_evidence

    packet = build_investigation_packet(
        _candidate(
            name="NOS Security",
            why_on_radar="The Nuclear Company launched NOS Security for nuclear infrastructure.",
        )
    )

    investigation = reconcile_search_evidence(
        packet,
        [
            {
                "title": "The Nuclear Company launches integrated cyber-physical security platform",
                "url": "https://securityjournalamericas.com/the-nuclear-company-launches-integrated-cyber-physical-security-platform/",
                "snippet": "The Nuclear Company has launched NOS Security.",
                "source": "grounding",
            }
        ],
    )

    assert investigation["official_domain"] == ""
    assert investigation["url_roles"][0]["role"] == "article"
    assert investigation["evidence_urls"] == [
        "https://securityjournalamericas.com/the-nuclear-company-launches-integrated-cyber-physical-security-platform/"
    ]
    assert investigation["unsafe_domain_attempts_blocked"] == 1


def test_reconcile_rejects_generic_launch_name_when_domain_context_does_not_match():
    from signal_investigator import build_investigation_packet, reconcile_search_evidence

    packet = build_investigation_packet(
        {
            "name": "Sentinel",
            "source_lane": "Product Hunt",
            "tagline": "Control your robots from anywhere in the world",
            "product_hunt_url": "https://www.producthunt.com/products/sentinel-10",
        }
    )

    investigation = reconcile_search_evidence(
        packet,
        [
            {
                "title": "SentinelOne Threat Hunting Championship",
                "url": "https://www.sentinelone.com/lp/threat-hunting-championship/",
                "snippet": "Threat hunting, endpoint security, and enterprise cyber defense.",
            },
            {
                "title": "Microsoft Sentinel hunting API",
                "url": "https://learn.microsoft.com/en-us/azure/sentinel/hunts",
                "snippet": "Microsoft Sentinel hunting rules and API docs.",
            },
        ],
    )

    assert investigation["official_domain"] == ""
    assert "domain_context_mismatch" in investigation["identity_risk_flags"]


def test_reconcile_treats_same_root_subdomains_as_one_company_candidate():
    from signal_investigator import build_investigation_packet, reconcile_search_evidence

    packet = build_investigation_packet(
        {
            "name": "Databox MCP",
            "source_lane": "Product Hunt",
            "tagline": "Create and update Databox data from AI tools",
        }
    )

    investigation = reconcile_search_evidence(
        packet,
        [
            {
                "title": "Databox MCP",
                "url": "https://mcp.databox.com/mcp",
                "snippet": "Databox MCP lets AI tools create and update Databox data.",
            },
            {
                "title": "Databox MCP docs",
                "url": "https://developers.databox.com/docs/mcp",
                "snippet": "Developer docs for Databox MCP.",
            },
            {
                "title": "Databox MCP",
                "url": "https://databox.com/mcp",
                "snippet": "Connect Databox to AI tools.",
            },
        ],
    )

    assert investigation["official_domain"] in {"databox.com", "mcp.databox.com", "developers.databox.com"}
    assert "ambiguous_official_domain_candidates" not in investigation["identity_risk_flags"]


def test_apply_investigation_sets_domain_only_from_backed_official_evidence():
    from signal_investigator import apply_investigation_to_candidate

    updated = apply_investigation_to_candidate(
        _candidate(),
        {
            "official_domain": "envio.app",
            "official_domain_confidence": 85,
            "official_url": "https://envio.app",
            "mode": "llm",
            "signal_type": "product_launch",
            "route": "evidence_gap",
            "founder_hints": ["https://x.com/anton__dev"],
            "evidence_urls": ["https://envio.app", "https://x.com/anton__dev/status/1"],
            "url_roles": [{"url": "https://envio.app", "role": "official_site", "domain": "envio.app"}],
            "evidence_needed": ["stage_funding_or_headcount_missing"],
        },
    )

    assert updated.domain == "envio.app"
    assert "signal_investigator_official_evidence" in updated.verified_domain_basis
    assert "signal_investigator" in updated.identity_resolved_from
    assert "https://envio.app" in updated.source_outbound_urls
    assert updated.weak_founder_team_hints == ["https://x.com/anton__dev"]
    assert updated.evidence_metadata[-1]["query_kind"] == "signal_investigation"


def test_source_row_investigation_covers_ph_hn_and_oss_seed_urls():
    from signal_investigator import investigate_source_rows

    queries = []

    def fake_provider(_packet: dict) -> dict:
        return {
            "signal_type": "product_launch",
            "company_hypotheses": [],
            "domain_hypotheses": [],
            "search_plan": [{"query": "official website", "purpose": "official_domain", "sources": "grounding"}],
            "evidence_needed": ["official_domain"],
            "risk_flags": [],
        }

    def fake_query_runner(*args, **kwargs):
        queries.append(args[0] if args else kwargs["topic"])
        return {"items": []}

    report = investigate_source_rows(
        [
            {"source": "producthunt", "name": "AgentFence", "url": "https://www.producthunt.com/products/agentfence"},
            {"source": "github", "full_name": "pullfrog/pullfrog", "url": "https://github.com/pullfrog/pullfrog"},
            {"source": "hackernews", "title": "Launch HN: AgentFence", "url": "https://news.ycombinator.com/item?id=1"},
        ],
        query_runner=fake_query_runner,
        provider=fake_provider,
        max_rows_per_lane=2,
        max_queries_per_row=1,
    )

    assert report["summary"]["provider_mode"] == "llm"
    assert report["summary"]["rows_investigated"] == 3
    assert report["summary"]["search_queries_run"] == 3
    assert report["summary"]["url_roles_classified"] == 3
    assert sorted(item["source_lane"] for item in report["items"]) == ["Hacker News", "OSS", "Product Hunt"]
    assert queries == ["official website", "official website", "official website"]
