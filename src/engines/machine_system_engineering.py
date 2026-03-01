"""
System-level engineering for multi-board machines.

This module goes beyond schema checks by adding:
- board placement optimization
- interconnect signal/path sanity simulation
- system power distribution simulation
- optional mechanism simulation bridge via Mecha-Splicer
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .kicad_netlist_compiler import compile_kicad_netlist
from .machine_requirements import compile_machine_requirements
from .netlist import Resistor, is_ground
from .power_tree_validator import validate_pcb_power_tree
from .spice_runner import run_ngspice


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _board_dims(board: Dict[str, Any]) -> Tuple[float, float]:
    dims = board.get("pcb_outline_mm")
    if isinstance(dims, list) and len(dims) >= 2:
        return max(_as_float(dims[0], 40.0), 5.0), max(_as_float(dims[1], 30.0), 5.0)
    return 50.0, 40.0


def _init_positions(boards: List[Dict[str, Any]]) -> Dict[str, Tuple[float, float]]:
    pos: Dict[str, Tuple[float, float]] = {}
    x = 0.0
    for b in boards:
        bid = str(b.get("board_id") or "").strip()
        if not bid:
            continue
        p = b.get("position_mm")
        if isinstance(p, list) and len(p) >= 2:
            pos[bid] = (_as_float(p[0]), _as_float(p[1]))
        else:
            pos[bid] = (x, 0.0)
            x += 80.0
    return pos


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _interface_weight(interface: str) -> float:
    i = (interface or "").strip().lower()
    if i in ("power", "motor_power", "high_current"):
        return 3.0
    if i in ("spi", "can", "usb2"):
        return 2.0
    if i in ("i2c", "uart", "gpio"):
        return 1.5
    return 1.0


def optimize_board_placement(machine: Dict[str, Any]) -> Dict[str, Any]:
    boards = [b for b in (machine.get("boards") or []) if isinstance(b, dict)]
    interconnects = [c for c in (machine.get("interconnects") or []) if isinstance(c, dict)]
    if not boards:
        return {"ok": False, "error": "no_boards"}

    pos0 = _init_positions(boards)
    pos = dict(pos0)
    ids = [str(b.get("board_id") or "") for b in boards if str(b.get("board_id") or "")]
    neighbors: Dict[str, List[Tuple[str, float]]] = {bid: [] for bid in ids}
    dims = {str(b.get("board_id") or ""): _board_dims(b) for b in boards}
    for c in interconnects:
        a = str(c.get("from_board") or "").strip()
        b = str(c.get("to_board") or "").strip()
        if a in neighbors and b in neighbors:
            w = _interface_weight(str(c.get("interface") or ""))
            neighbors[a].append((b, w))
            neighbors[b].append((a, w))

    if not interconnects:
        return {"ok": True, "before_mm": 0.0, "after_mm": 0.0, "positions_mm": {k: [v[0], v[1]] for k, v in pos.items()}}

    for _ in range(80):
        updated = dict(pos)
        for bid in ids:
            nbs = neighbors.get(bid) or []
            if not nbs:
                continue
            total_w = sum(w for _, w in nbs)
            if total_w <= 0:
                continue
            x = sum(pos[other][0] * w for other, w in nbs) / total_w
            y = sum(pos[other][1] * w for other, w in nbs) / total_w
            ox, oy = pos[bid]
            nx = 0.6 * ox + 0.4 * x
            ny = 0.6 * oy + 0.4 * y
            # Keep parts from collapsing: simple pairwise repulsion based on board footprint.
            bw, bh = dims.get(bid, (50.0, 40.0))
            min_sep = math.sqrt(bw * bw + bh * bh) * 0.55 + 12.0
            rx = 0.0
            ry = 0.0
            for other in ids:
                if other == bid:
                    continue
                ow, oh = dims.get(other, (50.0, 40.0))
                min_sep_ij = (min_sep + (math.sqrt(ow * ow + oh * oh) * 0.55 + 12.0)) * 0.5
                dx = nx - pos[other][0]
                dy = ny - pos[other][1]
                d = math.sqrt(dx * dx + dy * dy)
                if d < 1e-6:
                    d = 1e-6
                    dx = 1.0
                    dy = 0.0
                if d < min_sep_ij:
                    k = (min_sep_ij - d) / min_sep_ij
                    rx += (dx / d) * k * 18.0
                    ry += (dy / d) * k * 18.0
            updated[bid] = (nx + rx, ny + ry)
        pos = updated

    def _total_len(pmap: Dict[str, Tuple[float, float]]) -> float:
        s = 0.0
        for c in interconnects:
            a = str(c.get("from_board") or "").strip()
            b = str(c.get("to_board") or "").strip()
            if a in pmap and b in pmap:
                s += _dist(pmap[a], pmap[b])
        return s

    before = _total_len(pos0)
    after = _total_len(pos)
    rec_lengths: List[Dict[str, Any]] = []
    for c in interconnects:
        a = str(c.get("from_board") or "").strip()
        b = str(c.get("to_board") or "").strip()
        if a in pos and b in pos:
            length_mm = _dist(pos[a], pos[b]) * 1.20 + 20.0
            rec_lengths.append(
                {
                    "from_board": a,
                    "to_board": b,
                    "interface": c.get("interface") or "custom",
                    "recommended_length_cm": round(length_mm / 10.0, 1),
                }
            )

    return {
        "ok": True,
        "before_mm": round(before, 2),
        "after_mm": round(after, 2),
        "improvement_mm": round(before - after, 2),
        "positions_mm": {k: [round(v[0], 2), round(v[1], 2)] for k, v in pos.items()},
        "recommended_lengths": rec_lengths,
    }


def simulate_interconnects(machine: Dict[str, Any], placement: Dict[str, Any]) -> Dict[str, Any]:
    interconnects = [c for c in (machine.get("interconnects") or []) if isinstance(c, dict)]
    positions = placement.get("positions_mm") or {}
    limits_cm = {
        "i2c": 30.0,
        "spi": 20.0,
        "uart": 100.0,
        "can": 500.0,
        "usb2": 300.0,
        "power": 200.0,
        "gpio": 80.0,
    }
    issues: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []
    for c in interconnects:
        a = str(c.get("from_board") or "").strip()
        b = str(c.get("to_board") or "").strip()
        iface = str(c.get("interface") or "custom").strip().lower()
        length_cm = _as_float(c.get("length_cm"), 0.0)
        if length_cm <= 0.0 and a in positions and b in positions:
            pa = positions[a]
            pb = positions[b]
            length_cm = (_dist((pa[0], pa[1]), (pb[0], pb[1])) * 1.2 + 20.0) / 10.0
        limit = limits_cm.get(iface, 60.0)
        margin = limit - length_cm
        status = "pass" if margin >= 0 else "fail"
        link = {
            "from_board": a,
            "to_board": b,
            "interface": iface,
            "length_cm": round(length_cm, 2),
            "recommended_max_cm": round(limit, 2),
            "margin_cm": round(margin, 2),
            "status": status,
        }
        links.append(link)
        if status != "pass":
            issues.append(
                {
                    "severity": "error",
                    "topic": "interconnect",
                    "message": f"{a}->{b} {iface} length {length_cm:.1f}cm exceeds {limit:.1f}cm.",
                    "fix": "Shorten cable, lower speed, or move to differential/robust interface (CAN/RS485).",
                }
            )
    return {"links": links, "issues": issues}


def _sum_board_load_current(board: Dict[str, Any]) -> float:
    req = board.get("requirements")
    if not isinstance(req, dict):
        return _as_float(board.get("estimated_current_a"), 0.2)
    power = req.get("power")
    if not isinstance(power, dict):
        return _as_float(board.get("estimated_current_a"), 0.2)
    loads = power.get("loads")
    total = 0.0
    if isinstance(loads, list):
        for l in loads:
            if isinstance(l, dict):
                total += max(_as_float(l.get("current_a"), 0.0), 0.0)
    if total <= 0.0:
        total = _as_float(board.get("estimated_current_a"), 0.2)
    return total


def _wire_ohm_per_m(awg: str | None) -> float:
    table = {"20": 0.033, "22": 0.053, "24": 0.084, "26": 0.133, "28": 0.213}
    if not awg:
        return table["24"]
    k = "".join(ch for ch in str(awg) if ch.isdigit())
    return table.get(k, table["24"])


def simulate_power_distribution(machine: Dict[str, Any], placement: Dict[str, Any]) -> Dict[str, Any]:
    boards = {str(b.get("board_id") or "").strip(): b for b in (machine.get("boards") or []) if isinstance(b, dict)}
    power_tree = [p for p in (machine.get("power_tree") or []) if isinstance(p, dict)]
    interconnects = [c for c in (machine.get("interconnects") or []) if isinstance(c, dict)]
    interconnect_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for c in interconnects:
        a = str(c.get("from_board") or "").strip()
        b = str(c.get("to_board") or "").strip()
        if a and b:
            interconnect_map[(a, b)] = c
            interconnect_map[(b, a)] = c

    board_currents = {bid: _sum_board_load_current(b) for bid, b in boards.items()}
    by_source: Dict[str, float] = {}
    rails: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    for row in power_tree:
        source = str(row.get("source") or "").strip() or "unknown_source"
        bid = str(row.get("board_id") or "").strip()
        v_nom = _as_float(row.get("voltage_v"), 0.0)
        i_need = board_currents.get(bid, 0.0)
        c = interconnect_map.get((source.split(":")[0], bid)) if ":" in source else interconnect_map.get((source, bid))
        length_cm = _as_float((c or {}).get("length_cm"), 20.0)
        awg = str((c or {}).get("wire_awg") or "24")
        r_per_m = _wire_ohm_per_m(awg)
        r_loop = r_per_m * (length_cm / 100.0) * 2.0
        vdrop = i_need * r_loop
        v_at_board = max(v_nom - vdrop, 0.0)
        min_required = v_nom * 0.95 if v_nom > 0 else 0.0
        status = "pass" if v_at_board >= min_required else "fail"
        rails.append(
            {
                "source": source,
                "board_id": bid,
                "rail": str(row.get("rail") or ""),
                "voltage_nominal_v": round(v_nom, 4),
                "board_current_a": round(i_need, 4),
                "wire_awg": awg,
                "length_cm": round(length_cm, 2),
                "voltage_drop_v": round(vdrop, 4),
                "voltage_at_board_v": round(v_at_board, 4),
                "status": status,
            }
        )
        by_source[source] = by_source.get(source, 0.0) + i_need
        max_current = _as_float(row.get("max_current_a"), 0.0)
        if max_current > 0 and by_source[source] > max_current + 1e-9:
            issues.append(
                {
                    "severity": "error",
                    "topic": "power_source",
                    "message": f"{source} overloaded: {by_source[source]:.3f}A > {max_current:.3f}A.",
                    "fix": "Increase source capacity, split rails, or reduce board load.",
                }
            )
        if status == "fail":
            issues.append(
                {
                    "severity": "error",
                    "topic": "voltage_drop",
                    "message": f"{bid} undervoltage on {row.get('rail')}: {v_at_board:.2f}V < {min_required:.2f}V.",
                    "fix": "Shorter/thicker wires, higher source voltage with local regulation, or lower current draw.",
                }
            )

    spice = _simulate_power_spice(rails)
    return {"rails": rails, "source_currents_a": {k: round(v, 4) for k, v in by_source.items()}, "issues": issues, "spice": spice}


def _simulate_power_spice(rails: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rails:
        return {"ok": False, "error": "no_power_paths"}

    lines: List[str] = ["* machine power distribution"]
    source_nodes: Dict[str, str] = {}
    for i, r in enumerate(rails):
        src = str(r.get("source") or f"S{i}")
        if src not in source_nodes:
            source_nodes[src] = f"NSRC{i+1}"
            v = _as_float(r.get("voltage_nominal_v"), 0.0)
            lines.append(f"V_{i+1} {source_nodes[src]} 0 DC {v:.6f}")
    for i, r in enumerate(rails):
        src = str(r.get("source") or "")
        bid = str(r.get("board_id") or f"b{i+1}")
        nload = f"N_{bid}_{i+1}"
        v = max(_as_float(r.get("voltage_nominal_v"), 0.0), 1e-6)
        i_a = max(_as_float(r.get("board_current_a"), 0.0), 1e-6)
        rv = max(_as_float(r.get("voltage_drop_v"), 0.0) / i_a, 1e-5)
        rl = max(v / i_a, 1.0)
        lines.append(f"RPATH_{i+1} {source_nodes.get(src, '0')} {nload} {rv:.6f}")
        lines.append(f"RLOAD_{i+1} {nload} 0 {rl:.6f}")
    lines.extend([".op", ".end"])
    return run_ngspice(netlist_text="\n".join(lines) + "\n", timeout_s=20)


def _extract_primary_anchor(machine: Dict[str, Any]) -> Dict[str, Any] | None:
    boards = [b for b in (machine.get("boards") or []) if isinstance(b, dict)]
    if not boards:
        return None
    b = boards[0]
    dims = b.get("pcb_outline_mm")
    if not isinstance(dims, list) or len(dims) < 2:
        return None
    return {
        "device": b.get("name") or b.get("board_id") or "primary_board",
        "pcb_w_mm": max(_as_float(dims[0]), 5.0),
        "pcb_h_mm": max(_as_float(dims[1]), 5.0),
        "pcb_t_mm": max(_as_float(dims[2], 1.6), 0.4) if len(dims) >= 3 else 1.6,
        "mounts": b.get("mounts") or [],
        "ports": b.get("ports") or [],
    }


def run_mecha_bridge(
    machine: Dict[str, Any],
    mechanism: Dict[str, Any],
    *,
    simulation_fidelity: str = "high",
    use_3d_splicer: bool = True,
    render_stl: bool = False,
) -> Dict[str, Any]:
    mecha_root = Path(__file__).resolve().parents[3] / "Mecha-Splicer"
    cli = mecha_root / "scripts" / "mecha_splicer_spec.py"
    if not cli.exists():
        return {"ok": False, "error": "mecha_splicer_not_found"}

    mech_spec = dict(mechanism) if isinstance(mechanism, dict) else {}
    if not mech_spec.get("project_name"):
        mech_spec["project_name"] = f"{machine.get('machine_name') or 'machine'}_mecha"
    if "mode" not in mech_spec:
        mech_spec["mode"] = str(machine.get("design_intent") or "prototype")
    if "process" not in mech_spec:
        mech_spec["process"] = "fdm"
    if "electronics" not in mech_spec:
        anchor = _extract_primary_anchor(machine)
        if anchor:
            mech_spec["electronics"] = anchor

    tmp = Path(tempfile.gettempdir()) / "circuit-ai" / "machine_mecha"
    tmp.mkdir(parents=True, exist_ok=True)
    spec_path = tmp / f"mecha_spec_{next(tempfile._get_candidate_names())}.json"
    out_dir = tmp / f"out_{next(tempfile._get_candidate_names())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(mech_spec, indent=2), encoding="utf-8")

    cmd = [
        "python3",
        str(cli),
        "--spec",
        str(spec_path),
        "--out",
        str(out_dir),
        "--simulation-fidelity",
        simulation_fidelity if simulation_fidelity in ("starter", "high") else "high",
    ]
    if use_3d_splicer:
        cmd.append("--use-3d-splicer")
        if render_stl:
            cmd.append("--render-stl")
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180, check=False)
    bundle_path = out_dir / "mecha_splicer.bundle.json"
    parsed: Dict[str, Any] = {}
    if bundle_path.exists():
        try:
            parsed = json.loads(bundle_path.read_text(encoding="utf-8"))
        except Exception:
            parsed = {}
    return {
        "ok": p.returncode == 0 and bool(parsed),
        "returncode": p.returncode,
        "command": cmd,
        "out_dir": str(out_dir),
        "bundle_file": str(bundle_path),
        "simulation": parsed.get("simulation") if isinstance(parsed, dict) else [],
        "dfm": parsed.get("dfm") if isinstance(parsed, dict) else [],
        "safety": parsed.get("safety") if isinstance(parsed, dict) else [],
        "splicer3d": parsed.get("splicer3d") if isinstance(parsed, dict) else None,
        "use_3d_splicer": bool(use_3d_splicer),
        "render_stl": bool(render_stl),
        "stderr_tail": (p.stderr or "")[-4000:],
    }


def _actuation_requirements(mechanism: Dict[str, Any]) -> Dict[str, Any]:
    req = {"servo_channels": 0, "stepper_channels": 0, "estimated_actuation_current_a": 0.0}
    if not isinstance(mechanism, dict):
        return req
    if isinstance(mechanism.get("pan_tilt"), dict):
        req["servo_channels"] += 2
        pan = str((mechanism.get("pan_tilt") or {}).get("pan_servo") or "sg90").lower()
        tilt = str((mechanism.get("pan_tilt") or {}).get("tilt_servo") or "sg90").lower()
        req["estimated_actuation_current_a"] += 1.8 if ("mg996r" in (pan, tilt)) else 0.6
    if isinstance(mechanism.get("gripper"), dict):
        req["servo_channels"] += 1
        servo = str((mechanism.get("gripper") or {}).get("servo_type") or "sg90").lower()
        req["estimated_actuation_current_a"] += 1.2 if servo == "mg996r" else 0.3
    if isinstance(mechanism.get("linear_axis"), dict) or isinstance(mechanism.get("leadscrew_axis"), dict):
        req["stepper_channels"] += 1
        req["estimated_actuation_current_a"] += 1.2
    return req


def evaluate_control_coupling(machine: Dict[str, Any], mechanism: Dict[str, Any]) -> Dict[str, Any]:
    boards = {str(b.get("board_id") or "").strip(): b for b in (machine.get("boards") or []) if isinstance(b, dict)}
    ctrl_bid = str((machine.get("actuation") or {}).get("board_id") or "").strip()
    if not ctrl_bid:
        ctrl_bid = next(iter(boards.keys()), "")
    ctrl = boards.get(ctrl_bid) or {}
    caps = ctrl.get("capabilities") if isinstance(ctrl.get("capabilities"), dict) else {}
    pwm = int(_as_float(caps.get("pwm_channels"), 6))
    step = int(_as_float(caps.get("stepper_channels"), 2))
    current_budget = _as_float(caps.get("actuation_current_budget_a"), 1.0)
    req = _actuation_requirements(mechanism)

    issues: List[Dict[str, Any]] = []
    if req["servo_channels"] > pwm:
        issues.append(
            {
                "severity": "error",
                "topic": "control_channels",
                "message": f"Controller {ctrl_bid} needs {req['servo_channels']} servo channels but has {pwm}.",
                "fix": "Add PCA9685 or move actuation to dedicated driver board.",
            }
        )
    if req["stepper_channels"] > step:
        issues.append(
            {
                "severity": "error",
                "topic": "stepper_channels",
                "message": f"Controller {ctrl_bid} needs {req['stepper_channels']} stepper channels but has {step}.",
                "fix": "Use dedicated stepper driver board.",
            }
        )
    if req["estimated_actuation_current_a"] > current_budget:
        issues.append(
            {
                "severity": "warning",
                "topic": "actuation_current",
                "message": f"Estimated actuation current {req['estimated_actuation_current_a']:.2f}A exceeds budget {current_budget:.2f}A.",
                "fix": "Power actuators from separate rail and isolate logic supply.",
            }
        )

    return {"control_board_id": ctrl_bid, "capabilities": {"pwm_channels": pwm, "stepper_channels": step, "actuation_current_budget_a": current_budget}, "requirements": req, "issues": issues}


def _build_improvements(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    improvements: List[Dict[str, Any]] = []
    placement = results.get("placement") or {}
    if placement.get("ok") and _as_float(placement.get("improvement_mm"), 0.0) > 30.0:
        improvements.append(
            {
                "priority": "high",
                "topic": "layout",
                "message": f"Reposition boards to cut harness length by {placement.get('improvement_mm')}mm.",
                "action": "Apply suggested positions_mm and update cable lengths from recommended_lengths.",
            }
        )

    for issue in (results.get("power") or {}).get("issues") or []:
        improvements.append({"priority": "high", "topic": issue.get("topic"), "message": issue.get("message"), "action": issue.get("fix")})
    for issue in (results.get("interconnects") or {}).get("issues") or []:
        improvements.append({"priority": "high", "topic": issue.get("topic"), "message": issue.get("message"), "action": issue.get("fix")})
    for issue in (results.get("control_coupling") or {}).get("issues") or []:
        improvements.append({"priority": "high", "topic": issue.get("topic"), "message": issue.get("message"), "action": issue.get("fix")})

    mecha = results.get("mechanism") or {}
    for issue in (mecha.get("dfm") or []):
        if isinstance(issue, dict) and str(issue.get("severity")) in ("block", "warn"):
            improvements.append(
                {
                    "priority": "high" if issue.get("severity") == "block" else "medium",
                    "topic": "mechanical_dfm",
                    "message": str(issue.get("message") or "mecha dfm finding"),
                    "action": "Adjust mechanism spec dimensions/materials and rerun high-fidelity simulation.",
                }
            )
    return improvements[:80]


def _readiness_verdict(compiled: Dict[str, Any], results: Dict[str, Any]) -> str:
    base = str(((compiled.get("machine") or {}).get("readiness_level") or "draft")).lower()
    hard_fail = False
    for section in ("power", "interconnects", "control_coupling"):
        for i in ((results.get(section) or {}).get("issues") or []):
            if str(i.get("severity") or "").lower() == "error":
                hard_fail = True
                break
        if hard_fail:
            break
    if hard_fail:
        return "needs_revision"
    if base in ("ready", "manufacturable"):
        return "sim_ready"
    if base == "reviewable":
        return "reviewable_with_sim"
    return "draft"


def _render_engineering_report(machine: Dict[str, Any], compiled: Dict[str, Any], results: Dict[str, Any]) -> str:
    m = compiled.get("machine") or {}
    lines: List[str] = []
    lines.append(f"# System Engineering Report — {m.get('machine_name') or machine.get('machine_name') or 'machine'}")
    lines.append("")
    lines.append(f"- Generated: `{_utc_now()}`")
    lines.append(f"- Boards: `{m.get('board_count')}`")
    lines.append(f"- Interconnects: `{m.get('interconnect_count')}`")
    lines.append(f"- Base readiness: `{m.get('readiness_level')}`")
    lines.append(f"- Simulation verdict: `{results.get('verdict')}`")
    lines.append("")
    lines.append("## Placement Optimization")
    p = results.get("placement") or {}
    lines.append(f"- Total cable (before): `{p.get('before_mm')}` mm")
    lines.append(f"- Total cable (after): `{p.get('after_mm')}` mm")
    lines.append(f"- Improvement: `{p.get('improvement_mm')}` mm")
    lines.append("")
    lines.append("## Power Simulation")
    power = results.get("power") or {}
    lines.append(f"- Paths simulated: `{len(power.get('rails') or [])}`")
    lines.append(f"- Issues: `{len(power.get('issues') or [])}`")
    spice = power.get("spice") or {}
    lines.append(f"- ngspice: `{'ok' if spice.get('ok') else spice.get('error') or 'not_run'}`")
    lines.append("")
    lines.append("## Interconnect Simulation")
    inter = results.get("interconnects") or {}
    lines.append(f"- Links checked: `{len(inter.get('links') or [])}`")
    lines.append(f"- Issues: `{len(inter.get('issues') or [])}`")
    lines.append("")
    lines.append("## Control/Mechanism Coupling")
    cc = results.get("control_coupling") or {}
    lines.append(f"- Control board: `{cc.get('control_board_id')}`")
    lines.append(f"- Coupling issues: `{len(cc.get('issues') or [])}`")
    mech = results.get("mechanism") or {}
    lines.append(f"- Mecha bridge: `{mech.get('ok')}`")
    if mech.get("ok"):
        lines.append(f"- Mecha simulation findings: `{len(mech.get('simulation') or [])}`")
    lines.append("")
    lines.append("## Improvements")
    for item in (results.get("improvements") or [])[:40]:
        lines.append(f"- [{item.get('priority')}] {item.get('message')} -> {item.get('action')}")
    if not (results.get("improvements") or []):
        lines.append("- No high-priority improvements emitted.")
    return "\n".join(lines).rstrip() + "\n"


def engineer_machine_system(
    machine: Dict[str, Any],
    *,
    run_mechanism_sim: bool = True,
    mechanism_spec: Dict[str, Any] | None = None,
    simulation_fidelity: str = "high",
) -> Dict[str, Any]:
    compiled = compile_machine_requirements(machine)
    placement = optimize_board_placement(machine)
    inter = simulate_interconnects(machine, placement)
    power = simulate_power_distribution(machine, placement)
    control = evaluate_control_coupling(machine, mechanism_spec or {})
    mechanism = {"ok": False, "skipped": True, "reason": "run_mechanism_sim=false"}
    if run_mechanism_sim and isinstance(mechanism_spec, dict) and mechanism_spec:
        mechanism = run_mecha_bridge(machine, mechanism_spec, simulation_fidelity=simulation_fidelity)

    results = {
        "placement": placement,
        "interconnects": inter,
        "power": power,
        "control_coupling": control,
        "mechanism": mechanism,
    }
    results["improvements"] = _build_improvements(results)
    results["verdict"] = _readiness_verdict(compiled, results)
    report_md = _render_engineering_report(machine, compiled, results)

    return {
        "machine": compiled.get("machine") or {},
        "compiled": compiled,
        "analysis": results,
        "report_md": report_md,
    }


def _board_file_map(machine: Dict[str, Any], board_design_files: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(board_design_files, dict):
        for bid, meta in board_design_files.items():
            if not isinstance(meta, dict):
                continue
            path = str(meta.get("path") or "").strip()
            kind = str(meta.get("kind") or "").strip().lower()
            if not path:
                continue
            if kind not in ("netlist", "pcb"):
                kind = "netlist" if path.lower().endswith(".net") else "pcb"
            out[str(bid)] = {"path": path, "kind": kind}
    for b in machine.get("boards") or []:
        if not isinstance(b, dict):
            continue
        bid = str(b.get("board_id") or "").strip()
        if not bid or bid in out:
            continue
        net_path = str(b.get("netlist_path") or "").strip()
        pcb_path = str(b.get("pcb_path") or "").strip()
        if net_path:
            out[bid] = {"path": net_path, "kind": "netlist"}
        elif pcb_path:
            out[bid] = {"path": pcb_path, "kind": "pcb"}
    return out


def _merge_hints(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in ("sources", "loads_cc", "voltage_constraints", "traces", "series_traces", "ldos", "loads_cp"):
        a = primary.get(k) if isinstance(primary, dict) else None
        b = fallback.get(k) if isinstance(fallback, dict) else None
        arr: List[Any] = []
        if isinstance(a, list):
            arr.extend(a)
        if isinstance(b, list):
            arr.extend([x for x in b if x not in arr])
        if arr:
            out[k] = arr
    max_drop = primary.get("max_trace_drop_v") if isinstance(primary, dict) else None
    if max_drop is None and isinstance(fallback, dict):
        max_drop = fallback.get("max_trace_drop_v")
    if max_drop is not None:
        out["max_trace_drop_v"] = max_drop
    return out


def _auto_board_hints_from_machine(machine: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    boards = [b for b in (machine.get("boards") or []) if isinstance(b, dict)]
    power_tree = [p for p in (machine.get("power_tree") or []) if isinstance(p, dict)]
    out: Dict[str, Dict[str, Any]] = {}
    for b in boards:
        bid = str(b.get("board_id") or "").strip()
        if not bid:
            continue
        row = next((r for r in power_tree if str(r.get("board_id") or "").strip() == bid), None)
        if row is None:
            continue
        rail = str(row.get("rail") or "VIN").strip() or "VIN"
        v = _as_float(row.get("voltage_v"), 5.0)
        i_max = _as_float(row.get("max_current_a"), 1.0)
        i_load = max(_sum_board_load_current(b), 0.05)
        out[bid] = {
            "sources": [{"name": f"AUTO_SRC_{bid}", "net": rail, "gnd": "GND", "volts": v, "max_current_a": i_max}],
            "loads_cc": [{"name": f"AUTO_LOAD_{bid}", "net": rail, "gnd": "GND", "amps": i_load}],
            "voltage_constraints": [{"name": f"AUTO_RAIL_{bid}", "net": rail, "gnd": "GND", "min_v": 0.90 * v, "max_v": 1.10 * v, "severity": "warning"}],
        }
    return out


def _compiled_netlist_to_spice(compiled_netlist: Any) -> str:
    lines: List[str] = ["* board-level spice generated from compiled netlist"]
    # Voltage sources
    for vs in getattr(compiled_netlist, "voltage_sources", []) or []:
        name = str(getattr(vs, "name", "VSRC")).replace(" ", "_")
        n_plus = str(getattr(vs, "n_plus", "0") or "0")
        n_minus = str(getattr(vs, "n_minus", "0") or "0")
        volts = float(getattr(vs, "volts", 0.0))
        lines.append(f"V_{name} {n_plus} {n_minus} DC {volts:.6f}")
    # Resistors
    for r in (getattr(compiled_netlist, "resistors", []) or []):
        name = str(getattr(r, "name", "R")).replace(" ", "_")
        n1 = str(getattr(r, "n1", "0") or "0")
        n2 = str(getattr(r, "n2", "0") or "0")
        ohms = max(float(getattr(r, "ohms", 1.0)), 1e-6)
        lines.append(f"R_{name} {n1} {n2} {ohms:.6f}")
    for t in (getattr(compiled_netlist, "traces", []) or []):
        name = str(getattr(t, "name", "TRACE")).replace(" ", "_")
        n1 = str(getattr(t, "n1", "0") or "0")
        n2 = str(getattr(t, "n2", "0") or "0")
        ohms = max(float(getattr(t, "ohms", 1e-3)), 1e-6)
        lines.append(f"R_TRACE_{name} {n1} {n2} {ohms:.6f}")
    # Loads
    for l in (getattr(compiled_netlist, "loads_cc", []) or []):
        name = str(getattr(l, "name", "LOAD")).replace(" ", "_")
        node = str(getattr(l, "node", "0") or "0")
        gnd = str(getattr(l, "gnd", "0") or "0")
        amps = max(float(getattr(l, "amps", 0.0)), 0.0)
        if amps > 0:
            lines.append(f"I_{name} {node} {gnd} DC {amps:.6f}")
    for i, l in enumerate((getattr(compiled_netlist, "loads_cp", []) or [])):
        node = str(getattr(l, "node", "0") or "0")
        gnd = str(getattr(l, "gnd", "0") or "0")
        watts = float(getattr(l, "watts", 0.0))
        if watts <= 0:
            continue
        # Approximate constant-power as resistor at nominal 5V.
        r_ohm = max((5.0 * 5.0) / watts, 1.0)
        lines.append(f"R_CP_{i+1} {node} {gnd} {r_ohm:.6f}")
    # LDO approximation (ideal source at nominal output)
    for ldo in (getattr(compiled_netlist, "ldos", []) or []):
        name = str(getattr(ldo, "name", "LDO")).replace(" ", "_")
        vout = str(getattr(ldo, "vout", "0") or "0")
        gnd = str(getattr(ldo, "gnd", "0") or "0")
        v_nom = float(getattr(ldo, "vout_nom_v", 0.0))
        lines.append(f"V_LDO_{name} {vout} {gnd} DC {v_nom:.6f}")
    lines.extend([".op", ".end"])
    return "\n".join(lines) + "\n"


def _issue_to_dict(issue: Any) -> Dict[str, Any]:
    if isinstance(issue, dict):
        return issue
    d = getattr(issue, "__dict__", None)
    if isinstance(d, dict):
        return dict(d)
    return {"severity": "error", "issue": "unknown_issue", "explanation": str(issue)}


def _simulate_board_design_file(board_id: str, design_path: str, hints: Dict[str, Any]) -> Dict[str, Any]:
    p = Path(design_path)
    if not p.exists():
        return {"board_id": board_id, "ok": False, "error": "file_not_found", "path": design_path}
    ext = p.suffix.lower()
    if ext not in (".net", ".kicad_pcb"):
        return {"board_id": board_id, "ok": False, "error": "unsupported_design_file", "path": design_path}

    try:
        compiled = compile_kicad_netlist(str(p), hints=hints)
        # Add very high-value shunts to ground to avoid singular floating islands in raw KiCad netlists.
        # This is a numerical stabilization trick (gmin) and has negligible impact on nominal voltages/currents.
        gmin_nodes = [n for n in (compiled.netlist.all_nodes() or []) if not is_ground(n)]
        for i, n in enumerate(gmin_nodes):
            compiled.netlist.resistors.append(Resistor(name=f"GMIN::{i+1}", n1=n, n2="0", ohms=1e9))
        op_results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)
        issue_dicts = [_issue_to_dict(i) for i in (issues or [])]
        error_count = len([i for i in issue_dicts if str(i.get("severity", "")).lower() == "error"])

        spice_netlist_text = _compiled_netlist_to_spice(compiled.netlist)
        spice_result = run_ngspice(netlist_text=spice_netlist_text, timeout_s=30)

        solution = op_results.get("solution")
        node_v = getattr(solution, "node_v", {}) if solution is not None else {}
        vsource_i = getattr(solution, "vsource_i", {}) if solution is not None else {}
        summary = {
            "converged": bool(op_results.get("converged")),
            "iterations": int(op_results.get("iterations") or 0),
            "node_count": len(node_v) if isinstance(node_v, dict) else 0,
            "source_count": len(vsource_i) if isinstance(vsource_i, dict) else 0,
            "error_count": error_count,
            "warning_count": len(issue_dicts) - error_count,
        }
        return {
            "board_id": board_id,
            "ok": error_count == 0 and bool(summary["converged"]),
            "path": str(p),
            "kind": "netlist" if ext == ".net" else "pcb",
            "issues": issue_dicts,
            "summary": summary,
            "op_results": {
                "converged": summary["converged"],
                "iterations": summary["iterations"],
                "node_v": node_v if isinstance(node_v, dict) else {},
                "vsource_i": vsource_i if isinstance(vsource_i, dict) else {},
            },
            "spice": spice_result,
        }
    except Exception as e:
        return {
            "board_id": board_id,
            "ok": False,
            "path": str(p),
            "kind": "netlist" if ext == ".net" else "pcb",
            "error": "solver_exception",
            "issues": [
                {
                    "severity": "error",
                    "issue": "solver_exception",
                    "explanation": str(e),
                    "solution": "Provide stronger board hints (sources/loads/constraints) or validate connectivity model.",
                }
            ],
            "summary": {"converged": False, "iterations": 0, "node_count": 0, "source_count": 0, "error_count": 1, "warning_count": 0},
            "op_results": {"converged": False, "iterations": 0, "node_v": {}, "vsource_i": {}},
            "spice": {"ok": False, "error": "skipped_due_solver_exception"},
        }


def _has_error_issue(items: List[Dict[str, Any]]) -> bool:
    for i in items:
        if str(i.get("severity") or "").lower() == "error":
            return True
    return False


def _has_mecha_block(mecha: Dict[str, Any]) -> bool:
    for item in (mecha.get("simulation") or []):
        if str((item or {}).get("severity") or "").lower() == "block":
            return True
    for item in (mecha.get("dfm") or []):
        if str((item or {}).get("severity") or "").lower() == "block":
            return True
    return False


def _build_full_sim_gates(analysis: Dict[str, Any], board_sims: List[Dict[str, Any]], *, strict: bool) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []

    gates.append(
        {
            "gate": "system_power_and_links",
            "passed": not _has_error_issue((analysis.get("power") or {}).get("issues") or [])
            and not _has_error_issue((analysis.get("interconnects") or {}).get("issues") or [])
            and not _has_error_issue((analysis.get("control_coupling") or {}).get("issues") or []),
            "required": True,
            "detail": "System-level power/interconnect/control checks must have no error issues.",
        }
    )

    missing_or_fail = [b for b in board_sims if not b.get("ok")]
    gates.append(
        {
            "gate": "board_level_operating_point",
            "passed": len(missing_or_fail) == 0,
            "required": True,
            "detail": "Each board netlist/pcb must compile and pass operating-point validation.",
        }
    )

    ng_ok = all(bool((b.get("spice") or {}).get("ok")) for b in board_sims) if board_sims else False
    gates.append(
        {
            "gate": "board_level_ngspice_crosscheck",
            "passed": ng_ok,
            "required": bool(strict),
            "detail": "Each board should pass ngspice .op cross-check (strict mode requires this).",
        }
    )

    mecha = analysis.get("mechanism") or {}
    mecha_ok = bool(mecha.get("ok")) and not _has_mecha_block(mecha)
    gates.append(
        {
            "gate": "mechanical_simulation",
            "passed": mecha_ok,
            "required": bool(strict),
            "detail": "Mechanism simulation should succeed with no block-level finding (strict mode).",
        }
    )
    return gates


def _full_sim_verdict(gates: List[Dict[str, Any]]) -> str:
    for g in gates:
        if bool(g.get("required")) and not bool(g.get("passed")):
            return "fail"
    if all(bool(g.get("passed")) for g in gates):
        return "pass"
    return "partial_pass"


def full_simulate_machine_system(
    machine: Dict[str, Any],
    *,
    board_design_files: Optional[Dict[str, Dict[str, Any]]] = None,
    mechanism_spec: Optional[Dict[str, Any]] = None,
    simulation_fidelity: str = "high",
    strict: bool = True,
) -> Dict[str, Any]:
    engineering = engineer_machine_system(
        machine,
        run_mechanism_sim=bool(mechanism_spec),
        mechanism_spec=mechanism_spec or {},
        simulation_fidelity=simulation_fidelity,
    )
    compiled = engineering.get("compiled") or {}
    analysis = engineering.get("analysis") or {}
    boards_compiled = compiled.get("boards") or []
    compiled_hints_by_board = {str(b.get("board_id")): (b.get("hints") or {}) for b in boards_compiled if isinstance(b, dict)}
    auto_hints_by_board = _auto_board_hints_from_machine(machine)
    hints_by_board = {
        bid: _merge_hints(compiled_hints_by_board.get(bid) or {}, auto_hints_by_board.get(bid) or {})
        for bid in set(list(compiled_hints_by_board.keys()) + list(auto_hints_by_board.keys()))
    }

    design_map = _board_file_map(machine, board_design_files)
    board_sims: List[Dict[str, Any]] = []
    missing_designs: List[str] = []
    for b in boards_compiled:
        bid = str((b or {}).get("board_id") or "").strip()
        if not bid:
            continue
        meta = design_map.get(bid)
        if not meta:
            missing_designs.append(bid)
            board_sims.append({"board_id": bid, "ok": False, "error": "missing_design_file"})
            continue
        board_sims.append(_simulate_board_design_file(bid, str(meta.get("path") or ""), hints_by_board.get(bid) or {}))

    gates = _build_full_sim_gates(analysis, board_sims, strict=strict)
    verdict = _full_sim_verdict(gates)
    report_lines: List[str] = []
    report_lines.append(f"# Full Simulation Report — {((compiled.get('machine') or {}).get('machine_name') or machine.get('machine_name') or 'machine')}")
    report_lines.append("")
    report_lines.append(f"- Generated: `{_utc_now()}`")
    report_lines.append(f"- Strict mode: `{strict}`")
    report_lines.append(f"- Verdict: `{verdict}`")
    if missing_designs:
        report_lines.append(f"- Missing board design files: `{', '.join(missing_designs)}`")
    report_lines.append("")
    report_lines.append("## Gates")
    for g in gates:
        report_lines.append(f"- `{g.get('gate')}` required=`{g.get('required')}` passed=`{g.get('passed')}`")
    report_lines.append("")
    report_lines.append("## Board Simulations")
    for b in board_sims:
        s = b.get("summary") or {}
        spice = b.get("spice") or {}
        report_lines.append(
            f"- `{b.get('board_id')}` ok=`{b.get('ok')}` converged=`{s.get('converged')}` errors=`{s.get('error_count')}` ngspice=`{'ok' if spice.get('ok') else spice.get('error') or 'n/a'}`"
        )
    full_report_md = "\n".join(report_lines).rstrip() + "\n"

    return {
        "machine": compiled.get("machine") or {},
        "engineering": engineering,
        "board_simulations": board_sims,
        "gates": gates,
        "strict": strict,
        "verdict": verdict,
        "report_md": full_report_md,
    }
