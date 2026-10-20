# Hardware Splicer: From digital design to reality

**This is an operator handoff, not a released machine. Physical printer, donor acquisition, electrical connections and tests remain BLOCKED.**

## Actual tested fabrication profile

- Test printer choice: Original Prusa MK4S, 0.4 mm nozzle. NOT detected on Optiplex.
- Genuine PrusaSlicer 2.9.2, manufacturer PrusaResearch.ini derived 0.20 mm structural profile and Prusament PLA settings.
- Actual SolidCraft editable case model, separate base/lid STL, 3MF and PartCAD two-part BOM enclosed.
- Offline G-code: MK4S_CASING_UNAPPROVED.gcode. It is not approved for a physical machine.
- Estimated time: 3h 13m 39s, PLA: 74.1 g, layers: 175.
- Real G-code contains start purge near Y = -4 mm, beyond nominal bed rectangle. Explicitly verify this is intended and supported by the chosen actual printer before using the file.
- No observed power supply, motor, scanner harness or independent emergency stop. Do not guess any pinout or wire colors.

## Agent's engineering feasibility assessment

The supplied receipts support a tested digital CAD/slicer package for a hypothetical stationary tabletop label indexer, not a fitted or electrically commissioned machine. No donor, printer, validated controller or independent stop is present. All physical work remains conditional on acquisition, verified measurements and authorization; unverified safety, wiring and connection claims are rejected.

## Print the actual casing with a verified machine

### 1. Identify the exact tested native SolidCraft base and lid, PartCAD assembly, slicer project and generated G-code by revision or checksum before preparing a print.

REQUIRED EVIDENCE: Traceable artifacts matching the supplied slicing receipt; the receipt alone does not establish possession of those files.

STOP IF: Artifacts are unavailable, revisions differ or the tested toolpath cannot be identified.

### 2. Acquire authorized access to a physical printer and verify its actual model, firmware, build surface, nozzle and operating instructions. Treat the MK4S name in the G-code as a profile identifier only.

REQUIRED EVIDENCE: Physical printer identification and documented configuration matching the intended slicer profile.

STOP IF: Printer access or authorization is absent, or any configuration remains unverified.

### 3. Open the identified project in the appropriate slicer and compare its settings and preview against the tested package before making changes.

REQUIRED EVIDENCE: Recorded comparison with the reported 74.1 g estimate, 3h 13m 39s estimate and 175 layer changes; explain differences rather than treating estimates as physical measurements.

STOP IF: Material, geometry, profile or toolpath differences lack an explanation.

### 4. Review all six reported extrusion moves outside the nominal bed, including the Y = -4 mm coordinates, against the actual machine's documented purge behavior and travel limits.

REQUIRED EVIDENCE: Machine-specific documentation and toolpath review establishing whether each reported move is an intended supported purge operation.

STOP IF: Any move remains unexplained, exceeds supported travel or risks contact; revise and re-slice before proceeding.

### 5. Inspect both objects and every start, purge, end and travel sequence in the toolpath preview. Check placement, first layer, supports, adhesion provisions and clearance.

REQUIRED EVIDENCE: Reviewed base bounds of X 19.0–119.0 and Y 67.5–142.5 mm and lid bounds of X 131.0–231.0 and Y 67.5–142.5 mm, together with the complete path on the verified printer profile.

STOP IF: Any object or auxiliary path is unsupported, colliding or outside the verified operating envelope.

### 6. Prepare a separate tolerance coupon representing the skirt fit, boss holes, selected fastener features and port interface; slice it using the verified material and printer configuration.

REQUIRED EVIDENCE: Coupon geometry linked to the 0.35 mm design skirt gap and actual proposed mating features; documented material settings.

STOP IF: The coupon does not represent critical interfaces or the material configuration is unknown.

### 7. After explicit print authorization and the printer's prescribed preflight, print and measure the coupon, then revise the CAD and re-slice if required.

REQUIRED EVIDENCE: Actual coupon dimensions, mating observations and recorded acceptance criteria.

STOP IF: Fit requires force, holes or bosses fail, adhesion fails or the printer behaves unexpectedly.

### 8. After accepting the coupon and reviewing the final revised toolpath, obtain authorization for the first-article base and lid print and follow the machine's operating procedure.

REQUIRED EVIDENCE: Accepted coupon, final artifact identifiers and completed machine-specific preflight.

STOP IF: Required reviews or authorization are missing, or printing exhibits lifting, collision or extrusion problems.

### 9. Cool and remove the first article according to the printer instructions, then measure and trial-fit it before installing electronics.

