"""Salvage/electronics → mecha-splicer ProjectSpec + offline mechanism pack."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

SCHEMA_VERSION = "hardware_splicer.mechanism_pack.v1"

_ROOT = Path(__file__).resolve().parents[2]
_MECHA_SRC = _ROOT / "apps" / "mecha-splicer" / "src"


def select_mechanism_kind(
    *,
    build_id: str = "",
    goal: str = "",
    resolved_modules: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Deterministic role/build → mechanism kind (no LLM)."""
    roles = [str(r.get("role") or "").lower() for r in (resolved_modules or [])]
    module_ids = [str(r.get("module_id") or "").lower() for r in (resolved_modules or [])]
    svo_n = sum(1 for r in roles if r == "svo") + sum(1 for m in module_ids if "sg90" in m or "mg996" in m)
    text = f"{build_id} {goal}".lower()
    mot_n = sum(1 for r in roles if r == "mot")

    if (
        "pan_tilt" in text
        or "inspection_motion" in text
        or svo_n >= 2
        or ("sg90" in " ".join(module_ids) and svo_n >= 1 and "tilt" in text)
    ):
        return "pan_tilt"
    if "plotter" in text or "stepper" in text or any("a4988" in m or "28byj" in m for m in module_ids):
        return "linear_axis"
    if "robot_drive" in text or "enabot" in text or mot_n >= 2:
        return "mobile_drive"
    if any(x in text for x in ("fume", "relay", "sensor_logger", "plant", "watering", "logger")):
        return "enclosure"
    if any(r in roles for r in ("rly", "load", "sns", "drv")):
        return "enclosure"
    return "enclosure"


def build_mecha_project_spec(
    *,
    project_name: str,
    build_id: str = "",
    goal: str = "",
    resolved_modules: Sequence[Mapping[str, Any]] | None = None,
    pcb_w_mm: float = 70.0,
    pcb_h_mm: float = 50.0,
    mechanism_kind: str | None = None,
) -> Dict[str, Any]:
    kind = mechanism_kind or select_mechanism_kind(
        build_id=build_id, goal=goal, resolved_modules=resolved_modules
    )
    name = (project_name or build_id or "salvage_mech").strip() or "salvage_mech"
    electronics = {
        "device": build_id or name,
        "pcb_w_mm": float(pcb_w_mm),
        "pcb_h_mm": float(pcb_h_mm),
        "pcb_t_mm": 1.6,
        "mounts": [
            {"x_mm": 4.0, "y_mm": 4.0, "d_mm": 3.2},
            {"x_mm": float(pcb_w_mm) - 4.0, "y_mm": 4.0, "d_mm": 3.2},
            {"x_mm": 4.0, "y_mm": float(pcb_h_mm) - 4.0, "d_mm": 3.2},
            {"x_mm": float(pcb_w_mm) - 4.0, "y_mm": float(pcb_h_mm) - 4.0, "d_mm": 3.2},
        ],
        "ports": [
            {
                "kind": "rect",
                "face": "front",
                "label": "usb",
                "rect": {"x_mm": 10.0, "y_mm": 4.0, "w_mm": 12.0, "h_mm": 8.0},
            }
        ],
    }
    spec: Dict[str, Any] = {
        "project_name": name,
        "mode": "prototype",
        "process": "fdm",
        "simulation_fidelity": "starter",
        "auto_compose": False,
        "electronics": electronics,
        "notes": f"Generated from salvage build_id={build_id}; kind={kind}",
    }

    if kind == "pan_tilt":
        spec["pan_tilt"] = {
            "name": f"{name}_pan_tilt",
            "pan_servo": "sg90",
            "tilt_servo": "sg90",
        }
        spec["enclosure"] = {
            "name": f"{name}_controller_box",
            "inner_w_mm": max(80.0, pcb_w_mm + 10.0),
            "inner_d_mm": max(50.0, pcb_h_mm + 10.0),
            "inner_h_mm": 30.0,
        }
        spec["system_goal"] = {
            "application": "pan_tilt_camera",
            "payload_kg": 0.15,
            "budget_usd": 80.0,
        }
    elif kind == "linear_axis":
        spec["linear_axis"] = {
            "name": f"{name}_axis",
            "travel_mm": 200.0,
            "rod_length_mm": 300.0,
        }
        spec["enclosure"] = {
            "name": f"{name}_controller_box",
            "inner_w_mm": max(90.0, pcb_w_mm + 12.0),
            "inner_d_mm": max(60.0, pcb_h_mm + 12.0),
            "inner_h_mm": 35.0,
        }
    elif kind == "mobile_drive":
        spec["auto_compose"] = True
        spec["system_goal"] = {
            "application": "mobile_robot",
            "payload_kg": 0.8,
            "target_speed_m_s": 0.25,
            "budget_usd": 120.0,
            "workspace_w_mm": 200.0,
            "workspace_h_mm": 120.0,
        }
        spec["enclosure"] = {
            "name": f"{name}_drive_bay",
            "inner_w_mm": max(100.0, pcb_w_mm + 15.0),
            "inner_d_mm": max(70.0, pcb_h_mm + 15.0),
            "inner_h_mm": 40.0,
        }
    else:
        # enclosure-only (relay, logger, plant, fume, …)
        spec["enclosure"] = {
            "name": f"{name}_enclosure",
            "inner_w_mm": max(70.0, pcb_w_mm + 10.0),
            "inner_d_mm": max(50.0, pcb_h_mm + 10.0),
            "inner_h_mm": 35.0 if "relay" in f"{build_id} {goal}".lower() else 30.0,
        }
        spec["system_goal"] = {
            "application": "control_box",
            "budget_usd": 60.0,
        }

    return {"kind": kind, "project_spec": spec}


