# Derivative Discovery Cycle 001 — Pre-Proof Candidate Pool

**Status:** pre-proof scouting only; no candidate is authorized for fabrication, purchasing, external validation, or commercial claims.

**Snapshot date:** 2026-08-18

**Frozen technical anchor:** `8d687da6e29e110bdc969d9632385f3f31239e5c`

## Why this cycle exists

The purpose is to exercise the commercial conversion logic before spending money: identify product classes that may deserve a controlled derivative experiment after a physically validated capability exists, and kill obviously weak directions early.

This cycle does **not** qualify any candidate under `DERIVATIVE_OPPORTUNITY_SCORECARD.md` because the required physical baseline is not yet closed. Required Gate 1 items therefore remain `OPEN`, so otherwise promising candidates are `HOLD`.

The current authoritative HS state remains:

> **NO DEMONSTRATED SOFTWARE BLOCKER REMAINS ON THE FROZEN HEAD / LIVE-UNSEEN EVIDENCE BLOCKED BY PROVIDER CREDENTIAL**

A repeated live-job check on 2026-08-18 again reached provider-secret detection, then skipped the live replay because no usable Qwen/DashScope Actions credential was available.

## Contamination firewall

The unseen SPI corpus, evaluator, prompt target and answer-bearing engineering choices remain frozen.

Until the first genuine unseen run is sealed:

- do not select a translator;
- do not select a regulator;
- do not select an SPI BOM;
- do not turn a product-market observation into an expected SPI answer;
- do not use the candidates below to tune the live experiment.

SPI/test-fixture product candidates are quarantined as market hypotheses only until the unseen result is sealed.

## Market-signal snapshot

These are directional signals, **not demand validation**.

### Programming / fixture market

- Taiwan marketplace listings show very low-cost CH341A-class SPI/BIOS programmers around roughly NT$70–170 and an EZP2026 listing around NT$197, indicating severe commodity pricing at the low end.
- DediProg positions materially more expensive professional flash-programming equipment: a Taiwan retailer lists the SF100 at NT$12,800, while DediProg lists the SF600Plus-G2 at USD 365.
- Current fixture vendors sell customized PCB/PCBA test fixtures and programming/functional-test tooling rather than only generic programmers. FixturFab, for example, advertises design-file upload, configurable custom fixtures and a four-week delivery model; other engineering vendors explicitly sell PCBA test-fixture development from customer board documentation and requirements.

Interpretation: **generic programmer hardware is a poor first arbitrage target; bounded board-specific programming/test fixtures are more compatible with HS's evidence/revision advantage.**

### Embedded-vision market / platform signal

- Seeed's current XIAO ESP32-S3 Sense documentation continues to support camera capture, microSD and embedded-vision/TinyML use.
- The current getting-started documentation explicitly notes camera-module evolution: OV2640 was discontinued, later Sense units use OV3660, and OV5640 is a compatible replacement. That directly supports HS's existing rule that camera identity/revision must be bound rather than assumed universal.
- Commercial AI/machine-vision inspection is an active product category, but broad inspection systems carry substantial calibration, optics, data and support burden. This favors narrow acceptance-test products for the first derivative experiments.

Interpretation: **the already-preregistered Vision A → B/C family remains a better first controlled arbitrage experiment than a broad "AI inspection platform."**

## Candidate pool

Hypothesis labels are `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`. They are not added into a weighted score.

### D001 — Vision B: bounded package/presence QC checker

**State:** `HOLD — preregistered first derivative`

**Operator/job:** verify presence/absence or gross placement of a bounded object/package under fixed geometry before a non-safety-critical workflow continues.

- capability adjacency: `HIGH`
- evidence reuse potential: `HIGH`
- validation tractability: `HIGH`
- physical complexity: `LOW-MEDIUM`
- safety/authority risk: `LOW` when kept non-safety-critical
- supply/BOM dependence: `LOW-MEDIUM`
- time to first physical evidence: `HIGH`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM` hypothesis
- distribution access: `UNKNOWN`
- differentiation/evidence moat: `MEDIUM-HIGH`
- regulatory/legal complexity: `LOW`

**Cheapest information-gain experiment:** after Vision A physical closure, freeze one fixture/background and a binary presence task, then compare reuse path versus blank slate under the existing protocol.

**Kill condition:** required optical/model retesting approaches blank-slate effort or fixed-condition performance cannot be made repeatable.

### D002 — Vision C: parts counter / simple inventory checker

**State:** `HOLD — preregistered second derivative`

**Operator/job:** count a bounded class of parts in a fixed tray/field of view and export/log the result.

- capability adjacency: `HIGH`
- evidence reuse potential: `HIGH`
- validation tractability: `HIGH`
- physical complexity: `MEDIUM`
- safety/authority risk: `LOW`
- supply/BOM dependence: `LOW`
- time to first physical evidence: `HIGH`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM` hypothesis
- distribution access: `UNKNOWN`
- differentiation/evidence moat: `MEDIUM`
- regulatory/legal complexity: `LOW`

