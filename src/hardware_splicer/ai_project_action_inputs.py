"""Typed data inputs for deterministic AI project tools.

Executable inputs must be preserved exactly or rejected. The prose/context
sanitizer may truncate collections, which is inappropriate for circuit graphs.
Paths, executable commands and execution-policy overrides are not tool inputs.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr


MAX_ACTION_INPUT_BYTES = 2 * 1024 * 1024


class ComposePreviewInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    phrase: StrictStr | None = None
    goal: StrictStr | None = None
    module_ids: list[StrictStr] | None = None
    resolved_modules: list[dict[str, Any]] | None = None
    canvas_nodes: list[dict[str, Any]] | None = None
    canvas_wires: list[dict[str, Any]] | None = None
    netlist: dict[str, Any] | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    material_mode: StrictStr | None = None
    salvage_mode: StrictBool = False
    wire_only: StrictBool = False
    build_id: StrictStr | None = None
    splice_plan: dict[str, Any] | None = None
    drc_fixup: dict[str, float] | None = None


class PromoteSourcesInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ids: list[StrictStr] | None = Field(default=None, min_length=1, max_length=16)
    primary_source_id: StrictStr | None = None


class KicadEditInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["schematic", "pcb"]
    ops: list[dict[str, Any]] = Field(min_length=1, max_length=200)
    note: StrictStr = Field(default="", max_length=2000)


ACTION_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "run_compose": ComposePreviewInputs,
    "promote_registered_sources": PromoteSourcesInputs,
    "propose_kicad_edit": KicadEditInputs,
}

ACTION_INPUT_HINT = (
    "run_compose inputs can contain a structured netlist, canvas_nodes/canvas_wires, "
    "or module_ids/resolved_modules with constraints and optional splice_plan/build_id. "
    "Preserve complete component, pin and connection data. Output directories and "
    "execution flags are server-owned; do not supply out_dir, commands, "
    "allow_llm_first or export_gerber."
    " promote_registered_sources accepts only optional registered source_ids and "
    "primary_source_id; it imports a source bundle into editable project artifacts. "
    "propose_kicad_edit accepts kind (pcb or schematic), ops, and optional note; "
    "ops use native object ref/uuid with move, rotate, set_property, delete, "
    "PCB set_track_width, or schematic set_flag/add_label. It opens a pending "
    "candidate review; it never accepts the edit. Source and base revision come "
    "from the project, never caller paths or raw native file content."
)


def validate_action_inputs(action_type: str, value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a supported tool's bounded JSON without silently dropping data."""
    encoded = json.dumps(dict(value), ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_ACTION_INPUT_BYTES:
        raise ValueError("AI action inputs exceed the bounded JSON ceiling")
    model = ACTION_INPUT_MODELS[action_type]
    return model.model_validate(dict(value)).model_dump(mode="json", exclude_unset=True)


def action_input_schemas() -> dict[str, Any]:
    return {name: model.model_json_schema() for name, model in ACTION_INPUT_MODELS.items()}