def _ensure_mecha_on_path() -> bool:
    if not _MECHA_SRC.is_dir():
        return False
    path = str(_MECHA_SRC)
    if path not in sys.path:
        sys.path.insert(0, path)
    return True


def run_mechanism_pack(
    *,
    project_name: str,
    build_id: str = "",
    goal: str = "",
    resolved_modules: Sequence[Mapping[str, Any]] | None = None,
    out_dir: str | Path | None = None,
    pcb_w_mm: float = 70.0,
    pcb_h_mm: float = 50.0,
) -> Dict[str, Any]:
    """Build + run mecha-splicer offline. Never raises — returns degraded pack on failure."""
    selected = build_mecha_project_spec(
        project_name=project_name,
        build_id=build_id,
        goal=goal,
        resolved_modules=resolved_modules,
        pcb_w_mm=pcb_w_mm,
        pcb_h_mm=pcb_h_mm,
    )
    kind = str(selected["kind"])
    project_spec = dict(selected["project_spec"])
    pack: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending",
        "kind": kind,
        "project_spec": project_spec,
        "outputs": [],
        "parts": [],
        "bundle_dir": None,
        "claim_boundary": "Starter printable pack from electronics roles — verify fit on bench.",
        "degraded_reason": None,
    }

    if not _ensure_mecha_on_path():
        pack["status"] = "degraded"
        pack["degraded_reason"] = f"mecha-splicer src missing at {_MECHA_SRC}"
        try:
            from .integrations.oss_export_bundle import attach_oss_mech_refs

            return attach_oss_mech_refs(pack)
        except Exception:
            return pack

    try:
        from mecha_splicer.runner import run as mecha_run  # type: ignore
    except Exception as exc:  # pragma: no cover - import env
        pack["status"] = "degraded"
        pack["degraded_reason"] = f"mecha-splicer import failed: {exc}"
        try:
            from .integrations.oss_export_bundle import attach_oss_mech_refs

            return attach_oss_mech_refs(pack)
        except Exception:
            return pack

    target: Optional[Path] = None
    if out_dir is not None:
        target = Path(out_dir) / "mecha_bundle"
        target.mkdir(parents=True, exist_ok=True)

    try:
        bundle = mecha_run(
            project_spec,
            out_dir=str(target) if target else None,
            use_3d_splicer=False,
            render_stl=False,
            render_openscad_stl=False,
            simulation_fidelity="starter",
        )
    except Exception as exc:
        pack["status"] = "degraded"
        pack["degraded_reason"] = f"mecha-splicer run failed: {exc}"
        try:
            from .integrations.oss_export_bundle import attach_oss_mech_refs

            return attach_oss_mech_refs(pack)
        except Exception:
            return pack

    outputs = list(bundle.get("outputs") or [])
    parts = list(bundle.get("parts") or [])
    pack.update(
        {
            "status": "ok",
            "outputs": outputs,
            "parts": parts,
            "bundle_dir": str(target) if target else None,
            "simulation": bundle.get("simulation") or [],
            "dfm": bundle.get("dfm") or [],
        }
    )
    try:
        from .integrations.oss_export_bundle import attach_oss_mech_refs

        pack = attach_oss_mech_refs(pack)
    except Exception:
        pass
    return pack


