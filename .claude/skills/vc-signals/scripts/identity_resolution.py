from __future__ import annotations

import json
from pathlib import Path
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from radar_focus import ACTION_ASSIGN_OWNER, ACTION_MONITOR_ONLY, ACTION_REFRESH_ATTIO, ACTION_RESEARCH_DEEPER
from radar_models import Candidate, IdentityResolution


IDENTITY_VERIFIED_COMPANY = "verified_company"
IDENTITY_LAUNCH_NEEDS_IDENTITY = "launch_style_needs_identity"
IDENTITY_OSS_COMMERCIAL = "oss_with_commercial_intent"
IDENTITY_OSS_WATCH = "oss_project_watch"
IDENTITY_INSUFFICIENT = "insufficient_identity"
HN_ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{item_id}"
DEFAULT_HN_ENRICHMENT_CACHE_PATH = Path(__file__).parent.parent / "data" / "companies" / "hn_enrichment_cache.json"
BLOCKED_OUTBOUND_DOMAINS = {
    "github.com",
    "news.ycombinator.com",
    "ycombinator.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "medium.com",
    "substack.com",
}


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))


def _text_blob(*values: object) -> str:
    return " ".join(str(value) for value in values if value is not None).lower()


def _source_urls(candidate: Candidate) -> list[str]:
    urls = []
    for source in list(candidate.sources or []) + [candidate.source]:
        if source and source.startswith(("http://", "https://")) and source not in urls:
            urls.append(source)
    return urls


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        raw = parsed.netloc
    raw = raw.lower().strip("/")
    if raw.startswith("www."):
        raw = raw[4:]
    return raw


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    domain = _normalize_domain(parsed.netloc)
    if domain in {"github.com", "news.ycombinator.com", "www.github.com"}:
        return ""
    return domain


def _is_blocked_outbound_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in BLOCKED_OUTBOUND_DOMAINS)


def _company_domain_from_outbound_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"}:
        return "", "hn_internal_url_only"
    domain = _normalize_domain(parsed.netloc)
    if not domain or _is_blocked_outbound_domain(domain):
        return "", "hn_internal_url_only"
    return domain, ""


def extract_hn_item_id(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.netloc.lower() not in {"news.ycombinator.com", "www.news.ycombinator.com"}:
        return ""
    item_ids = parse_qs(parsed.query).get("id") or []
    return item_ids[0] if item_ids else ""


def _is_github_only(candidate: Candidate) -> bool:
    urls = _source_urls(candidate)
    return bool(urls) and all("github.com" in url for url in urls) and not candidate.domain


def _has_launch_evidence(candidate: Candidate) -> bool:
    text = _text_blob(candidate.name, candidate.why_on_radar, candidate.source, candidate.sources)
    return any(term in text for term in ("show hn", "launch", "ycombinator.com", "product launch"))


def _founder_or_maintainer_names(candidate: Candidate) -> tuple[list[str], list[str]]:
    founders = list(candidate.founders or [])
    maintainers = []
    for profile in candidate.founder_profiles or []:
        name = profile.get("name") or profile.get("title") or profile.get("url") or ""
        if name and name not in founders:
            founders.append(name)
    for profile in candidate.maintainer_profiles or []:
        name = profile.get("name") or profile.get("login") or profile.get("url") or ""
        if name and name not in maintainers:
            maintainers.append(name)
    return founders, maintainers


class _HNTitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_titleline = False
        self.capture_text = False
        self.title_parts = []
        self.outbound_url = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        class_value = attrs_dict.get("class", "")
        if tag == "span" and "titleline" in class_value:
            self.in_titleline = True
        elif self.in_titleline and tag == "a":
            href = attrs_dict.get("href", "")
            if href and not href.startswith("item?id="):
                self.outbound_url = href
            self.capture_text = True

    def handle_endtag(self, tag):
        if tag == "a":
            self.capture_text = False
        elif tag == "span" and self.in_titleline:
            self.in_titleline = False

    def handle_data(self, data):
        if self.capture_text:
            text = data.strip()
            if text:
                self.title_parts.append(text)


def parse_hn_item(html: str) -> dict:
    parser = _HNTitleParser()
    parser.feed(html or "")
    return {
        "title": " ".join(parser.title_parts).strip(),
        "outbound_url": parser.outbound_url.strip(),
    }


def parse_github_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return {}
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return {}
    owner, repo = parts[0], parts[1]
    return {
        "owner": owner,
        "repo": repo,
        "project_url": f"https://github.com/{owner}/{repo}",
    }


def fetch_existing_url(url: str, cache: dict | None = None, timeout_seconds: int = 8) -> str:
    if cache is not None and url in cache:
        return cache[url]
    request = Request(url, headers={"User-Agent": "vc-signals-identity-resolution/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8", errors="replace")
    if cache is not None:
        cache[url] = body
    return body


def load_hn_enrichment_cache(cache_path: Path | None = None) -> dict:
    path = cache_path or DEFAULT_HN_ENRICHMENT_CACHE_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_hn_enrichment_cache(cache: dict, cache_path: Path | None = None) -> None:
    path = cache_path or DEFAULT_HN_ENRICHMENT_CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True))


