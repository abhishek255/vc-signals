from __future__ import annotations

import json
from pathlib import Path

from radar_synthesis import build_synthesis_payload


WORKBENCH_INPUT = "research-workbench-input.json"
WORKBENCH_PROMPT = "research-workbench-prompt.md"


def build_workbench_package(
    *,
    evidence: dict,
    signals: list,
    candidates: list,
    sector_intelligence: list,
    theme_signals: list,
    company_discovery: dict | None = None,
) -> dict:
    """Build an agent-native evidence pack for Codex/Claude research synthesis."""
    payload = build_synthesis_payload(
        evidence=evidence,
        signals=signals,
        candidates=candidates,
        sector_intelligence=sector_intelligence,
        theme_signals=theme_signals,
    )
    return {
        "mode": "agent_native_research_workbench",
        "rules": {
            "never_write_to_candidates_json": True,
            "possible_leads_require_verification": True,
            "use_only_supplied_evidence_for_facts": True,
            "do_not_invent_domains_funding_headcount_founders_or_customers": True,
        },
        "output_contract": {
            "artifact": "research-workbench.md",
            "allowed_sections": [
                "Partner Notes",
                "Source Gap Diagnosis",
                "Theme Hypotheses",
                "Possible Companies Requiring Verification",
                "Recommended Next Searches",
            ],
        },
        "source_digest": payload["source_digest"],
        "source_gaps": _source_gaps(evidence=evidence, company_discovery=company_discovery),
        "next_searches": _next_searches(theme_signals),
        "company_discovery": company_discovery or {"queries": [], "items": [], "warnings": [], "errors": []},
        "synthesis_payload": payload,
    }


def render_workbench_prompt(package: dict) -> str:
    searches = package.get("next_searches", [])
    search_lines = "\n".join(f"- {item.get('query', '')}" for item in searches) or "- No next searches generated."
    gaps = "\n".join(f"- {item}" for item in package.get("source_gaps", [])) or "- No explicit source gaps found."
    return (
        "# VC Signals Research Workbench\n\n"
        "Use your own LLM reasoning to synthesize the supplied evidence into a research workbench. "
        "This is a verification artifact, not the canonical weekly radar.\n\n"
        "## Hard Rules\n\n"
        "- Do not add rows to candidates.json.\n"
        "- Do not claim a company, domain, funding, headcount, founder, customer, or stage unless it appears in supplied evidence.\n"
        "- Treat possible company names as leads requiring verification unless they already have a credible supplied URL.\n"
        "- Separate facts, inferences, assumptions, open questions, and recommended searches.\n\n"
        "## Required Output Sections\n\n"
        "1. Partner Notes\n"
        "2. Source Gap Diagnosis\n"
        "3. Theme Hypotheses\n"
        "4. Possible Companies Requiring Verification\n"
        "5. Recommended Next Searches\n\n"
        "## Current Source Gaps\n\n"
        f"{gaps}\n\n"
        "## Suggested Next Searches\n\n"
        f"{search_lines}\n\n"
        "## Evidence Pack\n\n"
        "The companion JSON file is `research-workbench-input.json`. Use it as the only factual source.\n"
    )


def write_workbench_artifacts(*, run_dir: Path, output_dir: Path | None = None) -> dict:
    run_dir = Path(run_dir)
    output_dir = Path(output_dir) if output_dir else run_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence = _read_raw_evidence(run_dir)
    signals = _read_json(run_dir / "signals.json", [])
    candidates = _read_json(run_dir / "candidates.json", [])
    sector_intelligence = _read_json(run_dir / "sector-intelligence.json", [])
    theme_signals = _read_json(run_dir / "theme-signals.json", [])
    company_discovery = _read_json(run_dir / "company-discovery.json", {"queries": [], "items": [], "warnings": [], "errors": []})

    package = build_workbench_package(
        evidence=evidence,
        signals=signals,
        candidates=candidates,
        sector_intelligence=sector_intelligence,
        theme_signals=theme_signals,
        company_discovery=company_discovery,
    )
    package_path = output_dir / WORKBENCH_INPUT
    prompt_path = output_dir / WORKBENCH_PROMPT
    package_path.write_text(json.dumps(package, indent=2))
    prompt_path.write_text(render_workbench_prompt(package))
    return {"package": str(package_path), "prompt": str(prompt_path)}


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _read_raw_evidence(run_dir: Path) -> dict:
    candidates = sorted(run_dir.glob("*-raw-evidence.json"))
    if candidates:
        return _read_json(candidates[-1], {})
    return _read_json(run_dir / "raw-evidence.json", {})


def _source_gaps(*, evidence: dict, company_discovery: dict | None) -> list[str]:
    gaps = []
    for warning in evidence.get("warnings", []):
        if isinstance(warning, str):
            gaps.append(warning)
    discovery = company_discovery or {}
    for key in ("warnings", "errors"):
        for item in discovery.get(key, []):
            if isinstance(item, str):
                gaps.append(item)
    return list(dict.fromkeys(gaps))


def _next_searches(theme_signals: list) -> list[dict]:
    searches = []
    for item in theme_signals:
        payload = item.to_dict() if hasattr(item, "to_dict") else item
        if not isinstance(payload, dict):
            continue
        query = payload.get("suggested_search")
        if query:
            searches.append(
                {
                    "query": query,
                    "market_sector": payload.get("market_sector", ""),
                    "theme": payload.get("theme", ""),
                    "reason": payload.get("why_no_company_yet", ""),
                }
            )
    return searches
