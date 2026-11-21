# Rust/WebAssembly scene geometry and TypeScript status modules (21 November 2026)

Branch `agent/change-dossier`. All timings come from headless Chromium 1440×900 on an Intel UHD 630 (ANGLE/Vulkan). The page was the Fielddeck change-dossier project (`digital-996558719b13454fb1724bef8f218093`, 7-inch → 5-inch display), served by `product_api:app` from the change-dossier bench store. Each figure is the median of the warm runs, and the phase marks are the stage's own `performance.mark` entries.

## Where the load time went (before)

| Phase | Before (1368c2ba) |
|---|---:|
| Mesh step on the main thread (`meshes-start` → `meshes-done`) | 1.15–1.3 s |
| Edge welding and coincidence culling in 4 workers (`meshes-done` → `chains-done`) | 1.2–1.4 s |
| Shader compile | 0.2–0.45 s |
| Model fully drawn (`compiled`, from navigation) | ~4.6 s |

Run one job at a time in Node, the chain jobs total **8.9 s of CPU**. The longest single job is 2.76 s, and the worker pool cannot finish before it does. `cullCoincidentChains` accounts for nearly all of that time.

## What changed

- `apps/splice-ui/wasm/fielddeck-chains` (Rust, no dependencies) holds ports of three groups of functions:
  - from `fielddeckLogic.js`: `weldEdgeChains`, `simplifyEdgeChain`, `cullCoincidentChains` and `cullIsolatedChains`;
  - from `fielddeckChains.js`: the diff/overlay composition in `runChainJob`;
  - from three.js r187: `EdgesGeometry`.
