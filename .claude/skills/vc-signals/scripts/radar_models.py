from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


def _known_payload(cls, payload: dict) -> dict:
    names = {item.name for item in fields(cls)}
    return {key: value for key, value in payload.items() if key in names}


@dataclass(frozen=True)
class Signal:
    source: str
    role: str
    title: str
    url: str = ""
    sector: str = ""
    theme: str = ""
    text: str = ""
    can_create_candidate: bool = False
    evidence_strength: int = 0
    reason: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Signal":
        return cls(**_known_payload(cls, payload))


@dataclass
class Candidate:
    name: str
    sector: str
    theme: str
    source: str
    candidate_type: str
    stable_key: str = ""
    weekly_tag: str = ""
    domain: str = ""
    why_on_radar: str = ""
    why_this_may_be_noise: str = ""
    sources: list[str] = field(default_factory=list)
    source_count: int = 1
    company_linkedin: str = ""
    company_x: str = ""
    founder_profiles: list[dict] = field(default_factory=list)
    attio_status: str = "unknown"
    attio_action: str = ""
    attio_lists: list[str] = field(default_factory=list)
    action: str = "watch"
    investment_interest_score: int = 0
    evidence_confidence_score: int = 0
    investment_interest: str = ""
    evidence_confidence: str = ""
    tier: str = ""
    engagement: dict = field(default_factory=dict)
    stage: str = ""
    raised: str = ""
    headcount: str = ""
    founders: list[str] = field(default_factory=list)
    founding_year: str = ""
    lead_investor: str = ""
    enrichment_evidence: dict = field(default_factory=dict)
    attio_record_url: str = ""
    attio_owner: str = ""
    attio_last_interaction: str = ""
    attio_staleness_reason: str = ""
    oss_company_formation_score: int = 0
    oss_action_reason: str = ""
    license: str = ""
    repo_age_days: int = 0
    stars: int = 0
    stars_30d: int = 0
    maintainer_profiles: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Candidate":
        return cls(**_known_payload(cls, payload))


@dataclass
class RejectedSignal:
    sector: str
    source: str
    title: str
    reason: str
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "RejectedSignal":
        return cls(**_known_payload(cls, payload))


@dataclass
class SectorCoverage:
    sector: str
    raw_signals: int = 0
    candidates: int = 0
    rejected: int = 0
    status: str = "no qualified candidates"
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "SectorCoverage":
        return cls(**_known_payload(cls, payload))
