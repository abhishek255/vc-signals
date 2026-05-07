from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from radar_focus import ACTION_ASSIGN_OWNER, ACTION_MONITOR_ONLY, ACTION_REFRESH_ATTIO, ACTION_RESEARCH_DEEPER
from radar_models import Candidate, IdentityResolution


IDENTITY_VERIFIED_COMPANY = "verified_company"
IDENTITY_LAUNCH_NEEDS_IDENTITY = "launch_style_needs_identity"
IDENTITY_OSS_COMMERCIAL = "oss_with_commercial_intent"
IDENTITY_OSS_WATCH = "oss_project_watch"
IDENTITY_INSUFFICIENT = "insufficient_identity"


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


def resolve_from_existing_urls(candidate: Candidate, fetch_cache: dict | None = None) -> dict:
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
            try:
                html = fetch_existing_url(url, cache=fetch_cache)
                parsed = parse_hn_item(html)
            except Exception as exc:
                hints["fetch_warnings"].append(f"{url}: {exc}")
                continue
            if parsed.get("title"):
                hints["source_titles"].append(parsed["title"])
            outbound_url = parsed.get("outbound_url") or ""
            if outbound_url:
                hints["source_outbound_urls"].append(outbound_url)
                outbound_domain = _domain_from_url(outbound_url)
                if outbound_domain:
                    hints["verified_domain"] = hints["verified_domain"] or outbound_domain
                    hints["domain_confidence"] = "High"
                    hints["verified_domain_basis"].append("hn_outbound_url_domain")
                    hints["resolved_from"].append("hn_item_outbound_url")

    hints["verified_domain_basis"] = list(dict.fromkeys(hints["verified_domain_basis"]))
    hints["identity_confidence_basis"] = list(dict.fromkeys(hints["identity_confidence_basis"]))
    hints["resolved_from"] = list(dict.fromkeys(hints["resolved_from"]))
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


def resolve_candidate_identity(candidate: Candidate, fetch_cache: dict | None = None) -> IdentityResolution:
    urls = _source_urls(candidate)
    url_hints = resolve_from_existing_urls(candidate, fetch_cache=fetch_cache)
    candidate_domain = _normalize_domain(candidate.domain)
    verified_domain = url_hints.get("verified_domain") or candidate_domain
    domain_confidence = url_hints.get("domain_confidence") or ("Medium" if candidate_domain else "Low")
    verified_domain_basis = list(url_hints.get("verified_domain_basis") or [])
    if candidate_domain and not verified_domain_basis:
        verified_domain_basis.append("candidate_domain_present")
    founders, maintainers = _founder_or_maintainer_names(candidate)
    attio_match_keys = [key for key in [verified_domain, candidate.name] if key]
    source_titles = list(url_hints.get("source_titles") or [])
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
        extra_basis=list(url_hints.get("identity_confidence_basis") or []),
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
        project_url=url_hints.get("project_url") or next((url for url in urls if "github.com" in url), ""),
        company_linkedin=candidate.company_linkedin,
        company_x=candidate.company_x,
        founders=founders,
        founder_profiles=list(candidate.founder_profiles or []),
        maintainers=maintainers,
        maintainer_profiles=list(candidate.maintainer_profiles or []),
        commercial_intent_score=commercial_score,
        commercial_intent_basis=commercial_basis,
        identity_confidence_score=confidence_score,
        identity_confidence=confidence,
        identity_confidence_basis=confidence_basis,
        attio_match_keys=attio_match_keys,
        attio_safe_to_match=bool(verified_domain),
        missing_identity_evidence=missing,
        evidence_urls=urls,
        source_outbound_urls=list(url_hints.get("source_outbound_urls") or []),
        source_titles=source_titles,
        fetch_warnings=list(url_hints.get("fetch_warnings") or []),
        resolved_from=list(dict.fromkeys(["candidate_fields"] + list(url_hints.get("resolved_from") or []))),
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
    for candidate in candidates:
        resolution = resolve_candidate_identity(candidate, fetch_cache=fetch_cache)
        resolutions.append(resolution)
        resolved_candidates.append(apply_identity_to_candidate(candidate, resolution))
    return resolved_candidates, resolutions
