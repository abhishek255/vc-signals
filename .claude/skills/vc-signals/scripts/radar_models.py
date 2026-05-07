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
    evidence_metadata: list[dict] = field(default_factory=list)
    identity_type: str = ""
    candidate_domain: str = ""
    domain_confidence: str = ""
    verified_domain_basis: list[str] = field(default_factory=list)
    identity_confidence_score: int = 0
    identity_confidence: str = ""
    identity_confidence_basis: list[str] = field(default_factory=list)
    commercial_intent_score: int = 0
    commercial_intent_basis: list[str] = field(default_factory=list)
    attio_match_keys: list[str] = field(default_factory=list)
    attio_safe_to_match: bool = False
    recommended_identity_action: str = ""
    missing_identity_evidence: list[str] = field(default_factory=list)
    source_outbound_urls: list[str] = field(default_factory=list)
    source_titles: list[str] = field(default_factory=list)
    fetch_warnings: list[str] = field(default_factory=list)
    identity_resolved_from: list[str] = field(default_factory=list)

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
class DiscoveryQuery:
    id: str
    movement: str
    market_sector: str
    source_reason: str = ""
    topic: str = ""
    sources: str = "grounding"
    lookback_days: int = 30
    web_backend: str = "auto"
    candidate_eligible: bool = True
    origin_row_ids: list[str] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)
    limited: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "DiscoveryQuery":
        return cls(**_known_payload(cls, payload))


@dataclass
class VerifiedCompanyDiscoveryLead:
    name: str
    movement: str
    market_sector: str
    source_url: str
    source: str = ""
    domain: str = ""
    founder_or_maintainer: str = ""
    candidate_type: str = "launch_style_needs_identity"
    verification_status: str = "rejected"
    verification_basis: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    movement_assignment_basis: list[str] = field(default_factory=list)
    query_id: str = ""
    query_topic: str = ""
    why_on_radar: str = ""
    why_this_may_be_noise: str = ""
    raw_title: str = ""
    raw_snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "VerifiedCompanyDiscoveryLead":
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
class FocusItem:
    id: str
    rank: int = 0
    name: str = ""
    company_domain: str = ""
    project_url: str = ""
    market_movement_id: str = ""
    market_movement: str = ""
    market_sector: str = ""
    why_focus_this_week: str = ""
    who_is_talking: list[str] = field(default_factory=list)
    talker_types: list[str] = field(default_factory=list)
    talker_type_confidence: str = "Low"
    evidence_snapshot: list[str] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    attio_status: str = "unknown"
    attio_owner: str = ""
    attio_last_touch: str = ""
    identity_type: str = ""
    attio_safe_to_match: bool = False
    recommended_action: str = "Research deeper"
    investment_interest_score: int = 0
    evidence_confidence_score: int = 0
    focus_priority_score: int = 0
    actionability_score: int = 0
    freshness_score: int = 0
    market_movement_score: int = 0
    marathon_fit_score: int = 0
    noise_risk_score: int = 0
    consensus_risk_score: int = 0
    company_identity_quality_score: int = 0
    company_identity_quality_basis: list[str] = field(default_factory=list)
    focus_priority_basis: list[str] = field(default_factory=list)
    actionability_basis: list[str] = field(default_factory=list)
    freshness_basis: list[str] = field(default_factory=list)
    market_movement_basis: list[str] = field(default_factory=list)
    marathon_fit_basis: list[str] = field(default_factory=list)
    noise_risk_basis: list[str] = field(default_factory=list)
    consensus_risk_basis: list[str] = field(default_factory=list)
    movement_assignment_method: str = "direct_match"
    movement_assignment_confidence: str = "Medium"
    movement_assignment_evidence_url: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    seen_in_prior_runs: bool = False
    weekly_tag: str = ""
    new_evidence_this_week: list[str] = field(default_factory=list)
    why_this_may_be_noise: str = ""
    skepticism_events: list[str] = field(default_factory=list)
    source_candidate_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "FocusItem":
        return cls(**_known_payload(cls, payload))


@dataclass
class MarketMovement:
    id: str
    name: str
    market_sector: str = ""
    what_is_moving: str = ""
    why_now: str = ""
    why_not_now: str = ""
    who_is_talking: list[str] = field(default_factory=list)
    talker_mix: dict = field(default_factory=dict)
    companies_or_projects: list[str] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    skepticism_events: list[str] = field(default_factory=list)
    momentum_label: str = "provisional"
    confidence: str = "Low"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "MarketMovement":
        return cls(**_known_payload(cls, payload))


