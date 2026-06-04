from __future__ import annotations

import math
from typing import Any, Dict, List, Literal

from ..spec import ProjectSpec
from .servo_library import get_servo_dims, torque_nm


Fidelity = Literal["starter", "high"]


def run_simulation_summary(project: ProjectSpec, *, fidelity: Fidelity = "starter") -> List[Dict[str, Any]]:
    """
    Mechanical simulation summary.

    starter:
      - fast conservative estimates.
    high:
      - expanded analytical model with margins/critical-speed/stress checks.
      - pybullet mechanism scenes for linear-axis / pan-tilt when available.
    """
    if fidelity == "high":
        out = _run_high_fidelity(project)
        out.extend(_run_pybullet_scenes(project))
        return out
    return _run_starter(project)


def _run_starter(project: ProjectSpec) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    if project.linear_axis is not None:
        ax = project.linear_axis
        r_m = (ax.pulley_teeth * 2.0 / 1000.0) / (2.0 * math.pi)
        est_torque = ax.payload_n * r_m
        out.append(
            {
                "severity": "info",
                "domain": "linear_axis",
                "model": "starter",
                "message": f"Load torque estimate: {est_torque:.2f} N·m at pulley {ax.pulley_teeth}T.",
            }
        )
        if est_torque > 0.35:
            out.append(
                {
                    "severity": "warn",
                    "domain": "linear_axis",
                    "model": "starter",
                    "message": "Estimated torque is near/above typical NEMA17 comfort range.",
                }
            )

    if project.leadscrew_axis is not None:
        ax = project.leadscrew_axis
        rpm = (ax.target_speed_mm_s / ax.lead_mm_per_rev) * 60.0 if ax.lead_mm_per_rev > 0 else 0.0
        out.append(
            {
                "severity": "info",
                "domain": "leadscrew_axis",
                "model": "starter",
                "message": f"Leadscrew speed estimate: {rpm:.0f} rpm.",
            }
        )
        if rpm > 1200:
            out.append(
                {
                    "severity": "warn",
                    "domain": "leadscrew_axis",
                    "model": "starter",
                    "message": "RPM is high for a T8 axis; expect whip/backlash unless heavily constrained.",
                }
            )

    if project.gripper is not None:
        g = project.gripper
        t_req = g.max_payload_n * (g.lever_arm_mm / 1000.0)
        t_servo = torque_nm(get_servo_dims(g.servo_type))
        out.append(
            {
                "severity": "info",
                "domain": "gripper",
                "model": "starter",
                "message": f"Torque estimate: required≈{t_req:.2f} N·m vs servo stall≈{t_servo:.2f} N·m.",
            }
        )
        if t_req > 0.6 * t_servo:
            out.append(
                {
                    "severity": "warn",
                    "domain": "gripper",
                    "model": "starter",
                    "message": "Required torque is high relative to servo stall torque.",
                }
            )

    if project.pan_tilt is not None:
        ptt = project.pan_tilt
        t_req = ptt.max_payload_n * (ptt.payload_offset_mm / 1000.0)
        t_servo = torque_nm(get_servo_dims(ptt.tilt_servo))
        out.append(
            {
                "severity": "info",
                "domain": "pan_tilt",
                "model": "starter",
                "message": f"Tilt torque estimate: required≈{t_req:.2f} N·m vs servo stall≈{t_servo:.2f} N·m.",
            }
        )
        if t_req > 0.6 * t_servo:
            out.append(
                {
                    "severity": "warn",
                    "domain": "pan_tilt",
                    "model": "starter",
                    "message": "Tilt torque margin is low; reduce offset/payload or use stronger actuator.",
                }
            )

    return out