REQUIRED EVIDENCE: Actual enclosure dimensions, lid engagement, boss integrity and donor clearance records.

STOP IF: Cracking, distortion, interference or inadequate clearances prevent acceptance.

## Mechanical assembly and fit validation

### 1. Measure acquired donor components, connectors, cable bends, label stock and the complete motion envelope before adapting the enclosure.

REQUIRED EVIDENCE: Actual dimensional records and component identification; the 100×75×35 mm case is only a test design.

STOP IF: A fit decision depends on a listing, photograph or assumed donor dimension.

### 2. Define a stable stationary tabletop layout with guarded pinch points, accessible scanner presentation and an accessible independent stop.

REQUIRED EVIDENCE: Measured mechanism envelope, stability assessment and documented access and guarding requirements.

STOP IF: The unit can shift or tip, moving parts remain accessible or stop access is obstructed.

### 3. Adapt mounting interfaces and verify the 14×7 mm port, 2.4 mm walls and lid against measured connectors, loads and required clearances.

REQUIRED EVIDENCE: Updated CAD using actual measurements and supported mounting requirements.

STOP IF: Connectors interfere, cables lack strain relief or structural adequacy is unestablished.

### 4. Print and measure the representative fit coupon through the gated printer route before accepting the skirt, holes or bosses.

REQUIRED EVIDENCE: Physical coupon results for the selected material and printer, including the nominal 0.35 mm skirt gap.

STOP IF: Fit, retention or fastener engagement fails the defined criteria.

### 5. Select screws and retention hardware from measured hole geometry, boss depth, material and mounted loads; trial-fit with all power disconnected.

REQUIRED EVIDENCE: Verified screw diameter, length, engagement and clearance from electronics and moving parts.

STOP IF: Screws bottom out, split bosses, protrude into hazards or require an assumed size.

### 6. Evaluate ventilation and component temperature limits before closing the enclosure, then verify temperatures during authorized commissioning.

REQUIRED EVIDENCE: Actual component dissipation and temperature specifications followed by measured operating temperatures.

STOP IF: Thermal limits are unknown or temperatures exceed accepted limits.

### 7. Complete first-article assembly inspection and verify label travel and service access using only a documented safe manual procedure or subsequently authorized bounded motion.

REQUIRED EVIDENCE: Recorded fit, alignment, clearances, guarding, stability and cable-routing acceptance.

STOP IF: Binding, rubbing, exposed pinch points or unresolved mechanical interference remains.

## Connect and commission real hardware only after evidence

### 1. Acquire and identify candidate scanner, motion components, controller and power equipment without energizing unknown parts. Keep vendor listings separate from physical inventory.

REQUIRED EVIDENCE: Actual part identifiers, condition inspection and documentation tied to each acquired item.

STOP IF: Identity, condition or ownership and use authorization remain unresolved.

### 2. Quarantine the scanner's cut cable. Establish its interface through exact-model documentation and qualified inspection; do not infer USB, serial or keyboard-wedge wiring from colors or connector appearance.

REQUIRED EVIDENCE: Verified interface specification and an intact documented replacement cable or otherwise professionally validated interface assembly.

STOP IF: Any conductor function, voltage, interface type or cable compatibility is unknown.

### 3. Only after acquiring an intact scanner verified to be a compatible USB peripheral, connect its documented intact USB cable to a verified Linux host USB port for enumeration and scan capture. Use this scanner, not the cut cable or bare NAS board, for the initial input test.

REQUIRED EVIDENCE: Exact scanner USB documentation, intact cable inspection, compatible host port and authorization for this connection; the supplied host receipt shows no recognized scanner.

STOP IF: The scanner needs an undocumented adapter or supply, enumeration is abnormal or the cable is cut or damaged.

### 4. Characterize the actual recovered motor, driver, sensors and transmission using documentation and appropriate qualified measurements before selecting an electrical architecture.

REQUIRED EVIDENCE: Verified motor type, ratings, winding or interface information, driver compatibility and sensor specifications.

STOP IF: Any motor lead, drive rating, sensor pinout or operating limit would require guessing.

### 5. Select an actual validated controller and compatible documented low-voltage power supply, then produce a reviewed harness diagram with protective devices, connectors and strain relief.

REQUIRED EVIDENCE: Verified voltage, current, polarity, isolation and protection requirements for every connected component; documented controller interfaces.

STOP IF: Supply suitability, harness protection or any connection is unverified; do not treat the bare NAS board as a controller.

