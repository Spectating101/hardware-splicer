# Circuit-AI Handoff - 2026-05-24

This handoff exists because there are two Circuit-AI working copies, and the project has accumulated a lot of context across long agent sessions.

## Start Here

Canonical repo for future work:

```text
/home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai
```

Treat this as the real continuation point. It is the richer Circuit-AI repo under Hardware-Splicer, with backend engines, functional salvage, circuit graph reasoning, DeepSeek smoke scripts, docs, tests, and integration files.

Secondary/standalone repo:

```text
/home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI
```

Treat the standalone repo as a patch source only. It contains some recent frontend/library/DeepSeek validation work that should be carefully ported into the canonical repo, but it is not the main continuation target.

For the product direction, read these first:

- `docs/CIRCUIT_AI_MASTER_BLUEPRINT.md`
- `docs/SALVAGE_TO_PRODUCT_WORKFLOW.md`
- `docs/VALUE_AND_WORKFLOWS.md`
- `docs/CERTAINTY_LEDGER.md`
- `docs/BOARD_SESSION_LAUNCH_LOOP.md`
- `docs/COMPETITIVE_ENGINE_CATCHUP.md`
- `docs/RESEARCH_TECH_RADAR.md`

## Product Intent

Circuit-AI is not just "upload one PCB photo and label components." That is too shallow for the intended venture.

The real target is a circuit and hardware intelligence layer for repair, reuse, salvage, upcycling, and machine/gadget composition. A user may have a physical board, junk electronics, spare modules, e-commerce parts, or an existing device. Images are scans and evidence, not the only source of truth. The system should build confidence through multiple evidence types:

- photos from different angles
- board markings and chip labels
- connector and pin evidence
- datasheets and known module pinouts
- circuit graph/netlist/layout evidence when available
- user measurements such as voltage, continuity, current, logic level, and functional bring-up
- safety and uncertainty gates before any splice or reuse recommendation

The valuable loop is:

1. Identify the board, modules, functions, and probable role.
2. Build a functional graph of power, signal, connectors, ICs, sensors, actuators, and reusable blocks.
3. Decide what is repairable, reusable, extractable, or unsafe.
4. Produce a certainty ledger and measurement plan.
5. Convert proven reusable functions into splice/build plans.
6. Feed verified contracts into Hardware-Splicer, Mecha-Splicer, and later physical fabrication/enclosure flows.
7. Capture user outcomes as training/eval data.

## Repo Split Facts

Canonical nested repo:

```text
path:   /home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai
branch: master
remote: origin https://github.com/Spectating101/circuit.ai.git
remote: ultraplan https://github.com/Spectating101/optiplex-optima.git
HEAD:   8d31e52 feat(modules): library 144 -> 154 - second web-research wave
state:  ahead of origin; dirty worktree
```

Standalone repo:

```text
path:   /home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI
branch: master
remote: origin https://github.com/Spectating101/circuit.ai.git
HEAD:   663e984 feat(library): /library page - browseable encyclopedia of all 154 modules
state:  ahead of origin; dirty worktree with additional uncommitted fixes
```

Important: `/home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer` itself is not the Circuit-AI git root. Git operations for Circuit-AI should run from:

```text
/home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai
```

## Canonical Repo Dirty State When This Was Written

The canonical repo already had uncommitted work. Do not reset or overwrite it blindly.

Modified:

```text
.claude/settings.local.json
circuit-ai-frontend/components/site-header.tsx
data/datasheets/metadata.json
docs/README.md
pyproject.toml
setup.cfg
src/api/v1/main.py
src/config/__init__.py
src/engines/cam/splicer_engine.py
src/engines/machine_system_engineering.py
src/engines/mechatronic_context.py
src/engines/system_structure_extractor.py
src/intelligence/board_session_store.py
src/intelligence/salvage_splice_planner.py
tests/unit/test_salvage_splice_planner.py
```

Untracked:

```text
circuit-ai-frontend/app/library/
docs/CIRCUIT_AI_MASTER_BLUEPRINT.md
scripts/deepseek_circuit_reasoning_smoke.py
src/engines/board_intelligence.py
src/engines/circuit_board_graph.py
src/intelligence/circuit_ai_reasoner.py
src/intelligence/functional_salvage.py
src/intelligence/functional_salvage_workflow.py
tests/integration/test_hardware_splicer_e2e.py
tests/unit/test_board_intelligence_workflow.py
tests/unit/test_circuit_ai_reasoner.py
tests/unit/test_circuit_board_graph.py
tests/unit/test_functional_salvage_workflow.py
tests/unit/test_hardware_splicer_integration.py
tests/unit/test_machine_system_power_distribution.py
```

## Standalone Work That Should Be Ported

The standalone repo has recent work that was implemented and verified there, but has not yet been cleanly merged into the canonical repo.