def fetch_hn_algolia_item(item_id: str, cache: dict | None = None, timeout_seconds: int = 8) -> dict:
    url = HN_ALGOLIA_ITEM_URL.format(item_id=item_id)
    raw = fetch_existing_url(url, cache=cache, timeout_seconds=timeout_seconds)
    return json.loads(raw)


def _hn_hints_from_payload(payload: dict, *, resolved_from: str) -> dict:
    title = payload.get("title") or payload.get("story_title") or ""
    outbound_url = payload.get("url") or payload.get("outbound_url") or ""
    domain, reason = _company_domain_from_outbound_url(outbound_url)
    hints = {
        "title": title,
        "outbound_url": outbound_url if domain else "",
        "domain": domain,
        "author": payload.get("author", ""),
        "points": payload.get("points") or 0,
        "comments": payload.get("num_comments") or payload.get("comments") or 0,
        "resolved_from": resolved_from,
        "failure_reason": "",
    }
    if outbound_url and not domain:
        hints["failure_reason"] = reason
    elif not outbound_url:
        hints["failure_reason"] = "hn_no_outbound_url"
    return hints


def resolve_hn_item_url(
    url: str,
    *,
    hn_cache: dict | None = None,
    fetch_cache: dict | None = None,
) -> dict:
    item_id = extract_hn_item_id(url)
    if not item_id:
        return {"failure_reason": "hn_algolia_not_found"}

    owns_cache = hn_cache is None
    cache = hn_cache if hn_cache is not None else load_hn_enrichment_cache()
    cached = cache.get(item_id)
    if isinstance(cached, dict):
        return {**cached, "cache_hit": True}

    warnings = []
    try:
        algolia_payload = fetch_hn_algolia_item(item_id, cache=fetch_cache)
        if not algolia_payload:
            hints = {"failure_reason": "hn_algolia_not_found"}
        else:
            hints = _hn_hints_from_payload(algolia_payload, resolved_from="hn_algolia")
            if hints.get("domain"):
                cache[item_id] = hints
                if owns_cache:
                    save_hn_enrichment_cache(cache)
                return {**hints, "cache_hit": False}
            if hints.get("failure_reason"):
                warnings.append(hints["failure_reason"])
    except HTTPError as exc:
        reason = "hn_fetch_429" if exc.code == 429 else f"hn_algolia_http_{exc.code}"
        warnings.append(reason)
    except Exception as exc:
        warnings.append(f"hn_algolia_error: {exc}")

    try:
        html = fetch_existing_url(url, cache=fetch_cache)
        parsed = parse_hn_item(html)
        hints = _hn_hints_from_payload(parsed, resolved_from="hn_page")
    except HTTPError as exc:
        reason = "hn_fetch_429" if exc.code == 429 else f"hn_page_http_{exc.code}"
        hints = {"failure_reason": reason}
    except Exception as exc:
        hints = {"failure_reason": f"hn_page_error: {exc}"}

    if warnings:
        hints["warnings"] = warnings
    if hints.get("domain"):
        cache[item_id] = hints
        if owns_cache:
            save_hn_enrichment_cache(cache)
        return {**hints, "cache_hit": False}

    hints.setdefault("failure_reason", "hn_no_outbound_url")
    cache[item_id] = hints
    if owns_cache:
        save_hn_enrichment_cache(cache)
    return {**hints, "cache_hit": False}


