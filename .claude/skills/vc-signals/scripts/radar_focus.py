from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from radar_models import (
    AlexFeedback,
    Candidate,
    ExecutiveSnapshot,
    FocusItem,
    MarketMovement,
    SectorIntelligence,
    ThemeSignal,
    WeeklyFocusArtifact,
)


ACTION_ASSIGN_OWNER = "Assign owner"
ACTION_RESEARCH_DEEPER = "Research deeper"
ACTION_REFRESH_ATTIO = "Refresh Attio"
ACTION_TAKE_MEETING = "Take meeting"
ACTION_MONITOR_ONLY = "Monitor only"
LEAD_ROUTE_CATEGORY_CONTEXT = "category_context"
LEAD_ROUTE_MONITOR_ONLY = "monitor_only"

ATTIO_NEW_STATUSES = {"no_match", "not_found", "new"}
ATTIO_UNKNOWN_STATUSES = {"unknown", ""}
ATTIO_NO_OWNER_STATUSES = {"no_owner", "no owner"}
ATTIO_MATCH_STATUSES = {"active", "no_owner", "no owner", "stale", "passed"}
ATTIO_STALE_TERMS = ("stale", "passed")


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))


def _stable_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "unknown"


def _text_blob(*values: object) -> str:
    return " ".join(str(value) for value in values if value is not None).lower()


def score_company_identity(candidate: Candidate) -> tuple[int, list[str], list[str]]:
    if candidate.identity_confidence_score:
        score = candidate.identity_confidence_score
        basis = [f"identity_resolution_{candidate.identity_type or 'unknown'}"]
        missing = list(candidate.missing_identity_evidence or [])
        if candidate.identity_type == "verified_company" and candidate.domain:
            score = max(score, 85)
            basis.append("resolved_verified_domain")
        elif candidate.identity_type == "oss_with_commercial_intent":
            score = max(score, 65)
            basis.append("resolved_oss_commercial_intent")
        elif candidate.identity_type in {"oss_project_watch", "insufficient_identity"}:
            score = min(score, 45)
            basis.append("identity_resolution_weak")
        return _clamp(score), basis, missing

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

    status = (candidate.attio_status or "unknown").lower()
    if status in ATTIO_MATCH_STATUSES:
        score = max(score, 70)
        basis.append("attio_status_present")

    if len((candidate.name or "").strip()) <= 2 and not candidate.domain and "/" not in (candidate.name or ""):
        score = min(score, 40)
        basis.append("weak_candidate_name")
        missing.append("weak candidate name")

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
    if candidate.category_anchor or candidate.lead_route in {LEAD_ROUTE_CATEGORY_CONTEXT, LEAD_ROUTE_MONITOR_ONLY}:
        score -= 35
        basis.append("category_context_not_sourcing_lead")
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
    if any(term in text for term in ("epic games", "free titles", "freebies", "captcha solving")):
        score += 55
        basis.append("consumer_gaming_automation")
    if not candidate.sources:
        score += 20
        basis.append("no_evidence_url")
    return _clamp(score), basis or ["baseline_noise_risk"]


