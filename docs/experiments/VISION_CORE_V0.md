# Vision Core V0 — Platform-to-Derivative Experiment

**Status:** experiment definition only; not yet a validated platform.

## Goal

Use one embedded-vision base to create three distinct products while measuring whether Hardware-Splicer preserves valid engineering evidence and materially reduces marginal engineering effort.

First family:

1. **Vision A:** TinyML / embedded-vision training station.
2. **Vision B:** package/presence QC checker for bounded non-safety-critical workflows.
3. **Vision C:** parts counter / simple inventory checker.

The experiment succeeds only if reuse is measured; three working demos alone are insufficient.

## Candidate base

Initial reference class: **Seeed Studio XIAO ESP32-S3 Sense**, subject to exact physical identity verification.

This class is attractive because current official materials provide camera-capable ESP32-S3 hardware, microSD and wireless support, TinyML examples, and open hardware resources including schematics, KiCad libraries, pinout and mechanical files.

## Identity rule

Do not encode a universal camera-sensor identity into the core. Official documentation reflects camera-module evolution across revisions. The platform must therefore bind:

- exact board revision;
- exact installed camera identity;
- interface/driver compatibility;
- image format/resolution used;
- mechanical and optical assumptions;
- firmware/runtime version.

A camera/module change is a revision event whose affected evidence must be reevaluated.

## Reusable capability contract

Vision Core V0 should treat these as explicit capability/evidence classes:

- compute identity and memory configuration;
- imaging identity and capture configuration;
- local storage / dataset capture path;
- model artifact and deployment metadata;
- illumination geometry/state;
- mechanical camera/lighting/base interfaces;
- operator configuration surface;
- deterministic verification;
- physical test evidence.

Illumination and optics are part of the sensing condition. Changes that can affect model validity must invalidate the relevant evidence instead of being treated as cosmetic enclosure changes.

## Variant A — training station

Adds education/lab workflow such as guided capture, labeling, deployment, bounded inference and reproducible exercises.

This becomes the baseline platform only after the physical imaging/deployment/inference path is exercised and recorded.

## Variant B — package/presence checker

Adds a fixed fixture/background, bounded pass/fail task, logging and optional non-safety-critical alert output.

The experiment asks how much of Variant A's compute, imaging, lighting, configuration and evidence stack remains valid.

## Variant C — parts counter

Adds a fixed tray/field of view, counting/detection task and result export/logging.

Again, measure inheritance rather than merely reporting model accuracy.

## Evidence transition

Before deriving B or C, freeze the baseline evidence inventory. Every inherited item must be classified as one of:

- `RETAINED_VALID`
- `INVALIDATED_BY_CHANGE`
- `NOT_APPLICABLE`
- `NEW_REQUIRED`

Copying a component, file or model never automatically grants retained-valid status.

## Controlled module-revision test

After one derivative is validated, change one relevant camera/module revision if available and measure whether HS selectively invalidates affected evidence.

Likely affected classes include driver compatibility, framing/field of view, image quality, model validity, mounting and illumination interaction.

The desired behavior is selective evidence invalidation: neither blind reuse nor unnecessary blank-slate retesting.

## Measurement

Use `PLATFORM_DERIVATIVE_EVIDENCE.template.json` and `platform_derivative_metrics.py`.

Precommitted initial targets for at least two derivatives:

- engineering reuse ratio >= 0.70;
- evidence reuse ratio >= 0.65;
- marginal engineering ratio <= 0.40;
- invalidation precision >= 0.95;
- authority violations = 0.

These are experimental thresholds, not external industry standards.

## What this one family can establish

Research evidence:

- evidence survival across product variation;
- invalidation under module revision;
- agent behavior with incomplete/conflicting identity;
- relationship between file reuse and actual engineering-time reuse;
- physical retest compression and its limits.

Commercial evidence:

- marginal engineering cost across three verticals;
- reusable embedded-vision platform economics;
- component-revision/sourcing flexibility;
- support/calibration burden versus reuse benefit.

## Stop/revise conditions

Reconsider the platform thesis if repeated derivatives show low engineering-time reuse, widespread hidden optical/model invalidation, near-blank-slate physical retesting, or support/calibration burden large enough to erase the apparent leverage.
