# Internet Reference Corpus Eval

Public internet sources are evaluated as reference/planning evidence only.

## Summary

- Dataset/source lanes: 7
- Reference board cases: 10
- Pass rate: 1.0
- Overclaim cases: 0
- Measurement-plan cases: 10
- Estimated arbitrary-board push: 60_to_75_or_80_percent_before_physical_bench_cases

## Source Lanes

| Source | Access | Use | Limits |
| --- | --- | --- | --- |
| [SparkFun open hardware repositories and product docs](https://github.com/sparkfun) | `public` | `reference_topology`, `pinout_seed`, `measurement_plan` | Reference only; physical board revision and condition still require bench confirmation. |
| [Adafruit PCB design files and Learn pinouts](https://learn.adafruit.com/accessing-and-using-adafruit-pcb-design-files/overview) | `public` | `reference_topology`, `resource_catalog`, `measurement_plan` | Reference only; Eagle/GitHub files do not prove the user's board is intact. |
| [FICS PCB Image Collection](https://physicaldb.ece.ufl.edu/index.php/fics-pcb-image-collection-fpic/) | `registration_required` | `visual_candidate_training`, `ocr_training`, `component_detection_eval` | Excellent visual corpus, but no direct repair/pinout authority without measurements. |
| [PCB Component Detection dataset](https://datasetninja.com/pcb-component-detection) | `public_dataset` | `component_detection_eval`, `salvage_visual_candidate_training` | Component boxes support visual grounding, not electrical topology or safe reuse. |
| [DeepPCB and related PCB defect datasets](https://github.com/tangsanli5201/DeepPCB) | `public_dataset` | `defect_detection_eval`, `hazard_visual_candidate_training` | Mostly surface-defect inspection; not a functional repair/topology dataset. |
| [Open Repair Alliance repair attempts dataset](https://openrepair.org/open-data/downloads/) | `public_dataset` | `failure_mode_prior`, `repair_value_prior`, `outcome_taxonomy` | Strong repair priors, but no board-level topology or measurement evidence. |
| [OSHWA certified open source hardware API](https://certificationapi.oshwa.org/endpoints/) | `public_api` | `source_discovery`, `documentation_discovery`, `license_filtering` | Discovery layer; docs must still be parsed and bench-gated. |

## Cases

| Case | Pass | Authority | Required Measurements | Overclaim | Source |
| --- | --- | --- | ---: | --- | --- |
| `sparkfun_ch340c_usb_serial_reference` | `True` | `visual_candidate` | 11 | `False` | [source](https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html) |
| `adafruit_bme280_sensor_reference` | `True` | `visual_candidate` | 5 | `False` | [source](https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts) |
| `adafruit_drv8833_motor_driver_reference` | `True` | `visual_candidate` | 5 | `False` | [source](https://learn.adafruit.com/adafruit-drv8833-dc-stepper-motor-driver-breakout-board/pinouts) |
| `adafruit_mcp23017_gpio_reference` | `True` | `visual_candidate` | 5 | `False` | [source](https://learn.adafruit.com/adafruit-mcp23017-i2c-gpio-expander/pinouts) |
| `sparkfun_qwiic_soil_moisture_reference` | `True` | `visual_candidate` | 5 | `False` | [source](https://learn.sparkfun.com/tutorials/qwiic-soil-moisture-sensor-hookup-guide/all) |
| `sparkfun_qwiic_relay_reference` | `True` | `visual_candidate` | 5 | `False` | [source](https://learn.sparkfun.com/tutorials/qwiic-relay-hookup-guide/all) |
| `arduino_uno_rev3_headers_reference` | `True` | `visual_candidate` | 5 | `False` | [source](https://docs.arduino.cc/hardware/uno-rev3/) |
| `raspberry_pi_40pin_reference` | `True` | `visual_candidate` | 12 | `False` | [source](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) |
| `adafruit_powerboost_1000c_reference` | `True` | `visual_candidate` | 5 | `False` | [source](https://learn.adafruit.com/adafruit-powerboost-1000c-load-share-usb-charge-boost/pinouts) |
| `adafruit_pam8302_audio_amp_reference` | `True` | `visual_candidate` | 5 | `False` | [source](https://learn.adafruit.com/adafruit-pam8302-mono-2-5w-class-d-audio-amplifier/pinouts) |

## Failed Checks

No failed checks.
