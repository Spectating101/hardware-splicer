"""Adapters from structured engineering artifacts into Engineering Source Graph inputs."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .robot_model_import import ParsedRobotModel, parse_robot_model


SOURCE_ADAPTER_SCHEMA = "hardware_splicer.engineering_source_adapter.v1"


class AdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AdaptedSourceBundle(AdapterModel):
    schema_version: str = SOURCE_ADAPTER_SCHEMA
    sources: list[Dict[str, Any]] = Field(default_factory=list)
    robot_models: Dict[str, ParsedRobotModel] = Field(default_factory=dict)
    unresolved: list[Dict[str, Any]] = Field(default_factory=list)


class EngineeringSourceAdapterError(ValueError):
    pass


def _hash_payload(value: Any) -> str:
    rendered = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _source_id(row: Mapping[str, Any], index: int) -> str:
    return str(row.get("source_id") or row.get("id") or row.get("name") or f"source-{index + 1}")


def _robot_model_source(row: Mapping[str, Any], index: int) -> tuple[Dict[str, Any], ParsedRobotModel]:
    model_format = str(row.get("format") or row.get("model_format") or row.get("source_type") or "").lower()
    content = row.get("content") or row.get("xml") or row.get("text")
    if not isinstance(content, (str, bytes)):
        raise EngineeringSourceAdapterError(f"{model_format} source requires XML content")
    model = parse_robot_model(content, model_format)
    source_id = _source_id(row, index)
    claims: list[Dict[str, Any]] = [
        {"subject_id": model.model_id, "predicate": "robot_model_format", "value": model.model_format.value},
        {"subject_id": model.model_id, "predicate": "link_count", "value": len(model.links)},
        {"subject_id": model.model_id, "predicate": "joint_count", "value": len(model.joints)},
        {"subject_id": model.model_id, "predicate": "actuator_count", "value": len(model.actuators)},
    ]
    for link in model.links:
        claims.append(
            {
                "subject_id": link.link_id,
                "predicate": "robot_link",
                "value": {
                    "name": link.name,
                    "mass_kg": link.mass_kg,
                    "visual_refs": link.visual_refs,
                    "collision_refs": link.collision_refs,
                },
            }
        )
    for joint in model.joints:
        claims.extend(
            [
                {
                    "subject_id": joint.joint_id,
                    "predicate": "joint_relationship",
                    "value": {
                        "parent_link_id": joint.parent_link_id,
                        "child_link_id": joint.child_link_id,
                        "joint_type": joint.joint_type.value,
                    },
                },
                {
                    "subject_id": joint.joint_id,
                    "predicate": "joint_axis",
                    "value": joint.axis,
                },
                {
                    "subject_id": joint.joint_id,
                    "predicate": "joint_limits",
                    "value": joint.limits,
                },
            ]
        )
    source = {
        "source_id": source_id,
        "source_type": "cad",
        "uri": row.get("uri") or row.get("url"),
        "revision": row.get("revision") or row.get("version"),
        "content_hash": model.content_hash,
        "retrieved_at": row.get("retrieved_at"),
        "authority_ceiling": row.get("authority_ceiling") or "declared",
        "claims": claims,
        "metadata": {
            "adapter": SOURCE_ADAPTER_SCHEMA,
            "artifact_kind": model.model_format.value,
            "robot_model": model.model_dump(mode="json"),
            "original_metadata": dict(row.get("metadata") or {}),
        },
    }
    return source, model


def _firmware_manifest_source(row: Mapping[str, Any], index: int) -> Dict[str, Any]:
    manifest = row.get("manifest") if isinstance(row.get("manifest"), Mapping) else row
    source_id = _source_id(row, index)
    component_id = str(manifest.get("firmware_component_id") or manifest.get("component_id") or "firmware")
    fields = (
        "source_revision",
        "repository",
        "toolchain",
        "toolchain_version",
        "dependency_lock",
        "build_command",
        "binary_hash",
        "flash_command",
        "flash_result",
        "pin_map_hash",
        "board_profile",
        "hardware_revision",
        "configuration_hash",
    )
    claims = [
        {
            "subject_id": component_id,
            "predicate": field,
            "value": manifest.get(field),
        }
        for field in fields
        if manifest.get(field) not in (None, "", [], {})
    ]
    return {
        "source_id": source_id,
        "source_type": row.get("graph_source_type") or "repository",
        "uri": row.get("uri") or manifest.get("repository"),
        "revision": row.get("revision") or manifest.get("source_revision"),
        "content_hash": row.get("content_hash") or _hash_payload(manifest),
        "retrieved_at": row.get("retrieved_at"),
        "authority_ceiling": row.get("authority_ceiling") or "declared",
        "claims": claims,
        "metadata": {
            "adapter": SOURCE_ADAPTER_SCHEMA,
            "artifact_kind": "firmware_manifest",
            "firmware_manifest": dict(manifest),
        },
    }


def _ros_manifest_source(row: Mapping[str, Any], index: int) -> Dict[str, Any]:
    manifest = row.get("manifest") if isinstance(row.get("manifest"), Mapping) else row
    source_id = _source_id(row, index)
    node_id = str(manifest.get("node_id") or manifest.get("package") or manifest.get("robot_id") or "robot-middleware")
    claims: list[Dict[str, Any]] = []
    for field, predicate in (
        ("topics", "ros_topics"),
        ("services", "ros_services"),
        ("actions", "ros_actions"),
        ("frames", "coordinate_frames"),
        ("parameters", "ros_parameters"),
        ("urdf_revision", "urdf_revision"),
        ("middleware", "middleware"),
        ("distribution", "ros_distribution"),
    ):
        if manifest.get(field) not in (None, "", [], {}):
            claims.append({"subject_id": node_id, "predicate": predicate, "value": manifest[field]})
    return {
        "source_id": source_id,
        "source_type": row.get("graph_source_type") or "manual",
        "uri": row.get("uri") or row.get("url"),
        "revision": row.get("revision") or manifest.get("revision") or manifest.get("urdf_revision"),
        "content_hash": row.get("content_hash") or _hash_payload(manifest),
        "retrieved_at": row.get("retrieved_at"),
        "authority_ceiling": row.get("authority_ceiling") or "declared",
        "claims": claims,
        "metadata": {
            "adapter": SOURCE_ADAPTER_SCHEMA,
            "artifact_kind": "ros_interface_manifest",
            "ros_interface_manifest": dict(manifest),
        },
    }


def _measurement_source(row: Mapping[str, Any], index: int, *, telemetry: bool) -> Dict[str, Any]:
    source_id = _source_id(row, index)
    values = row.get("measurements") or row.get("samples") or row.get("values") or []
    if isinstance(values, Mapping):
        values = [
            {"subject_id": row.get("subject_id") or "machine", "predicate": key, "value": value}
            for key, value in values.items()
        ]
    if not isinstance(values, list):
        raise EngineeringSourceAdapterError("measurement or telemetry values must be a list or mapping")
    claims: list[Dict[str, Any]] = []
    for item_index, item in enumerate(values):
        if not isinstance(item, Mapping):
            claims.append(
                {
                    "subject_id": str(row.get("subject_id") or "machine"),
                    "predicate": f"sample_{item_index + 1}",
                    "value": item,
                    "authority": "measured",
                }
            )
            continue
        claim = {
            "subject_id": str(item.get("subject_id") or row.get("subject_id") or "machine"),
            "predicate": str(item.get("predicate") or item.get("field") or item.get("name") or f"sample_{item_index + 1}"),
            "value": item.get("value", item.get("measurement", item.get("sample"))),
            "units": item.get("units"),
            "confidence": item.get("confidence"),
            "authority": item.get("authority") or "measured",
            "metadata": {
                "instrument_id": item.get("instrument_id") or row.get("instrument_id"),
                "calibration_id": item.get("calibration_id") or row.get("calibration_id"),
                "timestamp": item.get("timestamp"),
                "sample_count": item.get("sample_count"),
            },
        }
        claims.append(claim)
    payload_hash = row.get("content_hash") or _hash_payload(values)
    return {
        "source_id": source_id,
        "source_type": "telemetry" if telemetry else "measurement",
        "uri": row.get("uri") or row.get("url"),
        "revision": row.get("revision") or row.get("capture_id") or row.get("run_id"),
        "content_hash": payload_hash,
        "retrieved_at": row.get("retrieved_at"),
        "authority_ceiling": row.get("authority_ceiling") or "measured",
        "claims": claims,
        "metadata": {
            "adapter": SOURCE_ADAPTER_SCHEMA,
            "artifact_kind": "telemetry" if telemetry else "measurement",
            "instrument_id": row.get("instrument_id"),
            "calibration_id": row.get("calibration_id"),
            "sample_rate_hz": row.get("sample_rate_hz"),
        },
    }


def _graph_visible_metadata(source: Mapping[str, Any]) -> Dict[str, Any]:
    """Expose adapter metadata at the graph ingestion boundary without losing it.

    ``EngineeringSourceGraph`` treats unknown top-level fields as source metadata. Older
    adapter rows placed structured artifact identity only inside a nested ``metadata``
    object, so graph normalization turned it into ``source.metadata[\"metadata\"]`` and
    downstream projectors could not see ``artifact_kind`` or its manifest. Promote the
    declared adapter metadata to graph-visible top-level keys while retaining the nested
    object for backwards compatibility. No authority is upgraded here.
    """

    row = dict(source)
    metadata = row.get("metadata")
    if isinstance(metadata, Mapping):
        for key, value in metadata.items():
            if key not in row:
                row[str(key)] = value
    return row


def adapt_engineering_source(value: Mapping[str, Any] | str, index: int = 0) -> tuple[Dict[str, Any] | str, ParsedRobotModel | None]:
    if not isinstance(value, Mapping):
        return str(value), None
    row = dict(value)

    # A source that already carries graph identity and an explicit claims list is already
    # normalized. Re-adapting it as a raw measurement/telemetry artifact would discard the
    # claims and rewrite provenance metadata. Preserve graph-ready rows byte-for-structure;
    # downstream graph validation remains responsible for judging the claims themselves.
    if (
        str(row.get("source_id") or "").strip()
        and str(row.get("source_type") or "").strip()
        and isinstance(row.get("claims"), list)
    ):
        return row, None

    artifact_kind = str(
        row.get("artifact_kind")
        or row.get("format")
        or row.get("model_format")
        or row.get("source_type")
        or ""
    ).strip().lower().replace("-", "_")
    if artifact_kind in {"urdf", "sdf", "mjcf"}:
        source, model = _robot_model_source(row, index)
        return _graph_visible_metadata(source), model
    if artifact_kind in {"firmware_manifest", "firmware", "build_manifest"}:
        return _graph_visible_metadata(_firmware_manifest_source(row, index)), None
    if artifact_kind in {"ros_manifest", "ros_interface_manifest", "ros_interfaces", "middleware_manifest"}:
        return _graph_visible_metadata(_ros_manifest_source(row, index)), None
    if artifact_kind in {"measurement", "measurements", "instrument_capture"}:
        return _graph_visible_metadata(_measurement_source(row, index, telemetry=False)), None
    if artifact_kind in {"telemetry", "rosbag", "ros_bag", "time_series"}:
        return _graph_visible_metadata(_measurement_source(row, index, telemetry=True)), None
    return row, None


def adapt_engineering_sources(values: Iterable[Mapping[str, Any] | str] | None) -> AdaptedSourceBundle:
    sources: list[Dict[str, Any]] = []
    robot_models: Dict[str, ParsedRobotModel] = {}
    unresolved: list[Dict[str, Any]] = []
    for index, value in enumerate(values or []):
        try:
            source, model = adapt_engineering_source(value, index)
        except EngineeringSourceAdapterError as exc:
            unresolved.append({"index": index, "reason": str(exc), "source": dict(value) if isinstance(value, Mapping) else str(value)})
            continue
        if isinstance(source, Mapping):
            source_row = dict(source)
            sources.append(source_row)
            if model is not None:
                robot_models[str(source_row["source_id"])] = model
        else:
            unresolved.append({"index": index, "reason": "unresolved source reference", "source": source})
    return AdaptedSourceBundle(sources=sources, robot_models=robot_models, unresolved=unresolved)
