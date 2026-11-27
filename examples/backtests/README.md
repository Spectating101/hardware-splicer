# Back-tests and the prediction ledger

HS's predictions checked against measurements someone else published. Each file names its data, quotes it, gives HS's
numbers from the same inputs, and says what changed in HS because of it.

| File | Measured against | Result |
|---|---|---|
| `nanobench_crazyflie_hover_20261127.json` | NanoBench battery-drain hovers (BSD-3) | At a usable thrust-to-weight of 1.13, HS's hover time was about 3x too long; HS now marks it an upper bound under 1.5 |
| `osr_rocker_bogie_climb_20261127.json` | OSR's rocker-bogie README | HS's one-radius cap was its own model's limit; a wall phase was added |
| `so101_shoulder_load_20261127.json` | SO-ARM100 issues, an SO-101 builder's report, LeRobot's servo settings | Consistent with HS's shoulder warning; not settled |

`PREDICTIONS.json` lists every open prediction with how to measure it. A measurement is added beside a prediction, never
in place of it.
