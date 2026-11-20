# Source-bound witness-station operating-envelope experiment

Date: 20 November 2026. Experimental digital-only result, not an approved hardware build.

## Why it matters

The original HS 5 V witness station passes native KiCad 9 ERC/DRC and a 5 V, 10 ohm nominal ngspice model (~2.463 W). Its existing station-spec-5v.json also permits a 5.25 V maximum bus but declares 2.5 W maximum load power. The prior HS independent audit already found that the unchanged 10 ohm load exceeds the declared power envelope under relevant corners. This experiment tests an actual modeled alternative, retaining Policy Lab intake and source custody.

## Frozen experimental criteria (not manufacturer/owner specifications)

experiment-20261120.json pins the original station spec and SPICE source hashes before optimization. Six candidate external loads: 10, 11, 12, 13, 15 and 18 ohms. Trial assumptions: source 4.75, 5.0 or 5.25 V; resistor ±5%; series resistance 0, 0.075 or 0.15 ohm; declared 2.5 W plus a researcher-imposed 10% reserve (2.25 W maximum); 0.34 A minimum current at the weak corner; 0.65 A assumed current-limited source.

The program optimize.py executes 162 ngspice corner cases with an independent series-circuit arithmetic check. Select the eligible candidate with the greatest minimum-case current, or hold when none qualifies.

## Measured SOFTWARE results (no physical measurements)

| External load | Nominal power at 5 V | Worst power at 5.25 V, -5% resistance, 0 series ohm | Digital target |
|---|---:|---:|---|
| 10 ohm | 2.462918 W | 2.901316 W | Block: above 2.5 W |
| 12 ohm | 2.057534 W | 2.417763 W | Block: below imposed 10% reserve |
| 13 ohm | 1.901078 W | 2.231781 W | Conditional digital pass |
| 15 ohm | 1.650124 W | 1.934211 W | Block: below experimental 0.34 A current floor |

The 13 ohm plan delivers about 0.3824 A nominal and 0.3442 A at the weakest trial current corner, instead of 0.4963 A nominal under the original 10 ohm load. At a hypothetical -10% rather than -5% actual load variation, it fails the 10% power reserve. No exact 13-ohm load part, tolerance, thermal characteristic, wiring or measurement instrument was selected or procured.

## Native replay and policy evaluation

verify_and_replay.py has an *optional* load profile. Its original default 10-ohm results remain unchanged. For the selected 13-ohm profile, it checks the original PCB ERC/DRC (no board change), generates a source-bound temporary ngspice load overlay, runs the unchanged INA228 register decoder on 183 fake I2C samples and hands those samples to the existing frozen Policy Lab PLRS-6 receiver. Nominal revised load power ~1.901078 W and three-minute energy ~0.0950539 Wh. Policy Lab retains TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS.

The companion opt-in Policy Lab application (witness-envelope) independently recomputes electrical policy conditions and uses the existing Policy Lab application foundation and replay receipts. It blocks 10 and 15 ohms and conditionally admits the 13-ohm *digital* trial only. All original source, experiment, native replay and feasibility hashes are bound in the decision. Mutated files, tampered decisions and falsely promoted physical status are refused.

## Reproduction

Run the frozen optimizer:

    python3 operating-envelope/optimize.py --native-replay /ABS/PATH/ORIGINAL/verification.json --out /NEW/OUT

Then, from this witness fixture directory, with the Policy Lab equipment receiver present:

    python3 verify_and_replay.py --pl-root /PATH/TO/PL-EQUIPMENT \
        --load-profile /OUT/proposed-revision.json \
        --parent-verification /ABS/PATH/ORIGINAL/verification.json \
        --out /NEW/REVISED-OUTPUT

The Policy Lab witness-envelope CLI takes four original JSON sources (feasibility, experiment, station and native verification) and an externally known SHA. Its README gives the exact invocation. No services or physical devices are started.

## Engineering and commercial limits

No new board PCB layout was required for the modeled resistor choice. No physical load, independent calibrated reference meter, fuse link, protected and isolated power supply, ESD/thermal design or independent operator exists. The prior PHY-02 through PHY-09 physical HOLDs remain open, and PHY-10 is at most *conditionally addressed as a modeled operating-plan proposal*, not physically closed.

An independent engineer equipped with SPICE and the same criterion would discover the power violation and can choose a suitable load without this portfolio. Thus the measured value here is **reproducible cross-project decision reversal** (native test-only pass versus explicit 2.5 W envelope block and conditional adjusted scenario), not a demonstrated cost, speed, market or unique research advantage.
