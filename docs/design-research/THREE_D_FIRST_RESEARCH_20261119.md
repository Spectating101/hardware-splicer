# HS 3D-first interface: research and data audit

Date of work: 2026-11-18 to 2026-11-19. Repo inspected read-only: `/home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer` (branch `integration/github-features-20261116`, dirty tree not touched).
Scratch/evidence dir: `/home/phyrexian/.cache/tmp/claude-1000/-home-phyrexian-Downloads-llm-automation-project-portfolio-Hardware-Splicer/4b35ef01-debd-4af2-beff-4450d0563dd3/scratchpad/ui-research-3d/` (`shots/` screenshots, `poc/` throwaway prototype).

Evidence tags used everywhere:
- **SEEN**: I loaded it in headless Chromium and looked at the downscaled screenshot (file in `shots/`).
- **DOCS**: read from a fetched/searched documentation page in this session (summaries came through a small model, so treat exact wording as approximate).
- **MEMORY**: my background knowledge, not verified today.
- **REPO**: verified by reading or parsing files in the HS repo.

Method limits, stated up front: all browsing was headless (swiftshader WebGL), no logins, no cookie banners appeared that needed dismissing. Several large vendors (3DEXPERIENCE, NX/Teamcenter, Creo View, Isaac Sim, Unity, Godot, Altium) were not opened in any live form. Where a tool is listed under "DOCS" or "MEMORY" below it was not seen.

---

## PART A. What real tools do

### A0. Pattern matrix (which tool proves which interaction)

Legend: S = seen, D = docs, M = memory, - = not found / not applicable.

| Pattern | Tools and evidence |
|---|---|
| Tree to 3D selection sync | xeokit BIM viewer S (`shots/xk_explorer.png`); Online 3D Viewer S (`shots/o3dv_hs3g_pick.png`); three.js editor outliner S (`shots/threejs_editor_hs3g.png`); Unreal World Outliner D; Rerun entity tree S (`shots/rerun_urdf2.png`); Fusion browser to viewport D (explode picks from browser); Composer assembly tree D |
| Explode (authored, stepwise) | Onshape Explode steps, triad, rollback bar, explode lines D; Fusion Animation workspace Auto Explode one level / all levels / manual axis, slider D; FreeCAD 1.0 Assembly "Create Exploded View" with `ExplodedViewStep` objects D; eDrawings plays saved explode with slider, cannot author D; Speckle `ExplodeExtension.setExplode` D; HS's own VIEWER.html slider S-by-code (REPO) |
| Isolate / hide others / X-ray | xeokit context menu: Hide, Hide Others, X-Ray, X-Ray Others, X-Ray All S (`shots/xk_select_context.png`); Speckle `FilteringExtension.isolateObjects(ids, stateKey, includeDescendants, ghost)` D; APS viewer isolate + `ghosting` preference D; Unreal "Show Only Selected" D |
| Section plane / clipping | xeokit toolbar scissor "Slices" button S; Speckle `SectionTool` D; KiCad 3D viewer clipping M |
| Measurement | xeokit distance and angle tools S (toolbar ruler, context "Measure"); Foxglove measure tool with Alt/Option snapping to faces/points/lines D; Speckle `MeasurementsExtension` D |
| Callouts / hotspots anchored to geometry | model-viewer hotspots with `data-position`, `data-normal`, fade when facing away, `data-visibility-attribute` and `hotspot-visibility` event S (`shots/modelviewer_annotations.png`); Sketchfab annotations D; xeokit AnnotationsPlugin D (only in feature list); Vuforia/Creo Illustrate 3D connecting lines D (thin) |
| Camera bookmarks | Sketchfab: each annotation stores position plus camera position and target, next/prev, J/K keys, Autopilot, `?annotation=N` deep link D; xeokit BCF viewpoints D; APS viewer state D (name only) |
| Revision compare / ghost overlay | Siemens Teamcenter Visualization Lifecycle Viewer red/green/black difference between item revisions D (community post, not official); Autodesk CrossFadeEffects D (image fade); HS's own comparison = two iframes side by side REPO |
| Properties / inspector | xeokit "Inspect Properties" S; Foxglove click to inspect popup, `$selected_id` D; Rerun Selection panel S; three.js editor Object panel with UUID/name/transform/userData S; APS property database D |
| Time scrub / activity per entity | Rerun timeline, per-entity streams S; Foxglove playback D; LeRobot visualizer "synchronized state and actions and a 3D replay" (landing page text only) S |
| Joint/link control | URDF viewer joint sliders, show collision, hide fixed joints S (`shots/urdf_controls.png`); Foxglove URDF layers: hide link, per-link offset D; MuJoCo web demo actuators panel S (`shots/mujoco_wasm.png`) |
| BOM row to 3D with state | InteractiveHtmlBom: row to footprint highlight, reverse lookup, "Sourced" and "Placed" checkboxes, layer toggles S (`shots/ibom_board.png`) |

### A1. CAD explode and assembly navigation

