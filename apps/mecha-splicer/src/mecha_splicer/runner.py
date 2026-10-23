from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .bundle import generate_bundle as _generate_bundle
from .engines.catalog import MechanicalCatalog
from .engines.composer import compose_project
from .engines.control import synthesize_control_profile
from .engines.economics import estimate_digital_pack
from .engines.fx import convert, get_rate
from .engines.parts_meta import build_parts_meta
from .engines.procurement import apply_overrides, load_overrides, lock_bom, write_buy_list_csv, write_lock_report_md
from .engines.safety import evaluate_safety_checks
from .engines.sim import run_simulation_summary
from .engines.splicer3d_client import Splicer3DClient
from .spec import ProjectSpec


def run(
    spec: Dict[str, Any],
    *,
    out_dir: Optional[str | Path] = None,
    use_3d_splicer: bool = False,
    render_stl: bool = False,
    include_pricing: bool = False,
    sku_overrides_path: Optional[str | Path] = None,
    render_openscad_stl: bool = False,
    openscad_docker_image: Optional[str] = None,
    report_currency: str = "TWD",
    simulation_fidelity: Optional[str] = None,
    structural_screening: str = "advisory",
    structural_mesh_sizes_mm: tuple[float, ...] = (8., 6., 5.),
    structural_pin_drive_mm: float = .02,
    structural_radial_clearance_mm: float = .005,
) -> Dict[str, Any]:
    """
    High-level runner:
      - Generates the base bundle (OpenSCAD + DFM + BOM)
      - Adds simulation/control/safety analysis
      - Optionally calls 3d-splicer for a CadQuery script/STL (electronics-anchored enclosure only)
      - Adds procurement/commerce/evidence outputs
    """
    project = ProjectSpec.model_validate(spec)
    if simulation_fidelity is not None:
        project = ProjectSpec.model_validate({**project.model_dump(), "simulation_fidelity": simulation_fidelity})
    project = _auto_fill_from_electronics(project)
    project = _apply_mode_defaults(project)
    project, composition = compose_project(project)
    # An enclosure always gets a no-assumptions construction comparison.
    # This is advisory only: no alternative CAD is auto-selected.
    if project.enclosure is not None and project.construction is None:
        project = ProjectSpec.model_validate({
            **project.model_dump(), "construction": {"preference":"auto"},
        })

    bundle = _generate_bundle(project.model_dump(), out_dir=out_dir)
    bundle["parts"] = [p.to_dict() for p in build_parts_meta(project, bundle.get("outputs") or [])]
    bundle["composition"] = composition
    bundle["simulation"] = run_simulation_summary(project, fidelity=project.simulation_fidelity)
    bundle["control_profile"] = synthesize_control_profile(project)
    bundle["safety"] = evaluate_safety_checks(project)

    # The mechanical solver is an OPTIONAL, LOCAL bounded capability.
    # Every ordinary Mecha build receives an explicit advisory; only the
    # opt-in "run" mode pays for Gmsh/FEM or writes structural artifacts.
    if structural_screening not in {"off", "advisory", "run"}:
        raise ValueError("structural_screening must be off, advisory, or run")
    if structural_screening == "run" and out_dir is None:
        raise ValueError("structural_screening='run' requires out_dir")
    try:
        from hardware_splicer.mechanical_workflow_integration import screen_mecha_project
        structural = screen_mecha_project(
            project.model_dump(mode="json"),
            out_dir=out_dir if out_dir is not None else ".",
            mode=structural_screening,
            mesh_sizes_mm=structural_mesh_sizes_mm,
            pin_drive_mm=structural_pin_drive_mm,
            clearance_mm=structural_radial_clearance_mm,
        )
    except ImportError as exc:
        structural = {
            "schema_version": "hardware_splicer.mechanical_workflow_bridge.v1",
            "status": "capability_unavailable",
            "blockers": ["hardware_splicer_mechanical_bridge_not_installed"],
            "failure_detail": str(exc)[:250],
            "structural_safety_verified": False,
            "fabrication_authorized": False,
            "release_authorized": False,
        }
    bundle["structural_screening"] = structural
    bundle["structural_release_blocked"] = bool(
        project.bracket is not None or
        structural.get("status") in {"solver_blocked", "unsupported_mechanical_topology"}
    )

    # Existing Mecha output remains the fallback. This is a zero-dependency
    # construction comparison, not a new generator or production approval.
    if project.construction is not None:
        try:
            from hardware_splicer.construction_alternatives import evaluate_construction_alternatives
        except ImportError:
            # Mecha-Splicer can also be installed without the HS package.
            bundle["construction_alternatives"] = {
                "status": "capability_unavailable",
                "blockers": ["hardware_splicer_construction_evaluator_not_installed"],
                "alternatives": [],
                "fabrication_authorized": False,
                "release_authorized": False,
            }
        else:
            from hardware_splicer.construction_alternatives import inspect_local_connector_assets
            bundle["construction_alternatives"] = evaluate_construction_alternatives(
                project.model_dump(mode="json")
            )
            if out_dir is not None:
                bundle["construction_alternatives"]["external_asset_integrity"] = (
                    inspect_local_connector_assets(
                        project.construction.model_dump(mode="json"),out_dir
                    )
                )
            else:
                bundle["construction_alternatives"]["external_asset_integrity"] = {
                    "status": "not_checked_no_local_build_folder",
                    "assets": [],
                    "assets_usable_for_manufacturing": False,
                }

    commerce = estimate_digital_pack(price_usd=29.0, support_minutes=10.0).to_dict()
    bundle["commerce"] = {"digital_pack": commerce, "assumptions": {"price_usd": 29.0, "support_minutes": 10.0}}

    if include_pricing:
        catalog_path = Path(__file__).resolve().parents[2] / "data/catalog/mechanical_catalog.jsonl"
        catalog = MechanicalCatalog(catalog_path)
        outp = Path(out_dir) if out_dir is not None else None

        effective_overrides_path: Optional[str | Path] = sku_overrides_path
        if effective_overrides_path is None and outp is not None and (outp / "SKU_OVERRIDES.json").exists():
            effective_overrides_path = outp / "SKU_OVERRIDES.json"

        overrides = load_overrides(effective_overrides_path)
        bom = bundle.get("bom") or []
        if isinstance(bom, list):
            unlocked = lock_bom(bom, catalog=catalog)
            bom_locked = apply_overrides(bom, overrides)
            locked = lock_bom(bom_locked, catalog=catalog)
            bundle["procurement"] = {
                "locked": [l.__dict__ for l in locked],
                "unlocked": [l.__dict__ for l in unlocked],
                "cogs_usd": round(sum(l.subtotal_usd for l in locked), 2),
                "overrides_path": str(effective_overrides_path) if effective_overrides_path else "",
            }
            try:
                fx_cache = Path(__file__).resolve().parents[2] / "data/fx_cache.json"
                fx = get_rate("USD", report_currency, cache_path=fx_cache)
                bundle["procurement"]["fx"] = fx.to_dict()
                bundle["procurement"][f"cogs_{report_currency.lower()}"] = round(convert(bundle["procurement"]["cogs_usd"], fx), 2)
            except Exception:
                pass
            if out_dir is not None:
                if effective_overrides_path:
                    try:
                        (outp / "SKU_OVERRIDES.json").write_text(Path(effective_overrides_path).read_text(encoding="utf-8"), encoding="utf-8")
                    except Exception:
                        pass
                write_buy_list_csv(outp / "BUY_LIST.csv", unlocked)
                write_buy_list_csv(outp / "BUY_LIST.locked.csv", locked)
                (outp / "bom.locked.json").write_text(json.dumps(bom_locked, indent=2), encoding="utf-8")
                write_lock_report_md(outp / "PROCUREMENT_LOCK_REPORT.md", locked)

    if use_3d_splicer and project.electronics is not None:
        payload = _to_3d_splicer_description(project)
        client = Splicer3DClient()
        try:
            if render_stl:
                resp = client.splice_stl(payload)
            else:
                resp = client.splice_script(payload)
            bundle["splicer3d"] = resp
            if out_dir is not None:
                outp = Path(out_dir)
                (outp / "splicer3d.json").write_text(json.dumps(resp, indent=2), encoding="utf-8")
        except Exception as e:
            fallback = {"ok": False, "error": str(e)}
            if render_stl:
                try:
                    script_resp = client.splice_script(payload)
                    fallback = {
                        **script_resp,
                        "ok": False,
                        "mode": "script_fallback",
                        "stl_error": str(e),
                        "error": "STL rendering failed; CadQuery script fallback was generated.",
                    }
                except Exception as script_error:
                    fallback["script_fallback_error"] = str(script_error)
            bundle["splicer3d"] = fallback
            if out_dir is not None:
                outp = Path(out_dir)
                outp.mkdir(parents=True, exist_ok=True)
                (outp / "splicer3d.json").write_text(json.dumps(fallback, indent=2), encoding="utf-8")

    if out_dir is not None:
        outp = Path(out_dir)
        outp.mkdir(parents=True, exist_ok=True)

        # Primary artifacts
        (outp / "MECH_CHECK.md").write_text(_render_mech_check(bundle), encoding="utf-8")
        (outp / "BUILD_RECIPE.md").write_text(_render_build_recipe(bundle), encoding="utf-8")
        (outp / "PARTS.json").write_text(json.dumps(bundle.get("parts") or [], indent=2), encoding="utf-8")
        (outp / "PRINT_PLAN.md").write_text(_render_print_plan(bundle), encoding="utf-8")
        if bundle.get("construction_alternatives"):
            construction = bundle["construction_alternatives"]
            (outp / "CONSTRUCTION_ALTERNATIVES.json").write_text(
                json.dumps(construction, indent=2, allow_nan=False), encoding="utf-8"
            )
            try:
                from hardware_splicer.construction_alternatives import render_construction_plan
            except ImportError:
                # Mecha must remain usable standalone without the HS package.
                content = (
                    "# Construction alternatives unavailable\n\n"
                    "HS's optional construction evaluator is not installed; "
                    "no alternative manufacturing method is approved.\n"
                )
            else:
                content = render_construction_plan(construction)
            (outp / "CONSTRUCTION_PLAN.md").write_text(content, encoding="utf-8")
            schedule = construction.get("hybrid_sheet_geometry") or {}
            if schedule.get("status")=="dimensioned_blank_cut_proposal":
                from hardware_splicer.construction_sheet_geometry import (
                    schedule_csv, schedule_svg, schedule_parts,
                )
                (outp / "HYBRID_PANEL_CUTS.csv").write_text(
                    schedule_csv(schedule),encoding="utf-8"
                )
                (outp / "HYBRID_PANEL_BLANKS.svg").write_text(
                    schedule_svg(schedule),encoding="utf-8"
                )
                (outp / "HYBRID_PARTS.json").write_text(
                    json.dumps(schedule_parts(
                        schedule,
                        project.construction.model_dump(mode="json"),
                        next((
                            row.get("connector_source") for row in construction.get("alternatives") or []
                            if row.get("method")=="sheet_hybrid"
                        ),None)
                    ),indent=2),encoding="utf-8"
                )
                (outp / "HYBRID_INTERFACE_REVIEW.json").write_text(
                    json.dumps({
                        "geometry":schedule["untransformed_interfaces"],
                        "status":"requires_manual_connector_and_cutout_layout",
                        "fabrication_authorized":False,
                        "warning":"Preliminary panel dimensions only. No actual joint seats, fasteners or port toolpaths.",
                    },indent=2),encoding="utf-8"
                )

        if render_openscad_stl:
            from .engines.render import render_openscad_to_stl

            renders = {}
            for out_name in bundle.get("outputs") or []:
                if not str(out_name).endswith(".scad"):
                    continue
                scad_path = outp / str(out_name)
                stl_path = outp / (Path(str(out_name)).stem + ".stl")
                renders[out_name] = render_openscad_to_stl(scad_path, stl_path, docker_image=openscad_docker_image)
            bundle["renders"] = renders
            (outp / "RENDER_REPORT.json").write_text(json.dumps(renders, indent=2), encoding="utf-8")

        # Evidence bundle
        evidence_files = _write_evidence_bundle(outp, bundle, project)
        bundle["evidence_files"] = evidence_files

        # Persist bundle + manifest after all outputs are present.
        (outp / "mecha_splicer.bundle.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        (outp / "MANIFEST.json").write_text(json.dumps(_manifest(outp), indent=2), encoding="utf-8")

    return bundle


def _auto_fill_from_electronics(project: ProjectSpec) -> ProjectSpec:
    if project.electronics is None:
        return project

    if project.enclosure is None:
        inner_w = project.electronics.pcb_w_mm + 10.0
        inner_d = project.electronics.pcb_h_mm + 10.0
        inner_h = 25.0
        project = ProjectSpec.model_validate(
            {
                **project.model_dump(),
                "enclosure": {
                    "name": f"{project.electronics.device}_enclosure",
                    "inner_w_mm": inner_w,
                    "inner_d_mm": inner_d,
                    "inner_h_mm": inner_h,
                    "mount_holes": [m.model_dump() for m in project.electronics.mounts],
                    "cutouts": [c.model_dump() for c in project.electronics.ports],
                },
            }
        )
        return project

    enc = project.enclosure
    if enc and not enc.mount_holes and project.electronics.mounts:
        enc.mount_holes = list(project.electronics.mounts)
    if enc and not enc.cutouts and project.electronics.ports:
        enc.cutouts = list(project.electronics.ports)
    return project


def _apply_mode_defaults(project: ProjectSpec) -> ProjectSpec:
    if project.mode != "professional":
        return project
    if project.print_settings is not None:
        return project
    return ProjectSpec.model_validate(
        {
            **project.model_dump(),
            "print_settings": {
                "material": "PETG",
                "layer_height_mm": 0.2,
                "perimeters": 5,
                "infill_pct": 45,
                "nozzle_mm": 0.4,
                "orientation": "best_guess",
            },
        }
    )


def _to_3d_splicer_description(project: ProjectSpec) -> Dict[str, Any]:
    e = project.electronics
    enc = project.enclosure
    if e is None or enc is None:
        raise ValueError("3d-splicer integration requires both: electronics and enclosure.")

    # 3d-splicer API expects this strict schema shape:
    # pcb.width_mm/height_mm/thickness_mm and ports with name/x/y/w/h/side.
    pcb = {
        "width_mm": e.pcb_w_mm,
        "height_mm": e.pcb_h_mm,
        "thickness_mm": e.pcb_t_mm,
        "corner_radius_mm": 3.0,
    }
    enclosure = {
        "wall_mm": enc.wall_mm,
        "clearance_mm": enc.clearance_mm,
        "lip_mm": max(1.0, float(enc.lid_mm)),
        "fillet_mm": 1.0,
    }

    side_map = {
        # Mecha-Splicer uses front/back; 3d-splicer uses bottom/top.
        "front": "bottom",
        "back": "top",
        "left": "left",
        "right": "right",
        "top": "top",
    }
    ports = []
    for p in e.ports:
        if p.kind == "rect" and p.rect:
            ports.append(
                {
                    "name": p.label or "port",
                    "type": "rect",
                    "x_mm": p.rect.x_mm,
                    "y_mm": p.rect.y_mm,
                    "w_mm": p.rect.w_mm,
                    "h_mm": p.rect.h_mm,
                    "side": side_map.get(str(p.face), "bottom"),
                }
            )
    mounts = [{"x_mm": m.x_mm, "y_mm": m.y_mm, "diameter_mm": m.d_mm} for m in e.mounts]

    return {
        "version": "v1",
        "device": e.device,
        "pcb": pcb,
        "enclosure": enclosure,
        "ports": ports,
        "mounts": mounts,
    }


def _render_mech_check(bundle: Dict[str, Any]) -> str:
    lines = []
    lines.append("# Mechanical Sanity Check\n")
    lines.append("This is a conservative checklist with high-fidelity simulation entries where available.\n")
    for d in bundle.get("dfm") or []:
        lines.append(f"- [{d.get('severity')}] {d.get('message')}")
    if not (bundle.get("dfm") or []):
        lines.append("- ✅ No DFM warnings emitted by heuristic checks.")

    structural = bundle.get("structural_screening") or {}
    if structural.get("status") not in {"not_applicable", "disabled_by_request"}:
        lines.extend([
            "",
            "## Structural FEM / Contact Evidence",
            f"- Status: {structural.get('status')}",
            "- No numerical structural screen authorizes load-bearing fabrication.",
        ])
        for blocker in structural.get("blockers") or []:
            lines.append(f"- [block] {blocker}")
        artifacts = structural.get("artifacts") or {}
        if artifacts.get("review_html"):
            lines.append(f"- Open investigation review: {artifacts['review_html']}")
    construction = bundle.get("construction_alternatives") or {}
    if construction:
        lines.extend(["", "## Construction and Material Alternatives",
                      f"- Status: {construction.get('status')}",
                      "- Thermal/chemical compatibility and joint strength are not certified."])
        for method in construction.get("alternatives") or []:
            lines.append(f"- {method['method']}: {method['status']}")
    sim = bundle.get("simulation") or []
    if sim:
        lines.append("")
        lines.append("## Simulation Hints")
        for s in sim:
            lines.append(f"- [{s.get('severity')}] ({s.get('model')}) {s.get('message')}")

    safety = bundle.get("safety") or []
    if safety:
        lines.append("")
        lines.append("## Safety Checks")
        for s in safety:
            lines.append(f"- [{s.get('severity')}] {s.get('message')}")

    lines.append("")
    return "\n".join(lines)


def _render_build_recipe(bundle: Dict[str, Any]) -> str:
    lines = []
    lines.append("# Build Recipe\n")
    lines.append("## Outputs")
    outputs = list(bundle.get("outputs") or [])
    for o in outputs:
        lines.append(f"- `{o}`")
    if bundle.get("splicer3d"):
        lines.append("- `splicer3d.json` (3d-splicer response)")

    lines.append("")
    lines.append("## Procurement")
    if bundle.get("procurement"):
        lines.append("- `BUY_LIST.csv` (unlocked)")
        lines.append("- `BUY_LIST.locked.csv` (after `SKU_OVERRIDES.json`)")
        lines.append("- `PROCUREMENT_LOCK_REPORT.md`")
        lines.append(f"- Est. COGS (USD): {bundle.get('procurement', {}).get('cogs_usd')}")
    else:
        lines.append("- (not generated) Run with `--include-pricing` to emit buy lists.")

    lines.append("")
    lines.append("## Evidence Bundle")
    lines.append("- `DESIGN_DECISIONS.md`")
    if bundle.get("construction_alternatives"):
        lines.extend(["- `CONSTRUCTION_ALTERNATIVES.json`", "- `CONSTRUCTION_PLAN.md`",
                      "- Construction suggestions do not replace existing enclosure CAD."])
        schedule = (bundle.get("construction_alternatives") or {}).get("hybrid_sheet_geometry") or {}
        if schedule.get("status")=="dimensioned_blank_cut_proposal":
            lines.extend([
                "- `HYBRID_PANEL_CUTS.csv` (blank sizes, not validated cut paths)",
                "- `HYBRID_PANEL_BLANKS.svg` (dimensioned reference drawing, NOT CAM)",
                "- `HYBRID_PARTS.json` (separate hybrid-only parts schedule)",
                "- `HYBRID_INTERFACE_REVIEW.json` (untransformed ports/mounts and missing connectors)",
            ])
    structural = bundle.get("structural_screening") or {}
    if structural.get("status") not in {"not_applicable", "disabled_by_request"}:
        lines.append("- Structural contact analysis: " + str(structural.get("status")))
        artifacts = structural.get("artifacts") or {}
        if artifacts.get("review_html"):
            lines.append("- Structural review: " + str(artifacts["review_html"]))
        else:
            lines.append("- Obtain a bounded structural analysis before any load-bearing claims.")
    lines.append("- `SIM_RESULTS.json`")
    lines.append("- `RISK_REGISTER.md`")
    lines.append("- `REVISION_NOTES.md`")

    lines.append("")
    lines.append("## Assembly (prototype-grade)")
    if bundle.get("construction_alternatives"):
        lines.append("- Review `CONSTRUCTION_PLAN.md` before deciding whether to print entire walls.")
        lines.append("- Sheet panels and external connector files are NOT generated or verified by this comparison.")
    lines.append("- Print base + lid; test-fit PCB/module with clearance.")
    lines.append("- Install heat-set inserts (optional) and fasteners.")
    lines.append("- Verify connector cutouts and cable strain relief.")

    has_gt2_axis = any(n in outputs for n in ("motor_mount.scad", "idler_mount.scad", "carriage.scad"))
    has_leadscrew_axis = any(str(n).startswith("ls_") for n in outputs)

    if has_gt2_axis:
        lines.append("")
        lines.append("## Linear axis (prototype-grade)")
        lines.append("- Print `motor_mount.scad`, `idler_mount.scad`, `carriage.scad` (and optional tensioner/endstop parts).")
        lines.append("- Install rods, bearings/bushings, belt, pulley, idler; tension belt.")
        lines.append("- Check carriage moves smoothly across full travel.")
        lines.append("- Tune accel/speed to avoid skipped steps (start conservative).")

    if has_leadscrew_axis:
        lines.append("")
        lines.append("## Lead-screw axis (prototype-grade)")
        lines.append("- Print `ls_motor_mount.scad`, `ls_screw_end_support.scad`, `ls_carriage_nut_mount.scad` (+ `rod_holder.scad`, `endstop_mount.scad`).")
        lines.append("- Install rods + bearings/bushings; ensure the rod axis is straight and parallel.")
        lines.append("- Install the lead screw + nut; align to minimize binding.")
        lines.append("- Add end support bearings (e.g. 608) if possible; it reduces wobble and wear.")
        lines.append("- Tune steps/mm: `steps_per_mm = steps_per_rev * microsteps / lead_mm_per_rev`.")

    lines.append("")
    return "\n".join(lines)


def _render_print_plan(bundle: Dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Print Plan\n")
    lines.append("This is a heuristic print plan. Validate critical fits and iterate.\n")
    for p in bundle.get("parts") or []:
        if p.get("kind") == "assembly":
            continue
        lines.append(f"- `{p.get('file')}`: {p.get('print_orientation')} ({p.get('kind')})")
        if p.get("notes"):
            lines.append(f"  - {p.get('notes')}")
    lines.append("")
    return "\n".join(lines)


def _write_evidence_bundle(out_dir: Path, bundle: Dict[str, Any], project: ProjectSpec) -> list[str]:
    files: list[str] = []

    decisions_path = out_dir / "DESIGN_DECISIONS.md"
    decisions_path.write_text(_render_design_decisions(bundle, project), encoding="utf-8")
    files.append(decisions_path.name)

    sim_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "simulation": bundle.get("simulation") or [],
        "severity_counts": _severity_counts(bundle.get("simulation") or []),
        "structural_screening": bundle.get("structural_screening") or {},
        "structural_release_blocked": bundle.get("structural_release_blocked", True),
        "construction_alternatives": bundle.get("construction_alternatives"),
    }
    sim_path = out_dir / "SIM_RESULTS.json"
    sim_path.write_text(json.dumps(sim_summary, indent=2), encoding="utf-8")
    files.append(sim_path.name)

    risk_path = out_dir / "RISK_REGISTER.md"
    risk_path.write_text(_render_risk_register(bundle), encoding="utf-8")
    files.append(risk_path.name)

    rev_path = out_dir / "REVISION_NOTES.md"
    rev_path.write_text(_render_revision_notes(bundle), encoding="utf-8")
    files.append(rev_path.name)

    return files


def _render_design_decisions(bundle: Dict[str, Any], project: ProjectSpec) -> str:
    lines: list[str] = []
    lines.append("# Design Decisions\n")
    lines.append(f"- Project: `{project.project_name}`")
    lines.append(f"- Mode: `{project.mode}`")
    lines.append(f"- Process: `{project.process}`")
    lines.append(f"- Simulation Fidelity: `{project.simulation_fidelity}`")
    if bundle.get("construction_alternatives"):
        lines.append("- Construction alternatives: evidence-only, no automatic redesign or approval.")

    composition = bundle.get("composition") or {}
    lines.append("")
    lines.append("## Composition")
    if composition.get("applied"):
        lines.append(f"- Goal: `{composition.get('goal')}`")
        for d in composition.get("decisions") or []:
            lines.append(f"- Decision: {d}")
    else:
        lines.append(f"- Composer: {composition.get('reason', 'not applied')}")

    lines.append("")
    lines.append("## Generated Modules")
    for out_name in bundle.get("outputs") or []:
        lines.append(f"- `{out_name}`")

    lines.append("")
    lines.append("## Control Profile")
    cp = bundle.get("control_profile") or {}
    for loop in cp.get("loops") or []:
        lines.append(f"- `{loop.get('name')}` ({loop.get('type')})")
    if not (cp.get("loops") or []):
        lines.append("- No active motion control loops emitted.")

    lines.append("")
    lines.append("## Assumptions")
    lines.append("- Physics outputs are engineering estimates, not certification results.")
    lines.append("- Validate final dimensions/tolerances against real hardware before production.")
    lines.append("")
    return "\n".join(lines)


def _render_risk_register(bundle: Dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Risk Register\n")
    lines.append("| Source | Severity | Risk | Suggested Mitigation |")
    lines.append("|---|---|---|---|")

    def emit(rows: list[Dict[str, Any]], source: str) -> None:
        for r in rows:
            sev = str(r.get("severity", "info")).lower()
            if sev not in {"warn", "block", "error", "critical"}:
                continue
            msg = str(r.get("message", "")).replace("|", "/")
            mitigation = _suggest_mitigation(source=source, message=msg)
            lines.append(f"| {source} | {sev} | {msg} | {mitigation} |")

    emit(bundle.get("dfm") or [], "dfm")
    emit(bundle.get("simulation") or [], "simulation")
    emit(bundle.get("safety") or [], "safety")
    construction = bundle.get("construction_alternatives") or {}
    sheet = next((x for x in construction.get("alternatives") or []
                  if x.get("method") == "sheet_hybrid"), {})
    for blocker in sheet.get("blockers") or []:
        message = str(blocker).replace("|", "/").replace("\n", " ")[:160]
        lines.append(f"| construction | block | {message} | "
                     "Obtain sourced material/fit evidence before changing fabrication. |")
    structural = bundle.get("structural_screening") or {}
    for blocker in structural.get("blockers") or []:
        # Candidate/advisory/solver blockers are not material strength evidence.
        msg = str(blocker).replace("|","/").replace("\n"," ")[:240]
        lines.append(
            f"| structural_fem | block | {msg} | "
            "Collect reliable structural and physical evidence before release. |"
        )

    if len(lines) == 3:
        lines.append("| n/a | info | No warn/block risks emitted. | Continue with prototype validation checklist. |")

    lines.append("")
    return "\n".join(lines)


def _render_revision_notes(bundle: Dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Revision Notes\n")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")

    lines.append("## Current Snapshot")
    lines.append(f"- Outputs: {len(bundle.get('outputs') or [])}")
    lines.append(f"- DFM issues: {len(bundle.get('dfm') or [])}")
    lines.append(f"- Simulation findings: {len(bundle.get('simulation') or [])}")

    lines.append("")
    lines.append("## Next Revision Checklist")
    lines.append("- Validate printed part fit and revise clearances.")
    lines.append("- Resolve all `block` simulation/DFM findings before client handoff.")
    lines.append("- Update BOM lock with final supplier SKUs and lead times.")
    lines.append("")
    return "\n".join(lines)


def _suggest_mitigation(*, source: str, message: str) -> str:
    m = message.lower()
    if "torque" in m:
        return "Reduce acceleration/load, increase reduction ratio, or choose higher-torque actuator."
    if "deflection" in m or "stiff" in m:
        return "Increase section thickness/support spacing; switch to stiffer material/frame."
    if "critical-speed" in m or "rpm" in m:
        return "Reduce speed, shorten unsupported screw length, or add end supports."
    if "outdoor" in m or "ingress" in m:
        return "Add sealing strategy, glanded connectors, and corrosion-resistant hardware."
    if source == "dfm":
        return "Adjust geometry/clearances per DFM note and re-run bundle."
    return "Address issue and re-run simulation + prototype verification."


def _severity_counts(items: list[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {"info": 0, "warn": 0, "block": 0}
    for it in items:
        sev = str(it.get("severity", "info")).lower()
        if sev not in counts:
            counts[sev] = 0
        counts[sev] += 1
    return counts


def _manifest(out_dir: Path) -> Dict[str, Any]:
    files = []
    for p in sorted(out_dir.glob("*")):
        if p.is_file():
            files.append({"name": p.name, "bytes": p.stat().st_size})
    return {"files": files}