**Cheapest information-gain experiment:** fixed tray, bounded part family, manually counted reference sets, frozen lighting/FOV and repeatability test.

**Kill condition:** occlusion/pose sensitivity forces uncontrolled optical complexity or repeated retraining that erases reuse advantage.

### D003 — Kit-completeness checker

**State:** `HOLD — high-priority backlog`

**Operator/job:** verify that a bounded assembly/service kit contains the required visible items before shipment/use.

- capability adjacency: `HIGH`
- evidence reuse potential: `HIGH`
- validation tractability: `HIGH`
- physical complexity: `LOW-MEDIUM`
- safety/authority risk: `LOW`
- supply/BOM dependence: `LOW`
- time to first physical evidence: `HIGH`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM-HIGH` hypothesis
- distribution access: `UNKNOWN`
- differentiation/evidence moat: `MEDIUM`
- regulatory/legal complexity: `LOW`

**Cheapest information-gain experiment:** one fixed kit layout with deliberately omitted/swapped items and a frozen confusion set.

**Kill condition:** product variation requires bespoke data/calibration per customer to the point that HS reuse is not material.

### D004 — Connector/component orientation checker

**State:** `HOLD — high-priority backlog`

**Operator/job:** detect gross wrong orientation or missing connector/component in a fixed, bounded assembly step.

- capability adjacency: `HIGH`
- evidence reuse potential: `HIGH`
- validation tractability: `HIGH`
- physical complexity: `LOW-MEDIUM`
- safety/authority risk: `LOW-MEDIUM`; must not become a safety certification gate
- supply/BOM dependence: `LOW`
- time to first physical evidence: `HIGH`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM-HIGH` hypothesis
- distribution access: `UNKNOWN`
- differentiation/evidence moat: `MEDIUM-HIGH`
- regulatory/legal complexity: `LOW` if bounded/non-safety-critical

**Cheapest information-gain experiment:** frozen fixture with correct, absent, reversed and visibly mis-seated examples.

**Kill condition:** acceptable error rate requires metrology/3D vision or safety authority beyond the bounded product.

### D005 — Label/marking presence and gross-content verifier

**State:** `HOLD — medium-priority backlog`

**Operator/job:** verify that a label/marking exists and matches a bounded expected class/string pattern under controlled imaging.

- capability adjacency: `HIGH`
- evidence reuse potential: `MEDIUM-HIGH`
- validation tractability: `HIGH`
- physical complexity: `MEDIUM`
- safety/authority risk: `LOW`
- supply/BOM dependence: `LOW`
- time to first physical evidence: `HIGH`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM` hypothesis
- distribution access: `UNKNOWN`
- differentiation/evidence moat: `LOW-MEDIUM`
- regulatory/legal complexity: `LOW`

**Cheapest information-gain experiment:** controlled labels with present/missing/wrong-text/blur/rotation cases; prefer bounded OCR/decoding rather than general document understanding.

**Kill condition:** uncontrolled fonts/reflections/printing variation creates high support/calibration burden.

### D006 — Bench electronics visual evidence station

**State:** `HOLD — medium-priority backlog`

**Operator/job:** capture repeatable before/after or revision-bound bench images for electronics rework, education or lab evidence packages.

- capability adjacency: `HIGH`
- evidence reuse potential: `HIGH`
- validation tractability: `HIGH`
- physical complexity: `LOW`
- safety/authority risk: `LOW`
- supply/BOM dependence: `LOW`
- time to first physical evidence: `HIGH`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM` hypothesis
- distribution access: `MEDIUM` hypothesis
- differentiation/evidence moat: `MEDIUM` if tightly integrated with HS evidence lineage
- regulatory/legal complexity: `LOW`

**Cheapest information-gain experiment:** revision/hash-linked capture workflow with fixed stand/lighting and reconstruction test.

**Kill condition:** standalone value is indistinguishable from a phone/camera plus folders unless HS evidence binding materially improves the job.

### D007 — Board-specific low-volume programming fixture

**State:** `HOLD — quarantined until unseen SPI result is sealed and physical SPI capability exists`

**Operator/job:** repeatedly program a specific known board/device family with fixture identity, interface limits, revision evidence and a deterministic acceptance sequence.

