import json
import time

import board
import busio
import usb_cdc
from adafruit_bme280 import basic
from sample import read_channels


def find_sensor(bus):
    for address in (0x76, 0x77):
        try:
            return basic.Adafruit_BME280_I2C(bus, address=address)
        except (OSError, RuntimeError, ValueError):
            pass
    return None


bus = busio.I2C(board.GP1, board.GP0, frequency=100000)
port = usb_cdc.data
port.timeout = 0.25
port.write_timeout = 0.5
sensor = None
while True:
    if not port.connected or not port.in_waiting:
        time.sleep(0.01)
        continue
    if port.readline().strip() != b"GJSON":
        continue
    if sensor is None:
        sensor = find_sensor(bus)
    record = read_channels(sensor) if sensor is not None else {"error": "sensor_error"}
    if "error" in record:
        sensor = None
    port.write((json.dumps(record) + "\n").encode("ascii"))