def score_consensus_risk(candidate: Candidate) -> tuple[int, list[str]]:
    basis = []
    score = 20
    text = _text_blob(candidate.stage, candidate.raised, candidate.headcount, candidate.why_on_radar)
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
    if candidate.maturity_status in {"likely_too_late", "acquired"}:
        score += 60
        basis.extend(candidate.maturity_basis or [candidate.maturity_status])
    if candidate.category_anchor:
        score += 25
        basis.append("category_anchor")
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
    if candidate.category_anchor or candidate.lead_route in {LEAD_ROUTE_CATEGORY_CONTEXT, LEAD_ROUTE_MONITOR_ONLY}:
        return ACTION_MONITOR_ONLY
    if can_take_meeting(item):
        return ACTION_TAKE_MEETING
    if candidate.recommended_identity_action in {
        ACTION_ASSIGN_OWNER,
        ACTION_REFRESH_ATTIO,
        ACTION_RESEARCH_DEEPER,
        ACTION_MONITOR_ONLY,
    }:
        if candidate.recommended_identity_action == ACTION_ASSIGN_OWNER:
            if item.company_identity_quality_score >= 70 and item.evidence_confidence_score >= 45:
                return ACTION_ASSIGN_OWNER
        elif candidate.recommended_identity_action == ACTION_REFRESH_ATTIO:
            return ACTION_REFRESH_ATTIO
        elif candidate.recommended_identity_action == ACTION_RESEARCH_DEEPER:
            return ACTION_RESEARCH_DEEPER
        elif candidate.recommended_identity_action == ACTION_MONITOR_ONLY:
            return ACTION_MONITOR_ONLY
    if "stale" in status or "stale" in staleness or "passed" in status or "passed" in staleness:
        return ACTION_REFRESH_ATTIO
    if item.company_identity_quality_score < 60 or item.evidence_confidence_score < 45:
        return ACTION_RESEARCH_DEEPER
    if status in ATTIO_NEW_STATUSES or status in ATTIO_NO_OWNER_STATUSES:
        if not candidate.attio_safe_to_match or candidate.identity_type != "verified_company":
            return ACTION_RESEARCH_DEEPER
        return ACTION_ASSIGN_OWNER
    if status in ATTIO_UNKNOWN_STATUSES:
        if item.company_identity_quality_score >= 60 and item.evidence_confidence_score >= 45:
            return ACTION_RESEARCH_DEEPER
        return ACTION_MONITOR_ONLY
    return ACTION_MONITOR_ONLY


def is_partner_focus_eligible(item: FocusItem) -> bool:
    if item.category_anchor or item.lead_route in {LEAD_ROUTE_CATEGORY_CONTEXT, LEAD_ROUTE_MONITOR_ONLY}:
        return False
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


def _market_sector(candidate: Candidate) -> str:
    return candidate.market_sector or candidate.sector or "Unclassified"


def _source_urls(candidate: Candidate) -> list[str]:
    urls = [source for source in candidate.sources if source and source.startswith(("http://", "https://"))]
    if candidate.source and candidate.source.startswith(("http://", "https://")):
        urls.append(candidate.source)
    return list(dict.fromkeys(urls))


def _project_url(candidate: Candidate) -> str:
    for url in _source_urls(candidate):
        if "github.com" in url:
            return url
    return ""


def _has_ai_agent_security_evidence(candidate: Candidate) -> bool:
    text = _text_blob(
        candidate.name,
        candidate.why_on_radar,
        candidate.why_this_may_be_noise,
        candidate.source_lane,
    )
    return any(
        term in text
        for term in (
            "ai agent",
            "agent security",
            "mcp",
            "tool permission",
            "tool permissions",
            "runtime security for ai agents",
            "coding agent",
            "autonomous agent",
        )
    )


def _sector_fallback_movement(candidate: Candidate) -> str:
    sector = _market_sector(candidate)
    text = _text_blob(candidate.name, candidate.why_on_radar, candidate.theme)
    if sector == "Devtools":
        if any(term in text for term in ("security", "compliance", "static analyzer", "scanner")):
            return "Devtools security/compliance tooling"
        if any(term in text for term in ("github actions", "ci/cd", "ci ", "build pipeline", "yaml")):
            return "Devtools workflow automation"
        return "Devtools OSS workflow tooling"
    if sector == "Cybersecurity":
        return "Cybersecurity tooling"
    if sector == "AI Infra":
        return "AI infrastructure tooling"
    if sector == "Vertical AI":
        return "Vertical AI workflow automation"
    if sector == "Data Infra":
        return "Data infrastructure tooling"
    if sector == "OSS":
        return "OSS company-formation watchlist"
    return f"{sector} tooling" if sector and sector != "Unclassified" else "Unclassified technical tooling"


