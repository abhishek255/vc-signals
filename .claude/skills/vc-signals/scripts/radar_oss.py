from __future__ import annotations

from datetime import datetime, timezone

from radar_models import Candidate


OSS_ACTIONS = {"watch", "contact maintainer", "map ecosystem", "track company formation", "ignore"}


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _repo_age_days(item: dict) -> int:
    created = item.get("created_at") or item.get("pushed_at")
    if not created:
        return 0
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, (datetime.now(timezone.utc) - created_dt).days)


def _maintainer_profiles(item: dict) -> list[dict]:
    owner = (item.get("owner") or item.get("full_name", "").split("/", 1)[0]).strip()
    url = item.get("url") or ""
    if not owner:
        return []
    github = url.rsplit("/", 1)[0] if "github.com/" in url else f"https://github.com/{owner}"
    return [{"name": owner, "github": github}]


def _score(candidate: Candidate, item: dict) -> tuple[int, list[str]]:
    stars = _int(item.get("stars") or item.get("stargazers_count"))
    velocity = item.get("velocity", {}) if isinstance(item.get("velocity"), dict) else {}
    stars_30d = _int(item.get("stars_30d") or velocity.get("stars_last_30d"))
    text = " ".join([
        candidate.name,
        item.get("description") or "",
        " ".join(item.get("topics") or []),
    ]).lower()

    score = 10
    reasons = []
    if stars_30d >= 150:
        score += 30
        reasons.append(f"+{stars_30d} stars in 30d")
    elif stars_30d >= 50:
        score += 20
        reasons.append(f"+{stars_30d} stars in 30d")
    elif stars_30d > 0:
        score += 8
        reasons.append(f"+{stars_30d} stars in 30d")

    if stars >= 1000:
        score += 15
        reasons.append(f"{stars} total stars")
    elif stars >= 250:
        score += 10
        reasons.append(f"{stars} total stars")

    strategic_terms = [term for term in ("agent", "mcp", "security", "infrastructure", "enterprise", "workflow", "eval") if term in text]
    if strategic_terms:
        score += min(20, len(strategic_terms) * 5)
        reasons.append("strategic keywords: " + ", ".join(strategic_terms[:4]))

    if item.get("license"):
        score += 5
        reasons.append("license present")
    if _maintainer_profiles(item):
        score += 5
        reasons.append("maintainer identifiable")

    return min(100, score), reasons


def action_for_score(score: int) -> str:
    if score >= 70:
        return "track company formation"
    if score >= 55:
        return "contact maintainer"
    if score >= 35:
        return "watch"
    if score >= 20:
        return "map ecosystem"
    return "ignore"


def enrich_oss_candidate(candidate: Candidate, source_metadata: dict) -> Candidate:
    if candidate.candidate_type != "oss_project":
        return candidate

    velocity = source_metadata.get("velocity", {}) if isinstance(source_metadata.get("velocity"), dict) else {}
    candidate.stars = _int(source_metadata.get("stars") or source_metadata.get("stargazers_count"))
    candidate.stars_30d = _int(source_metadata.get("stars_30d") or velocity.get("stars_last_30d"))
    candidate.license = source_metadata.get("license") or ""
    candidate.repo_age_days = _repo_age_days(source_metadata)
    if not candidate.maintainer_profiles:
        candidate.maintainer_profiles = _maintainer_profiles(source_metadata)
    if not candidate.founder_profiles and candidate.maintainer_profiles:
        candidate.founder_profiles = candidate.maintainer_profiles.copy()

    score, reasons = _score(candidate, source_metadata)
    candidate.oss_company_formation_score = score
    candidate.action = action_for_score(score)
    candidate.oss_action_reason = "; ".join(reasons) if reasons else "Low formation signal; keep as ecosystem context."
    return candidate