def write_mechanism_pack_artifacts(pack: Mapping[str, Any], out_dir: str | Path) -> Path:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "MECHANISM_PACK.json"
    path.write_text(json.dumps(dict(pack), indent=2), encoding="utf-8")
    mecha_dir = pack.get("bundle_dir")
    summary = {
        "schema_version": "hardware_splicer.mechatronics_pack.v1",
        "mechanism_status": pack.get("status"),
        "mechanism_kind": pack.get("kind"),
        "bundle_dir": mecha_dir,
        "outputs": pack.get("outputs") or [],
        "degraded_reason": pack.get("degraded_reason"),
        "claim_boundary": pack.get("claim_boundary"),
    }
    (root / "MECHATRONICS_PACK.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return path


def attach_mechatronics_authority(
    *,
    salvage_package: Mapping[str, Any],
    mechanism_pack: Mapping[str, Any],
    out_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Build authority ledger from salvage + mechanism evidence (honest, not production theater)."""
    from .mechatronics_authority import build_mechatronics_authority

    engineering = {
        "analysis": {
            "mechanism": {
                "bundle_file": mechanism_pack.get("bundle_dir"),
                "outputs": mechanism_pack.get("outputs") or [],
                "dfm": mechanism_pack.get("dfm") or [],
                "simulation": mechanism_pack.get("simulation") or [],
                "kind": mechanism_pack.get("kind"),
                "status": mechanism_pack.get("status"),
            }
        }
    }
    build_id = str(salvage_package.get("recommended_build_id") or "")
    fw = salvage_package.get("firmware_scaffold") or {}
    body = {
        "goal": build_id,
        "mechanism": {"kind": mechanism_pack.get("kind")},
        "firmware_scaffold": fw,
        "resolved_modules": salvage_package.get("resolved_modules"),
        # Minimal machine context so the ledger can see an electrical side exists
        "machine": {
            "boards": [
                {
                    "board_id": build_id or "carrier",
                    "requirements": {"roles": ["mcu"]},
                }
            ]
        },
    }
    authority = build_mechatronics_authority(body, engineering=engineering)
    mech_ok = str(mechanism_pack.get("status") or "") == "ok"
    fw_ok = bool(str((fw or {}).get("source") or "").strip())
    # Honest starter pack — never claim production_authorized from offline salvage alone
    authority["offline_pack"] = {
        "ready": mech_ok and fw_ok,
        "mechanism_kind": mechanism_pack.get("kind"),
        "mechanism_status": mechanism_pack.get("status"),
        "firmware_filename": (fw or {}).get("filename"),
        "claim_boundary": (
            "Starter elec+mech+fw pack from salvage — not production mechatronics release."
        ),
    }
    if authority.get("production_authorized") and not (
        authority.get("current_authority_level") == "production_mechatronics_release"
    ):
        authority["production_authorized"] = False
    if out_dir is not None:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / "MECHATRONICS_AUTHORITY.json").write_text(
            json.dumps(authority, indent=2), encoding="utf-8"
        )
    return authority


def mechanism_kinds_present(pack: Mapping[str, Any]) -> List[str]:
    kinds: List[str] = []
    kind = str(pack.get("kind") or "")
    if kind:
        kinds.append(kind)
    # Normalize aliases for verifier
    if kind == "mobile_drive":
        kinds.extend(["drive_base", "enclosure", "linear_axis", "belt_reduction"])
    if kind == "enclosure":
        kinds.append("enclosure")
    if kind == "pan_tilt":
        kinds.extend(["pan_tilt", "enclosure"])
    if kind == "linear_axis":
        kinds.extend(["linear_axis", "enclosure"])
    return sorted(set(kinds))
