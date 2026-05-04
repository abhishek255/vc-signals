from __future__ import annotations

import re

from radar_models import Candidate


INTEREST_TERMS = (
    "agent",
    "security",
    "mcp",
    "workflow",
    "enterprise",
    "bank",
    "developer",
    "infrastructure",
    "open source",
    "lineage",
    "observability",
    "testing",
)
CONSENSUS_TERMS = ("series c", "series d", "$200m", "$1b", "consensus", "too late")


def label(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def _stars_delta(text: str) -> int:
    match = re.search(r"\+(\d+)\s+stars?\s+in\s+30d", text)
    if not match:
        return 0
    return int(match.group(1))


def score_and_tier(candidate: Candidate) -> Candidate:
    text = " ".join([
        candidate.name,
        candidate.sector,
        candidate.theme,
        candidate.why_on_radar,
        candidate.why_this_may_be_noise,
    ]).lower()

    interest = 30
    evidence = 20

    interest += min(35, sum(5 for term in INTEREST_TERMS if term in text))
    evidence += min(30, int(candidate.source_count or 0) * 10)

    stars = _stars_delta(text)
    if stars >= 150:
        interest += 15
        evidence += 10
    elif stars >= 50:
        interest += 10
        evidence += 5

    if candidate.domain:
        evidence += 10
    if candidate.company_linkedin:
        evidence += 10
    if candidate.founder_profiles:
        evidence += 5
    if candidate.candidate_type == "oss_project":
        interest += 10
    if candidate.candidate_type == "theme_probe":
        evidence -= 10
    if any(term in text for term in CONSENSUS_TERMS):
        interest -= 20

    interest = max(0, min(100, interest))
    evidence = max(0, min(100, evidence))

    candidate.investment_interest_score = interest
    candidate.evidence_confidence_score = evidence
    candidate.investment_interest = label(interest)
    candidate.evidence_confidence = label(evidence)

    if interest >= 70 and evidence >= 45:
        candidate.tier = "Partner Review"
    elif interest >= 45 and evidence >= 35:
        candidate.tier = "Watchlist"
    elif interest >= 35:
        candidate.tier = "Needs More Evidence"
    else:
        candidate.tier = "Filtered"

    return candidate