- capability adjacency: `UNKNOWN` until SPI baseline closes
- evidence reuse potential: `HIGH` hypothesis
- validation tractability: `HIGH` for a known device/board family
- physical complexity: `MEDIUM`
- safety/authority risk: `MEDIUM`
- supply/BOM dependence: `MEDIUM`
- time to first physical evidence: `MEDIUM`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM-HIGH` hypothesis
- distribution access: `LOW-MEDIUM` hypothesis
- differentiation/evidence moat: `HIGH` if revision/evidence handling beats generic tooling
- regulatory/legal complexity: `LOW-MEDIUM`

**Cheapest information-gain experiment:** only after SPI evidence closure, adapt the validated capability to one distinct known target/revision and measure retained/invalidated evidence.

**Kill condition:** outcome collapses into a generic programmer with no material evidence/revision advantage.

### D008 — Board-specific functional-test / pogo fixture

**State:** `HOLD — promising but later`

**Operator/job:** provide repeatable electrical/functional access and a bounded test sequence for one PCBA family.

- capability adjacency: `MEDIUM-HIGH` hypothesis
- evidence reuse potential: `MEDIUM-HIGH`
- validation tractability: `HIGH`
- physical complexity: `MEDIUM-HIGH` due mechanics + board interfaces
- safety/authority risk: `MEDIUM`
- supply/BOM dependence: `MEDIUM`
- time to first physical evidence: `MEDIUM`
- development-cost measurability: `HIGH`
- customer value: `HIGH` hypothesis
- distribution access: `LOW-MEDIUM` hypothesis
- differentiation/evidence moat: `HIGH`
- regulatory/legal complexity: `LOW-MEDIUM`

**Cheapest information-gain experiment:** one low-voltage board with frozen test points and acceptance sequence; avoid production-volume claims.

**Kill condition:** bespoke mechanical work dominates enough that reusable engineering capability does not reduce marginal effort.

### D009 — Vision training station as a packaged educational/lab kit

**State:** `HOLD — productization of baseline, not a derivative proof substitute`

**Operator/job:** guided capture, labeling, deployment and bounded inference exercises on a known embedded-vision unit.

- capability adjacency: `HIGH`
- evidence reuse potential: `HIGH`
- validation tractability: `HIGH`
- physical complexity: `LOW-MEDIUM`
- safety/authority risk: `LOW`
- supply/BOM dependence: `MEDIUM` because camera/board revisions matter
- time to first physical evidence: `HIGH`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM` hypothesis
- distribution access: `MEDIUM` hypothesis
- differentiation/evidence moat: `MEDIUM`
- regulatory/legal complexity: `LOW`

**Cheapest information-gain experiment:** first complete Vision A proof; then determine whether packaging/workflow adds enough value beyond commodity dev boards and tutorials.

**Kill condition:** the offering is merely repackaged public examples with no meaningful evidence/reproducibility advantage.

### D010 — Reel/spool component counting assistant

**State:** `HOLD — lower priority`

**Operator/job:** estimate/count visible components or reel state for low-stakes inventory assistance.

- capability adjacency: `MEDIUM-HIGH`
- evidence reuse potential: `MEDIUM`
- validation tractability: `MEDIUM`
- physical complexity: `MEDIUM-HIGH`
- safety/authority risk: `LOW`
- supply/BOM dependence: `LOW`
- time to first physical evidence: `MEDIUM`
- development-cost measurability: `HIGH`
- customer value: `MEDIUM` hypothesis
- distribution access: `UNKNOWN`
- differentiation/evidence moat: `LOW-MEDIUM`
- regulatory/legal complexity: `LOW`

**Cheapest information-gain experiment:** compare fixed-view count error against manual reference on several reel geometries before any custom mechanics.

**Kill condition:** geometry/occlusion requires x-ray or specialized industrial imaging rather than reusable Vision Core capability.

## Explicit kills

### K001 — Generic low-cost USB SPI/BIOS programmer

**Decision:** `KILL`

Reasons:

- mature commodity listings already compete near NT$100–200;
- weak evidence/revision moat when sold as generic hardware;
- support burden across devices can become large;
- pursuing it before the frozen SPI experiment would invite answer contamination;
- likely competes on price rather than HS capability accumulation.

The existence of high-end professional programmers does not rescue the low-end generic-product thesis; it instead suggests differentiation must come from bounded workflow, target-specific fixtures, evidence or professional capability.

### K002 — Universal flash programmer

**Decision:** `KILL as first derivative`

Reasons:

