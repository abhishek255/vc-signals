from __future__ import annotations

from radar_models import Candidate, RejectedSignal, SectorCoverage, SectorIntelligence, ThemeSignal


MARKET_SECTOR_LABELS = {
    "devtools": "Devtools",
    "cybersecurity": "Cybersecurity",
    "ai-infra": "AI Infra",
    "vertical-ai": "Vertical AI",
    "data-infra": "Data Infra",
    "oss": "OSS",
}


def _label(sector: str) -> str:
    return MARKET_SECTOR_LABELS.get(sector, sector)


def _slug(label: str) -> str:
    return label.strip().lower().replace(" ", "-")


def _sector_candidates(candidates: list[Candidate], market_sector: str, sector_slug: str) -> list[Candidate]:
    normalized_market = _slug(market_sector)
    return [
        candidate
        for candidate in candidates
        if _slug(candidate.market_sector or candidate.sector) in {normalized_market, sector_slug}
    ]


def _sector_themes(theme_signals: list[ThemeSignal], market_sector: str, sector_slug: str) -> list[ThemeSignal]:
    normalized_market = _slug(market_sector)
    return [
        theme
        for theme in theme_signals
        if _slug(theme.market_sector) in {normalized_market, sector_slug}
    ]


def _sector_rejections(rejected: list[RejectedSignal], market_sector: str, sector_slug: str) -> list[RejectedSignal]:
    normalized_market = _slug(market_sector)
    return [
        item
        for item in rejected
        if _slug(item.sector) in {normalized_market, sector_slug}
    ]


def build_sector_intelligence(
    *,
    sectors: tuple[str, ...],
    coverage: dict[str, SectorCoverage],
    candidates: list[Candidate],
    rejected: list[RejectedSignal],
    theme_signals: list[ThemeSignal],
    source_errors: dict[str, list[str]],
    grounded_available: bool,
) -> list[SectorIntelligence]:
    """Summarize every requested market sector, including no-company pain."""
    out: list[SectorIntelligence] = []

    for sector in sectors:
        if sector == "oss":
            continue

        market_sector = _label(sector)
        cov = coverage.get(sector, SectorCoverage(sector=sector))
        sector_candidates = _sector_candidates(candidates, market_sector, sector)
        sector_rejected = _sector_rejections(rejected, market_sector, sector)
        sector_themes = _sector_themes(theme_signals, market_sector, sector)
        errors = source_errors.get(sector, [])
        source_lanes = sorted({candidate.source_lane for candidate in sector_candidates if candidate.source_lane})
        company_candidates = [candidate for candidate in sector_candidates if candidate.candidate_type != "oss_project"]

        if company_candidates:
            status = "Company candidates found"
        elif sector_candidates:
            status = "OSS/project candidates found"
        elif sector_themes:
            status = "Pain signal, no company yet"
        elif errors:
            status = "Source failure / incomplete coverage"
        else:
            status = "No meaningful signal this week"

        if sector_candidates:
            best_evidence = f"{len(sector_candidates)} promoted rows from {', '.join(source_lanes) or 'available sources'}."
        elif sector_themes:
            best_evidence = sector_themes[0].evidence_summary
        elif errors:
            best_evidence = "Source collection returned errors before enough evidence could be promoted."
        else:
            best_evidence = "No promoted candidate evidence."

        why_no_more = ""
        if not sector_candidates:
            why_no_more = "No verified company/domain/founder evidence appeared in this run."
            if not grounded_available:
                why_no_more += " Grounded company discovery is not configured, so non-OSS company discovery is limited."
        elif not company_candidates:
            why_no_more = "Promoted rows are OSS/project evidence; no verified company pages or funding/company discovery rows qualified."
            if not grounded_available:
                why_no_more += " Grounded company discovery is not configured, so non-OSS company discovery is limited."

        next_hunt = (
            sector_themes[0].suggested_search
            if sector_themes
            else f"{market_sector} startups Seed Series A founder launch"
        )
        candidate_eligible = len(sector_candidates) + sum(
            1 for item in sector_rejected if item.reason != "source_not_candidate_eligible"
        )

        out.append(
            SectorIntelligence(
                market_sector=market_sector,
                status=status,
                raw_signals=cov.raw_signals,
                candidate_eligible_signals=candidate_eligible,
                promoted_candidates=len(sector_candidates),
                rejected_signals=len(sector_rejected) or cov.rejected,
                best_evidence=best_evidence,
                why_no_more_companies=why_no_more,
                next_hunt=next_hunt,
                source_errors=errors,
            )
        )

    return out
