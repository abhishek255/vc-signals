from __future__ import annotations

import re

from radar_models import Candidate, FocusItem


ACTION_ASSIGN_OWNER = "Assign owner"
ACTION_RESEARCH_DEEPER = "Research deeper"
ACTION_REFRESH_ATTIO = "Refresh Attio"
ACTION_TAKE_MEETING = "Take meeting"
ACTION_MONITOR_ONLY = "Monitor only"

ATTIO_NEW_STATUSES = {"no_match", "not_found", "new"}
ATTIO_UNKNOWN_STATUSES = {"unknown", ""}
ATTIO_NO_OWNER_STATUSES = {"no_owner", "no owner"}
ATTIO_STALE_TERMS = ("stale", "passed")


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))


def _stable_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "unknown"


def score_company_identity(candidate: Candidate) -> tuple[int, list[str], list[str]]:
    basis = []
    missing = []
    score = 20

    if candidate.domain:
        score = max(score, 80)
        basis.append("domain_present")
    else:
        missing.append("no verified company domain")

    if candidate.company_linkedin:
        score = max(score, 80)
        basis.append("company_linkedin_present")

    if candidate.founder_profiles or candidate.founders or candidate.maintainer_profiles:
        score = max(score, 60)
        basis.append("founder_or_maintainer_identity_present")
    else:
        missing.append("no founder identity")

    sources = [source for source in candidate.sources if source]
    if sources:
        basis.append("evidence_urls_present")
    if any("ycombinator.com" in source or "launch" in source.lower() or "show hn" in source.lower() for source in sources):
        score = max(score, 80)
        basis.append("launch_source_present")

    if candidate.attio_status and candidate.attio_status.lower() not in ATTIO_UNKNOWN_STATUSES:
        score = max(score, 70)
        basis.append("attio_status_present")

    if candidate.candidate_type == "oss_project":
        if candidate.maintainer_profiles or candidate.oss_company_formation_score >= 50:
            score = max(score, 60)
            basis.append("oss_project_with_company_formation_signal")
        else:
            score = min(score, 40)
            basis.append("oss_project_commercial_intent_unclear")

    if score <= 20:
        basis.append("inferred_name_only")

    return _clamp(score), basis, missing


def score_actionability(candidate: Candidate, identity_score: int) -> tuple[int, list[str]]:
    basis = []
    score = 35
    status = (candidate.attio_status or "unknown").lower()
    staleness = " ".join([candidate.attio_staleness_reason or "", candidate.attio_action or ""]).lower()

    if status in ATTIO_NEW_STATUSES and identity_score >= 60:
        score += 25
        basis.append("new_to_attio")
    elif status in ATTIO_UNKNOWN_STATUSES:
        basis.append("attio_unknown_not_new")
    if "stale" in staleness or "stale" in status:
        score += 20
        basis.append("attio_stale_with_new_signal")
    if "no owner" in staleness or status in ATTIO_NO_OWNER_STATUSES:
        score += 15
        basis.append("attio_no_owner")
    if "passed" in status or "passed" in staleness:
        score += 10
        basis.append("passed_with_new_signal")
    if candidate.founder_profiles or candidate.maintainer_profiles:
        score += 10
        basis.append("clear_founder_to_investigate")
    if identity_score < 40:
        score -= 20
        basis.append("no_company_identity")
    if not basis:
        basis.append("baseline_actionability")

    return _clamp(score), basis


