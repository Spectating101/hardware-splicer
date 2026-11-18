# Advanced, dynamic engineering interfaces: patterns for Hardware Splicer

Research snapshot, 2026-11-18. Companion to `docs/FRONTEND_GITHUB_SIGNALS_20261118.md` (22-repo survey; not repeated here).

Screenshot base directory (all `shots/...` names below are under it; `s_*.png` are the downscaled copies I actually viewed):
`/home/phyrexian/.cache/tmp/claude-1000/-home-phyrexian-Downloads-llm-automation-project-portfolio-Hardware-Splicer/4b35ef01-debd-4af2-beff-4450d0563dd3/scratchpad/ui-research-advanced/`

## Evidence labels used throughout

| Label | Meaning |
|---|---|
| SAW | I loaded the live page headlessly (Playwright Chromium, no login) and looked at the screenshot. Screenshot name given. |
| DOCS | I read the product's own docs, README, changelog, release notes or PR text this session. I did not see it run. |
| SECONDARY | Third-party blog or search-result summary. Treat as weaker. |
| MEMORY | From my own prior knowledge, not re-verified this session. Treat as a lead, not a fact. |
| BLOCKED | Page refused (403/404/429/login) so nothing seen. |

Limits you should know before relying on this: I could not run the logged-in apps (Zoo Design Studio, Flux, Circuitly, Foxglove app, Linear app, Cursor, Devin, OpenHands, Onshape, InvenTree demo). For those, "what the user sees" comes from docs and changelogs, not from the interface. No video was watched; I did not find downloadable showcase videos I could inspect headlessly, so "dynamic" claims come from described behaviour plus the static states I captured. Where I scrubbed or clicked a live viewer, I say so.

---

## Part 1. Per tool: the distinctive patterns

### 1. Agentic CAD, EDA and code-CAD

**Zoo Design Studio and Zookeeper (KittyCAD/modeling-app)**
1. *GUI actions are edits to code.* README: "All GUI (or point-and-click) interactions should be actions performed on this code representation under the hood." You click a sketch or fillet, and a KCL line appears in the CodeMirror pane; the 3D view is a video stream from a hosted engine. Source: https://github.com/KittyCAD/modeling-app . DOCS.
2. *Selection-aware agent with self-checking snapshots.* Zookeeper knows which bodies, faces or edges you highlighted, so you select in the viewport and prompt on that selection. By default it takes snapshots to review and validate its own modifications, and it is exposed through a Zoo MCP server so other agents use the same CAD tools. Source: https://zoo.dev/blog/announcing-zookeeper (dated 2026-02-05). I saw the post's top and section headings ("Use vision for accurate results", "Plan collaboratively and answer questions", "Search the internet") in `shots/s_zoo_blog.png`; the specific claims above come from a search summary of the post, so SECONDARY for the details, not the app.
3. *Resumable agent conversations.* v1.5.5 (2026-11-09): "Automatically resume interrupted Zookeeper requests after reconnect"; PR #15255 keeps a Resume button for an unfinished response tail after reopening a conversation. Same release trail adds a **Views pane to manage scene layouts** (v1.5.4), Named Views with export, and a command palette used for modeling commands. Source: https://github.com/KittyCAD/modeling-app/releases . DOCS.
Not seen: the app itself. The design-studio landing page (`shots/s_zoo_design_studio.png`) shows only a dimensioned-callout hero.

**CADAM (Adam-CAD/CADAM)**
1. *Chat once, then drag sliders.* Prompt generates parametric OpenSCAD; the app extracts adjustable dimensions as sliders and applies changes "without AI re-generation". Source: https://github.com/Adam-CAD/CADAM . DOCS.
Nothing else distinctive found; the README says nothing about version history or mesh import.

**atopile**
1. *Build button in the editor bar, source of truth is text.* The VS Code/Cursor extension has a bottom-left ▶ build control that updates the `.kicad_pcb` even without KiCad installed; layout is handed to KiCad. Source: https://github.com/atopile/atopile . DOCS. Interface is deliberately thin; no custom viewer described. Lesson is "stay in the engineer's tool", already in your signals doc.