@dataclass
class ExecutiveSnapshot:
    top_movement: str = ""
    top_new_to_marathon: str = ""
    rows_needing_owner: int = 0
    rows_needing_attio_refresh: int = 0
    biggest_source_gap: str = ""
    top_actions: list[str] = field(default_factory=list)
    partner_focus_rows: int = 0
    oss_project_only_rows: int = 0
    company_or_launch_style_rows: int = 0
    readiness_note: str = ""
    top_identity_resolution_target: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ExecutiveSnapshot":
        return cls(**_known_payload(cls, payload))


@dataclass
class EvidenceMetadata:
    candidate_key: str = ""
    source_url: str = ""
    source: str = ""
    title: str = ""
    author: str = ""
    published_at: str = ""
    container: str = ""
    query_kind: str = ""
    query_topic: str = ""
    outbound_url: str = ""
    domain: str = ""
    owner_name: str = ""
    owner_type: str = ""
    topics: list[str] = field(default_factory=list)
    description: str = ""
    homepage: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "EvidenceMetadata":
        return cls(**_known_payload(cls, payload))


@dataclass
class IdentityResolution:
    candidate_key: str
    original_name: str = ""
    resolved_name: str = ""
    identity_type: str = "insufficient_identity"
    candidate_domain: str = ""
    verified_domain: str = ""
    domain_confidence: str = "Low"
    verified_domain_basis: list[str] = field(default_factory=list)
    project_url: str = ""
    company_linkedin: str = ""
    company_x: str = ""
    founders: list[str] = field(default_factory=list)
    founder_profiles: list[dict] = field(default_factory=list)
    maintainers: list[str] = field(default_factory=list)
    maintainer_profiles: list[dict] = field(default_factory=list)
    commercial_intent_score: int = 0
    commercial_intent_basis: list[str] = field(default_factory=list)
    identity_confidence_score: int = 0
    identity_confidence: str = "Low"
    identity_confidence_basis: list[str] = field(default_factory=list)
    attio_match_keys: list[str] = field(default_factory=list)
    attio_safe_to_match: bool = False
    recommended_identity_action: str = "Research deeper"
    missing_identity_evidence: list[str] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    source_outbound_urls: list[str] = field(default_factory=list)
    source_titles: list[str] = field(default_factory=list)
    fetch_warnings: list[str] = field(default_factory=list)
    resolved_from: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "IdentityResolution":
        return cls(**_known_payload(cls, payload))


@dataclass
class WeeklyFocusArtifact:
    run_id: str
    executive_snapshot: ExecutiveSnapshot = field(default_factory=ExecutiveSnapshot)
    partner_focus: list[FocusItem] = field(default_factory=list)
    market_movements: list[MarketMovement] = field(default_factory=list)
    new_to_marathon: list[FocusItem] = field(default_factory=list)
    workflow_view: dict[str, list[FocusItem]] = field(default_factory=dict)
    extended_watchlist: list[FocusItem] = field(default_factory=list)
    appendix: dict = field(default_factory=dict)
    source_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "executive_snapshot": self.executive_snapshot.to_dict(),
            "partner_focus": [item.to_dict() for item in self.partner_focus],
            "market_movements": [item.to_dict() for item in self.market_movements],
            "new_to_marathon": [item.to_dict() for item in self.new_to_marathon],
            "workflow_view": {
                action: [item.to_dict() for item in items]
                for action, items in self.workflow_view.items()
            },
            "extended_watchlist": [item.to_dict() for item in self.extended_watchlist],
            "appendix": deepcopy(self.appendix),
            "source_gaps": list(self.source_gaps),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "WeeklyFocusArtifact":
        known = _known_payload(cls, payload)
        snapshot = known.get("executive_snapshot", {})
        known["executive_snapshot"] = (
            snapshot
            if isinstance(snapshot, ExecutiveSnapshot)
            else ExecutiveSnapshot.from_dict(snapshot)
        )
        known["partner_focus"] = [
            item if isinstance(item, FocusItem) else FocusItem.from_dict(item)
            for item in known.get("partner_focus", [])
        ]
        known["market_movements"] = [
            item if isinstance(item, MarketMovement) else MarketMovement.from_dict(item)
            for item in known.get("market_movements", [])
        ]
        known["new_to_marathon"] = [
            item if isinstance(item, FocusItem) else FocusItem.from_dict(item)
            for item in known.get("new_to_marathon", [])
        ]
        known["workflow_view"] = {
            action: [
                item if isinstance(item, FocusItem) else FocusItem.from_dict(item)
                for item in items
            ]
            for action, items in known.get("workflow_view", {}).items()
        }
        known["extended_watchlist"] = [
            item if isinstance(item, FocusItem) else FocusItem.from_dict(item)
            for item in known.get("extended_watchlist", [])
        ]
        return cls(**known)


@dataclass
class AlexFeedback:
    run_id: str
    feedback: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "feedback": deepcopy(self.feedback),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "AlexFeedback":
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
