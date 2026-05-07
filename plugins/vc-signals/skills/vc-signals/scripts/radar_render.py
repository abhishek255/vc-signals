from __future__ import annotations

from types import SimpleNamespace


def render_weekly_brief(
    candidates: list,
    coverage: dict,
    rejected: list,
    *,
    faded: list[dict] | None = None,
    theme_signals: list | None = None,
    sector_intelligence: list | None = None,
    partner_review: list | None = None,
    synthesis=None,
    company_discovery: dict | None = None,
) -> str:
    partner = partner_review if partner_review is not None else [candidate for candidate in candidates if candidate.tier == "Partner Review"][:15]
    if partner_review is None and not partner:
        partner = [candidate for candidate in candidates if candidate.tier == "Watchlist"][:15]

    lines = [
        "# VC Signals Weekly Radar",
        "",
        _run_summary(candidates),
        "",
        "## Partner Review",
        "",
        _partner_table(partner),
    ]

    lines.extend([
        "",
        "## Full Radar",
        "",
        _table(candidates[:50]),
        "",
        "## Faded Off Radar",
        "",
        _faded_table(faded or []),
        "",
        _sector_intelligence_section(sector_intelligence or _coverage_intelligence_items(coverage)),
        "",
        _theme_signals_table(theme_signals or []),
        "",
        _company_discovery_section(company_discovery),
    ])
    synthesis_notes = _synthesis_section(synthesis)
    if synthesis_notes:
        lines.extend(["", synthesis_notes])
    if coverage:
        lines.extend(["", _legacy_sector_coverage_section(coverage)])

    lines.extend(["", "## Weak Evidence / Rejected Summary", ""])
    reason_counts = {}
    for item in rejected:
        reason_counts[item.reason] = reason_counts.get(item.reason, 0) + 1
    if reason_counts:
        for reason, count in sorted(reason_counts.items()):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- No rejected signals.")

    needs_more = [candidate for candidate in candidates if candidate.tier == "Needs More Evidence"]
    if needs_more:
        lines.extend(["", "### Needs More Evidence", ""])
        for candidate in needs_more[:15]:
            lines.append(f"- **{candidate.name}** ({candidate.sector}): {candidate.why_on_radar}")

    return "\n".join(lines).rstrip() + "\n"


