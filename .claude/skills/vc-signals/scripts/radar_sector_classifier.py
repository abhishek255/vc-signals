from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SectorClassification:
    market_sector: str
    sector_confidence: str
    sector_reason: str


SECTOR_KEYWORDS = {
    "Cybersecurity": (
        "penetration testing",
        "security scanner",
        "prompt injection",
        "mcp permissions",
        "api security",
        "red team",
        "security",
        "scanner",
        "phishing",
        "jailbreak",
        "vulnerability",
        "threat",
        "risk",
        "permissions",
        "pentest",
        "sast",
        "secrets",
        "auth",
        "policy",
        "compliance",
        "identity",
        "iam",
        "siem",
        "soc",
    ),
    "Devtools": (
        "developer",
        "devtool",
        "github action",
        "github actions",
        "ci",
        "cd",
        "pipeline",
        "code review",
        "pull request",
        "sdk",
        "api",
        "cli",
        "ide",
        "debug",
        "testing",
        "deploy",
    ),
    "AI Infra": (
        "agent",
        "llm",
        "model",
        "inference",
        "eval",
        "evaluation",
        "rag",
        "embedding",
        "vector",
        "mcp",
        "orchestration",
        "runtime",
        "observability",
    ),
    "Vertical AI": (
        "dental",
        "healthcare",
        "clinic",
        "legal",
        "law firm",
        "real estate",
        "construction",
        "insurance",
        "finance",
        "accounting",
        "workflow",
        "operator",
        "smb",
        "front desk",
    ),
    "Data Infra": (
        "data lineage",
        "lineage",
        "warehouse",
        "etl",
        "elt",
        "pipeline",
        "data pipeline",
        "catalog",
        "governance",
        "lakehouse",
        "metadata",
        "dbt",
        "snowflake",
        "databricks",
    ),
}

SECURITY_PRIORITY_KEYWORDS = (
    "penetration testing",
    "security scanner",
    "prompt injection",
    "mcp permissions",
    "api security",
    "red team",
    "vulnerability",
    "pentest",
    "sast",
    "secrets",
    "auth",
    "threat",
)


def _keyword_matches(keyword: str, haystack: str) -> bool:
    words = [re.escape(word) for word in keyword.lower().split()]
    phrase = r"[\s/-]+".join(words)
    pattern = rf"(?<![a-z0-9]){phrase}(?![a-z0-9])"
    return bool(re.search(pattern, haystack))


def classify_market_sector(title: str = "", text: str = "", source_lane: str = "") -> SectorClassification:
    haystack = " ".join(part for part in (title, text, source_lane) if part).lower()
    security_priority_matches = [keyword for keyword in SECURITY_PRIORITY_KEYWORDS if _keyword_matches(keyword, haystack)]
    if security_priority_matches:
        confidence = "High" if len(security_priority_matches) >= 1 else "Medium"
        return SectorClassification(
            market_sector="Cybersecurity",
            sector_confidence=confidence,
            sector_reason=f"Matched priority Cybersecurity keywords: {', '.join(security_priority_matches[:5])}.",
        )

    best_sector = "Unclassified"
    best_matches: list[str] = []
    best_keyword_length = 0

    for sector, keywords in SECTOR_KEYWORDS.items():
        matches = [keyword for keyword in keywords if _keyword_matches(keyword, haystack)]
        keyword_length = sum(len(keyword) for keyword in matches)
        if (len(matches), keyword_length) > (len(best_matches), best_keyword_length):
            best_sector = sector
            best_matches = matches
            best_keyword_length = keyword_length

    if not best_matches:
        return SectorClassification(
            market_sector="Unclassified",
            sector_confidence="Low",
            sector_reason="No sector keywords matched.",
        )

    confidence = "High" if len(best_matches) >= 2 else "Medium"
    reason = f"Matched {best_sector} keywords: {', '.join(best_matches[:5])}."
    return SectorClassification(
        market_sector=best_sector,
        sector_confidence=confidence,
        sector_reason=reason,
    )
