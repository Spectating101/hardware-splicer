# Native Teardown integration: source-bound HS machine explanation

2026-11-01. Stacked on verified PR #244. External upstream: https://github.com/elvarofficial/teardown (MIT).

## Scope and honest engineering classification

The **real upstream Teardown runtime and offline bundler** is used for an interactive, standalone HTML page with mesh picking, part isolation, exploded view, a section plane, alternate camera angles and source-linked dimension annotations. The machine description comes from HS's generic multi-CAD parts manifest. It does NOT pretend to be an independently measured machine mechanism or pressurized operating device.

- Input: actual source-bound CADCLAW -> independently authored build123d/CadQuery STEP -> PartCAD CLI-executed 4-part package, as proven in #244.
- \`TEARDOWN_INPUT.json\` contains exactly those parts, original hashed STEP metadata and independently checked bounding dimensions.
- Geometry in the viewer is **analytic box/cylinder reconstruction from verified extents**, NOT a tessellation of arbitrary vendor STEP and NOT validated physical assembly. User-visible text makes this explicit.
- Output: \`machine/main.js\` imports \`teardown-kit/runtime.js\` from the exact pinned upstream repository. Their \`sims/build.mjs\` and npm-locked Three.js produce one offline self-contained \`dist/machine.html\`.
- Native browser gate: Playwright uses Chromium to load the actual offline file, tests part buttons, exploded movement, section/isolation and rendered canvas, and captures a real screenshot. Refuse any remote network call or browser exception.
- Source/Evidence: separate hashes of original spec, rendered HTML, screenshot, CLI evidence; test harness checks both provenance and that no physical authorization was promoted.

## Why this adds value

This reuses Teardown's existing offline packaging and shared animation/runtime interface to present machines to users and potential reviewers without HS building its own renderer. Unlike the static product sheet, the user can pick, isolate and inspect a source-bound part and animate an exploded visualization. It is reusable across HS products that produce independently verified analytic part manifests.

## What remains unproven

Teardown's repo is a **Claude Code skill + browser runtime**, not a physics/FEA mechanism solver and not a verified CAD/STEP importer. Current HS integration intentionally does not invent hydraulic pressure, airflow, trajectories, contact constraints, vendor bracket fits or functional operation. To animate real motors, fluid actuators or gear trains, connect **validated motion models** before claiming a "functional simulator." A later adapter may consume verified glTF tessellations from native STEP BReps, explicit assembly transforms, calibrated kinematic models and field measurements. This PR does none of that.

No external source is vendored in HS; upstream Teardown is cloned and pinned in the CI job, MIT attribution retained upstream.
