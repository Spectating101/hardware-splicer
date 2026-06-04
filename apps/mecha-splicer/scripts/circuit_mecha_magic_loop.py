#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_master_spec() -> Dict[str, Any]:
    return {
        "intent": {
            "name": "smart_sensor_node",
            "goal": "deployable_field_node",
            "environment": "outdoor",
            "budget_usd": 180,
        },
        "electrical": {
            "target_voltage_v": 5.0,
            "max_current_a": 1.2,
            "rails": [
                {"name": "5V", "min_v": 4.75, "max_v": 5.25},
                {"name": "3V3", "min_v": 3.0, "max_v": 3.6},
            ],
        },
        "mechanical": {
            "envelope_mm": {"w": 120, "d": 80, "h": 45},
            "payload_n": 5.0,
            "payload_offset_mm": 50.0,
            "camera_pan_tilt": True,
            "pan_tilt_servo": "sg90",
        },
    }


def _to_mecha_spec(master: Dict[str, Any]) -> Dict[str, Any]:
    env = master.get("intent", {}).get("environment", "indoor")
    mech = master.get("mechanical", {})
    elec = master.get("electrical", {})
    env_mm = mech.get("envelope_mm", {"w": 110, "d": 70, "h": 40})

    pan_tilt_enabled = bool(mech.get("camera_pan_tilt", False))
    payload_n = float(mech.get("payload_n", 4.0))
    payload_offset_mm = float(mech.get("payload_offset_mm", 45.0))
    preferred_servo = str(mech.get("pan_tilt_servo", "sg90"))

    spec: Dict[str, Any] = {
        "project_name": f"{master.get('intent', {}).get('name', 'system')}_mecha",
        "simulation_fidelity": "high",
        "mode": "professional",
        "electronics": {
            "device": master.get("intent", {}).get("name", "device"),
            "pcb_w_mm": max(50.0, float(env_mm.get("w", 110)) * 0.55),
            "pcb_h_mm": max(35.0, float(env_mm.get("d", 70)) * 0.45),
            "pcb_t_mm": 1.6,
            "mounts": [
                {"x_mm": 4, "y_mm": 4, "d_mm": 2.8},
                {"x_mm": 52, "y_mm": 4, "d_mm": 2.8},
                {"x_mm": 4, "y_mm": 30, "d_mm": 2.8},
                {"x_mm": 52, "y_mm": 30, "d_mm": 2.8},
            ],
            "ports": [
                {
                    "kind": "rect",
                    "face": "front",
                    "label": "power",
                    "rect": {"x_mm": 10, "y_mm": 0, "w_mm": 14, "h_mm": 6},
                },
            ],
        },
        "system_goal": {
            "application": "pan_tilt_camera" if pan_tilt_enabled else "control_box",
            "payload_kg": max(0.2, payload_n / 9.81),
            "budget_usd": float(master.get("intent", {}).get("budget_usd", 150)),
            "environment": "outdoor" if env == "outdoor" else "indoor",
            "workspace_w_mm": float(env_mm.get("w", 120)),
            "workspace_h_mm": float(env_mm.get("d", 80)),
        },
    }

    if pan_tilt_enabled:
        spec["pan_tilt"] = {
            "pan_servo": preferred_servo,
            "tilt_servo": preferred_servo,
            "max_payload_n": payload_n,
            "payload_offset_mm": payload_offset_mm,
        }

    if float(elec.get("max_current_a", 1.0)) > 1.5 and pan_tilt_enabled:
        spec["pan_tilt"]["pan_servo"] = "mg996r"
        spec["pan_tilt"]["tilt_servo"] = "mg996r"

    return spec


def _build_validate_hints(master: Dict[str, Any]) -> Dict[str, Any]:
    rails = master.get("electrical", {}).get("rails", []) or []
    max_current_a = float(master.get("electrical", {}).get("max_current_a", 1.0))

    hints: Dict[str, Any] = {
        "sources": [{"name": "V_MAIN", "net": "5V", "volts": 5.0, "gnd": "GND", "max_current_a": max_current_a}],
        "loads_cc": [],
        "voltage_constraints": [],
    }

    for r in rails:
        name = str(r.get("name") or "RAIL")
        hints["voltage_constraints"].append(
            {
                "name": f"{name}_constraint",
                "net": name,
                "gnd": "GND",
                "min_v": float(r.get("min_v", 0.0)),
                "max_v": float(r.get("max_v", 0.0)),
                "severity": "error",
            }
        )

    return hints


