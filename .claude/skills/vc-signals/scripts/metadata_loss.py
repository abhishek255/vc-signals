from __future__ import annotations

from dataclasses import asdict, dataclass, field


IDENTITY_USEFUL_FIELDS = (
    "outbound_url",
    "resolved_url",
    "story_url",
    "domain",
    "homepage",
    "owner_name",
    "owner_type",
    "topics",
    "description",
    "query_kind",
    "query_topic",
)
CRITICAL_IDENTITY_FIELDS = (
    "outbound_url",
    "resolved_url",
    "story_url",
    "domain",
    "homepage",
)

INTERNAL_METADATA_FIELDS = {
    "_raw_fields_present",
    "_identity_fields_present_upstream",
}


@dataclass
class MetadataLossRow:
    row_name: str
    source: str
    source_url: str
    raw_fields_present: list[str] = field(default_factory=list)
    normalized_fields_preserved: list[str] = field(default_factory=list)
    signal_metadata_fields: list[str] = field(default_factory=list)
    candidate_evidence_metadata_fields: list[str] = field(default_factory=list)
    identity_useful_fields_present: list[str] = field(default_factory=list)
    identity_useful_fields_missing: list[str] = field(default_factory=list)
    loss_point: str = "upstream_missing"
    recommended_fix: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _object_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return getattr(value, "__dict__", {}) or {}


def _truthy_fields(payload: dict) -> list[str]:
    return sorted(
        key
        for key, value in payload.items()
        if key not in INTERNAL_METADATA_FIELDS and value not in ("", None, [], {})
    )


def _identity_fields(payload: dict) -> list[str]:
    return sorted(field for field in IDENTITY_USEFUL_FIELDS if payload.get(field) not in ("", None, [], {}))


def _flatten_evidence_items(evidence: dict) -> list[dict]:
    items = []
    for payload in evidence.get("last30days", {}).values():
        if isinstance(payload, dict):
            items.extend(item for item in payload.get("items", []) if isinstance(item, dict))
    items.extend(item for item in evidence.get("github", []) if isinstance(item, dict))
    for payload in evidence.get("company_discovery", {}).get("items", []):
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _candidate_metadata_by_url(candidates) -> dict[str, list[dict]]:
    by_url: dict[str, list[dict]] = {}
    for candidate in candidates:
        payload = _object_dict(candidate)
        for metadata in payload.get("evidence_metadata") or []:
            if not isinstance(metadata, dict):
                continue
            source_url = metadata.get("source_url") or metadata.get("url") or ""
            if source_url:
                by_url.setdefault(source_url, []).append(metadata)
    return by_url


def _signals_by_url(signals) -> dict[str, dict]:
    by_url = {}
    for signal in signals:
        payload = _object_dict(signal)
        url = payload.get("url") or ""
        if url:
            by_url[url] = _object_dict(payload.get("metadata") or {})
    return by_url


def _resolution_by_url(identity_resolutions) -> dict[str, dict]:
    by_url = {}
    for resolution in identity_resolutions:
        payload = _object_dict(resolution)
        for url in payload.get("evidence_urls") or []:
            if url:
                by_url[url] = payload
    return by_url


def _raw_identity_fields(item: dict, raw_fields: list[str]) -> list[str]:
    if isinstance(item.get("_identity_fields_present_upstream"), list):
        return [field for field in item["_identity_fields_present_upstream"] if field in IDENTITY_USEFUL_FIELDS]
    if "_raw_fields_present" in item:
        return [field for field in IDENTITY_USEFUL_FIELDS if field in raw_fields]
    return [field for field in IDENTITY_USEFUL_FIELDS if item.get(field) not in ("", None, [], {}) or field in raw_fields and item.get(field) not in ("", None, [], {})]


def _loss_point(item: dict, raw_fields: list[str], normalized_fields: list[str], signal_fields: list[str], candidate_fields: list[str], identity_present: list[str]) -> str:
    raw_identity = _raw_identity_fields(item, raw_fields)
    if not raw_identity:
        return "upstream_missing"
    if (item.get("source") or "").lower() in {"hackernews", "hn"} and not any(field in raw_identity for field in CRITICAL_IDENTITY_FIELDS):
        return "upstream_missing"
    if any(field not in normalized_fields for field in raw_identity):
        return "adapter_dropped"
    if any(field not in signal_fields for field in raw_identity):
        return "signal_dropped"
    if any(field not in candidate_fields for field in raw_identity):
        return "candidate_dropped"
    if raw_identity and not identity_present:
        return "identity_ignored"
    return "preserved"


def _recommended_fix(loss_point: str) -> str:
    return {
        "upstream_missing": "Source output lacks identity-useful metadata; add a narrow source-specific enrichment fallback if this row matters.",
        "adapter_dropped": "Preserve identity-useful upstream fields in the source adapter normalization.",
        "signal_dropped": "Preserve normalized identity fields when building Signal.metadata.",
        "candidate_dropped": "Preserve signal identity fields in Candidate.evidence_metadata.",
        "identity_ignored": "Teach identity resolution to consume preserved evidence metadata.",
        "preserved": "No metadata loss detected for identity-useful fields.",
    }[loss_point]


def build_metadata_loss_report(
    *,
    evidence: dict,
    signals,
    candidates,
    identity_resolutions,
) -> list[MetadataLossRow]:
    signal_by_url = _signals_by_url(signals)
    candidate_metadata = _candidate_metadata_by_url(candidates)
    resolution_by_url = _resolution_by_url(identity_resolutions)
    rows = []

    for item in _flatten_evidence_items(evidence):
        source_url = item.get("url") or item.get("source_url") or ""
        if not source_url:
            continue
        raw_fields = sorted(item.get("_raw_fields_present") or item.keys())
        normalized_fields = _truthy_fields(item)
        signal_fields = _truthy_fields(signal_by_url.get(source_url, {}))
        metadata_items = candidate_metadata.get(source_url, [])
        candidate_fields = sorted({
            field
            for metadata in metadata_items
            for field in _truthy_fields(metadata)
        })
        resolution = resolution_by_url.get(source_url, {})
        present_payload = {}
        for payload in [item, signal_by_url.get(source_url, {})] + metadata_items:
            present_payload.update({field: payload.get(field) for field in IDENTITY_USEFUL_FIELDS if payload.get(field) not in ("", None, [], {})})
        if resolution.get("verified_domain"):
            present_payload.setdefault("domain", resolution["verified_domain"])
        if resolution.get("source_outbound_urls"):
            present_payload.setdefault("outbound_url", resolution["source_outbound_urls"][0])
        identity_present = _identity_fields(present_payload)
        missing = [field for field in IDENTITY_USEFUL_FIELDS if field not in identity_present]
        loss_point = _loss_point(item, raw_fields, normalized_fields, signal_fields, candidate_fields, identity_present)
        rows.append(
            MetadataLossRow(
                row_name=item.get("company_name") or item.get("full_name") or item.get("title") or item.get("name") or "",
                source=item.get("source", ""),
                source_url=source_url,
                raw_fields_present=raw_fields,
                normalized_fields_preserved=normalized_fields,
                signal_metadata_fields=signal_fields,
                candidate_evidence_metadata_fields=candidate_fields,
                identity_useful_fields_present=identity_present,
                identity_useful_fields_missing=missing,
                loss_point=loss_point,
                recommended_fix=_recommended_fix(loss_point),
            )
        )

    return rows
