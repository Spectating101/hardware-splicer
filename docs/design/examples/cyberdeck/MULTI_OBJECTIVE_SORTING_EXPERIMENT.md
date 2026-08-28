# Cyberdeck Multi-Objective Sorting Experiment

> **SYNTHETIC DESIGN TEST ONLY.** No physical hardware, benchmark result, price, mass, runtime, reliability or performance number in this document is a measured claim. The purpose is to test whether one Hardware-Splicer resource pool can produce different defensible architectures when the optimization objective changes while evidence and safety gates remain invariant.

## 1. Question

Can Hardware-Splicer take the **same target machine and same candidate resource pool** and legitimately produce different recommendations for:

- lowest new cash cost;
- maximum useful performance;
- maximum donor reuse;
- maximum portability;
- maximum serviceability / upgradeability;
- minimum integration risk;

without creating a separate cyberdeck-specific planner for each goal?

## 2. Existing HS basis

Current `resource_strategy.v1` already establishes the correct architectural pattern:

> salvage, owned inventory, procurement and designed parts are one resource pool; changing strategy changes scoring policy, not the core engine.

It currently exposes three coarse strategy modes:

- `constrained` / reuse-first;
- `open_procurement` / buy-first;
- `hybrid` / gap-fill.

That is enough to prove **policy-swappable resource selection exists today**. It is not yet enough to claim a mature arbitrary multi-objective optimizer.

## 3. Frozen target

Target is the same DECK-001 class machine:

- x86-class Linux development workstation;
- integrated display and keyboard;
- NVMe;
- networking + >=2 USB ports;
- rechargeable portable power;
- serviceable enclosure;
- evidence-backed donor provenance.

Hard constraints are invariant across all objective profiles:

1. unsafe / failed-evidence resources remain ineligible;
2. unresolved critical power interfaces cannot be authorized;
3. high-speed links cannot be promoted merely because an objective rewards cost/reuse;
4. thermal and mechanical release gates remain required;
5. every selected resource must still cover required capabilities or have an explicit gap-fill path.

**Optimization may change preference. It may not weaken authority.**

## 4. Same candidate resource pool

The experiment assumes one heterogeneous pool, deliberately containing overlapping alternatives.

### Compute candidates

- `C-A donor-mini-pc`: complete known-good x86 mini-PC; moderate performance; native HDMI/USB/network; donor/owned; compact; comparatively low integration burden.
- `C-B donor-laptop-board`: faster donor laptop board; higher performance potential; less convenient mounting/power/display integration; donor/owned.
- `C-C modular-mainboard`: new/procurable documented modular laptop-class mainboard; high performance; high monetary cost; strong serviceability.

### Display candidates

- `D-A raw-donor-panel`: raw laptop LCD; donor/owned; lowest purchase cost; high identity/interface burden until evidenced.
- `D-B donor-portable-monitor`: salvaged portable monitor assembly retaining its validated controller/cable path; donor/owned; moderate bulk; lower electrical integration risk.
- `D-C new-portable-display`: documented HDMI/USB-C portable display; procurable; highest purchase cost; lowest display-integration burden.

### Input candidates

- `I-A donor-usb-keyboard`: complete known-good USB keyboard; donor/owned; easy electrical reuse; moderate packaging burden.
- `I-B keyboard-parts-rebuild`: donor switches/keycaps plus rebuilt controller/mechanics; high reuse and customization; larger integration burden.
- `I-C compact-new-keyboard`: procurable compact USB keyboard; low integration burden; low donor reuse.

### Power candidates

- `P-A old-donor-lithium`: old unknown donor battery; donor/owned; **unsafe hold unless provenance/condition/protection can be evidenced**.
- `P-B documented-pd-powerbank`: known-good documented USB-C PD battery; external/procurable; moderate cost; comparatively low integration burden.
- `P-C custom-pack`: new cells + BMS + charger/power-path design; high modularity and design freedom; highest verification burden.

### Structure candidates

- `M-A donor-case-rework`: heavily reuse donor chassis/case; low cash cost; may constrain layout.
- `M-B generated-simple-shell`: generated serviceable enclosure around validated component envelopes; moderate fabrication burden.
- `M-C modular-rail-chassis`: deliberately modular generated chassis with replaceable bays; higher mass/cost/complexity but strong upgradeability.