def _movement_name(candidate: Candidate) -> str:
    theme = candidate.theme or ""
    if theme == "Emerging technical signal":
        return _sector_fallback_movement(candidate)
    if theme == "AI agent security" and not _has_ai_agent_security_evidence(candidate):
        return _sector_fallback_movement(candidate)
    return theme or _sector_fallback_movement(candidate)


def _movement_id(candidate: Candidate) -> str:
    return _stable_id(f"{_market_sector(candidate)}-{_movement_name(candidate)}")


def _talker_types(candidate: Candidate) -> tuple[list[str], str, list[str]]:
    if candidate.founder_profiles:
        return ["founder"], "Medium", ["founder/company evidence"]
    if candidate.maintainer_profiles or candidate.candidate_type == "oss_project":
        return ["oss_maintainer"], "Medium", ["OSS maintainer/project evidence"]
    if candidate.source_lane in {"Reddit", "Hacker News"}:
        return ["practitioner"], "Medium", [candidate.source_lane]
    return ["unknown"], "Low", ["actor unclear"]


def build_focus_item(candidate: Candidate) -> FocusItem:
    identity_score, identity_basis, missing = score_company_identity(candidate)
    actionability_score, actionability_basis = score_actionability(candidate, identity_score)
    freshness_score, freshness_basis = score_freshness(candidate)
    movement_score, movement_basis = score_market_movement(candidate)
    marathon_fit_score, marathon_fit_basis = score_marathon_fit(candidate)
    noise_score, noise_basis = score_noise_risk(candidate, identity_score)
    consensus_score, consensus_basis = score_consensus_risk(candidate)
    focus_score, focus_basis = compute_focus_priority(
        investment_interest_score=candidate.investment_interest_score,
        actionability_score=actionability_score,
        freshness_score=freshness_score,
        market_movement_score=movement_score,
        marathon_fit_score=marathon_fit_score,
        evidence_confidence_score=candidate.evidence_confidence_score,
        noise_risk_score=noise_score,
        consensus_risk_score=consensus_score,
    )
    talker_types, talker_confidence, who_is_talking = _talker_types(candidate)
    urls = _source_urls(candidate)
    movement_id = _movement_id(candidate)
    item = FocusItem(
        id=candidate.stable_key or _stable_id(candidate.name),
        name=candidate.name,
        company_domain=candidate.domain,
        project_url=_project_url(candidate),
        market_movement_id=movement_id,
        market_movement=_movement_name(candidate),
        market_sector=_market_sector(candidate),
        why_focus_this_week=candidate.why_on_radar,
        who_is_talking=who_is_talking,
        talker_types=talker_types,
        talker_type_confidence=talker_confidence,
        evidence_snapshot=[candidate.why_on_radar] if candidate.why_on_radar else [],
        evidence_urls=urls,
        missing_evidence=missing,
        attio_status=candidate.attio_status,
        attio_owner=candidate.attio_owner,
        attio_last_touch=candidate.attio_last_interaction,
        identity_type=candidate.identity_type,
        attio_safe_to_match=candidate.attio_safe_to_match,
        investment_interest_score=candidate.investment_interest_score,
        evidence_confidence_score=candidate.evidence_confidence_score,
        actionability_score=actionability_score,
        freshness_score=freshness_score,
        market_movement_score=movement_score,
        marathon_fit_score=marathon_fit_score,
        noise_risk_score=noise_score,
        consensus_risk_score=consensus_score,
        company_identity_quality_score=identity_score,
        company_identity_quality_basis=identity_basis,
        actionability_basis=actionability_basis,
        freshness_basis=freshness_basis,
        market_movement_basis=movement_basis,
        marathon_fit_basis=marathon_fit_basis,
        noise_risk_basis=noise_basis,
        consensus_risk_basis=consensus_basis,
        focus_priority_score=focus_score,
        focus_priority_basis=focus_basis,
        movement_assignment_method="direct_match",
        movement_assignment_confidence="Medium" if candidate.theme else "Low",
        movement_assignment_evidence_url=urls[0] if urls else "",
        first_seen_at="",
        last_seen_at="",
        seen_in_prior_runs=bool(candidate.weekly_tag and candidate.weekly_tag != "NEW"),
        weekly_tag=candidate.weekly_tag,
        new_evidence_this_week=urls[:2],
        why_this_may_be_noise=candidate.why_this_may_be_noise,
        skepticism_events=[candidate.why_this_may_be_noise] if candidate.why_this_may_be_noise else [],
        source_candidate_id=candidate.stable_key or candidate.name,
        maturity_status=candidate.maturity_status,
        maturity_basis=list(candidate.maturity_basis),
        maturity_evidence_urls=list(candidate.maturity_evidence_urls),
        category_anchor=candidate.category_anchor,
        consensus_risk_reason=candidate.consensus_risk_reason,
        lead_route=candidate.lead_route,
    )
    item.recommended_action = choose_recommended_action(candidate, item)
    return item