def _run_high_fidelity(project: ProjectSpec) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    if project.linear_axis is not None:
        ax = project.linear_axis
        g = 9.81
        mass_kg = ax.payload_n / g
        accel_m_s2 = ax.target_accel_mm_s2 / 1000.0
        r_m = (ax.pulley_teeth * 2.0 / 1000.0) / (2.0 * math.pi)
        force_n = ax.payload_n + mass_kg * accel_m_s2
        torque_nm_load = force_n * r_m

        j_ref = mass_kg * (r_m**2)
        alpha = accel_m_s2 / max(r_m, 1e-6)
        torque_nm_dyn = j_ref * alpha
        torque_nm_total = torque_nm_load + torque_nm_dyn

        torque_nm_cont_limit = 0.28
        margin = torque_nm_cont_limit / max(torque_nm_total, 1e-9)
        sev = "info" if margin >= 1.3 else "warn" if margin >= 1.0 else "block"
        out.append(
            {
                "severity": sev,
                "domain": "linear_axis",
                "model": "high",
                "message": (
                    f"Axis torque (load+dynamic)≈{torque_nm_total:.2f} N·m; "
                    f"continuous-target margin≈{margin:.2f}x."
                ),
                "metrics": {
                    "torque_total_nm": round(torque_nm_total, 4),
                    "torque_margin_x": round(margin, 3),
                },
            }
        )

        E = 200e9
        d_m = ax.rod_d_mm / 1000.0
        L_m = ax.rod_length_mm / 1000.0
        I = math.pi * d_m**4 / 64.0
        delta_mm = ((ax.payload_n * (L_m**3)) / (48.0 * E * max(I, 1e-12))) * 1000.0
        sev = "info" if delta_mm <= 0.5 else "warn" if delta_mm <= 1.0 else "block"
        out.append(
            {
                "severity": sev,
                "domain": "linear_axis",
                "model": "high",
                "message": f"Estimated rod deflection≈{delta_mm:.2f} mm (steel, simply-supported assumption).",
                "metrics": {"rod_deflection_mm": round(delta_mm, 4)},
            }
        )

    if project.leadscrew_axis is not None:
        ax = project.leadscrew_axis
        lead_mm = ax.lead_mm_per_rev
        rpm_target = (ax.target_speed_mm_s / lead_mm) * 60.0 if lead_mm > 0 else 0.0

        c = 0.36
        d_root_mm = max(5.5, ax.screw_d_mm - 2.0)
        n_crit = (4.76e6 * d_root_mm * c) / max(ax.screw_length_mm**2, 1.0)
        ratio = rpm_target / max(n_crit, 1e-9)
        sev = "info" if ratio <= 0.7 else "warn" if ratio <= 1.0 else "block"
        out.append(
            {
                "severity": sev,
                "domain": "leadscrew_axis",
                "model": "high",
                "message": f"Leadscrew target speed≈{rpm_target:.0f} rpm, critical-speed ratio≈{ratio:.2f} (est.).",
                "metrics": {
                    "rpm_target": round(rpm_target, 2),
                    "critical_speed_ratio": round(ratio, 4),
                },
            }
        )

        force_n = ax.payload_n + (ax.payload_n / 9.81) * (ax.target_accel_mm_s2 / 1000.0)
        lead_m = lead_mm / 1000.0
        eff = 0.32
        torque_nm_req = (force_n * lead_m) / (2.0 * math.pi * eff)
        sev = "info" if torque_nm_req <= 0.30 else "warn" if torque_nm_req <= 0.45 else "block"
        out.append(
            {
                "severity": sev,
                "domain": "leadscrew_axis",
                "model": "high",
                "message": f"Lead-screw drive torque≈{torque_nm_req:.2f} N·m (efficiency {eff:.2f} assumed).",
                "metrics": {"required_torque_nm": round(torque_nm_req, 4)},
            }
        )

    if project.rotary_joint is not None:
        r = project.rotary_joint
        force_n = 20.0
        arm_m = r.arm_len_mm / 1000.0
        moment_nm = force_n * arm_m
        b = r.arm_w_mm / 1000.0
        h = r.arm_t_mm / 1000.0
        section_modulus = b * (h**2) / 6.0
        stress_mpa = (moment_nm / max(section_modulus, 1e-12)) / 1e6
        sev = "info" if stress_mpa <= 20 else "warn" if stress_mpa <= 35 else "block"
        out.append(
            {
                "severity": sev,
                "domain": "rotary_joint",
                "model": "high",
                "message": f"Arm bending stress≈{stress_mpa:.1f} MPa (reference load {force_n:.0f} N).",
                "metrics": {"bending_stress_mpa": round(stress_mpa, 4)},
            }
        )

    if project.gripper is not None:
        gspec = project.gripper
        t_req = gspec.max_payload_n * (gspec.lever_arm_mm / 1000.0)
        t_servo = torque_nm(get_servo_dims(gspec.servo_type))
        sf = t_servo / max(t_req, 1e-9)
        sev = "info" if sf >= 2.0 else "warn" if sf >= 1.2 else "block"
        out.append(
            {
                "severity": sev,
                "domain": "gripper",
                "model": "high",
                "message": f"Gripper torque safety-factor≈{sf:.2f}x (stall/reference).",
                "metrics": {"torque_safety_factor_x": round(sf, 4)},
            }
        )

    if project.pan_tilt is not None:
        ptt = project.pan_tilt
        t_req = ptt.max_payload_n * (ptt.payload_offset_mm / 1000.0)
        t_servo = torque_nm(get_servo_dims(ptt.tilt_servo))
        sf = t_servo / max(t_req, 1e-9)
        sev = "info" if sf >= 2.0 else "warn" if sf >= 1.2 else "block"
        out.append(
            {
                "severity": sev,
                "domain": "pan_tilt",
                "model": "high",
                "message": f"Tilt torque safety-factor≈{sf:.2f}x (stall/reference).",
                "metrics": {"tilt_torque_safety_factor_x": round(sf, 4)},
            }
        )

    if not out:
        out.append(
            {
                "severity": "info",
                "domain": "general",
                "model": "high",
                "message": "No motion subsystem available for high-fidelity analysis.",
            }
        )
    return out


