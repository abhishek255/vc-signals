from __future__ import annotations

import json


def test_build_workbench_package_is_agent_native_and_verification_safe():
    from radar_models import Signal, ThemeSignal
    from radar_workbench import build_workbench_package

    signal = Signal(
        source="reddit",
        role="pain",
        title="How are teams controlling AI agent permissions?",
        url="https://reddit.com/r/cybersecurity/comments/1",
        sector="cybersecurity",
        text="MCP tools and AI agents are creating permission review headaches.",
        can_create_candidate=False,
    )
    theme = ThemeSignal(
        market_sector="Cybersecurity",
        theme="AI agent security",
        evidence_count=2,
        evidence_summary="Two practitioner threads mention MCP permission reviews.",
        suggested_search="AI agent security startups Seed Series A founder launch",
    )

    package = build_workbench_package(
        evidence={"warnings": ["grounded company discovery unavailable"]},
        signals=[signal],
        candidates=[],
        sector_intelligence=[],
        theme_signals=[theme],
    )

    assert package["mode"] == "agent_native_research_workbench"
    assert package["rules"]["never_write_to_candidates_json"] is True
    assert package["rules"]["possible_leads_require_verification"] is True
    assert package["source_digest"]["candidate_count"] == 0
    assert package["source_gaps"][0] == "grounded company discovery unavailable"
    assert package["next_searches"][0]["query"] == "AI agent security startups Seed Series A founder launch"
    assert package["next_searches"][0]["market_sector"] == "Cybersecurity"
    assert package["output_contract"]["artifact"] == "research-workbench.md"


def test_render_workbench_prompt_names_allowed_and_forbidden_outputs():
    from radar_workbench import render_workbench_prompt

    prompt = render_workbench_prompt(
        {
            "mode": "agent_native_research_workbench",
            "rules": {
                "never_write_to_candidates_json": True,
                "possible_leads_require_verification": True,
            },
            "source_digest": {"candidate_count": 0},
            "source_gaps": ["grounded company discovery unavailable"],
            "next_searches": [{"query": "AI agent security startups Seed Series A founder launch"}],
        }
    )

    assert "Use your own LLM reasoning" in prompt
    assert "Do not add rows to candidates.json" in prompt
    assert "Possible Companies Requiring Verification" in prompt
    assert "AI agent security startups Seed Series A founder launch" in prompt


def test_write_workbench_artifacts_reads_weekly_run_folder(tmp_path):
    from radar_workbench import write_workbench_artifacts

    run_dir = tmp_path / "run"
    output_dir = tmp_path / "workbench"
    run_dir.mkdir()
    (run_dir / "signals.json").write_text(
        json.dumps(
            [
                {
                    "source": "reddit",
                    "role": "pain",
                    "title": "How are teams controlling AI agent permissions?",
                    "url": "https://reddit.com/r/cybersecurity/comments/1",
                    "sector": "cybersecurity",
                    "text": "MCP permissions are hard.",
                    "can_create_candidate": False,
                }
            ]
        )
    )
    (run_dir / "candidates.json").write_text("[]")
    (run_dir / "theme-signals.json").write_text(
        json.dumps(
            [
                {
                    "market_sector": "Cybersecurity",
                    "theme": "AI agent security",
                    "evidence_count": 2,
                    "evidence_summary": "MCP permission reviews are painful.",
                    "suggested_search": "AI agent security startups Seed Series A founder launch",
                }
            ]
        )
    )
    (run_dir / "sector-intelligence.json").write_text("[]")
    (run_dir / "company-discovery.json").write_text('{"queries": [], "items": [], "warnings": [], "errors": []}')
    (run_dir / "2026-05-04-raw-evidence.json").write_text('{"warnings": ["grounded company discovery unavailable"]}')

    result = write_workbench_artifacts(run_dir=run_dir, output_dir=output_dir)

    assert result["package"].endswith("research-workbench-input.json")
    assert result["prompt"].endswith("research-workbench-prompt.md")
    package = json.loads((output_dir / "research-workbench-input.json").read_text())
    assert package["source_gaps"] == ["grounded company discovery unavailable"]
    prompt = (output_dir / "research-workbench-prompt.md").read_text()
    assert "Possible Companies Requiring Verification" in prompt
