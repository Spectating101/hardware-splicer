# Physical Operator Control Plane

Hardware Splicer does not treat a 3D printer as the end state. The printer is the first concrete physical operator beneath a generic mission-controlled fabrication boundary.

The control plane is intended to support additive fabrication, CNC/laser tools, firmware programmers/debug probes, programmable bench instruments, and eventually robot/workcell execution without giving an AI agent raw machine authority.

## Authority classes

Every declared operator action is one of four classes:

| Class | Meaning | Agent may dispatch? | Human grant |
| --- | --- | --- | --- |
| `observe` | Read status/identity/measurements without causing intended actuation | yes | no |
| `prepare` | Stage, preflight, configure, or generate a server-side plan without intended actuation | yes | no |
| `risk_reduce` | Pause, cancel, stop, or disable an already active physical process | yes | no new grant |
| `actuate` | Move, heat, cut, flash, energize, print, or resume physical execution | only after approval | exact one-shot grant |

`FabricationMission.accepted` is **not** physical authority. Physical actuation has a separate human decision.

## Exact-plan approval

The server creates a `PhysicalExecutionPlan` containing:

- project id;
- mission id;
- registered operator id and kind;
- declared action and action class;
- canonical JSON payload;
- SHA-256 of that payload.

`PhysicalPlanGrantStore` binds the human approval to the SHA-256 of the entire execution plan. Changing an artifact, target, fixture, material/profile binding, workcell state, or any other payload field creates a different plan and invalidates the approval.

The grant is consumed before dispatch. If the machine acts but the transport response is lost, HS cannot automatically replay the same authority.

## Immutable executable artifacts

Agents do not provide raw physical commands at dispatch time. `PhysicalArtifactRegistry` stores server-generated executable artifacts privately and exposes only descriptors/hashes.

Current artifact classes:

- `gcode` — additive printer job;
- `machine_job` — CNC/laser toolpath or machine job;
- `firmware` — compiled image for a programmer/debug probe;
- `motion_plan` — server-generated robot/workcell trajectory;
- `measurement_recipe` — bounded server-generated instrument/output recipe.

Compatibility is enforced before an actuation plan can be requested. A firmware image cannot be used as a CNC job, for example.

## Operator classes

### Additive printers

Concrete live-capable adapters exist for OctoPrint and Moonraker/Klipper. Geometry is sliced through a deterministic slicer boundary, with geometry/profile/G-code hashes captured in a `SlicerReceipt`. Raw printer endpoint/credentials stay server-side.

### CNC and laser

The generic contract is present now: `status`, `preflight`, `stage`, `start`, `pause`, `cancel`, `resume`. `start`/`resume` are actuation. No live CNC or laser network driver is configured by this PR; those should be introduced behind a private server handle and exercised in simulation/dry-run before real hardware.

### Programmers/debug probes

The contract distinguishes target inspection/staging from `flash`. Firmware must be a registered immutable artifact. A future OpenOCD/picotool/AVR adapter should use a fixed argv shape, no shell, server-owned executable/configuration, and verification readback where the tool supports it.

### Bench instruments

Passive status/read operations are observational. Configuration without enabling output is preparation. Enabling an output is actuation and should bind to a server-generated measurement/output recipe. `disable_output` is risk-reducing.

### Robot/workcell

Motion plans are immutable artifacts. Workcell state/fixture/tool identity should be included in the approved bindings. `execute_motion`/`resume_motion` are actuation; `stop` is risk-reducing. No live robot driver is enabled by this PR.

## Agent workflow

`AgentPhysicalWorkbench` is the bounded agent-facing seam:

1. list safe registered operators;
2. list safe registered physical artifacts;
3. perform non-actuating operations;
4. request an actuation using an exact compatible artifact;
5. receive a persistent pending approval request;
6. wait for a human operator-token decision;
7. execute only after that request holds the exact one-shot grant.

The workbench cannot register an operator, set a URL, read credentials, mint a grant, or submit arbitrary raw machine commands.

## Canonical HTTP projection

`/v1/fabrication/*` is mounted on the canonical product API. The routes exist for discovery but fail closed with HTTP 503 unless `app.state.physical_workbench` is configured by the server.

Agent-side routes cover safe discovery, non-actuating operations, approval request creation/status, and execution of an already human-approved request. Approve/reject reuse the existing `X-HS-Operator-Token` human identity boundary.

There is deliberately no HTTP route for:

- registering machines;
- changing endpoints or credentials;
- registering arbitrary executable artifacts;
- minting a physical grant directly;
- sending raw G-code/toolpath/SCPI/robot commands.

## MCP direction

The canonical FastAPI OpenAPI surface already exposes these routes to generic backend discovery. A dedicated bounded task manifest can project them later without duplicating authority logic.

The eventual physical-fabrication MCP surface should remain a projection of canonical HTTP truth, not a second driver implementation.

## Physical truth

A completed machine job does not establish engineering correctness.

`physical_correctness` therefore remains `UNPROVEN` until admissible physical evidence is returned and evaluated through the appropriate HS evidence/review path.

A printer reporting `completed`, a programmer reporting `verified`, or a robot reporting `trajectory complete` proves only that the operator reported that execution outcome. It does not prove fit, safety, system-level function, or the user's intended result.

## Next concrete driver gates

The generic contract is deliberately ahead of the live driver count. The next adapters should be added only with a real benchmark and should preserve the same authority classes:

1. programmer/debug probe (fixed-argv OpenOCD/picotool-style adapter, target identity + verify receipt);
2. read-first bench instrument/SCPI adapter, with any source/output enable remaining human-gated;
3. CNC/laser controller in simulator/dry-run first, then a real registered machine;
4. camera/vision observation as read-only physical evidence;
5. robot/workcell simulator before any live motion driver.

The objective is not to make every machine autonomous. It is to let the mission runtime select and coordinate specialist physical operators while HS preserves intent, provenance, evidence and authority across the whole fabrication process.