**Onshape** (DOCS: https://cad.onshape.com/help/Content/Assembly/exploded_views.htm, https://cad.onshape.com/help/Content/exploded_views.htm). An Explode feature holds one or more steps; steps are authored by dragging with the triad manipulator, edit distance or angle afterwards, drag a rollback bar to view intermediate stages; explode lines inherit selection from the previous step and can be shown/hidden per view or per step. I found no documented animated explode. Mate connectors (DOCS: https://cad.onshape.com/help/Content/Assembly/assembly_mate_connector.htm) are named local coordinate systems on or between entities; they matter for HS as the CAD concept of "this part has a defined datum", which HS could expose as a part's mounting datum record. Not seen live (login).

**Fusion** (DOCS: https://help.autodesk.com/cloudhelp/ENU/Fusion-Animate/files/ANI-TRANSFORM.htm and the explode pages). Animation workspace Transform has Auto Explode: One Level (top-level children only), All Levels (down to leaves), and Manual Explode (pick component, pick axis). A slider sets distance, confirm with a check. The distinction one-level vs all-levels is directly relevant to HS: an assembly where a "part" like the Pi is nine nodes should explode as one level first. Browser-tree to viewport selection is how manual explode is driven (DOCS). Not seen (desktop app).

**FreeCAD 1.0 Assembly** (DOCS: https://wiki.freecad.org/Assembly_CreateView). One exploded-views container per assembly holding `Exploded_View` objects whose moves are `ExplodedViewStep` objects, shown only while editing and in TechDraw views derived from them. The wiki page is marked unfinished. External workbench ExplodedAssembly (JMG1) adds animation. DOCS only.

**SolidWorks eDrawings / Composer** (DOCS: https://help.solidworks.com/2023/English/eDrawings/t_Exploded_Views.htm). eDrawings only plays back saved explodes; radio button animates out/in; slider scrubs. Composer: assembly tree on the left, properties below, cutaway "peel layers" faster than hiding parts. 3DEXPERIENCE-specific docs not found; do not claim anything about it.

**Web viewers.**
- **xeokit BIM viewer** SEEN (`https://xeokit.github.io/xeokit-bim-viewer/app/index.html?projectId=Duplex&tab=objects`, screenshots `shots/xk_explorer.png`, `shots/xk_select_context.png`). Left explorer with Models / Objects / Classes / Storeys tabs, checkboxes per node, Show all / Hide all. Toolbar: reset, 3D/ortho, fit, first person, hide, select, marquee, measure distance/angle, section planes with count. Right-click context menu on a part: Inspect Properties, Show in Explorer, View Fit / Fit Selected / Fit All, Hide, Hide Others, Hide All, Show All, X-Ray, X-Ray Others, X-Ray All, X-Ray None, Select, Undo Select, Select None, Clear Slices, Measure. This is the most complete small vocabulary for isolate/ghost found; HS should copy the verbs. Corner view cube present. Not seen: BCF viewpoints (DOCS: listed on https://xeokit.io/).
- **Online 3D Viewer** SEEN (https://3dviewer.net/). I loaded HS's own GLBs (client-side; the page says files stay local). Result: tree "world" with every HS node name, Details panel with size, no per-part metadata (`shots/o3dv_fielddeck7.png`, `shots/o3dv_hs3g_pick.png`). Useful as a baseline: generic viewers show HS geometry but nothing about evidence.
- **Speckle** DOCS (https://docs.speckle.systems/developers/viewer/extensions/filtering-extension-api): `isolateObjects(objectIds, stateKey, includeDescendants, ghost)`, `SectionTool`, `MeasurementsExtension`, `ExplodeExtension.setExplode`. A community thread notes isolate can reset custom colours, a reminder that "state styling" and "evidence styling" must be one layered material system, not two competing ones. Live app needs login, not opened.
- **CAD Assistant** (Open Cascade): not opened; MEMORY only.

### A2. Digital twin and industrial 3D

- **NVIDIA Omniverse / USD Composer / Isaac Sim**: DOCS (search) only on the pipeline: Siemens converts JT to OpenUSD preserving assembly hierarchy, Teamcenter REST APIs carry BOM and change data, USD Notify gives live updates (https://blogs.nvidia.com/blog/openusd-digital-twins-industrial-physical-ai and the Siemens/NVIDIA pages). I did not read Composer or Isaac Sim UI docs; the stage tree/viewport sync is MEMORY. The relevant idea: hierarchy plus BOM plus change data travel with the geometry, which is exactly what HS's GLBs lack (see Part B).
- **Siemens NX / Teamcenter Visualization / JT2Go**: DOCS (search). PMI organised into model views; revision comparison with a default red/green/black difference display is described only in a community answer (https://eng-tips.com/threads/teamcenter-visualization-10-1-overlaying-drawing-files-for-comparison.368299), not Siemens docs.
- **PTC Creo View, Creo Illustrate, Vuforia Studio**: DOCS (search results only): authoring in Illustrate, animated step sequences, ThingMark anchoring; I got no detail on part-mapped instructions. Part-to-instruction mapping beyond that is not verified.
- **Dynamics 365 Guides**: DOCS (https://learn.microsoft.com/en-us/training/modules/author-guides/06-holographic-anchor). Authors align a hologram to the physical object by hand; QR/object anchors; precision depends on anchor position. The search surfaced a Microsoft Learn note that Guides and Remote Assist are not available after 2026-12-31; I did not open that page, so treat as unverified, but it argues against building HS around headset AR.
- **Autodesk Platform Services viewer**: DOCS (https://aps.autodesk.com/en/docs/viewer/v7/developers_guide/viewer_basics/). Documents/manifest nodes from Model Derivative, `loadDocumentNode`; property database, `setThemingColor`, `ghosting` preference, CrossFadeEffects extension found via search. I did not find `Autodesk.Explode` docs. Key lesson: properties come from a derivative property database keyed by object id (dbId), a separation HS should copy (geometry file small, part facts in a sidecar keyed by stable id).

### A3. Teardown, repair and PCB 3D

- **iFixit**: DOCS (search). No interactive 3D exploded model found on iFixit; guides are step photos, exploded views exist as 2D guides; Lumafield CT scans are internal planning models. A commercial vendor (Viflux) advertises interactive 3D repair guides with exploded views; not opened. So "3D repair guide" is a thin field, which is an opening for HS but also a sign that demand is unproven.
- **Sketchfab annotations**: DOCS (https://help.sketchfab.com/en/articles/16152328). Annotation = position + title (64 chars) + description (1024) + saved camera position and target; next/prev buttons, menu, Autopilot, J/K keys, `?annotation=N` link; annotations can be hidden but next/prev still moves camera. Live page not captured.
- **model-viewer hotspots** SEEN (`https://modelviewer.dev/examples/annotations/`, `shots/modelviewer_annotations.png`). Screenshot shows blue dot hotspots on an astronaut, a red hotspot whose label "disappears completely" when facing away, and a label "fixed in screen-space". DOCS: `data-position`, `data-normal`, `--min-hotspot-opacity`, `data-visibility-attribute`, `hotspot-visibility` event.
- **InteractiveHtmlBom** SEEN (https://openscopeproject.org/InteractiveHtmlBomDemo/html/pic_programmer.html, `shots/ibom_board.png`). BOM table left, board right; clicking row C3 highlights the footprint with a red box; DOCS: reverse lookup by clicking a footprint; Sourced and Placed checkboxes per row; filter and reference lookup; F / FB / B layer buttons. The check-state-per-BOM-line is the closest real precedent to an evidence column. I found no 3D fork in the README (the brief mentioned "3D forks"; not verified).
- **KiCanvas**: landing page SEEN (`shots/kicanvas.png`); DOCS README says early alpha, 2D schematic/board, no 3D mention. HS already embeds it (REPO, below).
- **KiCad 3D viewer / Altium 3D**: the manual page I fetched cut off before the 3D section (DOCS: it lists 3D viewer under "Inspecting a board" and STEP/GLB export). Cross-probing, clipping, raytracing are MEMORY.

### A4. Robotics and simulation 3D

- **Rerun** SEEN (https://rerun.io/viewer, URDF example SO-ARM100, `shots/rerun_urdf2.png`). Layout: Sources, Blueprint, 3D view in centre, Selection panel on right (recording id, size, entities, rows), timeline panel with entity-path streams (`so_arm100/collision_geometries`, `visual_geometries`, `tf_static`, `transforms`) and a time cursor. DOCS (https://rerun.io/docs/reference/types/views/spatial3d_view): eye controls with tracking entity, spin speed, time ranges, WASDQE. The entity-path tree plus per-entity timeline is the best precedent for "agent activity attached to a part over time".
- **Foxglove 3D panel**: DOCS (https://docs.foxglove.dev/docs/visualization/panels/3d). URDF layers (visual or collision geometry, hide link, per-link offset), click opens inspector popup, sets `$selected_id`, follow modes Pose/Heading/Position, measure tool with snapping, in-app transform offset editing without changing source data (a nice precedent for "what-if without upgrading authority"). Live app needs login.
- **Isaac Sim**: not read; skip.
- **MuJoCo wasm demo** SEEN (https://zalo.github.io/mujoco_wasm/, `shots/mujoco_wasm.png`): humanoid, Controls and Simulation panel (pause, reload, reset, keyframe, noise), collapsible Actuators. Little to borrow beyond scene-level controls.
- **URDF loaders viewer** SEEN (https://gkjohnson.github.io/urdf-loaders/javascript/example/bundle/, `shots/urdf_controls.png`): joint sliders with values per joint, toggles Ignore Joint Limits, Hide Fixed Joints, Show Collision, Animate Joints. "Ignore Joint Limits" is the kind of switch HS must label as unsafe/assumed.
- **LeRobot dataset visualizer**: landing page SEEN (`shots/lerobot_vis.png`): "camera recordings, synchronized state and actions, and a 3D replay of the robot". I did not load a dataset.
- **OpenArm upstream viewer**: REPO shows `scripts/vendor_upstream_openarm_viewer_001.py` vendors a three.js viewer with `openarm_follower.glb` plus `follower_metadata.json` from `github.com/Utsav92/openarm-3d-cad-assembly` at a pinned revision. The upstream page was not reachable (GitHub Pages 404), so not seen.

### A5. Sci-fi UI craft and game-engine editors

- **Jayse Hansen** (DOCS, read: https://www.pushing-pixels.org/?p=7447 and https://www.provideocoalition.com/marvels_the_avengers_taking_the_hud_to_new_heights/amp/). Relevant statements: all graphics had a purpose and text related to the scene; chasing "cool" gives "a bunch of circles and random text"; goal is information understandable "at a glance", complex data can remain complex if it conveys what is needed; a fighter pilot taught him to "blank out the rest"; stereo made micro text legible but raised concern about "very fast 3D movements and motion shake" and foreground graphics causing viewer discomfort; Mark 7 HUD had Diagnostic, Battle, Flight modes, and a 2D radar map unfolding into 3D; diagnostic variants had 1,000+ elements; "reality comes in as a second" and corners were cut on functionality. The pushing-pixels page does not discuss exploded views; an unsourced search snippet said Hansen describes holograms of suit parts showing "the inside structure and the breakdown of how it works", which I did not verify.
- **Perception** (DOCS, search only: https://www.pushing-pixels.org/2014/02/12/the-craft-of-screen-graphics-and-movie-user-interfaces-interview-with-john-koltai.html, https://www.engadget.com/2015/12/14/perception-ui-design/). Iron Man 2 was their breakthrough; later real-world spinoffs (Ford GT dashboard). I did not read any statement from them about readability or exploded holograms.
- **What real products borrowed and what failed**: I found no authoritative source for either (the uxdesign.cc article "why all of hollywood ui looks the same" returned 403; Chris Noessel's sci-fi interface critiques are MEMORY). Evidence-backed adjacent facts: AR label research (DOCS via search: Tu Graz / Purdue papers) says naive annotation placement leads to clutter and occlusion, crossing leader lines are a core constraint, and systems either freeze or continuously re-layout labels while the camera moves; headset hologram anchoring in Dynamics 365 Guides needs manual alignment and drifts. Motion sickness: I found no source; the rule in section B-synthesis is a design inference.
- **Game-engine editors**: Unreal selection in World Outliner is linked both ways with the viewport, "Show Only Selected" isolate and "Show all actors" restore (DOCS, forum and docs pages via search), with reported bugs for grouped actors (a caution: isolate on a grouped part may hide children). three.js editor SEEN (https://threejs.org/editor/; after importing HS3G_B_ASSEMBLY.glb the outliner shows `HS3G_B_ASSEMBLY.glb > world`, a translate/rotate/scale gizmo is on screen, shading dropdown SOLID, and the Object panel shows UUID, Name, Position, Rotation, Scale, **User data `{}`**; `shots/threejs_editor_hs3g.png`). The empty user data is the visible evidence that HS GLBs carry no part metadata. Unity hierarchy/scene view and Godot scene tree: MEMORY only (same outliner-viewport sync, gizmos, isolation).

---

## PART B. What HS's own data honestly supports

All figures below are REPO unless noted. I parsed GLB JSON chunks directly, loaded GLBs with trimesh from `.cache/hardware-splicer/digital-native-venv/bin/python` for the revision diff, and read model.json, results.json, geometry_report.json, bom.json, BOM.csv, the STEP `PRODUCT(...)` names, and the nested FieldDeck-5 integration zip.

### B0. Cross-cutting findings

1. **Identity is carried by name only.** In every GLB: one `world` node with flat children, node name equals mesh name equals the STEP `PRODUCT('<name>')` name. No `extras`, no `extensionsUsed`, no materials (colour is vertex colour), no node transforms (positions baked into mesh vertices), no animation. A generic editor shows `User data {}` (SEEN).
2. **Units disagree.** HS3G_B_ASSEMBLY.glb is in metres (Online 3D Viewer shows size 0.16 x 0.16 x 0.07, SEEN; README says GLB metres, STEP mm). FIELDDECK_7.glb is millimetres (bounds 0..310 by 0..285.7). Pen plotter GLB units not checked.
3. **Per-part provenance exists in some places, not in the GLB.** Drone: `model.json.parts[].native_frame` (true only for bottom_plate and top_plate) and `label` text such as "Representative lens"; `results.json.parts[].sources[].class` (maker_page, maker_drawing, repo, retailer_page, retailer_search, maker_search, assumption) is per BOM id, not per node. Fielddeck: `geometry_report.json.parts[].kind` (custom / purchased_envelope / manufacturer_step) with a notes sentence per part. Pen plotter: the node name itself says `REFERENCE_ENVELOPE_...`.
4. **No measured evidence exists for any of these devices.** `physical_validation`, `fabrication_authorized`, `flight_authorized`, `power_on_authorized` are all false in drone results.json; Fielddeck `physical_fit_verified` is false; the display swap JSON says `physical_validation_performed: false`. The word "measured" appears in drone results.json only for values measured from HS's own CAD (`measured.bottom_bbox_mm`, hole counts). A UI must not render those as "measured" in the physical sense; call them "computed from CAD".
5. **Explode data**: only the drone has authored explode vectors (`model.json.parts[].explode_m`, for example top_plate +0.06 m z, battery -0.04 m z, motors/props radial plus z). No explode vectors for Fielddeck or the pen plotter. `docs/TEARDOWN_NATIVE_MACHINE_EXPLAINER_20261101.md` says its visual guided sequence uses "scripted exploded offsets, not independently verified kinematics", so even authored explodes are presentation, not assembly order.
6. **Revision pairs for ghost-compare**: Fielddeck 7 (`projects/cyberdeck-real-trial-20261020/digital_v1/cad/FIELDDECK_7.glb`, tracked) versus Fielddeck 5 (`revision/cad/FIELDDECK_5.glb`, only inside `projects/cyberdeck-real-trial-20261020/display_swap/integration-trial/FieldDeck-5-integration.zip` > `fielddeck-study.zip`). By node name and geometry signature (vertex count, volume, bounds) in the shared millimetre frame: 28 nodes identical, 4 changed (`tray_rear_left`, `face_rear_left`, `tray_rear_right`, `face_rear_right`; matches `mechanical/changed-parts.json`), 5 added (`touch_display_2_5inch_sc1975`, `display_spacer_1..4`), 1 removed (`touch_display_2_manufacturer`). Drone: HS3G rev B has per-requirement saved revisions in the UI (see B6) but I found no Rev A assembly GLB; Rev A plate STEP/STL exist under `examples/drone_proving_ground/generated/` (not examined further).
7. **Evidence about the 3D itself** is in sidecars: drone `verification.json`, Fielddeck `analysis/verification.json` (`glb_part_bounds_checked`, `physical_fit_or_operation_proven`, `all_flexible_cables_and_fasteners_modelled`), display swap `geometry.json` (`plug_exits_and_bends_verified: false`, `obstruction_free: true` for a reserved FFC corridor with centreline and boxes in mm).

### B1. HS-3G-B drone (`examples/drone_proving_ground/`)

Files: `digital/reference/HS3G_B_ASSEMBLY.glb` (571 KB), `.step` (33 PRODUCT names), `model.json` (3.3 MB), `VIEWER.html` (3.4 MB, three.js inlined), `revision_b/reference/results.json`, `BOM.csv`.

| Item | Count / finding |
|---|---|
| Parts in 3D | 32 nodes: bottom_plate, top_plate, stack_ESC, stack_FC, 8 grommets (ESC_grommet_x_y, FC_grommet_x_y), vtx_1, camera_1, camera_lens, receiver_1, gps_1, battery_1, standoff_1..4, motor_1..4, prop_1..4, strap_bottom, strap_top |
| Real geometry vs representative | 2 native CAD (`native_frame: true`: both plates). 30 representative (README: "simplified electronics and blades", "not vendor-detailed"; `representation` string in model.json). SEEN in my prototype: plates look real, everything else is a box/cylinder |
| BOM lines | 12 in results.json/BOM.csv: stack, motor, prop, battery, gps, receiver, camera, vtx, standoff, hardware, wiring, frame_cut |
| Nodes mappable to a BOM/evidence id | 24 of 32 by name convention only: frame_cut <- bottom_plate, top_plate (name differs completely; needs a table); stack <- stack_ESC, stack_FC; vtx, camera, receiver, gps, battery <- `<id>_1`; camera_lens is a sub-part of camera; standoff 4, motor 4, prop 4; strap_* maps into the `hardware` line (strap is an item inside it, not its own line) |
| Nodes with no BOM line | 8: the ESC/FC grommets ("Stack damper") appear nowhere in BOM.csv (grep count 0) |
| BOM lines with no geometry | wiring (12 g allowance), hardware (16 M2 screws, 4 M3x30, 8 M3x6, spacers, nuts: only the strap is drawn); prop is 1 line with qty 2 packs vs 4 prop nodes |
| Per-part evidence fields | results.json parts: `sources[]` with `class` and `accessed`, `price_class` (maker_page / assumption), `unit_mass_g`, notes such as the stack mass conflict ("parts sum to more than the whole, so the sum 16.8 g is used until the stack is weighed"), `motor_thread_depth_verified: false` (engagement 2.99 mm), battery envelope "conservative 62 x 33 x 33 mm interpretation of conflicting maker dimensions". Four BOM ids (standoff, hardware, wiring, frame_cut) are `assumption` |
| Explode vectors | yes, `explode_m` for all 32 |
| Part transforms | baked into vertices; `rotor_centres_m`, `rotor_spin_signs`, `centre_of_mass_m` in model.json; `mass_proxies` has 21 entries (not 32) |
| Revision pair | not as GLB (see B0.6) |
| In-UI today | VIEWER.html: orbit, explode slider, labels toggle (DOM labels centred on parts), scenario playback; no evidence state, no selection event out (REPO: zero `postMessage` in the file) |
| Missing for an honest parts-mapped view | stable `part_id` on each node; node-to-BOM-id table (including frame_cut, strap-to-hardware, grommets as explicit "no BOM line"); per-part evidence state enum computed from `sources[].class`; per-part blockers (thread depth unverified, battery dimension conflict, stack mass conflict, discontinued controller per README); unit declaration; alternates (BOM has none per part) |

### B2. Fielddeck 7 (`projects/cyberdeck-real-trial-20261020/digital_v1/`)

| Item | Count / finding |
|---|---|
| Parts in 3D | 33 meshes in GLB (+ `world`), 38 solids in STEP reimport |
| Geometry basis (geometry_report.json) | 20 `custom` (4 tray quarters, 4 face pieces, 6 seam plates, fan_guard, fan_duct, 4 feet); 12 `purchased_envelope` (keyboard, power bank, pi4 board, 8 Pi connector/SoC proxies, fan); 1 `manufacturer_step` (Raspberry Pi touch display STEP, MIT licence, "approximate vendor geometry, not physical metrology") |
| BOM lines | 22 in bom.json / BOM.csv: bank_pad, computer, display, keyboard, bank, microsd, fan, power_cable, dsi, gpio_extensions, filament, m3_10, m3_25, m3_nut, m25_10, m25_nut, m25_6, bank_straps, keyboard_pads, tape, retention, printed_parts |
| Nodes mappable to a BOM line | all 33 by convention: display 1; keyboard 1; bank 1; computer 9 (pi4_board_envelope + 8 proxies); fan 1; 20 custom parts all roll into the single aggregate `printed_parts` (+ `filament`) line, so no per-printed-part BOM or evidence line |
| BOM lines with no geometry | about 16: dsi cable, gpio_extensions, power_cable, microsd (only the slot proxy `pi4_microsd` exists), all fasteners (verification: "threads and flexible cables are not complete solid models", `all_flexible_cables_and_fasteners_modelled` false), pads, tape, retention, straps |
| Per-part evidence fields | geometry_report `kind` + `notes` per part (e.g. "Adafruit 1736 published 285 x 123 x 22 mm", "Anker A1259; buttons/ports are not inferred from the envelope", "Conservative connector proxy; exact plug/cable dimensions remain separate keep-outs"); BOM has `price_basis` ("observed retail" vs "planning allowance, not a quote"), `open_issue`; `sources/references.json` with hashes |
| Explode vectors | none authored. My prototype derived radial+z offsets from part centroids |
| Revision pair | yes, 7 to 5 (see B3) |
| Missing | stable ids in GLB; explicit node-to-BOM table (the Pi's 9 nodes share one BOM line); per-printed-part ids; evidence state per BOM line (maker/retail observation vs allowance); blockers per part (bank port placement unpublished, keyboard underside unknown, display lug engagement nominal, per README) |

### B3. Fielddeck 5 display swap (`display_swap/`, `docs/status/generated/fielddeck-display-swap-20261118.json`)

This is the richest per-part evidence in the repo and the best demo case.

| Item | Finding |
|---|---|
| 3D | FIELDDECK_5.glb, 37 mesh nodes (see B0.6 diff). The new display node is not watertight (vendor STEP tessellation) |
| Evidence attached to the changed display | `revision/source-evidence.json`: vendor STEP URL + archive and STEP sha256, product brief sha256, documented power 1.4 W, glass 143.4 x 91.46 mm, viewing area 111.4 x 63.1, mount pitch 103.7 x 51, nominal lug depth 14.92 |
| Unknowns and blockers | candidate SC1975: `manufacturer_declares_pi4_compatibility: true` but `generic_interface_result: unresolved`, `open_checks: [pin_mapping_unknown, signal_voltage_unknown]`; FFC route: `obstruction_free: true` for the rigid reserved corridor but `plug_exits_and_bends_verified: false`, `minimum_bend_radius_mm: null`, `exact_installed_cable_route_verified: false`; `physical_fit_verified: false` |
| Alternates | `incompatible_control`: "10-inch Touch Display 2" status `blocked`, failed checks `enclosure_fit`, `connector_mismatch`, `protocol_mismatch`; baseline part SC1635 |
| Changed parts evidence | `mechanical/changed-parts.json`: mass of four changed printed parts plus 4 spacers (466.773 g solid-equivalent PETG), STEP hashes; 288 nominal changed-pair intersection checks, limit 0.05 mm3 |
| Electrical | `electrical/KICAD_ERC.json`, `netlist.json`, `lead_check.json` (I did not read the ERC outcome; do not quote it) |
| Missing | the evidence is JSON keyed by BOM ids and part names, not by 3D node names; no machine link from `pin_mapping_unknown` to the node (it belongs to a connection between `pi4_dsi` and the display, not to a mesh) |

### B4. Pen plotter (`projects/ender3-penplotter-digital/`)

| Item | Finding |
|---|---|
| Parts in 3D | `exports/plotter.glb`: 24 meshes |
| Real vs envelope | 18 are named `REFERENCE_ENVELOPE_*` (bed, bases, uprights, top, X rail, belts, 3 motors, PSU, controller enclosure, LCD, parked hotend, parked fans/shroud); 6 detailed: `pen_adapter`, `pen_clamp`, `hotend_parking_plate` (HS-authored), `manufacturer_E_plate` (manufacturer STEP), `paper_180mm_square`, `pen_envelope`. README: "Other retained components are explicitly named REFERENCE_ENVELOPE shapes". This is the only project that encodes honesty in the node name already |
| BOM | `BOM.md`, prose table of donor identifiers (400201001 motors, 400212037 belt, ...) from the manufacturer XLS, no CSV/JSON, no purchase links or prices |
| Transforms | `sources/assembly_parts.json`: 300 instances (`NAUO265`...) with location and bbox from the one-time import of the 44.8 MB manufacturer assembly (not retained); instance ids are not the GLB node names |
| Per-part evidence | `sources/interface.json` for the E plate only (mount centres, "evidence" string, tolerance 0.001 mm); verification report scope: no hardware or powered tests |
| Explode / revision pair | none |
| Missing | machine table envelope node to donor identifier; evidence for envelopes (just "reference"); explode vectors |

### B5. PCB inspection nest (`projects/pcb-inspection-nest/`)

| Item | Finding |
|---|---|
| 3D artifacts | no GLB tracked; STEP/STL live inside `inspection-nest-v0.1.zip` (dock, 3 carriers, 3 assemblies in v0.1) and v0.2 adds a fourth (README table lists four; I did not unzip v0.2). `preview.png` is a static exploded render |
| Per-part metadata | `boards.json`: pinned repo, revision, path, sha256, board centre/envelope, `mount_refs` (H1..H4, U$29...) for each source board |
| Honest limits | models omit components and cables; board shapes are "adapted from the external contour and mounting holes" of CC BY-SA sources; a fixture, not a device |
| Verdict | small and proof-friendly (6 to 10 solids), but not a "device" scene; skip for the first 3D view, use later to show source-pinned provenance |

### B6. How apps/splice-ui renders 3D today

- `apps/splice-ui/package.json` dependencies: `@xyflow/react`, `react`, `react-dom`. No three.js, no model-viewer, no GLTF loader.
- `src/projectSession/DigitalStudyPanel.jsx`: if `VIEWER.html` exists, renders an `<iframe ... src="...VIEWER.html?embed=1" sandbox="allow-scripts allow-downloads" loading="lazy">`; otherwise a download link for the GLB plus a static render. The comparison feature renders a second iframe ("Comparison design") side by side. With the sandbox lacking `allow-same-origin` and VIEWER.html having no `postMessage`, the host cannot receive selection or drive camera/explode.
- `src/components/DesignPreviewPanel.jsx` loads `/kicanvas/kicanvas.js` and renders a `kicanvas-embed`: the 2D schematic/PCB path exists.
- Working tree already has uncommitted `DigitalStudyLibrary.jsx`, `FieldDeckDisplayComparison.jsx`, and `docs/OPUS_FRONTEND_DESIGN_BRIEF.md` (not read; another agent's work). `docs/FRONTEND_GITHUB_SIGNALS_20261118.md` recommends the FieldDeck display change as the first acceptance case ("Inspect and decide. A mounting issue opens the relevant geometry"), consistent with this research.
- The robot-arm lane uses a vendored upstream OpenArm viewer with its own GLB/metadata JSON (REPO scripts); no tracked robot GLB found.

### B7. Summary table: what an honest "parts mapped in 3D" view needs

| Project | Nodes | Real geometry | Envelope/representative | Nodes with BOM/evidence tie (by name convention) | Nodes with no tie | Authored explode | Revision pair | Biggest missing piece |
|---|---|---|---|---|---|---|---|---|
| HS-3G-B | 32 | 2 | 30 | 24 | 8 (grommets) | yes (32) | no GLB pair | per-node id plus evidence state; frame_cut and strap tables |
| Fielddeck 7 | 33 | 20 custom + 1 vendor (approx.) | 12 | 33 (20 via one aggregate line) | 0 | no | yes (7 to 5) | per-printed-part ids; Pi proxies tied to one line |
| Fielddeck 5 swap | 37 | 20 custom (4 changed) + 4 spacers + 1 vendor | 12 | all | 0 | no | yes | part-to-evidence key; connection-level unknowns need a "link" object, not a mesh |
| Pen plotter | 24 | 6 detailed | 18 (named) | ~0 machine-readable | 24 | no | no | envelope-to-donor-id table |
| PCB nest | n/a | all custom | board outline refs | via boards.json | n/a | no | v0.1 to v0.2 zips | not a device scene |

---

## C. Prototype that proves feasibility (SEEN)

Throwaway, scratch only: `poc/scene.html` (three.js 0.160 from unpkg, OrbitControls, GLTFLoader), driven headless by `poc/shoot.cjs`, served from a local python server. It reads only existing data: GLB node names, `fd7_kinds.json` (extracted from `geometry_report.json`), `hs3g_meta.json` (from `model.json`). It makes no evidence claims; colour means geometry basis only.

- `shots/poc_fd7_exploded.png`: Fielddeck 7, derived explode (centroid-based, not authored). Solid pale = custom printed parts; amber dashed = vendor display STEP (approximate); cyan dashed ghost = purchased envelopes (Pi, bank, keyboard, fan). Reads clearly; the distinction between "drawn from real design" and "stand-in volume" is visible without any legend text.
- `shots/poc_fd_swap.png`: Fielddeck 5 vs 7 in one canvas. Red dashed = removed 7-inch display; green dashed = added 5-inch display plus spacers. Limit seen in the shot: the four changed rear tray/face parts are not highlighted (I only coded added/removed); that is easy because the changed list is derivable.
- `shots/poc_hs3g_exploded.png` (authored `explode_m`, factor 1.6): the two native plates are solid, everything else is dashed ghost boxes/cylinders. This is the honest picture of the drone: 2 of 32 parts are real geometry. Labels did not appear in my run (bug in my throwaway label anchoring, not investigated).
- Generic-viewer baselines: `shots/o3dv_fielddeck7.png`, `shots/o3dv_hs3g_pick.png`, `shots/threejs_editor_hs3g.png`.

---

## D. Synthesis

### D1. Patterns worth adopting (13), with proof, honesty rule and backend cost

| # | Pattern | Proven by | How it respects "no fake authority" | Data/backend work |
|---|---|---|---|---|
| 1 | Tree and 3D selection sync, both directions, tree includes unmapped geometry and BOM lines with no geometry | xeokit S, three.js editor S, Rerun S, Unreal D, IBOM S | Unknown/unmapped items are rows in the tree (not hidden); selecting a BOM line with no geometry flashes the tree row and shows "no geometry" | `part_id` in GLB `extras` and a `parts.json` sidecar mapping part_id to node(s), BOM line(s), qty index |
| 2 | Evidence-state as a visual channel on the part (solid / hatched / dashed / ghost), never a colour alone | PoC S; pen plotter's `REFERENCE_ENVELOPE_` naming REPO | States are only the four HS words (measured / datasheet / assumed / unknown); no "ready"/green; unknown = dashed ghost, still visible and pickable | Per-part evidence record; rule to derive state from `sources[].class` (maker_page = datasheet, assumption = assumed, none = unknown). "measured" never produced until a physical measurement record exists (none today) |
| 3 | Geometry-basis marker separate from evidence state (real CAD vs vendor STEP vs envelope vs proxy) | geometry_report `kind` REPO; PoC S | Prevents a rendered-looking part from implying measured truth; envelope shown dashed with the word "envelope" in the card | Export `geometry_basis` per node (drone `native_frame` and Fielddeck `kind` already hold it) |
| 4 | Explode with slider, authored vectors, and one-level vs all-levels grouping; show explode lines | Onshape D, Fusion D, eDrawings D, Speckle D, HS3G model.json REPO | Label "presentation offset, not assembly order"; derive vectors visibly as derived when not authored | Drone has `explode_m`; Fielddeck needs authored or derived vectors plus group ids (Pi = 9 nodes = one group); no safe-assembly-order claim |
| 5 | Isolate / hide others / X-ray others as verbs in a context menu | xeokit S | De-emphasis must use a different channel (low opacity solid) from "unknown" (dashed outline); never reuse the ghost style for both | None beyond ids; UI state only |
| 6 | Anchored hotspots/callouts only for selected part, blockers and top-N, with facing-fade and leader line | model-viewer S, Sketchfab D, AR label papers D | Callout text is the blocker or unknown sentence from the record, verbatim; no decorative micro-text | Blocker records with `part_id`, short text, severity |
| 7 | Blocker tour: camera bookmarks stepped with next/prev, deep link per item | Sketchfab D (J/K, `?annotation=`), xeokit BCF D | Each stop is a recorded blocker, so the tour is a list of open unknowns, not a showcase | Stored viewpoints (camera, selection, explode, revision pair) keyed to blocker id |
| 8 | Revision compare in one canvas: added / removed / changed, plus unchanged dimmed | Siemens Lifecycle viewer D (community); PoC S (7 vs 5) | Added/removed come from geometry hashes, not model opinion; a changed part is "geometry changed", not "worse" or "fixed" | Revision records with GLB per revision and a node-hash diff (cheap; computed above); put FIELDDECK_5.glb in the project, not only in a nested zip |
| 9 | Part card = properties panel with evidence ledger rows (field, value, state, source, date) | xeokit Inspect S, Foxglove D, APS property DB D, Rerun Selection S | Unknown fields are rows with value "unknown" (for example `pin_mapping_unknown`); source hashes shown | Sidecar keyed by part_id; map from results.json/source-evidence.json |
| 10 | BOM row to part with state checkboxes, reverse lookup | IBOM S | Columns are evidence states, not "Sourced/Placed" checkmarks implying done | BOM line ids already exist; need line-to-node table |
| 11 | Section plane and measure, labelled by what was measured | xeokit S, Foxglove D | A measurement across an envelope is tagged "envelope dimension"; vendor STEP measure tagged "approximate vendor geometry" | Geometry-basis per node; no new backend |
| 12 | Timeline/stream of agent activity per entity, with a scrub cursor | Rerun S | Show only recorded events (who, what, when, result); empty state is "no recorded agent activity for this part" | Event log with `part_id` and run id; not verified to exist per part in HS today |
| 13 | Camera-view state deep link (camera + selection + explode + revision pair + layers) | Sketchfab D, xeokit BCF D | Share link restores what the reviewer saw, including which items were ghosted unknowns | A small view-state schema; no geometry changes |

Honourable mentions for the arm lane only: joint/link control with explicit "limits ignored" and "assumed" flags (URDF viewer S, Foxglove D), and visible collision geometry toggle.

### D2. Patterns to avoid

- Idle auto-rotate or any camera motion the user did not trigger. Source support: Hansen on motion shake and foreground discomfort (D); beyond that the motion-sickness rule is my inference, no source found. Camera moves only on a bookmark click, short and eased, with a view cube/axes visible.
- Always-on labels for every part. VIEWER.html's labels toggle centres a DOM label on each part (REPO); with 32 nodes this collides. Label only selected, hovered and blocker parts; AR research (D) shows crossing leaders and occlusion are the failure modes.
- Floating text without a part anchor or with decorative micro-copy (Hansen: "a bunch of circles and random text").
- Glow, scan lines, bloom, hologram transparency as styling. Transparency is already used for "unknown" and "de-emphasised"; adding decorative transparency destroys the channel.
- Progress rings, pulsing "agent working" indicators and counters that are not driven by recorded events.
- Any green/"ready"/checkmark badge. The repo's own results say `fabrication_authorized` and `flight_authorized` false; the scene must show scene-level blockers, never a summary pass.
- Showing envelopes as if they were parts (solid, same material). 30 of 32 drone nodes are stand-ins.
- A separate iframe viewer with no message bridge, and two iframes for comparison (cameras cannot sync; REPO).
- Physical-looking playback (flight, joint motion) beside part cards, which can read as validation. Label sim as simulation of representative geometry; the drone README says "not a physically calibrated twin".
- Treating CAD-measured numbers as "measured" evidence.
- Headset AR as a primary surface (Dynamics 365 Guides end-of-support note is unverified but points the same way).

### D3. Backend/data work, in priority order

1. Export contract for each revision: `parts.json` sidecar plus GLB with `extras.hs_part_id`, `hs_geometry_basis` (custom / vendor_step / envelope / proxy), `hs_units`; normalise to one unit (mm).
2. Node-to-BOM table per project (and "no BOM line" flag), including aggregates (printed_parts) and sub-parts (camera_lens, strap in hardware).
3. Evidence-state derivation function, deterministic and tested: source class to state; absence to unknown; nothing becomes measured without a physical measurement record; CAD-computed values tagged separately.
4. Blocker and alternate records bound to `part_id` (display swap already has `open_checks`, `failed_checks`, `incompatible_control`; drone has thread depth, battery dimension conflict, stack mass note).
5. Revision records with per-node hash diff and first-class FIELDDECK_5.glb.
6. Connection objects (FFC between `pi4_dsi` and display) as selectable 3D links, since the main unknowns (`pin_mapping_unknown`) belong to interfaces, not meshes.
7. Authored or clearly derived explode vectors and group ids for Fielddeck.
8. Per-part agent event log (verify first whether HS audit already stores part references; not checked).
9. Front-end: replace the VIEWER.html iframe with an in-app three.js scene (new dependency; none present today) so selection, camera and explode are shared with React; keep VIEWER.html as the offline export.

### D4. Recommended first "impressive but honest" scenes

**Scene 1: Fielddeck display swap (primary).** Data exists today for everything except the id/evidence keying.
- Centre: Fielddeck 5 assembled, printed parts solid pale, Pi/bank/keyboard/fan as dashed ghost envelopes, the display amber dashed (vendor STEP, approximate). Slider "explode" derived by group (Pi = one group).
- Compare toggle: red dashed ghost of the removed 7-inch display, green dashed new 5-inch display and four spacers, four changed rear tray/face parts hatched "geometry changed", other 28 dimmed.
- Click SC1975: part card with ledger rows: glass size, mount pitch, lug depth (datasheet, source hash), power 1.4 W (datasheet), pin mapping (unknown), signal voltage (unknown), fit (unknown, `physical_fit_verified` false). Blocker callout anchored to the DSI link and the FFC corridor: "rigid corridor free; plug exits and bends not verified". Alternates drawer: 10-inch panel, blocked: enclosure fit, connector mismatch, protocol mismatch.
- Bookmarks: "Display stack", "FFC corridor" (draw the reserved boxes from `geometry.json` as ghost volumes), "Changed parts".
- Agent activity strip: shows "no recorded agent activity" until events carry part ids.
- No ready badge; header states "No physical validation performed".

**Scene 2: HS-3G-B drone.**
- Centre: two native plates solid; 30 stand-ins as dashed cyan envelopes tagged "representative"; authored explode slider (z stack: battery below, stack, plates, GPS above, props raised).
- Click motor_2: card from results.json: F1404 KV2900 (maker page + maker drawing, datasheet), unit mass 9.34 g (datasheet), M2 thread engagement 2.99 mm (computed from CAD), usable thread depth unknown (`motor_thread_depth_verified: false`). Click battery: dimensions conflicting between maker sources, drawn as conservative envelope (assumed). Click stack: maker mass conflict, mass assumed as the sum. Wiring and hardware screws appear only in the tree/BOM as "no geometry".
- Scene-level blockers pinned: fabrication, power-on and flight not authorised; controller marked discontinued by maker (README). Eight grommet nodes appear as "no BOM line".
- Optional: computed centre of mass marker, labelled computed.

Pen plotter and arm: later. The plotter already names envelopes honestly but lacks any BOM/evidence tie; the arm needs the vendored OpenArm viewer's metadata sidecar and a real URDF-backed joint model before a 3D-first view makes sense.

### D5. Gaps in this research (do not over-trust)

Not opened live: Onshape, Fusion, SolidWorks/3DEXPERIENCE, FreeCAD, Speckle, APS viewer, Omniverse, NX/Teamcenter, Creo View, Vuforia, Dynamics 365 Guides, iFixit 3D, Sketchfab annotated model, Foxglove, Isaac Sim, KiCad/Altium 3D, Unity, Godot; KiCanvas and LeRobot only landing pages. Claims on those are from searched docs summaries or memory. I found no authoritative source for what real products borrowed from sci-fi UIs or for motion-sickness rules. I did not find any InteractiveHtmlBom 3D fork. I did not read the other agent's in-progress `FieldDeckDisplayComparison.jsx` or `OPUS_FRONTEND_DESIGN_BRIEF.md`, so a design brief may already cover parts of D4.
