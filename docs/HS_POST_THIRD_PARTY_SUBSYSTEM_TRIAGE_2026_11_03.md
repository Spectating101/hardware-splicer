# Post-#271 repair subsystem routing repairs — development only

The independently frozen #271 source evidence remains **unchanged**, including its original 34 predictions, labels, and raw reports. The first replay correctly matched **22/24** supported product categories, **14/16** broad diagnostic families, and abstained **10/10** OOD checkpoints, but its leading fault and software readiness still failed important source-specific differentials.

### Newly observed weaknesses

- Game Boy with confirmed audio output defects or abnormal LCD-bias power still defaulted to AA battery contacts, including two unresolved cases labeled software `solvable_now`.
- ThinkPad S430 was misclassified as a small USB gadget; it lacked explicit ThinkPad model identity.
- Dell and MSI charger-detection cases with nominal adapter voltage were given generic battery charge candidates instead of interrogating adapter ID, DC-in sense, or compatible supply.
- ASUS barrel-charger fluctuation was misrouted to a laptop USB-C input fault despite separate USB-C charging working.
- Switch with charging current and black-screen no-boot was routed toward the USB-C/HDMI port without considering boot software/AutoRCM as an unverified alternative.
- iPhone 12 Pro with degraded battery and state-dependent charging was routed to replacement port/flex, not a battery/BMS versus controller differential; owner reported battery replacement succeeded.
- Printer printing-registration failures were routed to relay/driver electronics instead of encoder and printhead-positioning evidence.
- FPV drone with powered motors and no lift did not enter the existing propeller/motor-orientation differential when the wording was "fails to take off."

### Software changes

`repair_differential_triage.py` now adds separate **unverified** subsystem branches for LCD-bias, retro audio, DC adapter identification, barrel supply droop, battery/BMS state, console boot versus port, printer print registration, and expanded no-lift drone wording. Exact ThinkPad/Ideapad/Latitude/Zephyrus identity outranks market-value keywords.

All new branches prevent premature replacement and mark `repair_ready=false`, while requiring qualified measurements and refusing to authorize live printer movement, drone flight, unsafe battery work, or guessed component replacement. Source owner repairs remain self-reported, not verified device certification.

### Evaluation integrity

This PR is a **post-holdout development change**. Its synthetic regressions were authored with knowledge of #271's failures and MUST NOT be counted as new blind evidence. Its CI asserts the original frozen #271 source blob `c4473c96309cd95d043e12dcaf4c9f308e66960d` and the original benchmark/verifier are unchanged. Older #269 synthetic checks also run to detect direct regression.

A third untouched corpus or controlled physical bench observations is necessary before claiming real generalization. Even a perfect synthetic score would show only software regression success, not correctly repaired devices.