WORKFLOW_ACTIONS = [
    ACTION_ASSIGN_OWNER,
    ACTION_RESEARCH_DEEPER,
    ACTION_REFRESH_ATTIO,
    ACTION_TAKE_MEETING,
    ACTION_MONITOR_ONLY,
]


def _rank_focus_items(items: list[FocusItem]) -> list[FocusItem]:
    ranked = sorted(
        items,
        key=lambda item: (
            item.focus_priority_score,
            item.investment_interest_score,
            item.evidence_confidence_score,
        ),
        reverse=True,
    )
    for index, item in enumerate(ranked, start=1):
        item.rank = index
    return ranked


def _cap_oss_project_only(items: list[FocusItem], *, max_oss: int = 5) -> list[FocusItem]:
    kept = []
    oss_count = 0
    for item in items:
        is_project_only = bool(item.project_url) and not item.company_domain
        if is_project_only:
            if oss_count >= max_oss:
                continue
            oss_count += 1
        kept.append(item)
    return kept


def build_market_movements(items: list[FocusItem], theme_signals: list[ThemeSignal] | None = None) -> list[MarketMovement]:
    grouped = defaultdict(list)
    for item in items:
        grouped[item.market_movement_id].append(item)

    movements = []
    for movement_id, group in grouped.items():
        first = group[0]
        evidence_urls = []
        for item in group:
            evidence_urls.extend(item.evidence_urls[:2])
        evidence_urls = list(dict.fromkeys(evidence_urls))
        talker_mix = Counter(talker for item in group for talker in item.talker_types)
        movements.append(
            MarketMovement(
                id=movement_id,
                name=first.market_movement,
                market_sector=first.market_sector,
                what_is_moving=f"{first.market_movement} is showing enough signal to attach companies/projects.",
                why_now=first.why_focus_this_week,
                why_not_now=first.why_this_may_be_noise,
                who_is_talking=list(dict.fromkeys(talker for item in group for talker in item.who_is_talking)),
                talker_mix=dict(talker_mix),
                companies_or_projects=[item.name for item in group[:6]],
                evidence_urls=evidence_urls[:5],
                skepticism_events=[item.why_this_may_be_noise for item in group if item.why_this_may_be_noise][:5],
                momentum_label="NEW" if any(item.weekly_tag == "NEW" for item in group) else "PERSISTENT",
                confidence="Medium" if len(group) >= 2 else "Low",
            )
        )

    return sorted(movements, key=lambda movement: len(movement.companies_or_projects), reverse=True)[:6]


def _new_to_marathon(items: list[FocusItem]) -> list[FocusItem]:
    selected = []
    for item in items:
        if item.category_anchor or item.lead_route in {LEAD_ROUTE_CATEGORY_CONTEXT, LEAD_ROUTE_MONITOR_ONLY}:
            continue
        status = item.attio_status.lower()
        weak_name = len((item.name or "").strip()) <= 2 and not item.company_domain
        credible_new_identity = (
            bool(item.company_domain)
            and (
                item.identity_type == "verified_company"
                or not item.identity_type
            )
            and (item.attio_safe_to_match or not item.identity_type)
        )
        credible_launch_identity = (
            bool(item.company_domain)
            and item.attio_safe_to_match
            and item.identity_type == "launch_style_needs_identity"
        )
        if (
            status in ATTIO_NEW_STATUSES
            and not weak_name
            and "weak_candidate_name" not in item.company_identity_quality_basis
            and (credible_new_identity or credible_launch_identity)
        ):
            selected.append(item)
    return selected[:10]


