# Competitive engineering challenge: absorb useful external tools (2026-10-23)

**Intent:** Compete against Flux, Cirkit, Schemr and capable OSS engineering stacks on **delivered hardware engineering outputs**, not number of integrations or claims that we have already lost. Where better tools are available, use their authorized exports in HS. Do not claim vendor APIs, premium access, or a completed head-to-head without actual artifacts.

**Branch:** `agent/open-provider-interop-challenge-20261023`, stacked on [draft #201](https://github.com/Spectating101/hardware-splicer/pull/201). Not merged or deployed.

## What was built

1. Wokwi's documented `diagram.json` v1 is accepted directly through the existing HS Design workspace and Interface Lab file chooser. It detects the **actual JSON envelope**, not a special filename or invented API.
2. The adapter preserves every source part, connection, attributes, virtual `$serialMonitor` endpoint and unknown pin; maps supported ESP32-family, Arduino Nano, DHT22, SSD1306, HC-SR04 and servo *functional-family candidates*, never asserting physical donor identity or exact board revision.
3. HS compares mapped part-family quantities to its compiled BOM. Unmapped parts, wires and mismatches are explicit. **Partial results cannot be promoted into an editable Studio graph.**
4. When **all** parts and pin connections have verified mapping to the *current HS module catalog*, and the greenfield Studio canvas is empty, the operator can explicitly import a draft into the existing pin-level Design Studio. There is no auto-compile, auto-fabricate or evidence promotion. Bench/physical authorization remains independent.
5. A normalized provenance-bearing proposal can be copied from the file chooser without import, with an original file SHA-256 (when browser Web Crypto is available).
6. A reproducible **source-coverage challenge CLI** is included under `examples/integrations/wokwi/challenge.mjs`.

## Real upstream evaluation — no synthetic source substitution

**Real public Wokwi project A:** [AlexGyver/wokwi-plotter diagram.json](https://github.com/AlexGyver/wokwi-plotter/blob/main/diagram.json). Tested using the unmodified publicly posted file in a temporary sandbox, not committed or redistributed.

| Measurement | Result |
| --- | --- |
| Source components / wiring connections | 7 / 15 |
| Components / connections preserved by HS | **7 / 15** |
| HS family mappings | **0 / 7** |
| Pin connections mapped to existing HS catalog | **0 / 15** |
| Verdict | **Partial only**, Arduino Uno/buttons/potentiometers are not represented by HS's current supported import family mapping |

This is a valid interoperability *coverage failure*, not an integration win. Original source content is preserved and never silently discarded.

**Real public Wokwi project B:** [potentialhades/ESP32_Simulation_Sensor_DHT22 diagram.json](https://github.com/potentialhades/ESP32_Simulation_Sensor_DHT22/blob/main/diagram.json). Also tested unmodified in a temporary sandbox.

| Measurement | Result |
| --- | --- |
| Source components / wiring connections | 2 / 5 |
| Components / connections preserved by HS | **2 / 5** |
| HS recognized part families | **2 / 2** |
| HS catalog pin links mapped | **3 / 3 physical** (5 total source links including 2 virtual serial endpoints) |
| Remaining links | 2 virtual Wokwi serial-monitor links (not physical PCB nets); no unmapped physical wire |
| Verdict | **Functional-family mapping complete for this public sensor project**; opt-in Studio draft permitted after cross-check against actual HS catalog, while exact board variant/physical connection safety remains unverified |

Originally the public DHT22 example exposed a missing GPIO14 in HS. We expanded the structured ESP32 DevKit family and its physical pad map based on Espressif-documented GPIO14 availability, then reran the unmodified Wokwi source: **2/2 parts, 3/3 physical pin links mapped**. The two virtual Wokwi serial-monitor connections are retained in provenance but intentionally excluded from the electrical copper draft. This is a measured external-artifact coverage improvement, not certification of a specific donor DevKit PCB.

**Documented-schema control (authored by HS for tests, not a public competitor output):** 3 components (ESP32 + DHT22 + SSD1306), 7 connections, **3/3 recognized and 7/7 pin mapped**. Can become a draft Studio canvas after real catalog pin validation. This proves internal round-trip *structure*, **not simulation**, firmware execution, component delivery or a finished sensor product.

## Repeatable provider challenge

```bash
# Use an export you own or are authorized to inspect:
node examples/integrations/wokwi/challenge.mjs /path/to/diagram.json
# Optional direct comparison to current HS compiled BOM:
node examples/integrations/wokwi/challenge.mjs /path/to/diagram.json /path/to/PROJECT_PACKAGE.json
```

Output includes the source SHA-256, source-part count, preserved-part count, source-wire count, preserved-wire count, mapped part families, mapped pin connections, unresolved fields, Studio import eligibility and (optionally) differences from HS's compiled BOM. No shell access to Wokwi or vendor token needed. CLI exits with an error for malformed sources or lost data, but *a valid partially mapped diagram exits successfully with explicit review status*.

## What competitors can really contribute

| Tool | Verified official interchange route | What HS can currently do | Unverified / blocked |
| --- | --- | --- | --- |
| **Wokwi** | Documented `diagram.json` and `wokwi.toml`; optional `wokwi-cli lint` / simulator | **New actual diagram import**, parity with HS BOM, fully mapped Studio draft; current firmware simulation still requires supported firmware and Wokwi CLI token | Actual cloud simulation and test output not run, standard Wokwi supported hardware does not include all donor DC motors/H-bridges |
| **tscircuit** | Circuit JSON, KiCad, PCB/fabrication formats | Existing live npm 4-part Circuit JSON -> HS canonical review verified on #197 | Full multi-domain power and physical build not proven |
| **Flux** | Manufacturer BOM CSV, IPC-D-356, Gerber and STEP/STL according to official docs | HS already has a generic CSV BOM validator and local STL inspection; *actual Flux exports not tested* | No direct Flux API, project access, or licensed engineering project output verified |
| **Cirkit Designer** | Public diagram/docs/share, circuit and firmware simulation | Candidate input source to inspect when user-owned export is available | No supported Cirkit-native import API confirmed |
| **Schemr** | Public share display, advertised user exports | Browser evaluation recorded in #195; **real user export not obtained** | Account-gated generation; no public API confirmed |

Official references: https://docs.wokwi.com/diagram-format, https://docs.wokwi.com/wokwi-ci/cli-usage, https://docs.flux.ai/reference/data-portability, https://docs.tscircuit.com/.

## Acceptance: not better until outcome evidence says so

- **Immediate:** real third-party projects preserve 100% source parts and connections, disclose exactly what HS cannot map. Done for two public Wokwi inputs; mapping coverage remains poor on one.
- **Interchange quality:** improve *real external project's* mapped coverage without inventing identical physical modules, voltages, donor part identity or simulation claims.
- **Product quality:** run same greenfield sensor system and same salvaged two-motor rover through HS and one competitor's authorized exporter; evaluate completeness, electrical false positives and omissions, mechanical fit, firmware result and actual actions required.
- **Cost/effort:** record human interventions, rework time, real BOM quantities, substitute cost and price provenance. Do not count a manual reformat as autonomous import.
- **Bench and independent outcome:** one verified low-voltage build with source authentication, measured supply and motor currents, driver thermal data, and reproducible test plan. Until then power-on remains blocked.

HS should win by **combining external generation and simulation strengths with genuine hardware reuse and evidence-based engineering resolution**. The present work makes the challenge executable, not won.