def score_freshness(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 40
    tag = (candidate.weekly_tag or "").upper()
    if tag == "NEW":
        score += 35
        basis.append("weekly_tag_new")
    elif tag in {"RETURNING", "CHANGED"}:
        score += 25
        basis.append(f"weekly_tag_{tag.lower()}")
    elif tag == "PERSISTENT":
        score += 10
        basis.append("weekly_tag_persistent")
    if candidate.stars_30d >= 100:
        score += 15
        basis.append("high_oss_star_velocity")
    if not basis:
        basis.append("no_strong_freshness_signal")
    return _clamp(score), basis


def score_marathon_fit(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 45
    sector = (candidate.market_sector or candidate.sector or "").lower()
    target_terms = ("devtools", "cybersecurity", "ai infra", "vertical ai", "data infra", "oss")
    if any(term in sector for term in target_terms):
        score += 25
        basis.append("target_sector")
    if candidate.stage and any(stage in candidate.stage.lower() for stage in ("seed", "series a", "series b", "pre-seed")):
        score += 20
        basis.append("seed_to_series_b_stage")
    elif not candidate.stage:
        score += 10
        basis.append("stage_unknown_but_not_disqualifying")
    if candidate.domain:
        score += 10
        basis.append("actionable_company_context")
    elif candidate.attio_status and candidate.attio_status.lower() not in ATTIO_UNKNOWN_STATUSES:
        score += 10
        basis.append("actionable_attio_context")
    text = " ".join([candidate.name, candidate.why_on_radar, candidate.theme]).lower()
    if any(term in text for term in ("consumer", "prosumer", "creator")):
        score -= 20
        basis.append("possible_consumer_or_prosumer_fit_risk")
    if any(term in text for term in ("series c", "series d", "unicorn", "$1b")):
        score -= 25
        basis.append("likely_late_or_consensus")
    return _clamp(score), basis or ["baseline_marathon_fit"]


def score_noise_risk(candidate: Candidate, identity_score: int) -> tuple[int, list[str]]:
    basis = []
    score = 35
    text = " ".join([candidate.why_on_radar, candidate.why_this_may_be_noise, candidate.theme]).lower()
    if identity_score < 60:
        score += 25
        basis.append("weak_company_identity")
    if candidate.candidate_type == "oss_project" and candidate.oss_company_formation_score < 50:
        score += 15
        basis.append("oss_commercialization_unclear")
    if "hype" in text or "crowded" in text:
        score += 15
        basis.append("explicit_hype_or_crowding_risk")
    if not candidate.sources:
        score += 20
        basis.append("no_evidence_url")
    return _clamp(score), basis or ["baseline_noise_risk"]


def score_consensus_risk(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 20
    text = " ".join([candidate.stage, candidate.raised, candidate.headcount, candidate.why_on_radar]).lower()
    if any(term in text for term in ("series c", "series d", "series e")):
        score += 40
        basis.append("series_c_or_later")
    if any(term in text for term in ("unicorn", "$1b", "$100m", "$200m")):
        score += 30
        basis.append("large_funding_or_valuation_signal")
    if "consensus" in text or "top-tier" in text:
        score += 20
        basis.append("consensus_chatter")
    if candidate.attio_status and candidate.attio_status.lower() in {"active", "passed"}:
        score += 10
        basis.append(f"attio_{candidate.attio_status.lower()}")
    return _clamp(score), basis or ["low_consensus_signal"]


def score_market_movement(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 45
    if candidate.theme:
        score += 15
        basis.append("theme_present")
    if candidate.source_count >= 2:
        score += 15
        basis.append("multiple_sources")
    if candidate.market_sector:
        score += 10
        basis.append("market_sector_classified")
    return _clamp(score), basis or ["baseline_market_movement"]


def compute_focus_priority(
    *,
    investment_interest_score: int,
    actionability_score: int,
    freshness_score: int,
    market_movement_score: int,
    marathon_fit_score: int,
    evidence_confidence_score: int,
    noise_risk_score: int,
    consensus_risk_score: int,
) -> tuple[int, list[str]]:
    score = (
        0.25 * investment_interest_score
        + 0.20 * actionability_score
        + 0.15 * freshness_score
        + 0.15 * market_movement_score
        + 0.15 * marathon_fit_score
        + 0.10 * evidence_confidence_score
        - 0.20 * noise_risk_score
        - 0.15 * consensus_risk_score
    )
    return _clamp(round(score)), ["focus_formula_v1"]


def can_take_meeting(item: FocusItem) -> bool:
    return (
        item.evidence_confidence_score >= 75
        and item.company_identity_quality_score >= 80
        and item.actionability_score >= 75
        and item.noise_risk_score <= 40
        and item.attio_status.lower() not in ATTIO_UNKNOWN_STATUSES
        and not (item.attio_status.lower() == "active" and item.attio_owner)
    )


def choose_recommended_action(candidate: Candidate, item: FocusItem) -> str:
    status = (candidate.attio_status or "unknown").lower()
    staleness = " ".join([candidate.attio_staleness_reason or "", candidate.attio_action or ""]).lower()
    if can_take_meeting(item):
        return ACTION_TAKE_MEETING
    if "stale" in status or "stale" in staleness or "passed" in status or "passed" in staleness:
        return ACTION_REFRESH_ATTIO
    if item.company_identity_quality_score < 60 or item.evidence_confidence_score < 45:
        return ACTION_RESEARCH_DEEPER
    if status in ATTIO_NEW_STATUSES or status in ATTIO_NO_OWNER_STATUSES:
        return ACTION_ASSIGN_OWNER
    if status in ATTIO_UNKNOWN_STATUSES:
        if item.company_identity_quality_score >= 60 and item.evidence_confidence_score >= 45:
            return ACTION_RESEARCH_DEEPER
        return ACTION_MONITOR_ONLY
    return ACTION_MONITOR_ONLY


def is_partner_focus_eligible(item: FocusItem) -> bool:
    return (
        item.company_identity_quality_score >= 60
        and len(item.evidence_urls) > 0
        and "pure_llm_inferred" not in item.focus_priority_basis
        and item.noise_risk_score < 70
        and bool(item.recommended_action)
        and (
            bool(item.company_domain)
            or bool(item.project_url)
            or item.attio_status.lower() in {"no_match", "not_found", "new", "no_owner", "stale", "passed"}
        )
        and not (item.recommended_action == ACTION_MONITOR_ONLY and item.focus_priority_score < 85)
    )
