# Mapping robot v0: gap log

What HS could not do on this project, what was used instead, and whether the gap is filled elsewhere or fixed in HS.
Open draft PRs are searched (`gh pr list --state open --search <topic>`) before a row is written.

| date | step | what HS could not do | what was used instead | filled on an open PR? | fixed in HS? |
|---|---|---|---|---|---|
| 2026-11-06 | sourcing | No Ruten listing client on `main` | Added `hardware_splicer.ruten_listings` (read-only, retries, masked-price flag) | Ruten readers exist on #286, #289, #291 (each project-local, not merged) | yes, on this branch |
| 2026-11-06 | parts | No library for bought robot parts (motors, LiDAR, packs); `device_modules.json` is for breadboard gadgets (8 modules, 3 kinds) | Added `hardware_splicer.robot_parts` with per-fact sources, units, quotes and a quote checker | no | yes, on this branch |
| 2026-11-06 | sizing | `robotics_actuation` gives a DC motor 6.0 V, 0.5 A run and 3× stall current when they are missing, without saying so | `sizing.py` refuses to size a part missing those facts | no | no (guarded here) |
| 2026-11-06 | sizing | `robotics_simulation` assumes robot mass = payload + 1.0 kg and a 0.25 A baseline when absent | `sizing.py` always passes mass (summed from parts + labelled chassis allowance) and baseline current | no | no (guarded here) |
| 2026-11-06 | sizing | `robotics_simulation` force model has no slope or step term, so it would accept motors too weak for a door threshold | Threshold torque worked by hand in `REQUIREMENTS.md` | no | no |
| 2026-11-06 | sizing | `robotics_simulation` has almost no tests of its own (one incidental reference in `tests/test_testing_mode.py`) | `tests/test_mapping_robot_sizing.py` exercises it through `sizing.py` | no | partly (indirect tests) |
