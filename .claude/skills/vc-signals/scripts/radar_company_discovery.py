from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

from radar_models import Candidate, DiscoveryQuery, FocusItem, ThemeSignal, VerifiedCompanyDiscoveryLead


COMPANY_INTENT_TERMS = ("startup", "company", "founder", "launch", "seed", "yc", "raises", "website")
BROAD_THEMES = {"ai", "devtools", "cybersecurity", "data", "oss", "automation"}
GENERIC_MOVEMENTS = {"emerging technical signal", "unclassified technical tooling", "oss company-formation watchlist"}
IDENTITY_MISSING_TERMS = ("domain", "founder", "company", "identity")
NOISY_OSS_TERMS = ("template", "tutorial", "example", "demo", "boilerplate")
STRONG_MOVEMENT_PHRASES = ("ai agent", "agent security", "mcp", "tool permissions", "runtime security", "agent permissions")
CONTENT_PLATFORM_DOMAINS = {
    "github.com",
    "news.ycombinator.com",
    "medium.com",
    "substack.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "reddit.com",
    "docs.google.com",
    "notion.site",
    "deepwiki.com",
}
PUBLISHER_DOMAIN_HINTS = (
    "news",
    "times",
    "today",
    "sun",
    "week",
    "crunch",
    "morningstar",
    "prnewswire",
    "wire",
    "press",
)


def build_company_discovery_queries(
    theme_signals: list[ThemeSignal],
    *,
    focus_items: list[FocusItem] | None = None,
    unresolved_candidates: list[Candidate] | None = None,
    grounded_available: bool,
    social_available: bool,
    lookback_days: int = 30,
    max_queries_per_theme: int = 3,
) -> list[dict]:
    """Build targeted company searches from non-company theme evidence."""
    queries: list[dict] = []
    seen_topics = set()

    for signal in theme_signals:
        theme = signal.theme
        if _is_broad_movement(theme):
            continue
        market_sector = signal.market_sector
        required_terms = _movement_terms(theme)
        query_specs = [
            (
                "theme_company_search",
                signal.suggested_search or f"{theme} startups Seed Series A founder launch",
                "theme_signal",
                [f"theme:{_stable_slug(theme)}"],
            ),
            (
                "theme_founder_search",
                f"{theme} startup founder launch company {market_sector}",
                "theme_signal",
                [f"theme:{_stable_slug(theme)}"],
            ),
            (
                "theme_funding_search",
                f"{theme} startup raises seed Series A funding company",
                "theme_signal",
                [f"theme:{_stable_slug(theme)}"],
            ),
        ]
        for kind, topic, reason, origin_ids in query_specs[:max_queries_per_theme]:
            _append_query(
                queries,
                seen_topics,
                kind=kind,
                topic=topic,
                movement=theme,
                market_sector=market_sector,
                source_reason=reason,
                origin_row_ids=origin_ids,
                required_terms=required_terms,
                grounded_available=grounded_available,
                lookback_days=lookback_days,
            )

    for item in focus_items or []:
        if not _focus_item_can_seed_query(item):
            continue
        movement = item.market_movement
        required_terms = _movement_terms(movement)
        topic = f"{movement} startup company founder launch {item.market_sector}".strip()
        _append_query(
            queries,
            seen_topics,
            kind="focus_identity_search",
            topic=topic,
            movement=movement,
            market_sector=item.market_sector,
            source_reason="needs_more_evidence",
            origin_row_ids=[item.id],
            required_terms=required_terms,
            grounded_available=grounded_available,
            lookback_days=lookback_days,
        )

    for candidate in unresolved_candidates or []:
        if not _candidate_can_seed_query(candidate):
            continue
        movement = candidate.theme
        required_terms = _movement_terms(movement)
        topic = f"{movement} startup company founder launch {candidate.name}".strip()
        _append_query(
            queries,
            seen_topics,
            kind="candidate_identity_search",
            topic=topic,
            movement=movement,
            market_sector=candidate.market_sector or candidate.sector,
            source_reason="identity_resolution_target",
            origin_row_ids=[candidate.stable_key or candidate.name],
            required_terms=required_terms,
            grounded_available=grounded_available,
            lookback_days=lookback_days,
        )

    return queries