### 6. Design and install an independently effective hardware stop that removes or inhibits hazardous motion without depending on host software, scanner events or application firmware.

REQUIRED EVIDENCE: Reviewed stop architecture appropriate to the measured mechanism, including stored energy, stopping behavior and prevention of automatic restart.

STOP IF: The stop exists only in software or its independent effectiveness has not been established.

### 7. With power isolated, have the completed assembly inspected against the verified diagram and applicable equipment procedures before requesting energization authorization.

REQUIRED EVIDENCE: Recorded harness, polarity, protection, insulation, connector and strain-relief checks performed by a competent person.

STOP IF: Any discrepancy remains or inspection would require an undocumented connection assumption.

### 8. After explicit energization authorization, commission the validated controller and motion system under the reviewed procedure, with the mechanism guarded and the independent stop accessible. Test stop effectiveness before barcode-driven operation.

REQUIRED EVIDENCE: Approved commissioning limits, actual electrical observations and successful independent-stop and restart-prevention tests.

STOP IF: Unexpected motion, heating, current, voltage, stop failure or automatic restart occurs.

## Scanner and motion firmware validation

### 1. Implement scanner capture and logging on the verified Linux host using synthetic barcode input first, then the conditionally connected intact USB scanner.

REQUIRED EVIDENCE: Observed scanner enumeration and interface mode, captured sample scans and verified log records.

STOP IF: Input handling assumes an absent serial device, unknown scanner protocol or validated NAS operation.

### 2. Define barcode validation, duplicate handling, queue limits, index completion and fault states, with motion disabled by default.

REQUIRED EVIDENCE: Explicit state transitions and tests for malformed input, repeated scans, timeouts and disconnects.

STOP IF: A scan can bypass validation, create unbounded queued motion or trigger automatic recovery into motion.

### 3. Run bounded motion tests against a virtual controller using declared simulation limits and fault injection before enabling physical outputs.

REQUIRED EVIDENCE: Recorded tests for command bounds, sensor failures, communication loss and restart behavior; simulation values clearly distinguished from measured physical limits.

STOP IF: Commands exceed configured bounds or simulated success is used as proof of physical safety.

### 4. Bind the application to the selected controller only after its protocol, measured travel limits, sensors and electrical commissioning gates are verified.

REQUIRED EVIDENCE: Documented controller API and actual calibrated direction, travel and indexing parameters.

STOP IF: Firmware requires guessed pins, motor ratings, steps per distance or unverified sensor behavior.

### 5. Validate the independent hardware stop during authorized physical tests, including host failure and loss of application communication; require deliberate re-arming after a stop.

REQUIRED EVIDENCE: Observed stopping behavior and restart prevention independent of application execution.

STOP IF: Motion depends on a software stop, continues beyond accepted limits or resumes automatically.

### 6. After all physical gates and operating authorization are satisfied, test one bounded label index per accepted scan and reconcile each scan, movement result and log entry.

REQUIRED EVIDENCE: Actual end-to-end records showing indexing accuracy, fault handling and successful stop tests.

STOP IF: Labels misindex, logs disagree with outcomes or any mechanical, thermal or electrical gate fails.

## Unresolved components and safety gates

- Acquired and identified physical donor components; none are established as present.
- Exact tested CAD, assembly, slicer and G-code artifacts with traceable identifiers.
- Authorized physical printer access with verified model, firmware, plate, nozzle and material configuration.
- Machine-specific resolution of the six outside-nominal-bed extrusion moves and Y = -4 mm purge path.
- Measured printed tolerance coupon and accepted first-article enclosure.
- Intact documented USB scanner and compatible cable, or another fully verified scanner interface.
- Characterized motor, transmission, driver and position or label sensors.
- Validated controller; the bare NAS board is unverified.
- Compatible documented low-voltage supply, protection and reviewed harness.
- Independently effective hardware stop and verified restart prevention.
- Measured mounting hardware, guarding, strain relief and thermal provisions.
- Explicit fabrication, energization and motion authorization at the applicable gates.

## What passed vs what did not

Passed: source-linked native CAD; two closed STL meshes; two-part 3MF; actual PartCAD BOM; native PrusaSlicer G-code; independent footprint, printer profile and thermal command scan.

Passed in fake transport only: stage exact G-code with print=false; unapproved print-start is denied.

Passed virtually only: motion/barcode simulation adversarial suite. Physical motion, scan identity and independent hardware stop remain unverified.

NOT DONE: physical printing, test-fitting to real donors, electrical wiring, firmware flash, energized motion, independent stop trial or validation of any actual recycled machine.