def is_extended_watchlist_eligible(item: FocusItem) -> bool:
    if item.category_anchor or item.lead_route in {LEAD_ROUTE_CATEGORY_CONTEXT, LEAD_ROUTE_MONITOR_ONLY}:
        return False
    return (
        bool(item.evidence_urls)
        and item.noise_risk_score < 85
        and item.focus_priority_score >= 35
        and item.recommended_action != ACTION_MONITOR_ONLY
    )


def _themes_without_companies(theme_signals: list[ThemeSignal] | None) -> list[dict]:
    return [item.to_dict() for item in (theme_signals or [])[:10]]


def _workflow_view(items: list[FocusItem]) -> dict[str, list[FocusItem]]:
    grouped = {action: [] for action in WORKFLOW_ACTIONS}
    for item in items:
        grouped.setdefault(item.recommended_action, []).append(item)
    return {action: rows for action, rows in grouped.items() if rows}


def _dedupe_focus_items(items: list[FocusItem]) -> list[FocusItem]:
    deduped: list[FocusItem] = []
    seen: set[str] = set()
    for item in items:
        key = item.id or item.company_domain or item.name
        if key in seen:
            continue
        deduped.append(item)
        seen.add(key)
    return deduped


def _source_gap_error(error: str, *, source_gap_context: str = "") -> str:
    if source_gap_context == "bounded_validation" and "last30days query timed out" in (error or "").lower():
        return f"{error} during bounded validation profile; rerun with a larger query timeout before treating this as a source outage."
    return error


def _source_gaps(sector_intelligence: list[SectorIntelligence] | None, *, source_gap_context: str = "") -> list[str]:
    gaps = [
        "No X/Product Hunt/package-registry adapters in Phase 1A/1B; focus list is based on current candidates, signals, and Attio fields only."
    ]
    for item in sector_intelligence or []:
        if item.source_errors:
            errors = [_source_gap_error(error, source_gap_context=source_gap_context) for error in item.source_errors]
            gaps.append(f"{item.market_sector}: {'; '.join(errors)}")
        elif "grounded" in (item.why_no_more_companies or "").lower():
            gaps.append(f"{item.market_sector}: {item.why_no_more_companies}")
    return list(dict.fromkeys(gaps))[:8]


def _executive_snapshot(
    *,
    partner_focus: list[FocusItem],
    action_items: list[FocusItem],
    identity_source_items: list[FocusItem] | None = None,
    movements: list[MarketMovement],
    new_to_marathon: list[FocusItem],
    source_gaps: list[str],
) -> ExecutiveSnapshot:
    action_counts = Counter(item.recommended_action for item in (action_items or partner_focus))
    oss_project_only_rows = sum(
        1
        for item in partner_focus
        if item.project_url and item.identity_type in {"oss_project_watch", "oss_with_commercial_intent", ""}
    )
    company_or_launch_style_rows = len(partner_focus) - oss_project_only_rows
    readiness_note = (
        "This run produced a research queue, not owner-ready leads."
        if action_items and len(action_counts) == 1 and action_counts.get(ACTION_RESEARCH_DEEPER) == len(action_items)
        else ""
    )
    identity_missing_terms = {
        "no verified company domain",
        "no verified domain",
        "no founder identity",
        "no founder or maintainer identity",
    }
    identity_pool = []
    seen_identity_ids = set()
    for item in new_to_marathon + partner_focus + action_items + list(identity_source_items or []):
        if item.id not in seen_identity_ids:
            identity_pool.append(item)
            seen_identity_ids.add(item.id)
    identity_resolution_candidates = [
        item
        for item in identity_pool
        if any(missing in item.missing_evidence for missing in identity_missing_terms)
        and "weak_candidate_name" not in item.company_identity_quality_basis
    ]
    identity_resolution_candidates = sorted(
        identity_resolution_candidates,
        key=lambda item: (
            item in new_to_marathon,
            bool(item.company_domain) or not item.project_url,
            item.focus_priority_score,
        ),
        reverse=True,
    )
    top_identity_resolution_target = ""
    for item in identity_resolution_candidates:
        if any(missing in item.missing_evidence for missing in identity_missing_terms):
            top_identity_resolution_target = item.name
            break
    return ExecutiveSnapshot(
        top_movement=movements[0].name if movements else "",
        top_new_to_marathon=new_to_marathon[0].name if new_to_marathon else "",
        rows_needing_owner=action_counts.get(ACTION_ASSIGN_OWNER, 0),
        rows_needing_attio_refresh=action_counts.get(ACTION_REFRESH_ATTIO, 0),
        biggest_source_gap=source_gaps[0] if source_gaps else "",
        top_actions=[f"{action}: {count}" for action, count in action_counts.most_common(5)],
        partner_focus_rows=len(partner_focus),
        oss_project_only_rows=oss_project_only_rows,
        company_or_launch_style_rows=company_or_launch_style_rows,
        readiness_note=readiness_note,
        top_identity_resolution_target=top_identity_resolution_target,
    )


