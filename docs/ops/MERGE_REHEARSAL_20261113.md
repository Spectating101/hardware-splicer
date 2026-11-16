# Merge rehearsal, 2026-11-13

A rehearsal of the merge order recommended by the 2026-11-13 open-PR triage, applied to
main (`38dbad2`) on the branch `auto/hs-merge-rehearsal-20261113`. Nothing was pushed,
merged on GitHub, or re-run in CI. The merge commits exist only on this branch.

Order rehearsed: #278, #235, #231 (into #230), #230, #276, #291, cherry-pick of `695d036`
from #336 (not the #336 stack), #217.

## Outcome

**All eight steps were applied, and none of them added a test failure.** The rehearsal branch
ends at `85f2844` with 3912 passed, 1 failed and 35 skipped, against 3872 passed, 1 failed and
35 skipped on main. The one failure is the same test at every step, and it fails on main
for an environmental reason (see below). There were no merge conflicts, so nothing was
resolved by hand and no test was dropped or edited.

#278's failing "Device and evidence browser checks" on GitHub are caused by the CI runner
image, not by #278. Both jobs fail before any test runs because Playwright 1.55.0 cannot
install Chromium on `ubuntu-26.04`. main already pins those jobs to `ubuntu-24.04` (#234).
Both browser legs pass locally on main + #278: 41 tests (real) and 114 tests (mock). The
details are in the section on #278 below.

## Method

- Each PR head was fetched with `git fetch origin pull/<n>/head` and merged at the exact
  head SHA GitHub reported on 2026-11-13 (listed in the table below).
- PRs were merged with `git merge --no-ff`. #231 targets #230's branch, so it was first
  merged into #230's head (`efa2fff`) as a separate merge commit (`0525095`, parents
  `efa2fff` and `740d071`), and that commit was then merged into the rehearsal branch.
  This mirrors "merge #231 into #230 on GitHub, then merge #230 into main". #230 was
  not tested on its own without #231.
- `695d036` was applied with `git cherry-pick -x`.
- After each step the full suite ran with the requested command:
  `PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 <hs venv python> -m pytest -q -p no:cacheprovider tests`
  (plus `-rfE` so failing test IDs are listed). "Failures vs previous step" compares the
  set of failing and erroring test IDs with the step before.
- No step had a textual conflict, so no conflict resolution was needed and no test was
  dropped or edited. A `git merge-tree` dry run of the whole sequence also predicted no
  conflicts before any real merge was made.

### Environment note: the scheduler's venv lacks `pypdf`

The scheduler's `hs` virtualenv does not have `pypdf`, which `pyproject.toml` and
`requirements.txt` declare (`pypdf>=5,<7`). With the command exactly as given, main itself
stops at collection: **62 errors during collection** (`ModuleNotFoundError: No module named
'pypdf'`, all through `hardware_splicer.document_evidence`), zero tests run.

The rehearsal could not modify that venv (it is outside the worktree). Instead `pypdf`
6.21.4 was installed into a git-ignored directory inside the worktree and appended to
`PYTHONPATH` for every run, main baseline included. Nothing else differs from the given
command. The scheduler's own check (`pytest --collect-only tests`) therefore still fails
on this branch, as it does on main, until `pypdf` is installed in that venv. See "Owner
decisions".

### Baseline failure on main (environmental, present at every step)

`tests/test_assembly_plan.py::test_outlines_agree_with_kicads_own_geometry_for_turned_and_flipped_parts`
fails on main. The test runs the system `python3` (the interpreter that has KiCad's
`pcbnew` module) and imports `hardware_splicer` there; that interpreter has no `pydantic`,
so the subprocess exits with `ModuleNotFoundError: No module named 'pydantic'`. This is a
property of the workstation, not of any PR. It fails identically at every step.

## Per-step results

