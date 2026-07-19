"""Blueprint-shaped project package from splice/synthesis build artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .intent_clarifier import analyze_intent_clarifications

SCHEMA_VERSION = "hardware_splicer.project_package.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path | None) -> Dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return [str(item).strip() for item in value if str(item).strip()]


def _bom_lines_from_sources(
    *,
    salvage_bom: Mapping[str, Any],
    compile_bom: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    if salvage_bom.get("lines"):
        return [dict(row) for row in salvage_bom.get("lines") or []]
    if compile_bom.get("lines"):
        return [dict(row) for row in compile_bom.get("lines") or []]
    rows: List[Dict[str, Any]] = []
    for module_id in candidate.get("selected_modules") or []:
        rows.append(
            {
                "module_id": str(module_id),
                "description": str(module_id),
                "qty": 1,
                "source": "synthesis_candidate",
            }
        )
    return rows


def _estimate_cost_usd(lines: List[Mapping[str, Any]]) -> Optional[float]:
    total = 0.0
    found = False
    for row in lines:
        for key in ("estimated_unit_usd", "unit_price_usd", "price_usd"):
            value = row.get(key)
            if value is None:
                continue
            try:
                qty = float(row.get("qty") or 1)
                total += float(value) * qty
                found = True
                break
            except (TypeError, ValueError):
                continue
        subtotal = row.get("line_total_usd")
        if subtotal is not None:
            try:
                total += float(subtotal)
                found = True
            except (TypeError, ValueError):
                pass
    return round(total, 2) if found else None


def _graph_node_label(graph: Mapping[str, Any], node_id: str) -> str:
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        if str(node.get("id")) != str(node_id):
            continue
        module_id = str(node.get("moduleId") or node_id)
        try:
            from .pcb.module_registry import find_module

            spec = find_module(module_id)
            if spec:
                return str(spec.get("label") or module_id)
        except Exception:
            pass
        return module_id
    return str(node_id)


def _format_wire_endpoint(graph: Mapping[str, Any], endpoint: Any) -> str:
    if isinstance(endpoint, Mapping):
        node_id = str(endpoint.get("nodeId") or "")
        pin = str(endpoint.get("pinId") or endpoint.get("pin") or "")
        if node_id and pin:
            return f"**{_graph_node_label(graph, node_id)}** `{pin}`"
        if pin:
            return f"`{pin}`"
    return f"`{endpoint}`"


def _wiring_narrative(
    *,
    splice_plan: Mapping[str, Any],
    candidate: Mapping[str, Any],
    graph: Mapping[str, Any],
) -> str:
    lines: List[str] = ["# Wiring guide", ""]
    topology = list(candidate.get("generated_topology") or [])
    if topology:
        lines.append("## Topology operators")
        for op in topology:
            if not isinstance(op, dict):
                continue
            lines.append(
                f"- **{op.get('operator_id')}** (`{op.get('operator_type')}`): "
                f"{', '.join(_string_list(op.get('inputs')))} → {', '.join(_string_list(op.get('outputs')))}"
            )
            if op.get("notes"):
                lines.append(f"  - {op['notes']}")
        lines.append("")

    splice_pkg = splice_plan.get("splice_package") if isinstance(splice_plan.get("splice_package"), dict) else splice_plan
    wiring_steps = splice_pkg.get("wiring_steps") or splice_plan.get("wiring_steps") or []
    if wiring_steps:
        lines.append("## Harness / splice steps")
        for index, step in enumerate(wiring_steps, start=1):
            if isinstance(step, dict):
                lines.append(f"{index}. {step.get('instruction') or step.get('step') or step}")
            else:
                lines.append(f"{index}. {step}")
        lines.append("")

    # Prefer bring-up card lines when present (already humanized + donor harness).
    bringup = splice_plan.get("bringup_card") if isinstance(splice_plan.get("bringup_card"), dict) else {}
    bringup_connections = list(bringup.get("connections") or [])
    if bringup_connections:
        lines.append("## Bench hookup (bring-up card)")
        if bringup.get("sourced_from_graph"):
            lines.append("_Pins match compiled build_graph / firmware scaffold._")
            lines.append("")
        for row in bringup_connections[:50]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('from')} → {row.get('to')}"
                + (f" — {row.get('purpose')}" if row.get("purpose") else "")
            )
        if len(bringup_connections) > 50:
            lines.append(f"- … {len(bringup_connections) - 50} more connections")
        lines.append("")
    else:
        wires = list(graph.get("wires") or [])
        if wires:
            lines.append("## Net connections (compile graph)")
            for wire in wires[:40]:
                if not isinstance(wire, dict):
                    continue
                lines.append(
                    f"- {_format_wire_endpoint(graph, wire.get('from'))} → "
                    f"{_format_wire_endpoint(graph, wire.get('to'))}"
                    + (f" ({wire.get('net')})" if wire.get("net") else "")
                )
            if len(wires) > 40:
                lines.append(f"- … {len(wires) - 40} more connections")
            lines.append("")

    if len(lines) <= 2:
        lines.append("_No wiring narrative generated yet — add load/supply details or run synthesis/splice planning._")
    return "\n".join(lines).strip() + "\n"


def _assembly_steps(
    *,
    bom_lines: List[Mapping[str, Any]],
    bringup: Mapping[str, Any],
    bench_session: Mapping[str, Any],
    splice_plan: Mapping[str, Any],
    gates: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = [
        {
            "step": 1,
            "title": "Gather parts",
            "body": f"Collect {len(bom_lines)} BOM line(s). Verify MPNs and donor harness labels before soldering.",
        },
        {
            "step": 2,
            "title": "Fabricate or prepare carrier PCB",
            "body": "Order or mill the carrier board from KiCad outputs. Preview copper is not production-ready unless gates say otherwise.",
        },
    ]
    splice_pkg = splice_plan.get("splice_package") if isinstance(splice_plan.get("splice_package"), dict) else splice_plan
    reuse = splice_pkg.get("reuse_blocks") or splice_plan.get("reuse_blocks") or []
    if reuse:
        steps.append(
            {
                "step": 3,
                "title": "Prepare donor splice",
                "body": "Follow splice plan reuse blocks. Do not cut donor sections until continuity and rail gates are planned.",
            }
        )
    bench_checks = bringup.get("bench_checks") or []
    if bench_checks or bench_session.get("open_gate_count"):
        steps.append(
            {
                "step": len(steps) + 1,
                "title": "Bench measurements",
                "body": "Complete open evidence gates (DMM / PSU ramp / thermal) before energizing donor harnesses.",
            }
        )
    steps.append(
        {
            "step": len(steps) + 1,
            "title": "First power-on",
            "body": (
                "Authorized only when gates report power_on_authorized."
                if gates.get("power_on_authorized")
                else "BLOCKED until bench gates close and compile/fab checks pass."
            ),
        }
    )
    return steps


def _gate_section(
    *,
    result: Mapping[str, Any],
    design_quality_gate: Mapping[str, Any],
    bench_session: Mapping[str, Any],
    candidate: Mapping[str, Any],
    fabrication_inspection: Mapping[str, Any],
) -> Dict[str, Any]:
    blocked = bool(candidate.get("result") == "blocked" or result.get("error") == "candidate_blocked")
    compile_ok = bool(result.get("ok"))
    blockers: List[str] = _string_list(candidate.get("missing_evidence"))
    for row in candidate.get("constraints") or []:
        if isinstance(row, dict) and row.get("status") in {"blocked", "open"}:
            blockers.append(str(row.get("requirement") or row.get("constraint_id")))
    if not compile_ok and not blocked:
        blockers.append(str(result.get("message") or result.get("error") or "compile_not_ready"))
    if bench_session.get("critical_open_count"):
        blockers.append(f"{bench_session['critical_open_count']} critical bench gate(s) open")

    if blocked:
        verdict = "BLOCKED"
    elif compile_ok and bench_session.get("power_on_authorized"):
        verdict = "POWER_ON_AUTHORIZED"
    elif compile_ok and design_quality_gate.get("build_ready"):
        verdict = "COMPILE_READY_REVIEW_BENCH"
    elif compile_ok:
        verdict = "COMPILE_OK_REVIEW_REQUIRED"
    else:
        verdict = "BLOCKED"

    return {
        "verdict": verdict,
        "compile_ok": compile_ok,
        "build_ready": bool(design_quality_gate.get("build_ready")),
        "fabrication_ready": bool(design_quality_gate.get("fabrication_ready")),
        "fab_recommendation": design_quality_gate.get("fab_recommendation"),
        "copper_tier": design_quality_gate.get("copper_tier"),
        "power_on_authorized": bool(bench_session.get("power_on_authorized")),
        "bench_readiness": bench_session.get("readiness"),
        "open_gate_count": bench_session.get("open_gate_count"),
        "critical_open_count": bench_session.get("critical_open_count"),
        "blockers": blockers[:20],
        "next_actions": _string_list(bench_session.get("next_actions"))[:10],
        "fabrication_inspection_summary": fabrication_inspection.get("summary"),
    }


def build_project_package(
    build_dir: str | Path,
    *,
    result: Mapping[str, Any] | None = None,
    source: str = "auto",
) -> Dict[str, Any]:
    """Assemble PROJECT_PACKAGE.v1 from an on-disk build directory."""
    root = Path(build_dir).resolve()
    payload = dict(result or {})
    intake = _read_json(root / "PROJECT_INTAKE.json")
    if not intake and payload.get("goal"):
        intake = {"goal": payload.get("goal"), "project_name": payload.get("project_name")}
    clarifier = analyze_intent_clarifications(intake or payload)

    splice_plan = _read_json(root / "SPLICE_PLAN.json")
    if not splice_plan and isinstance(payload.get("salvage_package"), dict):
        splice_plan = dict(payload["salvage_package"])
    candidate = dict(payload.get("candidate") or {})
    candidate_path = root / "SYNTHESIS_CANDIDATE.json"
    if not candidate and candidate_path.is_file():
        candidate = _read_json(candidate_path)

    salvage_bom = _read_json(root / "SALVAGE_BOM.json")
    compile_bom = _read_json(root / "build_compilation" / "BOM.json")
    if not compile_bom:
        compile_bom = _read_json(root / "BOM.json")
    bringup = _read_json(root / "BRINGUP_CARD.json")
    bench_session = _read_json(root / "SPLICE_BENCH_SESSION.json")
    if not bench_session and isinstance(payload.get("bench_session"), dict):
        bench_session = dict(payload["bench_session"])
    design_quality_gate = dict(payload.get("design_quality_gate") or _read_json(root / "build_compilation" / "DESIGN_QUALITY_GATE.json"))
    fabrication_inspection = _read_json(root / "FABRICATION_INSPECTION.json")
    physical_assembly = _read_json(root / "physical_assembly" / "ASSEMBLY_MAP.json")

    build_graph = _read_json(root / "build_compilation" / "build_graph.json")
    if not build_graph and payload.get("compose_result"):
        build_graph = dict((payload.get("compose_result") or {}).get("graph") or {})

    bom_lines = _bom_lines_from_sources(salvage_bom=salvage_bom, compile_bom=compile_bom, candidate=candidate)
    cost_usd = _estimate_cost_usd(bom_lines) or salvage_bom.get("estimated_total_usd")

    goal = str(payload.get("goal") or intake.get("goal") or splice_plan.get("goal") or candidate.get("notes") or "Hardware project")
    summary_parts = [
        str(splice_plan.get("verdict") or candidate.get("result") or payload.get("salvage_verdict") or "").strip(),
        str(payload.get("claim_boundary") or "").strip(),
    ]
    summary = " ".join(part for part in summary_parts if part) or "Generated hardware project package."

    wiring_md = _wiring_narrative(splice_plan=splice_plan, candidate=candidate, graph=build_graph)
    gates = _gate_section(
        result=payload,
        design_quality_gate=design_quality_gate,
        bench_session=bench_session,
        candidate=candidate,
        fabrication_inspection=fabrication_inspection,
    )
    assembly_steps = _assembly_steps(
        bom_lines=bom_lines,
        bringup=bringup,
        bench_session=bench_session,
        splice_plan=splice_plan,
        gates=gates,
    )

    package = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "source": source,
        "build_dir": str(root),
        "info": {
            "project_name": payload.get("project_name") or intake.get("project_name") or root.name,
            "goal": goal,
            "summary": summary,
            "assumptions": _string_list(candidate.get("assumptions")),
            "clarifier": clarifier,
            "cost_estimate_usd": cost_usd,
            "build_id": payload.get("build_id"),
            "archetype": payload.get("archetype") or intake.get("archetype"),
        },
        "bom": {
            "line_count": len(bom_lines),
            "lines": bom_lines,
            "estimated_total_usd": cost_usd,
            "salvage_bom_path": str(root / "SALVAGE_BOM.json") if (root / "SALVAGE_BOM.json").is_file() else "",
            "compile_bom_path": str(root / "build_compilation" / "BOM.json")
            if (root / "build_compilation" / "BOM.json").is_file()
            else "",
        },
        "wiring": {
            "topology_operators": list(candidate.get("generated_topology") or []),
            "graph_wire_count": len(build_graph.get("wires") or []),
            "narrative_markdown": wiring_md,
        },
        "mech": {
            "physical_assembly": physical_assembly,
            "assembly_ready": physical_assembly.get("assembly_ready"),
            "preview_path": str(root / "physical_assembly" / "assembly_preview.scad")
            if (root / "physical_assembly" / "assembly_preview.scad").is_file()
            else "",
        },
        "firmware_scaffold": payload.get("firmware_scaffold")
        or _read_json(root / "firmware" / "FIRMWARE_SCAFFOLD.json")
        or (splice_plan.get("firmware_scaffold") if isinstance(splice_plan, dict) else None),
        "mechanism_pack": payload.get("mechanism_pack")
        or _read_json(root / "MECHANISM_PACK.json")
        or (splice_plan.get("mechanism_pack") if isinstance(splice_plan, dict) else None),
        "mechatronics_authority": payload.get("mechatronics_authority")
        or _read_json(root / "MECHATRONICS_AUTHORITY.json")
        or (splice_plan.get("mechatronics_authority") if isinstance(splice_plan, dict) else None),
        "instructions": {
            "assembly_steps": assembly_steps,
            "bringup_markdown": str(bringup.get("markdown") or ""),
            "bringup_path": str(root / "BRINGUP_CARD.md") if (root / "BRINGUP_CARD.md").is_file() else "",
        },
        "parts": {
            "selected_modules": _string_list(candidate.get("selected_modules"))
            or _string_list(splice_plan.get("resolved_modules")),
            "selected_parts": list(candidate.get("selected_parts") or []),
        },
        "gates": gates,
        "artifacts": dict(payload.get("artifacts") or {}),
    }
    return package


def render_project_page_md(package: Mapping[str, Any]) -> str:
    info = dict(package.get("info") or {})
    bom = dict(package.get("bom") or {})
    gates = dict(package.get("gates") or {})
    instructions = dict(package.get("instructions") or {})
    lines = [
        f"# {info.get('project_name') or 'Hardware-Splicer Project'}",
        "",
        f"**Goal:** {info.get('goal') or '—'}",
        "",
        f"**Summary:** {info.get('summary') or '—'}",
        "",
        f"**Estimated cost (USD):** {info.get('cost_estimate_usd') if info.get('cost_estimate_usd') is not None else '—'}",
        "",
        "## INFO",
        f"- Build ID: `{info.get('build_id') or '—'}`",
        f"- Archetype: `{info.get('archetype') or '—'}`",
        f"- Clarification needed: `{((info.get('clarifier') or {}).get('needs_clarification'))}`",
        "",
        "## BOM",
        f"- Lines: **{bom.get('line_count', 0)}**",
    ]
    for row in (bom.get("lines") or [])[:12]:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('ref') or row.get('module_id')}` — {row.get('description') or row.get('module_id')} × {row.get('qty', 1)}")
    if int(bom.get("line_count") or 0) > 12:
        lines.append(f"- … {int(bom['line_count']) - 12} more")
    lines.extend(["", "## WIRING", "", str((package.get("wiring") or {}).get("narrative_markdown") or "_See WIRING_GUIDE.md_"), ""])
    lines.extend(["## INSTRUCTIONS", ""])
    for step in instructions.get("assembly_steps") or []:
        if isinstance(step, dict):
            lines.append(f"{step.get('step')}. **{step.get('title')}** — {step.get('body')}")
    lines.extend(
        [
            "",
            "## GATES",
            f"- **Verdict:** `{gates.get('verdict')}`",
            f"- Compile OK: `{gates.get('compile_ok')}`",
            f"- Build ready: `{gates.get('build_ready')}`",
            f"- Power-on authorized: `{gates.get('power_on_authorized')}`",
            f"- Fab recommendation: `{gates.get('fab_recommendation') or '—'}`",
        ]
    )
    blockers = _string_list(gates.get("blockers"))
    if blockers:
        lines.append("- Blockers:")
        for blocker in blockers[:8]:
            lines.append(f"  - {blocker}")
    return "\n".join(lines).strip() + "\n"


def write_project_package_artifacts(
    build_dir: str | Path,
    *,
    result: Mapping[str, Any] | None = None,
    source: str = "auto",
    candidate: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Write PROJECT_PACKAGE.json, PROJECT_PAGE.md, WIRING_GUIDE.md, ASSEMBLY_GUIDE.md."""
    root = Path(build_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if candidate:
        (root / "SYNTHESIS_CANDIDATE.json").write_text(json.dumps(dict(candidate), indent=2), encoding="utf-8")
    package = build_project_package(root, result=result, source=source)
    package_path = root / "PROJECT_PACKAGE.json"
    page_path = root / "PROJECT_PAGE.md"
    wiring_path = root / "WIRING_GUIDE.md"
    assembly_path = root / "ASSEMBLY_GUIDE.md"
    package_path.write_text(json.dumps(package, indent=2), encoding="utf-8")
    page_path.write_text(render_project_page_md(package), encoding="utf-8")
    wiring_path.write_text(str((package.get("wiring") or {}).get("narrative_markdown") or ""), encoding="utf-8")
    assembly_lines = ["# Assembly guide", ""]
    for step in (package.get("instructions") or {}).get("assembly_steps") or []:
        if isinstance(step, dict):
            assembly_lines.append(f"{step.get('step')}. **{step.get('title')}**")
            assembly_lines.append(f"   {step.get('body')}")
            assembly_lines.append("")
    assembly_path.write_text("\n".join(assembly_lines).strip() + "\n", encoding="utf-8")

    csv_hint = ""
    salvage_csv = root / "SALVAGE_BOM.csv"
    compile_csv = root / "build_compilation" / "BOM.csv"
    if salvage_csv.is_file():
        csv_hint = str(salvage_csv)
    elif compile_csv.is_file():
        csv_hint = str(compile_csv)

    oss_exports: Dict[str, Any] = {}
    try:
        from .integrations.oss_export_bundle import run_oss_export_bundle

        oss_exports = run_oss_export_bundle(
            root,
            build_id=str((result or {}).get("build_id") or package.get("info", {}).get("build_id") or ""),
            project_name=str(
                (result or {}).get("project_name") or package.get("info", {}).get("project_name") or root.name
            ),
            enforce_roots=False,
        )
        package["oss_exports"] = {
            "present_count": oss_exports.get("present_count"),
            "exports": oss_exports.get("exports") or [],
            "oss_mech_refs": oss_exports.get("oss_mech_refs") or [],
        }
        package_path.write_text(json.dumps(package, indent=2), encoding="utf-8")
    except Exception:
        oss_exports = {"ok": False, "skipped": True, "reason": "oss_export_bundle_error"}

    return {
        "schema_version": SCHEMA_VERSION,
        "package": package,
        "artifacts": {
            "project_package": str(package_path),
            "project_page": str(page_path),
            "wiring_guide": str(wiring_path),
            "assembly_guide": str(assembly_path),
            "bom_csv": csv_hint,
            "oss_exports": str((root / "build_compilation" / "exports" / "OSS_EXPORTS.json"))
            if (root / "build_compilation" / "exports" / "OSS_EXPORTS.json").is_file()
            else "",
        },
        "gates": package.get("gates"),
        "oss_exports": oss_exports,
    }
