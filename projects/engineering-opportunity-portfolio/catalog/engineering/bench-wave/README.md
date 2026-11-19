# Bench equipment and process trials

Twelve digital trials cover repair, print layout, indoor visual inspection, measurement, winding, photo registration and accessible teaching. Each product report records what changed between the candidate and the rejected control, which checks replayed successfully, and the remaining physical acceptance work.

| Report | Bench question |
| --- | --- |
| [P003 cabinet handle layout](P003/README.md) | Do both axes stay at true scale and do all distances register? |
| [P004 OpenLog dock](P004/README.md) | Does the pocket fit the source board envelope and leave service space? |
| [P023 slide locators](P023/README.md) | Can a matched pair be staged parallel with room for clamps? |
| [P025 screw tray](P025/README.md) | Can thin washers cross the lid gap? |
| [P026 keyboard supports](P026/README.md) | Do the mirrored support footprints cover the modeled typing loads? |
| [P030 indoor inspection rover](P030/README.md) | Does the loaded chassis clear a 75 mm roof over a 6 mm threshold? |
| [P039 parts-counting scale](P039/README.md) | Are neighboring counts separable under stated mass and reading errors? |
| [P040 top-off controller](P040/README.md) | Does simulated filling stay within bounds under sensor faults? |
| [P045 pickup winder](P045/README.md) | Does the discrete guide maintain usable turn pitch through reversal? |
| [P046 registered tray photo mount](P046/README.md) | Where do ideal specular spots land at worst modeled placement? |
| [P228 adjustable phone arm](P228/README.md) | Does assumed lock stiffness leave acceptable static sag? |
| [P229 desk-scale orientation exercise](P229/README.md) | Are the route ridge and distinct keyed symbols separated? |

Use Python 3.10 or later.

```bash
cd projects/engineering-opportunity-portfolio/catalog/engineering/bench-wave
python3 verify.py
```

The verifier reads the saved neutral exports and rebuilds them in a temporary directory. It checks the measured outputs in [results.json](results.json), requires each candidate to pass and checks each revision against its intended rejection criterion. Edit [designs.json](designs.json), replay `python3 build.py` and use `python3 verify.py --write` after reviewing a change. Hardware envelopes and operating assumptions are documented per trial.
