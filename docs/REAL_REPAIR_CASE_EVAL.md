# Real Repair Case Evaluation

This evaluation checks whether Circuit-AI can do more than run. It runs sourced
repair scenarios through market coverage, repair guide generation,
video/playbook conversion, and board-session evidence task creation.

Run:

```bash
scripts/evaluate_real_repair_cases.py --output-dir eval/real_repair_cases
```

Artifacts:

```text
eval/real_repair_cases/README.md
eval/real_repair_cases/real_repair_case_eval.json
eval/real_repair_cases/cases.json
```

## Current Result

Latest run:

- 7 sourced cases
- 4 solvable now
- 3 assistive only
- 0 not ready
- average workflow score: 0.725

Solvable now:

- Xbox controller thumbstick/stick-drift workflow
- electric toothbrush not charging
- DeWalt cordless drill battery will not charge
- USB fan motor will not spin with intermittent harness

Assistive only:

- laptop will not turn on
- coffee maker not hot enough
- TV has sound but no picture

These assistive-only cases are still useful, but they should not be sold as
complete autonomous repair coverage yet. They require model-specific teardown,
boardview/schematic data, or trained high-voltage/mains procedures.

## Sources Used

- iFixit: Xbox One wireless controller malfunctioning thumbstick
  <https://www.ifixit.com/Troubleshooting/Xbox_One_Controller/Xbox%2BOne%2BWireless%2BController%2BHas%2BMalfunctioning%2BThumbstick/444889>
- iFixit: Laptop will not turn on
  <https://www.ifixit.com/Troubleshooting/PC_Laptop/Laptop%2BWill%2BNot%2BTurn%2BOn/505262>
- iFixit: Coffee maker not hot enough
  <https://www.ifixit.com/Troubleshooting/Coffee_Maker/Not%2BHot%2BEnough/483047>
- iFixit: Electric toothbrush not charging
  <https://www.ifixit.com/Troubleshooting/Electric_Toothbrush/Not%2BCharging/564390>
- iFixit: DeWalt DC970 troubleshooting
  <https://www.ifixit.com/Wiki/DeWalt_DC970_Troubleshooting>
- iFixit: TV has sound but no picture
  <https://www.ifixit.com/Troubleshooting/Television/TV%2BHas%2BSound%2BBut%2BNo%2BPicture/493422>

## What Improved

The repair encyclopedia now has explicit lanes for:

- game-controller input repair
- battery charging gadgets and packs
- simple mains heater appliance triage
- TV/monitor backlight and power-board triage
- laptop charging and power-path triage

Board sessions also create evidence tasks from repair guides, not only from
PCB image analysis. That matters for real practice, where a user has the item in
hand and collects photos, measurements, and outcomes over time.

The frontend now exposes these as a case workbench at:

```text
/cases
```

The workbench starts with three pilot lane packs:

- controller stick/button repair
- battery and charging gadgets
- USB/small motor gadgets

Creating a case from the workbench runs case evaluation, persists a board
session, and sends the operator into the review/evidence loop.

The workbench also has a value-proof check. A run is not treated as valuable
just because the case page or API succeeds. It is scored against:

- persisted session and action queue
- real captures/references
- measurements
- human review/correction
- repair/salvage/reuse outcome
- measured time saved or value recovered
- training/workflow export

API endpoints:

```text
GET /repair/value-trials
POST /repair/value-trials
GET /repair/value-trials/benchmark
```

Verdicts are intentionally strict:

- `plumbing_only`: software flow succeeded, but no real value was proven
- `not_valuable_yet`: some evidence exists, but the case is missing key proof
- `value_likely`: the system guided a real case with evidence and review
- `value_proven`: measured case with captures, measurements, review, outcome,
  and saved time or recovered value

## Honest Limits

Circuit-AI is most launchable now for low-voltage, board-in-hand workflows:
controllers, USB gadgets, battery charging gadgets, small motors, connector
faults, and salvage triage.

It is not ready to claim full autonomous repair for laptops, TVs, or mains
appliances. It can structure the work and identify evidence gates, but the
product still needs model-specific part catalogs, safety packs, boardviews,
schematics, calibration data, and outcome-backed cases before broad customer
claims.
