from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable

from radar_focus import (
    ACTION_ASSIGN_OWNER,
    ACTION_MONITOR_ONLY,
    ACTION_REFRESH_ATTIO,
    ACTION_RESEARCH_DEEPER,
    ATTIO_NEW_STATUSES,
    ATTIO_NO_OWNER_STATUSES,
    LEAD_ROUTE_CATEGORY_CONTEXT,
    LEAD_ROUTE_MONITOR_ONLY,
    OWNER_READY_THRESHOLD,
    _blocking_owner_missing,
    score_owner_readiness,
)
from radar_models import Candidate, FounderTeamVerification


LATE_OR_CONTEXT_STATUSES = {"likely_too_late", "acquired", "incumbent", "category_leader"}
ROLE_PATTERN = r"\b(?:founder|co-founder|cofounder|ceo|cto|chief executive officer|chief technology officer)\b"
PERSON_NAME_PATTERN = r"[A-Z][a-z]+\s+[A-Z][a-z]+"
GENERIC_NAME_WORDS = {
    "Agent",
    "Before",
    "Build",
    "Contact",
    "Corner",
    "Customer",
    "Customers",
    "Enterprise",
    "Founders",
    "Future",
    "Marketing",
    "Our",
    "Playbook",
    "Security",
    "Super",
    "Take",
    "Team",
    "Teams",
    "The",
    "Together",
    "Your",
}


