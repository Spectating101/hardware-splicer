# Mapping robot v0, Build 1 test 1: parts sourced and understood

**Status: sourced, not measured.** Every part below is a real, current listing, and each fact names its source. Nothing has been bought, contacted or measured; a number here is what a document says, not what a part does.

## Chosen parts

| Kind | Part | Listing | Variant | Facts: published / typical / conflicting / unconfirmed |
|---|---|---|---|---|
| drive_motor | JGA25-371 12 V 110 rpm gearmotor with 11-pulse Hall encoder (sold as a set with a 65 mm wheel, bracket and coupling) | [https://www.ruten.com.tw/item/21205165759474/](https://www.ruten.com.tw/item/21205165759474/) NT$550 (ruten) | 12V110RPM: the listing has one variant, 下標請告知電壓和轉速, so the buyer states voltage and speed when ordering | 9 / 2 / 1 / 3 |
| wheel | 65 mm wheel included in the JGA25-371 set | [https://www.ruten.com.tw/item/21205165759474/](https://www.ruten.com.tw/item/21205165759474/) NT$550 (ruten) | included in the 12V110RPM set (one listing variant) | 1 / 1 / 0 / 2 |
| lidar | Slamtec RPLIDAR C1 (C1M1) 360° DTOF 2D LiDAR | [https://www.ruten.com.tw/item/22403646891274/](https://www.ruten.com.tw/item/22403646891274/) NT$2700 (ruten) | only variant (the listing has no options) | 12 / 0 / 0 / 1 |
| compute_board | Raspberry Pi 4 Model B, 4 GB | [https://www.ruten.com.tw/item/22640800216898/](https://www.ruten.com.tw/item/22640800216898/) NT$3171 (ruten) | only variant (4GB, no options) | 6 / 2 / 0 / 1 |
| imu | GY-521 breakout with InvenSense MPU-6050 6-axis IMU | [https://www.ruten.com.tw/item/21438233309457/](https://www.ruten.com.tw/item/21438233309457/) NT$85 (ruten) | only variant (no options) | 4 / 0 / 0 / 1 |
| battery_pack | 12 V (3S2P) 18650 Li-ion pack, 6000 mAh, with protection board and charger | [https://www.ruten.com.tw/item/22627027679167/](https://www.ruten.com.tw/item/22627027679167/) NT$900 (ruten) | 3S2P 6000Ah (the seller's label; the description gives 6000 mAh) | 4 / 2 / 0 / 2 |
| dc_dc_converter | XL4015 5 A adjustable buck module (with heatsink) | [https://www.ruten.com.tw/item/21519300644500/](https://www.ruten.com.tw/item/21519300644500/) NT$40 (ruten) | only variant (no options) | 6 / 0 / 0 / 0 |
| caster | Ball caster, 25 mm ball (牛眼萬向輪) | [https://www.ruten.com.tw/item/22424722682045/](https://www.ruten.com.tw/item/22424722682045/) NT$25 (ruten) | 萬向輪（球直徑25mm）1個 | 1 / 0 / 0 / 3 |

## Open questions: measure these on the bench

JGA25-371 12 V 110 rpm gearmotor with 11-pulse Hall encoder (sold as a set with a 65 mm wheel, bracket and coupling):
- **encoder_cpr** 11 or 12 count/rev_motor (conflicting): Seller: 11 signals per motor revolution on each of two channels. Open Impulse: 12 counts per revolution. Count on the bench before trusting odometry.
- **run_current** 0.18 A (typical): Derived, not published: linear DC motor model I = I0 + (Istall - I0) x T/Tstall with Open Impulse's I0 46 mA and Istall 1 A, Tstall 0.381 N·m at 11.1 V, and a carpet load (rolling coefficient 0.1, 1.1 kg, 65 mm wheel) of 0.0175 N·m per motor, giving 0.09 A; doubled for margin. Measure on the bench.
- **stall_torque** 0.412 N·m (typical): Not published for the seller's 110 rpm ratio. Open Impulse's neighbouring ratios bracket it: 4.2 kg·cm at 126 rpm (1:34) and 5.5 kg·cm at 95 rpm (1:45); the lower bound, 4.2 kg·cm = 0.412 N·m, is used. Measure on the bench.
- **rated_current** unconfirmed: No source publishes the current at rated load; run_current is derived instead.
- **gear_ratio** unconfirmed: The seller lists speeds only. Open Impulse's ratios (1:34 at 126 rpm, 1:45 at 95 rpm) do not include 110 rpm. Counts per wheel revolution must be measured.
- **body_dimensions** unconfirmed: Diameter 25 mm is published; gearbox length depends on ratio and is not published for 110 rpm. Measure the part.

65 mm wheel included in the JGA25-371 set:
- **mass** 30 g (typical): Not published; class-typical for a 65 mm rubber robot wheel. Weigh it, i.e. measure on the bench.
- **width** unconfirmed: Not published by the seller; measure the wheel.
- **bore** unconfirmed: Not published; the set includes a coupling (連軸器) for the 4 mm D shaft, so the wheel bore matches the coupling, not the shaft. Measure.

Slamtec RPLIDAR C1 (C1M1) 360° DTOF 2D LiDAR:
- **body_dimensions** unconfirmed: The datasheet gives dimensions only as a drawing (Figure 4-1). Retailers state 55.6 x 55.6 x 41.3 mm, but no page stating it could be captured for checking. Read the drawing or measure the part.

Raspberry Pi 4 Model B, 4 GB:
- **typical_current** 1.4 A (typical): Raspberry Pi publishes 600 mA typical for a bare board. SLAM Toolbox and Nav2 keep all four cores busy, so 1.4 A (7 W) is assumed, between that figure and the 3.0 A supply rating. Measure on the bench.
- **mass** 46 g (typical): Raspberry Pi does not publish the board's mass; 46 g is class-typical. Weigh it, i.e. measure on the bench.
- **body_dimensions** unconfirmed: The product brief gives dimensions only as a drawing. Read the drawing or measure the board.

GY-521 breakout with InvenSense MPU-6050 6-axis IMU:
- **body_dimensions** unconfirmed: Not published, and the seller may ship a different factory's layout. Measure the board received.

12 V (3S2P) 18650 Li-ion pack, 6000 mAh, with protection board and charger:
- **nominal_voltage** 11.1 V (typical): The seller labels the pack 12V(12.6V). A 3S Li-ion pack's nominal voltage is 3 x 3.6-3.7 V = 10.8-11.1 V, so 11.1 V is used. Measure on the bench.
- **mass** 300 g (typical): Not published; six 18650 cells at about 45 g plus board and wrap. Weigh it, i.e. measure on the bench.
- **connector** unconfirmed: Not published. Check the plug on the pack and the included charger.
- **body_dimensions** unconfirmed: The seller states 18 x 58 x 65 mm, which cannot hold six 18650 cells (two cells side by side need about 36 mm). Treat as wrong; measure the pack.

Ball caster, 25 mm ball (牛眼萬向輪):
- **height** unconfirmed: Only the ball diameter is published; the chassis plan sets ride height with a printed spacer after measuring the caster.
- **mount** unconfirmed: Not published; the photo shows a flanged housing but hole spacing is not stated. Measure.
- **mass** unconfirmed: Not published; small enough to sit inside the chassis allowance. Weigh it.

## Sizing through HS robotics simulation

The design meets the targets.

| Quantity | Value | Target |
|---|---|---|
| Runtime, continuous mapping | 222.79 min | ≥ 60 min |
| Speed margin at 0.2 m/s | 1.731 | ≥ 1.5 |
| Wheel speed needed | 58.76 rpm | motor gives 101.7 rpm at pack voltage |
| Force margin (acceleration and rolling only) | 7.853 | ≥ 1 |
| Robot mass | 1.316 kg | |
| Average power | 14.349 W | |

Assumptions (not part facts):

- `usable_fraction` = 0.8 (typical): share of a Li-ion pack's rated energy used before the BMS cut-off; measure on the bench
- `converter_efficiency` = 0.85 (typical): buck converter efficiency at about 1-2 A; measure on the bench
- `mcu_power_w` = 0.5 (typical): ESP32-class microcontroller average with Wi-Fi idle; measure on the bench
- `chassis_mass_kg` = 0.6 (typical): printed chassis, board, fasteners, caster and wiring; weigh it

## Quote check

49 quotes checked against captured copies of their sources: all found.


Gaps in HS met on the way are in `GAP_LOG.md`; why each part was chosen is in `selection/`.
