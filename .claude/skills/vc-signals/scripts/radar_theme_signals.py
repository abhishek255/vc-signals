from __future__ import annotations

from collections import defaultdict

from radar_models import Signal, ThemeSignal
from radar_sector_classifier import classify_market_sector


NOISE_TERMS = (
    "remote job",
    "[hiring]",
    "hiring",
    "job -",
    "jobs thread",
    "salary",
    "review my resume",
    "resume review",
    "roast my resume",
    "daily digest",
    "weekly digest",
    "news roundup",
    "statistics of the week",
    "course",
    "tutorial",
    "beginner guide",
)

UNNAMED_SOCIAL_HYPE_TERMS = (
    "unnamed",
    "insane",
    "changed my workflow forever",
    "productivity hack",
    "you need this",
    "mind blowing",
    "game changer",
)

THEME_KEYWORDS = (
    (("security", "permission", "permissions", "phishing", "soc", "appsec"), "AI agent security"),
    (("mcp", "runtime", "tool server", "agent protocol"), "Agent runtime infrastructure"),
    (("lineage", "data quality", "warehouse", "etl", "pipeline", "dbt"), "AI data infrastructure"),
    (("workflow", "sales", "legal", "healthcare", "operator", "front desk"), "Vertical AI operations"),
    (("eval", "evaluation", "testing", "simulation", "reliability"), "Agent reliability and evals"),
)

THEME_LIMIT = 8
THEME_ELIGIBLE_SOURCES = {"reddit", "github", "hackernews", "youtube", "tiktok", "instagram", "threads"}


def _sector_label(sector: str) -> str:
    return {
        "devtools": "Devtools",
        "cybersecurity": "Cybersecurity",
        "ai-infra": "AI Infra",
        "vertical-ai": "Vertical AI",
        "data-infra": "Data Infra",
        "oss": "OSS",
    }.get(sector, sector)


def _text(signal: Signal) -> str:
    return " ".join(
        str(part)
        for part in (
            signal.title,
            signal.text,
            signal.metadata.get("description", ""),
            " ".join(signal.metadata.get("topics", []) if isinstance(signal.metadata.get("topics"), list) else []),
        )
        if part
    )


def _is_noise(signal: Signal) -> bool:
    text = _text(signal).lower()
    if any(term in text for term in NOISE_TERMS):
        return True
    if signal.source in {"youtube", "tiktok", "instagram", "threads"}:
        has_named_product = bool(
            (signal.metadata.get("company_name") or signal.metadata.get("name") or signal.metadata.get("product_name") or "").strip()
        )
        if not has_named_product and any(term in text for term in UNNAMED_SOCIAL_HYPE_TERMS):
            return True
    return False


def infer_theme_from_text(text: str) -> str:
    lower = text.lower()
    for keywords, theme in THEME_KEYWORDS:
        if any(keyword in lower for keyword in keywords):
            return theme
    return "Emerging technical signal"


def _market_sector_for(signal: Signal) -> str:
    source_lane = signal.metadata.get("source_lane", signal.source)
    classification = classify_market_sector(title=signal.title, text=_text(signal), source_lane=source_lane)
    if classification.market_sector != "Unclassified":
        return classification.market_sector
    return _sector_label(signal.sector) if signal.sector else "Unclassified"


def _qualifies(items: list[Signal]) -> bool:
    urls_or_titles = {item.url or item.title for item in items}
    sources = {item.source for item in items}
    if len(urls_or_titles) >= 2:
        return True
    return len(items) >= 2 and len(sources) >= 2


def build_theme_signals(signals: list[Signal], *, sectors: tuple[str, ...]) -> list[ThemeSignal]:
    """Convert clustered non-candidate evidence into partner-useful hunt prompts."""
    requested = set(sectors)
    grouped: dict[tuple[str, str], list[Signal]] = defaultdict(list)

    for signal in signals:
        if signal.can_create_candidate:
            continue
        if requested and signal.sector not in requested and "all" not in requested:
            continue
        if signal.source not in THEME_ELIGIBLE_SOURCES:
            continue
        if _is_noise(signal):
            continue

        text = _text(signal)
        grouped[(_market_sector_for(signal), infer_theme_from_text(text))].append(signal)

    out: list[ThemeSignal] = []
    for (market_sector, theme), items in grouped.items():
        if not _qualifies(items):
            continue
        source_lanes = sorted({item.metadata.get("source_lane", item.source.title()) for item in items if item.source})
        evidence_summary = "; ".join(item.title for item in items[:3])
        out.append(
            ThemeSignal(
                market_sector=market_sector,
                theme=theme,
                source_lanes=source_lanes,
                evidence_count=len(items),
                evidence_summary=evidence_summary,
                why_it_matters=f"Repeated non-company signal suggests buyer/operator pain around {theme}.",
                why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
                suggested_search=f"{theme} startups Seed Series A founder launch",
                confidence="Medium" if len(items) >= 2 else "Low",
            )
        )

    return sorted(
        out,
        key=lambda item: (item.confidence == "Medium", item.evidence_count, item.market_sector, item.theme),
        reverse=True,
    )[:THEME_LIMIT]
