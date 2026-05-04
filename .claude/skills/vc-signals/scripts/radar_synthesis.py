from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from urllib import request

from radar_models import (
    Candidate,
    PossibleCompanyLead,
    SectorDiagnosis,
    SynthesisResult,
    ThemeHypothesis,
)


DEFAULT_SYNTHESIS_MODEL = "gpt-4.1-mini"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

SECRET_KEY_RE = re.compile(r"(api[_-]?key|authorization|bearer|password|secret|token)", re.IGNORECASE)
SECRET_NAME_RE = re.compile(
    r"\b[A-Z][A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*(?:\s*=\s*\S+)?"
)
SECRET_VALUE_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9._-]{12,}|sk-(?:proj-|or-)?[A-Za-z0-9._-]{12,}|AIza[A-Za-z0-9._-]{12,}|fwKR[A-Za-z0-9._-]{8,})"
)

SIGNAL_FIELDS = (
    "source",
    "role",
    "title",
    "url",
    "sector",
    "theme",
    "text",
    "can_create_candidate",
    "evidence_strength",
    "reason",
    "metadata",
)

CANDIDATE_FIELDS = (
    "name",
    "sector",
    "market_sector",
    "source_lane",
    "theme",
    "source",
    "candidate_type",
    "stable_key",
    "weekly_tag",
    "domain",
    "why_on_radar",
    "why_this_may_be_noise",
    "sources",
    "source_count",
    "action",
    "investment_interest_score",
    "evidence_confidence_score",
    "investment_interest",
    "evidence_confidence",
    "tier",
    "stage",
    "raised",
    "headcount",
    "founders",
    "founding_year",
    "lead_investor",
    "license",
    "repo_age_days",
    "stars",
    "stars_30d",
    "oss_company_formation_score",
    "oss_action_reason",
    "evidence_role",
    "sector_confidence",
    "sector_reason",
    "partner_priority_score",
)

SECTOR_INTELLIGENCE_FIELDS = (
    "market_sector",
    "status",
    "url",
    "urls",
    "source",
    "sources",
    "source_urls",
    "evidence_urls",
    "raw_signals",
    "candidate_eligible_signals",
    "promoted_candidates",
    "rejected_signals",
    "best_evidence",
    "why_no_more_companies",
    "next_hunt",
    "source_errors",
)