| Step | How | HEAD after step | Passed | Failed | Skipped | Errors | Failures vs previous step |
|---|---|---|---|---|---|---|---|
| Baseline: main | - | 38dbad2b | 3872 | 1 | 35 | 0 | baseline |
| 1. Merge #278 | `git merge --no-ff` c69d779 | 51f98896 | 3875 | 1 | 35 | 0 | new: 0 |
| 2. Merge #235 | `git merge --no-ff` 22b6f8c | e3651274 | 3885 | 1 | 35 | 0 | new: 0 |
| 3-4. Merge #231 into #230, then #230 | synthetic merge 740d071 into efa2fff, then `git merge --no-ff` | a657e5d3 | 3897 | 1 | 35 | 0 | new: 0 |
| 5. Merge #276 | `git merge --no-ff` 902ad2d | d006f1e1 | 3897 | 1 | 35 | 0 | new: 0 |
| 6. Merge #291 | `git merge --no-ff` afa56ca | 9024d844 | 3897 | 1 | 35 | 0 | new: 0 |
| 7. Cherry-pick 695d036 (#336) | `git cherry-pick -x` | 6e9d911d | 3897 | 1 | 35 | 0 | new: 0 |
| 8. Merge #217 | `git merge --no-ff` d9bda19 | 85f2844c | 3912 | 1 | 35 | 0 | new: 0 |

Head SHAs merged: #278 `c69d779`, #235 `22b6f8c`, #230 `efa2fff`, #231 `740d071`,
#276 `902ad2d`, #291 `afa56ca`, #336's commit `695d036`, #217 `d9bda19`.

Notes per step:

- **#278** adds 3 tests (`tests/test_project_pre_fabrication_plan_api.py`). It changes one
  source file and its test file.
- **#235** adds 10 tests (`tests/test_native_spi_capability.py`), a verification script and a
  workflow. The workflow (`native-spi-eda-acceptance.yml`) was not run: it needs KiCad 9 on
  a CI runner.
- **#231 into #230, then #230** adds 12 tests (`tests/test_system_example_microdrone.py`).
  The Crazyflie firmware and simulation workflows they add were not run.
- **#276** adds no tests under `tests/`. The counts are unchanged and nothing regressed.
  Its flight lab, its FreeCAD and OpenSCAD packaging scripts and its airframe workflow
  were not run. `pybullet` is not in the test virtualenv.
- **#291** adds 20 tests, but they sit in `examples/arbitrage_lab/build_vs_buy/tests/`,
  outside `tests/`, so the requested command does not collect them. They were run
  separately on the step-6 tree:
  `pytest examples/arbitrage_lab/build_vs_buy/tests` gave **20 passed**.
- **Cherry-pick 695d036** changes packaging, the Makefile, the install script, a
  catalogue export script and a README. No Python behaviour changes. The test
  virtualenv already has `cadquery` and `trimesh`, which the new `cad` extra declares.
  That is why the two project-intake failures its commit message mentions do not show up
  here, before or after. Applying it with `cherry-pick -x` was clean. The original
  commit's message already carried a co-author trailer, so the rehearsal commit
  has that trailer twice. This is cosmetic.
- **#217** adds 15 Python tests (`tests/test_request_fidelity*.py`). It also changes
  `apps/splice-ui` (a status header and the project-truth derivation), with 5 new vitest
  tests that pytest does not run. These were run separately: `npm ci && npx vitest run` in
  `apps/splice-ui` gave **77 passed** before the #217 merge (at step 7) and **82 passed,
  0 failed** after it.

## Why #278's "Device and evidence browser checks" fail on GitHub

**Cause: the CI runner image, not #278.** Both failing jobs (mock and real), in both
runs on the PR head `c69d779` (run 41814133456, `push`, and run 41814141125,
`pull_request`, 2026-11-04 10:25Z), stop in the step "Install locked frontend and
pinned headless browser", before any test runs. The log of every one of the four jobs says:

```text
Image: ubuntu-26.04
BEWARE: your OS is not officially supported by Playwright; installing dependencies for ubuntu26.04-x64 as a fallback.
Cannot install dependencies for ubuntu26.04-x64 with Playwright 1.55.0!
Failed to install browsers
Error: ERROR: Playwright does not support chromium on ubuntu26.04-x64
##[error]Process completed with exit code 1.
```

Evidence that this is pre-existing and unrelated to the PR's change:

1. #278 changes two files only, relative to its merge base `1545ae8`:
   `src/hardware_splicer/project_pre_fabrication_plan_api.py` and
   `tests/test_project_pre_fabrication_plan_api.py`. It does not touch the
   workflow, the frontend, or the browser scripts.
2. #278's branch was cut before #234 ("ci: pin device browser Playwright jobs to
   supported Ubuntu 24.04", merged 2026-11-04 17:30Z as `35ecbe1`). On the PR
   branch, `.github/workflows/device-plan-deliverables.yml` still has
   `runs-on: ubuntu-latest`, which GitHub had moved to ubuntu-26.04. main has
   `runs-on: ubuntu-24.04`.
3. All 60 runs of the "Device Plan Deliverables" workflow created between 2026-11-01 and
   the #234 merge failed (branches for the teardown studio, the E5250 restoration episode,
   #276 and #278); a sampled failure from another branch (run 41675575323) shows the same
   `Playwright does not support chromium on ubuntu26.04-x64` error. Of the 100 runs
   created after the #234 merge, 94 succeeded (including `push` runs on main and #276's
   later head), 4 were cancelled and 2 failed. The two failures are one commit on an
   unrelated branch (2026-11-09, run 42674220376): the jobs that ran there, including the
   real-backend browser check, passed, so they do not show the Playwright install error.
