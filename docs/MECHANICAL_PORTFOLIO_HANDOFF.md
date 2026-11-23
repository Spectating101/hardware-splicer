# Generalized PCB mechanical handoff — HS, Policy Lab and Cite

**Experimental, 20 November 2026.** This is a bounded new mechanical capability, not a universal mechanical CAD solver and not a replacement for HS's mission or project store.

## Why

The existing registered rectangular PCB nest assumes a four-hole mounting pattern. That was not established for Seeed XIAO ESP32C3. The new module selects a non-clamping, stationary hole-less inspection tray instead of inventing hole coordinates. For SparkFun OpenLog Artemis it instead reads the pinned original EAGLE board XML, verifies four mounting footprints H1–H4 by position and drill, and selects a standoff-based tray. The two designs have independently reopened STEP files and watertight STL outputs. **Neither is physical fit evidence.**

## Source and execution contracts

- HS source: src/hardware_splicer/mechanical_fixture_handoff.py
- HS request: hardware_splicer.mechanical_fixture_request.v1
- HS output: hardware_splicer.mechanical_fixture_evidence.v1
- Policy Lab branch app: applications/mechanical-fixture-policy, reuses its real application foundation
- Cite native bridge: src/hardware_splicer/mechanical_portfolio_handoff.py
- Cite CLI: scripts/try_mechanical_portfolio_handoff.py
- Input examples: examples/mechanical_portfolio/xiao-nominal-request.json and openlog-source-holes-request.json
- Outcomes: exact source and implementation hashes, source-backed strategy choice, revised CAD, verification, Policy Lab decision and isolated Cite graph/HTML report.

XIAO's 21 × 17.8 mm model comes from **declared manufacturer nominal dimensions**, not a decoded outline from the source DXF ZIP. That original ZIP is hash-checked and is not redistributed. Board thickness, complete USB plug envelope, antenna, underside and GPIO/contact geometry, fixture retention, ESD properties, wear and actual fit are not verified. The USB corridor is **provisional**. The OpenLog's EAGLE hole coordinates are verified from the named source elements, but its mounting fitness is still untested in reality.

The caller provides project ID and revision. This pilot currently writes separate, immutable revision output folders; it is **not integrated into the HS canonical DigitalStudyEngine project store or live UI**, and does not automatically propagate changes. No source-independent material or geometry claims are authorized.

## Reproduce the existing XIAO route

Provide the official original DXF ZIP with the SHA specified in the example request. Use the checked HS CAD Python environment. Commands below run in private scratch output and do not alter current worktrees.

    HS=/path/to/hs-mechanical-handoff
    HS_PY=/path/to/hs-cad-python
    PL=/path/to/policy-mechanical
    CITE=/path/to/cite-refinery
    CITATION=/path/to/approved/citation-engine/src/citation_engine
    SOURCE=/path/to/XIAO-ESP32C3-DXF.zip
    OUT=/private/empty-test

    PYTHONPATH="$HS/src" "$HS_PY" -m hardware_splicer.mechanical_fixture_handoff --request "$HS/examples/mechanical_portfolio/xiao-nominal-request.json" --source "$SOURCE" --out "$OUT/hs"
    HASH=$(sha256sum "$OUT/hs/mechanical-evidence.json" | cut -d' ' -f1)
    node "$PL/applications/mechanical-fixture-policy/run.mjs" review --evidence "$OUT/hs/mechanical-evidence.json" --sha256 "$HASH" --policy "$PL/applications/mechanical-fixture-policy/example-policy.json" --out "$OUT/policy"
    node "$PL/applications/mechanical-fixture-policy/run.mjs" verify --evidence "$OUT/hs/mechanical-evidence.json" --review "$OUT/policy/review.json"
    cd "$HS"
    PYTHONPATH="$HS/src:$HS" "$HS_PY" -m scripts.try_mechanical_portfolio_handoff --evidence "$OUT/hs/mechanical-evidence.json" --review "$OUT/policy/review.json" --source "$SOURCE" --cite-root "$CITE" --citation-source "$CITATION" --policy-root "$PL" --out "$OUT/dossier"

The script must be invoked as a Python module because a legacy scripts/hardware_splicer.py would otherwise shadow the package.

## What was actually tested

- XIAO with unknown mount holes: automatic hole-less strategy, nominal geometry checks passed.
- A strict 0.8 mm gap policy blocked the first 0.4 mm revision. A second explicitly changed HS request generated different CAD, with 0.8 mm nominal gap. Policy Lab accepted only the digital target and replay verified it.
- Submitting a first-revision Policy Lab review with second-revision HS evidence was refused **before Cite output creation**.
- A physical-operation review was blocked.
- OpenLog: original manufacturer EAGLE hole coordinates matched all four source anchors and drove the standoff strategy. Deliberately altered coordinate/drill input is rejected.
- Cite: an explicitly invoked native isolated project imports and traces original source to strategy to CAD to Policy Lab decision to report. It does not touch the running private Atlas tenant.

The ordinary CadQuery route in the earlier controlled trial also produced a nominal tray. This does **not** establish an HS speed, cost or quality advantage: there was no blind engineering comparator or measured human effort. The contribution shown here is a source-aware change workflow, not proof of autonomous fabrication or profitable product production.

## Next acceptance

Before calling this a general HS product: connect source identification to canonical ProjectStore revisions, replace provisional USB/contact keepouts with source-specific geometry, independently test hardware/print repeatability, and run a clean-room engineering comparison with equal acceptance criteria. The cross-project watcher and unattended refresh remain unimplemented.
