# HS-3G-B: a revised GPS/FPV drone candidate

This advances the existing HS-3G project through the registered Hardware Splicer workshop operator. It preserves GPS, analog FPV and the sub-250 g objective, changes the motor/prop/battery combination, and regenerates the frame and manufacturing handoff. The original HS-3G package remains a retained baseline.

The [candidate package](reference/README.md) contains editable STEP/STL/DXF plates, a component placement STEP, a 1:1 post-drill sheet, hole coordinates, BOM, wiring guidance, a partial INAV configuration, and the hash-checked official firmware image with upstream source evidence and licence. Native data files retain their original bytes; Git attributes keep generated CAD/firmware noise out of the source diff.

Run from the repository root with a Python environment containing the CAD extra, PyYAML and native verification dependencies:

```bash
PYTHONPATH=src "$NATIVE_PYTHON" scripts/hs_workshop_operator.py \
  --case hs3g_drone_revision_b --out /path/to/a/new/run --execute
```

The operator stages the Git-tracked project, runs the CAD builder, tries the bounded wheelbase candidates, and starts a separate artifact verifier. It never overwrites the retained source. The committed firmware evidence allows offline replay; new downloads, when needed, must match the immutable lock hashes. `--execute` performs software work only.

The actual design iteration rejects 135 mm because prop clearance is 2.38 mm against the retained 3 mm requirement. At 137 mm the model reaches 3.34 mm clearance and 234.90 g takeoff mass, retaining 15.10 g nominal mass reserve. A named +5 g battery uncertainty leaves 10.10 g for other unmodeled mass. These are model outputs, not scale measurements.

The F1404 KV2900/Gemfan 3028-3 maker table gives 25.8 A total at full command. Including the explicit voltage sensitivity and 20% design factor gives 31.24 A, below the selected pack's 59.5 A nameplate continuous rating and the connector's conditional 35 A rating. The factory-XT60 pack provides specified 12AWG leads; no XT30 adapter or battery rewiring is proposed. No check depends on a throttle cap.

The cutting files omit the sixteen 2.2 mm motor holes; a composite shop must quote and qualify the separate drilling operation. Finished drilled geometry remains explicitly outside the waterjet-only small-hole/web screen. Passing the blank screen is not cutter approval or proof of laminate strength.

Independent checks reimport STEP, inspect DXF hole counts and STL closure/volume, reconcile BOM CSV with the model, validate the partial CLI against pinned INAV settings, verify the official HEX digest/checksums, and bind the receipt to artifact hashes. Tampering with the BOM, the cut blank or firmware is rejected.

The [verification receipt](reference/verification.json) is limited to that digital scope. Controller stock/shipping, shop acceptance, actual motor/battery dimensions, configuration/calibration, frame vibration and powered bench evidence remain open. Purchase readiness and all fabrication, power and flight permissions remain false. The thinner plates and motor pads require structural review; no hardware completion is claimed.

The retained build-versus-buy study indicates a commercial GPS BNF can cost less. This revision serves the editable design and engineering-operator objective, not a lowest-price purchasing claim. Prices in the BOM remain labelled snapshots or assumptions, with freight, tax and tooling excluded.
