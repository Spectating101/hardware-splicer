# Fabrication mission runtime: handover and frozen plan — 2026-10-16

Where the work stands, what to do next, and what is deliberately frozen. For the direction itself, see #120
(`docs/FABRICATION_MISSION_RUNTIME_2026Q4.md`). For the agent contract, see `docs/AGENT_MISSION.md`.

## The rule that governs every step

Authority is never implicitly upgraded. The agent proposes; HS's deterministic code decides; a person keeps every
physical action and every review decision. Success for a mission is the **correct** terminal state with an evidence
trail, not READY. Measure trials by **false persisted results**, not by how many attacks HS refused.

## Branches and pull requests

Merge order, each stacked on the one before:

| PR | Branch | What | State |
|---|---|---|---|
| #115–#119, #121 | device lane branches | Earlier device work; #121 is the typed parts list | green, unmerged |
| #122 | `agent/mission-runtime` | P0–P2, mission HTTP/MCP, agent trial 14/14, red-team 11/12 → 0 false, hardening | green |
| #123 | `agent/mission-delivery` | Step 6: deterministic mission package + design staged as a project review (P3) | open |
| #124 | `agent/mission-feedback` | Step 9: a mission waits for a person's evidence and resumes; P4/P5 design doc; this handover | open |
| — | `agent/device-i2c-straps-buses` (from #122) | Step 4, **work in progress**: tests written, planner partial | pushed, no PR |
| — | `agent/mission-donors` | Steps 7–8: not started; cut it from the tip of #124 | not created |

#120 (direction doc, another session) merges any time. Nothing has been merged by an agent; a person merges.

## The nine-step plan and where each step is

1. **Finish the red-team rerun — done, partially.** Report: `docs/status/MISSION_REDTEAM_2026-10-16.md`. The hardened
   replay ran 9 of 14 missions (Composer 7, Grok 2) before the Cursor usage limit stopped Grok and Composer. Owed: the
   other 5 (Grok's slots: address clash, budget, engineering limit, hidden part, false blocker).
2. **Report and #122 description — done.**
3. **Fix any surviving false result — none found** in the missions that ran.
4. **BME280 address straps and the Pico's second I2C bus — in progress.** Ticket:
   [`handover/TICKET_STEP4_I2C_STRAPS_BUSES.md`](handover/TICKET_STEP4_I2C_STRAPS_BUSES.md). Codex wrote the tests first
   (`tests/test_device_plan_i2c.py` plus new engineering, gate and store cases) and began the library data and
   planner; 20 tests fail, including one existing address-overlap test broken mid-change. Continue from commit
   `fb93c61c`. Also fixes a real bug: the planner tracks one I2C bus, so a second sensor on GP18/GP19 passes while the
   same bus on GP6/GP7 is refused, depending on net order.
5. **Rerun both trials after step 4 — not started.** The cooperative and the hostile trial, same scenarios. The
   address-clash mission should now reach READY through a strap repair, and no attack should get a false result
   through. A person must accept the new missions (operator token). Cursor agents: only the `auto` model had quota
   left on 2026-10-16.
6. **P3 + delivery — done, #123.**
7. **P4: donors in missions — designed, not built.** Design: `docs/MISSION_DONORS_EVIDENCE_FEEDBACK.md` (reviewed by
   Gemini Argon; 8 findings folded in). Ticket:
   [`handover/TICKET_P4_P5_DONORS_FINDINGS.md`](handover/TICKET_P4_P5_DONORS_FINDINGS.md), to run on a new
   `agent/mission-donors` branch cut from the tip of #124.
8. **P5: reverse-engineering findings as evidence — designed, not built.** Same design and ticket as P4.
9. **Physical feedback — done, #124.**

## How the trials were run

Trial harnesses lived in a session scratchpad and are not in the repo; rebuild them from this description.

- Backend: `uvicorn hardware_splicer.product_api:create_product_app --factory` on a spare port, with
  `HARDWARE_SPLICER_PROJECT_ROOT` set to a fresh folder and `HARDWARE_SPLICER_OPERATOR_TOKENS` holding a JSON registry
  of **hashed** tokens (`operator_identity.hash_operator_token`). The person keeps the plain token; never commit it.
- Agents: Cursor agent CLI, `agent -p --output-format stream-json --model <m> --force --trust --workspace <empty dir>`,
  one run per mission, the folder holding only `AGENT_MISSION.md`. Red-team prompt and rules of engagement are quoted
  in the red-team report.
- The harness opens the missions, a person accepts them, and the score is read from the server's mission record.

## Frozen plan: everything after step 9

Not to start until steps 4, 5, 7 and 8 are done and both trials pass again. In rough order:

1. **Donor blocks in the device planner.** Wire `donor:*` blocks as first-class planner modules (pin geometry and
   electrical contracts in planner form), so a reclaim-heavy candidate can be planned, not just referenced.
2. **Architecture search (M3).** HS compares clean-sheet, reclaim-heavy and hybrid candidates on cost, reuse,
   unresolved evidence, electrical and mechanical complexity, firmware and fabrication burden, and uncertainty, and
   the agent picks and repairs one. The candidate kinds already exist; the comparison does not.
3. **Person-confirmed constraints.** An agent proposes a structured reading of a free-text constraint ("fits in
   80 x 50 x 25 mm" → case limits); the person confirms it before acceptance; HS enforces it. Today free text is
   reported, not enforced.
4. **More generated deliverables.** Firmware for more than one sensor breakout, a BOM, assembly steps and drawings
   in the package. Each one generated by HS or named as blocked.
5. **Promoting mission measurements into donor contracts** through the existing evidence review, never directly.
6. **Running RE tools from HS** as bounded operators that emit `finding_offered` events. HS only receives findings
   today.
7. **Procurement and fabrication orchestration.** Parts sourcing, PCB and enclosure services as external operators
   with evidence, never authority.
8. **Physical automation.** Robots, instruments and printers as bounded operators under strict human and safety
   authority. A separate project; HS stays the decision layer.

The known-library device lane stays frozen: no new controller or sensor for coverage, only correctness fixes and
what a real mission demonstrably needs (as step 4's two capabilities were).

## Open limits to keep honest

- Agent-asserted blockers (physical measurement, reverse engineering, procurement, unsafe) can stop a buildable
  mission. They are stored with `grounding: agent_assertion`, not refused.
- READY means HS's software checks support the design and, from #123, a package exists. It never means the device
  works.
- Three tests fail locally and on the code before this work (`test_assembly_plan.py::test_outlines_agree_with_kicads_own_geometry_for_turned_and_flipped_parts`
  and two `test_project_intake.py` production-package tests): a local KiCad environment gap. They pass in CI.
- The workstation is memory-tight: run one heavy job (Codex, the full suite) at a time.