def _table(candidates: list) -> str:
    rows = [
        "| Company / Project | Market Sector | Source Lane | Theme | Tag | Stage | Raised | Headcount | Founders | Tier | Interest | Evidence | Attio | Attio Owner | Attio Last Touch | Attio URL | Staleness | Action | OSS Score | Action Reason | LinkedIn | X | Why On Radar | Why This May Be Noise | Best Source |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for candidate in candidates:
        rows.append(
            f"| {candidate.name} | {_market_sector(candidate)} | {_source_lane(candidate)} | {candidate.theme} | {candidate.weekly_tag} | "
            f"{candidate.stage} | {candidate.raised} | {candidate.headcount} | {_enriched_founders(candidate)} | {candidate.tier} | "
            f"{candidate.investment_interest} | {candidate.evidence_confidence} | {candidate.attio_status} | "
            f"{candidate.attio_owner} | {candidate.attio_last_interaction} | {candidate.attio_record_url} | {candidate.attio_staleness_reason} | "
            f"{candidate.action} | {_oss_score(candidate)} | {candidate.oss_action_reason} | {candidate.company_linkedin} | "
            f"{candidate.company_x} | {candidate.why_on_radar} | {candidate.why_this_may_be_noise} | {candidate.source} |"
        )
    return "\n".join(rows)


def _run_summary(candidates: list) -> str:
    market_sectors = sorted({_market_sector(candidate) for candidate in candidates if _market_sector(candidate)})
    source_counts = {}
    for candidate in candidates:
        lane = _source_lane(candidate) or "Unknown"
        source_counts[lane] = source_counts.get(lane, 0) + 1
    source_mix = ", ".join(f"{count} {lane}" for lane, count in sorted(source_counts.items(), key=lambda item: item[0]))
    lines = [
        "## Run Summary",
        "",
        f"This run produced {len(candidates)} qualified {_plural(len(candidates), 'row')} across {len(market_sectors)} market {_plural(len(market_sectors), 'sector')}.",
        f"Source mix: {source_mix or 'No qualified source lanes.'}.",
    ]
    if candidates and all(_source_lane(candidate) == "OSS" for candidate in candidates):
        lines.append("Warning: this run is OSS-heavy; non-OSS company discovery did not produce qualified rows.")
    return "\n".join(lines)


def _partner_table(candidates: list) -> str:
    rows = [
        "| Company / Project | Market Sector | Source Lane | Theme | Tag | Tier | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for candidate in candidates:
        rows.append(
            f"| {candidate.name} | {_market_sector(candidate)} | {_source_lane(candidate)} | {candidate.theme} | "
            f"{candidate.weekly_tag} | {candidate.tier} | {candidate.investment_interest} | {candidate.evidence_confidence} | "
            f"{candidate.attio_status} | {candidate.action} | {candidate.why_on_radar} | {candidate.why_this_may_be_noise} |"
        )
    return "\n".join(rows)


def _market_sector(candidate) -> str:
    return getattr(candidate, "market_sector", "") or getattr(candidate, "sector", "")


def _source_lane(candidate) -> str:
    lane = getattr(candidate, "source_lane", "")
    if lane:
        return lane

    source = getattr(candidate, "source", "") or ""
    sector = getattr(candidate, "sector", "") or ""
    source_lower = source.lower()
    if sector == "OSS" or source_lower in {"oss", "github"} or "github.com" in source_lower:
        return "OSS"
    if source and not source_lower.startswith(("http://", "https://")):
        return source
    return "Unknown"


def _sector_intelligence_section(items: list) -> str:
    if not items:
        return "## Sector Intelligence\n\n- No sector intelligence generated."

    lines = ["## Sector Intelligence", ""]
    for item in items:
        lines.extend(
            [
                f"### {item.market_sector}",
                f"Status: {item.status}",
                f"Signals: {item.raw_signals} raw, {item.candidate_eligible_signals} candidate-eligible, {item.promoted_candidates} promoted, {item.rejected_signals} rejected.",
                f"Best evidence: {item.best_evidence or 'No promoted evidence.'}",
                f"Why no more companies: {item.why_no_more_companies or 'Qualified candidates were found.'}",
                f"Next hunt: {item.next_hunt or 'No follow-up search suggested.'}",
            ]
        )
        if item.source_errors:
            lines.append("Source errors: " + "; ".join(item.source_errors))
        lines.append("")
    return "\n".join(lines).rstrip()


def _coverage_intelligence_items(coverage: dict) -> list:
    items = []
    for sector, item in coverage.items():
        items.append(
            SimpleNamespace(
                market_sector=sector,
                status=item.status,
                raw_signals=item.raw_signals,
                candidate_eligible_signals=item.candidates,
                promoted_candidates=item.candidates,
                rejected_signals=item.rejected,
                best_evidence="",
                why_no_more_companies=item.reason,
                next_hunt="",
                source_errors=[],
            )
        )
    return items


def _legacy_sector_coverage_section(coverage: dict) -> str:
    lines = [
        "## Sector Coverage",
        "",
        "_Compatibility view; see Sector Intelligence for the V3 market map._",
        "",
    ]
    for sector, item in coverage.items():
        lines.append(f"- **{sector}: {item.status}** - {item.reason or 'Qualified candidates found.'}")
    return "\n".join(lines)


def _plural(count: int, singular: str) -> str:
    if singular == "query":
        return "query" if count == 1 else "queries"
    return singular if count == 1 else f"{singular}s"


def _theme_signals_table(theme_signals: list) -> str:
    if not theme_signals:
        return "## Themes With No Company Yet\n\n- No meaningful non-company themes met the evidence bar."

    rows = [
        "## Themes With No Company Yet",
        "",
        "| Market Sector | Theme | Evidence | Why It Matters | Why No Company Yet | Suggested Search |",
        "|---|---|---|---|---|---|",
    ]
    for item in theme_signals[:8]:
        rows.append(
            f"| {item.market_sector} | {item.theme} | {item.evidence_summary} | {item.why_it_matters} | "
            f"{item.why_no_company_yet} | {item.suggested_search} |"
        )
    return "\n".join(rows)


def _markdown_table_cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("\n", " ").replace("\t", " ").replace("|", "\\|")


def _company_discovery_section(company_discovery: dict | None) -> str:
    if not company_discovery:
        return "## Company Discovery From Themes\n\n- Theme-driven company discovery did not run."

    queries = company_discovery.get("queries", [])
    items = company_discovery.get("items", [])
    warnings = company_discovery.get("warnings", [])
    errors = company_discovery.get("errors", [])
    lines = [
        "## Company Discovery From Themes",
        "",
        f"Searched {len(queries)} targeted theme-company {_plural(len(queries), 'query')} and found {len(items)} qualified evidence {_plural(len(items), 'item')}.",
    ]
    if warnings or errors:
        for warning in warnings[:5]:
            lines.append(f"- Warning: {warning}")
        for error in errors[:5]:
            lines.append(f"- Error: {error}")
    if not items:
        lines.append("- No company rows cleared the evidence bar from theme-driven discovery.")
        return "\n".join(lines)

    lines.extend(
        [
            "",
            "| Company | Market Sector | Theme | Source | Evidence URL | Query |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in items[:15]:
        company = item.get("company_name") or item.get("name") or item.get("title") or "Unknown"
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(company),
                    _markdown_table_cell(item.get("market_sector")),
                    _markdown_table_cell(item.get("query_theme")),
                    _markdown_table_cell(item.get("source")),
                    _markdown_table_cell(item.get("url")),
                    _markdown_table_cell(item.get("query_topic")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _synthesis_section(synthesis) -> str:
    if not synthesis or not getattr(synthesis, "enabled", False):
        return ""

    has_content = any(
        [
            getattr(synthesis, "partner_notes", []),
            getattr(synthesis, "sector_diagnoses", []),
            getattr(synthesis, "theme_hypotheses", []),
            getattr(synthesis, "possible_company_leads", []),
            getattr(synthesis, "warnings", []),
        ]
    )
    if not has_content:
        return ""

    lines = ["## LLM Synthesis Notes", ""]
    model = getattr(synthesis, "model", "")
    if model:
        lines.extend([f"Model: {model}", ""])

    partner_notes = getattr(synthesis, "partner_notes", [])
    if partner_notes:
        for note in partner_notes:
            lines.append(f"- {note}")
        lines.append("")

    sector_diagnoses = getattr(synthesis, "sector_diagnoses", [])
    if sector_diagnoses:
        lines.extend(["### Source Gap Diagnosis", ""])
        for item in sector_diagnoses:
            line = f"- {item.market_sector}: {item.diagnosis}"
            confidence = getattr(item, "confidence", "")
            if confidence:
                line += f" ({confidence})"
            next_queries = getattr(item, "recommended_next_queries", [])
            if next_queries:
                line += f"; next queries: {'; '.join(next_queries)}"
            evidence_urls = getattr(item, "evidence_urls", [])
            if evidence_urls:
                line += f"; evidence: {', '.join(evidence_urls)}"
            lines.append(line)
        lines.append("")

    theme_hypotheses = getattr(synthesis, "theme_hypotheses", [])
    if theme_hypotheses:
        lines.extend(
            [
                "### Theme Hypotheses",
                "",
                "| Market Sector | Theme | Evidence | Evidence URLs | Why It Matters | Why This May Be Noise | Confidence |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for theme in theme_hypotheses:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_table_cell(getattr(theme, "market_sector", "")),
                        _markdown_table_cell(getattr(theme, "theme", "")),
                        _markdown_table_cell(getattr(theme, "evidence_summary", "")),
                        _markdown_table_cell(", ".join(getattr(theme, "evidence_urls", []))),
                        _markdown_table_cell(getattr(theme, "why_it_matters", "")),
                        _markdown_table_cell(getattr(theme, "why_this_may_be_noise", "")),
                        _markdown_table_cell(getattr(theme, "confidence", "")),
                    ]
                )
                + " |"
            )
        lines.append("")

    possible_leads = getattr(synthesis, "possible_company_leads", [])
    if possible_leads:
        lines.extend(
            [
                "### Possible Companies Requiring Verification",
                "",
                "| Company | Market Sector | Source Lane | Evidence | Why On Radar | Verification Needed | Suggested Action | Confidence |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for lead in possible_leads:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_table_cell(getattr(lead, "name", "")),
                        _markdown_table_cell(getattr(lead, "market_sector", "")),
                        _markdown_table_cell(getattr(lead, "source_lane", "")),
                        _markdown_table_cell(", ".join(getattr(lead, "evidence_urls", []))),
                        _markdown_table_cell(getattr(lead, "why_on_radar", "")),
                        _markdown_table_cell("; ".join(getattr(lead, "verification_needed", []))),
                        _markdown_table_cell(getattr(lead, "suggested_action", "")),
                        _markdown_table_cell(getattr(lead, "confidence", "")),
                    ]
                )
                + " |"
            )
        lines.append("")

    warnings = getattr(synthesis, "warnings", [])
    if warnings:
        lines.extend(["### Synthesis Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines).rstrip()


def _faded_table(faded: list[dict]) -> str:
    if not faded:
        return "- No previously tracked candidates faded this week."
    rows = [
        "| Company / Project | Sector | Theme | Tag | Last Seen | Best Source |",
        "|---|---|---|---|---|---|",
    ]
    for item in faded:
        rows.append(
            f"| {item.get('name', '')} | {item.get('sector', '')} | {item.get('theme', '')} | "
            f"{item.get('weekly_tag', 'FADED')} | {item.get('last_seen', '')} | {item.get('source', '')} |"
        )
    return "\n".join(rows)


def _founders(founders: list[dict]) -> str:
    out = []
    for founder in founders:
        name = founder.get("name") or "Founder"
        links = [founder.get("linkedin"), founder.get("x"), founder.get("github")]
        links = [link for link in links if link]
        out.append(f"{name}: {', '.join(links)}" if links else name)
    return "; ".join(out)


def _enriched_founders(candidate) -> str:
    if candidate.founders:
        return "; ".join(candidate.founders)
    return _founders(candidate.founder_profiles)


def _oss_score(candidate) -> str:
    return str(candidate.oss_company_formation_score) if candidate.oss_company_formation_score else ""
