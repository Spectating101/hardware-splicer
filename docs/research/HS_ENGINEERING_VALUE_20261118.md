# Where Hardware Splicer earns its engineering time

Assessment on 18 November 2026 for a team designing and publishing its own hardware. The strongest case for HS is a family of products where changing one part forces someone to revisit earlier engineering decisions. The repository demonstrates that HS can perform some of that work digitally. The cost per accepted design is still an open question.

## Evidence from hardware builders

| Observation | What it supports |
| --- | --- |
| Voron's maintainers raised the skirts and feet by 2 mm because a 34 mm Z motor interfered with the bottom panel. [Voron 0 release history](https://github.com/VoronDesign/Voron-0#release-history) | A component choice can force an unexpected change elsewhere in a machine. A check that identifies the affected pieces has a concrete purpose. |
| An SO-ARM builder asked for alternatives when two specified servos were unavailable from their source. [Original builder report](https://github.com/TheRobotStudio/SO-ARM100/issues/161) | Sourcing can reopen an engineering decision even for a published design. One report establishes an example but gives no estimate of frequency or willingness to pay. |
| Participants in the ecoEDA study inventoried discarded devices, pooled 192 unique component records and used the inventory during schematic design. [Original study, sections 8.2–8.3](https://lab.plopes.org/published/2023-UIST-ecoEDA.pdf) | A known inventory can inform a design. Someone still has to identify donor parts and record usable information. The study stopped at schematic design. |
| FixturFab already designs board-specific cartridges for reusable fixture bases, updates the bill of materials and has a second engineer review the design. [Fixture design process](https://docs.fixturfab.com/process/fixture-design) | Reusable fixtures are an established approach. A fair comparison gives the alternative workflow credit for its existing templates and engineering checks. |

## Transfer test on a fourth board

The [HS inspection nest](../../projects/pcb-inspection-nest/README.md) has one dock and three registered board holders. I selected an Adafruit Feather M4 Express as a fourth layout, outside that list. Both runs used the existing [builder](../../projects/pcb-inspection-nest/build.py). The test used a published board drawing and generated nominal geometry. It required no purchases.

| Trial | Input and intervention | Result |
| --- | --- | --- |
| Existing PyGamer | Stock profile and pinned board source, normal build entry point | Generated dock and holder in STEP and STL. The reopened solids showed zero overlap when seated and 19.223 mm³ interference when the holder was reversed. |
| Feather, normal build entry point | Supplied the pinned drawing, 50.8 × 22.86 mm outline dimensions, centre (25.4, 11.43) mm and the two named mounting footprints | Stopped with `Expected four distinct mounting holes`. The drawing has four. Two are bare board holes that the profile cannot reference. No Feather holder was generated on this path. |
| Feather, assisted follow-up | Read both named pads and both bare holes from the same drawing, translated them to the board centre, then passed the four records to the existing geometry and verification functions | Generated STEP and STL for the dock and holder. The reopened solids passed pin and shoulder checks. Both seated overlap volumes were zero and the reversed holder interfered by 19.223 mm³. |

For reproduction, the [Feather drawing at the tested revision](https://github.com/adafruit/Adafruit-Feather-M4-Express-PCB/blob/d98407a6071813bc35c39c6e88ca09c0c9ef6f18/Adafruit%20Feather%20M4%20Express.brd) has SHA-256 `439104cb9a23a2df4e3204535889a891f12d246d3ba8bdcaf000b1193a6378a6`. After centring, the named pads U$31 and U$32 are at x = −22.86 mm and y = ±8.89 mm, with a 2.50 mm drill. The two board holes are at x = +22.86 mm and y = ±8.89 mm, with a 2.54 mm drill. The assisted path used `make_base`, `make_carrier`, `export_solid` and `check_fit`. These checks use an unpopulated rectangular board envelope. Underside components, connector access, manufacturing tolerances and physical fit remain unverified.

## Engineering and business implications

The fixture trial demonstrates reuse inside one project. A parametric CAD script can also reuse a dock. Stronger evidence for the broader HS idea comes from its [FieldDeck cyberdeck comparison](../status/generated/fielddeck-5-registered-20261118.json). Raising the assumed Pi working current from 1.0 to 1.35 A took modeled power from 7.25 to 9 W and the lower runtime estimate from 3.166 to 2.55 hours. The revised brief also raised the minimum from 2.5 to 3 hours. That gives the designer a decision before ordering hardware: revise the power budget, change the battery, or narrow the runtime claim. Actual runtime remains unmeasured.

For a team publishing its own designs, the economic unit is **total engineering cost per variant that meets the same release criteria**. Count the original template, source preparation, agent compute, human review, failed attempts and rework. A recorded geometry check has value each time it replaces work an engineer would otherwise repeat. A new input convention can consume part of that saving.

The next decision can be made digitally. Freeze three previously unused board layouts and one acceptance checklist. Run HS and a competent engineer's or agent's reusable CAD template on each, with the same public drawings and required outputs. Record active human minutes, compute cost, failures and omissions separately. Include the setup cost for each route and report how many accepted variants it takes to recover it. The repository's [economics protocol](../experiments/DERIVATIVE_ECONOMICS_PROTOCOL.md) describes isolation and accounting. A positive result would support investment in this product family. Broader claims about arbitrary devices, profitable e-waste recovery or demand for HS as a separate product require different evidence.