## 5. Objective-profile results

These are **selection-behavior expectations**, not measured product rankings.

### Profile A — lowest new cash cost

Priority order:

1. already-owned / donor reuse;
2. minimum procurement;
3. capability coverage;
4. integration burden;
5. performance above minimum requirement.

Expected architecture:

- `C-A donor-mini-pc`;
- `D-A raw-donor-panel` **only if its evidence closes cheaply enough**, otherwise `D-B`;
- `I-A donor-usb-keyboard`;
- `P-B documented-pd-powerbank` rather than unsafe `P-A`;
- `M-A donor-case-rework` where geometry permits.

Important outcome: **lowest cash does not imply reuse the old battery.** The evidence/safety hold dominates the objective score.

### Profile B — maximum useful performance

Priority order:

1. compute headroom;
2. sustained thermal capability;
3. memory/storage expansion;
4. IO capability;
5. monetary cost;
6. reuse.

Expected architecture:

- `C-B donor-laptop-board` if its power/thermal burden is closable and it materially beats C-A, otherwise `C-C modular-mainboard`;
- `D-B` or `D-C` to avoid spending the performance budget on display reverse engineering;
- `I-A` or `I-C`;
- power solution selected from verified load envelope, likely `P-B` only if its PD capability is sufficient, otherwise `P-C` after full engineering;
- `M-B` sized around cooling and ports.

This profile is allowed to buy more and reuse less.

### Profile C — maximum donor reuse

Priority order:

1. retained donor functional value;
2. donor component count / economic value retained;
3. evidence closability;
4. new BOM reduction;
5. integration burden.

Expected architecture:

- `C-B` or `C-A` donor compute;
- `D-A` raw panel if identity/interface evidence closes;
- `I-B` rebuilt donor keyboard;
- `M-A` donor chassis rework;
- **still reject/hold `P-A` unless battery evidence closes.**

This profile produces the most literal splicing but probably the largest engineering workload.

### Profile D — maximum portability

Priority order:

1. mass/volume;
2. energy efficiency/runtime;
3. charger mass;
4. thermal volume;
5. adequate compute;
6. cost/reuse.

Expected architecture:

- whichever compute candidate provides the best **verified performance-per-watt / packaging envelope**, not necessarily the fastest CPU;
- compact validated display path rather than raw-panel experimentation if the controller overhead is larger;
- compact input;
- verified high-energy-density removable power source;
- `M-B generated-simple-shell` tightly fitted to measured envelopes.

Current HS limitation exposed: resource metadata/scoring does not yet have mature first-class mass, volume, energy-efficiency and runtime dimensions.

### Profile E — maximum serviceability / upgradeability

Priority order:

1. independently replaceable modules;
2. standard connectors;
3. documented interfaces;
4. service access;
5. evidence preservation across upgrades;
6. cost.

Expected architecture:

- `C-C modular-mainboard`;
- `D-B`/`D-C` as replaceable display module;
- `I-A`/`I-C` as replaceable USB input module;
- `P-B` as removable externalized power module or a well-documented modular `P-C` design;
- `M-C modular-rail-chassis`.

This is probably the most natural architecture for the lifecycle/passport system because component swaps can selectively invalidate only affected evidence.

### Profile F — minimum integration risk / fastest route to working machine

Priority order:

1. known-good complete subsystems;
2. native manufacturer-validated interconnects;
3. high evidence confidence;
4. low number of custom interfaces;
5. lead time;
6. cash cost / reuse.

Expected architecture:

- `C-A donor-mini-pc` as an intact validated compute island;
- `D-B` or `D-C` with native HDMI/USB-C;
- `I-A` or `I-C` USB HID;
- `P-B documented-pd-powerbank`;
- `M-B simple enclosure`.

This architecture is less exciting as a salvage sculpture but is the most likely first physical cyberdeck benchmark to close quickly and cleanly.

## 6. What changed and what did not