def collect_company_discovery(
    theme_signals: list[ThemeSignal],
    *,
    focus_items: list[FocusItem] | None = None,
    unresolved_candidates: list[Candidate] | None = None,
    query_runner: Callable | None,
    grounded_available: bool,
    social_available: bool,
    lookback_days: int = 30,
    max_queries_per_theme: int = 3,
) -> dict:
    """Run theme-driven company searches and annotate returned evidence."""
    queries = build_company_discovery_queries(
        theme_signals,
        focus_items=focus_items,
        unresolved_candidates=unresolved_candidates,
        grounded_available=grounded_available,
        social_available=social_available,
        lookback_days=lookback_days,
        max_queries_per_theme=max_queries_per_theme,
    )
    result = {
        "queries": queries,
        "items": [],
        "accepted_leads": [],
        "rejected_leads": [],
        "warnings": [],
        "errors": [],
        "summary": {
            "queries_run": 0,
            "accepted": 0,
            "rejected": 0,
            "grounded_available": grounded_available,
        },
    }
    if queries and not grounded_available:
        result["warnings"].append("Grounded company discovery unavailable; company discovery is artifact-only.")
        return result
    if not query_runner or not queries:
        if queries and not query_runner:
            result["warnings"].append("Theme company discovery skipped because last30days query runner is unavailable.")
        return result

    items = []
    accepted_leads = []
    rejected_leads = []
    for query in queries:
        try:
            payload = query_runner(
                query["topic"],
                sources=query["sources"],
                lookback_days=query["lookback_days"],
                auto_resolve=True,
                store=True,
                web_backend=query.get("web_backend"),
            )
            result["summary"]["queries_run"] += 1
        except Exception as exc:  # pragma: no cover - defensive boundary around live tools
            result["errors"].append(f"{query['kind']}: {exc}")
            continue

        for warning in payload.get("warnings", []):
            if warning not in result["warnings"]:
                result["warnings"].append(warning)
        if payload.get("error"):
            result["errors"].append(payload["error"])

        for item in payload.get("items", []):
            enriched = dict(item)
            enriched.setdefault("query_kind", query["kind"])
            enriched.setdefault("query_topic", query["topic"])
            enriched.setdefault("query_theme", query["theme"])
            enriched.setdefault("market_sector", query["market_sector"])
            enriched.setdefault("candidate_eligible", True)
            enriched.setdefault("discovery_lane", "controlled_company_discovery")
            lead = verify_discovery_item(enriched, query)
            if lead.verification_status == "accepted":
                accepted_leads.append(lead.to_dict())
                items.append(_lead_to_item(lead))
            else:
                rejected_leads.append(lead.to_dict())

    result["items"] = _dedupe_items(items)
    result["accepted_leads"] = _dedupe_leads(accepted_leads)
    result["rejected_leads"] = _dedupe_leads(rejected_leads)
    result["summary"]["accepted"] = len(result["accepted_leads"])
    result["summary"]["rejected"] = len(result["rejected_leads"])
    return result


def verify_discovery_item(item: dict, query: dict) -> VerifiedCompanyDiscoveryLead:
    source_url = item.get("url") or item.get("source_url") or ""
    source = (item.get("source") or "").lower()
    title = item.get("title") or ""
    snippet = item.get("snippet") or item.get("description") or ""
    name = item.get("company_name") or item.get("name") or title
    domain = _normalize_domain(item.get("domain") or item.get("website") or _domain_from_url(source_url))
    required_terms = query.get("required_terms") or _movement_terms(query.get("movement", ""))

    basis = []
    missing = []
    movement_basis = []
    combined_text = f"{title} {snippet} {name} {domain}".lower()

    if not source_url:
        missing.append("no_source_url")
    if not name:
        missing.append("no_company_name")
    if source == "github" or "github.com" in source_url:
        missing.append("github_only_not_company_proof")
    domain_ok, domain_basis, domain_missing = _company_domain_evidence(item, domain, source_url, source)
    basis.extend(domain_basis)
    missing.extend(domain_missing)

    movement_ok, movement_reasons = _movement_match_strength(combined_text, required_terms)
    if movement_ok:
        movement_basis.extend(movement_reasons)
    else:
        missing.extend(movement_reasons)

    accepted = bool(source_url and name and domain_ok and movement_basis and "github_only_not_company_proof" not in missing)
    return VerifiedCompanyDiscoveryLead(
        name=name,
        movement=query.get("movement", ""),
        market_sector=query.get("market_sector", ""),
        source_url=source_url,
        source=item.get("source", ""),
        domain=domain if accepted else "",
        founder_or_maintainer=item.get("founder") or item.get("author") or "",
        candidate_type="verified_company" if accepted and domain else "launch_style_needs_identity",
        verification_status="accepted" if accepted else "rejected",
        verification_basis=basis,
        missing_evidence=list(dict.fromkeys(missing)),
        movement_assignment_basis=movement_basis,
        query_id=query.get("id", ""),
        query_topic=query.get("topic", ""),
        why_on_radar=snippet or title,
        why_this_may_be_noise="Needs verification across stronger company/founder/customer evidence.",
        raw_title=title,
        raw_snippet=snippet,
    )