4. A merge into current main uses main's workflow file, so the job would run on
   ubuntu-24.04. GitHub's `pull_request` run uses the merge ref, but these runs predate
   #234, so re-running the jobs (or updating the branch) should pick up the pin.
   That re-run has not been done: this rehearsal did not push or trigger anything.

**Can it run locally?** Yes. The job runs
`bash scripts/verify_device_frontend.sh real` and
`bash scripts/verify_device_frontend.sh mock <spec patterns>`. The script needs the repo
`.venv` (with the project's dependencies), `apps/circuit-ai/circuit-ai-frontend/node_modules`
(`npm ci`), Playwright 1.55.0 installed under `HS_PLAYWRIGHT_ROOT` with its Chromium build,
free ports 3102 and 8102, and, for the mock leg, KiCad 9 `kicad-cli` with the standard
symbol and footprint libraries. The workstation has all of these (Node 22, KiCad CLI, a
pinned Playwright 1.55.0 install and the Chromium 1187 build). I ran both legs locally on the
rehearsal commit after step 1 (main + #278, `51f9889`), in a throwaway clone, with the
workflow's environment flags (`HARDWARE_SPLICER_OFFLINE_LLM/VISION/SALVAGE=1`) and the
workflow's exact spec list for the mock leg:

| Leg | Command | Result |
|---|---|---|
| real | `verify_device_frontend.sh real` | 41 passed (4.2 min), exit 0 |
| mock | `verify_device_frontend.sh mock device-assembly device-firmware device-application device-observations device-modeled-run donor-lookup donor-device-handoff donor-capture evidence-` | 114 passed (9.2 min), exit 0 |

So #278 does not break the browser checks; the GitHub failure is the runner image alone.
Local differences from CI: Python 3.13 instead of 3.12, an existing virtualenv rather than a
fresh `pip install -e '.[dev]'`, and KiCad CLI 9.0.2 instead of the PPA's current 9.0.x.

## What this rehearsal does not prove

- **CI.** No workflow was run on GitHub. In particular, these were not exercised: the
  workflows added by #235, #230/#231 and #276 (KiCad 9 acceptance, Crazyflie firmware and
  simulation, original airframes), the KiCad-in-CI checks, and the browser checks on the
  merged tree. The browser checks were run locally only on main + #278 (step 1).
- **Python 3.12.** All runs used the scheduler's Python 3.13 virtualenv. CI uses 3.12.
- **`pypdf`.** It came from a side directory added to `PYTHONPATH`, not from the virtualenv.
  See the environment note.
- **The one baseline failure.** It still fails at every step. It needs a system Python that
  has both KiCad's `pcbnew` and the project's dependencies.
- **Merging on GitHub.** GitHub merges each PR into whatever main is at that moment. This
  rehearsal applies the PRs to a fixed main (`38dbad2`). If main moves first, the order
  needs another dry run (`git merge-tree`).
- **#231 into #230.** That was rehearsed as a local merge commit. On GitHub, #231 has to be
  merged into #230's branch first (or retargeted), and only then is #230 merged.

## Owner decisions

1. **Install `pypdf` in the scheduler's `hs` virtualenv.** Without it, the scheduler's own
   check command (`pytest --collect-only tests`) stops with 62 collection errors, on main as
   well as on this branch. This rehearsal did not change the virtualenv.
2. **Before merging #278, re-run its checks or update its branch from main**, so the
   "Device and evidence browser checks" run on `ubuntu-24.04`. The failure is not in the
   PR's code.
3. **Choose how #336's CAD-extra commit lands:** cherry-picked as here, or as a small new PR
   containing only `695d036`. The #336 stack itself should not be merged in this pass.
4. **Decide whether #291's tests should be collected by the main suite.** Today they live
   under `examples/` and only run when invoked directly.