def resolve_from_existing_urls(candidate: Candidate, fetch_cache: dict | None = None, hn_cache: dict | None = None) -> dict:
    hints = {
        "verified_domain": "",
        "domain_confidence": "Low",
        "verified_domain_basis": [],
        "project_url": "",
        "source_outbound_urls": [],
        "source_titles": [],
        "fetch_warnings": [],
        "identity_confidence_basis": [],
        "resolved_from": [],
    }

    for url in _source_urls(candidate):
        github = parse_github_url(url)
        if github:
            hints["project_url"] = hints["project_url"] or github["project_url"]
            hints["identity_confidence_basis"].append("github_project_identity")
            hints["resolved_from"].append("github_url")
            continue

        direct_domain = _domain_from_url(url)
        if direct_domain and "news.ycombinator.com" not in url:
            hints["verified_domain"] = hints["verified_domain"] or direct_domain
            hints["domain_confidence"] = "High"
            hints["verified_domain_basis"].append("company_url_already_present")
            hints["resolved_from"].append("source_url")

        if "news.ycombinator.com/item" in url:
            parsed = resolve_hn_item_url(url, hn_cache=hn_cache, fetch_cache=fetch_cache)
            if parsed.get("title"):
                hints["source_titles"].append(parsed["title"])
            outbound_url = parsed.get("outbound_url") or ""
            outbound_domain = parsed.get("domain") or ""
            if outbound_url and outbound_domain:
                hints["source_outbound_urls"].append(outbound_url)
                hints["verified_domain"] = hints["verified_domain"] or outbound_domain
                hints["domain_confidence"] = "High"
                hints["verified_domain_basis"].append("hn_enrichment_outbound_url")
                hints["resolved_from"].append(parsed.get("resolved_from") or "hn_enrichment")
            else:
                reason = parsed.get("failure_reason") or "hn_no_outbound_url"
                hints["fetch_warnings"].append(f"{url}: {reason}")
            for warning in parsed.get("warnings") or []:
                hints["fetch_warnings"].append(f"{url}: {warning}")

    hints["verified_domain_basis"] = list(dict.fromkeys(hints["verified_domain_basis"]))
    hints["identity_confidence_basis"] = list(dict.fromkeys(hints["identity_confidence_basis"]))
    hints["resolved_from"] = list(dict.fromkeys(hints["resolved_from"]))
    return hints


def _metadata_items(candidate: Candidate) -> list[dict]:
    return [item for item in candidate.evidence_metadata or [] if isinstance(item, dict)]


def resolve_from_evidence_metadata(candidate: Candidate) -> dict:
    hints = {
        "verified_domain": "",
        "domain_confidence": "Low",
        "verified_domain_basis": [],
        "project_url": "",
        "source_outbound_urls": [],
        "source_titles": [],
        "maintainers": [],
        "maintainer_profiles": [],
        "identity_confidence_basis": [],
        "resolved_from": [],
    }

    for item in _metadata_items(candidate):
        source_url = item.get("source_url") or item.get("url") or ""
        source = (item.get("source") or "").lower()
        title = item.get("title") or ""
        if title:
            hints["source_titles"].append(title)

        github = parse_github_url(source_url)
        if github:
            hints["project_url"] = hints["project_url"] or github["project_url"]
            hints["identity_confidence_basis"].append("github_project_identity")
            hints["resolved_from"].append("metadata")

        owner_name = item.get("owner_name") or ""
        if owner_name:
            hints["maintainers"].append(owner_name)
            hints["maintainer_profiles"].append(
                {
                    "name": owner_name,
                    "type": item.get("owner_type") or "",
                    "url": github.get("project_url", "") if github else source_url,
                }
            )
            hints["identity_confidence_basis"].append("github_owner_metadata")
            hints["resolved_from"].append("metadata")

        outbound_url = item.get("outbound_url") or ""
        if outbound_url:
            hints["source_outbound_urls"].append(outbound_url)
            outbound_domain = _domain_from_url(outbound_url)
            if outbound_domain and source in {"hackernews", "hn"}:
                hints["verified_domain"] = hints["verified_domain"] or outbound_domain
                hints["domain_confidence"] = "High"
                hints["verified_domain_basis"].append("hn_outbound_url_metadata")
                hints["resolved_from"].append("metadata")

        homepage = item.get("homepage") or ""
        if homepage:
            homepage_domain = _domain_from_url(homepage)
            if homepage_domain and not hints["verified_domain"]:
                hints["verified_domain"] = homepage_domain
                hints["domain_confidence"] = "Medium"
                hints["verified_domain_basis"].append("github_homepage_metadata")
                hints["source_outbound_urls"].append(homepage)
                hints["resolved_from"].append("metadata")

        direct_domain = _normalize_domain(item.get("domain") or "")
        if direct_domain and source not in {"github"} and not hints["verified_domain"]:
            hints["verified_domain"] = direct_domain
            hints["domain_confidence"] = "High" if source in {"hackernews", "hn"} and outbound_url else "Medium"
            basis = "hn_outbound_url_metadata" if source in {"hackernews", "hn"} and outbound_url else "source_domain_metadata"
            hints["verified_domain_basis"].append(basis)
            hints["resolved_from"].append("metadata")

    for key in (
        "verified_domain_basis",
        "source_outbound_urls",
        "source_titles",
        "maintainers",
        "identity_confidence_basis",
        "resolved_from",
    ):
        hints[key] = list(dict.fromkeys(hints[key]))

    seen_profiles = set()
    profiles = []
    for profile in hints["maintainer_profiles"]:
        key = (profile.get("name"), profile.get("type"), profile.get("url"))
        if key not in seen_profiles:
            profiles.append(profile)
            seen_profiles.add(key)
    hints["maintainer_profiles"] = profiles
    return hints