**tscircuit (playground, runframe, pcb-viewer)**
1. *Explicit Run plus linked view tabs.* Playground: code left, **Run** button, PCB / Schematic / 3D tabs, a warning badge ("1") on the schematic after the run. I clicked Run and switched tabs. Source: https://tscircuit.com/playground . SAW (`shots/s_tscircuit_playground.png`, `s_tscircuit_sch.png`).
2. *Cross-view jump from a pad.* pcb-viewer exposes a pad context-menu action "↗ U1 on Schematic", a toolbar with layer picker, "0 errors" counter, Rats Nest toggle, measure tool and Bounds rectangle select; right-click chooses rendering engine (WebGPU in a worker, or Canvas). Source: https://github.com/tscircuit/pcb-viewer . DOCS + SAW (`shots/s_pcbviewer_ctx.png`; WebGPU unavailable headless so the board did not draw).
3. *Schematic "Run Style Analysis" from right-click, and a System block-diagram view.* DOCS (schematic-viewer, runframe READMEs).
Runframe fixtures page (`shots/s_runframe_vd.png`) shows a Cosmos-style fixture list with Ctrl+K search and a right "inputs" panel; useful as a dev pattern, not an end-user one.

**circuit-synth, JITX, Circuitly, Flux**
- *Circuitly*: agents edit the real Altium/KiCad files in Git and open a pull request with visual diffs, risk flags and plain-language review notes; reviewers approve or request revisions with discussion tied to diffs. Source: https://circuitly.ai/ . DOCS (vendor page; the "two hours" and "80% faster reviews" figures are vendor claims). Not seen running.
- *JITX*: runs locally, design as Python, an approved model proposes code edits, simulation results feed the next edit. No viewer described. DOCS (https://www.jitx.com/).
- *Flux*: Copilot changes the schematic only with approval; an "AI Design Review" tab lets you choose checks by design phase, shows error/warning/pass rows, and clicking a flagged row jumps to the component on the board and explains the margin; you re-run to confirm. Sources: https://www.flux.ai/p/blog/introducing-the-ai-design-review-tab (DOCS), https://docs.flux.ai/reference/copilot (SECONDARY via search). Per-change accept/reject was not documented.
- *circuit-synth*: I did not examine its UI this session; your signals doc covers it as code-based KiCad only.

**CQ-editor and OCP CAD Viewer**
- *CQ-editor*: a debugger that steps through the script "and watch how your model changes", an object-stack inspector, auto-reload when an external editor saves, and a navigation cube where clicking a face animates the camera to it. Source: https://github.com/CadQuery/CQ-editor . DOCS.
- *OCP CAD Viewer (VS Code)*: every `show(...)` sends objects to a persistent viewer; hover shows geometry type and measurements (radius, centre for circular edges); topology filter keys a/v/e/f/s; Cmd-double-click hides an object and double-click on empty space restores the last hidden one; clip-plane sliders with caps only where the plane cuts a solid; measurement tools run with no Python backend; "visual debugging" shows CAD variables as they change. Source: https://github.com/bernhard-42/vscode-ocp-cad-viewer . DOCS.

**Onshape (newer features)**
- *Version graph.* Branches coloured, merges drawn as explicit lines (toggle them), open/closed dots for workspace present/deleted, filter to current branch plus parents, "Compare with base" before merge, Workspace Protection so a branch only changes through a merge. Source: https://cad.onshape.com/help/Content/Document/versions_and_history.htm . DOCS. Compare view itself: not described in what I read (MEMORY: visual overlay plus a feature list). Onshape's blog menu lists "AI Advisor" and "FeatureScript MCP"; I found no document describing how they relate to branches (a search summary suggested an agent could be handed a branch, SECONDARY, unverified).

### 2. Robotics and simulation studios

**Rerun (rerun.io viewer, v0.43.2 seen)**
1. *Linked panels around one time cursor.* Layout seen: Sources and Blueprint tree on the left, views in the middle, Selection panel on the right, a Streams (entity) tree with per-entity timeline rows at the bottom, transport controls with timeline selector and speed. Loaded the animated SO-ARM100 URDF example and a "detect and track objects" example with four synchronized views (log table, text, segmentation, video). Source: https://rerun.io/viewer . SAW (`shots/s_rerun_urdf.png`, `s_rerun_track_scrub.png`).
2. *Blueprints: the layout is data.* The layout is a saved/loadable `.rbl` file keyed by Application ID, "Reset to heuristic" versus "Reset to default" layout, and code can generate blueprints at runtime ("one view per detected anomaly"). Source: https://rerun.io/docs/concepts/visualization/blueprints . DOCS.
3. *Command palette that also opens things.* Ctrl+K lists Settings, Open file, Open from URL, Share, Copy direct link, Undo/Redo, Back/Forward in history, and accepts "a server, dataset, table, or a URL to open". Source: same. SAW (`shots/s_rerun_palette.png`).
The viewer is an egui canvas, so there is no DOM text to automate. I scrubbed by clicking the timeline; the views updated.

**Foxglove**
1. *Playback built for data, not video.* Darker timeline segments mark buffered data; on seek, "lookback" shows the most recent message per topic so panels aren't blank; latched topics persist; keys: Space, arrows for ±100 ms, Shift ±10 ms, Alt ±500 ms, Shift+Up/Down speed; trim the playback range from the command palette ("Trim start to here"). Source: https://docs.foxglove.dev/docs/visualization/playback . DOCS.
2. *Layouts as saved workspaces.* Unsaved changes get a purple indicator, Save/Revert, history with who saved when, share to team, org-curated templates for "sensor calibration or log review", JSON export, programmatic Layouts API from notebooks. Source: https://docs.foxglove.dev/docs/visualization/layouts . DOCS.
3. *Natural-language search over recordings, then "Save to Dataset".* Search bar with an AI label returns thumbnails with a "1 / 9" position, device, match time and topics; datasets reference episodes in place; events mark a moment you can share; an agents activity log lists each tool call. Source: https://foxglove.dev/ . SAW (marketing page, `shots/s_foxglove_home.png`, `s_foxglove_scroll.png`) plus DOCS. The app itself needs a login and was not seen.

**LeRobot dataset visualizer (Hugging Face Space)**
1. *Synchronized video, joint plots and a transport bar with visible key hints.* Episode list left, two camera feeds, the language instruction, plots below, floating transport with Space, ←→ frame, Shift 1 s, ↑↓ previous/next episode printed on screen. Source: https://huggingface.co/spaces/lerobot/visualize_dataset . SAW (`shots/s_lerobot_ds.png`).
2. *3D replay with a trail toggle.* A "3D REPLAY" tab drives the robot model from the recorded joints; Trail Off / Recent / Episode draws the end-effector path; "Joint Mapping (6/6 mapped)" disclosure shows how recorded channels were matched to model joints. SAW (`shots/s_lerobot_3d.png`). The mapping disclosure is a good honesty pattern.

**RoboSimStudio (studio package)**
1. *One inspector rebuilt per selected object, with two folds.* Source comments in `robosimstudio_studio/inspector.py`: live published values simply shown; static parts behind "Interface" and "Parameters", where "every field, every value, every slider" is flat, "one click is the whole difference between the simple reading and the expert one". Tunables (friction, mass sliders) are generated from the entity, not hand-wired. DOCS (source).
2. *Overlays drawn by the same reader that scores them.* `overlay.py`: "a picture computed a second way is free to disagree with the thing it depicts, and a disagreeing picture is worse than none because it is believed." Source: https://github.com/robosimstudio/robosimstudio . DOCS (source code; not run). I did not see the studio UI; it appears to be built on viser (MEMORY/inferred from a comment about viser sidebars).
Merged PR #31 also adds a lockstep clock so "the simulation waits while a graph thinks" and a pool watchdog; this is runtime, not interface.

**MuJoCo WASM demo (zalo/mujoco_wasm)**
- Scene dropdown, Pause, Reload, Reset, Load Keyframe, Noise rate/scale sliders, collapsible Actuators group, all over a live physics scene. Source: https://zalo.github.io/mujoco_wasm/ . SAW (`shots/s_mujoco_wasm.png`). Mouse drag-to-push is typical of MuJoCo viewers (MEMORY), I did not test it.

**viser, Genesis, RobotForge**
- viser: sidebar GUI handles, scene click/selection events and transform gizmos in a browser (DOCS, github.com/nerfstudio-project/viser; thin). Genesis: built-in GUI with joint control via ImGui, debug drawing and mesh point picking (DOCS, thin). RobotForge: BLOCKED (Cloudflare 403 on `shots/s_robotforge.png`); your signals doc already describes its URDF viewer.

### 3. Review and change

**deltaKi (hyperglitch)**
- View modes **A only / B only / Onion skin / Split** with an A-B blend slider ("A 50% / B 50%"), Tint A/B, Dim unchanged, Diff boxes, a legend (added, removed, modified/moved, not rendered), keys for step and fit, a "Coverage" section and a "metadata changes" toggle (UUID-only, zone-fill cache) to hide noise. Merge: select regions on the board and pick which changes to build into board A. Source: https://deltaki.hyperglitch.com/ and https://hyperglitch.com/articles/kitools . SAW (empty state only, `shots/s_deltaki.png`; I did not upload boards) plus DOCS.

**KiRI and KiCad-Diff**
- KiRI: per-page schematic compare and per-layer layout compare, shortcuts reachable with `i`. KiCad-Diff: gallery of layer pairs, combined diff, "Triptych" (before, after, combined), before/after pair pans and zooms together, commit picker. Sources: https://github.com/leoheck/kiri , https://github.com/Gasman2014/KiCad-Diff . DOCS. KiRI's "onion skin" claim comes from a Hackaday search result (SECONDARY). I did not examine 0x12net/kdif beyond your earlier doc.

**AllSpice**
- Review findings are comments with severity, claim, observed condition, requirement, consequence, evidence, suggested repair and linked datasheets; clicking a schematic snippet opens the design review at the component and the change that caused it; thumbs-down marks a finding wrong and suppresses it on later runs; "Reference in New Issue". Component Details table sortable and exportable. Source: https://learn.allspice.io/docs/drcy-review . DOCS. The visual-diff docs page 404'd, so slider/overlay modes at AllSpice are unconfirmed.

**PartCAD**
- Digital Thread view in the IDE/extension, `pc qual test` checks (overlaps, untoleranced faces, optional MuJoCo/Gazebo run), a Claude Code `/pc:gen` that writes the part, renders it and checks the render against the request, and generated assembly instructions with BOM. Source: https://github.com/partcad/partcad . DOCS. Interactive viewer not described.

**InvenTree UI**
- 1.0 React UI: customizable dashboard widgets you add/remove/rearrange, plugins render their own UI components, hotkey hook that shows hotkeys in the UI. Source: https://inventree.org/blog/2025/09/15/1.0.0 (SECONDARY via search). Spotlight search and barcode scanning UI were not verifiable; demo requires login, so skipped.

### 4. Agent workbenches and live-agent UIs

**Linear (agents and keyboard)**
1. *Agents as assignable teammates with a typed activity stream.* Activity types: thought, action (sent twice: started "Searching", finished "Searched" with result), elicitation, response, error; thoughts and actions can be ephemeral (replaced by the next activity); session states pending / active / error / awaitingInput / complete / stale set automatically; an agent that is silent for 10 s is marked unresponsive. Sources: https://linear.app/developers/agent-interaction , https://linear.app/docs/agents-in-linear . DOCS. UI rendering not described; not seen.
2. *Peek.* Space previews the focused issue from any list; hold Space for temporary peek; J/K move; right-arrow in Cmd+K adds a preview pane. Source: https://linear.app/docs/peek . DOCS.

**LangGraph Studio, time travel and Agent Inbox**
1. *Fork from a checkpoint.* Replay re-runs after a past checkpoint; fork edits state at that checkpoint and creates a new branch, original history intact. Source: https://docs.langchain.com/oss/python/langgraph/use-time-travel . DOCS (API; the Studio UI steps weren't described in what I read).
2. *Approval inbox.* Each interrupt shows action name, args and markdown description with only the allowed buttons: Accept, Edit (modify args), Respond (free text), Ignore. Source: https://github.com/langchain-ai/agent-inbox . DOCS. Not seen running (needs a deployment URL and key).

**Cursor 2/3**
- Sidebar of agents and plans, up to eight parallel agents each in a git worktree or remote box, plan mode where one model plans and another builds, multiple parallel plans to compare, all changes of an agent reviewed in one place, browser tool where you select a page element and send its DOM to the agent, sandboxed terminals with no network by default. Source: https://cursor.com/changelog/2-0 . DOCS. Cursor 3 (2026-04-02): Agents Window, agent tabs, tiled layout, Design Mode (click and annotate UI elements); SECONDARY, I did not verify against primary text.

**Claude Code on the web / desktop**
- Session list with live progress; steer or answer while it runs; queued message you can take back with ✕; a "Changes" card (+42 −18) opening a diff view with inline line comments sent with the next message; compare against any branch; share Private/Team; teleport into terminal; Auto-fix watches CI and review comments and asks before ambiguous changes. Source: https://code.claude.com/docs/en/claude-code-on-the-web . DOCS.

**Devin**
- A Progress tab that logs shell, edits and browser together; clicking a command jumps the session to that point; a read-only **side chat** that can read the codebase without interrupting; take over by pausing then editing in the IDE and telling the agent. Source: https://docs.devin.ai/work-with-devin/devin-session-tools . DOCS.

**OpenHands and Codex cloud**
- OpenHands: chat panel with Changes, VS Code, Terminal, App and Browser tabs (older docs, SECONDARY via search); Agent Canvas control center switches local/remote/cloud agents and any ACP agent (https://github.com/All-Hands-AI/OpenHands, DOCS). Codex cloud: per-task workspace, changed files and test results, follow-ups, PR (https://learn.chatgpt.com/docs/cloud, DOCS; page too thin to describe the view).

### 5. Command and graph-centric power tools

**Obsidian graph**
- Hover highlights a node's neighbours; filters, colour groups from searches, forces sliders, a **local graph with a depth slider**, and a time-lapse that replays creation order. Source: https://obsidian.md/help/plugins/graph . DOCS.

**marimo (reactive notebook) and Observable**
- marimo: a static dependency graph decides what re-runs; "lazy" mode marks downstream cells stale instead of running them; UI widgets bind to Python values with no callbacks; the notebook is a plain `.py` so it diffs in git; `marimo run` serves it as an app with code hidden. Source: https://github.com/marimo-team/marimo . DOCS; loading page `shots/s_marimo.png` SAW (only a spinner). Observable: BLOCKED (429); reactive-cell behaviour is MEMORY.

**Grafana and Foxglove panel layouts**
- Grafana Play loads with a left nav, Ctrl+K search, a "Viewing" mode toggle with Edit/Share nearby, and panels that load progressively. SAW (`shots/s_grafana_play2.png`). I did not drill into panel editing, so the "composable panels" claim for Grafana is MEMORY. Foxglove's drag-topic-into-panel, `,` for panel settings and per-panel JSON import/export are DOCS (https://docs.foxglove.dev/docs/visualization/panels/introduction).

**Figma multiplayer**
- The only page I could fetch (engineering blog) described the sync engine, not cursors or follow mode. Live cursors, named presence, "observation/follow" of another person's viewport and comment pins are MEMORY.

**Logseq** — not researched this session. Treat as absent.

---

## Part 2. Pattern catalogue (24 patterns, grouped)

For each: who does it, how it could apply to HS, and gimmick risk for engineers. "HS" objects named here come from your docs: revisions, evidence claims with authority levels, release blockers, substitutions, KiCad checks, kdif diff, FieldDeck display case, SO-ARM100 servo case.

### Time and replay

**P1. One shared time cursor across heterogeneous views.** Rerun, Foxglove, LeRobot (all SAW or DOCS). *HS:* for any run that has time (servo load trace, thermal, motion study, a recorded test), one scrubber drives the 3D model, the plot and the check status together. Time can also be revisions: dragging across revisions 1 to 4 moves geometry, BOM and claims at once. *Risk:* low where data is truly temporal; gimmicky if you invent a time axis for static review.

**P2. Per-entity timeline rows (who changed or measured what, when).** Rerun Streams panel (SAW), Foxglove device timeline (SAW marketing). *HS:* rows per part or requirement, dots where a measurement, datasheet, supplier offer or check result landed or went stale. Shows evidence age at a glance. *Risk:* medium; needs real timestamps on every record, otherwise the rows are empty decoration.

**P3. Lookback/latched last value on seek.** Foxglove (DOCS). *HS:* when viewing an old revision or stepping time, each claim shows its last known value with its age ("measured rev 3, 12 days") instead of blanking or silently showing current. Strong match to "authority is never implicitly upgraded". *Risk:* low.

**P4. Event markers and search-to-moment.** Foxglove events and semantic search with "Save to Dataset" (SAW marketing, DOCS); Rerun history navigation (SAW). *HS:* mark "ERC failed", "supplier offer expired", "agent proposal made" on the timeline and jump to them; search across evidence by meaning ("servo with 12 V stall torque above X"). *Risk:* medium-high for semantic ranking: engineers distrust results with no stated reason. Show the matched field and keep exact-parameter filters first.

**P5. Trail toggle (Off / Recent / Episode).** LeRobot 3D replay (SAW). *HS:* motion study of a salvaged mechanism: path of an end point over the cycle, to judge reach and clearance. *Risk:* low but narrow; only matters for kinematic cases.

### Linked multi-view

**P6. Click an element, jump to the same thing in another view.** tscircuit pad menu "↗ U1 on Schematic" (DOCS, SAW toolbar), InteractiveHtmlBom linked selection (your signals doc), Flux review row to board component (DOCS), AllSpice snippet to review (DOCS). *HS:* part row to geometry to schematic symbol to BOM line to supplier offer. Where there is no mapping, the row says "not linked" (already in the Opus brief). *Risk:* low, high value; the failure mode is a half-working link that implies a mapping exists.

**P7. Inspector rebuilt for the selected object, live values up top, static detail behind one fold.** RoboSimStudio (DOCS source), Rerun Selection panel (SAW). *HS:* select a part and see live evidence status first, then "Interface" and "Parameters" folds with every field flat. *Risk:* low.

**P8. Draw overlays from the same function that makes the verdict.** RoboSimStudio overlay principle (DOCS source). *HS:* a clearance or keep-out volume on the CAD view is rendered from the check's own geometry, never from a second computation. Pairs with "a disagreeing picture is believed". *Risk:* low; mostly an engineering rule, costs nothing visually.

### Command and keyboard flow

**P9. Command palette as the verb layer, and also an open-anything box.** Rerun (SAW), Zoo (DOCS changelog), Foxglove (DOCS), Linear (SECONDARY), marimo (SAW icon only). *HS:* "Substitute part...", "Run ERC on rev 3", "Compare rev 3 to 4", "Open part by MPN", "Open layout: Sourcing", "Ask agent about selection", plus paste a GitHub URL to start the tool-factory flow. Commands that are unavailable show why. *Risk:* low; but only worth building after the verbs exist. A palette over three actions is theatre.

**P10. Peek and keyboard transport with printed key hints.** Linear peek (DOCS), LeRobot on-screen Space / arrows / Shift (SAW), Foxglove keys (DOCS), OCP viewer topology keys (DOCS). *HS:* Space on a BOM row peeks at requirement, identified part, offers and stock without leaving the list; J/K walks the findings. *Risk:* low; do not rely on hidden shortcuts, print them.

### Agent visibility and approval

**P11. Typed activity stream with ephemeral thoughts and past-tense actions.** Linear (DOCS), Devin Progress tab with click-to-jump (DOCS), Foxglove agent activity log (SAW marketing). *HS:* MCP agent work shown as thought / action / elicitation / response / error rows; "Searching KiCad parts" becomes "Searched ... 14 results" with a link to the artefact; clicking a step jumps to what it touched. *Risk:* medium; streams of "thoughts" become noise. Keep actions and results, fold thoughts.

**P12. Approval queue with Accept / Edit args / Respond / Ignore.** Agent Inbox (DOCS), Flux (approval before schematic changes, DOCS), Cursor sandboxing (DOCS). *HS:* an inbox of agent proposals ("swap R12 to 0402", "run vetted repo X in sandbox"), each editable before apply, with the scope visible. *Risk:* approval fatigue; batch low-risk items, force a stop on anything that raises authority.

**P13. Sessions that survive navigation, with queue-and-unsend, read-only side questions and take-over.** Zoo Resume (DOCS), Claude Code web queued message ✕ (DOCS), Devin side chat and take-over (DOCS). *HS:* leaving the page never loses a proposal or its checks (already in your signals doc); you can ask a read-only question mid-run. *Risk:* low.

**P14. Parallel candidate agents, each isolated, compared in one table.** Cursor parallel agents and multiple plans (DOCS), Claude Code parallel cloud sessions (DOCS), Onshape branch-per-idea (DOCS). *HS:* try three substitute servos as three branches, each with its own checks, shown as a comparison with unresolved items per candidate. *Risk:* medium; easy to look impressive while all three are "insufficient evidence". Show the missing-evidence column first.

**P15. Selection-aware prompting.** Zookeeper (SECONDARY), Cursor Design Mode (SECONDARY). *HS:* select a connector or mounting hole, the agent's scope chip reads that selection, and the question "what else fits here" is bound to it. *Risk:* low; main risk is the agent silently widening scope beyond the chip.

**P16. The agent shows its own verification.** Zoo snapshots (SECONDARY), PartCAD `/pc:gen` render-and-check (DOCS), Flux re-run review (DOCS). *HS:* every agent proposal carries the checks it ran, with stale ones flagged; failed checks stay visible. *Risk:* low.

### Graph and provenance navigation

**P17. Evidence graph with a depth slider and colour by authority.** Obsidian local graph depth, groups (DOCS). *HS:* claim to evidence to source file to revision, local to the selected claim, depth 1 to 3, coloured by authority level, hover highlights the chain. *Risk:* high if it is a global force-directed hairball (Obsidian's global graph is famously decorative). Use only the local, depth-limited form and always offer the list view.

**P18. Revision graph with explicit merges and protected main.** Onshape (DOCS), LangGraph fork-from-checkpoint (DOCS). *HS:* project revisions plus agent branches drawn as a graph; "fork from revision 3 with a changed assumption" makes a new branch, original untouched; main only changes via reviewed merge. *Risk:* low-medium; keep the graph filterable (current branch plus parents).

### Compare and diff

**P19. Diff mode switch: A only / B only / onion skin with blend slider / split, plus change legend and stepping.** deltaKi (SAW empty state, DOCS), KiCad-Diff triptych (DOCS), KiRI (DOCS), Onshape visual plus list compare (DOCS). *HS:* surface kdif and enclosure geometry diffs in one component; the slider blends revisions; keys step through changes. *Risk:* low; the dynamic feel is real and the work is useful.

**P20. A "Coverage" panel and noise toggle on every diff.** deltaKi (SAW): Coverage section, "metadata changes (UUID-only, zone fill cache)" hidden by default, "not rendered" legend entry. *HS:* every diff states what it cannot see (no schematic mapping, no electrical meaning), matching your "kdif proves delivery, not electrical substitution". Direct fit. *Risk:* none; this is the pattern most aligned with the project's rule.

**P21. Finding cards: claim, observed, requirement, consequence, evidence, repair, with "wrong" feedback that suppresses repeats.** AllSpice (DOCS), Flux AI Design Review rows (DOCS). *HS:* release blockers and check results in this structure with a jump to the object. *Risk:* "mark as wrong to suppress" must not hide a real blocker; log suppression and keep it reversible.

### Layouts the user composes

**P22. Layouts as saved, shareable, versioned files, generated by code or agent.** Rerun blueprints `.rbl` and runtime-generated views (DOCS, SAW viewer), Foxglove layouts with unsaved indicator and history (DOCS), Zoo Views pane (DOCS changelog), Cursor tiled agents (SECONDARY). *HS:* "Sourcing", "Mechanical fit", "Electrical review" layouts of the same panels; an agent opens the layout that fits a finding. Unsaved-layout indicator and "reset to default" are worth copying. *Risk:* medium; a flexible layout engine is a lot of build. A small fixed set of presets plus resize is probably enough first.

**P23. Assumptions as live parameters (sliders) over a derived result.** CADAM (DOCS), MuJoCo demo sliders (SAW), marimo widgets (DOCS), Foxglove Variable Slider (DOCS list only). *HS:* load, voltage, duty cycle as sliders that recompute margin; results derived from assumptions are labelled as such. *Risk:* high if sliders make an estimate look measured. Mark slider-driven values "assumed" and keep them out of authority upgrades.

### Live collaboration

**P24. Presence, anchored comments and shareable deep links.** Figma cursors and follow mode (MEMORY), Flux multiplayer (MEMORY), Rerun "Share"/"Copy direct link" (SAW palette), Foxglove share timestamp (DOCS), Claude Code shared sessions (DOCS; viewer does not update live). *HS:* for a small team: who is looking at this revision, comments pinned to a part or a claim, a link that restores revision, layout, selection and time. Live cursors are probably the least valuable piece. *Risk:* cursors and follow mode are gimmicky for a two-person hardware team and bring sync complexity; deep links and anchored comments are not.

### Notebooks and reproducible runs

**P25. Reactive evidence graph with stale marking, not silent re-run.** marimo lazy mode and dependency graph (DOCS); Observable (MEMORY). *HS:* change a measurement or datasheet value and downstream checks turn "stale" with the reason, rather than recomputing or keeping their old green. This is the most natural fit with "authority is never implicitly upgraded". *Risk:* low if staleness is shown clearly; high if checks auto-rerun and quietly flip.

**P26. Everything is a plain file you can diff; GUI actions emit file changes; one-click "app mode".** Zoo code-first (DOCS), marimo `.py` plus `marimo run` (DOCS), Rerun `.rbl` and `.rrd` (DOCS), tscircuit "Copy URL" (SAW). *HS:* every GUI action shows the project-file diff it produced; a reproducible bench file replays a run read-only for a reviewer. CQ-editor and OCP "visual debugging" (DOCS) suggest a step-through view of a splice or check pipeline: step, see the object, see the intermediate value. *Risk:* low; a step-through debugger for the pipeline is real value only if the pipeline has meaningful steps.

---

## Part 3. What looks alive but may be gimmicky for engineers

1. Global force-directed graphs and "time-lapse" growth animations (Obsidian). Fine as a screenshot, weak for decisions.
2. Live multiplayer cursors and follow mode for tiny teams.
3. Streaming "thoughts" from the agent; keep actions and results.
4. Semantic search results without a stated reason or exact-parameter fallback.
5. A palette or layout engine built before there are verbs and panels worth composing.
6. Sliders that make assumptions look measured.
7. Parallel agent panels that all end "insufficient evidence"; the missing-evidence column should lead.
8. Smooth animation as a substitute for state. Zoo's v1.5.5 changelog says "Many UI animations removed", which is a small data point that the CAD audience prefers speed to polish (DOCS).

## Part 4. Short list I would prioritise for HS

Ordered by fit with "evidence first" and by effort:
1. P20 coverage panel on diffs, then P19 mode switch with blend slider (reuses the kdif capture you already have).
2. P3 lookback with age on every claim, and P25 stale marking.
3. P6 linked selection with honest "not linked" rows, with P7 inspector.
4. P11/P12/P13 agent run view plus approval inbox that never loses state.
5. P9 command palette once five or six real verbs exist.
6. P1/P2 time cursor for runs that truly have time (SO-ARM100 motion is the natural first case).
7. P18 revision/branch graph for agent proposals.

## Part 5. Screenshot index (what each shows)

| File | Shows |
|---|---|
| `shots/s_rerun_urdf.png` | Rerun with an animated SO-ARM100 URDF: Sources/Blueprint, 3D view, Selection panel, Streams timeline |
| `shots/s_rerun_track_scrub.png` | Rerun, four linked views at one frame (table, text, segmentation, video) |
| `shots/s_rerun_palette.png` | Rerun command palette over the welcome screen |
| `shots/s_lerobot_ds.png` | LeRobot visualizer: cameras, plots, transport bar with key hints |
| `shots/s_lerobot_3d.png` | LeRobot 3D replay with trail toggle and joint mapping disclosure |
| `shots/s_deltaki.png` | deltaKi empty state: onion skin / split controls, legend, Coverage |
| `shots/s_tscircuit_sch.png` | tscircuit playground after Run, schematic tab with warning badge |
| `shots/s_pcbviewer_ctx.png` | tscircuit pcb-viewer toolbar and right-click menu (board did not draw headless) |
| `shots/s_runframe_vd.png` | runframe fixture browser with inputs panel |
| `shots/s_mujoco_wasm.png` | MuJoCo WASM demo with simulation sliders |
| `shots/s_foxglove_home.png`, `s_foxglove_scroll.png` | Foxglove marketing: AI search, results, per-result detail with Save to Dataset |
| `shots/s_grafana_play2.png` | Grafana Play: nav, Ctrl+K, Viewing mode |
| `shots/s_zoo_design_studio.png`, `s_zoo_blog.png` | Zoo marketing pages only |
| `shots/s_langgraph_studio.png`, `s_marimo.png` | LangSmith Studio docs page (feature list only); marimo loading spinner. Low information |
| `shots/s_linear_home.png`, `s_robotforge.png` | Captured but not viewed by me; RobotForge returned a Cloudflare 403 title. Do not rely on them |

Scripts: `shoot.cjs`, `rerun2.cjs`, `batch2.cjs`, `misc.cjs`, `rf.cjs`, `pv.cjs` in the same directory.
