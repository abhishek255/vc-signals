from __future__ import annotations


def _candidate():
    from radar_models import Candidate

    return Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        market_sector="Cybersecurity",
        source_lane="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )


def _signal():
    from radar_models import Signal

    return Signal(
        source="reddit",
        role="pain",
        title="How are teams controlling AI agent permissions?",
        url="https://reddit.com/r/cybersecurity/comments/1",
        sector="cybersecurity",
        text="MCP tools and AI agents are creating permission review headaches.",
        can_create_candidate=False,
    )


def test_build_source_digest_counts_sources_and_sectors():
    from radar_synthesis import build_source_digest

    digest = build_source_digest(candidates=[_candidate()], signals=[_signal()])

    assert digest["candidate_count"] == 1
    assert digest["signal_count"] == 1
    assert digest["source_lanes"] == {"OSS": 1}
    assert digest["market_sectors"] == {"Cybersecurity": 1}


def test_build_source_digest_counts_dict_artifact_candidates():
    from radar_synthesis import build_source_digest

    digest = build_source_digest(
        candidates=[{"source_lane": "OSS", "market_sector": "Cybersecurity"}],
        signals=[{"source": "reddit"}],
    )

    assert digest["source_lanes"] == {"OSS": 1}
    assert digest["market_sectors"] == {"Cybersecurity": 1}
    assert digest["signal_count"] == 1


def test_run_synthesis_without_provider_keys_returns_disabled_result(monkeypatch):
    import radar_synthesis

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(radar_synthesis, "SYNTHESIS_ENV_PATHS", ())

    result = radar_synthesis.run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=None,
    )

    assert result.enabled is False
    assert "Harness LLM synthesis handoff" in result.warnings[0]


def test_run_synthesis_auto_does_not_call_direct_api_without_explicit_opt_in(monkeypatch):
    import radar_synthesis

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("VC_SIGNALS_ALLOW_DIRECT_LLM_API", raising=False)
    monkeypatch.delenv("VC_SIGNALS_SYNTHESIS_PROVIDER", raising=False)
    monkeypatch.delenv("VC_SIGNALS_SYNTHESIS_MODEL", raising=False)
    monkeypatch.setattr(radar_synthesis, "SYNTHESIS_ENV_PATHS", ())

    def fail_provider(*_args, **_kwargs):
        raise AssertionError("direct LLM API should be disabled unless explicitly opted in")

    monkeypatch.setattr(radar_synthesis, "call_gemini_synthesis", fail_provider)
    monkeypatch.setattr(radar_synthesis, "call_openai_synthesis", fail_provider)

    result = radar_synthesis.run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
    )

    assert result.enabled is False
    assert result.model == "harness-llm"
    assert "Harness LLM synthesis handoff" in result.warnings[0]


def test_run_synthesis_auto_uses_gemini_before_openai_when_direct_api_opted_in(monkeypatch):
    import radar_synthesis

    seen = {}
    monkeypatch.setenv("VC_SIGNALS_ALLOW_DIRECT_LLM_API", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("VC_SIGNALS_SYNTHESIS_PROVIDER", raising=False)
    monkeypatch.delenv("VC_SIGNALS_SYNTHESIS_MODEL", raising=False)
    monkeypatch.setattr(radar_synthesis, "SYNTHESIS_ENV_PATHS", ())

    def fake_gemini(payload, *, model, api_key):
        seen.update({"provider": "gemini", "model": model, "api_key": api_key, "payload": payload})
        return {
            "sector_diagnoses": [],
            "theme_hypotheses": [],
            "possible_company_leads": [],
            "partner_notes": [],
            "warnings": [],
        }

    def fail_openai(*_args, **_kwargs):
        raise AssertionError("OpenAI should not be used when Gemini is available")

    monkeypatch.setattr(radar_synthesis, "call_gemini_synthesis", fake_gemini)
    monkeypatch.setattr(radar_synthesis, "call_openai_synthesis", fail_openai)

    result = radar_synthesis.run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
    )

    assert result.enabled is True
    assert result.model == "gemini-2.0-flash"
    assert seen["provider"] == "gemini"
    assert seen["api_key"] == "gemini-key"


def test_run_synthesis_can_load_gemini_key_from_env_file(tmp_path, monkeypatch):
    import radar_synthesis

    env_file = tmp_path / ".env"
    env_file.write_text("VC_SIGNALS_ALLOW_DIRECT_LLM_API=1\nGEMINI_API_KEY=gemini-from-file\n")
    seen = {}
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(radar_synthesis, "SYNTHESIS_ENV_PATHS", (env_file,))

    def fake_gemini(_payload, *, model, api_key):
        seen.update({"model": model, "api_key": api_key})
        return {"sector_diagnoses": [], "theme_hypotheses": [], "possible_company_leads": []}

    monkeypatch.setattr(radar_synthesis, "call_gemini_synthesis", fake_gemini)

    result = radar_synthesis.run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
    )

    assert result.enabled is True
    assert seen == {"model": "gemini-2.0-flash", "api_key": "gemini-from-file"}


