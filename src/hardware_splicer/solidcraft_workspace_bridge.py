"""Non-authoritative, parametric CAD workspace handoff to SolidCraft.

SolidCraft (formerly SolveCraft) 0.16.2 exposes a JSON command registry,
MCP server, desktop and web surfaces. Generate a conservative concept
envelope ONLY when explicitly declared dimensions exist. Do not invent
donor geometry from advertisements. The generated shape is never a
fabrication drawing or measured assembly.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from math import isfinite

SCHEMA="hardware_splicer.solidcraft_workspace_bridge.v1"
UPSTREAM="https://github.com/tangency-labs/solidcraft"
UPSTREAM_RELEASE="v0.16.2"


def build_solidcraft_workspace_handoff(
    intake: Mapping[str,Any], functional: Mapping[str,Any],
)->dict[str,Any]:
    if not isinstance(intake,Mapping) or not isinstance(functional,Mapping):
        raise ValueError("intake and functional plan are required")
    raw=intake.get("concept_envelope_mm")
    domain=functional.get("functional_domain")
    result={
        "schema_version":SCHEMA,
        "cad_backend":"SolidCraft",
        "cad_backend_repo":UPSTREAM,
        "tested_protocol_release":UPSTREAM_RELEASE,
        "cad_workspace_kind":"editable_parametric_feature_timeline",
        "functional_domain":domain,
        "script_ready":False,
        "blocker":None,
        "command_script":None,
        "geometry_source":"NO_GEOMETRY",
        "materialized_cad_model_exists":False,
        "design_is_actual_salvaged_assembly":False,
        "component_fit_verified":False,
        "mechanical_dimensions_measured":False,
        "electrical_interface_verified":False,
        "power_or_fabrication_authorized":False,
    }
    if not functional.get("functional_decomposition_supported"):
        result["blocker"]="Functional domain unresolved; do not draw a fabricated substitute machine"
        return result
    if not isinstance(raw,Mapping):
        result["blocker"]="Missing explicitly declared concept_envelope_mm; no inferred donor geometry permitted"
        return result
    keys=("width","depth","height")
    if set(raw)!=set(keys):
        raise ValueError("concept_envelope_mm must have width, depth, height only")
    dims={}
    for key in keys:
        val=raw[key]
        if isinstance(val,bool) or not isinstance(val,(int,float)) or not isfinite(val) or not 1 <= val <= 2000:
            raise ValueError("dimension must be a finite numerical millimetre measurement 1..2000")
        dims[key]=round(float(val),4)
    w,d,h=(dims[key] for key in keys)
    commands=[
        {"command":"sketch.create","params":{"plane":"XY","name":"HS_Conceptual_Envelope"}},
        {"command":"sketch.rectangle.two_point","params":{"p0":[0,0],"p1":[w,d]}},
        {"command":"sketch.finish","params":{}},
        {"command":"solid.extrude","params":{"distance":h,"body_name":"HS_ConceptEnvelope"}},
    ]
    result.update({
        "script_ready":True,
        "geometry_source":"EXPLICIT_USER_OR_TEST_FIXTURE_CONCEPT_ENVELOPE",
        "concept_envelope_mm":dims,
        "expected_envelope_volume_mm3":round(w*d*h,4),
        "command_script":{"commands":commands},
        "blocker":None,
        "concept_only_not_assembly":True,
        "cad_commands_are_not_hardware_operations":True,
    })
    return result
