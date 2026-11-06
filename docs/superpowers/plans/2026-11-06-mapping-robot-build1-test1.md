# Mapping robot, Build 1 test 1 (real parts, sourced and understood) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Choose and document every bought module for the new-parts mapping robot (Build 1) from real listings and
primary sources, sized by HS's own drive and runtime maths, ending at the owner check-in.

**Architecture:** Two reusable HS capabilities are added: a Ruten listing client and a robot-part library whose every
fact names its source and is backed by a verbatim quote checked against a captured copy of that source. A project
folder `hardware/reference_designs/mapping_robot_v0/` holds the sizing script (which drives HS's
`robotics_simulation`), the gap log and the test 1 report. Part selection is research recorded as library entries.

**Tech Stack:** Python 3 (stdlib `urllib`), pytest, HS `robotics_simulation` / `robotics_actuation`.

**Spec:** `docs/superpowers/specs/2026-11-06-mapping-robot-design.md`

**Scope note:** this plan covers Build 1 test 1 only. Board, chassis, firmware and simulation depend on the parts chosen
here and get their own plans after the owner check-in at the end of Task 9.

## Global Constraints

- Nothing is bought and no seller is contacted. Ruten reads are read-only, about one request per second.
- No mains wiring. No lithium cell repacking; batteries are finished packs with a BMS.
- The repository is public: no secrets, no personal data.
- Commits are small, one concern each, imperative mood, capitalized, no prefix, no trailing period (`CLAUDE.md`);
  end each message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Every fact names its source; a typical rather than published figure says so and asks for a bench measurement;
  nothing is guessed silently; anything unconfirmed is marked unconfirmed.
- Sources order for bought modules: Ruten, then Taiwan maker shops or official stores, then cross-border (labelled).
  Shopee is not used.