| Objective | Compute preference | Display preference | Input preference | Power preference | Structure preference |
|---|---|---|---|---|---|
| Lowest cash | donor mini-PC | raw donor if evidence cheap, else retained-controller donor | donor USB | documented PD, not unsafe donor cell | donor case |
| Performance | fastest closable x86 board | validated/native path | easy input | load-driven | cooling-first generated shell |
| Maximum reuse | donor board | donor raw panel if closable | donor rebuild | safe new/verified solution | donor case |
| Portability | best perf/W + envelope | compact validated | compact | energy-density/runtime driven | tight generated shell |
| Serviceability | modular board | replaceable module | replaceable USB module | replaceable documented module | modular chassis |
| Minimum risk | intact mini-PC | portable monitor/native HDMI | USB HID | documented PD | simple generated shell |

**The answer changes when the objective changes. The evidence gates do not.**

That is the core flexibility property HS should preserve.

## 7. Current implementation verdict

### Already real in HS

Current `resource_strategy.v1` already demonstrates:

- one common resource representation for owned/salvaged/procurable/designed resources;
- selectable strategy policy rather than separate engines;
- capability coverage;
- confidence/evidence state;
- cost metadata;
- lead-time metadata;
- safety/evidence blocking;
- procurement gap fill;
- constrained vs open vs hybrid selection.

So **the architectural premise passes**.

### Not yet first-class enough

To support the six cyberdeck profiles as an actual deterministic runtime feature, HS needs generic resource/objective dimensions such as:

- `performance_score` or domain-specific performance vectors;
- `power_w` / efficiency / energy demand;
- mass and volume/envelope;
- integration effort;
- interface risk;
- serviceability;
- modularity/upgradeability;
- donor retained value;
- expected validation burden;
- thermal burden;
- lifecycle invalidation cost.

The right next abstraction is **not six more strategy enums**. It is an objective policy such as:

```text
objective_profile:
  hard_constraints:
    min_capability: ...
    authority: fail_closed
    max_mass_g: ...
  weights:
    cash_cost: -0.35
    performance: +0.25
    reuse_value: +0.15
    integration_risk: -0.15
    serviceability: +0.10
```

with transparent per-candidate score contributions.

## 8. Pareto behavior

A single weighted score should not be the only output.

For genuinely competing designs, HS should preserve a small **Pareto frontier** of non-dominated candidates, for example:

- cheapest viable;
- highest performance viable;
- highest reuse viable;
- lowest-risk viable;
- best balanced viable.

Then an agent/human can understand what is being traded away instead of receiving one opaque “best” answer.

A candidate is removed from the Pareto set if another candidate is at least as good on every active objective and strictly better on one, subject to the same hard evidence/authority constraints.

## 9. Frontend implication

This maps naturally into the future HS workbench.

The user should be able to change an objective profile or sliders and immediately see:

- ranked architecture candidates;
- which components changed;
- cost/performance/reuse/risk deltas;
- unresolved evidence burden;
- why a donor is blocked;
- which verification results would change the ranking;
- Pareto alternatives.

Example:

```text
[Cost        ████████░░]
[Performance ██████░░░░]
[Reuse       ███████░░░]
[Portability ████░░░░░░]
[Service     █████░░░░░]
[Risk        low ◄────► high]

Candidate A  balanced
Candidate B  +38% performance / +cost / +thermal burden
Candidate C  +reuse / +evidence work / lower serviceability
```

The 3D assembly view can then update to the selected candidate while the evidence/authority layer remains unchanged.

## 10. Final verdict

**Yes: the HS architecture is naturally compatible with multi-sort / multi-objective hardware planning.**

The current implementation already proves the key design pattern through swappable resource strategy modes. What it lacks is a sufficiently rich generic objective vector and Pareto-ranking layer for dimensions such as performance, portability, serviceability and integration burden.

Cyberdeck is a good benchmark specifically because the six objective profiles above produce visibly different machines from the same candidate pool while sharing the exact same evidence and safety rules.

Do not implement a cyberdeck-specific optimizer. If this becomes runtime work, generalize `resource_strategy.v1` into a transparent multi-objective resource/architecture planner usable by keyboards, cyberdecks, robots, donor conversions and future machine projects.