# Local diagnosis — `agent/evidence-first-integration-stack` @ `6a94ad2`

Date: 2026-07-20  
Host: Optiplex Linux (local Grok execution arm)  
Branch HEAD before fixes: `6a94ad2a814fc5a167064de27ae02969c83a8989`

## Concise diagnosis

1. **Catalog-engine KiCad failure is CI-environment-specific, not a local PCB/serializer failure.**  
   Local KiCad **9.0.2** supports `--format json`. `verify_engine.py` scored **18/18 DRC clean**. Manual DRC on `sensor_logger` exit 0 with warnings only.

2. **Real-bench failure is the obsolete golden fixture** you already identified (`power_on_authorized` expected immediately from manual capture). Local run: `power_on_authorized=False`, report `passed=false`. Left for your migration.

3. **Frontend was blocked by test-fixture/DOM-cleanup issues plus a real submit wiring bug**, not by Vite/production build. After fixes: **40/40 tests**, production build OK. Evidence workbench renders and the two-stage contract path works in browser.

## Task 1 — Frontend

| Check | Result |
|-------|--------|
| `make splice-ui-build` (after fixes) | **PASS** — 40 tests, Vite build OK |
| Before fixes | 2 failed / 40 (`EvidenceWorkbenchPanel`) |
| Vite warning | dynamic+static import of `api.js` from `IntegrationsPanel` (pre-existing) |
| Runtime console errors (after submit fix) | **none** on Evidence/Bench path |
| `EvidenceWorkbenchPanel` | Renders; screenshots under `review-ui/evidence-first-local-2026-07-20/` |

Defects found and fixed narrowly:
- Missing RTL `cleanup()` → duplicate DOM / multi-button query failures.
- Contract editor only mounts when `onContractUpdate` is provided (test fixture).
- **`onContractUpdate` called `onBenchSubmit(buildDir, measurements)` but handler expects `(measurements)` only → 422 Unprocessable Content.**
- Completeness attestation control was missing from UI despite backend support; added checkbox wiring `interface_complete`.

## Task 2 — KiCad

```
kicad-cli --version → 9.0.2
kicad-cli pcb drc --help → supports --format json|report, --output, --exit-code-violations
```

`PYTHONPATH=src python scripts/verify_engine.py --out /tmp/hs_verify_engine_local --json /tmp/verify-engine-local.json`  
→ **Engine verify: 18/18 KiCad DRC clean, 18/18 compile ok**

Manual:
```
kicad-cli pcb drc --format json --output /tmp/hs_local_diag_2026-07-20/sensor_logger_manual_drc.json \
  /tmp/hs_verify_engine_local/sensor_logger/build_compilation/main_ctrl_build.kicad_pcb
→ exit 0; stdout: Found 23 violations (all severity warning); 0 unconnected
```

**Cause classification (local):** none of unsupported-format / parse-failure / shared error DRC / report-parse bug.  
**Likely CI cause:** Ubuntu `apt` KiCad differs from local 9.0.2 (missing/older CLI, libs, or PATH). Inspect uploaded `verify-engine-report` artifact on GitHub; no local compatibility patch required.

Artifacts: `/tmp/hs_local_diag_2026-07-20/`, `/tmp/hs_verify_engine_local/`, `/tmp/verify-engine-local.json`

## Task 3 — Focused authority tests (after fixture alignment)

```
PYTHONPATH=src pytest -q \
  tests/test_integration_stack.py \
  tests/test_evidence_salvage_bridge.py \
  tests/test_evidence_bench_gates.py \
  tests/test_kicad_cli_drc_unit.py
→ 20 passed
```

Initial failure (verbatim before fix):
```
assert applied["unresolved_fields"] == []
E AssertionError: assert ['interface_complete'] == []
```
Updated `test_typed_contract_update_persists_and_recomputes_authority` to the two-stage sequence (signal → completeness). Authority rules preserved.

## Task 4 — PlatformIO / KiBot

```
platformio: not installed
kibot: not installed
```
Skipped (no system install without approval).

## Real-bench (confirmation only)

```
make verify-splice-real-bench equivalent:
Golden real S3 verify: FAIL
power_on_authorized=False
report: /tmp/hs_splice_golden_real_verify/SPLICE_GOLDEN_REAL_VERIFY.json
```

## Remaining blockers (for ChatGPT / PR owner)

1. Migrate golden-real / real-bench to typed contract → completeness → measurement → power auth.
2. Re-run GitHub CI; investigate CI KiCad package/version vs local 9.0.2 using uploaded engine report.
3. Do not merge PR #1 yet.
4. Optional later: install PlatformIO/KiBot for backend certification.

## Screenshots

`review-ui/evidence-first-local-2026-07-20/`
1. `01-evidence-authority-overview-desktop.png`
2. `02-donor-interface-selector.png`
3. `03-typed-interface-editor.png`
4. `04-incomplete-interface-state.png`
5. `05-after-signal-without-completeness.png`
6. `06-after-completeness-attestation.png`
7. `07-transition-into-bench-desktop.png`
8. `08-evidence-authority-mobile.png`
