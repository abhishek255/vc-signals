#!/usr/bin/env python3
"""Manual/high-value enrichment target report for top candidates."""

from __future__ import annotations

import json
from pathlib import Path

from radar_models import Candidate


TARGET_ACTIONS = {"assign owner", "research deeper", "watch", "contact maintainer"}


def _missing_evidence(candidate: Candidate) -> list[str]:
    missing = []
    if not candidate.company_linkedin:
        missing.append("company_linkedin_missing")
    if not candidate.founder_profiles and not candidate.founders and not candidate.founder_team_evidence:
        missing.append("founder_team_missing")
    if not candidate.headcount:
        missing.append("headcount_missing")
    if not candidate.stage and not candidate.raised and not candidate.stage_funding_evidence:
        missing.append("stage_or_funding_missing")
    return missing


def _manual_sources(missing: list[str]) -> list[str]:
    sources = []
    if "company_linkedin_missing" in missing or "founder_team_missing" in missing or "headcount_missing" in missing:
        sources.append("LinkedIn")
    if any(item in missing for item in ("founder_team_missing", "headcount_missing", "stage_or_funding_missing")):
        sources.append("Crunchbase/Coresignal/PDL/Dealroom/Apollo-Clay")
    return sources


def _is_high_value_manual_candidate(candidate: Candidate, missing: list[str]) -> bool:
    if not candidate.domain:
        return False
    if not missing:
        return False
    if candidate.category_anchor or candidate.action.lower() in {"monitor only", "map ecosystem"}:
        return False
    if candidate.action.lower() in TARGET_ACTIONS:
        return True
    return candidate.tier in {"Partner Review", "Watchlist"} or candidate.owner_readiness_score >= 60


def _manual_priority(candidate: Candidate, missing: list[str]) -> tuple:
    action_rank = {
        "assign owner": 5,
        "research deeper": 4,
        "watch": 3,
        "contact maintainer": 2,
    }.get(candidate.action.lower(), 1)
    tier_rank = {
        "Partner Review": 4,
        "Watchlist": 3,
        "Needs More Evidence": 2,
    }.get(candidate.tier, 1)
    source_rank = 2 if candidate.source_lane in {"HN", "Product Hunt", "YC Directory", "X", "Grounded web"} else 1
    gap_rank = sum(
        {
            "company_linkedin_missing": 2,
            "founder_team_missing": 4,
            "headcount_missing": 1,
            "stage_or_funding_missing": 4,
        }.get(gap, 1)
        for gap in missing
    )
    return (
        action_rank,
        tier_rank,
        candidate.owner_readiness_score,
        candidate.partner_priority_score,
        candidate.investment_interest_score,
        candidate.evidence_confidence_score,
        source_rank,
        gap_rank,
    )


def build_manual_enrichment_targets(candidates: list[Candidate], *, limit: int = 10) -> dict:
    scored = []
    excluded_complete_or_low_value = 0
    for candidate in candidates:
        missing = _missing_evidence(candidate)
        if _is_high_value_manual_candidate(candidate, missing):
            scored.append((candidate, missing, _manual_priority(candidate, missing)))
        else:
            excluded_complete_or_low_value += 1
    ranked = sorted(scored, key=lambda item: item[2], reverse=True)[:limit]
    items = []
    for candidate, missing, priority in ranked:
        items.append(
            {
                "name": candidate.name,
                "domain": candidate.domain,
                "tier": candidate.tier,
                "action": candidate.action,
                "lead_route": candidate.lead_route,
                "investment_interest_score": candidate.investment_interest_score,
                "evidence_confidence_score": candidate.evidence_confidence_score,
                "company_linkedin": candidate.company_linkedin,
                "company_x": candidate.company_x,
                "founder_profiles": list(candidate.founder_profiles),
                "founders": list(candidate.founders),
                "headcount": candidate.headcount,
                "stage": candidate.stage,
                "raised": candidate.raised,
                "owner_readiness_score": candidate.owner_readiness_score,
                "partner_priority_score": candidate.partner_priority_score,
                "manual_priority_score": sum(int(value or 0) for value in priority),
                "manual_sources": _manual_sources(missing),
                "missing_evidence": missing,
                "target_reason": "High-value row with official domain and concrete missing evidence.",
                "recommended_next_step": candidate.recommended_next_validation_step
                or "Manual enrichment only for high-value candidates; do not promote to Assign Owner without durable evidence.",
            }
        )
    return {
        "summary": {
            "targets": len(items),
            "with_missing_linkedin": sum(1 for item in items if "company_linkedin_missing" in item["missing_evidence"]),
            "with_missing_founder_team": sum(1 for item in items if "founder_team_missing" in item["missing_evidence"]),
            "with_missing_stage_or_funding": sum(1 for item in items if "stage_or_funding_missing" in item["missing_evidence"]),
            "excluded_complete_or_low_value": excluded_complete_or_low_value,
            "selection_policy": "Domain required; concrete missing evidence required; category/context rows excluded; ranked by action, tier, owner readiness, partner priority, and evidence scores.",
        },
        "items": items,
    }


def write_manual_enrichment_targets_json(report: dict, output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
