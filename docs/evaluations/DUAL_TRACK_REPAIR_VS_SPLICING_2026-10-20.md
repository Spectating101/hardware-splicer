# Hardware Splicer: first repair versus multi-donor splicing benchmark

2026-10-20, Optiplex, KiCad present, Qwen disabled, independent branch
stacked on the commerce-donor data branch (#148).

## Two fundamentally different missions

- Repair: one broken original device, diagnose, describe a supported repair,
  restore and independently verify its ORIGINAL functionality.
- Splicing: multiple unrelated broken sources, identify recoverable
  subassemblies, design a NEW integrated machine with working cross-donor
  interfaces, mechanical integration, control software and functional proof.

For the first run we used existing preconfigured examples as positive
controls and two truly unverified marketplace challenges. The latter were
fed to the current planner as explicitly untested candidate available_parts
to expose capability shortcomings. All marketplace items remain UNOWNED,
UNTESTED and seller-claimed: this was only a software-stress injection.

| Software test | Selected design | Pipeline PASS | KiCad DRC | Real mission proved |
| --- | --- | --- | --- | --- |
| RC repair-themed preconfigured fixture | robot_drive_base | yes | yes | not tested: RC repair not attempted |
| Inkjet motion preconfigured fixture | plotter_motion_stage | yes | yes | not tested: only one printer source |
| Unowned, cut-cable Symbol LS2208 (original-function repair) | usb_uart_debug_adapter | yes | yes | NO, produced wrong target |
| Unowned LS2208 + Epson LQ-680 + QNAP TS-219P II + Apple mouse (novel inspection/indexing machine) | inspection_motion_fixture | yes | yes | NO, zero verified donor circuit modules |

**Audit counts:** 2/2 fixture compiles passed; 2/2 marketplace compiles
passed; 2/2 marketplace cases reported pipeline PASS; 0/2 marketplace
engineering missions completed; 0 physical devices examined.

### Key discovered failure

Carrier DRC and process exit status are not an engineering acceptance
oracle. The currently deployed direct --intake path in scripts/splice_demo.py
reports manifest PASS based on result.ok, even when the actual source-bound
repair/recombination requirements are not demonstrated.

1. Repair: generic USB/UART debug adapter is not a repair plan to restore
   barcode decoding in the LS2208. A real repair must identify cable/
   interface variant, differential fault hypotheses, documented wiring,
   safe checks, and a real post-fix scan test.
2. Heterogeneous splicing: inspection_motion_fixture is a plausible
   concept, but this result has **zero** circuit-backed usable blocks
   derived from measured donor source electronics. No donor optical
   interface, printer motor contract, NAS power/computing integration,
   switch wiring, mechanical fit, firmware or product operation proved.
3. Marketplace sourcing claims were misrepresented as physical available
   parts *only for testing*. This must never occur on a real fabrication
   path. The discovery inventory in PR #148 exists precisely to keep
   seller information separate from real hardware evidence.
4. The preloaded repair-cafe RC example is itself a REPURPOSING story,
   rather than repair/restoration of the original RC system. It is a
   useful positive control for the splice compiler, not a repair score.

### Independent acceptance gates required next

Repair needs: actual owned faulty specimen; device baseline test; safe
fault-isolation evidence; documented compatible replacement/repair
instructions; repair attempt by qualified human; restoration test
on the original function; reproducibility and repair artifact record.

Splicing needs: multiple actual owned/inspected heterogeneous specimens;
subsystem IDs and interfaces proven with documents plus measurement;
explicit selection and rejection reasoning; a NEW product requirement;
correct circuit design, mechanics, control software; operator-logged
integration, physical operation and end-to-end functional evaluation.
Reusing every damaged component is NOT necessary.

Suggested engineering priorities:
- Separate repair/restore from salvage/repurpose at the goal router.
- Add goal-coverage acceptance, not a generic compiler PASS.
- Never elevate listings/part-name keyword matches to electrical contracts.
- For new product assembly, enforce source-specific module identities,
  documented pin/power specs, physical geometry and behavior tests.

### Reproduction

From repo root on a system with KiCad and Python dependencies:

    PYTHONPATH=src python -m scripts.benchmark_repair_vs_splicing \
      --out /tmp/hs-dual-track

Generates four full sets of software artifacts plus a separate objective
summary. For prior Optiplex run, a sanitized machine-readable summary is
in dual_track_marketplace_2026-10-20.json adjacent to this document.
No equipment was purchased, physically powered, repaired, wired, flashed,
fabricated or tested. KiCad DRC applies to *generated* carrier boards only.