def test_call_gemini_synthesis_parses_generate_content_json(monkeypatch):
    import io
    import json
    import radar_synthesis

    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "sector_diagnoses": [],
                                                "theme_hypotheses": [],
                                                "possible_company_leads": [],
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(radar_synthesis.request, "urlopen", fake_urlopen)

    result = radar_synthesis.call_gemini_synthesis({"source_digest": {}}, model="gemini-2.0-flash", api_key="key")

    assert result["possible_company_leads"] == []
    assert captured["url"].endswith("/v1beta/models/gemini-2.0-flash:generateContent")
    assert captured["headers"]["X-goog-api-key"] == "key"
    assert captured["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_run_synthesis_keeps_cited_items_from_fake_provider():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "sector_diagnoses": [
                {
                    "market_sector": "Cybersecurity",
                    "diagnosis": "OSS-heavy but relevant AI agent security signal.",
                    "evidence_urls": ["https://github.com/affaan-m/agentshield"],
                    "recommended_next_queries": ["AI agent security startup MCP permissions"],
                    "confidence": "Medium",
                }
            ],
            "theme_hypotheses": [
                {
                    "market_sector": "Cybersecurity",
                    "theme": "AI agent permission security",
                    "evidence_summary": "AgentShield and Reddit pain point to permission risk.",
                    "evidence_urls": [
                        "https://github.com/affaan-m/agentshield",
                        "https://reddit.com/r/cybersecurity/comments/1",
                    ],
                    "why_it_matters": "Agent tool use creates new security review surfaces.",
                    "why_this_may_be_noise": "Evidence is early and mostly OSS.",
                    "confidence": "Medium",
                }
            ],
            "possible_company_leads": [
                {
                    "name": "AgentShield",
                    "market_sector": "Cybersecurity",
                    "source_lane": "OSS",
                    "evidence_urls": ["https://github.com/affaan-m/agentshield"],
                    "why_on_radar": "Fast OSS momentum.",
                    "verification_needed": ["Confirm company formation"],
                    "suggested_action": "track company formation",
                    "confidence": "Medium",
                }
            ],
            "partner_notes": ["This run is OSS-heavy because grounded company discovery is unavailable."],
            "warnings": [],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
        model="fake-synthesis",
    )

    assert result.enabled is True
    assert result.model == "fake-synthesis"
    assert result.theme_hypotheses[0].theme == "AI agent permission security"
    assert result.possible_company_leads[0].name == "AgentShield"
    assert result.partner_notes[0] == "This synthesis run reviewed 1 candidate rows across 1 market sectors."
    assert result.partner_notes[1] == "This run is OSS-heavy; treat possible company leads as verification prompts."
    assert any("provider partner_notes" in warning.lower() for warning in result.warnings)


def test_run_synthesis_drops_freeform_provider_partner_notes():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "sector_diagnoses": [],
            "theme_hypotheses": [],
            "possible_company_leads": [],
            "partner_notes": ["MadeUpCo raised $10M and has 80 employees."],
            "warnings": [],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    rendered = repr(result.to_dict())
    assert "MadeUpCo" not in rendered
    assert "$10M" not in rendered
    assert result.partner_notes[0] == "This synthesis run reviewed 1 candidate rows across 1 market sectors."
    assert result.partner_notes[1] == "This run is OSS-heavy; treat possible company leads as verification prompts."
    assert any("provider partner_notes" in warning.lower() for warning in result.warnings)


def test_run_synthesis_drops_freeform_provider_warnings():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "sector_diagnoses": [],
            "theme_hypotheses": [],
            "possible_company_leads": [],
            "partner_notes": [],
            "warnings": ["MadeUpCo raised $10M and has 80 employees."],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    rendered = repr(result.to_dict())
    assert "MadeUpCo" not in rendered
    assert "$10M" not in rendered
    assert result.partner_notes[0] == "This synthesis run reviewed 1 candidate rows across 1 market sectors."
    assert any("provider warnings" in warning.lower() for warning in result.warnings)


def test_run_synthesis_drops_uncited_and_unknown_url_items():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "theme_hypotheses": [
                {
                    "market_sector": "Cybersecurity",
                    "theme": "Uncited theme",
                    "evidence_summary": "No citations.",
                    "evidence_urls": [],
                    "why_it_matters": "Cannot trust this.",
                    "why_this_may_be_noise": "",
                    "confidence": "High",
                },
                {
                    "market_sector": "Cybersecurity",
                    "theme": "Unknown URL theme",
                    "evidence_summary": "Unknown citation.",
                    "evidence_urls": ["https://made-up.example.com"],
                    "why_it_matters": "Cannot trust this.",
                    "why_this_may_be_noise": "",
                    "confidence": "High",
                },
            ],
            "possible_company_leads": [
                {
                    "name": "MadeUpCo",
                    "market_sector": "Cybersecurity",
                    "evidence_urls": ["https://made-up.example.com"],
                    "why_on_radar": "Invented.",
                    "verification_needed": [],
                    "suggested_action": "take meeting",
                    "confidence": "High",
                }
            ],
            "sector_diagnoses": [],
            "partner_notes": [],
            "warnings": [],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    assert result.theme_hypotheses == []
    assert result.possible_company_leads == []
    assert any("dropped" in warning.lower() for warning in result.warnings)