- broad target/support matrix;
- high firmware/device-definition/support burden;
- established professional vendors;
- weak fit with a first controlled adjacency experiment;
- difficult to separate platform reuse from endless compatibility engineering.

Could be reconsidered only after repeated validated programming capabilities exist; no current justification.

### K003 — General-purpose "AI visual inspection box"

**Decision:** `KILL as first product`

Reasons:

- task definition is too broad;
- optics, lighting, model/data and calibration burden are customer-specific;
- acceptance criteria are not bounded without a specific inspection job;
- support burden can erase apparent platform reuse;
- encourages marketing claims ahead of evidence.

Use narrow presence/count/orientation jobs instead.

### K004 — Camera-based people/behavior counter

**Decision:** `KILL`

Reasons:

- weak adjacency to HS's physical-engineering validation thesis;
- privacy/legal burden adds no useful platform evidence;
- crowded generic vision use case;
- does not leverage the semiconductor/test-fixture wedge.

### K005 — "Custom test fixture for anything"

**Decision:** `KILL as a product definition`

Reasons:

- this is a consultancy scope, not a bounded first product;
- requirements, mechanics and test coverage can vary arbitrarily;
- cannot preregister one reusable acceptance boundary;
- would hide whether HS actually creates reuse economics.

Instead test board-specific fixture families one bounded capability at a time.

## Pre-proof priority queue

No item below is authorized yet. This ordering only says which hypotheses are worth attempting first **after** prerequisites close.

1. **D001 Vision B — package/presence checker** — already preregistered and strongest controlled derivative.
2. **D002 Vision C — parts counter** — already preregistered and gives a distinct inference/output task.
3. **D003 kit-completeness checker** — strong adjacency and deterministic physical test with modest new hardware.
4. **D004 orientation checker** — good bounded manufacturing/lab value hypothesis.
5. **D007 board-specific programming fixture** — high strategic fit, but quarantined until unseen + physical SPI evidence is sealed.
6. **D008 board-specific functional-test fixture** — potentially high value but more mechanical/interface complexity.
7. **D005 label/marking verifier**.
8. **D009 packaged Vision training station**.
9. **D006 bench evidence station**.
10. **D010 reel/spool counter**.

## What would actually advance the queue

### Before any Vision derivative can qualify

- Vision A physical unit acquired;
- exact board/camera identity closed;
- baseline revision/hash/evidence inventory frozen;
- Vision A capture/deploy/inference path physically closed;
- acceptance conditions frozen;
- authority state explicit.

### Before any SPI-derived product can qualify

- genuine frozen unseen provider run sealed, pass or fail;
- actual candidate/result preserved;
- physical SPI protocol executed;
- physically validated capability manifest frozen;
- no answer-bearing market/product work leaked into the unseen experiment.

### Before economics can be claimed

- reuse prediction frozen before derivative-result leakage;
- blank-slate comparator launched under the preregistered firewall;
- active human hours and direct development cash recorded;
- physical retest burden recorded;
- authority violations measured rather than assumed;
- product COGS kept separate from development economics.

## Cycle-001 conclusion

The first useful commercial finding is already negative:

> **Do not use HS to manufacture generic commodity hardware merely because it can.**

The more defensible factory wedge is **narrow, target-specific physical tooling or inspection products where a validated capability/evidence base materially reduces the engineering delta and where correctness has a frozen, reproducible acceptance test.**

The strongest first controlled family remains the already-preregistered Vision A → B/C sequence. The strongest later semiconductor-adjacent family is board-specific programming/test fixtures, not a universal low-cost programmer.

## Sources used for directional market scouting

Market observations are a snapshot only and must not be promoted to willingness-to-pay evidence.

- Seeed Studio Wiki, "Getting Started with Seeed Studio XIAO ESP32-S3 Series" — https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/
- Seeed Studio Wiki, "Camera Usage in Seeed Studio XIAO ESP32S3 Sense" — https://wiki.seeedstudio.com/xiao_esp32s3_camera_usage/
- FixturFab, custom PCB test fixtures — https://fixturfab.com/
- Microelectronicos, PCBA test fixtures — https://www.microelectronicos.net/testfixtures/
- Zeus Design, PCB test jigs / test-jig development — https://zeusdesign.com.au/pcb-test-jigs-why-they-matter-for-production-quality
- Ruten Taiwan flash programmer search snapshot — https://www.ruten.com.tw/find/?q=flash%20%E7%87%92%E9%8C%84&sort=ords%2Fdc
- 100Y Taiwan, DediProg SF100 listing — https://www.100y.com.tw/product/66923
- DediProg, SF600Plus-G2 — https://www.dediprog.com/product/SF600Plus-G2