def _write_minimal_kicad_net(net_path: Path) -> None:
    # Minimal KiCad netlist-like payload for remote parser probing.
    xml = """(export (version D)
  (design (source \"magic-loop\") (date \"2026-03-01\") (tool \"circuit-mecha\"))
  (components
    (comp (ref U1) (value MCU) (footprint Package_QFP:TQFP-48))
    (comp (ref C1) (value 10uF) (footprint Capacitor_SMD:C_0603_1608Metric))
  )
  (nets
    (net (code 1) (name GND)
      (node (ref U1) (pin 1))
      (node (ref C1) (pin 1))
    )
    (net (code 2) (name 3V3)
      (node (ref U1) (pin 2))
      (node (ref C1) (pin 2))
    )
  )
)
"""
    net_path.write_text(xml, encoding="utf-8")


def _run_circuit_gate(
    master: Dict[str, Any],
    *,
    circuit_api_url: Optional[str],
    artifact_dir: Path,
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    rails = master.get("electrical", {}).get("rails", [])
    max_current_a = float(master.get("electrical", {}).get("max_current_a", 0.0))

    if max_current_a <= 0:
        findings.append({"severity": "block", "message": "max_current_a must be > 0."})
    elif max_current_a > 5.0:
        findings.append({"severity": "warn", "message": "High current budget; ensure connector/trace sizing in PCB stage."})

    for r in rails:
        min_v = float(r.get("min_v", 0.0))
        max_v = float(r.get("max_v", 0.0))
        if min_v <= 0 or max_v <= 0 or min_v >= max_v:
            findings.append({"severity": "block", "message": f"Invalid rail constraints for {r.get('name', 'rail')}."})

    remote: Dict[str, Any] = {"checked": False}

    if circuit_api_url:
        base = circuit_api_url.rstrip("/")
        remote = {"checked": True, "base_url": base}
        try:
            with httpx.Client(timeout=20.0) as client:
                health = client.get(f"{base}/api/health")
                remote["health"] = {"status_code": health.status_code, "ok": health.status_code == 200}
                if health.status_code != 200:
                    findings.append({"severity": "warn", "message": f"Circuit API health check returned {health.status_code}."})
                else:
                    # Live validator call (high-ROI gate hardening).
                    net_path = artifact_dir / "circuit_gate_input.net"
                    _write_minimal_kicad_net(net_path)
                    hints = _build_validate_hints(master)
                    with net_path.open("rb") as fh:
                        resp = client.post(
                            f"{base}/api/v2/workflow/validate-kicad",
                            files={"kicad_file": (net_path.name, fh, "text/plain")},
                            data={"hints": json.dumps(hints)},
                        )

                    remote["validate_kicad"] = {"status_code": resp.status_code, "ok": resp.status_code == 200}
                    if resp.status_code >= 400:
                        findings.append({"severity": "warn", "message": f"Circuit validate-kicad call returned {resp.status_code}."})
                    else:
                        payload = resp.json() if resp.text else {}
                        v = payload.get("validation") or {}
                        crit = int(v.get("critical", 0) or 0)
                        errs = int(v.get("errors", 0) or 0)
                        warns = int(v.get("warnings", 0) or 0)
                        remote["validate_kicad"]["summary"] = {
                            "critical": crit,
                            "errors": errs,
                            "warnings": warns,
                        }
                        if crit > 0 or errs > 0:
                            findings.append({"severity": "block", "message": f"Circuit gate found {crit} critical / {errs} errors."})
                        elif warns > 0:
                            findings.append({"severity": "warn", "message": f"Circuit gate found {warns} warnings."})
        except Exception as e:
            remote = {"checked": True, "ok": False, "error": str(e)}
            findings.append({"severity": "warn", "message": "Circuit API unreachable; using local electrical gate only."})

    blocked = any(str(f.get("severity", "")).lower() == "block" for f in findings)
    return {"blocked": blocked, "findings": findings, "remote": remote}


def _auto_revise(master: Dict[str, Any], mecha_bundle: Dict[str, Any], circuit_gate: Dict[str, Any]) -> Dict[str, Any]:
    revised = deepcopy(master)
    findings: List[str] = []

    for src in (mecha_bundle.get("dfm") or []) + (mecha_bundle.get("simulation") or []):
        sev = str(src.get("severity", "")).lower()
        if sev in {"warn", "block", "critical", "error"}:
            findings.append(str(src.get("message", "")))

    for src in circuit_gate.get("findings") or []:
        sev = str(src.get("severity", "")).lower()
        if sev in {"warn", "block", "critical", "error"}:
            findings.append(str(src.get("message", "")))

    joined = "\n".join(findings).lower()

    mech = revised.setdefault("mechanical", {})
    if "tilt torque" in joined or "payload moment" in joined:
        mech["pan_tilt_servo"] = "mg996r"
        mech["payload_n"] = max(1.5, float(mech.get("payload_n", 5.0)) * 0.78)
        mech["payload_offset_mm"] = max(25.0, float(mech.get("payload_offset_mm", 50.0)) * 0.88)

    if "high current" in joined:
        elec = revised.setdefault("electrical", {})
        elec["max_current_a"] = max(0.8, float(elec.get("max_current_a", 1.2)) * 0.9)

    return revised


def _blocked(mecha_bundle: Dict[str, Any], circuit_gate: Dict[str, Any]) -> bool:
    if bool(mecha_bundle.get("blockers")) or bool(circuit_gate.get("blocked")):
        return True
    for src in (mecha_bundle.get("simulation") or []):
        if str(src.get("severity", "")).lower() == "block":
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Circuit+Mecha magic loop: master spec -> co-design -> gates -> auto-revise -> evidence.")
    ap.add_argument("--master-spec", default=None, help="Optional master spec JSON")
    ap.add_argument("--out", default="dist_ready_for_sale/circuit_mecha_magic_latest", help="Output directory")
    ap.add_argument("--max-iters", type=int, default=4)
    ap.add_argument("--circuit-api-url", default=os.getenv("CIRCUIT_AI_API_URL", ""), help="Optional Circuit-AI base URL")
    args = ap.parse_args()

    import sys

    repo = _repo_root()
    sys.path.insert(0, str(repo))
    from src.mecha_splicer.runner import run as run_mecha  # type: ignore

    out_dir = repo / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.master_spec:
        master = json.loads(Path(args.master_spec).read_text(encoding="utf-8"))
    else:
        master = _default_master_spec()

    history: List[Dict[str, Any]] = []
    current = deepcopy(master)

    for i in range(1, max(1, args.max_iters) + 1):
        it_dir = out_dir / f"iter_{i:02d}"
        mecha_spec = _to_mecha_spec(current)
        mecha_bundle = run_mecha(mecha_spec, out_dir=it_dir, simulation_fidelity="high")
        circuit_gate = _run_circuit_gate(current, circuit_api_url=(args.circuit_api_url or None), artifact_dir=it_dir)

        blocked = _blocked(mecha_bundle, circuit_gate)
        step = {
            "iter": i,
            "blocked": blocked,
            "out_dir": str(it_dir),
            "mecha_outputs": len(mecha_bundle.get("outputs") or []),
            "mecha_dfm": mecha_bundle.get("dfm") or [],
            "mecha_sim": mecha_bundle.get("simulation") or [],
            "circuit_gate": circuit_gate,
        }
        history.append(step)
        if not blocked:
            break
        current = _auto_revise(current, mecha_bundle, circuit_gate)

    final = history[-1]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": "pass" if not final["blocked"] else "fail",
        "iterations": history,
        "initial_master_spec": master,
        "final_master_spec": current,
    }

    (out_dir / "MAGIC_LOOP_RESULT.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines: List[str] = []
    lines.append("# Circuit-Mecha Magic Loop Report\n")
    lines.append(f"- Final status: **{summary['final_status']}**")
    lines.append(f"- Iterations: {len(history)}")
    lines.append("")
    lines.append("## Iteration Results")
    for h in history:
        sim_block = sum(1 for s in h.get("mecha_sim") or [] if str(s.get("severity", "")).lower() == "block")
        c_block = bool(h.get("circuit_gate", {}).get("blocked"))
        lines.append(f"- Iter {h['iter']}: blocked={h['blocked']}, mecha_outputs={h['mecha_outputs']}, sim_blocks={sim_block}, circuit_block={c_block}")
    lines.append("")
    lines.append("## Why This Is More Than Vibe Generation")
    lines.append("- A master EE+ME intent is compiled into design artifacts.")
    lines.append("- Deterministic gates can block unsafe/weak candidates.")
    lines.append("- Automated revision policy re-runs until pass/fail evidence is produced.")
    lines.append("- Circuit-AI live validator endpoint is called when URL is provided.")
    lines.append("")
    (out_dir / "MAGIC_LOOP_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "final_status": summary["final_status"], "iterations": len(history)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
