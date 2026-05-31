from __future__ import annotations

from radar_models import Signal


SOURCE_LANE_LABELS = {
    "reddit": "Reddit",
    "hackernews": "Hacker News",
    "github": "OSS",
    "producthunt": "Product Hunt",
    "product_hunt": "Product Hunt",
    "grounding": "Grounded web",
    "web": "Grounded web",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "threads": "Threads",
    "x": "X",
    "twitter": "X",
    "yc_directory": "YC Directory",
    "linkedin": "LinkedIn",
}


def source_lane_for(source: str) -> str:
    normalized = (source or "").lower()
    return SOURCE_LANE_LABELS.get(normalized, source.title() if source else "")


def _metadata_with_source_lane(item: dict, source_lane: str) -> dict:
    metadata = item.copy()
    metadata["source_lane"] = source_lane
    return metadata


def _social_has_company_evidence(item: dict) -> bool:
    has_name = bool((item.get("company_name") or item.get("name") or "").strip())
    if not has_name:
        return False
    return any(
        bool(item.get(key))
        for key in (
            "website",
            "domain",
            "company_linkedin",
            "company_x",
            "founder",
            "founders",
            "waitlist_url",
        )
    )


def classify_source_item(*, sector: str, item: dict) -> Signal:
    source = (item.get("source") or "").lower()
    source_lane = source_lane_for(source)
    title = item.get("title") or item.get("full_name") or item.get("name") or ""
    url = item.get("url", "")
    text = item.get("snippet") or item.get("description") or item.get("text") or ""
    metadata = _metadata_with_source_lane(item, source_lane)

    if source == "reddit":
        return Signal(
            source=source,
            role="pain",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=False,
            evidence_strength=30,
            reason="Reddit pain should support themes/candidates, not directly create company rows.",
            metadata=metadata,
        )

    if source == "hackernews" and title.lower().startswith(("show hn:", "launch hn:")):
        return Signal(
            source=source,
            role="launch",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=True,
            evidence_strength=45,
            reason="HN launch posts can create candidates when the product name is clear.",
            metadata=metadata,
        )

    if source == "github" and ("/issues/" in url or "/pull/" in url):
        return Signal(
            source=source,
            role="activity",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=False,
            evidence_strength=20,
            reason="GitHub issues and PRs are activity evidence, not company/project candidates.",
            metadata=metadata,
        )

    if source == "github":
        return Signal(
            source=source,
            role="oss_project",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=True,
            evidence_strength=45,
            reason="GitHub repo results can create OSS project candidates.",
            metadata=metadata,
        )

    if source in {"producthunt", "product_hunt"}:
        return Signal(
            source="producthunt",
            role="producthunt_launch",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=True,
            evidence_strength=45,
            reason="Product Hunt launches can create weak company-formation candidates for research, not owner routing.",
            metadata=metadata,
        )

    if source == "yc_directory":
        has_official_domain = bool(item.get("domain") or item.get("website"))
        return Signal(
            source=source,
            role="yc_company",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=has_official_domain,
            evidence_strength=60 if has_official_domain else 35,
            reason=(
                "YC directory rows with official website/domain can create research candidates."
                if has_official_domain
                else "YC directory row needs official website/domain before candidate creation."
            ),
            metadata=metadata,
        )

    if source in {"x", "twitter"}:
        can_create_candidate = _social_has_company_evidence(item)
        return Signal(
            source="x",
            role="social_launch",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=can_create_candidate,
            evidence_strength=45 if can_create_candidate else 30,
            reason=(
                "X launch posts with company evidence can create research candidates."
                if can_create_candidate
                else "X social evidence supports launch confidence, but needs company evidence before creating rows."
            ),
            metadata=metadata,
        )

    if source in {"youtube", "tiktok", "instagram", "threads"}:
        can_create_candidate = _social_has_company_evidence(item)
        return Signal(
            source=source,
            role="product_demo" if can_create_candidate else "social_demo",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=can_create_candidate,
            evidence_strength=40 if can_create_candidate else 25,
            reason=(
                "Social/video product demos with company evidence can create candidates."
                if can_create_candidate
                else "Social/video evidence supports demos or demand, but needs company evidence before creating rows."
            ),
            metadata=metadata,
        )

    if source in {"grounding", "web"}:
        return Signal(
            source=source,
            role="company_web",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=True,
            evidence_strength=55,
            reason="Grounded web/company pages can create company candidates.",
            metadata=metadata,
        )

    return Signal(source=source, role="unknown", title=title, url=url, sector=sector, text=text, metadata=metadata)