def build_weekly_focus_artifact(
    *,
    candidates: list[Candidate],
    category_context_items: list[FocusItem] | None = None,
    theme_signals: list[ThemeSignal] | None = None,
    sector_intelligence: list[SectorIntelligence] | None = None,
    source_gap_context: str = "",
    run_id: str = "",
) -> WeeklyFocusArtifact:
    focus_items = _rank_focus_items([build_focus_item(candidate) for candidate in candidates])
    eligible = _cap_oss_project_only([item for item in focus_items if is_partner_focus_eligible(item)])
    partner_focus = eligible[:15]
    partner_ids = {item.id for item in partner_focus}
    extended_watchlist = [
        item
        for item in focus_items
        if item.id not in partner_ids and is_extended_watchlist_eligible(item)
    ][:15]
    category_context = [
        item
        for item in focus_items
        if item.category_anchor or item.lead_route in {LEAD_ROUTE_CATEGORY_CONTEXT, LEAD_ROUTE_MONITOR_ONLY}
    ]
    category_context = _dedupe_focus_items(category_context + list(category_context_items or []))[:10]
    movement_source_items = partner_focus + extended_watchlist + category_context
    movements = build_market_movements(movement_source_items, theme_signals)
    new_to_marathon = _new_to_marathon(partner_focus + extended_watchlist)
    workflow_view = _workflow_view(partner_focus + extended_watchlist)
    gaps = _source_gaps(sector_intelligence, source_gap_context=source_gap_context)
    focus_and_watchlist_ids = {item.id for item in partner_focus + extended_watchlist}
    appendix = {
        "needs_more_evidence": [
            item.to_dict()
            for item in focus_items
            if item.company_identity_quality_score < 60 or item.evidence_confidence_score < 45
        ][:10],
        "oss_project_watchlist": [
            item.to_dict()
            for item in extended_watchlist
            if item.project_url and not item.company_domain
        ][:10],
        "themes_without_companies": _themes_without_companies(theme_signals),
        "category_context": [item.to_dict() for item in category_context],
        "source_gaps": gaps,
        "filtered_or_noisy": [
            item.to_dict()
            for item in focus_items
            if item.id not in focus_and_watchlist_ids
        ][:10],
    }
    return WeeklyFocusArtifact(
        run_id=run_id,
        executive_snapshot=_executive_snapshot(
            partner_focus=partner_focus,
            action_items=partner_focus + extended_watchlist,
            identity_source_items=focus_items,
            movements=movements,
            new_to_marathon=new_to_marathon,
            source_gaps=gaps,
        ),
        partner_focus=partner_focus,
        market_movements=movements,
        new_to_marathon=new_to_marathon,
        workflow_view=workflow_view,
        extended_watchlist=extended_watchlist,
        appendix=appendix,
        source_gaps=gaps,
    )


