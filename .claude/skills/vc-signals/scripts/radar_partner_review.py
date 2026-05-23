from __future__ import annotations

from candidate_quality import candidate_quality_from_candidate
from radar_models import Candidate


LABEL_SCORES = {
    "High": 80,
    "Medium": 55,
    "Low": 30,
}


def _label_score(label: str) -> int:
    return LABEL_SCORES.get((label or "").strip(), 0)


def _market_sector(candidate: Candidate) -> str:
    return candidate.market_sector or candidate.sector or "Unclassified"


def _source_lane(candidate: Candidate) -> str:
    return candidate.source_lane or candidate.source or "Unknown"


def _dedupe_key(candidate: Candidate) -> str:
    return candidate.stable_key or candidate.domain or candidate.name


def _is_oss(candidate: Candidate) -> bool:
    return _source_lane(candidate).lower() == "oss"


def _is_likely_too_late(candidate: Candidate) -> bool:
    haystack = " ".join([
        candidate.action,
        candidate.attio_action,
        candidate.why_on_radar,
        candidate.why_this_may_be_noise,
    ]).lower()
    return "likely too late" in haystack or "too late" in haystack


def _has_owner_ready_action(candidate: Candidate) -> bool:
    return (
        (candidate.recommended_owner_action or "").lower() == "assign owner"
        and int(candidate.owner_readiness_score or 0) >= 80
        and candidate.identity_type == "verified_company"
        and candidate.attio_safe_to_match
        and not candidate.missing_owner_evidence
    )


def compute_partner_priority(candidate: Candidate) -> int:
    interest = int(candidate.investment_interest_score or 0) or _label_score(candidate.investment_interest)
    evidence = int(candidate.evidence_confidence_score or 0) or _label_score(candidate.evidence_confidence)

    score = interest
    score += evidence // 2

    if candidate.tier == "Partner Review":
        score += 15
    elif candidate.tier == "Watchlist":
        score += 5
    elif candidate.tier == "Needs More Evidence":
        score -= 8

    weekly_tag = (candidate.weekly_tag or "").upper()
    if weekly_tag == "NEW":
        score += 8
    elif weekly_tag == "RETURNING":
        score += 5
    elif weekly_tag == "CHANGED":
        score += 4

    if candidate.attio_status in {"no_match", "stale", "no_owner"}:
        score += 5
    elif candidate.attio_status in {"active", "passed"}:
        score -= 5

    actions = {(candidate.action or "").lower(), (candidate.attio_action or "").lower()}
    if "take meeting" in actions or "refresh attio" in actions or (candidate.attio_action or "").lower() == "assign owner":
        score += 6
    elif "assign owner" in actions and _has_owner_ready_action(candidate):
        score += 6
    elif actions & {"contact maintainer", "track company formation", "map category"}:
        score += 4
    if "ignore" in actions:
        score -= 20

    if _is_oss(candidate):
        score += min(15, int(candidate.oss_company_formation_score or 0) // 5)

    if _is_likely_too_late(candidate):
        score -= 30
    if _market_sector(candidate) == "Unclassified":
        score -= 15

    return max(0, min(150, score))


def _ranked_qualified(candidates: list[Candidate]) -> list[Candidate]:
    for candidate in candidates:
        candidate.partner_priority_score = compute_partner_priority(candidate)

    qualified = [
        candidate
        for candidate in candidates
        if candidate.tier not in {"Filtered", "Needs More Evidence"}
        and candidate.partner_priority_score > 0
        and candidate_quality_from_candidate(candidate).usable
    ]
    return sorted(
        qualified,
        key=lambda item: (
            item.partner_priority_score,
            item.investment_interest_score,
            item.evidence_confidence_score,
            item.name.lower(),
        ),
        reverse=True,
    )


def _append_candidate(
    selected: list[Candidate],
    seen_keys: set[str],
    candidate: Candidate,
) -> bool:
    key = _dedupe_key(candidate)
    if key in seen_keys:
        return False
    selected.append(candidate)
    seen_keys.add(key)
    return True


def select_partner_review(
    candidates: list[Candidate],
    *,
    min_rows: int = 10,
    max_rows: int = 15,
    max_oss_rows: int = 5,
) -> list[Candidate]:
    ranked = _ranked_qualified(candidates)
    if not ranked:
        return []

    non_oss_exists = any(not _is_oss(item) for item in ranked)
    selected: list[Candidate] = []
    seen_keys: set[str] = set()

    best_by_sector: dict[str, Candidate] = {}
    for candidate in ranked:
        best_by_sector.setdefault(_market_sector(candidate), candidate)

    for candidate in sorted(best_by_sector.values(), key=lambda item: item.partner_priority_score, reverse=True):
        if len(selected) >= max_rows:
            break
        if non_oss_exists and _is_oss(candidate) and sum(1 for item in selected if _is_oss(item)) >= max_oss_rows:
            continue
        _append_candidate(selected, seen_keys, candidate)

    for candidate in ranked:
        if len(selected) >= max_rows:
            break
        if non_oss_exists and _is_oss(candidate) and sum(1 for item in selected if _is_oss(item)) >= max_oss_rows:
            continue
        _append_candidate(selected, seen_keys, candidate)

    if len(selected) < min_rows:
        target = min(min_rows, max_rows, len(ranked))
        for candidate in ranked:
            if len(selected) >= target:
                break
            if _is_oss(candidate):
                continue
            _append_candidate(selected, seen_keys, candidate)
        for candidate in ranked:
            if len(selected) >= target:
                break
            _append_candidate(selected, seen_keys, candidate)

    return selected