THEME_SIGNAL_FIELDS = (
    "market_sector",
    "theme",
    "url",
    "urls",
    "source",
    "sources",
    "source_urls",
    "evidence_urls",
    "source_lanes",
    "evidence_count",
    "evidence_summary",
    "why_it_matters",
    "why_no_company_yet",
    "suggested_search",
    "confidence",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(item) -> dict:
    if hasattr(item, "to_dict"):
        return item.to_dict()
    if isinstance(item, dict):
        return dict(item)
    return {}


def _safe_text(value: str) -> str:
    return SECRET_NAME_RE.sub("[redacted]", SECRET_VALUE_RE.sub("[redacted]", value))


def _scrub(value):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if SECRET_KEY_RE.search(str(key)):
                continue
            out[key] = _scrub(item)
        return out
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return [_scrub(item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _safe_projection(item, fields: tuple[str, ...]) -> dict:
    payload = _as_dict(item)
    return _scrub({field: payload.get(field) for field in fields if field in payload})


def _canonical_url(url) -> str | None:
    if not isinstance(url, str):
        return None
    canonical = url.strip().rstrip("/")
    if not canonical.startswith(("http://", "https://")):
        return None
    return canonical


def _add_url(urls: set[str], value) -> None:
    url = _canonical_url(value)
    if url:
        urls.add(url)


def _collect_urls(value, urls: set[str]) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _collect_urls(item, urls)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_urls(item, urls)
    elif isinstance(value, str):
        _add_url(urls, value)


def build_source_digest(*, candidates: list, signals: list) -> dict:
    source_lanes = {}
    market_sectors = {}
    for candidate in candidates:
        payload = _as_dict(candidate)
        lane = payload.get("source_lane") or payload.get("source") or "Unknown"
        sector = payload.get("market_sector") or payload.get("sector") or "Unclassified"
        source_lanes[lane] = source_lanes.get(lane, 0) + 1
        market_sectors[sector] = market_sectors.get(sector, 0) + 1
    return {
        "candidate_count": len(candidates),
        "signal_count": len(signals),
        "source_lanes": source_lanes,
        "market_sectors": market_sectors,
    }


def _known_urls_from_payload(payload: dict) -> set[str]:
    urls: set[str] = set()
    for section in ("signals", "candidates", "sector_intelligence", "theme_signals"):
        _collect_urls(payload.get(section, []), urls)
    return urls


def build_synthesis_payload(
    *,
    evidence: dict,
    signals: list,
    candidates: list,
    sector_intelligence: list,
    theme_signals: list,
) -> dict:
    return {
        "source_digest": build_source_digest(candidates=candidates, signals=signals),
        "signals": [_safe_projection(item, SIGNAL_FIELDS) for item in signals],
        "candidates": [_safe_projection(item, CANDIDATE_FIELDS) for item in candidates],
        "sector_intelligence": [_safe_projection(item, SECTOR_INTELLIGENCE_FIELDS) for item in sector_intelligence],
        "theme_signals": [_safe_projection(item, THEME_SIGNAL_FIELDS) for item in theme_signals],
        "source_warnings": _scrub(evidence.get("warnings", [])),
    }


def _all_urls_known(urls: list[str], known_urls: set[str]) -> bool:
    if not urls:
        return False
    canonical_urls = [_canonical_url(url) for url in urls]
    return all(url is not None and url in known_urls for url in canonical_urls)


def _item_label(item: dict, *fields: str) -> str:
    if not isinstance(item, dict):
        return ""
    for field in fields:
        value = item.get(field)
        if value:
            return str(value)
    return ""


def _try_from_dict(cls, item: dict, warnings: list[str], label: str):
    if not isinstance(item, dict):
        warnings.append(f"Dropped malformed {label}: non-object item")
        return None
    try:
        return cls.from_dict(_scrub(item))
    except (TypeError, ValueError) as exc:
        warnings.append(f"Dropped malformed {label}: {_safe_text(str(exc))}")
        return None


def _validate_result(payload: dict, *, known_urls: set[str], model: str, source_digest: dict) -> SynthesisResult:
    warnings = list(_scrub(payload.get("warnings", [])))

    sector_diagnoses = []
    for item in payload.get("sector_diagnoses", []):
        if not isinstance(item, dict):
            warnings.append("Dropped malformed sector diagnosis: non-object item")
            continue
        urls = item.get("evidence_urls", [])
        if urls and not _all_urls_known(urls, known_urls):
            warnings.append(f"Dropped sector diagnosis with unknown citation: {item.get('market_sector', '')}")
            continue
        diagnosis = _try_from_dict(SectorDiagnosis, item, warnings, "sector diagnosis")
        if diagnosis is not None:
            sector_diagnoses.append(diagnosis)

    theme_hypotheses = []
    for item in payload.get("theme_hypotheses", []):
        if not isinstance(item, dict):
            warnings.append("Dropped malformed theme: non-object item")
            continue
        urls = item.get("evidence_urls", [])
        if not _all_urls_known(urls, known_urls):
            warnings.append(f"Dropped uncited or unsupported theme: {_item_label(item, 'theme')}")
            continue
        theme = _try_from_dict(ThemeHypothesis, item, warnings, "theme")
        if theme is not None:
            theme_hypotheses.append(theme)

    possible_company_leads = []
    for item in payload.get("possible_company_leads", []):
        if not isinstance(item, dict):
            warnings.append("Dropped malformed company lead: non-object item")
            continue
        urls = item.get("evidence_urls", [])
        if not _all_urls_known(urls, known_urls):
            warnings.append(f"Dropped uncited or unsupported company lead: {_item_label(item, 'name')}")
            continue
        lead = _try_from_dict(PossibleCompanyLead, item, warnings, "company lead")
        if lead is not None:
            possible_company_leads.append(lead)

    return SynthesisResult(
        enabled=True,
        model=model,
        generated_at=_now_iso(),
        source_digest=source_digest,
        sector_diagnoses=sector_diagnoses,
        theme_hypotheses=theme_hypotheses,
        possible_company_leads=possible_company_leads,
        partner_notes=list(_scrub(payload.get("partner_notes", [])))[:8],
        warnings=warnings,
    )


def call_openai_synthesis(payload: dict, *, model: str, api_key: str) -> dict:
    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a skeptical VC research analyst for Marathon Management Partners. "
                    "Use only supplied evidence. Separate facts, inferences, assumptions, and open questions. "
                    "Cite evidence_urls for every theme hypothesis or possible company lead. "
                    "Sector diagnoses may be uncited when describing source gaps, but cited diagnoses must use supplied URLs. "
                    "Do not invent company domains, funding, headcount, stage, founders, customers, or LinkedIn URLs. "
                    "Prefer needs-verification language when evidence is weak. "
                    "Penalize generic activity, tutorials, jobs, bounties, PR chores, resume reviews, and news digests. "
                    "Return only valid JSON with sector_diagnoses, theme_hypotheses, possible_company_leads, partner_notes, warnings."
                ),
            },
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ],
    }
    req = request.Request(
        OPENAI_CHAT_COMPLETIONS_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read() or b"{}")
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def run_synthesis(
    *,
    evidence: dict,
    signals: list,
    candidates: list[Candidate],
    sector_intelligence: list,
    theme_signals: list,
    provider=None,
    model: str | None = None,
) -> SynthesisResult:
    model = model or os.environ.get("VC_SIGNALS_SYNTHESIS_MODEL", DEFAULT_SYNTHESIS_MODEL)
    payload = build_synthesis_payload(
        evidence=evidence,
        signals=signals,
        candidates=candidates,
        sector_intelligence=sector_intelligence,
        theme_signals=theme_signals,
    )
    source_digest = payload["source_digest"]
    known_urls = _known_urls_from_payload(payload)

    if provider is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return SynthesisResult(
                enabled=False,
                model=model,
                generated_at=_now_iso(),
                source_digest=source_digest,
                warnings=["OPENAI_API_KEY is not set; LLM synthesis skipped."],
            )

        def provider(request_payload):
            return call_openai_synthesis(request_payload, model=model, api_key=api_key)

    try:
        raw = provider(payload)
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            raise ValueError("provider returned non-object JSON")
    except Exception as exc:
        return SynthesisResult(
            enabled=False,
            model=model,
            generated_at=_now_iso(),
            source_digest=source_digest,
            warnings=[f"LLM synthesis failed: {_safe_text(str(exc))}"],
        )

    return _validate_result(raw or {}, known_urls=known_urls, model=model, source_digest=source_digest)
