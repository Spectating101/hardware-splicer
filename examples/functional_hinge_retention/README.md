# HS cyberdeck hinge: retained shaft + modeled external cable

This is a **new reference engineering experiment**, stacked on the
two-leaf hinge project in PR #333. Its purpose is to move beyond an
uncaptured pivot and a hypothetical empty cable keepout. Geometry is
actual CadQuery/OpenCascade, not illustrative CAD-shaped JSON.

## New actual solids and acceptance gates

The source design (spec.json) uses the previous balanced_60 hinge,
but does NOT claim measurements from a purchased phone or screen.

**Grooved 96 mm metal reference shaft**
- Nominal diameter 3.0 mm, matching the parent hinge's 3.5 mm
  through-bore (0.25 mm nominal radial clearance).
- Two shaft grooves, centered at X = -45.2 and +45.2 mm; 2.2 mm
  reduced diameter, 0.95 mm axial width.
- Two separate C-shaped metal spring-ring *reference* solids, with
  6.2 mm outside diameter, 2.34 mm bore, 0.70 mm axial thickness.
  Actual spring deflection during installation is NOT simulated.
- Source BRep check: 1.85 mm minimum retaining-ring to moving-leaf
  gap over 37 sampled hinge positions; 3.7 mm modeled TOTAL nominal
  permitted axial shaft float between both stop locations.
- Ring outer radial diameter exceeds source knuckle bore and ring
  inner radius clears the machined reference groove. STEP import
  confirms distinct actual shaft/left/right hardware geometries.
- No metal parts have been purchased, grooved or tested. The
  modeled C-ring geometry is NOT a catalog-qualified circlip.
  Retainer pullout load, vibrational motion, shaft wear, ring elastic
  deformation and realistic machining tolerances remain unknown.

**Actual swept cable-envelope solids, NOT a real installed wire**
- Two declared but unanchored exit points, one rotating with lid,
  with nominal 1.1 mm round cable width and a hypothetical minimum
  discrete centerline bending radius of 2.0 mm.
- Four alternative free-wire paths, each reoptimized at 5-degree
  increments for a constant nominal length. The nominal winner is
  re-evaluated across **181 positions at 1-degree intervals**.
- Actual 3D swept-tube BRep wires, one each at 0, 90 and 180 degrees,
  are exported as STEP with all five other solids of the assembly.
- The routes are **virtual**; no connectors, anchor clips, tabs,
  electrical continuity or strain relief have been designed or
  physically fabricated. Angle-dependent 3D splines do not prove
  elastic deformation, motion continuity or lifetime.

## Source-locked design results

| Modeled routing option | Minimum discrete bend radius | Folded cable-inclusive height | Status |
| --- | ---: | ---: | --- |
| Compact relief | 1.12 mm | 14.58 mm | Reject: misses assumed 2.0 mm radius |
| Medium relief | — | — | Reject: fixed-length path impossible at some angles |
| **Roomy relief** | **2.16 mm** | **18.57 mm** | **Nominal geometry selected** |
| Tall relief | 2.46 mm | 20.56 mm | Reject: above assumed 20 mm outer-envelope limit |

**New finding:** The original #333 12 mm closed height accounted
only for **printed hinge leaves**. Even the nominal feasible external
route increases the *cable-inclusive* folded envelope to approximately
**18.57 mm**, before actual screens, covers, electronics and fastening.
The original reserved empty 9 mm-radius cable cylinder does NOT
contain the newly modeled cable route. The original keepout therefore
needs resizing/repositioning, not just a confidence label.

The 2.0 mm bend-radius requirement is an illustrative screen, NOT a
verified real cable manufacturer minimum. A real flexible flat cable,
touchscreen ribbon or coax may need an entirely different route and
a significantly larger bend radius. The 20 mm outer-envelope gate
is also a scenario assumption rather than a validated device spec.

## Generated artifacts

- generated/shaft.step
- generated/ring_left.step and ring_right.step
- generated/cable_envelope_open_0.step,
  cable_envelope_half_90.step, cable_envelope_folded_180.step
- generated/assembled_with_virtual_wire_open_0.step,
  assembled_with_virtual_wire_half_90.step,
  assembled_with_virtual_wire_folded_180.step
- generated/function_intent.json, produced using the **existing**
  HS function-intent → MachineProject acceptance chain.
- generated/RETENTION_AND_CABLE_TRIAL.json: source hashes, BRep
  clearances, route failures, one-degree route checks and
  physical-authority flags.

The assembly files contain SIX independently re-importable solids:
two original leaves, one grooved metal shaft, two nominal C-rings
and one swept virtual cable tube. There is **no** claim that the
metal rings or virtual cable should be sent to an FDM printer.

## Run / audit

CadQuery 2.6.1 and NumPy are required for real BRep geometry.

    PYTHONPATH=src python3 examples/functional_hinge_retention/run.py \
      --out /tmp/hs_retention_trial

Independent source and STEP audit of committed output:

    PYTHONPATH=src python3 examples/functional_hinge_retention/run.py --audit-only

No experiment silently overwrites prior source results.

## Physical gates before treating this as a functional foldable

1. Choose an actual 3 mm rod or catalog shaft and matching standard
   retaining rings, then manufacture/buy and measure groove fit.
2. Determine spring-ring assembly access and maximum axial holding
   load; validate installation, serviceability and repeated rotation.
3. Specify actual screen modules/connectors and an actual cable type
   with datasheet bend-radius / maximum cycle requirements.
4. Design and integrate real physical cable anchoring and strain
   relief at both ends. The current endpoints are explicitly UNATTACHED.
5. Measure real closed thickness including external cable, display
   layers, covers, cables, buttons and electronics.
6. Print small hinge-bore and cable-guide coupons before committing
   full shells; qualify durability and electrical/ESD protection.

The nominal mechanism is a mechanically modeled candidate. It is not
a working physical hinge with a working flex harness, and neither
manufacturing nor hardware actuation has been authorized.
