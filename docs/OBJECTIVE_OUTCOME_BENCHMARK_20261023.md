# Engineering outcome benchmark — real donor rover (2026-10-23)

**Purpose:** Prevent self-congratulation from tool-integration counts and test passing. Evaluate whether the actual generated engineering output represents the user's physical goal.

## Input and evaluator

Identical example input on both revisions: `examples/intakes/splice_robot_drive_brief.json`. Its inventory explicitly lists **left and right salvaged DC gear motors**, with distinct names and declared 6 V ratings. The goal requests the motors for a robot drive base. Evaluation is from raw JSON artifacts, not UI badges.

Procedure (in an isolated HS Python environment with optional hardware/LLM integrations disabled):
```python
import json
from pathlib import Path
from hardware_splicer.project_intake import splice_and_build_from_intake
x=json.loads(Path('examples/intakes/splice_robot_drive_brief.json').read_text())
result=splice_and_build_from_intake(x,out_dir='/tmp/hs-rover',export_gerber=False)
package=json.loads(Path('/tmp/hs-rover/PROJECT_PACKAGE.json').read_text())
graph=json.loads(Path('/tmp/hs-rover/build_compilation/build_graph.json').read_text())
# Count the source motor parts, compiled dc_motor_3v_6v nodes, and BOM rows independently.
```

## Hard comparative results

| Criterion | PR #197 base (before quality gate) | This branch (after quality gate) | Desired |
| --- | --- | --- | --- |
| Input motors in source intake | 2 | 2 | 2 |
| Compiled motor nodes | **0** | **0** | 2 |
| Motor units in BOM | **1** | **1** | 2 |
| Input→graph count detection | No source inventory report | **blocked**, code `intake_selected_quantity_underrepresented` | Accurate |
| Reported motor deficit | No explicit intake quantities | 2 missing graph nodes, 1 missing BOM unit | 0 |
| Software job success | yes | yes | Not a meaningful success metric |
| Build-ready | false | false | Only after verified power, wiring, bench and mechanical checks |

**Conclusion:** Engineering **output accuracy has not improved** on this example. Source-count defect detection improved (unreported → explicitly blocked), but the model still generates the wrong motor topology and BOM. The PR is not proof of greater design capability.

### Root-cause trace

1. `resolve_parts_to_modules(normalized_parts)` independently resolves both motors correctly as separate `dc_motor_3v_6v` instances.
2. The completed `SPLICE_PLAN.json` keeps only one of those resolved motor rows, and the `robot_drive_base` recipe generates no motor graph nodes, even while `SALVAGE_BOM.json` lists one motor.
3. The compiled graph also introduces a DC 12 V barrel, 5 V USB and MP1584 without a demonstrated physical donor connection matching the user's constraints. Those are *proposed topology*, not proven donor measurements.

The **next engineering fix** must preserve two motor identities through plan/graph/BOM and route driver channels with explicit pin/interface evidence. Do not arbitrarily duplicate one motor row, assert a measured supply, or bypass the existing authorization gate to make the score look green.

## Objective release scorecard

These are proposed acceptance tests; they are **not achieved** by #197 or this change.

| Gate | Pass requirement |
| --- | --- |
| Source-to-project quantity fidelity | 100% of intended selected hardware represented in graph and BOM on 5 fixed cases including two-donor-motor rover |
| Power and polarity | Zero asserted operating power sources/rails unsupported by declaration, verified catalog data or measurement; unknowns stay blocked |
| Multi-domain coherence | Every required mechanical/electrical/firmware interface traced to an inspected source and an explicit constraint or missing-evidence task |
| Safety-critical false-ready | **Zero** failures in red-team cases that must remain unpowered/blocked |
| First-use completion | At least 4 of 5 external test users understand blockers and produce a coherent next action without coaching |
| Physical proof | At least one independently measured and successfully built low-voltage device with recorded power, behavior, tolerances and failures |
| Comparative value | Same tasks, hardware and review standard against pre-integration HS and a capable external tool; independently record errors, omitted requirements, task time, repeatability and operator effort |

