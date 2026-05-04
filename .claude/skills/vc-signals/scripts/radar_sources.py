from __future__ import annotations

from radar_models import Signal


def classify_source_item(*, sector: str, item: dict) -> Signal:
    source = (item.get("source") or "").lower()
    title = item.get("title") or item.get("full_name") or item.get("name") or ""
    url = item.get("url", "")
    text = item.get("snippet") or item.get("description") or item.get("text") or ""

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
            metadata=item.copy(),
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
            metadata=item.copy(),
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
            metadata=item.copy(),
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
            metadata=item.copy(),
        )

    if source in {"youtube", "tiktok", "instagram", "threads"}:
        return Signal(
            source=source,
            role="social_demo",
            title=title,
            url=url,
            sector=sector,
            text=text,
            can_create_candidate=False,
            evidence_strength=25,
            reason="Social/video evidence supports demos or demand, but should not alone create company rows.",
            metadata=item.copy(),
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
            metadata=item.copy(),
        )

    return Signal(source=source, role="unknown", title=title, url=url, sector=sector, text=text, metadata=item.copy())
