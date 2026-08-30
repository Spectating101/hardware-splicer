"""Execute bounded parsers against registered project source blobs.

The parser boundary re-opens only content-addressed bytes already registered by
Hardware Splicer, verifies their SHA-256 identity again, and emits bounded JSON
outputs. Raw bytes never enter the project snapshot or API response.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .engineering_source_graph import build_engineering_source_graph
from .engineering_source_ingestion import MAX_ENGINEERING_SOURCE_BYTES
from .machine_project import AuthorityState
from .project_store import default_project_root, validate_project_id
from .robot_model_import import parse_robot_model, topology_from_robot_model
from .step_geometry import build_mechanical_geometry_report, parse_step_model


STORED_SOURCE_PARSER_SCHEMA = "hardware_splicer.stored_source_parser.v1"
STORED_SOURCE_PARSER_IMPLEMENTATION = (
    "hardware_splicer.stored_source_parser.python.v1"
)
MAX_PERSISTED_PARSER_OUTPUT_BYTES = 8 * 1024 * 1024


class StoredParserStatus(str, Enum):
    PARSED = "parsed"
    SKIPPED = "skipped"


class StoredSourceParserModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class StoredSourceParserResult(StoredSourceParserModel):
    schema_version: str = STORED_SOURCE_PARSER_SCHEMA
    parser_identity: str = STORED_SOURCE_PARSER_IMPLEMENTATION
    project_id: str
    source_id: str
    content_hash: str
    parser_route: str | None = None
    status: StoredParserStatus
    authority_ceiling: AuthorityState
    parsed_output: Dict[str, Any] = Field(default_factory=dict)
    derived_sources: list[Dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    raw_bytes_returned: bool = False
    automatic_authorization: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _descriptor_metadata(source: Mapping[str, Any]) -> Dict[str, Any]:
    value = source.get("metadata")
    return dict(value) if isinstance(value, Mapping) else {}


def _authority(value: Any) -> AuthorityState:
    try:
        authority = AuthorityState(
            str(value or AuthorityState.DECLARED.value).lower()
        )
    except ValueError as exc:
        raise ValueError(f"unsupported source authority: {value!r}") from exc
    if authority not in {
        AuthorityState.UNKNOWN,
        AuthorityState.PROPOSED,
        AuthorityState.DECLARED,
    }:
        raise ValueError(
            "stored uploaded sources cannot execute above declared authority"
        )
    return authority


def _expected_digest(source: Mapping[str, Any]) -> str:
    content_hash = str(source.get("content_hash") or source.get("revision") or "")
    if not content_hash.startswith("sha256:") or len(content_hash) != 71:
        raise ValueError(
            "registered source requires a canonical sha256 content_hash"
        )
    digest = content_hash.split(":", 1)[1]
    if any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("registered source sha256 digest is invalid")
    return digest


def _blob_path(
    project_root: str | Path | None,
    project_id: str,
    source: Mapping[str, Any],
) -> Path:
    root = Path(project_root) if project_root is not None else default_project_root()
    root = root.expanduser().resolve()
    unresolved_project_dir = root / validate_project_id(project_id)
    if unresolved_project_dir.is_symlink():
        raise ValueError("project source directory must not be a symlink")
    project_dir = unresolved_project_dir.resolve()
    if project_dir.parent != root:
        raise ValueError("project source directory resolves outside project root")

    metadata = _descriptor_metadata(source)
    blob_ref = str(metadata.get("blob_ref") or "")
    if not blob_ref:
        raise ValueError("registered source has no blob_ref")
    relative = Path(blob_ref)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("registered source blob_ref is not project-relative")

    unresolved_target = project_dir / relative
    current = project_dir
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("registered source path contains a symlink")
    target = unresolved_target.resolve()
    if target == project_dir or project_dir not in target.parents:
        raise ValueError("registered source blob resolves outside its project")
    if not target.is_file():
        raise ValueError("registered source blob does not exist")
    return target


def read_registered_source_bytes(
    project_id: str,
    source: Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
) -> bytes:
    """Read and re-verify one registered source blob."""

    target = _blob_path(project_root, project_id, source)
    size = target.stat().st_size
    if size > MAX_ENGINEERING_SOURCE_BYTES:
        raise ValueError("registered source exceeds the bounded parser size")
    content = target.read_bytes()
    expected = _expected_digest(source)
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        raise ValueError(
            "registered source blob no longer matches its content_hash"
        )
    return content


def _authority_rank(value: AuthorityState) -> int:
    return {
        AuthorityState.UNKNOWN: 0,
        AuthorityState.PROPOSED: 1,
        AuthorityState.DECLARED: 2,
        AuthorityState.OBSERVED: 3,
        AuthorityState.MEASURED: 4,
        AuthorityState.VERIFIED: 5,
        AuthorityState.AUTHORIZED: 6,
    }[value]


def _bounded_authority(value: Any, ceiling: AuthorityState) -> str:
    try:
        requested = AuthorityState(str(value or ceiling.value).lower())
    except ValueError:
        requested = ceiling
    return (
        requested.value
        if _authority_rank(requested) <= _authority_rank(ceiling)
        else ceiling.value
    )


def _bounded_source_descriptor(
    source: Mapping[str, Any],
    *,
    parent_source_id: str,
    ceiling: AuthorityState,
    index: int,
) -> Dict[str, Any]:
    row = dict(source)
    row["source_id"] = str(
        row.get("source_id") or f"{parent_source_id}-derived-{index + 1}"
    )
    row["authority_ceiling"] = _bounded_authority(
        row.get("authority_ceiling"), ceiling
    )
    claims: list[Dict[str, Any]] = []
    for claim in row.get("claims") or []:
        if not isinstance(claim, Mapping):
            continue
        bounded_claim = dict(claim)
        bounded_claim["authority"] = _bounded_authority(
            bounded_claim.get("authority"), ceiling
        )
        claims.append(bounded_claim)
    row["claims"] = claims
    metadata = (
        dict(row.get("metadata") or {})
        if isinstance(row.get("metadata"), Mapping)
        else {}
    )
    metadata.update(
        {
            "derived_from_uploaded_source_id": parent_source_id,
            "authority_bounded_by_parent_upload": True,
            "automatic_authorization": False,
        }
    )
    row["metadata"] = metadata
    return row


def _json_descriptors(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, Mapping):
        if isinstance(value.get("engineering_sources"), list):
            rows = value["engineering_sources"]
        elif isinstance(value.get("sources"), list):
            rows = value["sources"]
        elif any(
            key in value
            for key in ("source_id", "source_type", "uri", "url", "claims")
        ):
            rows = [value]
        else:
            raise ValueError(
                "JSON is valid but does not contain an engineering source "
                "descriptor envelope"
            )
    else:
        raise ValueError("engineering source JSON must be an object or array")
    if not rows or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError(
            "engineering source JSON must contain one or more object descriptors"
        )
    return list(rows)


def execute_stored_source_parser(
    project_id: str,
    source: Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
) -> StoredSourceParserResult:
    """Execute the parser route registered during bounded ingestion."""

    project_id = validate_project_id(project_id)
    source_id = str(source.get("source_id") or "")
    if not source_id:
        raise ValueError("registered source requires source_id")
    authority = _authority(source.get("authority_ceiling"))
    metadata = _descriptor_metadata(source)
    parser_route = str(metadata.get("parser_route") or "").strip() or None
    parser_disposition = str(
        metadata.get("parser_disposition") or "inventory_only"
    )
    content_hash = f"sha256:{_expected_digest(source)}"
    content = read_registered_source_bytes(
        project_id,
        source,
        project_root=project_root,
    )

    if parser_disposition != "structured" or not parser_route:
        return StoredSourceParserResult(
            project_id=project_id,
            source_id=source_id,
            content_hash=content_hash,
            parser_route=parser_route,
            status=StoredParserStatus.SKIPPED,
            authority_ceiling=authority,
            limitations=[
                "The registered source is inventory-only and has no executable "
                "bounded parser."
            ],
            metadata={
                "parser_disposition": parser_disposition,
                "blob_hash_reverified": True,
                "verified_size_bytes": len(content),
                "physical_authority_unchanged": True,
            },
        )

    if parser_route == "robot_model_import":
        model_format = str(metadata.get("structured_format") or "")
        model = parse_robot_model(content, model_format)
        if model.content_hash != content_hash:
            raise ValueError(
                "robot-model parser hash disagrees with registered source"
            )
        topology = topology_from_robot_model(model)
        return StoredSourceParserResult(
            project_id=project_id,
            source_id=source_id,
            content_hash=content_hash,
            parser_route=parser_route,
            status=StoredParserStatus.PARSED,
            authority_ceiling=authority,
            parsed_output={
                "parsed_robot_model": model.model_dump(mode="json"),
                "robot_topology": topology.model_dump(mode="json"),
                "summary": {
                    "model_format": model.model_format.value,
                    "link_count": len(model.links),
                    "joint_count": len(model.joints),
                    "actuator_count": len(model.actuators),
                    "topology_unresolved_count": len(topology.unresolved),
                },
            },
            limitations=[
                "Parsed design relationships do not prove physical fit, "
                "calibration, ratings, or safe motion."
            ],
            metadata={
                "parser_reverified_hash": True,
                "verified_size_bytes": len(content),
                "candidate_only": True,
                "physical_authority_unchanged": True,
            },
        )

    if parser_route == "engineering_source_descriptor":
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"registered JSON source cannot be decoded: {exc}"
            ) from exc
        bounded = [
            _bounded_source_descriptor(
                row,
                parent_source_id=source_id,
                ceiling=authority,
                index=index,
            )
            for index, row in enumerate(_json_descriptors(value))
        ]
        graph = build_engineering_source_graph(bounded)
        return StoredSourceParserResult(
            project_id=project_id,
            source_id=source_id,
            content_hash=content_hash,
            parser_route=parser_route,
            status=StoredParserStatus.PARSED,
            authority_ceiling=authority,
            parsed_output={
                "engineering_source_graph": graph.model_dump(mode="json"),
                "summary": {
                    "derived_source_count": len(graph.sources),
                    "derived_claim_count": len(graph.claims),
                    "blocking_conflict_count": len(graph.blocking_conflicts),
                },
            },
            derived_sources=bounded,
            limitations=[
                "Parsing validates structure and authority bounds; it does not "
                "establish correctness or trustworthiness."
            ],
            metadata={
                "parser_reverified_hash": True,
                "verified_size_bytes": len(content),
                "derived_authority_capped": True,
                "physical_authority_unchanged": True,
            },
        )

    if parser_route == "step_geometry":
        model = parse_step_model(content, source_id=source_id, model_id=source_id)
        if model.content_hash != content_hash:
            raise ValueError("STEP parser hash disagrees with registered source")
        model = model.model_copy(
            update={
                "authority": authority,
                "metadata": {
                    **model.metadata,
                    "registered_source_hash_reverified": True,
                    "authority_bounded_by_parent_upload": True,
                    "physical_authority_unchanged": True,
                },
            }
        )
        report = build_mechanical_geometry_report(
            project_id=project_id,
            models=[model],
            mounts=[],
        )
        return StoredSourceParserResult(
            project_id=project_id,
            source_id=source_id,
            content_hash=content_hash,
            parser_route=parser_route,
            status=StoredParserStatus.PARSED,
            authority_ceiling=authority,
            parsed_output={
                "step_model": model.model_dump(mode="json"),
                "mechanical_geometry": report.model_dump(mode="json"),
                "summary": {
                    "model_id": model.model_id,
                    "units": model.units,
                    "entity_count": model.entity_count,
                    "cartesian_point_count": model.cartesian_point_count,
                    "has_bounding_box": model.bounding_box is not None,
                    "unresolved_count": len(model.unresolved),
                },
            },
            limitations=[
                "Stored STEP parsing establishes bounded file identity and a Cartesian-point envelope only.",
                "It does not establish BREP validity, solid interference, mass properties, service access, structural safety, or fabrication authority.",
            ],
            metadata={
                "parser_reverified_hash": True,
                "verified_size_bytes": len(content),
                "parser_available": True,
                "step_point_envelope_only": True,
                "full_brep_validation": False,
                "authority_bounded_by_parent_upload": True,
                "physical_authority_unchanged": True,
            },
        )

    return StoredSourceParserResult(
        project_id=project_id,
        source_id=source_id,
        content_hash=content_hash,
        parser_route=parser_route,
        status=StoredParserStatus.SKIPPED,
        authority_ceiling=authority,
        limitations=[
            f"No bounded parser implementation is registered for {parser_route!r}."
        ],
        metadata={
            "blob_hash_reverified": True,
            "verified_size_bytes": len(content),
            "parser_available": False,
            "physical_authority_unchanged": True,
        },
    )