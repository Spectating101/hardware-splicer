# Hardware Splicer — REAL cyberdeck capability trial (20 October 2026)

**Verdict: FAIL to produce an engineering-ready device.** This is an **actual invocation** of the HS backend and its internal AI and design endpoints against a practical project, not synthetic test fixtures. The material facts are in [`evidence_summary.json`](./evidence_summary.json), including **SHA-256 hashes of thirteen original request, response and external validation files** preserved on the Optiplex trial machine.

## Exact assignment

> Engineer a self-contained Linux field-electronics cyberdeck with display, keyboard, USB access, offline documentation, remote access, a safe commercial USB-C power-bank supply, a realizable enclosure, and a *trial target* under US$250 before tools/shipping.

The budget was an **evaluator-imposed constraint**, not a confirmed price or user-selected budget. No components, wiring map, manufacturer part numbers, enclosure dimensions, or design source were supplied at the start. No physical device was assembled, energized, purchased or tested.

## Method: do not confuse evaluator, model and product

- **HS product:** canonical FastAPI backend on Optiplex, isolated project store; real endpoints, persistent revisions, internal planning, composition and source ingestion.
- **External operating agent:** GitHub Copilot CLI; instructed to use HS's real HTTP API, not hand-write a design or modify product source. Its first default profile exceeded quota before tool use; a working `copilot-spectator26` identity performed the operator attempts. The agent made HTTP calls whose responses are retained. The generated response was truncated after approximately 90 seconds on each Copilot operator run; it did not finish a complete design.
- **Evaluator intervention #1:** when the agent's intake did not persist a project, the evaluator created **only the goal/constraints** at canonical project revision 1. This assisted initialization must not be attributed to HS autonomy.
- **Evaluator intervention #2:** after HS's Qwen-backed AI session failed, the evaluator implemented an **explicit opt-in, tools-disabled Copilot CLI provider** for the existing HS text-client. Test and live results are below. This made AI sessions functional, not their engineering conclusions correct.
- **Evaluator intervention #3 / distinct source condition:** the evaluator cloned the public [sector07-dev/RPI_DEV](https://github.com/sector07-dev/RPI_DEV) cyberdeck hardware repository at commit `ebdfcff` and supplied three unmodified CAD/PCB sources: one KiCad schematic, one KiCad PCB, and one STL enclosure file. This tests whether **HS can actually consume supplied real engineering assets**, *not* whether HS independently discovered them.
- **Independent control:** `kicad-cli 9.0.2` ran ERC and DRC against the cloned KiCad files directly. These are evaluator checks, **not successful HS engineering actions**.

## Evidence-backed results

| Objective-level requirement | Product result | Verdict |
| --- | --- | --- |
| Make sense of the cyberdeck objective and retain project truth | The initial standalone `/v1/intake-run` returned `ok:false` but produced **88 output files** including PCB/Gerbers, SCAD and STEP from a `hardware_splicer_project` generic scaffold with **zero bill-of-materials parts** | **FAIL** on target-specific intake; generic artifacts misleading |
| Persist the real goal in a project | Evaluator seeded `/v1/projects/{id}/snapshot` rev 1; backend persisted revisions thereafter | **PASS** with human/evaluator assistance |
| Generate a native project engineering plan | `/v1/projects/{id}/engineering/plan` returned 200, persisted rev 2, but architecture was `unresolved`, no build ID, zero source claims, seven unknown engineering checks | **BLOCKED** |
| Native AI project session | First request failed 503 (`qwen_http_error`); first Copilot-bridge attempt failed 422 due malformed `actions[*].inputs`; explicit schema guidance and strict validation allowed 200 on retry and rev 3 | **PASS** after *two code-level interventions*, proposals only |
| Automatically execute actual engineering actions | Native AI session generated 3 architecture concepts and 6 **proposed, unexecuted** actions; source-backed session generated 5 further unexecuted actions | **FAIL** as autonomous end-to-end workflow; deliberate review boundary remains in force |
| Compose a device-specific circuit | `/v1/compose/agent-loop` returned HTTP 200 but `ok:false`, `need >=2 modules, got []`, no KiCad PCB or netlist; it did not design a cyberdeck circuit | **FAIL** |
| Read real cyberdeck KiCad + STL sources | `/sources/ingest-file` **retained and hashed** all three originals (HTTP 201); `/sources/{id}/parse` then returned `status: skipped`, `inventory-only`, zero derived sources for every file | **PASS retention / FAIL content extraction** |
| Independent electrical checks on real third-party design | KiCad external control: **43 ERC** and **16 DRC** findings, exit 5; mostly missing library/footprint references in local setup. No validated correctness claim. | **Control available, NOT exercised by HS** |
| Generate a source-backed PCB, dimensioned enclosure, verified BOM and instructions | No target-specific HS netlist, PCB, CAD modification, BOM, sourced interface verification or physical assembly | **FAIL** |