def _run_pybullet_scenes(project: ProjectSpec) -> List[Dict[str, Any]]:
    try:
        import pybullet as p  # type: ignore
    except Exception:
        return [
            {
                "severity": "info",
                "domain": "rigid_body",
                "model": "pybullet_skip",
                "message": "PyBullet not installed; skipped mechanism dynamics scenes.",
            }
        ]

    out: List[Dict[str, Any]] = []
    if project.linear_axis is not None:
        out.append(_simulate_linear_axis_pybullet(project, p))
    if project.pan_tilt is not None:
        out.append(_simulate_pan_tilt_pybullet(project, p))
    if not out:
        out.append(
            {
                "severity": "info",
                "domain": "rigid_body",
                "model": "pybullet",
                "message": "PyBullet available, but no supported scene type requested (linear_axis / pan_tilt).",
            }
        )
    return out


def _simulate_linear_axis_pybullet(project: ProjectSpec, p: Any) -> Dict[str, Any]:
    ax = project.linear_axis
    assert ax is not None

    cid = p.connect(p.DIRECT)
    try:
        p.setTimeStep(1.0 / 240.0, physicsClientId=cid)
        p.setGravity(0, 0, -9.81, physicsClientId=cid)

        base_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.2, 0.03, 0.02], physicsClientId=cid)
        car_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.02, 0.03, 0.02], physicsClientId=cid)

        link_mass = max(0.05, ax.payload_n / 9.81)
        body = p.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=base_col,
            basePosition=[0.0, 0.0, 0.02],
            linkMasses=[link_mass],
            linkCollisionShapeIndices=[car_col],
            linkVisualShapeIndices=[-1],
            linkPositions=[[0.0, 0.0, 0.03]],
            linkOrientations=[[0.0, 0.0, 0.0, 1.0]],
            linkInertialFramePositions=[[0.0, 0.0, 0.0]],
            linkInertialFrameOrientations=[[0.0, 0.0, 0.0, 1.0]],
            linkParentIndices=[0],
            linkJointTypes=[p.JOINT_PRISMATIC],
            linkJointAxis=[[1.0, 0.0, 0.0]],
            physicsClientId=cid,
        )

        pulley_radius_m = (ax.pulley_teeth * 2.0 / 1000.0) / (2.0 * math.pi)
        max_force = max(5.0, 0.28 / max(pulley_radius_m, 1e-6))
        target_v = ax.target_speed_mm_s / 1000.0

        positions: List[float] = []
        velocities: List[float] = []
        steps = 480
        for _ in range(steps):
            p.setJointMotorControl2(
                body,
                0,
                p.VELOCITY_CONTROL,
                targetVelocity=target_v,
                force=max_force,
                physicsClientId=cid,
            )
            p.stepSimulation(physicsClientId=cid)
            js = p.getJointState(body, 0, physicsClientId=cid)
            positions.append(float(js[0]))
            velocities.append(float(js[1]))

        max_vel_mm_s = max(abs(v) for v in velocities) * 1000.0 if velocities else 0.0
        final_travel_mm = abs(positions[-1]) * 1000.0 if positions else 0.0
        tracking_ratio = max_vel_mm_s / max(ax.target_speed_mm_s, 1e-6)

        severity = "info"
        if tracking_ratio < 0.7:
            severity = "warn"
        if final_travel_mm < min(ax.travel_mm * 0.2, 20.0):
            severity = "block"

        return {
            "severity": severity,
            "domain": "linear_axis",
            "model": "pybullet_linear_axis",
            "message": (
                f"PyBullet axis scene: max speed≈{max_vel_mm_s:.1f} mm/s, "
                f"travel≈{final_travel_mm:.1f} mm, tracking ratio≈{tracking_ratio:.2f}."
            ),
            "metrics": {
                "target_speed_mm_s": round(ax.target_speed_mm_s, 2),
                "max_speed_mm_s": round(max_vel_mm_s, 2),
                "tracking_ratio": round(tracking_ratio, 4),
                "simulated_travel_mm": round(final_travel_mm, 2),
                "steps": steps,
            },
        }
    finally:
        p.disconnect(physicsClientId=cid)


