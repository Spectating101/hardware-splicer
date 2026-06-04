# Spec (v1)

Mecha‑Splicer v1 accepts a single JSON object (see `src/mecha_splicer/spec.py`).

Scopes in v1:
- `enclosure` (rectangular base + lid, cutouts)
- `bracket` (simple plate with holes)
- `servo_mount` (robotics template: servo cutout + flange holes)
- `linear_axis` (robotics template: GT2 belt-driven axis printable parts)
- `leadscrew_axis` (robotics primitive: T8 lead-screw axis printable parts)
- `rotary_joint` (robotics primitive: bearing block + arm)
- `belt_reduction` (movement primitive: GT2 reduction plate)
- `gripper` (mechanism primitive: servo scissor gripper parts)
- `pan_tilt` (mechanism primitive: servo pan/tilt plates)
- `assembly` (placement graph: generates `ASSEMBLY.scad` that imports + places modules)
  - Supports `instances[].anchors` and `mates[]` for simple constraint-based placement.
  - `mates[].kind`: `anchor`, `center_to_center`, `mount_plane_flush`, `shaft_into_bearing`
  - `mates[].kind`: also supports `bolt_pattern`, `rod_pair_align`, `axis_collinear`
  - `mates[].params`:
    - `bolt_pattern`:
      - single hole align: `{ "pattern": "nema17", "hole": "ne" }`
      - full pattern align: `{ "pattern": "nema17", "align": "full", "a1": "ne", "a2": "nw", "b1": "ne", "b2": "nw" }`
      - best-fit align: `{ "pattern": "nema17", "align": "best_fit", "holes": ["ne","nw","se","sw"] }`

EE→ME bridge (v1):
- `electronics` (PCB outline + ports/mounts). This is a stub for future integration flows.

Run:
- `python3 scripts/mecha_splicer_spec.py --spec examples/enclosure_basic.json --out /tmp/mecha_bundle`
- `python3 scripts/mecha_splicer_spec.py --spec examples/servo_mount_sg90.json --out /tmp/mecha_servo_bundle`
- `python3 scripts/mecha_splicer_spec.py --spec examples/linear_axis_gt2.json --out /tmp/mecha_axis_bundle`
- `python3 scripts/mecha_splicer_spec.py --spec examples/leadscrew_axis_t8.json --out /tmp/mecha_ls_bundle`
- `python3 scripts/mecha_splicer_spec.py --spec examples/rotary_joint_608.json --out /tmp/mecha_rj_bundle`
- `python3 scripts/mecha_splicer_spec.py --spec examples/belt_reduction_gt2.json --out /tmp/mecha_br_bundle`
- `python3 scripts/mecha_splicer_spec.py --spec examples/gripper_scissor_sg90.json --out /tmp/mecha_gr_bundle`
- `python3 scripts/mecha_splicer_spec.py --spec examples/pan_tilt_sg90.json --out /tmp/mecha_pt_bundle`
- `python3 scripts/mecha_splicer_spec.py --spec examples/assembly_demo.json --out /tmp/mecha_asm_bundle`