def score_commercial_intent(
    candidate: Candidate,
    verified_domain: str,
    founders: list[str],
    maintainers: list[str],
    source_titles: list[str] | None = None,
) -> tuple[int, list[str]]:
    score = 20
    basis = []
    text = _text_blob(
        candidate.name,
        candidate.why_on_radar,
        candidate.why_this_may_be_noise,
        candidate.source_lane,
        source_titles or [],
    )
    if any(term in text for term in ("pricing", "demo", "waitlist", "customers", "enterprise", "cloud", "hosted", "company", "startup", "contact sales")):
        score += 25
        basis.append("commercial_language_present")
    if verified_domain and "github.com" not in verified_domain:
        score += 20
        basis.append("non_github_domain_present")
    if founders or candidate.company_linkedin or candidate.company_x:
        score += 15
        basis.append("founder_or_company_profile_present")
    if _has_launch_evidence(candidate):
        score += 15
        basis.append("launch_source_present")
    if candidate.candidate_type == "oss_project" and maintainers:
        score += 10
        basis.append("oss_maintainer_identity_present")
    if any(term in text for term in ("side project", "toy", "demo only", "example", "tutorial")):
        score -= 20
        basis.append("side_project_or_demo_language")
    if _is_github_only(candidate):
        score -= 20
        basis.append("github_only_no_domain")
    if any(term in text for term in ("epic games", "freebies", "consumer", "gaming")):
        score -= 15
        basis.append("consumer_or_off_thesis_language")
    return _clamp(score), basis or ["baseline_commercial_intent"]


def score_identity_confidence(
    candidate: Candidate,
    verified_domain: str,
    founders: list[str],
    maintainers: list[str],
    commercial_intent_score: int,
    attio_match_keys: list[str],
    extra_basis: list[str] | None = None,
) -> tuple[int, str, list[str]]:
    score = 20
    basis = list(extra_basis or [])
    text = _text_blob(candidate.name, candidate.why_on_radar)
    if verified_domain:
        score += 35
        basis.append("verified_domain_present")
    if founders or maintainers:
        score += 20
        basis.append("founder_or_maintainer_identity_present")
    if _has_launch_evidence(candidate):
        score += 15
        basis.append("launch_source_present")
    if candidate.company_linkedin or candidate.company_x:
        score += 15
        basis.append("company_social_profile_present")
    if attio_match_keys:
        score += 10
        basis.append("attio_match_key_present")
    if commercial_intent_score >= 60:
        score += 10
        basis.append("commercial_intent_medium_or_better")
    if not verified_domain and not founders and not maintainers:
        score -= 25
        basis.append("missing_domain_and_people")
    if len((candidate.name or "").strip()) <= 2 and not verified_domain:
        score -= 20
        basis.append("inferred_name_only")
    if any(term in text for term in ("consumer", "gaming", "freebies")):
        score -= 15
        basis.append("off_thesis_language")
    score = _clamp(score)
    if score >= 80:
        label = "High"
    elif score >= 55:
        label = "Medium"
    else:
        label = "Low"
    return score, label, list(dict.fromkeys(basis or ["baseline_identity_confidence"]))


