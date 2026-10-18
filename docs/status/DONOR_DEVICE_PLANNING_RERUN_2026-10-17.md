# Native donor planning — full verification rerun, 2026-10-17

Tested branch: `agent/mission-donor-planning`.
Tested commit: `0e8e0a6f9570087ee186cfbc918f6820fdb82d84`.
This is a follow-up to [the implementation handover](DONOR_DEVICE_PLANNING_2026-10-17.md),
not a replacement for its historical verification record.

## Result

The new donor cases passed again, and a complete Python suite run finished:

```text
Focused: 40 passed, 2 warnings in 6.48s
Full:    2 failed, 4243 passed, 56 skipped, 125 warnings in 1032.95s (0:17:12)
```

The full suite is not green. No additional failing tests were observed relative to the saved parent full run.
All 40 cases in `tests/test_donor_device_plan.py` passed in both runs. The assembly geometry test
`test_outlines_agree_with_kicads_own_geometry_for_turned_and_flipped_parts` also passed.

The deterministic-package test exercised the real planner, engineering review, enclosure generator and mission
delivery code using synthetic temporary-project evidence. Repeated package hashes matched, ZIP integrity passed,
the native donor appeared in the plan, the enclosure STL was present and firmware was explicitly blocked.
The public HTTP boundary test also passed. These are software integration checks, not physical measurements or a
fresh live-model mission.

## Baseline comparison

The only failures were:

- `tests/test_project_intake.py::test_project_intake_evidence_pack_closes_scoped_production_package`
  — line 285, `assert result["ok"] is True`.
- `tests/test_project_intake.py::test_project_intake_extracts_notes_into_production_evidence`
  — line 317, `assert result["ok"] is True`.

JUnit comparison confirmed identical test identities and failure messages against both the saved P4/P5 full run
and the earlier untouched #124 baseline check. Full failure text also matches the P4/P5 full run exactly; the #124
report uses a longer traceback format. This comparison establishes that these failures predate this feature; it
does not establish their root cause or repair them.

The parent full run had 4,203 passes, 56 skips and the same two failures. This branch adds 40 passing cases without
changing the observed failure set. No test was removed, relaxed or marked skipped to obtain that comparison.

## Reproduction and artifacts

Run from the donor-planning worktree with the shared root virtual environment:

```bash
rtk proxy env PYTHONPATH=src /home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_donor_device_plan.py --tb=short --junitxml=.cache/donor-planning-focused-rerun.xml
rtk proxy env PYTHONPATH=src /home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/.venv/bin/python -m pytest -q -p no:cacheprovider tests --tb=short --junitxml=.cache/donor-planning-full-rerun.xml
```

Local reports are ignored scratch artifacts, not published CI evidence:

| Report | SHA-256 |
|---|---|
| `.cache/donor-planning-full-rerun.xml` | `c974d7dd58e27ccf841077c2bcd8afe484d78926340edd277ddbd2743e2f8f6e` |
| `../mission-donors/.cache/donors-full-suite.xml` | `68b8d2f69e8795e320f6644496a8f66d0f63c1edc48809ef53eb8f46f1137e08` |
| `../mission-step4-integration/.cache/baseline-kicad.xml` | `9b4a8d0c477cb5bfa5f88804ed10321355843c03f5e2bfd478403272fbef577a` |

The remote-worker retry still reported zero healthy workers, below the minimum of two; all three had SSH
connectivity/authentication failures. After the user's renewed rerun request, this verification ran locally,
sequentially, with one test process and no overlapping heavy job started by this agent. No remote execution or CI
success is claimed.

## Unchanged limits and handoff

No implementation changes were made during this rerun. Main, the frozen #122/#123/#124 branches, Step 4 and P4/P5
remain unchanged. Nothing was pushed or merged; no other agent process was stopped.

Donor firmware/runtime remain unsupported, and physical correctness remains `UNPROVEN`. No live mission was
accepted, operator credential used, fabrication authorized, device flashed or hardware powered. The independent
live reruns remain outstanding. The next functional development boundary is still a bounded passive-switch input
firmware adapter with modeled runtime checks; this result does not claim that capability exists.