Software CI and successful file exchange are *prerequisites*, **not substitutes** for any of these acceptance outcomes.

## What this quality branch changes

- Reads real `PROJECT_INTAKE.json` when assembling a package.
- Compares selected multi-instance inventory against both compiled graph and BOM (includes a BOM-only motor absent from graph).
- Blocks package/build/fab release while such an undercount is unresolved.
- Never assumes every unused inventory part must be installed; unselected quantities become review warnings.
- Unit + integration tests cover two motors lost, valid two-motor representation, spare inventory, explicit quantities and package verdicts.

**Measured quality gain is detection of this specific defect, not correction of design generation.** Keep this branch in draft until a corrected rover output and a second greenfield negative-control case prove actual improvement.


---

## Follow-up engineering outcome correction — dual-motor rover

**Code:** `fix/rover-two-motor-outcome-20261023`, based on the intake integrity PR #198. This section supersedes the earlier "not achieved" motor-quantity row **for the explicitly offline salvage rover test only**.

The previous quality audit isolated two independent defects:

1. `merge_truth_rows` dropped multiple physically distinct inventory rows with the same module ID when `instance_id` was absent. The legacy rover carried just one `dc_motor_3v_6v` into `SPLICE_PLAN.json`.
2. `robot_drive_base`'s catalog recipe included an L298N driver but **zero motor load nodes**. It also inserted an undeclared 12 V barrel/MP1584 and USB path.

### Same-input artifact benchmark

The `examples/intakes/splice_robot_drive_brief.json` original example was run against the earlier branch and this correction, each with `export_gerber=False` and no real physical devices.

| Measured item | Before outcome repair | After outcome repair | Assessment |
| --- | ---: | ---: | --- |
| Source motor units | 2 | 2 | Same original input |
| Resolved donor motor instances | 1 | **2** | Actual identity preservation improved |
| Compiled motor nodes | 0 | **2** | Actual circuit representation improved |
| Motor units in project BOM | 1 | **2** | Quantity fidelity improved |
| L298N output ports connected to motor loads | 0 | **OUT1–OUT4** across 2 motor nodes | Proposed two-channel wiring included |
| Motor control signals from ESP32 | Existing IN1/IN2 only | **IN1–IN4** | Both driver control channels represented |
| Unsupported fixed 12 V barrel, USB and MP1584 source nodes | 3 | **0** | No automatic fictional supply assertion |
| Source→graph→BOM quantity gate | Blocked | **Clear** | Specific count defect resolved |
| Electrical power verified | No | **No** | Remains unresolved |
| Software job `ok` | True (despite incorrect topology) | **False** (incomplete unpowered design) | Not an overall success-rate gain |
| Physical build-ready | False | **False** | Correctly held |

The correct display label for a motor terminal connected to L298N OUT2/OUT4 is a **switched H-bridge terminal, not common ground**; this was also repaired in the bring-up wiring narrative.

### Scope and remaining engineering blockers

**This is evidence of better generation fidelity on one real previously failing software case**, not proof the rover can be built, powered or driven. The unmeasured donor power source has intentionally been omitted; the resulting design is electrically incomplete, with two electrical errors (power connections to ESP32 and L298N). No battery-to-buck design, shared-ground plan or enable/driver-thermal path has been independently specified or validated. The example input contains a declared 7.4 V battery constraint, **not** an identified, measured donor supply. A 6 V motor is not thereby approved for 7.4 V operation.

The compiler may produce KiCad documents and wiring proposals; these are **not** power-on instructions.

The follow-up needs actual power-source characterization, L298N losses/current/thermal assessment versus measured motors, enable/control and MCU power checks, mechanical load and firmware verification. Independent physical validation remains required. Until that evidence exists, `build_ready` must remain false.

**Negative control:** `examples/intakes/sensor_logger_brief.json` remained successful, did not acquire motor nodes, and retained clear source-quantity reconciliation. No third-party head-to-head comparative improvement is claimed.
