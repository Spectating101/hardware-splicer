# Mapping robot v0, Build 1 test 1: parts sourced and understood

**Status: sourced, not measured.** Every part below is a real, current listing, and each fact names its source. Nothing has been bought, contacted or measured; a number here is what a document says, not what a part does.

## Chosen parts

| Kind | Part | Listing | Variant | Facts: published / typical / conflicting / unconfirmed |
|---|---|---|---|---|
| drive_motor | JGA25-371 12 V 110 rpm gearmotor (8,500 rpm motor, 1:78 gearbox) with Hall encoder, sold as a set with a 65 mm wheel, bracket and coupling | [https://www.ruten.com.tw/item/21205165759474/](https://www.ruten.com.tw/item/21205165759474/) NT$550 (ruten) | 12V110RPM: the listing has one variant, 下標請告知電壓和轉速, so the buyer states voltage and speed when ordering | 11 / 1 / 2 / 1 |
| wheel | 65 mm wheel included in the JGA25-371 set | [https://www.ruten.com.tw/item/21205165759474/](https://www.ruten.com.tw/item/21205165759474/) NT$550 (ruten) | included in the 12V110RPM set (one listing variant) | 1 / 1 / 0 / 2 |
| lidar | Slamtec RPLIDAR C1 (C1M1) 360° DTOF 2D LiDAR | [https://www.ruten.com.tw/item/22403646891274/](https://www.ruten.com.tw/item/22403646891274/) NT$2700 (ruten) | only variant (the listing has no options) | 13 / 0 / 0 / 1 |
| compute_board | Raspberry Pi 4 Model B, 4 GB | [https://www.ruten.com.tw/item/22640800216898/](https://www.ruten.com.tw/item/22640800216898/) NT$3171 (ruten) | only variant (4GB, no options) | 7 / 2 / 0 / 1 |
| imu | GY-521 breakout with InvenSense MPU-6050 6-axis IMU | [https://www.ruten.com.tw/item/21438233309457/](https://www.ruten.com.tw/item/21438233309457/) NT$85 (ruten) | only variant (no options) | 4 / 0 / 0 / 1 |
| battery_pack | 12 V (3S2P) 18650 Li-ion pack, 6000 mAh, with protection board and charger | [https://www.ruten.com.tw/item/22627027679167/](https://www.ruten.com.tw/item/22627027679167/) NT$900 (ruten) | 3S2P 6000Ah (the seller's label; the description gives 6000 mAh) | 3 / 3 / 0 / 2 |
| dc_dc_converter | XL4015 5 A adjustable buck module (with heatsink) | [https://www.ruten.com.tw/item/21519300644500/](https://www.ruten.com.tw/item/21519300644500/) NT$40 (ruten) | only variant (no options) | 6 / 0 / 0 / 0 |
| caster | Ball caster, 25 mm ball (牛眼萬向輪) | [https://www.ruten.com.tw/item/22424722682045/](https://www.ruten.com.tw/item/22424722682045/) NT$25 (ruten) | 萬向輪（球直徑25mm）1個 | 1 / 0 / 0 / 3 |

## Open questions: measure these on the bench

JGA25-371 12 V 110 rpm gearmotor (8,500 rpm motor, 1:78 gearbox) with Hall encoder, sold as a set with a 65 mm wheel, bracket and coupling:
- **output_free_speed_rpm** 110 or 108 rpm (conflicting): Seller lists 110 rpm; NFP's 78:1 row gives 108 rpm with ±15% tolerance on reduced speeds. Measure on the bench.
- **encoder_cpr** 11 or 12 count/rev_motor (conflicting): Seller: 11 signals per motor revolution on each of two channels. Open Impulse's JGA25-371 (a different winding, same encoder family) says 12 counts per revolution. Count on the bench before trusting odometry.
- **gear_ratio** 78 ratio (typical): Inferred, not published for the seller's part: NFP's 108 rpm row is 78:1. Count encoder pulses per wheel turn to measure it on the bench.
- **body_dimensions** unconfirmed: Diameter 25 mm is published; gearbox length depends on ratio and is not published for 110 rpm. Measure the part.

65 mm wheel included in the JGA25-371 set:
- **mass** 30 g (typical): Not published; class-typical for a 65 mm rubber robot wheel. Weigh it, i.e. measure on the bench.
- **width** unconfirmed: Not published by the seller; measure the wheel.
- **bore** unconfirmed: Not published; the set includes a coupling (連軸器) for the 4 mm D shaft, so the wheel bore matches the coupling, not the shaft. Measure.

Slamtec RPLIDAR C1 (C1M1) 360° DTOF 2D LiDAR:
- **body_dimensions** unconfirmed: The datasheet gives dimensions only as a drawing (Figure 4-1). Retailers state 55.6 x 55.6 x 41.3 mm, but no page stating it could be captured for checking. Read the drawing or measure the part.

Raspberry Pi 4 Model B, 4 GB:
- **typical_current** 1.4 A (typical): Raspberry Pi publishes 600 mA idle and 1.2 A average under stress for the 4B. SLAM Toolbox and Nav2 load all four cores, so 1.4 A (7 W) is assumed, above the stress average. Measure on the bench.
- **mass** 46 g (typical): Raspberry Pi does not publish the board's mass; 46 g is class-typical. Weigh it, i.e. measure on the bench.
- **body_dimensions** unconfirmed: The product brief gives dimensions only as a drawing. Read the drawing or measure the board.

GY-521 breakout with InvenSense MPU-6050 6-axis IMU:
- **body_dimensions** unconfirmed: Not published, and the seller may ship a different factory's layout. Measure the board received.

12 V (3S2P) 18650 Li-ion pack, 6000 mAh, with protection board and charger:
- **nominal_voltage** 11.1 V (typical): The seller labels the pack 12V(12.6V). A 3S Li-ion pack's nominal voltage is 3 x 3.6-3.7 V = 10.8-11.1 V, so 11.1 V is used. Measure on the bench.
- **capacity** 2400 mAh (typical): The seller says 6000 mAh, but its stated size (18 x 58 x 65 mm) is one row of three 18650 cells, a 3S1P layout, and the listing's variants run from '2400' to '6000' with one shared description. The smallest variant's 2400 mAh is used as the worst case. Measure capacity on the bench.
- **mass** 300 g (typical): Not published; 300 g assumes six cells (worst case for traction); three cells would be about 150 g. Weigh it, i.e. measure on the bench.
- **connector** unconfirmed: Not published. Check the plug on the pack and the included charger.
- **body_dimensions** unconfirmed: The seller states 18 x 58 x 65 mm, which fits three 18650 cells (3S1P), not the six a 3S2P pack needs. Measure the pack.

Ball caster, 25 mm ball (牛眼萬向輪):
- **height** unconfirmed: Only the ball diameter is published; the chassis plan sets ride height with a printed spacer after measuring the caster.
- **mount** unconfirmed: Not published; the photo shows a flanged housing but hole spacing is not stated. Measure.
- **mass** unconfirmed: Not published; small enough to sit inside the chassis allowance. Weigh it.

## Sizing through HS robotics simulation

The design meets the targets.

| Quantity | Value | Target |
|---|---|---|
| Runtime, continuous mapping | 66.49 min | ≥ 60 min |
| Speed margin at 0.2 m/s | 1.516 | ≥ 1.5 |
| Wheel speed needed | 58.76 rpm | motor gives 99.9 rpm at pack voltage |
| Force margin (acceleration and rolling only) | 14.33 | ≥ 1 |
| Pack peak current (motors at their limit, electronics at peak, minimum voltage) | 3.68 A | ≤ 4.0 A |
| 5 V converter peak | 2.55 A | ≤ 4.5 A |
| Door threshold torque per motor | 0.371 N·m available | ≥ 0.306 N·m |
| Robot mass | 1.316 kg | |
| Average power | 19.233 W | |

Warnings:

- full charge 12.6 V is above the motor's 12.0 V rating; limit PWM duty or accept slightly over-volted motors when the pack is full

Assumptions (not part facts):

- `usable_fraction` = 0.8 (typical): share of a Li-ion pack's rated energy used before the BMS cut-off; measure on the bench
- `converter_efficiency` = 0.85 (typical): buck converter efficiency at about 1-2 A; measure on the bench
- `mcu_power_w` = 0.5 (typical): ESP32-class microcontroller average with Wi-Fi idle; measure on the bench
- `chassis_mass_kg` = 0.6 (typical): printed chassis, board, fasteners, caster and wiring; weigh it
- `min_operating_voltage` = 9.9 (typical): 3S Li-ion at 3.3 V per cell, near the end of useful charge; the pack's BMS cuts off at 8 V. Measure the voltage under load at end of run.
- `motor_current_limit_a` = 1.2 (design): Requirement for the board plan: the motor driver regulates each motor to 1.2 A. Without it two stalled motors (2 x 2.6 A) exceed the pack's 4 A.
- `step_height_mm` = 10 (design): door threshold the robot must climb
- `drive_wheel_load_fraction` = 0.7 (typical): share of weight on the two drive wheels with a rear caster; measure on the bench with a scale under each wheel
- `step_torque_margin` = 2.0 (design): margin on the threshold torque

## Handed to later stages

- The microcontroller is not a bought module here: it is soldered on the HS board as a module from the LCSC/JLCPCB catalogue, chosen in the board plan; its power is the `mcu_power_w` assumption above.
- `motor_current_limit_a` = 1.2: Requirement for the board plan: the motor driver regulates each motor to 1.2 A. Without it two stalled motors (2 x 2.6 A) exceed the pack's 4 A.
- `step_height_mm` = 10: door threshold the robot must climb
- `step_torque_margin` = 2.0: margin on the threshold torque
- Dimensions given only as drawings (LiDAR, Raspberry Pi) are read from those drawings by the chassis plan.

## Quote check

55 quotes checked against captured copies of their sources: all found.


Gaps in HS met on the way are in `GAP_LOG.md`; why each part was chosen is in `selection/`.