def classify_identity(candidate: Candidate, verified_domain: str, commercial_intent_score: int) -> str:
    if verified_domain and commercial_intent_score >= 50:
        return IDENTITY_VERIFIED_COMPANY
    if _has_launch_evidence(candidate):
        return IDENTITY_LAUNCH_NEEDS_IDENTITY
    if candidate.candidate_type == "oss_project" and commercial_intent_score >= 60:
        return IDENTITY_OSS_COMMERCIAL
    if candidate.candidate_type == "oss_project":
        return IDENTITY_OSS_WATCH
    return IDENTITY_INSUFFICIENT


def choose_identity_action(candidate: Candidate, resolution: IdentityResolution) -> str:
    status = (candidate.attio_status or "unknown").lower()
    if status in {"stale", "passed"} and resolution.identity_confidence_score >= 60:
        return ACTION_REFRESH_ATTIO
    if status in {"no_match", "not_found", "new"}:
        has_actionable_identity = bool(resolution.verified_domain) or (
            bool(resolution.founders or resolution.maintainers)
            and "launch_source_present" in resolution.identity_confidence_basis
        )
        if (
            resolution.identity_confidence_score >= 70
            and resolution.commercial_intent_score >= 50
            and resolution.attio_safe_to_match
            and has_actionable_identity
        ):
            return ACTION_ASSIGN_OWNER
        return ACTION_RESEARCH_DEEPER
    if status in {"unknown", ""}:
        if resolution.identity_confidence_score >= 70 and resolution.commercial_intent_score >= 60:
            return ACTION_RESEARCH_DEEPER
        return ACTION_MONITOR_ONLY
    if resolution.identity_confidence_score < 45 or resolution.commercial_intent_score < 35:
        return ACTION_MONITOR_ONLY
    return ACTION_RESEARCH_DEEPER


def resolve_candidate_identity(candidate: Candidate, fetch_cache: dict | None = None, hn_cache: dict | None = None) -> IdentityResolution:
    urls = _source_urls(candidate)
    metadata_hints = resolve_from_evidence_metadata(candidate)
    has_hn_item_url = any("news.ycombinator.com/item" in url for url in urls)
    needs_live_hn_fallback = not metadata_hints.get("verified_domain") and has_hn_item_url
    should_parse_existing_urls = not has_hn_item_url or needs_live_hn_fallback
    url_hints = resolve_from_existing_urls(candidate, fetch_cache=fetch_cache, hn_cache=hn_cache) if should_parse_existing_urls else {
        "verified_domain": "",
        "domain_confidence": "Low",
        "verified_domain_basis": [],
        "project_url": "",
        "source_outbound_urls": [],
        "source_titles": [],
        "fetch_warnings": [],
        "identity_confidence_basis": [],
        "resolved_from": [],
    }
    candidate_domain = _normalize_domain(candidate.domain)
    verified_domain = metadata_hints.get("verified_domain") or url_hints.get("verified_domain") or candidate_domain
    if metadata_hints.get("verified_domain"):
        domain_confidence = metadata_hints.get("domain_confidence") or "Medium"
    elif url_hints.get("verified_domain"):
        domain_confidence = url_hints.get("domain_confidence") or "Medium"
    else:
        domain_confidence = "Medium" if candidate_domain else "Low"
    verified_domain_basis = list(metadata_hints.get("verified_domain_basis") or []) + list(url_hints.get("verified_domain_basis") or [])
    if candidate_domain and not verified_domain_basis:
        verified_domain_basis.append("candidate_domain_present")
    founders, maintainers = _founder_or_maintainer_names(candidate)
    for maintainer in metadata_hints.get("maintainers") or []:
        if maintainer and maintainer not in maintainers:
            maintainers.append(maintainer)
    attio_match_keys = [key for key in [verified_domain, candidate.name] if key]
    source_titles = list(dict.fromkeys(list(metadata_hints.get("source_titles") or []) + list(url_hints.get("source_titles") or [])))
    commercial_score, commercial_basis = score_commercial_intent(
        candidate,
        verified_domain,
        founders,
        maintainers,
        source_titles=source_titles,
    )
    confidence_score, confidence, confidence_basis = score_identity_confidence(
        candidate,
        verified_domain,
        founders,
        maintainers,
        commercial_score,
        attio_match_keys,
        extra_basis=list(metadata_hints.get("identity_confidence_basis") or []) + list(url_hints.get("identity_confidence_basis") or []),
    )
    missing = []
    if not verified_domain:
        missing.append("no verified domain")
    if not founders and not maintainers:
        missing.append("no founder or maintainer identity")
    identity_type = classify_identity(candidate, verified_domain, commercial_score)
    resolution = IdentityResolution(
        candidate_key=candidate.stable_key or candidate.name,
        original_name=candidate.name,
        resolved_name=candidate.name,
        identity_type=identity_type,
        candidate_domain=candidate_domain,
        verified_domain=verified_domain,
        domain_confidence=domain_confidence,
        verified_domain_basis=verified_domain_basis,
        project_url=metadata_hints.get("project_url") or url_hints.get("project_url") or next((url for url in urls if "github.com" in url), ""),
        company_linkedin=candidate.company_linkedin,
        company_x=candidate.company_x,
        founders=founders,
        founder_profiles=list(candidate.founder_profiles or []),
        maintainers=maintainers,
        maintainer_profiles=list(candidate.maintainer_profiles or []) + list(metadata_hints.get("maintainer_profiles") or []),
        commercial_intent_score=commercial_score,
        commercial_intent_basis=commercial_basis,
        identity_confidence_score=confidence_score,
        identity_confidence=confidence,
        identity_confidence_basis=confidence_basis,
        attio_match_keys=attio_match_keys,
        attio_safe_to_match=bool(verified_domain),
        missing_identity_evidence=missing,
        evidence_urls=urls,
        source_outbound_urls=list(dict.fromkeys(list(metadata_hints.get("source_outbound_urls") or []) + list(url_hints.get("source_outbound_urls") or []))),
        source_titles=source_titles,
        fetch_warnings=list(url_hints.get("fetch_warnings") or []),
        resolved_from=list(dict.fromkeys(["candidate_fields"] + list(metadata_hints.get("resolved_from") or []) + list(url_hints.get("resolved_from") or []))),
    )
    resolution.recommended_identity_action = choose_identity_action(candidate, resolution)
    return resolution