def write_weekly_focus_json(artifact: WeeklyFocusArtifact, path: Path) -> Path:
    path.write_text(json.dumps(artifact.to_dict(), indent=2))
    return path


def _cell(value) -> str:
    return ("" if value is None else str(value)).replace("\n", " ").replace("|", "\\|")


def _item_row(item: FocusItem) -> str:
    return " | ".join(
        [
            str(item.rank),
            _cell(item.name),
            _cell(item.market_movement),
            _cell(item.market_sector),
            _cell(item.why_focus_this_week),
            _cell("; ".join(item.who_is_talking[:2])),
            _cell("; ".join(item.evidence_snapshot[:2])),
            _cell(item.attio_status),
            _cell(item.recommended_action),
            str(item.investment_interest_score),
            str(item.evidence_confidence_score),
            _cell("; ".join(item.missing_evidence[:2])),
            _cell(item.why_this_may_be_noise),
        ]
    )


def _movement_heading(movement: MarketMovement) -> str:
    if movement.market_sector and movement.market_sector not in movement.name:
        return f"{movement.name} ({movement.market_sector})"
    return movement.name


def render_weekly_focus_markdown(artifact: WeeklyFocusArtifact) -> str:
    lines = [
        "# Marathon Signal Radar: Weekly Focus",
        "",
        "## Executive Snapshot",
        "",
        f"- Top movement: {artifact.executive_snapshot.top_movement or 'None'}",
        f"- Top new-to-Marathon row: {artifact.executive_snapshot.top_new_to_marathon or 'None'}",
        f"- Partner Focus rows: {artifact.executive_snapshot.partner_focus_rows}",
        f"- OSS/project-only rows: {artifact.executive_snapshot.oss_project_only_rows}",
        f"- Company/launch-style rows: {artifact.executive_snapshot.company_or_launch_style_rows}",
        f"- Rows needing owner: {artifact.executive_snapshot.rows_needing_owner}",
        f"- Rows needing Attio refresh: {artifact.executive_snapshot.rows_needing_attio_refresh}",
        f"- Top identity-resolution target: {artifact.executive_snapshot.top_identity_resolution_target or 'None'}",
        f"- Readiness note: {artifact.executive_snapshot.readiness_note or 'None'}",
        f"- Biggest source gap: {artifact.executive_snapshot.biggest_source_gap or 'None'}",
    ]
    if artifact.executive_snapshot.top_actions:
        lines.append("- Top actions: " + "; ".join(artifact.executive_snapshot.top_actions))

    lines.extend(
        [
            "",
            "## Partner Focus",
            "",
            "| # | Company / Project | Market Movement | Sector | Why Focus This Week | Who Is Talking | Evidence | Attio | Action | Interest | Confidence | Missing Evidence | Why This May Be Noise |",
            "|---|---|---|---|---|---|---|---|---|---:|---:|---|---|",
        ]
    )
    if artifact.partner_focus:
        lines.extend(f"| {_item_row(item)} |" for item in artifact.partner_focus)
    else:
        lines.append("|  | No rows cleared Partner Focus gates. |  |  |  |  |  |  |  |  |  |  |  |")

    lines.extend(["", "### Focus Evidence Links", ""])
    if artifact.partner_focus:
        for item in artifact.partner_focus:
            if item.evidence_urls:
                links = ", ".join(item.evidence_urls[:3])
                lines.append(f"- **{item.name}**: {links}")
            else:
                lines.append(f"- **{item.name}**: No evidence links captured.")
    else:
        lines.append("- No focus evidence links.")

    lines.extend(["", "## Market Movements", ""])
    for movement in artifact.market_movements[:6]:
        lines.extend(
            [
                f"### {_movement_heading(movement)}",
                f"- What is moving: {movement.what_is_moving}",
                f"- Why now: {movement.why_now}",
                f"- Why not now: {movement.why_not_now or 'No specific skepticism captured.'}",
                f"- Who is talking: {', '.join(movement.who_is_talking[:4]) or 'Unknown'}",
                f"- Companies/projects: {', '.join(movement.companies_or_projects[:6]) or 'None'}",
                "",
            ]
        )
    if not artifact.market_movements:
        lines.append("- No market movements generated.")

    lines.extend(["", "## New To Marathon", ""])
    if artifact.new_to_marathon:
        for item in artifact.new_to_marathon[:10]:
            lines.append(f"- **{item.name}** — {item.attio_status}; action: {item.recommended_action}")
    else:
        lines.append("- No new-to-Marathon Attio rows surfaced.")

    lines.extend(["", "## Workflow View", ""])
    if artifact.workflow_view:
        for action, items in artifact.workflow_view.items():
            names = ", ".join(item.name for item in items[:10])
            lines.append(f"- **{action}** ({len(items)}): {names}")
    else:
        lines.append("- No workflow actions generated.")

    lines.extend(["", "## Extended Watchlist", ""])
    if artifact.extended_watchlist:
        for item in artifact.extended_watchlist[:15]:
            lines.append(f"- **{item.name}** — {item.recommended_action}; missing: {', '.join(item.missing_evidence[:2]) or 'none'}")
    else:
        lines.append("- No extended watchlist rows.")

    lines.extend(["", "## Appendix", ""])
    gaps = artifact.source_gaps or artifact.appendix.get("source_gaps", [])
    if gaps:
        lines.append("### Source Gaps")
        for gap in gaps[:8]:
            lines.append(f"- {gap}")
    needs_more = artifact.appendix.get("needs_more_evidence", [])
    if needs_more:
        lines.extend(["", "### Needs More Evidence"])
        for row in needs_more[:10]:
            lines.append(f"- **{row.get('name', 'Unknown')}** — {', '.join(row.get('missing_evidence', [])[:2])}")
    oss_watchlist = artifact.appendix.get("oss_project_watchlist", [])
    if oss_watchlist:
        lines.extend(["", "### OSS Project Watchlist"])
        for row in oss_watchlist[:10]:
            lines.append(f"- **{row.get('name', 'Unknown')}** — {row.get('recommended_action', 'Research deeper')}")
    category_context = artifact.appendix.get("category_context", [])
    if category_context:
        lines.extend(["", "### Category Context / Market Anchors"])
        for row in category_context[:10]:
            basis = ", ".join(row.get("maturity_basis", [])[:2]) or row.get("consensus_risk_reason", "")
            links = row.get("evidence_urls", []) or row.get("maturity_evidence_urls", [])
            link_text = f" Evidence: {', '.join(links[:2])}" if links else ""
            lines.append(f"- **{row.get('name', 'Unknown')}** — {row.get('maturity_status', 'unknown')}; {basis}.{link_text}")
    themes_without_companies = artifact.appendix.get("themes_without_companies", [])
    if themes_without_companies:
        lines.extend(["", "### Themes Without Companies Yet"])
        for row in themes_without_companies[:10]:
            label = row.get("theme") or row.get("name") or row.get("title") or "Unknown theme"
            lines.append(f"- **{label}**")
    filtered_or_noisy = artifact.appendix.get("filtered_or_noisy", [])
    if filtered_or_noisy:
        lines.extend(["", "### Filtered Or Noisy"])
        for row in filtered_or_noisy[:10]:
            lines.append(f"- **{row.get('name', 'Unknown')}** — {row.get('why_this_may_be_noise', 'Failed focus/watchlist gates.')}")

    return "\n".join(lines).rstrip() + "\n"


def write_feedback_scaffold(run_id: str, focus_items: list[FocusItem], path: Path) -> Path:
    payload = AlexFeedback(
        run_id=run_id,
        feedback=[
            {
                "focus_item_id": item.id,
                "rating": "",
                "notes": "",
            }
            for item in focus_items[:15]
        ],
    )
    path.write_text(json.dumps(payload.to_dict(), indent=2))
    return path
