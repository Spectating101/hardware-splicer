# Splice best practices — what we enforce and what to push next

## Product invariants (keep)

1. **Vision is advisory** — `board_evidence` and Qwen output produce candidates and measurement queues; they never set `power_on_authorized` alone.
2. **Bench capture is authoritative** — `bench_topology_capture.v1` → `submit_bench_capture` → gate closure with operator + instrument provenance.
3. **Carrier DRC ≠ donor safety** — KiCad DRC on the **new** board does not validate donor VMOTOR, polarity, or cut lines.
4. **Agent-first handoff** — SDK/MCP/API before UI; artifacts are JSON + KiCad on disk for git review.
5. **Offline CI path** — fixture salvage + pinned board evidence so demos work without API keys.

## Golden loop (polished path)

```bash
# Vision junk intake → compile → simulated bench closure (CI-safe)
make splice-golden-loop

# CI bar: fixture S2 + vision S3
make verify-splice-loop
```

Flow:

```
intake (+ optional donor_board_vision)
  → splice_and_build_from_intake
  → SPLICE_BENCH_SESSION.json + BENCH_CAPTURE_TEMPLATE.json
  → fill capture (real instrument or golden_loop_simulator)
  → submit_bench_capture
  → power_on_authorized when critical gates closed
```

## Operator best practices

| Step | Practice |
|------|----------|
| Before cut | Photo donor board; run vision enrich; export `DONOR_BOARD_VISION_REPORT.json` |
| Before splice | Read `BRINGUP_CARD.md`; confirm open gates in bench session |
| Measure | Use `BENCH_CAPTURE_TEMPLATE.json`; one row per open gate; attach photo URI when possible |
| Submit | `hs_splice_bench_submit_capture` or `POST /v1/splice-bench/submit-capture` |
| Power-on | Only when `power_on_authorized: true` in session |

## Engineering best practices (repo)

| Area | Current | Push further |
|------|---------|--------------|
| Demos | `verify-splice` (S2 manifest) | `verify-splice-loop` (S3 bench closure) |
| Junk testing | `splice_robot_drive_vision_brief.json` + pinned evidence | Live photo regression set |
| Gates | Per-block measurements from splice plan | PSU foldback + thermal gates |
| Provenance | `operator_id`, `instrument_id` in capture | Signed capture packets / hash chain |
| Dum-E | Archived multi-view in Circuit-AI | MCP tool: `hs_donor_multi_view_capture` |
| UX | JSON templates | Minimal web capture form |

## Anti-patterns

- Treating KiCad `drc_pass` as “safe to energize donor VMOTOR”
- Skipping `bench_capture_template` and posting ad-hoc measurements without `gate_id`
- Using static donor fixtures in production without vision or bench cross-check
- Building a full ECAD editor before nailing salvage + bench closure

## Maturity checklist

| Tier | Bar |
|------|-----|
| S1 | Splice plan + evidence gates |
| S2 | DRC-clean carrier (`make verify-splice`) |
| S3 | Bench gates closed (`make verify-splice-loop`) |
| S4 | Mech envelope + field validation (future) |

See [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md) for product positioning and [`REAL_WORLD_PARALLELS.md`](REAL_WORLD_PARALLELS.md) for how community/pro lab workflows map to our gates.
