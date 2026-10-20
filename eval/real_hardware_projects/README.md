# Real-device engineering trial — October 20, 2026

This project suite **replaces trivial synthetic input as the main question**: can Hardware Splicer produce a useful design or repair casefile for real consumer hardware and complete assemblies? These cases contain a real target, a bounded task, documented reference leads, device-specific deliverables and acceptance criteria. They are *not* simplified renamed robot fixtures.

## Casefiles

| Hardware project | Task | HS catalog mapping | Independent catalog verdict | Live model output |
| --- | --- | --- | --- | --- |
| PX4 quadcopter with Pixhawk 6C | Complete non-flight-authorizing assembly design | `bench_power_adapter` | Mismatch; not a substitute for a quadcopter | 10 subsystems, 11-stage sequence, 22 unknowns; BLOCKED |
| Sony PSP-3000 | UMD no-read fault isolation and repair plan | `usb_fume_extractor` | Mismatch | 8 subsystems, 11-stage sequence, 10 unknowns; BLOCKED |
| Steam Deck OLED | SSD failure diagnosis, storage replacement and recovery | `room_display_station` | Mismatch | 7 subsystems, 11-stage sequence, 10 unknowns; BLOCKED |

The live model operator was `copilot-spectator26` with its repo-editing and command-execution tools unavailable. Output JSON lives under `reports/`. The full unmodified HS source-aware planner outputs for this trial were stored under `/tmp/hs_real_<id>.json` on Optiplex. None of these devices was acquired, repaired, manufactured, or tested. The model only saw the curated source claims from the input cases, not a fully ingested manual, schematic or archived source snapshot.

## Actual findings

- **Drone:** HS knew it was an aerial robot but still recommended a bench-power-adapter catalog build. It correctly retained two reference sources and some aerial topology structure; however motor/prop/ESC/BMS sizing, mass budget, current, regulated Pixhawk rails, fabrication drawings and flight-control validation are not completed. The live operator suggested a sensible subsystem plan but incorrectly marked the adapter as relevant. The separate catalog allowlist gate rejects it.
- **PSP:** HS categorized a game-console repair as an airflow controller and proposed a USB fume extractor. The model explicitly rejected that recommendation and produced a revision-aware triage, teardown and replacement-decision outline. It did not establish the actual UMD fault or prove compatibility of a specific donor drive.
- **Steam Deck:** HS returned generic mechatronics and a room display station, with mechanical robot-like gaps irrelevant to an SSD repair. The model recognized the OLED-specific single-sided M.2 2230 requirement and called for backup/diagnostics before replacement. It did not diagnose an SSD, prove a particular replacement compatible, or guarantee recovery.

## Primary documents used as cited leads

- [PX4 Pixhawk 6C hardware](https://github.com/PX4/PX4-Autopilot/blob/main/docs/en/flight_controller/pixhawk6c.md); [PX4 6C wiring](https://docs.px4.io/v1.17/en/assembly/quick_start_pixhawk6c)
- [PSP 300x UMD removal](https://www.ifixit.com/Guide/PSP+300x+UMD+Drive+Replacement/1586); [PSP 2000/3000 compatible drive listing](https://www.ifixit.com/products/sony-psp-2000-3000-umd-drive)
- [Steam Deck OLED SSD guide](https://www.ifixit.com/Guide/Steam+Deck+OLED+SSD+Replacement/168255); [SteamOS recovery instructions](https://help.steampowered.com/en/faqs/view/65B4-2AA3-5F37-4227)

**Source integrity limitation:** these are live public URLs and manually curated claims. The experiment does not prove the operator accessed or verified full documents. Source revisions are not content-addressed snapshots.

## Launch criterion is not a passing test count

A case should only be considered a usable deliverable when it has a verified device identity, source-backed interfaces, concretely compatible part selections, bill of materials or donor alternatives, device-specific procedures, an engineering calculation/review package where applicable, repair acceptance gates, and explicit human/bench verification requirements. None of the three cases meets all those conditions yet. This is a real-target *failure discovery and engineering planning* experiment, not a validated build.

The next work should upgrade actual document ingestion and domain-specific output/validation pipelines instead of adding more synthetic diagnostic fixtures. In particular, fail closed rather than map an unsupported PSP, Steam Deck, or drone into irrelevant generic catalog builds.

## October 20 implementation follow-through: routing repaired and work packages

The production source-aware planner now accepts the opt-in `approved_catalog_build_ids` allowlist from project intake. For these three real devices it is explicitly empty, so the truthful planner skips the legacy catalog planner and leaves architecture `unresolved`, with **no build ID**. This prevents PSP repairs being converted into a fume extractor, Steam Deck service into a display station, and an aircraft project into an unrelated adapter. Existing legacy demo flows remain unchanged where this policy is absent.

A new `real_device_work_package` compiler converts the device-specific advisory reviews into explicit requirements, proposed work steps, unverified part requirements, source leads, acceptance gates and unresolved engineering gaps. The generated JSON packages live under `work_packages/`. All three remain `blocked`: no component compatibility, full-source ingestion, field measurement, physical repair, or fabrication has been established. This is an improvement to the actual real-device project path, **not** a claim of build readiness.

The planner still runs some generic mechatronic topology/analysis checks for consumer devices; those need domain-specific replacement. To produce a build-ready project, next bind document contents and component identifiers to device-specific steps, then exercise verification with real reference schematics or measured parts.