def apply_identity_to_candidate(candidate: Candidate, resolution: IdentityResolution) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    if resolution.verified_domain:
        out.domain = resolution.verified_domain
    if resolution.company_linkedin:
        out.company_linkedin = resolution.company_linkedin
    if resolution.company_x:
        out.company_x = resolution.company_x
    if resolution.founders:
        out.founders = list(resolution.founders)
    if resolution.founder_profiles:
        out.founder_profiles = list(resolution.founder_profiles)
    if resolution.maintainer_profiles:
        out.maintainer_profiles = list(resolution.maintainer_profiles)
    out.identity_type = resolution.identity_type
    out.candidate_domain = resolution.candidate_domain
    out.domain_confidence = resolution.domain_confidence
    out.verified_domain_basis = list(resolution.verified_domain_basis)
    out.identity_confidence_score = resolution.identity_confidence_score
    out.identity_confidence = resolution.identity_confidence
    out.identity_confidence_basis = list(resolution.identity_confidence_basis)
    out.commercial_intent_score = resolution.commercial_intent_score
    out.commercial_intent_basis = list(resolution.commercial_intent_basis)
    out.attio_match_keys = list(resolution.attio_match_keys)
    out.attio_safe_to_match = resolution.attio_safe_to_match
    out.recommended_identity_action = resolution.recommended_identity_action
    out.missing_identity_evidence = list(resolution.missing_identity_evidence)
    out.source_outbound_urls = list(resolution.source_outbound_urls)
    out.source_titles = list(resolution.source_titles)
    out.fetch_warnings = list(resolution.fetch_warnings)
    out.identity_resolved_from = list(resolution.resolved_from)
    return out


def apply_identity_resolution(candidates: list[Candidate]) -> tuple[list[Candidate], list[IdentityResolution]]:
    resolved_candidates = []
    resolutions = []
    fetch_cache: dict[str, str] = {}
    hn_cache = load_hn_enrichment_cache()
    for candidate in candidates:
        resolution = resolve_candidate_identity(candidate, fetch_cache=fetch_cache, hn_cache=hn_cache)
        resolutions.append(resolution)
        resolved_candidates.append(apply_identity_to_candidate(candidate, resolution))
    save_hn_enrichment_cache(hn_cache)
    return resolved_candidates, resolutions