def _lead_to_item(lead: VerifiedCompanyDiscoveryLead) -> dict:
    return {
        "source": lead.source or "grounding",
        "title": lead.raw_title or lead.name,
        "url": lead.source_url,
        "snippet": lead.why_on_radar,
        "company_name": lead.name,
        "domain": lead.domain,
        "market_sector": lead.market_sector,
        "query_theme": lead.movement,
        "query_topic": lead.query_topic,
        "query_id": lead.query_id,
        "query_kind": _query_kind_from_id(lead.query_id),
        "candidate_eligible": True,
        "signal_role": "launch",
        "source_lane": "Grounded web",
        "discovery_lane": "controlled_company_discovery",
        "discovery_verification_status": "accepted",
        "discovery_verification_basis": lead.verification_basis,
        "movement_assignment_basis": lead.movement_assignment_basis,
    }


def _sources(*, grounded_available: bool, social_available: bool) -> str:
    return "grounding" if grounded_available else ""


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        raw = urlparse(raw).netloc
    raw = raw.lower().strip("/")
    return raw[4:] if raw.startswith("www.") else raw


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    return _normalize_domain(parsed.netloc)


def _is_content_platform_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in CONTENT_PLATFORM_DOMAINS)


def _company_domain_evidence(item: dict, domain: str, source_url: str, source: str) -> tuple[bool, list[str], list[str]]:
    """Decide whether a grounded result domain is company evidence, not just the article publisher."""
    basis: list[str] = []
    missing: list[str] = []
    normalized = _normalize_domain(domain)
    source_domain = _domain_from_url(source_url)
    if not normalized:
        return False, basis, ["no_source_backed_domain"]
    if _is_content_platform_domain(normalized):
        return False, basis, ["content_platform_not_company_domain", "no_source_backed_domain"]
    if source == "github" or "github.com" in (source_url or ""):
        return False, basis, ["github_only_not_company_proof", "no_source_backed_domain"]
    if _looks_academic_or_government_domain(normalized):
        return False, basis, ["academic_or_government_domain_not_company_proof", "no_source_backed_domain"]

    declared_name = (item.get("company_name") or item.get("name") or "").strip()
    title = (item.get("title") or "").strip()
    homepage_like = _is_homepage_like(source_url)
    if homepage_like and source_domain == normalized and not _looks_like_publisher_domain(normalized):
        return True, ["official_homepage_domain"], missing

    if declared_name and declared_name != title and _domain_matches_name(normalized, declared_name):
        return True, ["declared_company_name_matches_domain"], missing

    if item.get("domain") and source_domain == normalized and _domain_matches_name(normalized, declared_name or title):
        return True, ["source_backed_domain"], missing

    return False, basis, ["source_domain_not_company_proof", "no_source_backed_domain"]


def _is_homepage_like(url: str) -> bool:
    parsed = urlparse(url or "")
    path = (parsed.path or "").strip("/")
    return not path


def _looks_academic_or_government_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return normalized.endswith(".edu") or ".edu." in normalized or normalized.endswith(".gov") or ".gov." in normalized


def _looks_like_publisher_domain(domain: str) -> bool:
    first_label = _normalize_domain(domain).split(".", 1)[0]
    return any(hint in first_label for hint in PUBLISHER_DOMAIN_HINTS)


def _domain_matches_name(domain: str, name: str) -> bool:
    base = _normalize_domain(domain).split(".", 1)[0]
    name_slug = "".join(char.lower() for char in (name or "") if char.isalnum())
    base_slug = "".join(char.lower() for char in base if char.isalnum())
    return bool(base_slug and name_slug and (base_slug in name_slug or name_slug in base_slug))