**Quality-metric warning:** The generic standalone intake's dashboard reported `build_ready:true`, `drc_pass:true`, `gerber_ready:true` even though its primary result was `ok:false` and it had no identified cyberdeck components. These are generic-scaffold metrics, **not proof that HS engineered the requested device**. Project `claimable:false` and release gates remained correctly closed.

## What the explicit Copilot provider actually fixed

The added `HARDWARE_SPLICER_LLM_PROVIDER=copilot_cli` route invokes the existing configured `copilot-spectator26` identity **without shell/file/MCP tools**. Its output is treated only as candidate JSON, checked against the HS action schema, and remains non-authoritative. The default provider selection is unchanged. With this opt-in, the HS backend produced a valid real project AI session (HTTP 200, provider `copilot_cli`, 3 architecture concepts, 6 typed actions). After uploading real sources it produced another session that correctly recognized the parser had skipped them; it did not fabricate pinouts or dimensions.

**This repaired AI reasoning connectivity only.** The AI still cannot exercise arbitrary project engineering endpoints by writing prose; the native session operates under explicit proposal/review/preview policy. There is no evidence of a generalized autonomous design agent.

## Real engineering blockers, ranked by what must be fixed

1. **Source semantics unavailable:** make HS's canonical source pipeline actually parse/reference KiCad schemas/PCB netlists and externally validated STL/STEP geometry rather than only hash-registering files. Bind extracted pins, connectors, component IDs, dimensions and source evidence to the project.
2. **Project-to-tools gap:** add an explicit, auditable software-only operator progression that can use discovered source facts to choose components, generate actual designs, run HS/KiCad verification, revise failed artifacts and persist them to the SAME project. Respect review and physical-authority boundaries; do not bypass them.
3. **Target-specific truth gates:** suppress or prominently invalidate `build_ready`/`drc_pass`/Gerber success language when only an unrelated generic scaffold with no matched target components exists. Verify completion against the user's functional objective, not generic artifact existence.
4. **Source-backed engineering outputs:** select actual compute, display, USB and certified power components with manufacturer interfaces and conservative supplier costs. Produce a dimensioned enclosure and matching wiring/circuit outputs, then rerun the cyberdeck without evaluator-curated design decisions.

No other domain or test project is needed before addressing these concrete failures on this same cyberdeck assignment. The drone, repair-arbitrage and utility portfolios remain separate objectives.

## Inspect original experiment

The isolated experiment root on Optiplex is `/tmp/hs-capability-trial-20261020/` (temporary; not a durable public artifact), containing original agent HTTP requests/responses, project and provider logs, generic generated output, public cloned source assets, canonical ingestion/parse responses, and KiCad ERC/DRC reports. The hashes and distilled statuses in [`evidence_summary.json`](./evidence_summary.json) are the Git-tracked audit record; upstream third-party engineering binaries and complete model transcripts are **not redistributed** in this repo.

**Source revision:** trial code from `e7888b22` before explicit connector/validation changes, then tested connector/validation patch on this branch. **No physical device, finished PCB, usable enclosure, model-authorized fabrication or demonstrated profit.**
