from __future__ import annotations

from copy import deepcopy
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
    market_sector: str = ""
    source_lane: str = ""
    evidence_role: str = ""
    sector_confidence: str = ""
    sector_reason: str = ""
    partner_priority_score: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Candidate":
        return cls(**_known_payload(cls, payload))


@dataclass
class ThemeSignal:
    market_sector: str
    theme: str
    source_lanes: list[str] = field(default_factory=list)
    evidence_count: int = 0
    evidence_summary: str = ""
    why_it_matters: str = ""
    why_no_company_yet: str = ""
    suggested_search: str = ""
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ThemeSignal":
        return cls(**_known_payload(cls, payload))


@dataclass
class SectorIntelligence:
    market_sector: str
    status: str = "No meaningful signal this week"
    raw_signals: int = 0
    candidate_eligible_signals: int = 0
    promoted_candidates: int = 0
    rejected_signals: int = 0
    best_evidence: str = ""
    why_no_more_companies: str = ""
    next_hunt: str = ""
    source_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "SectorIntelligence":
        return cls(**_known_payload(cls, payload))


@dataclass
class SectorDiagnosis:
    market_sector: str
    diagnosis: str = ""
    evidence_urls: list[str] = field(default_factory=list)
    recommended_next_queries: list[str] = field(default_factory=list)
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "SectorDiagnosis":
        return cls(**_known_payload(cls, payload))


@dataclass
class ThemeHypothesis:
    market_sector: str
    theme: str
    evidence_summary: str = ""
    evidence_urls: list[str] = field(default_factory=list)
    why_it_matters: str = ""
    why_this_may_be_noise: str = ""
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ThemeHypothesis":
        return cls(**_known_payload(cls, payload))


@dataclass
class PossibleCompanyLead:
    name: str
    market_sector: str = ""
    source_lane: str = ""
    domain: str = ""
    evidence_urls: list[str] = field(default_factory=list)
    why_on_radar: str = ""
    verification_needed: list[str] = field(default_factory=list)
    suggested_action: str = "investigate"
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "PossibleCompanyLead":
        return cls(**_known_payload(cls, payload))


@dataclass
class SynthesisResult:
    enabled: bool = False
    model: str = ""
    generated_at: str = ""
    source_digest: dict = field(default_factory=dict)
    sector_diagnoses: list[SectorDiagnosis] = field(default_factory=list)
    theme_hypotheses: list[ThemeHypothesis] = field(default_factory=list)
    possible_company_leads: list[PossibleCompanyLead] = field(default_factory=list)
    partner_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "model": self.model,
            "generated_at": self.generated_at,
            "source_digest": deepcopy(self.source_digest),
            "sector_diagnoses": [item.to_dict() for item in self.sector_diagnoses],
            "theme_hypotheses": [item.to_dict() for item in self.theme_hypotheses],
            "possible_company_leads": [item.to_dict() for item in self.possible_company_leads],
            "partner_notes": list(self.partner_notes),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "SynthesisResult":
        known = _known_payload(cls, payload)
        known["sector_diagnoses"] = [
            item if isinstance(item, SectorDiagnosis) else SectorDiagnosis.from_dict(item)
            for item in known.get("sector_diagnoses", [])
        ]
        known["theme_hypotheses"] = [
            item if isinstance(item, ThemeHypothesis) else ThemeHypothesis.from_dict(item)
            for item in known.get("theme_hypotheses", [])
        ]
        known["possible_company_leads"] = [
            item if isinstance(item, PossibleCompanyLead) else PossibleCompanyLead.from_dict(item)
            for item in known.get("possible_company_leads", [])
        ]
        return cls(**known)


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
