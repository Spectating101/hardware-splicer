# Third-party public repair holdout — preregistered original source evidence

**Research freeze:** November 3, 2026, Git blob `c4473c96309cd95d043e12dcaf4c9f308e66960d`. **Engine freeze:** after PR #269 commit `c296b7fb06df581b929f2bfff08664c3ca420aef`.

These are 17 independently linked **public owner repair histories**, not devices or test benches owned, measured or repaired by HS. Four early repair development stories (#266/#267) and seven first untouched stories (#268) have been excluded. The 34 symptom checkpoints were committed before the first engine evaluation in this PR. Their eventual fixes, outcomes and source-label expectations remain separate from the inputs.

## Frozen sample selection

- **17 different source threads/devices; 34 earlier-observation checkpoints.**
- **9** owner narratives contain numeric electrical readings, but none are independently laboratory verified: no original DMM file, metrology calibration, setup photograph or signed technician work order is required/available for the source report. Treat all as *owner-reported readings*, never as a bench-certified measurement.
- **5** devices are outside the current market classification catalogue (three printers, two drones), totaling **10** abstention checkpoints. Do not award them guessed product labels.
- **10** owners have not supplied a complete confirmed fix; partial restorations remain partial.
- Multiple owner-reported fixes are interventions rather than proven causal component identification. No ground truth available for an exact component-level accuracy percentage.

## Source selection and target phenomena

| Domain | Source | Pre-solution observation | Outcome oracle (never in engine input) |
| --- | --- | --- | --- |
| Retro handheld | [Game Boy DMG bias supply](https://www.reddit.com/r/Gameboy/comments/1ljgr0j) | Unexpected -33 V on nominal ~-19 V LCD bias rail; abnormal screen/audio | Owner describes external Zener/resistor intervention; full result unverified |
| Retro handheld | [Game Boy speaker voltage](https://www.reddit.com/r/consolerepair/comments/r8j565) | Owner reports 1.48 V / 0.42 V on speaker leads; headphone audio only at certain volume | No confirmed full fix; voltages are not meaningful waveform proof |
| Retro handheld | [Game Boy Color weak audio](https://www.reddit.com/r/Gameboy/comments/198q34o) | New speaker and cleaned volume control did not restore volume | Owner says capacitor replacement made audio much louder |
| Laptop | [ASUS ROG Zephyrus M15](https://www.reddit.com/r/computerhelp/comments/1r6t8eh/asus_rog_zephyrus_m15_charging_issue/) | Adapter 19.6-19.9 V unloaded; 13-19 V fluctuations under load | No confirmed fixed jack or laptop |
| Laptop | [MSI GS65](https://www.reddit.com/r/laptops/comments/1jutr2e) | Owner reports 19.5 V present but charger not recognized | No confirmed fix |
| Laptop | [Dell power adapter identification](https://www.reddit.com/r/techsupport/comments/n7nb5x) | Original adapter 19-20 V; battery connector 3.4, 1.2 and 0 V at various pins | No confirmed fix; do not conflate nominal rail presence with adapter ID |
| Laptop | [ThinkPad S430](https://www.ifixit.com/Answers/View/854222/Laptop+isn't+coming+on.) | Known-good charger tested on another ThinkPad; laptop still dead | No owner measurement or confirmed DC-jack repair |
| Phone | [iPhone 12 Pro screen-dependent charging](https://www.reddit.com/r/mobilerepair/comments/1t8zo1y/iphone_12_pro_charging_issue_only_charges_with/) | 0.4 A off, 0.7-1.2 A screen active, 0 A locked | Owner reports battery replacement resolved problem |
| Phone | [iPhone 16 Pro intermittent charging](https://www.reddit.com/r/iPhone16Pro/comments/1iauzsw) | Charging repeatedly connects/disconnects; restarts and laptop cable tests insufficient | Owner says service-center magnetic-debris cleaning fixed it |
| Console | [Switch V1 black screen](https://www.reddit.com/r/consolerepair/comments/snxpdy) | 0.1/0.44 A charging and ~3.4 V battery, M92 replacement did not fix | Owner found AutoRCM configuration; not an M92 component repair |
| Console | [Switch Lite battery ceiling](https://www.reddit.com/r/consolerepair/comments/1sg0hk5/switch_lite_not_charging_over_36v_how_should_i/) | Battery 3.4->3.6 V after overnight; USB-C VBUS 15 V | No confirmed fix; IC and battery not isolated |
| Console | [Switch V1 CC1 anomaly](https://www.reddit.com/r/Switchrepair/comments/1vk2yy4/v1_switch_boots_on_charged_battery_but_0a/) | CC1 0.126 V diode-mode and 0.00 A; M92 swap transiently changed CC1 | No confirmed final fix; diode values not source rail readings |
| Printer | [HP Smart Tank 615](https://www.reddit.com/r/fuckHPprinters/comments/1kdq7tb) | Initial encoder-strip jam errors plus subsequent tray/ADF failure | Earlier encoder reseating fixed two errors, feed/ADF remain broken |
| Printer | [Epson L3250 carriage](https://www.reddit.com/r/printers/comments/1p2zktz/epson_l3250_printhead_gets_stuck_at_the_same/) | Carriage sticks at repeatable location even after encoder cleaning | No verified repair |
| Printer | [HP OfficeJet 9015e distorted print](https://www.reddit.com/r/printers/comments/1jf1vas) | Alignment and printhead cleaning failed | Owner reports success after encoder strip cleaning |
| Drone | [Homebuilt FPV no lift](https://www.reddit.com/r/diydrones/comments/1qa6rtc/no_lift/) | Motors/props spin without lift; later rotation correction considered | Owner reports the craft flew after direction correction, not a flight-safety certificate |
| Drone | [TinyWhoop no lift](https://www.reddit.com/r/TinyWhoop/comments/1xgbiv5/need_some_help/) | Drone arms, no lift, prop placement initially assumed correct | Owner reports wrong motor direction corrected |

## Measurement and causation integrity

A measurement is counted as **source-reported numeric evidence**, not as HS-instrumented evidence. Charger ratings in responders' replies are not counted as owner measurements. Do not compare diagnostic root-cause accuracy when the source never established root cause. A public forum's "SOLVED" flair is not independently verified component causality. A positive outcome on one device is never imputed to a different commenter.

**Known device category and known diagnostic family** are scored as literal label matches against predeclared known classes. Unknown/out-of-market categories are scored separately for *abstention*. The actual leading hypothesis, software workflow readiness, and risky `solvable_now` verdicts on unresolved cases are reported as evidence of behavior, but not automatically called electrically correct or wrong.

## Safety and next step

Never copy unsafe commenter repair actions into a powered procedure. No DIY lithium battery charging, USB-C microsoldering, live mains-printer cycling, rotating props, autonomous flight or physical acceptance authority is supplied by this benchmark. Subsequent code fixes must use a new developer branch; retesting these same stories after tuning can only be a **regression**, never another untouched generalization measurement.
