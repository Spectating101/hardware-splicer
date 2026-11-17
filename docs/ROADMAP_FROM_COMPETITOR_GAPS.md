# Roadmap from competitor gaps — v1.0.2 (internal)

**Historical scope:** the July v1.0.2 launch plan below describes the narrow SPI/donor pilot. The broader [engineering mission](HARDWARE_SPLICER_MISSION_FREEZE.md) governs current backend work. The [November 17 research assessment](#november-17-2026-practical-build-from-parts-assessment) below evaluates that broader objective; the old numerical competitor scores are not current measurements.

**Purpose:** Prevent panic-building after competitor comparison. **Only** items that strengthen layer 5 (bring-up proof).

**Inputs:** [`COMPETITOR_SCORECARD_v1.0.2.md`](COMPETITOR_SCORECARD_v1.0.2.md) · [`COMPARISON_DEMO_CASE_robot_repair_cafe.md`](COMPARISON_DEMO_CASE_robot_repair_cafe.md)

---

## Do now (≤1 week)

| Item | Why | Owner |
|------|-----|-------|
| **CI badge fix** | README badge red because legacy `verify` job fails; Splice v1 bar is green | Split workflow or badge to `splice-v1` job only |
| **Competitor pack** | Internal alignment before external talk | ✅ this doc set |
| **One trusted reviewer** | External proof = one conversation with release zip | Founder |
| **Claims discipline** | [`CLAIMS_BOUNDARY.md`](CLAIMS_BOUNDARY.md) on all outbound copy | Founder + agents |

**Do not** start outreach blast or grant apps until badge + one conversation.

---

## Do only if comparison exposes weakness

| Gap | Competitor pressure | Priority | Notes |
|-----|-------------------|----------|-------|
| UI job failure copy | Blueprint UX | P1 | User-visible errors — not Flux parity |
| BOM LCSC/JLC enrich | Flux/EasyEDA sourcing | P2 | Engine hooks exist |
| Wiring Mermaid in UI | Blueprint presentation | P2 | Data already in package |
| Cleaner `git clone` on lab WSL | Repro story | P2 | Tarball worked; network hung |
| 5-min demo video | Blueprint onboarding | P2 | Script exists: `DEMO_5_MIN_UI.md` |

---

## Do not (competitor traps)

| Trap | Why stop |
|------|----------|
| Browser ECAD editor | Flux bucket — **build from scratch**; prefer KiCanvas / KiCad MCP / circuit-json **embed** |
| Production autoroute default | Quilter bucket |
| Native Windows installer | Not wedge; WSL2 sufficient for v1 |
| Public multi-tenant SaaS | Different product + liability |
| “Beat Flux” repositioning | [`FLUX_TARGET.md`](FLUX_TARGET.md) is engine aspiration, not v1 SKU |
| Full fleet cluster Splice installs | Distraction from one good alien proof |
| More 40-page strategy docs | Comparison pack is enough |
| GDELT / data-lab mixed into Splice launch | Separate system |

---

## Integration (not competition) — later

| Partner class | Integration idea |
|---------------|------------------|
| **Quilter** | Export carrier constraints → route → re-import for DRC + gates |
| **JITX** | High-end path — different buyer |
| **Schematic AI (SINA, etc.)** | Intake adapter → existing splice spine |
| **KiCad** | Stay substrate; contribute upstream if useful |

---

## Success criteria for this sprint

```text
✓ Team can explain layer-5 wedge in one sentence
✓ Sample zip used in comparison, not hypothetical outputs
✓ No new roadmap items unless they strengthen gates/package/handoff
✓ One conversation scheduled or completed with release link
```

---

*Timebox: 1 day for docs; stop after one reviewer conversation.*

## November 17, 2026: practical build-from-parts assessment

The user wants an engine that helps produce useful devices such as drones and cyberdecks from obtainable materials, available inventory or reusable donor equipment. Their current deliverables remain digital: concrete construction packages, representative models and engineering checks. Frontend work is deferred.

This review inspected **20 repositories**, using current GitHub metadata, exact default-branch commit pins, README files, selected implementation/documentation files and four repository asset trees. It is a source-level fit assessment, not a comparative runtime benchmark. No third-party software was installed or executed, no supplier quote or checkout was performed, and no physical work occurred. Direct GitHub search/API and web discovery supplied the signals; no authenticated GitHub Signals subscription feed is claimed.

### What to reuse and where we fit

| Projects | Source-backed observation | Implication for HS |
| --- | --- | --- |
| [atopile](https://github.com/atopile/atopile), [tscircuit](https://github.com/tscircuit/tscircuit), [circuit-synth](https://github.com/circuit-synth/circuit-synth) | Code-defined circuits, reusable blocks, part selection or KiCad/manufacturing interchange. Specific features differ between projects. | Reuse specialist design tools and the existing Circuit JSON/KiCad paths. Another general PCB compiler would duplicate substantial work. |
| [Nimbalyst Electronics](https://github.com/nimbalyst/nimbalyst-electronics), [Circuitiny](https://github.com/mfranzon/circuitiny) | Both document agent-assisted design, simulation and firmware workflows. Nimbalyst also documents evidence, freshness and review mechanisms. | These are close workflow comparisons. HS cannot claim uniqueness from agent tools or artifact evidence alone. A complete device built around an actual parts situation is the more useful acceptance target. |
| [InvenTree](https://github.com/inventree/InvenTree) | Inventory, supplier/manufacturer parts, BOM/build workflows and a REST API. | First connector candidate for available quantities, missing materials and traceable supplier identifiers. HS should contribute engineering decisions while consuming this stock information. |
| [Part-DB](https://github.com/Part-DB/Part-DB-server) | Electronics inventory, BOM allocation, supplier information providers, API and documented MCP access. | Alternative inventory source. Its provider model is useful; adding an MCP endpoint by itself would not complete the engineering workflow. |
| [KiCost](https://github.com/hildogjr/KiCost), [Ki-nTree](https://github.com/sparkmicro/Ki-nTree) | Distributor-aware BOM costing and supplier-to-inventory/KiCad identity mapping respectively. | Review before writing another component-price collector or part-creation bridge. Exact API/server compatibility and quantity/currency semantics need evaluation. |
| [WireViz](https://github.com/wireviz/WireViz), [InvenTree WireViz plugin](https://github.com/inventree/inventree-wireviz) | Connector/cable descriptions generate harness diagrams and a harness BOM; an inventory/report bridge already exists. | Strong candidate for actionable wiring handoffs from HS source-bound interfaces. WireViz expects an already specified harness and does not determine full-system electrical compatibility. |
| [Mainboard Terminal](https://github.com/penk/MainboardTerminal), [HandiPi](https://github.com/brickbots/HandiPi), [Pilet](https://github.com/soulscircuit/pilet) | Actual cyberdeck/portable-computer mechanical and electronic assets. Mainboard Terminal includes editable STEP; HandiPi includes a BOM and build tour. | Evaluate these as architectures and source assets for the existing cyberdeck objective. Their source completeness and component generations must be checked before adaptation. |
| [Framework Laptop 13 documentation](https://github.com/FrameworkComputer/Framework-Laptop-13), [OpenMower](https://github.com/ClemensElflein/OpenMower) | Manufacturer-documented module reuse and a supported-donor appliance conversion. | Useful patterns for identifying a donor, matching its documented interfaces and designing the missing integration pieces. This supports a more defensible reuse path than assigning functions to an unidentified board. |
| [PX4](https://github.com/PX4/PX4-Autopilot), [ArduPilot](https://github.com/ArduPilot/ardupilot) | Maintained flight software ecosystems; PX4 explicitly documents SITL and vehicle integration. | Future actual-firmware simulation candidates after selecting a supported controller/firmware combination. They do not validate the current INAV review configuration or its selected board. |
| [akcli](https://github.com/tipoLi5890/akcli), [kdif](https://github.com/0x12net/kdif) | Current default-branch heads match the two existing HS-approved pins. | No upstream update is needed for the existing diagnostic/diff adapters. akcli's other documented commands, including component search, require separate adapter review before HS uses them. |

The two closest workflow projects also illustrate the sourcing gap. Nimbalyst's [quote implementation](https://github.com/nimbalyst/nimbalyst-electronics/blob/d00fc14aacd05e8bdf493189fd4c080b2da33d32/src/fab/quote.ts) calculates an offline prototype estimate; its supplier searches do not establish availability. HS's current `salvage_bom_estimate.py` similarly uses catalog hints and prototype fallback prices. A useful improvement is fresh, exact procurement evidence attached to the same design revision.

Existing open builds do not automatically provide a complete purchase/build package. HandiPi's [BOM](https://github.com/brickbots/HandiPi/blob/9cb9c32a14060ed7b145196f1ef0f36c87e8b424/docs/BOM.md) explicitly leaves some hardware and wiring unspecified. Its build documentation describes a tour. Mainboard Terminal's default head is from 2022; useful CAD can remain valuable while its supplier links and component availability need refreshing. Pilet describes a gradual asset release. No present-day stock, price or complete-device reproducibility claim is made for these references.

License metadata also needs source inspection. OpenMower's API returns `NOASSERTION`, but its root license is CC-BY-NC-SA-4.0; linked software and hardware have separate scopes. Mainboard Terminal's root license is MIT while its README also mentions CC-BY-SA-4.0, leaving file-level redistribution scope to resolve. Ki-nTree documents API-version and parameter-unit compatibility requirements. These are integration-review findings, not reasons to automatically install, vendor or reject an entire ecosystem.

### Assessment against the practical objective

HS already has project/source lineage, bounded native CAD/electrical checks, digital drone generation, inventory-constrained planning, donor evidence checks and repeatable artifact packages. The unresolved problem is connecting them into a complete device outcome across domains. The cyberdeck work remains incomplete, and salvage planning may still end with generic module identities and estimated prices.

The useful product promise to demonstrate is: **given a device goal and an actual materials situation, explain what to keep, buy and make, resolve their interfaces, and produce matching construction files and instructions.** Evidence and job infrastructure support that outcome; their presence is not a measurement of device completion. This positioning is an inference from the reviewed sources and existing HS capabilities, not a proven competitive advantage.

Three backend steps follow directly from that gap:

1. **Connect exact material identity to inventory and procurement evidence.** Review a read-only InvenTree/BOM bridge first, retaining HS's current project/source model. Each line needs a manufacturer/model or unambiguous material specification, required and available quantity, condition/verification state, source, dated price/stock evidence and identified gaps. Preserve unknowns. Regional shipping, minimum order quantities, substitute interfaces and missing screws/cables belong in the decision; an advertised price alone cannot close it.
2. **Finish the existing cyberdeck objective through this flow.** Compare obtainable modules and documented donors, evaluate the cost of required adapters, retain source-backed electrical and mounting dimensions, and produce a consistent enclosure/wiring/software package. Mainboard Terminal, HandiPi and manufacturer CAD are candidate inputs, not predetermined selections. Assembly instructions and material completeness must match the chosen design. Continue the user's digital-only scope.
3. **Produce construction-level connector and harness outputs.** Review WireViz and its existing InvenTree bridge before implementing a duplicate exporter. Derive connector identities, pin assignments, wire specifications and the harness BOM from HS's verified project facts. An unknown donor connector remains unresolved; diagram generation cannot determine its pinout.

A first comparative acceptance should use the same cyberdeck requirements, declared materials and source evidence across approaches. Compare completeness of exact materials, unresolved interfaces, cost basis, enclosure fit and usable build outputs. Do not rank projects by GitHub stars or by incompatible internal test counts. No such head-to-head execution was performed during this research.

### Own GitHub follow-up

Remote main remains at the previously integrated `38dbad2b`. The newer [keyboard-salvage draft #342](https://github.com/Spectating101/hardware-splicer/pull/342) contains two commits beyond the locally integrated `f2310b96`: `e30b7a50` and `70a1e8de`. The new work includes a compact junction, source-bound nominal switch plates and corrected switch-aperture cut geometry. It is relevant to keyboard reuse for a cyberdeck and warrants selective review when that device objective needs it. The current draft remains a conditional reference design with unresolved real-donor/physical limitations. It was not merged in this research pass.

The [normalized discovery feed](../examples/github_signals/build_from_parts_candidates_20261117.json) validates with the existing HS signal importer: 18 new discovery-only candidates plus the two unchanged existing approved adapters. The [research snapshot](status/generated/github-build-research-2026-11-17.json) records all 20 source pins, metadata, selected-source identities, asset inventories, comparison findings and upstream PR heads. Backend runtime and frontend files were not changed by this research.
