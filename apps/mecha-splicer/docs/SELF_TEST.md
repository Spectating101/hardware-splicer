# Self-Test (confidence checklist)

If you want a quick “is this actually working?” verification, run these and inspect the outputs.

## 1) GT2 belt axis bundle
- Input spec: `examples/linear_axis_gt2.json`
- Expected outputs include: `motor_mount.scad`, `idler_mount.scad`, `carriage.scad`, `belt_clamp.scad`

## 2) T8 lead-screw axis bundle
- Input spec: `examples/leadscrew_axis_t8.json`
- Expected outputs include: `ls_motor_mount.scad`, `ls_screw_end_support.scad`, `ls_carriage_nut_mount.scad`

## 3) Enclosure bundle
- Input spec: `examples/enclosure_basic.json`
- Expected outputs include: `enclosure.scad` and `bom.csv`

## 4) Rotary joint bundle
- Input spec: `examples/rotary_joint_608.json`
- Expected outputs include: `rj_bearing_block.scad`, `rj_arm.scad`

## 5) Belt reduction bundle
- Input spec: `examples/belt_reduction_gt2.json`
- Expected outputs include: `br_reduction_plate.scad`

## 6) Gripper bundle
- Input spec: `examples/gripper_scissor_sg90.json`
- Expected outputs include: `gr_base.scad`, `gr_jaw_left.scad`, `gr_jaw_right.scad`

## 7) Pan/tilt bundle
- Input spec: `examples/pan_tilt_sg90.json`
- Expected outputs include: `pt_base.scad`, `pt_bracket.scad`, `pt_platform.scad`

## 8) Assembly bundle
- Input spec: `examples/assembly_demo.json`
- Expected outputs include: `ASSEMBLY.scad` (and referenced part `.scad` files)

## Commands
Run from the repo root:

```bash
python3 scripts/mecha_splicer_spec.py --spec examples/linear_axis_gt2.json --out /tmp/mecha_gt2
python3 scripts/mecha_splicer_spec.py --spec examples/leadscrew_axis_t8.json --out /tmp/mecha_ls
python3 scripts/mecha_splicer_spec.py --spec examples/enclosure_basic.json --out /tmp/mecha_enc
python3 scripts/mecha_splicer_spec.py --spec examples/rotary_joint_608.json --out /tmp/mecha_rj
python3 scripts/mecha_splicer_spec.py --spec examples/belt_reduction_gt2.json --out /tmp/mecha_br
python3 scripts/mecha_splicer_spec.py --spec examples/gripper_scissor_sg90.json --out /tmp/mecha_gr
python3 scripts/mecha_splicer_spec.py --spec examples/pan_tilt_sg90.json --out /tmp/mecha_pt
python3 scripts/mecha_splicer_spec.py --spec examples/assembly_demo.json --out /tmp/mecha_asm
```

Then open:
- `/tmp/mecha_gt2/MECH_CHECK.md`
- `/tmp/mecha_ls/MECH_CHECK.md`
- `/tmp/mecha_enc/MECH_CHECK.md`
- `/tmp/mecha_rj/MECH_CHECK.md`
- `/tmp/mecha_br/MECH_CHECK.md`
- `/tmp/mecha_gr/MECH_CHECK.md`
- `/tmp/mecha_pt/MECH_CHECK.md`
- `/tmp/mecha_asm/ASSEMBLY.scad`
