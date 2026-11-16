# Hardware Splicer: unfamiliar keyboard PCB corpus (2026-11-15)

**Purpose:** independent challenge set against the existing cut/reconnect engine, instead of reusing an internally authored six-switch success fixture. These eight designs were found through public GitHub repository discovery and come from **seven independent repositories** (Vyom contributes two); selection is a **convenience sample**, not random sampling and not physical e-waste.

**Result: no strict arbitrary-donor success**. One external f.60 design recovers all model-cut copper connections using the existing source net graph, but the proposed cut still damages retained switches. Four require additional electrical reconstruction; three are rejected at intake.

| External source and design | Unknown-input result | Reason |
|---|---|---|
| coarse/st40 | REPAIR_INCOMPLETE | 49 detected switch footprints, but 8 required source copper groups remain disconnected and no qualified interposer channel exists |
| dodotronix/kinesis_board fkeys | SOURCE_TRIAGE_REJECTED | 18 detected switches; two conducting GND zones lack saved polygon fills, so a source-conformant electrical model cannot be trusted |
| bhoppe-dev/Shortcut_Keyboard | SOURCE_TRIAGE_REJECTED | Four copper layers; experimental reconstruction currently covers only two |
| Logan-Fouts/Plink | UNSUPPORTED_KICAD_SOURCE_FORMAT_OR_NATIVE_IMPORT | Board saved in KiCad 10 format; tested engine uses native KiCad 9 |
| robertcalvert/f.60 | RECONNECTED_BUT_CUT_COLLIDES | All cut-related required copper groups model-reconnected; proposed geometry intersects five switch keepouts and one pad keepout |
| dingyifei/NHW68 | REPAIR_INCOMPLETE | 68 detected keys, but a modeled required group remains disconnected and source geometry is not fully verified |
| Vyom88/Mechanical-Keyboard-PCBs practice2by2 | REPAIR_INCOMPLETE | Four detected MX keys and source gap uncertainties; model still has a required disconnected group |
| Vyom88/Mechanical-Keyboard-PCBs vyom60 | REPAIR_INCOMPLETE | Larger 91-candidate switch layout, unresolved source/cut connections and route interference |

The exact source paths and SHA-256 values are pinned in **manifest.json**. Source files were downloaded into an external temporary directory for analysis and **are not vendored into Hardware Splicer**. Every result is source-bound, and unsupported cases cannot inherit success from another board.

## Run or reproduce

From the HS repository root:

    PYTHONPATH=src python scripts/run_arbitrary_keyboard_pilot.py \
      --sources /tmp/your-external-pcb-corpus \
      --out /tmp/your-new-benchmark-output \
      --system-python /usr/bin/python3 \
      --fetch

The --fetch option downloads any missing pinned public source file, verifying its SHA-256. Existing files also require the exact expected digest. A changed upstream repository fails closed instead of substituting a newer design. The output directory must be new to prevent stale successes. Install the optional Shapely/NumPy dependency and KiCad 9 first; see the parent README.

**Inspect** evidence_final_20261115/BENCHMARK.json and the eight individual case summaries. Each qualified source has its original KiCad DRC evidence if obtainable within the bounded check window, a cut-path report, post-cut island simulation, repair iteration trace and (only when bridge candidates exist) a KiCad preview with actual DRC evidence. Missing DRC information counts as **not verified**, never zero violations.

**Scoring rule:** a strict digital pass requires all required post-cut modeled copper groups reconnected, no original modeled terminal gaps, a cut that clears all recorded pads/vias/switches/controller regions, a DRC-clean original PCB, a DRC-clean bridge PCB, and no unresolved approximations. It is deliberately tougher than merely drawing a jumper.

## Engineering implications

