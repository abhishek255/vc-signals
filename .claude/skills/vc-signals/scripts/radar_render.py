from __future__ import annotations


def render_weekly_brief(candidates: list, coverage: dict, rejected: list) -> str:
    partner = [candidate for candidate in candidates if candidate.tier == "Partner Review"][:15]
    if not partner:
        partner = [candidate for candidate in candidates if candidate.tier == "Watchlist"][:15]

    lines = [
        "# VC Signals Weekly Radar",
        "",
        "## Partner Review",
        "",
        _table(partner),
        "",
        "## Full Radar",
        "",
        _table(candidates[:50]),
        "",
        "## Sector Coverage",
        "",
    ]

    for sector, item in coverage.items():
        lines.append(f"- **{sector}: {item.status}** - {item.reason or 'Qualified candidates found.'}")

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
        "| Company / Project | Sector | Theme | Tier | Interest | Evidence | Attio | Action | LinkedIn | Founders | X | Why On Radar | Why This May Be Noise | Best Source |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for candidate in candidates:
        rows.append(
            f"| {candidate.name} | {candidate.sector} | {candidate.theme} | {candidate.tier} | "
            f"{candidate.investment_interest} | {candidate.evidence_confidence} | {candidate.attio_status} | "
            f"{candidate.action} | {candidate.company_linkedin} | {_founders(candidate.founder_profiles)} | "
            f"{candidate.company_x} | {candidate.why_on_radar} | {candidate.why_this_may_be_noise} | {candidate.source} |"
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
