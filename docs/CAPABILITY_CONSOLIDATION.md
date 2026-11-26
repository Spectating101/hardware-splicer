# HS capability consolidation: which module does which job (2026-11-26)

Read this after `docs/CAPABILITY_MAP.md` (generated). The map says what each module is and how it is reached; this page
says, for each job where several modules compete, which one to use and what the others are. It was written by reading
the modules' own descriptions, imports and tests on branch `agent/capability-consolidation`; regenerate the map before
trusting any number here.

**What was checked, and what was not.** Docs in this repo were written during the work, not after it, so they are
claims. Checked in the code: every count, status and reach figure (the import graph), test and importer counts, the
planner chain (each imports the next), that the toolbelt is served by `mcp_server` and by `product_api` (and through it
`backend_mcp_server`), the `*_compat` history (`git log -S`), and the five new tools (tests). Not checked: the one-line
summaries of what a module does, which come from its own docstring. Before relying on one, read the module.

**Agents: do not read the area pages or 130 docs to find something. Run**
`PYTHONPATH=src python -m hardware_splicer.capability_map find <words>` (or the `hs_capability_search` tool) and
`... show <module>`. Each answer is a few lines.

## 1. The measurement, corrected

The first map (2026-11-26, earlier the same day) matched modules by bare file name and counted only three entry points.
It reported 21 modules reached by the toolbelt, 321 by REST and 262 engineering modules reached by nothing. Resolved by
full dotted name, with the package's lazy re-exports, every console command, helper scripts run by path and tools the
toolbelt runs in the native interpreter:

On 2026-11-26, before wiring: 453 modules shipped, 117 reached only from scripts, 8 runnable only, 37 only from tests, 2
from nothing (deleted, §4). On 2026-11-27, after §5: **467 shipped, 140 in declared research lines, 0 undecided**; the
remaining 8 unshipped modules are plumbing (script and test helpers). Regenerate the map for current numbers.

Copy-paste is not the problem: identical helper functions total under 500 lines of 176,000. The problem is **parallel
subsystems for the same job** and an agent tool list that called only 9 modules. §2 names the canonical module per job.

## 2. One job, one canonical module

