# X500 V2 – first runnable hardware-assembly workflow in HS

## What's genuinely implemented

- A machine-readable Holybro X500 V2 + Pixhawk 6C BOM, seven gated assembly stages, compatibility unknowns and published reference URIs: [`x500_v2.json`](./x500_v2.json).
- A **real HTML-source compilation command**, `scripts/build_x500_dossier.py`, which reads a locally supplied PX4 X500 assembly guide snapshot, checks its identity, records a SHA256, discovers ten source assembly/configuration sections, and compiles nine distinct power/control interfaces. It exports both a JSON dossier and a readable Markdown assembly checklist under `generated/`. It does **not** ingest full manufacturer kit pages yet.
- A **parts-on-hand workflow**, `scripts/assess_x500_inventory.py`, that cross-references all BOM lines and required stages against reported inventory. Unknown quantity or unverified model/compatibility does not count as ready. The first run has no physical inventory declared, so all 11 BOM lines are missing, and all stages retain `hold`.
- Tests for no release authorization and for rejecting inconsistent inputs, irrelevant manual HTML and incomplete manuals.

## Reproduction on Optiplex

The PX4 source was retrieved into `/tmp/hs_px4_x500_source.html` at the time of the experiment. That source's SHA256 is retained in the dossier (`f6759d026ea9dfec459e1b0ff63f370915d4bd6f813e57602977602d06d48b36`). The HTML is not committed into this repository, because it belongs to the upstream publisher. It can be fetched afresh; hashes may change when the site changes.

```bash
curl -L --fail -o /tmp/hs_px4_x500_source.html https://docs.px4.io/main/en/frames_multicopter/holybro_x500v2_pixhawk6c
python3 scripts/build_x500_dossier.py --source-html /tmp/hs_px4_x500_source.html
python3 scripts/assess_x500_inventory.py eval/drone_reference_build/available_inventory.json
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_build_x500_dossier.py tests/test_drone_assembly_readiness.py tests/test_drone_reference_build.py
```

The published reference is the [PX4 X500 V2 build guide](https://docs.px4.io/main/en/frames_multicopter/holybro_x500v2_pixhawk6c). Its assembly sections are source-linked rather than copied wholesale; review its illustrations and original fastener directions when assembling.

## What the current output actually means

The generated dossier is an **assembly preparation package**, not proof of build success. It shows 11 reference BOM entries, 10 linked assembly sections, 9 interfaces and 7 unresolved engineering/release checks. The source content is captured and hash-addressed, **but manufacturer documents, connector revisions, thrust measurements, battery datasheets and physical build data remain unverified**. No parts have been bought or inspected; no drone has been assembled, powered or flown. No simulation has been run by this workflow yet.

This matters because the objective is to progress from HS's previous unrelated catalog recommendations into a real-documented assembly route, and later into measured engineering fit and cost. The immediate next practical task is manufacturer part-number crosswalk and actual purchased/on-hand inventory, not inventing another synthetic engineering scenario.

## Other repositories

See [`ecosystem.md`](./ecosystem.md) for integration choices and the clone-and-KiCad-rule-check results on a community drone controller repository. Those are deliberately not treated as proven drop-in substitutes for the X500 stack.