Files changed in standalone:

```text
.env.example
circuit-ai-frontend/app/globals.css
circuit-ai-frontend/app/library/page.tsx
circuit-ai-frontend/lib/jarvis/client.ts
circuit-ai-frontend/lib/modules/module-library.ts
circuit-ai-frontend/lib/salvage/plan-to-graph.ts
circuit-ai-frontend/package.json
circuit-ai-frontend/scripts/validate-module-library.cjs
```

What those standalone changes contain:

- DeepSeek text-provider support in `circuit-ai-frontend/lib/jarvis/client.ts`
  - OpenAI-compatible endpoint: `https://api.deepseek.com/chat/completions`
  - Default model: `deepseek-v4-flash`
  - Env vars: `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_THINKING`, `JARVIS_TEXT_PROVIDER`
  - DeepSeek currently covers text flows such as `chat` and `project`
  - Vision flows such as `identify` and `salvage` still need Anthropic or another vision provider
  - Provider selection should not silently fall back to Mistral when `JARVIS_TEXT_PROVIDER=deepseek` is explicitly selected but no DeepSeek key exists
- Complete `capabilityTags` coverage in `circuit-ai-frontend/lib/modules/module-library.ts`
  - Standalone runtime count: 154 modules
  - Missing capability tags after fix: 0
- New validator script: `circuit-ai-frontend/scripts/validate-module-library.cjs`
  - Added npm script: `validate:library`
  - Checks module count, duplicate IDs, pinouts, source counts, wave-2 modules, capability search, 14 salvage translators, electrical safety, geometry DRC, and KiCad serialization
- `/library` page polish
  - Human-readable category labels
  - Search/category/capability filtering
  - Slide-in detail drawer
  - Full pinout table
  - Warnings/source provenance
  - Header-level "Open in build" CTA so users do not have to scroll to the drawer footer
  - Existing build preload route: `/build?modules=mcp23017-ioexp`
- Global CSS reset in `circuit-ai-frontend/app/globals.css`
  - `box-sizing: border-box`
  - `html, body { margin: 0; min-height: 100%; }`
  - Fixed mobile horizontal overflow in standalone Playwright checks
- Removed unused `powerChain` local from `circuit-ai-frontend/lib/salvage/plan-to-graph.ts`
- Updated root `.env.example` with DeepSeek/Mistral vars

Port carefully because the canonical repo already has its own untracked `circuit-ai-frontend/app/library/` and broader backend work. Inspect diffs instead of copying over files blindly.

## Verified Standalone Baseline

The following was tested in the standalone repo after the recent patch:

```text
cd /home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI/circuit-ai-frontend
npm run validate:library
npm run lint
rm -rf .next && npm run build
```

Results:

- `npm run validate:library` passed
  - `OK module library: 154 modules, 14 salvage translators`
  - source counts:
    - `curated-original`: 21
    - `curated`: 23
    - `ingested-kb-board`: 4
    - `ingested-kb-ic`: 2
    - `ingested-datasheet-pdf`: 5
    - `ingested-component-db`: 87
    - `ingested-pinout-extract`: 12
  - nonfatal warning: 25 electrical info/warn findings remain across strict recipes
- `npm run lint` passed
  - 22 existing warnings, 0 errors
- clean Next build passed
- Playwright flow passed:
  - `/library` desktop rendered
  - search `MCP23017`
  - open detail drawer
  - header "Open in build" CTA visible and clickable
  - route changed to `/build?modules=mcp23017-ioexp`
  - build canvas showed `1 modules - 0 wires`
  - mobile viewport `390x844` had no horizontal overflow after CSS reset
  - no relevant console warnings/errors in that rendered flow
- Jarvis text smoke in standalone used Mistral because no standalone DeepSeek key was configured
  - parsed JSON returned successfully
  - model reported: `mistral-small-latest`

The standalone dev server used for verification was stopped.

## Canonical Environment Notes

The canonical repo has a DeepSeek key in:

```text
/home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai/.env.local
```

Do not print secrets. When testing, load the env into the shell without echoing it.

The canonical frontend did not have all frontend dependencies available when checked. A TypeScript import probe from `circuit-ai-frontend` failed with:

```text
Cannot find module 'typescript'
```

So before frontend validation in the canonical repo, expect to run dependency installation from:

```text
/home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai/circuit-ai-frontend
```

Use the repo's lockfile/package manager pattern. If it is npm, run `npm ci`.

## Immediate Continuation Plan

1. Work only from the canonical nested repo unless explicitly comparing patches:

```text
/home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai
```

2. Snapshot status before editing:

```bash
rtk git status --short
rtk git log --oneline -8
```

3. Diff standalone against canonical for the known patch files:

```bash
# Run from the canonical repo.
rtk git diff --no-index \
  /home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI/circuit-ai-frontend/lib/jarvis/client.ts \
  /home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai/circuit-ai-frontend/lib/jarvis/client.ts
```

Repeat for:

```text
.env.example
circuit-ai-frontend/app/globals.css
circuit-ai-frontend/app/library/page.tsx
circuit-ai-frontend/lib/modules/module-library.ts
circuit-ai-frontend/lib/salvage/plan-to-graph.ts
circuit-ai-frontend/package.json
circuit-ai-frontend/scripts/validate-module-library.cjs
```

4. Port the standalone patch into canonical with merge awareness:

- Preserve canonical backend work.
- Preserve canonical untracked library page work unless the standalone page has a clearly better section.
- Do not overwrite `docs/CIRCUIT_AI_MASTER_BLUEPRINT.md`.
- Add the validator script and npm script.
- Bring over DeepSeek text-provider logic.
- Bring over `capabilityTags` completion only after confirming it does not remove newer canonical entries.
- Bring over the CSS reset.

5. Run canonical frontend checks:

```bash
cd /home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai/circuit-ai-frontend
rtk npm run validate:library
rtk npm run lint
rtk rm -rf .next
rtk npm run build
```

6. Run canonical backend/unit checks relevant to the new circuit-intelligence work:

```bash
cd /home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/apps/circuit-ai
rtk pytest tests/unit/test_circuit_board_graph.py
rtk pytest tests/unit/test_board_intelligence_workflow.py
rtk pytest tests/unit/test_functional_salvage_workflow.py
rtk pytest tests/unit/test_circuit_ai_reasoner.py
rtk pytest tests/unit/test_hardware_splicer_integration.py
rtk pytest tests/integration/test_hardware_splicer_e2e.py
```

If dependency installation is needed first, do that before interpreting failures.

7. Verify the frontend user flow in a browser:

- `/library` renders.
- search `MCP23017`.
- open detail drawer.
- "Open in build" preloads the selected module.
- `/build?modules=mcp23017-ioexp` shows the module on the build canvas.
- mobile viewport has no horizontal overflow.

8. Verify DeepSeek in the canonical repo:

- Use the existing root `.env.local` key without printing it.
- Prefer `JARVIS_TEXT_PROVIDER=deepseek` for frontend Jarvis text smoke.
- For backend circuit reasoning, use:

```bash
export LLM_PROVIDER=deepseek
export LLM_MODEL=deepseek-v4-flash
```

Then call the reasoning smoke/test path with `use_llm_reasoner: true`.

Expected behavior:

- model calls may propose hypotheses
- verifier gates still decide whether claims become usable splice guidance
- no model output should bypass safety, measurement, or circuit-evidence checks

## Known Limits

- The standalone frontend patch is verified, but the canonical repo still needs the patch ported and tested.
- DeepSeek was not live-tested in standalone because that copy had no `DEEPSEEK_API_KEY`.
- Canonical has a DeepSeek key, but do not assume the frontend automatically sees the root `.env.local`; Next.js usually loads env from the frontend app directory or process env.
- Vision flows are still not DeepSeek-covered in the frontend Jarvis client.
- The library validator still reports 25 nonfatal electrical info/warn findings across strict recipes in standalone.
- Passing build/lint is not enough. The actual value test is whether the system can turn evidence into safe, useful repair/reuse/splice decisions with explicit certainty and missing-proof gates.

## What "Good Enough To Leave Alone" Means

The project should not be considered production AOI or production salvage until it can repeatedly do the following on real cases:

- ingest several photos or evidence records for the same board/device
- recognize useful ICs, modules, connectors, rails, and likely function blocks
- cite provenance for the recognition or datasheet/pinout assumption
- separate known facts from hypotheses
- ask for the smallest useful measurement when certainty is missing
- block unsafe reuse when power, battery, mains, high-voltage, or current evidence is incomplete
- produce a functional salvage plan with entry points, adapter needs, pin contracts, and verification gates
- route proven modules into the build/splice canvas
- retain the case as training/eval data

That is the benchmark. A single pretty component-labeling demo does not satisfy the product vision.

## Useful External DeepSeek References

These were used for provider integration checks:

- `https://api-docs.deepseek.com/api_samples/chat_curl`
- `https://api-docs.deepseek.com/quick_start/pricing`
- `https://api-docs.deepseek.com/news/news260424`

## Next Commit Strategy

Recommended sequence:

1. Add this handoff doc as its own commit if desired.
2. Port and commit the standalone frontend/library/DeepSeek patch separately.
3. Commit canonical backend circuit-intelligence work separately after tests pass.
4. Avoid a broad "commit everything" while the worktree contains mixed frontend, backend, docs, config, and generated/provenance changes.