def _stable_cache_name(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _cache_path(cache_dir: Path | None, key: str) -> Path | None:
    if not cache_dir:
        return None
    return cache_dir / "founder-team-queries" / f"{_stable_cache_name(key)}.json"


def _read_cache(cache_dir: Path | None, key: str) -> dict | None:
    path = _cache_path(cache_dir, key)
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _write_cache(cache_dir: Path | None, key: str, payload: dict) -> None:
    path = _cache_path(cache_dir, key)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _candidate_key(candidate: Candidate) -> str:
    return candidate.stable_key or candidate.domain or candidate.name


def _clean_company_name(candidate: Candidate) -> str:
    name = re.sub(r"\s+", " ", (candidate.name or "").strip())
    for separator in (" | ", " - ", " – ", " — ", ": "):
        if separator in name:
            parts = [part.strip() for part in name.split(separator) if part.strip()]
            if parts:
                name = parts[-1] if len(parts[-1]) >= 2 else parts[0]
                break
    return name[:80]


def _domain(candidate: Candidate) -> str:
    domain = (candidate.domain or candidate.candidate_domain or "").strip()
    return re.sub(r"^https?://", "", domain).strip("/")


def _domain_company_name(candidate: Candidate) -> str:
    domain = _domain(candidate)
    root = domain.split(".")[0] if domain else ""
    parts = [part for part in re.split(r"[-_]+", root) if part]
    return " ".join(part[:1].upper() + part[1:] for part in parts if part)


def _looks_like_tagline(name: str) -> bool:
    lowered = (name or "").lower()
    words = re.findall(r"[a-z0-9]+", lowered)
    return (
        len(words) > 5
        or any(term in lowered for term in ("your ", " faster", " platform for ", " built for ", " production"))
        or lowered.endswith(".")
    )


def _query_company_name(candidate: Candidate) -> str:
    name = _clean_company_name(candidate)
    domain_name = _domain_company_name(candidate)
    if domain_name and _looks_like_tagline(name):
        return domain_name
    return name or domain_name


def founder_team_query(candidate: Candidate) -> str:
    return f'"{_query_company_name(candidate)}" "{_domain(candidate)}" founder OR co-founder OR CEO OR CTO'


def _eligible_for_founder_team_verification(candidate: Candidate) -> tuple[bool, str]:
    if candidate.category_anchor or candidate.lead_route in {LEAD_ROUTE_CATEGORY_CONTEXT, LEAD_ROUTE_MONITOR_ONLY}:
        return False, "category_context_or_monitor_only"
    if candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return False, candidate.maturity_status
    if candidate.identity_type in {"oss_project_watch", "oss_with_commercial_intent"}:
        return False, "oss_project_only"
    if candidate.candidate_type == "oss_project" and candidate.identity_type != "verified_company":
        return False, "oss_project_only"
    if candidate.identity_type != "verified_company" or not _domain(candidate):
        return False, "not_verified_company"
    if _has_named_founder(candidate):
        return False, "founder_already_verified"
    return True, ""


def _has_named_founder(candidate: Candidate) -> bool:
    if candidate.founders:
        return True
    for profile in candidate.founder_profiles:
        name = str(profile.get("name", "")).strip()
        if name and name.lower() != "source-backed founder/team evidence":
            return True
    return False


def _item_text(item: dict) -> str:
    return " ".join(str(item.get(key, "")) for key in ("title", "snippet", "description", "body")).strip()


def _item_url(item: dict) -> str:
    return str(item.get("url") or item.get("source_url") or "").strip()


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _company_in_text(company_name: str, text: str) -> bool:
    company = _normalized(company_name)
    text_norm = _normalized(text)
    return bool(company and company in text_norm)


def _valid_person_name(name: str, company_name: str = "") -> bool:
    parts = [part for part in re.split(r"\s+", name.strip()) if part]
    if len(parts) < 2:
        return False
    if any(part in GENERIC_NAME_WORDS for part in parts):
        return False
    if company_name and any(_normalized(part) in _normalized(company_name) for part in parts):
        return False
    return all(re.match(r"^[A-Z][a-z]+$", part) for part in parts)


def _role_label(raw: str) -> str:
    lowered = raw.lower()
    if "co-founder" in lowered or "cofounder" in lowered:
        return "co-founder"
    if "founder" in lowered:
        return "founder"
    if "chief executive" in lowered or "ceo" in lowered:
        return "CEO"
    if "chief technology" in lowered or "cto" in lowered:
        return "CTO"
    return "founder/team"


def _extract_founders_from_text(*, company_name: str, text: str, url: str) -> tuple[list[dict], list[str]]:
    if not url:
        return [], ["evidence_url_required"]
    if not _company_in_text(company_name, text):
        return [], ["company_name_missing_from_founder_evidence"]

    profiles: list[dict] = []
    rejection_reasons: list[str] = []
    role = f"(?i:{ROLE_PATTERN})"
    company = re.escape(company_name)

    founded_by_pattern = re.compile(
        rf"(?i:{company})[^.\n]{{0,100}}founded by\s+(?P<names>{PERSON_NAME_PATTERN}(?:\s+and\s+{PERSON_NAME_PATTERN})?)"
    )
    for match in founded_by_pattern.finditer(text):
        for name in re.split(r"\s+and\s+", match.group("names")):
            if _valid_person_name(name, company_name):
                profiles.append({"name": name, "role": "founder", "source": url})

    person_role_pattern = re.compile(
        rf"(?P<name>{PERSON_NAME_PATTERN})\s*,\s*(?P<role>[^.\n]{{0,80}}?{role}[^.\n]{{0,80}})"
    )
    for match in person_role_pattern.finditer(text):
        name = match.group("name")
        role_text = match.group("role")
        local_text = text[max(0, match.start() - 120) : match.end() + 120]
        if _valid_person_name(name, company_name) and _company_in_text(company_name, local_text):
            profiles.append({"name": name, "role": _role_label(role_text), "source": url})

    role_person_pattern = re.compile(rf"(?P<role>{role})\s+(?P<name>{PERSON_NAME_PATTERN})", re.IGNORECASE)
    for match in role_person_pattern.finditer(text):
        name = match.group("name")
        local_text = text[max(0, match.start() - 120) : match.end() + 120]
        if _valid_person_name(name, company_name) and _company_in_text(company_name, local_text):
            profiles.append({"name": name, "role": _role_label(match.group("role")), "source": url})

    if not profiles:
        if re.search(ROLE_PATTERN, text or "", re.IGNORECASE):
            rejection_reasons.append("no_named_founder_company_match")
        else:
            rejection_reasons.append("no_named_founder_pattern")

    deduped: list[dict] = []
    seen = set()
    for profile in profiles:
        key = (profile["name"], profile["source"])
        if key not in seen:
            seen.add(key)
            deduped.append(profile)
    return deduped, rejection_reasons


def extract_named_founder_profiles_from_text(*, company_names: list[str], text: str, url: str) -> tuple[list[dict], list[str]]:
    """Extract source-backed named founder profiles for any company alias."""
    profiles: list[dict] = []
    rejection_reasons: list[str] = []
    for company_name in company_names:
        found, rejected = _extract_founders_from_text(company_name=company_name, text=text, url=url)
        profiles.extend(found)
        rejection_reasons.extend(rejected)

    deduped: list[dict] = []
    seen = set()
    for profile in profiles:
        key = (profile.get("name"), profile.get("role"), profile.get("source"))
        if key not in seen:
            seen.add(key)
            deduped.append(dict(profile))
    return deduped, list(dict.fromkeys(rejection_reasons))


def _query_items(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("items", []) if isinstance(item, dict)]


def _apply_founder_profiles(candidate: Candidate, profiles: list[dict]) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    urls = [profile["source"] for profile in profiles if profile.get("source")]
    names = [profile["name"] for profile in profiles if profile.get("name")]
    existing_names = set(out.founders)
    for name in names:
        if name not in existing_names:
            out.founders.append(name)
            existing_names.add(name)
    existing_profiles = {(profile.get("name"), profile.get("source")) for profile in out.founder_profiles}
    for profile in profiles:
        key = (profile.get("name"), profile.get("source"))
        if key not in existing_profiles:
            out.founder_profiles.append(dict(profile))
            existing_profiles.add(key)
    out.founder_team_evidence = list(dict.fromkeys(out.founder_team_evidence + urls))[:5]
    if profiles:
        out.owner_evidence_status = "founder_team_verified"
        out.missing_identity_evidence = [
            item
            for item in out.missing_identity_evidence
            if "founder" not in item.lower() and "maintainer" not in item.lower()
        ]
        if out.identity_type == "verified_company" and _domain(out) and out.attio_safe_to_match:
            out.recommended_identity_action = ACTION_ASSIGN_OWNER
        out.evidence_confidence_score = max(out.evidence_confidence_score, 60)
    out.owner_readiness_score = 0
    out.owner_readiness_basis = []
    out.missing_owner_evidence = []
    out.recommended_owner_action = ""
    out.recommended_next_validation_step = ""
    return out


def _remove_placeholder_founder_evidence(candidate: Candidate) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    out.founder_profiles = [
        profile
        for profile in out.founder_profiles
        if str(profile.get("name", "")).strip().lower() != "source-backed founder/team evidence"
    ]
    if not out.founders and not out.founder_profiles:
        out.founder_team_evidence = []
    out.owner_readiness_score = 0
    out.owner_readiness_basis = []
    out.missing_owner_evidence = []
    out.recommended_owner_action = ""
    out.recommended_next_validation_step = ""
    return out


def _recommended_owner_action(candidate: Candidate, score: int, missing: list[str]) -> str:
    if candidate.category_anchor or candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return ACTION_MONITOR_ONLY
    if score < OWNER_READY_THRESHOLD or _blocking_owner_missing(missing):
        return ACTION_RESEARCH_DEEPER
    status = (candidate.attio_status or "unknown").lower()
    if status in {"stale", "passed"}:
        return ACTION_REFRESH_ATTIO
    if status in ATTIO_NEW_STATUSES or status in ATTIO_NO_OWNER_STATUSES:
        return ACTION_ASSIGN_OWNER
    return ACTION_RESEARCH_DEEPER


def _score_candidate(candidate: Candidate, *, eligible: bool, skip_reason: str, query: str, query_status: str, profiles: list[dict], rejection_reasons: list[str]) -> tuple[Candidate, FounderTeamVerification]:
    scored = Candidate.from_dict(candidate.to_dict())
    if profiles:
        scored = _apply_founder_profiles(scored, profiles)
    elif eligible:
        scored = _remove_placeholder_founder_evidence(scored)
        scored.owner_evidence_status = "founder_team_missing"
    score, basis, missing, next_step = score_owner_readiness(scored)
    action = _recommended_owner_action(scored, score, missing)
    scored.owner_readiness_score = score
    scored.owner_readiness_basis = basis
    scored.missing_owner_evidence = missing
    scored.recommended_owner_action = action
    scored.recommended_next_validation_step = next_step
    founders = list(dict.fromkeys(profile.get("name", "") for profile in profiles if profile.get("name")))
    evidence_urls = list(dict.fromkeys(profile.get("source", "") for profile in profiles if profile.get("source")))
    missing_founder = [] if profiles else ["no source-backed named founder/team evidence"]
    verification = FounderTeamVerification(
        candidate_key=_candidate_key(scored),
        name=scored.name,
        domain=scored.domain,
        eligible=eligible,
        skip_reason=skip_reason,
        query=query,
        query_status=query_status,
        founders_found=founders,
        founder_profiles=[dict(profile) for profile in profiles],
        founder_team_evidence=list(scored.founder_team_evidence),
        evidence_urls=evidence_urls,
        verification_basis=["named_founder_company_match", "evidence_url_present"] if profiles else [],
        missing_founder_evidence=missing_founder,
        rejection_reasons=list(dict.fromkeys(rejection_reasons)),
        owner_readiness_score=score,
        missing_owner_evidence=list(missing),
        recommended_owner_action=action,
        recommended_next_validation_step=next_step,
    )
    return scored, verification


def enrich_founder_team_verification(
    candidates: list[Candidate],
    *,
    query_runner: Callable | None = None,
    cache_dir: Path | str | None = None,
    max_candidates: int = 5,
) -> tuple[list[Candidate], dict]:
    cache_path = Path(cache_dir) if cache_dir else None
    enriched: list[Candidate] = []
    verification_items: list[FounderTeamVerification] = []
    summary = {
        "eligible": 0,
        "skipped": 0,
        "queries_run": 0,
        "query_cache_hits": 0,
        "founders_found": 0,
        "still_missing": 0,
    }
    eligible_seen = 0

    for candidate in candidates:
        eligible, skip_reason = _eligible_for_founder_team_verification(candidate)
        if not eligible or eligible_seen >= max_candidates:
            reason = skip_reason or "founder_team_candidate_budget_exceeded"
            scored, item = _score_candidate(
                Candidate.from_dict(candidate.to_dict()),
                eligible=False,
                skip_reason=reason,
                query="",
                query_status="not_eligible",
                profiles=[],
                rejection_reasons=[],
            )
            scored.owner_evidence_status = "skipped" if reason != "founder_already_verified" else scored.owner_evidence_status
            enriched.append(scored)
            verification_items.append(item)
            summary["skipped"] += 1
            continue

        eligible_seen += 1
        summary["eligible"] += 1
        topic = founder_team_query(candidate)
        payload = _read_cache(cache_path, topic)
        query_status = "cache_hit" if payload else "not_queried"
        if payload:
            summary["query_cache_hits"] += 1
        elif query_runner:
            payload = query_runner(
                topic,
                sources="grounding",
                lookback_days=30,
                auto_resolve=True,
                store=True,
                web_backend="auto",
            )
            _write_cache(cache_path, topic, payload)
            query_status = "queried"
            summary["queries_run"] += 1

        profiles: list[dict] = []
        rejection_reasons: list[str] = []
        for item in _query_items(payload):
            found, rejected = _extract_founders_from_text(
                company_name=_query_company_name(candidate),
                text=_item_text(item),
                url=_item_url(item),
            )
            profiles.extend(found)
            rejection_reasons.extend(rejected)

        scored, verification = _score_candidate(
            candidate,
            eligible=True,
            skip_reason="",
            query=topic,
            query_status=query_status,
            profiles=profiles,
            rejection_reasons=rejection_reasons,
        )
        if profiles:
            summary["founders_found"] += 1
        else:
            summary["still_missing"] += 1
        enriched.append(scored)
        verification_items.append(verification)

    return enriched, {
        "summary": summary,
        "items": [item.to_dict() for item in verification_items],
    }


def write_founder_team_verification_json(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