- Requirement (designer's call): map and autonomously navigate a small apartment, fit through 70 cm doors, run at least
  60 minutes of continuous mapping (0.2 m/s with LiDAR, microcontroller and on-board computer running), repairable.
- Authority is never implicitly upgraded: no entry, report or script marks a part verified, approved or build-ready.
- Python: `PY=/home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/.venv/bin/python`, run from
  the worktree root with `PYTHONPATH=src`.

## Review Focus

1. A Ruten listing with several variants whose lowest price is a different item: the entry must name the chosen
   variant, and the client must expose `price_range` (Task 1 and Task 2 tests).
2. Seller-masked prices (e.g. 993800) read as real prices: the client flags them (Task 1 test).
3. Motor speed quoted at the motor shaft but used as wheel speed, or cell capacity used as pack capacity: facts carry
   explicit names and units, and the validator rejects a wrong unit (Task 2 test).
4. HS silently defaulting a missing motor voltage or current: sizing refuses to run on a part missing those facts
   (Task 4 test).
5. A quote that no longer appears in its source (page changed, typographic quotes): normalised matching, sha256 of the
   capture recorded, and a failing quote fails the check (Task 3 test).

---

### Task 1: Ruten listing client in HS

**Files:**
- Create: `src/hardware_splicer/ruten_listings.py`
- Test: `tests/test_ruten_listings.py`

**Interfaces:**
- Produces: `search(query: str, *, limit: int = 40, sleep: float = 1.0, client: RutenClient | None = None) -> list[Listing]`;
  `class RutenClient` with `.requests: int` and `.get(url: str, params: dict) -> object`;
  `Listing` = dict with keys `id, title, price_twd, price_range, sold_qty, stock, url, price_masked`.
- Endpoints (from `examples/arbitrage_lab/build_vs_buy/priced_bom.py` on PR #291):
  search `https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod` with
  `{"q", "type": "direct", "sort": "rnk/dc", "offset": 1, "limit"}` returning `Rows[].Id`;
  detail `https://rtapi.ruten.com.tw/api/prod/v2/index.php/prod` with `{"id": comma-joined ≤20 ids}` returning
  `ProdId, ProdName, PriceRange, SoldQty, StockQty`. User-Agent: `HS-robot-parts/1 (single-user research; low volume)`.

- [ ] **Step 1: Write failing tests** with `urllib.request.urlopen` monkeypatched to canned JSON:
  - `test_search_joins_search_and_detail`: one search reply with 2 ids, one detail reply → 2 listings,
    `url == "https://www.ruten.com.tw/item/<id>/"`, `client.requests == 2`.
  - `test_masked_price_is_flagged`: `PriceRange [993800, 993800]` → `price_masked is True`; `[450, 450]` → `False`
    (threshold 100000).
  - `test_detail_batches_of_twenty`: 45 ids → 3 detail requests.
  - `test_network_error_retried_http_error_not`: `URLError` twice then success → result returned after 3 calls;
    `HTTPError(500)` → raised after 1 call; `time.sleep` monkeypatched out.
- [ ] **Step 2: Run** `PYTHONPATH=src $PY -m pytest -q tests/test_ruten_listings.py` → FAIL (module missing).
- [ ] **Step 3: Implement** the module: 3 tries, backoff 5 s × attempt, `sleep` seconds after every request.
- [ ] **Step 4: Run** the same command → PASS.
- [ ] **Step 5: Commit** `Add a read-only Ruten listing client with retries and masked-price flags`.

### Task 2: Robot part library and validator

**Files:**
- Create: `src/hardware_splicer/robot_parts.py`, `src/hardware_splicer/data/robot_parts.json`
- Test: `tests/test_robot_parts.py`

**Interfaces:**
- Produces: `class RobotPartError(ValueError)`; `LIBRARY_PATH`; `PART_KINDS`; `REQUIRED_FACTS: dict[str, dict[str, str]]`
  (kind → fact name → unit); `validate_part(entry: dict) -> list[str]` (problems, empty when valid);
  `load_parts(path: Path = LIBRARY_PATH) -> list[dict]` (raises `RobotPartError` listing every problem).
- Library file: `{"schema_version": "hardware_splicer.robot_parts.v1", "rule": "<same rule sentence as device_modules.json>", "parts": []}`.
- Entry shape:

```json
{"id": "jga25-370-12v-130rpm-encoder", "kind": "drive_motor", "name": "...", "status": "SOURCED_NOT_MEASURED",
 "listing": {"url": "https://www.ruten.com.tw/item/.../", "marketplace": "ruten", "variant": "12V 130RPM",
             "price_twd": 280, "captured": "2026-11-07", "seller_claims": ["..."]},
 "sources": [{"label": "...", "url": "...", "as_of": "2026-11-07"}],
 "facts": {"rated_voltage": {"value": 12, "unit": "V", "basis": "published", "source": "<url in sources or listing>"},
           "encoder_cpr": {"alternatives": [{"value": 11, "source": "..."}, {"value": 12, "source": "..."}],
                           "unit": "count/rev_motor", "basis": "published", "confidence": "conflicting"}},
 "quotes": [{"claim": "rated_voltage", "quote": "...", "source": "..."}],
 "unconfirmed": [{"fact": "stall_current", "reason": "no source publishes it; measure on bench"}]}
```

- `PART_KINDS` and required facts (fact → unit):
  - `drive_motor`: rated_voltage V, output_free_speed_rpm rpm, rated_current A, stall_current A, stall_torque N·m,
    gear_ratio ratio, encoder_cpr count/rev_motor, encoder_supply_voltage V, shaft_diameter mm, body_dimensions mm,
    mass g, connector text
  - `wheel`: outer_diameter mm, width mm, bore mm, mass g
  - `caster`: height mm, mount text, mass g
  - `lidar`: supply_voltage V, supply_current A, interface text, baud_rate baud, protocol text, scan_rate Hz,
    range_max m, range_min m, motor_control text, pinout text, body_dimensions mm, mass g
  - `battery_pack`: nominal_voltage V, full_voltage V, capacity mAh, max_discharge_current A, bms text,
    connector text, body_dimensions mm, mass g
  - `dc_dc_converter`: input_voltage_range V, output_voltage V, max_output_current A, body_dimensions mm
  - `compute_board`: soc text, ram GB, supply_voltage V, typical_current A, peak_current A, ros2_support text,
    body_dimensions mm, mass g
  - `imu`: sensor text, interface text, supply_voltage V, body_dimensions mm

- [ ] **Step 1: Write failing tests** using in-test fixture entries (a valid drive motor `GOOD`):
  - `test_valid_entry_has_no_problems`: `validate_part(GOOD) == []`.
  - `test_fact_source_must_be_declared`: a fact whose `source` is in neither `sources` nor `listing.url` → problem
    naming the fact.
  - `test_wrong_unit_rejected`: `output_free_speed_rpm` with unit `"rad/s"` → problem.
  - `test_missing_required_fact_needs_unconfirmed_entry`: drop `stall_current` → problem; add it to `unconfirmed`
    with a reason → no problem.
  - `test_typical_basis_needs_bench_note`: `basis: "typical"` without `"measure"` in a `note` → problem.
  - `test_conflicting_needs_two_sourced_alternatives`: `confidence: "conflicting"` with one alternative → problem.
  - `test_multi_variant_listing_names_variant`: `listing.variant` empty → problem.
  - `test_cross_border_marketplace_is_labelled`: `marketplace` must be one of `ruten`, `maker_shop`,
    `official_store`, `cross_border`; `shopee` → problem.
  - `test_status_cannot_claim_authority`: `status` other than `SOURCED_NOT_MEASURED` (e.g. `VERIFIED`) → problem.
  - `test_quote_source_must_be_declared` and `test_quote_claim_names_a_fact`.
  - `test_load_parts_raises_with_every_problem` and `test_duplicate_ids_rejected` (tmp library file).
  - `test_shipped_library_loads`: `load_parts()` on the real file returns a list (empty now).
- [ ] **Step 2: Run** `PYTHONPATH=src $PY -m pytest -q tests/test_robot_parts.py` → FAIL.
- [ ] **Step 3: Implement** `robot_parts.py` and the empty library file.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `Add a sourced robot part library with a fact and unit validator`.

### Task 3: Quote verification against captured sources

**Files:**
- Modify: `src/hardware_splicer/robot_parts.py`
- Create: `scripts/capture_robot_part_sources.py`, `scripts/verify_robot_part_quotes.py`
- Test: `tests/test_robot_parts.py`

**Interfaces:**
- Consumes: `load_parts()` (Task 2).
- Produces: `normalise(text: str) -> str` (same rules as `scripts/verify_device_module_quotes.py`: NFKC, `−–`→`-`,
  `’`→`'`, collapse whitespace); `verify_quotes(parts: list[dict], capture_dir: Path) -> dict` returning
  `{"pass": bool, "quotes_checked": int, "failed": [...], "sources": {url: {"file", "sha256"}}}`;
  capture directory layout: `index.json` mapping `url → filename`, plus text files.
- Default capture dir: `.cache/hardware-splicer/robot_part_sources/` (gitignored: captures of third-party pages are
  not committed). The verify script writes its JSON result to
  `docs/status/generated/robot_part_quote_check_<YYYYMMDD>.json` (tracked evidence).
- Capture script: downloads each declared source URL, converts HTML to text (strip tags) and PDF to text with
  `pdftotext` when present, and records the file in `index.json`; a URL it cannot fetch is reported, not skipped.

- [ ] **Step 1: Write failing tests**: `test_quote_found_after_normalisation` (curly apostrophe and line break in the
  capture), `test_quote_missing_fails`, `test_quote_without_capture_fails`, `test_sha256_recorded`,
  `test_no_quotes_is_not_a_pass` (`pass` is False when `quotes_checked == 0`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `normalise`, `verify_quotes`, both scripts.
- [ ] **Step 4: Run** `PYTHONPATH=src $PY -m pytest -q tests/test_robot_parts.py` → PASS.
- [ ] **Step 5: Commit** `Verify robot part quotes against captured copies of their sources`.

### Task 4: Sizing through HS robotics simulation, and the gap log

**Files:**
- Create: `hardware/reference_designs/mapping_robot_v0/sizing.py`, `hardware/reference_designs/mapping_robot_v0/GAP_LOG.md`
- Test: `tests/test_mapping_robot_sizing.py` (load `sizing.py` with `importlib.util.spec_from_file_location`)

**Interfaces:**
- Consumes: `hardware_splicer.robotics_simulation.build_robotics_simulation_packet`; `load_parts()`.
- Produces: `TARGETS = {"speed_mps": 0.2, "runtime_min": 60, "duty_cycle": 1.0, "min_speed_margin": 1.5}`
  (the 70 cm door becomes a 350 mm maximum width in `REQUIREMENTS.md`; it is checked by the chassis plan, not here);
  `ROLES = ("drive_motor", "wheel", "lidar", "battery_pack", "dc_dc_converter", "compute_board")`;
  `load_selection(path: Path) -> dict[str, dict]` reading `hardware/reference_designs/mapping_robot_v0/selection.json`
  (`{role: part_id}`) and resolving ids through `load_parts()`;
  `build_payload(parts: dict[str, dict], assumptions: dict) -> dict` (keys are `ROLES`);
  `run_sizing(parts: dict[str, dict], assumptions: dict) -> dict` with keys
  `runtime_min, runtime_margin, required_wheel_rpm, speed_margin, force_margin, passed: bool, reasons: list[str], hs_packet`;
  `class SizingError(ValueError)`.
- HS input shape (verified by running it on 2026-11-06): `{"robotics_project": {"robot_class": "rover",
  "constraints": {"target_speed_mps", "min_runtime_min", "mission_duty_cycle", "payload_kg", "baseline_current_a"},
  "battery": {"nominal_voltage_v", "capacity_mah", "usable_fraction"}, "mobility": {"wheel_diameter_mm"},
  "platform": {"type": "rover", "domains": ["locomotion"], "mobility": {...}}},
  "robotics_actuation": {"actuators": [{"id": "left_drive", "name": "left drive motor", "type": "dc_motor",
  "role": "drive", "free_speed_rpm", "stall_torque_nm", "current_a", "stall_current_a", "voltage_v"}, ...]}}`.
  Outputs read: `runtime_estimate.estimated_runtime_min`, `.runtime_margin`, `drive_kinematics.required_wheel_rpm`,
  `.speed_margin`, `.force_margin`.
- `baseline_current_a` = (LiDAR supply_current × supply_voltage + compute typical_current × supply_voltage
  + 0.5 W microcontroller allowance, labelled typical) ÷ pack nominal voltage ÷ converter efficiency 0.85 (typical).
- `assumptions` holds every non-part figure with a `basis` and `note` (usable_fraction 0.8 typical, payload_kg, chassis
  mass); they go into the result so the report can list them.

- [ ] **Step 1: Write failing tests**:
  - `test_hs_wheel_rpm_for_65mm_wheel`: a two-motor fixture with 65 mm wheels → `required_wheel_rpm == pytest.approx(58.76, abs=0.01)`.
  - `test_refuses_motor_missing_voltage_or_current`: a drive motor lacking `rated_voltage` (listed unconfirmed) →
    `SizingError` naming the fact, because HS would otherwise default it to 6 V / 0.5 A.
  - `test_runtime_below_60_fails`: a 1000 mAh fixture pack → `passed is False` and a reason mentioning runtime.
  - `test_speed_margin_below_1_5_fails`.
  - `test_conflicting_fact_uses_worst_case`: a conflicting `output_free_speed_rpm` (alternatives 100 and 130) sizes on 100.
- [ ] **Step 2: Run** `PYTHONPATH=src $PY -m pytest -q tests/test_mapping_robot_sizing.py` → FAIL.
- [ ] **Step 3: Implement** `sizing.py`. Start `GAP_LOG.md` with columns `date | step | what HS could not do |
  what was used instead | filled on an open PR? | fixed in HS?` and its first row: `robotics_actuation` defaults a DC
  motor's voltage (6.0 V), run current (0.5 A) and stall current (3× run) when absent; guarded in `sizing.py`, not yet
  fixed in HS. Before writing any row, search open draft PRs (`gh pr list --state open --search <topic>`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Run a requirements pass** with class-typical figures (each labelled `typical`): print the minimum wheel
  rpm, stall torque per motor and pack energy (Wh) that meet `TARGETS`; record them in `GAP_LOG.md`'s sibling
  `hardware/reference_designs/mapping_robot_v0/REQUIREMENTS.md` as the search criteria for Tasks 5-8.
- [ ] **Step 6: Commit** `Size the mapping robot through HS robotics simulation and start its gap log`.

### Tasks 5-8: Choose and document each subsystem

Each task is research recorded as library entries, with the same shape and the same acceptance check. Per task:

- [ ] **Step 1: Search** with `ruten_listings.search` (≤ 40 requests per task), using Chinese and English queries; keep
  the shortlist (listing URL, title, variant, price, sold count) in the task's commit message body or a short
  `hardware/reference_designs/mapping_robot_v0/selection/<subsystem>.md`.
- [ ] **Step 2: Pick** one part and one alternative that meet `REQUIREMENTS.md`, preferring parts with a manufacturer
  datasheet or an open-source driver. Record why in the selection note.
- [ ] **Step 3: Write** the library entries (Task 2 shape) with a quote for every published fact, and `unconfirmed`
  rows for everything no source states. Set the chosen part's id for its role(s) in `selection.json`.
- [ ] **Step 4: Capture and check**: `PYTHONPATH=src $PY scripts/capture_robot_part_sources.py` then
  `PYTHONPATH=src $PY scripts/verify_robot_part_quotes.py` → `"pass": true`; and
  `PYTHONPATH=src $PY -c "from hardware_splicer.robot_parts import load_parts; print(len(load_parts()))"` → no error.
- [ ] **Step 5: Commit** `Source the mapping robot <subsystem> parts` (with the shortlist in the body).

Subsystems and selection criteria (beyond `REQUIREMENTS.md`):
- **Task 5, drive:** two gearmotors with quadrature encoders (same model), wheels and a caster. Encoder counts per
  wheel revolution must be derivable (encoder_cpr × gear_ratio).
- **Task 6, LiDAR:** a 2D LiDAR with a documented protocol and an open decoder (vendor SDK or `kaiaai/LDS`), range at
  least 6 m. Candidates to compare, not a preselection: Xiaomi LDS02RR module sold as a spare (ties to Build 2), LDROBOT
  LD06/LD19, YDLIDAR X2, Slamtec RPLIDAR C1.
- **Task 7, power:** a finished Li-ion pack with BMS whose `max_discharge_current` covers both motor stalls plus
  electronics, and a buck converter for the 5 V rail rated above the compute board's `peak_current` + LiDAR.
- **Task 8, compute and IMU:** an on-board computer that runs ROS 2 (Humble or Jazzy) with SLAM Toolbox and Nav2, and
  an IMU module. ROS 2 support must cite the distribution's platform page.

### Task 9: Close test 1 and check in

**Files:**
- Create: `hardware/reference_designs/mapping_robot_v0/report.py`, `hardware/reference_designs/mapping_robot_v0/BUILD1_TEST1.md`
- Test: `tests/test_mapping_robot_sizing.py` (add report tests)

**Interfaces:**
- Consumes: `load_parts()`, `load_selection()`, `run_sizing()`, `verify_quotes()`.
- Produces: `render_report(parts: list[dict], sizing: dict, quote_check: dict) -> str` (Markdown).

- [ ] **Step 1: Write failing tests**: `test_report_lists_every_part_with_listing_and_confidence`,
  `test_report_lists_unconfirmed_facts_and_assumptions`, `test_report_says_designed_not_built` (contains
  "sourced, not measured" and no "verified"/"approved"), `test_report_shows_sizing_fail_reasons`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `report.py`. **Step 4: Run** → PASS.
- [ ] **Step 5: Run sizing on the chosen parts.** If `passed` is False, go back to the failing subsystem's task, choose
  a different part, and repeat; record each swap in the selection note.
- [ ] **Step 6: Generate** `BUILD1_TEST1.md`, update `GAP_LOG.md`, and run the full focused suite:
  `PYTHONPATH=src $PY -m pytest -q tests/test_ruten_listings.py tests/test_robot_parts.py tests/test_mapping_robot_sizing.py`.
- [ ] **Step 7: Commit** `Report Build 1 test 1 parts, sizing and open questions`.
- [ ] **Step 8: Check in with the owner** with the report's summary. Do not push or open a PR without asking; the
  repository is public.
