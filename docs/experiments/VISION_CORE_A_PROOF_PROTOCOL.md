# Vision Core A — Baseline Proof Protocol

**Status:** prepared / not executed  
**Candidate manifest:** `vision_core_a_candidate_manifest.json`  
**Artifact accounting:** `PLATFORM_ARTIFACT_UNITS_V1.md`

## Purpose

Turn the Vision A candidate from manufacturer-declared capability into a revision-bound **validated baseline** that can legitimately seed derivative-reuse experiments.

This protocol does not claim that the current product-line documentation identifies an acquired physical unit. It exists specifically to close that gap.

## 0. Freeze before bench work

Record before testing:

- repository SHA;
- candidate-manifest hash;
- acquired board/package photographs and procurement reference;
- board revision/markings visible to the operator;
- camera-module markings if visible;
- firmware/toolchain versions;
- exact camera-driver release;
- power source used for the bench;
- artifact-unit inventory under `platform-artifact-units-v1`.

If the physical unit differs materially from the candidate manifest, create a new candidate revision before continuing. Do not edit the old record in place.

## 1. Physical-unit identity closure

Required observations:

1. identify the XIAO ESP32-S3 Sense board/revision as far as physical markings permit;
2. identify the attached camera module from physical marking where possible;
3. record runtime sensor identification separately from visual/package identification;
4. compare both against the manufacturer/upstream source record;
5. preserve disagreement rather than selecting the expected OV3660 identity.

**Gate:** camera physical-unit identity is either defensibly resolved or explicitly remains unresolved. An unresolved camera identity blocks downstream optical/model evidence from becoming reusable baseline evidence.

## 2. Deterministic interface/configuration check

Verify the candidate software configuration against the frozen interface contract:

- XCLK GPIO 10;
- SCCB SDA GPIO 40 / SCL GPIO 39;
- data GPIOs 15, 17, 18, 16, 14, 12, 11, 48;
- VSYNC GPIO 38;
- HREF GPIO 47;
- PCLK GPIO 13;
- no assumed PWDN/reset GPIO where the selected upstream XIAO definition uses `-1`;
- 20 MHz XCLK profile for the baseline experiment.

The purpose is not to prove electrical correctness from documentation. It is to ensure the executable candidate matches the contract that will later be bound to physical observations.

## 3. Camera bring-up baseline

Freeze one baseline capture profile before collecting performance data. Initial profile:

- frame: 240 × 240;
- pixel format: RGB565 for the ML-oriented capture path;
- frame buffer: PSRAM where supported by the exact runtime configuration;
- fixed camera configuration/revision recorded in the session.

Run:

1. cold boot and camera initialization;
2. 100 sequential capture attempts;
3. preserve every initialization/capture error;
4. record successful-frame count, failed-frame count, elapsed time and memory observations;
5. retain representative raw frame references/hashes.

**Initial experimental acceptance target:** 100/100 capture attempts complete without a camera reinitialization or process restart. This is a project experiment threshold, not an industry reliability standard.

A miss is retained as baseline evidence and must not be hidden by rerunning until perfect.

## 4. Freeze optical/test conditions

Before using image quality or model results as reusable evidence, freeze and record:

- illumination arrangement and approximate level/setting;
- camera-to-target geometry;
- lens/module orientation;
- background;
- target set;
- focus/exposure configuration if applicable;
- enclosure/mount revision.

These become dependency ids for optical/model evidence. If a derivative changes them, HS must invalidate or block affected evidence.

## 5. Data/model pipeline baseline

The model/training/deployment route remains unresolved in the candidate manifest until selected and frozen.

When selected, record at minimum:

- dataset identity/hash and split policy;
- preprocessing contract;
- model identity/hash;
- training configuration/tool version;
- quantization/deployment transformation if any;
- firmware inference integration revision;
- measured inference latency and memory use on the physical baseline;
- evaluation dataset and metric output.

Do not use training-set performance as model-validity evidence.

## 6. Product-facing baseline functions

For Vision A to count as an application baseline rather than a loose development board demo, demonstrate and retain evidence for:

- operator can start the device/workflow from the documented entrypoint;
- camera capture can be initiated without editing source code;
- captured data can be retrieved through the selected product-facing route;
- selected configuration is persisted or reproducibly reapplied;
- failure state is visible to the operator;
- evidence/session bundle can be exported.

Any feature not yet implemented remains a product blocker rather than being inferred from lower-level library capability.

## 7. Storage/network observations

Where the baseline uses them, separately exercise:

- SD initialization + bounded write/read test;
- Wi-Fi connection/configuration path;
- loss/recovery behavior relevant to the product workflow.

These are separate evidence units so a camera derivative does not automatically invalidate unrelated storage/network proof.

## 8. Baseline physical evidence package

Persist the baseline only after the session is bound to:

- exact project/candidate revision;
- physical unit identity record;
- exact firmware/artifact hashes;
- test-condition ids;
- raw evidence references;
- operator and timestamp;
- explicit `simulated: false` for physical evidence;
- failures/repairs and resulting revision changes.

Use Hardware-Splicer's existing revision/hash-bound physical-evidence path. A baseline passing this protocol does **not** automatically authorize field use or a derivative revision.

## 9. Derivative eligibility

Vision A becomes eligible to seed Vision B/C reuse accounting only when:

1. the artifact-unit inventory is frozen;
2. inherited evidence has explicit dependency coverage;
3. unresolved baseline dependencies relevant to claimed reuse are closed;
4. physical evidence is revision/hash bound;
5. the baseline operator workflow exists;
6. the baseline engineering-hour log is complete enough to support later comparison.

The resulting validated capability manifest is a **new revision** derived from the candidate manifest. Never relabel the candidate file as validated after the fact.
