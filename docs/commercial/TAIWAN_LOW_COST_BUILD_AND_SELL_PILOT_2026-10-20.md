# Hardware Splicer — Taiwan first hardware-product pilot, 20 October 2026

## Product factory scope and decision

The commercial goal is to **build a genuinely useful physical device first**, then evaluate whether repeatable, safe physical units can be sold. This follows PRODUCT_FACTORY_PROTOCOL.md: source/listing prices, simulation and printable artifacts are not physical acceptance or sales evidence.

Two parallel tracks:

**A. First likely sale experiment: modular non-powered PCB/phone-repair bench fixture.**
Swappable non-marring jaw modules and an adjustable rigid base, initially for our own electronics/repair work. A generic PCB fixture sells from NT$336 in Taiwan (https://www.ruten.com.tw/item/22635511227578/); a nominal NT$1,190 hypothesis only makes sense if the custom fixture demonstrates a real differentiation such as multi-board compatibility, modular jaws, rigidity and repair repeatability. First article and demand NOT yet tested.

**B. Main engineering demonstration: compact 4-axis arm.**
Reduce the previous 420 mm/150 g research arm to an illustrative 200–250 mm reach and <=30 g *initial target payload*. Investigate two actual DS3218 180-degree servos for shoulder/elbow and two MG996R 180-degree positional servos for yaw/wrist, plus a small MG90S for gripper. These are candidates, NOT verified continuous output drives. Its primary reward is an internal instrumented motion/fixture platform. At a hypothesized NT$5,990 asking price, assembled-arm economics are weak relative to existing kit competition.

**C. Secondary product: articulated inspection camera stand.**
Potentially useful for filming repairs and recording donor components. The inspection load, stability and willingness-to-pay are untested. Hold until A/B provide shared printing and hardware experience.

## Taiwan supplier references — advertised, not actual checkout

All prices NT dollars as viewed 2026-10-20, subject to variant/shipping/stock confirmation. The exact product/source basis is structured in examples/procurement/taiwan_small_hardware_products_20261020.json.

| Component | Indicative single unit | Source |
| --- | ---: | --- |
| MG996R positional 180-degree servo | NT$145 option | https://www.ruten.com.tw/item/21610014880630/ |
| DS3218MG high-torque 180-degree servo | NT$475 | https://www.ruten.com.tw/item/22638691325276/ |
| MG90S positional gripper servo | NT$83–90 | https://www.ruten.com.tw/item/21210302605787/ |
| ESP32 DevKit 30-pin | NT$169 | https://www.ruten.com.tw/item/22541165012010/ |
| PCA9685 I2C PWM module | NT$122 | https://www.ruten.com.tw/item/22326111365451/ |
| PETG 1 kg spool | NT$554–599 | https://www.ruten.com.tw/item/22632341480050/ |
| PLA 1 kg spool | NT$499 | https://www.ruten.com.tw/item/22046953019764/ |
| 608ZZ bearing | NT$13 each | https://www.ruten.com.tw/item/22635479599540/ |
| M3 heat-set inserts | NT$60–124 multi-variant bag; unit economics ASSUME NT$2/insert | https://www.ruten.com.tw/item/22540097538746/ |
| Safe enclosed low-voltage servo power supply | UNVERIFIED NT$500 planning budget | NO QUALIFIED VENDOR OR PART SELECTED |

Do **not** choose an exposed 110/220 V mains terminal power supply just because a generic 5V10A board is advertised cheaply. Need verified enclosed/approved adapter, effective output/current for simultaneous servos, protected distribution and controlled low-voltage commissioning. The DS3218 '20 kg-cm' and MG996R '13 kg-cm' figures are typically advertised STALL torque, not verified sustainable joint torque under speed/heat. Sellers sometimes publish contradictory torque specifications; measure actual samples. Confirm exact 180-degree positional options instead of continuous-rotation variants.

Published competitor listings: acrylic 4DOF kit at NT$897 (https://www.ruten.com.tw/item/22230882402946/), 4DOF metal variants NT$981–3,974 with lowest without servos (https://www.ruten.com.tw/item/22632331612269/), metal 4DOF arm at NT$2,581 without the main control board (https://www.ruten.com.tw/item/22628061812064/). Commercializing a generic arm at NT$5,990 would require a strong, experimentally demonstrated feature set and buyer validation, not merely printable design files.

## Unit economics — explicit hypotheses, not realized margin

Assumes illustrative assembly labor at NT$200/hour, 10% platform selling fee, packaging, outbound handling, small QA/return reserve, and planned BOM values. No actual customer willingness-to-pay, first-article print, production yield or sale. Excludes taxes, printer CAPEX, R&D amortization, insurance and advertising. Net amounts below are contribution before those fixed expenses.

| Candidate | Assumed selling NT$ | Nonprint hardware NT$ | Own-print contribution NT$ | Outsource low-price contribution NT$ | At NT$5/g outsourced NT$ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Modular repair jig | 1,190 | 250 | +421 | +329 | -319 |
| Articulated camera stand | 1,490 | 419 | +370 | +254 | -538 |
| Compact educational arm | 5,990 | 2,713 | +1,269 | +978 | -642 |

Own-print scenario uses PETG NT$554/kg plus assumed power/wear/scrap and DOES NOT include purchasing a 3D printer. The low outsourced PETG quote is a provider-advertised 'from NT$1.4/g' and minimum NT$150 per order (https://www.wancai-3d.com/fabrication-services-1), not a confirmed quote for our geometry. A different provider advertises NT$5/g PLA plus machine-hour charges (https://www.tasker.com.tw/workroom/voq3NR/service-detail/38343). NT$5/g here is a higher-rate illustration and NOT an actual PETG quotation; exact vendor PETG quotes can be higher still. At the higher outsourced price, **all three concepts have negative contribution at their hypothetical prices**.

The source-bound, recalculable BOM/economics are in:
- examples/procurement/taiwan_small_hardware_products_20261020.json
- docs/commercial/LOW_COST_BUILD_ECONOMICS_RESULT_2026-10-20.json
- scripts/evaluate_small_hardware_product_economics.py

## Build and evidence sequence

### Pilot A: first physical repair fixture

1. Freeze one job: adjustable 30–100 mm provisional gripping span, replaceable non-marring inserts, reversible screw/bearing mount, unpowered board-only workholding. These are design requirements, not manufactured/tested capabilities.
2. Create SolidCraft parametric jaws and rail/clamp supports; PartCAD two-jaw assembly and BOM; slice actual STL/3MF and procure a REAL manufacturing quotation including PETG, supports, postprocessing, delivery and tolerance.
3. Buy only enough M3 inserts/fasteners/bearings/grip pads for ONE article. Outsource one set until printer access is demonstrated; don't price the whole spool as the cost of one fixture.
4. Assemble, measure clamp opening/deflection and fit actual boards. Check workholding force, board scratching, slippage and repeatability. PETG is NOT ESD rated or a safe soldering-iron contact material without further validation.
5. Use it ourselves in multiple repair sessions. Preserve before/after observations and defects; revise. Separately ask at least five potential customers whether they would pay for a specified premium over existing cheap jigs.
6. Only physically validated, repeatable, legally compliant units become bounded build-to-order experiments. No speculative inventory or claimed orders.

### Pilot B: arm build from parts, not operating a borrowed arm

1. Initial arm target is modest (illustrative 200–250 mm, <=30 g pickup). We must re-derive required torque with ACTUAL motor/link/gripper masses; the prior 400+ mm arm simulations and 20 Nm assumed geared motors do not transfer to a cheap servo build.
2. Buy one representative DS3218 and one MG996R first, verify versions, actual servo range and controlled torque/current/temperature at safe low loads. Do not buy a 5-motor lot before the bench results.
3. Source an enclosed compatible low-voltage servo supply, a suitable multimeter/current-monitoring arrangement, verified wiring, fusing, positional homing/end limits and independent stop. The PCA9685 is a PWM signal distributor, NOT motor-power distribution or a safety circuit.
4. Design load-bearing links and joint brackets in SolidCraft from measured servo/shaft/fastener envelopes; map PartCAD and URDF inertias/collision geometry; re-run adverse servo torque and collision checks. Previous HS research arm had base collisions.
5. Print a fit coupon and one joint prototype, inspect structure, fasteners, bearing fit and deformation. Build the arm unpowered and guard pinch regions before commissioning.
6. Only with appropriate equipment, documented electrical interfaces and explicit human safety approval energize ONE isolated axis at low speed/current; validate stops, encoder/position feedback and heat before more joints.
7. Use the working arm as an internal HS testbed. Do not offer retail until several consistent physical test cycles and genuine willingness-to-pay evidence overcome the NT$897-2,581 kit competition.

### Prototype budget and release decisions

Planning cash envelope: fixture first article approx NT$600–1,200; arm initial servo/electronics characterization NT$900–1,600 excluding missing bench tools; a complete compact custom arm may exceed NT$3,000–4,500 before outsource and rework. These are cash planning ranges, NOT vendor quotes. Avoid a printer purchase until actual outsourcing cost, printing capacity and workload justify it.

Status under PRODUCT_FACTORY_PROTOCOL: **HOLD FOR PHYSICAL DERIVATIVE EXPERIMENT**. No actual parts ordered; no usable owned printer or motor identified; no market demand/revenue observed. Before selling, confirm product-specific Taiwan BSMI inspection rules, possible NCC/WiFi requirements, applicable tax/business rules and product liability (BSMI classification enquiry: https://www.bsmi.gov.tw/bsmiGIP/wSite/ct?ctNode=9814&mp=1&xItem=110595).

**Decision:** Treat the arm as the serious personal-use engineering build; treat the customized repair fixture as the earlier, lower-risk product economics experiment. Both share SolidCraft, PartCAD, PETG, M3 inserts and small-batch QA and remain useful if sales never happen.
