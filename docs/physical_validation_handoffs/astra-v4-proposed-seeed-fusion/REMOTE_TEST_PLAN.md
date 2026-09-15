# Remote physical validation test request

- Handoff: `remote-physical-handoff-987035a2e27e074b`
- Project: `hs-astra-rawdoc-v4-20260913-1`
- Candidate: `hs-astra-rawdoc-v4-20260913-1@b7c724e0561d4ec8`
- Provider target: Seeed Fusion PCBA
- Authority: none; this request does not authorize fabrication or power-on.

## Required execution order

| Phase | Gate | Procedure | Required return |
|---:|---|---|---|
| 0 | `identify-dut` — Record the exact physical DUT identity | `hs.spi.identify-dut.v1` | Original raw file(s); `observed_top_marking`, `observed_package`, `observed_pin_count`, `observed_dimensions_mm` |
| 0 | `identify-programmer` — Record the exact programmer and interface identity | `hs.spi.identify-programmer.v1` | Original raw file(s); `manufacturer`, `model`, `serial_or_asset_id`, `interface_connector` |
| 0 | `identify-adapter-artifact` — Bind the assembled adapter and translator to immutable identities | `hs.spi.identify-adapter-artifact.v1` | Original raw file(s); `assembly_id`, `assembly_revision`, `translator_orderable_mpn`, `translator_package`, `schematic_hash`, `pcb_or_wiring_hash` |
| 1 | `cold-continuity-and-isolation` — Verify pin mapping, ground continuity, shorts, and domain isolation | `hs.spi.cold-continuity-isolation.v1` | Original raw file(s); `net_by_net_results`, `ground_continuity_ohm`, `vcc_1v8_to_ground_ohm`, `vcc_3v3_to_ground_ohm`, `domain_isolation_results` |
| 2 | `current-limited-power-up` — Measure startup and steady-state rails under a current limit | `hs.spi.current-limited-power-up.v1` | Original raw file(s); `supply_current_limit_a`, `dut_vcc_min_v`, `dut_vcc_max_v`, `startup_peak_current_a`, `steady_state_current_a`, `power_off_backfeed_current_a` |
| 3 | `logic-level-and-timing-capture` — Capture both voltage domains and timing at the selected load and clock | `hs.spi.logic-level-timing.v1` | Original raw file(s); `spi_clock_hz`, `host_side_levels_v`, `dut_side_levels_v`, `rise_fall_times_s`, `propagation_delays_s`, `overshoot_undershoot_v` |
| 4 | `read-only-jedec-identity` — Repeat a read-only JEDEC identity transaction | `hs.spi.read-only-jedec-id.v1` | Original raw file(s); `command_hex`, `response_hex_by_trial`, `trial_count`, `clock_hz` |
| 4 | `thermal-dwell` — Measure translator, regulator, and DUT temperature over a bounded dwell | `hs.spi.thermal-dwell.v1` | Original raw file(s); `ambient_c`, `dwell_s`, `translator_max_c`, `regulator_max_c`, `dut_max_c` |

## Return rules

- Identify the provider work order, physical site, test article revision, and serial number.
- Name the direct operator for every executed gate.
- Return original instrument exports or captures with SHA-256 and byte size.
- Include instrument identities and calibration records for instrumented gates.
- Report failures with their raw captures; do not replace them with a summary PASS/FAIL sheet.
- Do not claim that the provider report grants fabrication, power-on, or physical authority.

## Safety boundary

- `identify-dut`: Unpowered inspection only.
- `identify-programmer`: Do not connect the DUT or enable target power.
- `identify-adapter-artifact`: Unpowered inspection only; no identity may be inferred from family name.
- `cold-continuity-and-isolation`: All sources disconnected; discharge rails before resistance measurements.
- `current-limited-power-up`: Requires an applicable human BENCH_POWER authorization before energizing.
- `logic-level-and-timing-capture`: Begin at the lowest supported clock; stop on rail, current, or thermal excursion.
- `read-only-jedec-identity`: Only read-only identity command 0x9F; WREN, program, erase, and status writes are forbidden.
- `thermal-dwell`: Stop immediately on unexpected heating or current-limit activation.

## Current release status

Missing production artifact roles: assembly_drawing, bom, fabrication_archive, pick_and_place, schematic, test_firmware.
Fabrication release remains false until a separate human authorization is persisted.
