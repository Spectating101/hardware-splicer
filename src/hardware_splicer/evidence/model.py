from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional


SCHEMA_VERSION = "hardware_splicer.evidence_graph.v1"


class EpistemicStatus(str, Enum):
    OBSERVED = "observed"
    MEASURED = "measured"
    INFERRED = "inferred"
    ASSUMED = "assumed"
    REFERENCE_ONLY = "reference_only"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class AuthorityState(str, Enum):
    UNMODELED = "unmodeled"
    OBSERVED = "observed"
    HYPOTHESIZED = "hypothesized"
    TEST_PLANNED = "test_planned"
    MEASURED = "measured"
    INTERFACE_BOUND = "interface_bound"
    DESIGN_COMPILED = "design_compiled"
    BENCH_READY = "bench_ready"
    POWER_AUTHORIZED = "power_authorized"
    FUNCTION_VERIFIED = "function_verified"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    kind: str
    method: str
    producer: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_uri: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceValue:
    value: Any = None
    unit: Optional[str] = None
    status: EpistemicStatus = EpistemicStatus.UNKNOWN
    confidence: float = 0.0
    evidence_ids: tuple[str, ...] = ()
    producer: str = "unknown"
    method: str = ""
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    supersedes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.status in {EpistemicStatus.MEASURED, EpistemicStatus.OBSERVED} and not self.evidence_ids:
            raise ValueError(f"{self.status.value} values require evidence_ids")

    @property
    def authoritative(self) -> bool:
        return (
            self.review_status == ReviewStatus.ACCEPTED
            and self.status in {EpistemicStatus.MEASURED, EpistemicStatus.OBSERVED}
            and bool(self.evidence_ids)
        )

    def to_dict(self) -> Dict[str, Any]:
        body = asdict(self)
        body["status"] = self.status.value
        body["review_status"] = self.review_status.value
        body["evidence_ids"] = list(self.evidence_ids)
        body["supersedes"] = list(self.supersedes)
        return body


@dataclass
class Claim:
    claim_id: str
    subject_id: str
    predicate: str
    value: EvidenceValue
    authority_state: AuthorityState = AuthorityState.UNMODELED
    blockers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "value": self.value.to_dict(),
            "authority_state": self.authority_state.value,
            "blockers": list(self.blockers),
        }


@dataclass
class EvidenceGraph:
    graph_id: str
    entities: MutableMapping[str, Dict[str, Any]] = field(default_factory=dict)
    evidence: MutableMapping[str, EvidenceRecord] = field(default_factory=dict)
    claims: MutableMapping[str, Claim] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def add_entity(self, entity_id: str, *, entity_type: str, **attributes: Any) -> None:
        if entity_id in self.entities:
            raise ValueError(f"entity already exists: {entity_id}")
        self.entities[entity_id] = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            **attributes,
        }

    def upsert_entity(self, entity_id: str, *, entity_type: str, **attributes: Any) -> None:
        current = dict(self.entities.get(entity_id) or {})
        current.update({"entity_id": entity_id, "entity_type": entity_type, **attributes})
        self.entities[entity_id] = current

    def add_evidence(self, record: EvidenceRecord) -> None:
        if record.evidence_id in self.evidence:
            raise ValueError(f"evidence already exists: {record.evidence_id}")
        self.evidence[record.evidence_id] = record

    def add_claim(self, claim: Claim) -> None:
        missing = [e for e in claim.value.evidence_ids if e not in self.evidence]
        if missing:
            raise ValueError(f"claim references missing evidence: {missing}")
        self.claims[claim.claim_id] = claim

    def claims_for(self, subject_id: str) -> List[Claim]:
        return [c for c in self.claims.values() if c.subject_id == subject_id]

    def unresolved_claims(self, subject_id: Optional[str] = None) -> List[Claim]:
        claims: Iterable[Claim] = self.claims.values()
        if subject_id is not None:
            claims = (c for c in claims if c.subject_id == subject_id)
        return [
            c
            for c in claims
            if c.blockers
            or c.value.status in {EpistemicStatus.UNKNOWN, EpistemicStatus.ASSUMED, EpistemicStatus.REFERENCE_ONLY}
            or c.value.review_status != ReviewStatus.ACCEPTED
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "graph_id": self.graph_id,
            "entities": list(self.entities.values()),
            "evidence": [r.to_dict() for r in self.evidence.values()],
            "claims": [c.to_dict() for c in self.claims.values()],
        }