- The arbitrary-source importer now recognizes Cherry/Alps/Kailh/Choc/MX keyboard switch footprints across diverse reference names. It no longer confuses the SKQG auxiliary reset button in the practice sample with a Cherry MX key.
- The KiCad zone extractor checks actual per-layer filled polygons before accessing them, avoiding a native crash on unfilled Kinesis zones. It reports the absent conducting GND fills rather than silently using the outline as copper.
- KiCad's native rounded-rectangle pads are represented with their source corner radii, instead of completely dropping them from net connectivity.
- The explicit intake gate rejects unsupported copper stackups, unfilled conductive zones, absent key-switch evidence, and missing routed copper before simulation.
- The benchmark runner records negative outcomes, rejects changed source hashes, and never marks simulated reference results as a tested physical junk keyboard.
- A disconnected board with **zero reconstructable bridge channels** now records a blocked interposer result rather than throwing away the already generated analysis report.

**Not proven:** reading arbitrary unknown e-waste PCBs from photographs, fabricating or physically sawing any used board, repairing flex-membrane keyboard silver ink, a universal connector/cable, firmware validation, production yields, commercial value, or a passing fully arbitrary e-waste conversion. Those are open tasks, not successful test claims.


## Follow-up virtual recovery (2026-11-16): source-preserving key remount

The strict eight-board benchmark above remains unchanged (0/8 physically complete or strict digital passes). For the externally authored **f.60** source, HS now searches 12 cut alternatives, selects a balanced route with no modeled live-pad/via/controller damage, *retires five key locations* and generates a second native KiCad daughterboard to remount those five original key functions. The selected split retains 24 original key positions left and 33 right; adding the five-key daughterboard accounts for all **62 source switch positions**.

The reconnection PCB has **17 native KiCad channels**; the five-key daughterboard provides **ten source net-bound wire endpoints**. Both PCBs have passed their own KiCad DRCs (0 violations / 0 opens), and the cut-related graph has no remaining required disconnections in the model. The source f.60's own legacy PCB DRC **timed out**, however, and the physical connector/assembly/firmware are unverified.

Full evidence, assembly/wiring preview and run command: [f60_remount_round5/README.md](f60_remount_round5/README.md).

**Conditional source-based electrical reconstruction is not arbitrary physical-junk proof**, and the strict 0/8 benchmark score is intentionally retained.


## Full original f.60 source equivalence and consolidated wiring (2026-11-16)

The conditional f.60 recovery now includes a SHA-pinned comparison with its independently authored schematic/netlist and original TMK firmware:

- 267 electrically connected schematic node assignments match all 267 actual source PCB pad net assignments.
- 62 actual source switches each connect through one diode to one of 5 firmware rows × 14 firmware columns, and all 62 firmware keymap entries match the source keys.
- 91,230 ideal simulated press patterns passed, including cross-row combinations and every one-row subset.
- A 20-net-group, 49-pin source-reference KiCad junction board removes double-terminating donor solder pads: 39 unique original donor pads and 10 relocated-key leads. Its native KiCad DRC is clean.
- HS canonical MachineProject declares the source firmware, full matrix, junction and three proposed unverified physical interfaces but still refuses fabrication.

See [f60_remount_round5/README.md](f60_remount_round5/README.md) and its full original-source SHA and machine evidence. The earlier original f.60 board DRC timeout and lack of a real donor remain unresolved, so the **strict eight-board arbitrary-junk success score remains 0/8**.


## Source DRC and smaller ID-connected conversion (2026-11-16)

Source-attested f.60 follow-up now has a **KiCad 9 refilled-zone copy with zero DRC errors and zero unconnected copper** (but **321 warnings**) while preserving every original pad, track, via, switch and component position outside the filled copper areas. The previously unfinishable legacy source DRC is thus understood and reproducibly bounded.

All **19 original Teensy 2.0 matrix GPIO pins** match the official PJRC pinout and exact original KiCad footprint, and the original 62-key TMK mapping remains fully source-attested. A new 50-pin latching IDC option retains the same 49 donor/remount source connections on a PCB with **49.1% less area** and zero native PCB DRC errors.

These proofs do **not** change the original eight-board *arbitrary donor* strict benchmark (0/8). They are derived from the known f.60 reference, not actual physical e-waste.

[Inspect source, DRC, controller and compact KiCad design proof](f60_remount_round5/README.md).