def _simulate_pan_tilt_pybullet(project: ProjectSpec, p: Any) -> Dict[str, Any]:
    ptt = project.pan_tilt
    assert ptt is not None

    cid = p.connect(p.DIRECT)
    try:
        p.setTimeStep(1.0 / 240.0, physicsClientId=cid)
        p.setGravity(0, 0, -9.81, physicsClientId=cid)

        base_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.05, 0.05, 0.01], physicsClientId=cid)
        l1_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.03, 0.01, 0.03], physicsClientId=cid)
        l2_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.04, 0.01, 0.01], physicsClientId=cid)

        payload_kg = max(0.02, ptt.max_payload_n / 9.81)
        body = p.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=base_col,
            basePosition=[0.0, 0.0, 0.02],
            linkMasses=[0.08, 0.05 + payload_kg],
            linkCollisionShapeIndices=[l1_col, l2_col],
            linkVisualShapeIndices=[-1, -1],
            linkPositions=[[0.0, 0.0, 0.03], [0.03, 0.0, 0.04]],
            linkOrientations=[[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]],
            linkInertialFramePositions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
            linkInertialFrameOrientations=[[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]],
            linkParentIndices=[0, 1],
            linkJointTypes=[p.JOINT_REVOLUTE, p.JOINT_REVOLUTE],
            linkJointAxis=[[0.0, 0.0, 1.0], [0.0, 1.0, 0.0]],
            physicsClientId=cid,
        )

        pan_target = math.radians(25.0)
        tilt_target = math.radians(20.0)
        pan_torque = torque_nm(get_servo_dims(ptt.pan_servo)) * 0.55
        tilt_torque = torque_nm(get_servo_dims(ptt.tilt_servo)) * 0.55

        pan_err2: List[float] = []
        tilt_err2: List[float] = []
        steps = 720
        for _ in range(steps):
            p.setJointMotorControl2(
                body,
                0,
                p.POSITION_CONTROL,
                targetPosition=pan_target,
                force=max(0.05, pan_torque),
                physicsClientId=cid,
            )
            p.setJointMotorControl2(
                body,
                1,
                p.POSITION_CONTROL,
                targetPosition=tilt_target,
                force=max(0.05, tilt_torque),
                physicsClientId=cid,
            )
            p.stepSimulation(physicsClientId=cid)
            pan_pos = float(p.getJointState(body, 0, physicsClientId=cid)[0])
            tilt_pos = float(p.getJointState(body, 1, physicsClientId=cid)[0])
            pan_err2.append((pan_target - pan_pos) ** 2)
            tilt_err2.append((tilt_target - tilt_pos) ** 2)

        pan_rms_deg = math.degrees(math.sqrt(sum(pan_err2) / max(len(pan_err2), 1)))
        tilt_rms_deg = math.degrees(math.sqrt(sum(tilt_err2) / max(len(tilt_err2), 1)))

        severity = "info"
        if pan_rms_deg > 4.0 or tilt_rms_deg > 4.0:
            severity = "warn"
        if pan_rms_deg > 9.0 or tilt_rms_deg > 9.0:
            severity = "block"

        return {
            "severity": severity,
            "domain": "pan_tilt",
            "model": "pybullet_pan_tilt",
            "message": (
                f"PyBullet pan-tilt scene: RMS error pan≈{pan_rms_deg:.2f}deg, "
                f"tilt≈{tilt_rms_deg:.2f}deg."
            ),
            "metrics": {
                "pan_rms_error_deg": round(pan_rms_deg, 4),
                "tilt_rms_error_deg": round(tilt_rms_deg, 4),
                "pan_target_deg": 25.0,
                "tilt_target_deg": 20.0,
                "steps": steps,
            },
        }
    finally:
        p.disconnect(physicsClientId=cid)
