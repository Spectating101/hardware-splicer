# HS native inset side-pivot hinge — actual CGAL build and vendor screen qualification

Date: 2026-11-08. This is **Hardware Splicer engineering**. It modifies the existing native Mecha-Splicer generator with a new `inset_side_pins` variant while retaining the old `external_three_knuckle` architecture. A real OpenSCAD CGAL engine exported binary STLs and ran 6 shell motion poses, **plus 6 full nominal-screen proxy motion poses and a vendor-maximum thickness interference negative-control**.

**Context:** User wants a genuinely good, economically rational *personal* two-touchscreen programming/SSH device. No physical keyboard; no plan to form a company. Current reference target: **155×80×18 mm closed** and suggested not-yet-user-approved ~NT$8,000 parts target. This design is **not authorized** to fabricate, power or purchase.

## The actual mechanical improvement

Previously HS's outer three-segment pin hinge projected 4.6mm beyond the 80mm-deep shell, resulting in a 155×84.6mm folded footprint.

New native Mecha-Splicer hinge style:

- An internal pivot at **y=76.6 mm**, barrel radius **3.4 mm**, fully enclosed in 0..80 mm rear shell envelope.
- Two side-only left/right steel pin pairs with separate base and lid cylinders. No center knuckle: the LCDs use the central x=13.7..141.3 mm; side knuckles must stay outside that panel envelope.
- An explicit rear-wall clearance cut of **6.0 mm** along the rear region, **6.7 mm** high on the base, plus upper rear clearance. A **28mm center cable passage** is just a *hole*, not a designed, tested or strain-relieved DSI harness.
- Modelled anchor ears join the inner lid barrels to the sidewalls. Real pin material, retention, fatigue, hinge stops and strength are **not** proven.
- Built-in frame profile preserves the true 155×80 XY closed envelope and 18mm nominal Z.

**Source:** `spec.json` -> `mecha_splicer.bundle.generate_bundle` -> `evidence/base_shell.scad`, `lid_shell.scad`, `clamshell_open_preview.scad`, `dual_touch_visual_preview.scad`, vendor-correct BOM, and physical CGAL-exported STLs.

Tested opening angles: **0°, 30°, 60°, 90°, 135°, 165°**. All **six shell intersections** are empty, with watertight/2-manifold output by the STL edge audit: base 964 triangles, lid 1044, zero non-manifold edges. This proves only mathematical intersection-free static shells, not a usable hinge mechanism.

The additional native `hardware_splicer.cyberdeck_panel_collision` uses **nominal 127.6×73.3×3.45mm LCD solids** in BOTH halves at the same six hinge positions; no cross-half intersections. The deliberate **3.95mm vendor maximum LCD** collision test against the current upper lid produces a **nonempty CGAL intersection**. Actual 3D panel STEP, FPC, connector and battery solids have NOT been included.

## Why a geometrically valid hinge does NOT mean a usable enclosure

**1. Screen retention and exposed rear edge fail.** Winstar's optical-bonded PCAP panel has no frame mounting holes. At 80mm shell depth and 73.3mm panel depth, the panel's rear edge ends at **y=76.65 mm**. The hinge swing cut begins at **y=74.0 mm**, leaving **2.65mm** of the LCD hanging beyond the local rear-upper shell support. Panel fastening, adhesive aging, service/repair and rear dust protection remain unresolved.

**2. Real tolerances fail the 18mm promise.** Manufacturer drawing for Winstar **WF50DTYA3MNG10-000** specifies **3.45±0.50mm** Z. The earlier HS nominal 5.1mm lid counted only 1.6mm shell + 3.45mm panel = **5.05mm**, leaving 0.05mm. With a explicitly assumed 0.15mm rear bondline and the vendor permitted 3.95mm panel, the lid alone requires **5.70mm**. The resulting minimum closed height under the *existing* 1mm component margin and 6.0mm **naked/unprotected** battery placeholder is **19.05mm**, a minimum **+1.05mm** above the fixed target. Even assuming **zero bondline** leaves a **18.90mm** lower bound. Real BMS/pack swelling, carrier mating uncertainty, thermal pad compression, fastening and FPC bends can only worsen this.

**3. Exact model needs a higher-voltage LED rail.** Datasheet for exact `WF50DTYA3MNG10#000` gives display LED **19.6–23.8 V at 40 mA**, or **0.784–0.952 W each** and **1.568–1.904 W for both**. The LEDs must have a dedicated current-controlled boost/backlight driver. **Never connect these LED pins directly to the battery or a generic 5V supply.** The panel also requires correct VCI/IOVCC and touch VDDT rails, power sequencing, and dual DSI at impedance-controlled 100-ohm differential. None is designed or powered.

**4. Firmware and real electronics remain untested.** RPi CM4 supports DSI0 (2 lanes) and DSI1 (4 lanes) *physically*, but Linux panel init/ILI9881C, GT928 addresses/interrupt/reset wiring, simultaneous dual-panel operation and keyboard touch layouts are **not** proven. Straight bare panel flex tails extend well outside the closed body and need a fatigue-tested hinged loop.

Sources:
- **Exact 2-lane Winstar panel**: https://www.winstar.com.tw/d/676/WF50DTYA3MNG10-000.pdf (pages 8–10, 30). Parent family page describes a different **4-lane** near-SKU—don't interchange.
- **CM4 DSI physical/electrical routing**: https://datasheets.raspberrypi.com/cm4/cm4-datasheet.pdf, section 2.8.
- **Prior HS architecture and CM4 nominal packaging**: `examples/cyberdeck/cm4_thin_stack/`, PR #309.

## HS conclusion

**KINEMATIC CAD GATE = PASS. SCREEN RETENTION + VENDOR TOLERANCE = FAIL. RELEASE GATE = BLOCKED.**

The important result is a stronger understanding of *what matters*:
- Hinge position can be improved without growing external dimensions.
- But the necessary rear hinge swing cut sacrifices screen support and environmental protection.
- And the dimensional tolerance plus even a nominal bonding allowance invalidates the 18mm build as currently specified.
- There is **no** defensible complete all-in parts cost or working Linux device yet.

Further changes should consider a **better hinge/screen frame with rear support**, a **thinner qualified display/cell stack**, and actual touch/DSI electrical tests. Do NOT erase structural, battery or tolerance allowances just to make a pretty render.

## Reproduce

From the repository root with actual OpenSCAD available:

```bash
export PYTHONPATH=src:apps/mecha-splicer:apps/mecha-splicer/src:examples/cyberdeck
python - <<'PY'
from pathlib import Path
from produce_terminal import run
root=Path("examples/cyberdeck/inset_hinge_test").resolve()
run(root/"spec.json",root/"evidence","/usr/bin/openscad")
PY
python -m hardware_splicer.cyberdeck_panel_collision \
  --spec examples/cyberdeck/inset_hinge_test/spec.json \
  --native-mecha examples/cyberdeck/inset_hinge_test/evidence \
  --openscad /usr/bin/openscad \
  --out examples/cyberdeck/inset_hinge_test/panel_CGAL_report.json
python -m hardware_splicer.cyberdeck_inset_hinge_gate \
  --qualification examples/cyberdeck/inset_hinge_test/qualification_input.json \
  --out examples/cyberdeck/inset_hinge_test/hinge_qualification.json
python -m pytest -q tests/test_cyberdeck_inset_hinge.py
```

The two vendor-aware native reports and all CAD meshes are included in this folder. CI verifies actual six-pose CGAL execution, an intentional vendor-thickness collision, source provenance and fail-closed release.