def test_run_synthesis_drops_raw_evidence_urls_not_present_in_prompt_payload():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "theme_hypotheses": [
                {
                    "market_sector": "Cybersecurity",
                    "theme": "Raw-only source should not validate",
                    "evidence_summary": "The provider cited a URL it never received.",
                    "evidence_urls": ["https://raw-only.example.com"],
                    "why_it_matters": "It would allow unsupported synthesis claims.",
                    "why_this_may_be_noise": "Citation is outside the prompt payload.",
                    "confidence": "High",
                }
            ],
            "sector_diagnoses": [],
            "possible_company_leads": [],
            "partner_notes": [],
            "warnings": [],
        }

    result = run_synthesis(
        evidence={"last30days": {"cybersecurity": {"items": [{"url": "https://raw-only.example.com"}]}}},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    assert result.theme_hypotheses == []
    assert any("unsupported theme" in warning.lower() for warning in result.warnings)


def test_run_synthesis_drops_malformed_provider_items_with_warning():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "theme_hypotheses": [{"evidence_urls": ["https://github.com/affaan-m/agentshield"]}],
            "sector_diagnoses": [],
            "possible_company_leads": [],
            "partner_notes": [],
            "warnings": [],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    assert result.enabled is True
    assert result.theme_hypotheses == []
    assert any("malformed theme" in warning.lower() for warning in result.warnings)


def test_run_synthesis_drops_non_string_citation_values_without_raising():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "theme_hypotheses": [
                {
                    "market_sector": "Cybersecurity",
                    "theme": "Bad URL",
                    "evidence_urls": [123],
                }
            ],
            "sector_diagnoses": [
                {
                    "market_sector": "Cybersecurity",
                    "diagnosis": "Bad URL",
                    "evidence_urls": [123],
                }
            ],
            "possible_company_leads": [
                {
                    "name": "BadCo",
                    "market_sector": "Cybersecurity",
                    "evidence_urls": [123],
                }
            ],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    assert result.theme_hypotheses == []
    assert result.sector_diagnoses == []
    assert result.possible_company_leads == []
    assert sum("dropped" in warning.lower() for warning in result.warnings) == 3


def test_run_synthesis_scrubs_secrets_from_provider_exception_warning():
    from radar_synthesis import run_synthesis

    secret = "OPENAI_API_" + "KEY=sk-proj-" + "abcdefghijklmnopqrstuvwxyz1234567890"

    def fake_provider(_payload):
        raise RuntimeError(f"provider failed with {secret}")

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    rendered = repr(result.warnings)
    assert result.enabled is False
    assert "sk-proj-" not in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert "[redacted]" in rendered


def test_run_synthesis_keeps_uncited_sector_diagnoses_but_drops_unknown_citations():
    from radar_synthesis import run_synthesis

    def fake_provider(_payload):
        return {
            "sector_diagnoses": [
                {
                    "market_sector": "Vertical AI",
                    "diagnosis": "Source failure / incomplete coverage",
                    "evidence_urls": [],
                    "recommended_next_queries": ["vertical AI workflow automation startup launch"],
                    "confidence": "High",
                },
                {
                    "market_sector": "Data Infra",
                    "diagnosis": "Cites a made-up source.",
                    "evidence_urls": ["https://made-up.example.com"],
                    "recommended_next_queries": ["data infra launch"],
                    "confidence": "High",
                },
            ],
            "theme_hypotheses": [],
            "possible_company_leads": [],
            "partner_notes": [],
            "warnings": [],
        }

    result = run_synthesis(
        evidence={},
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
        provider=fake_provider,
    )

    assert [item.market_sector for item in result.sector_diagnoses] == ["Vertical AI"]
    assert any("sector diagnosis" in warning.lower() for warning in result.warnings)


def test_prompt_payload_does_not_include_attio_secrets():
    from radar_synthesis import build_synthesis_payload

    attio_token_warning = "ATTIO_ACCESS_" + "TOKEN=secret"
    bearer_warning = "Bearer " + "abcdefghijklmnopqrstuvwxyz"
    payload = build_synthesis_payload(
        evidence={
            "warnings": ["ok", attio_token_warning, bearer_warning],
            "last30days": {"cybersecurity": {"items": [{"url": "https://example.com/secret"}]}},
        },
        signals=[_signal()],
        candidates=[_candidate()],
        sector_intelligence=[],
        theme_signals=[],
    )
    rendered = repr(payload)

    assert "ATTIO_ACCESS_TOKEN" not in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert bearer_warning not in rendered
    assert "https://example.com/secret" not in rendered
