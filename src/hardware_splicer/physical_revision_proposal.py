"""Build reviewable engineering-revision proposals from physical mission receipts.

This module never edits a project or mission.  It reads the append-only physical
sidecar and proposes a new revision only when retained physical evidence supports
that conclusion.  Raw observations and dispatch success alone cannot trigger a
passing/failing engineering claim.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError
from .mission_physical_log import MissionPhysicalLog


class PhysicalRevisionProposalBuilder:
    def __init__(self, *, physical_log: MissionPhysicalLog):
        self.physical_log = physical_log

    def build(self, project_id: str, mission_id: str, *, candidate_id: str | None = None) -> dict[str, Any]:
        rows = self.physical_log.list(project_id, mission_id)
        if candidate_id is not None:
            rows = [row for row in rows if row.get("candidate_id") in {None, candidate_id}]
        failed: list[dict[str, Any]] = []
        passed: list[dict[str, Any]] = []
        unresolved_observations: list[dict[str, Any]] = []
        promoted_observation_ids: set[str] = set()

        for row in rows:
            source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
            if row.get("receipt_type") == "evidence":
                evidence_id = source.get("evidence_id")
                metadata = source.get("metadata") if isinstance(source.get("metadata"), Mapping) else {}
                observation_id = metadata.get("observation_id")
                if isinstance(observation_id, str):
                    promoted_observation_ids.add(observation_id)
                item = {
                    "physical_receipt_seq": row.get("seq"),
                    "source_sha256": row.get("source_sha256"),
                    "evidence_id": evidence_id,
                    "kind": source.get("kind"),
                    "target_ids": source.get("target_ids") or [],
                    "procedure_id": source.get("procedure_id"),
                    "measured_values": source.get("measured_values") or {},
                    "acceptance_criteria": source.get("acceptance_criteria") or {},
                }
                if source.get("passed") is True:
                    passed.append(item)
                elif source.get("passed") is False:
                    failed.append(item)
            elif row.get("receipt_type") == "observation":
                observation = source.get("observation") if isinstance(source.get("observation"), Mapping) else source
                observation_id = observation.get("observation_id") if isinstance(observation, Mapping) else None
                if isinstance(observation_id, str):
                    unresolved_observations.append({
                        "physical_receipt_seq": row.get("seq"),
                        "observation_id": observation_id,
                        "source_sha256": row.get("source_sha256"),
                    })

        unresolved_observations = [
            row for row in unresolved_observations if row["observation_id"] not in promoted_observation_ids
        ]
        needs_revision = bool(failed)
        proposal = {
            "schema": "hardware_splicer.physical_revision_proposal.v1",
            "project_id": project_id,
            "mission_id": mission_id,
            "candidate_id": candidate_id,
            "needs_revision": needs_revision,
            "failed_evidence": failed,
            "passing_evidence": passed,
            "unresolved_observations": unresolved_observations,
            "recommended_action": (
                "CREATE_REVIEWABLE_ENGINEERING_REVISION" if needs_revision
                else "NO_REVISION_GROUNDED_BY_FAILED_PHYSICAL_EVIDENCE"
            ),
            "automatic_project_mutation": False,
            "automatic_mission_reopen": False,
            "physical_correctness": "UNPROVEN" if needs_revision or unresolved_observations else "EVIDENCE_REVIEW_REQUIRED",
        }
        proposal["proposal_sha256"] = _sha(proposal)
        return proposal

    @staticmethod
    def require_grounded_revision(proposal: Mapping[str, Any]) -> None:
        if not isinstance(proposal, Mapping) or proposal.get("schema") != "hardware_splicer.physical_revision_proposal.v1":
            raise FabricationValidationError("invalid physical revision proposal")
        expected = proposal.get("proposal_sha256")
        copy = dict(proposal)
        copy.pop("proposal_sha256", None)
        if expected != _sha(copy):
            raise FabricationValidationError("physical revision proposal hash does not match")
        if proposal.get("needs_revision") is not True or not proposal.get("failed_evidence"):
            raise FabricationValidationError("engineering revision requires failed retained physical evidence")


def _sha(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