def _append_query(
    queries: list[dict],
    seen_topics: set[str],
    *,
    kind: str,
    topic: str,
    movement: str,
    market_sector: str,
    source_reason: str,
    origin_row_ids: list[str],
    required_terms: list[str],
    grounded_available: bool,
    lookback_days: int,
) -> None:
    if not _query_is_specific(topic, required_terms):
        return
    normalized_topic = " ".join(topic.lower().split())
    if normalized_topic in seen_topics:
        return
    seen_topics.add(normalized_topic)
    query = DiscoveryQuery(
        id=f"{_stable_slug(movement)}-{kind}",
        movement=movement,
        market_sector=market_sector,
        source_reason=source_reason,
        topic=topic,
        sources=_sources(grounded_available=grounded_available, social_available=False),
        lookback_days=lookback_days,
        web_backend="auto" if grounded_available else "",
        candidate_eligible=True,
        origin_row_ids=origin_row_ids,
        required_terms=required_terms,
        limited=not grounded_available,
        reason="" if grounded_available else "Grounded company discovery unavailable; company discovery is artifact-only.",
    ).to_dict()
    query["kind"] = kind
    query["theme"] = movement
    queries.append(query)


def _stable_slug(text: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in text or "").strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "unknown"


def _movement_terms(text: str) -> list[str]:
    normalized = (text or "").lower().replace("/", " ").replace("-", " ")
    stop = {"the", "and", "for", "with", "from", "this", "that", "tooling", "tools", "startup", "company"}
    return [token for token in normalized.split() if len(token) >= 3 and token not in stop]


def _is_broad_movement(movement: str) -> bool:
    terms = _movement_terms(movement)
    return not terms or (len(terms) == 1 and terms[0] in BROAD_THEMES) or (movement or "").lower() in GENERIC_MOVEMENTS


def _movement_match_strength(text: str, required_terms: list[str]) -> tuple[bool, list[str]]:
    lowered = (text or "").lower()
    matched = [term for term in required_terms if term in lowered]
    if len(matched) >= 2:
        return True, [f"movement_terms_present:{','.join(matched)}"]
    strong = [phrase for phrase in STRONG_MOVEMENT_PHRASES if phrase in lowered]
    if strong:
        return True, [f"strong_movement_phrase:{strong[0]}"]
    return False, ["movement_terms_missing"]


def _query_is_specific(topic: str, required_terms: list[str]) -> bool:
    text = (topic or "").lower()
    return _movement_match_strength(text, required_terms)[0] and any(term in text for term in COMPANY_INTENT_TERMS)


def _focus_item_can_seed_query(item: FocusItem) -> bool:
    movement = (item.market_movement or "").lower()
    text = f"{item.name} {item.why_focus_this_week} {item.why_this_may_be_noise}".lower()
    missing = " ".join(item.missing_evidence).lower()
    return (
        item.recommended_action == "Research deeper"
        and bool(item.evidence_urls)
        and movement not in GENERIC_MOVEMENTS
        and any(term in missing for term in IDENTITY_MISSING_TERMS)
        and item.noise_risk_score < 70
        and not any(term in text for term in NOISY_OSS_TERMS)
    )


def _candidate_can_seed_query(candidate: Candidate) -> bool:
    name = (candidate.name or "").strip()
    theme = (candidate.theme or "").lower()
    text = f"{candidate.name} {candidate.why_on_radar} {candidate.why_this_may_be_noise}".lower()
    return (
        len(name) > 2
        and theme
        and theme not in GENERIC_MOVEMENTS
        and not _is_broad_movement(theme)
        and any(term in " ".join(candidate.missing_identity_evidence).lower() for term in IDENTITY_MISSING_TERMS)
        and not any(term in text for term in NOISY_OSS_TERMS)
    )


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = (item.get("domain") or item.get("url") or item.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_leads(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = (item.get("domain") or item.get("source_url") or item.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _query_kind_from_id(query_id: str) -> str:
    for suffix in ("theme_company_search", "theme_founder_search", "theme_funding_search", "focus_identity_search", "candidate_identity_search"):
        if (query_id or "").endswith(suffix):
            return suffix
    return ""
