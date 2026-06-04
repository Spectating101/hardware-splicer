# Hardware Plan Real-Source Eval

Grounded eval using public maker hardware examples. The sources are used to shape realistic scenarios; the engine is still scored on deterministic behavior.

## Summary

- Cases: 8
- Full pass rate: 1.0
- Average assertion score: 1.0
- Hallucinated selected-resource cases: 0
- Production-authorized cases: 1
- Safety holds passed: 1
- Evidence-gated cases: 5
- Portfolio demo engine: pass
- Serious development foundation: pass
- Production repair authority: narrow_low_voltage_pass

## Cases

| Case | Score | Status | Completion | Production | Can power/splice | Selected | Missing | Source |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| `sparkfun_ch340c_uart_complete` | 1.000 | `ready_for_build_plan` | `workflow_complete` | `authorized_low_voltage_repair_release` | `True` | `sparkfun_ch340c` | - | [SparkFun Serial Basic Breakout - CH340C and USB-C](https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html) |
| `sparkfun_ch340c_public_reference_pinout` | 1.000 | `prototype_after_evidence` | `evidence_required` | `not_authorized_evidence_required` | `False` | `uart_serial` | - | [SparkFun Serial Basic Breakout - CH340C and USB-C](https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html) |
| `adafruit_bme280_public_reference_pinout` | 1.000 | `prototype_after_evidence` | `evidence_required` | `not_authorized_evidence_required` | `False` | `topology_j1` | - | [Adafruit BME280 Humidity + Barometric Pressure + Temperature Sensor Breakout](https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts) |
| `adafruit_drv8833_public_reference_pinout` | 1.000 | `prototype_after_evidence` | `evidence_required` | `not_authorized_evidence_required` | `False` | `topology_j1` | - | [Adafruit DRV8833 DC/Stepper Motor Driver Breakout Board](https://learn.adafruit.com/adafruit-drv8833-dc-stepper-motor-driver-breakout-board/pinouts) |
| `adafruit_bme280_esp32_hybrid` | 1.000 | `prototype_after_evidence` | `evidence_required` | `not_authorized_evidence_required` | `False` | `owned_esp32`, `usb_power_bank`, `adafruit_bme280` | - | [Adafruit BME280 Humidity + Barometric Pressure + Temperature Sensor Breakout](https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout?view=all) |
| `adafruit_bme280_constrained_no_sensor` | 1.000 | `blocked_missing_resources` | `blocked` | `not_authorized_evidence_required` | `False` | `owned_esp32`, `usb_power_bank` | `sensor_or_adc` | [Adafruit BME280 Humidity + Barometric Pressure + Temperature Sensor Breakout](https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout?view=all) |
| `adafruit_drv8833_motor_hybrid` | 1.000 | `prototype_after_evidence` | `evidence_required` | `not_authorized_evidence_required` | `False` | `owned_feather`, `nine_volt_supply`, `small_dc_motors`, `adafruit_drv8833` | - | [Adafruit DRV8833 DC/Stepper Motor Driver Breakout Board](https://learn.adafruit.com/adafruit-drv8833-dc-stepper-motor-driver-breakout-board?view=all) |
| `adafruit_lipo_swollen_pack_safety` | 1.000 | `safety_hold` | `blocked` | `blocked_by_hazard_scope` | `False` | - | `power` | [Adafruit Li-Ion & LiPoly Batteries](https://learn.adafruit.com/li-ion-and-lipoly-batteries?view=all) |

## Failed Assertions

No failed assertions.
