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

    bundle = _generate_bundle(project.model_dump(), out_dir=out_dir)
    bundle["parts"] = [p.to_dict() for p in build_parts_meta(project, bundle.get("outputs") or [])]
    bundle["composition"] = composition
    bundle["simulation"] = run_simulation_summary(project, fidelity=project.simulation_fidelity)
    bundle["control_profile"] = synthesize_control_profile(project)
    bundle["safety"] = evaluate_safety_checks(project)

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
    lines.append("- `SIM_RESULTS.json`")
    lines.append("- `RISK_REGISTER.md`")
    lines.append("- `REVISION_NOTES.md`")

    lines.append("")
    lines.append("## Assembly (prototype-grade)")
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
