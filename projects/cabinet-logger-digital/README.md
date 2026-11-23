# USB cabinet logger

Monitor temperature, relative humidity and barometric pressure near stored parts or during an enclosure trial. A bench computer polls one device and writes one CSV per capture. Run the same collector against the Pico design or a purchased DogRatIan USB-PA that implements its documented GJSON command. For a cabinet that needs only a local humidity reading, the NT$199 ready-made meter costs less than our sensor alone. [Cost breakdown and alternatives](buy-or-build.md)

## Run the digital cabinet

From this directory, run the following with Python 3. The demo uses only the standard library.

```sh
python3 logger.py demo > my-cabinet.csv
```

The [example CSV](demo.csv) covers one synthetic day in five-minute intervals. A door-opening scenario raises humidity by 12 percentage points for an hour starting at 06:00 UTC. A sensor read fails at 08:20 and an impossible humidity value appears at 16:40. Both produce a timestamp and an error status with empty measurement fields. The next poll in each case succeeds. The 286 good rows and two fault rows come from a scripted input profile. They demonstrate how the records behave. Actual cabinet response, sensor accuracy, USB reliability and ventilation need physical measurements.

## Device and enclosure

Use a Pico H and the 3.3 V GY-BME280 breakout in I²C mode. Proposed connections, matched by signal labels on the actual board, are below. Breakouts with separate CSB and SDO pins need CSB high for I²C and SDO strapped for the chosen address. The driver probes both 0x76 and 0x77. Confirm the breakout has 3.3 V I²C pull-ups and populated headers. [Pico pinout](https://datasheets.raspberrypi.com/pico/Pico-R3-A4-Pinout.pdf) · [Bosch datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf)

| Pico H | Sensor |
|---|---|
| Pin 36, 3V3 OUT | VCC, 3.3 V |
| Pin 38, GND | GND |
| Pin 1, GP0 | SDA |
| Pin 2, GP1 | SCL |

The [STEP assembly](layout.step) places the controller beside a USB opening and reserves space for the sensor near the opposite vent. It uses the listed PW-3 outer dimensions of 125 × 60 × 40 mm. The 2 mm wall, interior, openings, header clearance and 25 × 22 × 12 mm sensor envelope are design assumptions. The open top exposes the layout. Measure the actual lid, bosses, adapter, wiring and case before using the model for a mounting or cutting template. Regenerate with CadQuery 2.6.1 using `python layout.py`. [Editable layout](layout.py) · [PW-3 listing](https://jin-hua.com.tw/page/product/show.aspx?lang=TW&num=3569)

## USB capture

The Pico implementation is a project-specific CircuitPython example. It is independent of HS's ESP32 application generator. For eventual bench use, the Pico needs its board-specific CircuitPython image and the matching library bundle with adafruit_bme280 and its dependencies in CIRCUITPY/lib. Copy the three files from firmware/ to the CIRCUITPY root and restart for boot.py to enable the data port. The proposed USB-PA purchase path uses its existing firmware. [Pico CircuitPython](https://circuitpython.org/board/raspberry_pi_pico/) · [Driver documentation](https://docs.circuitpython.org/projects/bme280/en/latest/api.html) · [USB-PA command specification](https://www.dogratian.com/index.php/sensor/usb-pa-bme280)

On a host with pyserial 3.5, select the Pico **data** port or the USB-PA port. For a two-poll sample on Linux, substitute the actual device path.

```sh
python3 logger.py capture /dev/ttyACM1 --interval 5 --count 2 > capture.csv
```

The default interval is five minutes and default capture continues until interrupted. The host timestamps each reply in UTC and converts pascals to hectopascals. A timeout, sensor error, malformed reply or out-of-range value leaves all three fields blank. The host must remain powered and connected. A disconnected device has no backlog for the host to download. Restart capture to a new file after a physical USB disconnect. [USB data-port documentation](https://docs.circuitpython.org/en/latest/shared-bindings/usb_cdc/)

Digital verification exercised the firmware's command loop with a missing sensor followed by discovery at 0x77. A separate pseudo-terminal exercised the real serial capture command against the supplier's example, injected a timeout, invalid JSON, sensor error and out-of-range reading, then recovered. No board or bought unit was connected. Reference comparison and actual assembly time remain open.