- The ports follow the JavaScript order of operations, use V8's `Math.hypot` and `Math.round` algorithms, and take the threshold cosine from JavaScript.
- The module is built to `src/components/wasm/fielddeck_chains.wasm` (54 KB) and committed, so `npm run build` needs no Rust toolchain. `npm run check:wasm` rebuilds it and fails if the committed module differs from the source.
- The workers use the module for diff/overlay jobs. The stage uses it for the change-accent weld and for feature-edge extraction. Each falls back to the JavaScript (or three's `EdgesGeometry`) when WebAssembly is unavailable.

## Parity (exact, not approximate)

| Check | Cases | Result |
|---|---:|---|
| Chain jobs captured from the live page (diff + overlay) | 8 | identical chains, points and order |
| `EdgesGeometry` on every mesh of both Fielddeck GLBs, indexed and non-indexed, at 1°, 32°, 40°, 42° and 60° | 700 | bit-identical float32 positions (`Object.is`, including −0) |
| vitest: captured jobs, synthetic cases, three primitives at four angles, weld at 0.01 and 0.0001, and the review reproducers (NaN, huge, partial and empty-index inputs) | 15 tests | pass |
| `cargo test` | 9 | pass |

## After

| Measure | Before | After |
|---|---:|---:|
| Chain-job CPU, all eight jobs (Node) | 8,929 ms | 131 ms |
| Longest chain job (Node) | 2,763 ms | 39 ms |
| `EdgesGeometry`, 700 cases (Node; timings vary run to run) | 2.5–4.9 s | 0.6–1.1 s |
| Welding phase in the page | 1.2–1.4 s | 0.1–0.13 s |
| Mesh phase in the page | 1.15–1.3 s | 0.62–0.73 s |
| Model fully drawn | ~4.6 s | 2.4–3.1 s |

## Independent review

Gemini 4 Neon (agy, `gemini-4-neon-high`) reviewed the port. The ledger is at `docs/review-program/wt-dossier-hs/2026-11-21-rust-wasm-chain-port.md` in the toolbox repository. Every finding was reproduced and fixed:

- **Number semantics.** Saturating i64 keys and NaN-swallowing min/max now follow JavaScript number semantics.
- **Index and partial input.** An empty index counts as indexed. Partial segments or triangles, and unusual index layouts, defer to the JavaScript or to three.
- **Memory.** Allocation is exact-length, frees accept null, the loader frees every allocation in `finally`, and pointers are read as unsigned.
- **Failure handling.** If the module throws at runtime, the worker and the stage fall back to JavaScript, and the stage build checks for cancellation once the module has loaded.

One known residual remains. If span starts are NaN, the sort comparator is inconsistent in both languages, and Rust's and V8's stable sorts may order those spans differently. Real geometry never produces NaN coordinates.

## Phone layout and Projects list

- **Phone layout.** At 390×844 the 3D stage now starts 598 px down the page instead of 749 px, with every qualifier still visible (`review-ui/rust-typescript-20261121/phone-bench.png`).
- **Projects list.** Projects that share a name now group under the newest copy. On a store of 33 journey-test projects the list goes from 33 rows to 5 (`projects-grouped-desktop.png` and `projects-grouped-phone.png`).

## TypeScript

- `tsconfig.json` is strict and `noEmit`, with `allowJs` on and `checkJs` off. `npm run typecheck` runs tsc 7.0.2.
- Six modules are now strict `.ts`: `statusLanguage`, `checkTransition`, `stageAvailability`, `deriveEvidenceTruth`, `deriveProjectTruth` and `router`. Gemini 4 Neon converted them through agy.
- With types stripped, each converted file emits the same JavaScript as the original.
- The state vocabularies are string-literal unions.
- `authorityVocabulary.typecheck.ts` uses `@ts-expect-error` to assert that these state types reject the words ready, approved, proven, passed, released, success and good. Removing one guard makes `npm run typecheck` fail.

## Verification on this branch

- vitest: 257 passed.
- tsc: clean.
- vite build: ok.
- Full Python suite on the merged tip before these UI commits: 4,669 passed, 0 failed.
- UI-serving tests after these commits: 25 passed.
- impeccable detect: 0 findings on the project bench and on Projects, at 390×844 and 1440×900.

## Follow-up (22 November 2026): picked by payoff, not by coverage

The owner asked for only the highest-return changes, not a wholesale conversion.

### Server: the request the 3D model waits on

The scene could not start until `GET /v1/projects/{id}/digital` returned. Profiling showed two costs:

- **Re-hashing on every read.** Every read re-hashed about 700 sealed study files, taking 0.76–0.9 s. `file_digest.py` now remembers each file's SHA-256 under its path, device, inode, size, mtime and ctime. Any write, truncate or replace re-hashes, and, as in git's racy-index rule, a file changed within 2 s of hashing is never remembered. The integrity check itself is unchanged.
- **A cold runtime probe on the first request.** The first request after a restart started an interpreter to import the CAD stack, taking 2–3 s. The probe now runs in a background thread at startup. A request that arrives mid-probe waits for that answer rather than starting a second one.

| Measure | Before | After |
|---|---:|---:|
| `/digital`, repeat request | 0.76 s | 0.12–0.17 s |
| `change-dossier`, repeat request | 0.78 s | 0.11–0.29 s |
| First `/digital`, 15 s after startup | 6.7 s | 0.32–0.84 s |
| Scene build starts (page time) | ~1.4 s | 0.58–0.75 s |
| Model fully drawn | 2.4–3.1 s | 1.6–2.6 s |

These timings come from a fresh server, with four loads after 15 s of warm-up and nothing else running on the machine.

### TypeScript, where a mistake changes what the screen claims

- **`projectPersistence` (save, conflict, revision, reopen baseline).** Typed by hand. Its save states must equal `PERSISTENCE_STATUS`'s keys exactly. Adding or removing a state there fails `npm run typecheck`, and both directions were tested.
- **The eight API client modules.** Gemini 4 Neon converted them, and each function's response is typed to the fields the UI reads. Backend status fields are open unions, because the backend may send values the UI does not know. Compiled with esbuild, seven files are byte-identical to the originals and `api` differs only in line wrapping.
- **Left as JavaScript on purpose.** The display components, where types catch little that the tests do not.
- **Python route test.** `tests/test_served_app_routes.py` now scans `.ts`/`.tsx` too. Without that it found no API calls once the clients moved, and it now finds 82 calls in 9 files.

### Verification

- Full Python suite on the server fixes: 4,679 passed, 0 failed.
- Digital, change-dossier and serving tests on the final tip: all pass, including the route-scan fix.
- vitest: 257 passed.
- tsc: clean.
- vite build: ok.