| Job | Use | The others, and what they are |
|---|---|---|
| Agent tools | `engineering_toolbelt` (33 tools; one envelope; every run recorded on an objective project) | `mcp_server` (`hs-mcp`) serves the toolbelt plus the historical compile-engine tools; `backend_mcp_server` (`hs-backend-mcp`) generates MCP tools from every REST operation, toolbelt included. **New agent tools go in the toolbelt only**, never as hand-written wrappers in either server. |
| HTTP API | `product_api` (`hs-serve`; builds on the engine app in `api`, adds 61 routers) | `extended_product_api` is a compatibility alias. |
| Programmatic (no HTTP) | `sdk` (compose, salvage, verify; 23 tests) | `workshop_operator` composes vetted capabilities for SPI checkpoints only (script). |
| An agent's work on one objective | `objective_project` (append-only step ledger behind the toolbelt) | Different grain from the next row; not a duplicate. |
| An engineering design and its revisions | `machine_project` + `project_store` (the spine; 44 and 112 tests, 62 and 75 importers) | `digital_project`, `mission_store`, `project_thread_store`, `engineering_plan_store` persist their own records beside a project. **Open decision:** an objective project should be able to point at a machine project id; today the two never meet. |
| Boards from real KiCad parts (new work) | `component_board_pipeline` → `kicad_component_board` (`hs_component_board`) | The older catalogue path (`build_compiler` → `netlist.*` → `pcb.*`, served by `sdk`, `api` and `mcp_server` compile tools) builds boards from HS's own module catalogue; keep it for module-carrier boards. Placement: `_pcbnew_helpers.place_free_footprints` is still a script, not a tool. |
| Review a KiCad schematic | `kicad_design_review` (any schematic, from KiCad's netlist; `hs_review_kicad_schematic`) | `netlist.erc` and `pcb.safety_rules` check HS's own netlist IR; `electrical_design` is the pin/net/power-domain model; `integrations.engineering_review` runs kicad-happy as a sidecar; `pcb.kicad_cli_erc` runs KiCad's ERC. Different inputs, not copies. |
| Review a device plan (board + sensors + case) | `device_engineering` (now `hs_device_review`) | `device_plan` builds the plan it reviews; `device_lab` packs a plan into a build folder (runnable only). |
| Identify a salvaged chip | `part_lookup` (KiCad symbol library, offline; now `hs_identify_part`) | `board_vision_salvage`, `donor_capture` work from photos. |
| Which junk gives which modules | `junk_catalogue` (`hs_junk_lookup`, device level) | `salvage_plan`, `salvage_intelligence`, `salvage_bridge` work at board level on a known donor. |
| Sizing | `drive_sizing`, `arm_actuator_sizing`, `propulsion_check`, `energy_budget`, `battery_runtime`, `prop_static` (all tools now) | `engineering_analysis` runs bounded calculations inside the planner chain. |
| Mechanical strength | `mechanical_cad_fem` (STEP → Gmsh → FEM; `hs-mechanical`) | `mechanical_fem` (small linear-tet solver), `mechanical_quadratic_fem`, `mechanical_fem_crosscheck`, `mechanical_cad_convergence` are its chain: second order, independent check, mesh sensitivity. Tool: `hs_fem_screen` (native venv). |
| Arm kinematics | `robot_arm_kinematics` on `robot_arm_design` (PyBullet; `hs_arm_kinematics`) | `arm_actuator_sizing` (tool) sizes the actuators; `motion_sweep` (tool) checks link collisions on a URDF. |
| Engineering plan for a project | `guided_engineering_planner` → `complete_engineering_planner` → `engineering_planner` | A layered chain (each wraps the next), not three planners. `engineering_status` is the single status and next-action surface. |
| Circuit topology from intent | `circuit_synthesis.planner.plan_circuit` (typed semantic selection over 8 bounded planners) | Served over REST (`api`, `semantic_circuit_api`), `sdk`, and `hs_plan_circuit`. |
| Text LLM calls | `integrations.llm_text_client` (cache, usage ledger, provider chain) | `qwen_text_client`, `agy_text_client`, `copilot_cli_text_client` are its providers; the billing guard is `qwen_model_policy`. New code calls `llm_text_client` only. |
| Benchmarks | `engine_benchmark` scores toolbelt runs on varied briefs | `robot_guidance_benchmark`, `robotics_benchmark`, `source_agnostic_benchmark`, `electronics_foundation_benchmark`, `robot_arm_reference_benchmark` are research instruments run from scripts; merge their scoring into `engine_benchmark` only when one is next used. |
| Prior art | `hs_prior_art_search` (HS's own docs and modules, landscape register, GitHub, BoardRepo) | `landscape_watch` (weekly job) feeds it; `github_data_sources` is a runnable helper. |

Research lines that are deliberately not shipped and should stay out of agents' way: `keyboard_splice*` and its pcbnew
helpers, `spi_*` and `cleanroom_*` (SPI-flash virtual lab), `codex_astra_*` (one investigation's adjudication),
`restoration_*` (video/board restoration assistant, mostly tests-only). The map marks them script or tests-only.

## 3. Wired into the toolbelt on 2026-11-26

Five tools, each a thin adapter over an existing, tested module, so the engine calls what HS already had instead of
new code:

| Tool | Module | Closes |
|---|---|---|
| `hs_capability_search` | `capability_map` | Agents search HS's own modules (status, tests, importers) instead of reading docs |
| `hs_device_review` | `device_engineering` | Thermal, RF, power, fit and printing review (benchmark gap) |
| `hs_identify_part` | `part_lookup` | Identify salvaged chips from their marking (benchmark gap) |
| `hs_battery_runtime` | `battery_runtime` | Duty-cycled battery life with cited self-discharge |
| `hs_prop_hover` | `prop_static` | Propeller thrust and power from UIUC measured data (needs `HARDWARE_SPLICER_UIUC_PROPDB`) |

## 4. Deduplicated on 2026-11-26

* Deleted `engineering_action_revalidation_compat` and `engineering_plan_store_audit_compat` (252 lines). Both were
  monkeypatch installers written on 2026-08-04 and never imported by any commit. Their guards are native now:
  `engineering_action` revalidates in `prepare_engineering_action` and marks the wrapper installed, and
  `engineering_plan_store` refuses rewritten audit history itself (`_assert_audit_history_not_rewritten`). The other
  eight `*_compat` installers are imported by their target modules (re-homed when the package went lazy on 2026-11-19).
* Identical helpers now have one home: `circuit_synthesis.common` (`dedupe`, `float_or_none`) for the motor-driver
  planner, `integrations.qwen_text_client.extract_json_object` for three Qwen integrations, and
  `operator_identity.header_token` for four REST routers.
* Left alone on purpose: `text_usage_ledger` / `vision_usage_ledger` (74% shared) sit on the LLM billing path; merge
  them only with the billing guard's tests in view. The remaining identical helpers (`_to_dict`, `_current_level` and
  similar across the `*_authority` and `robotics_*` modules) are under 10 lines each.

## 5. Connected on 2026-11-27: the tools now feed each other

The toolbelt has 33 tools. Each one below wraps an existing, tested module, and each chain passes one tool's output to the
next as a project file, so work on an objective builds on itself instead of starting over:

| Chain | Tools, in order | Modules |
|---|---|---|
| Parts on hand to a buildable device | `hs_what_can_i_build` → `hs_device_review` (applies the planner's own repair suggestions to a broken spec and returns `suggested_spec`) → `hs_device_lab` (plan, review, case, firmware, status ladder on the project) | `device_lab`, `device_suggestions`, `device_engineering` |
| Arm | `hs_size_arm_actuators` → `hs_arm_kinematics` (same cited servos and stall share; URDF on the project; PyBullet FK/IK/workspace; closes the workspace finding only when the sampled reach covers the requirement) → `hs_motion_sweep` | `arm_actuator_sizing`, `robot_arm_design`, `robot_arm_kinematics`, `motion_sweep` |
| Printed part | `hs_rover_chassis` (or any STEP/STL) → `hs_fem_screen` (full field saved on the project, summary to the agent; optional mesh study) | `mechanical_cad_fem`, `mechanical_cad_convergence` |
| Board | `hs_plan_circuit` (agent names the planner: HS makes no model call) → `hs_component_board` (unplaced parts placed by HS, re-routed up to 3 times until DRC is clean) → `hs_check_board_parts` (LCSC listing vs footprint and value) → `hs_price_parts` / `hs_bom_check` | `circuit_synthesis`, `component_board_pipeline`, `_pcbnew_helpers.place_free_footprints`, `distributor_check` |
| Salvaged modules | `hs_identify_part`, `hs_import_eagle_module` (geometry from the maker's board, electrical gaps listed) | `part_lookup`, `eagle_board_import` |
| Design spine | `hs_project_link_design` → `hs_project_status` shows the stored machine project's release blockers beside the objective's checks; `hs_salvage_resources` lists the design's donors and the bench tools | `machine_project`, `project_store`, `salvage_resource_graph` |
| Money | `hs_route_economics` (estimates per route) → `hs_record_outcome` (receipted sales on an append-only ledger) | `commercial_value_routing`, `commercial_outcomes` |

Native tools (`hs_fem_screen`, `hs_arm_kinematics`, `hs_motion_sweep`, `hs_rover_chassis`) run through `native_call` in the
interpreter named by `HARDWARE_SPLICER_DIGITAL_PYTHON` (`.cache/hardware-splicer/digital-native-venv` has CadQuery, Gmsh
and PyBullet; not scikit-fem). Board layout needs `HARDWARE_SPLICER_FREEROUTING_JAR` (a jar sits in
`.cache/hardware-splicer/extended-verification-20261116/`).

**Every engineering module is now either shipped (467) or in a declared research line (140; see the map).**
`tests/test_capability_map.py` fails when a new engineering module is neither, so nothing piles up unconnected again.

## 6. Open issues found by connecting things

1. **Netlist-compile pads.** `compile_from_netlist` now reports `netlist_pcb_parity`, and it fails on a two-part board:
   the generated PCB names pads by pin id (`GND`) while the module pad tables put ground on pad `2`. One side is wrong;
   check against the real footprints before fabricating from the catalogue netlist path.
2. **FEM size.** The bounded solver takes up to 5,000 elements and 2,000 nodes; the rover chassis is too large even at
   a 40 mm mesh. Screen a bracket or boss cut from a part, or add a sparse solver.
3. **FEM stays open.** Linear tetrahedra are not conservative in bending, so every `hs_fem_screen` result keeps an open
   blocker; installing scikit-fem in the native venv would let `mechanical_quadratic_fem` (second order) be wired next.
4. **Routing varies.** FreeRouting failed DRC on HS-BUS-A's own placement once in three runs; the board tool now
   retries, and reports each attempt's error count.
