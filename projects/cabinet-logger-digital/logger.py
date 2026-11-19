"""Capture cabinet measurements with the same CSV format for either USB device."""

import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from itertools import count

from firmware.sample import read_channels

COLUMNS = ("utc", "source", "status", "temperature_c", "humidity_pct", "pressure_hpa")


def decode(reply):
    if not reply:
        return ("timeout",)
    try:
        data = json.loads(reply)
        if not isinstance(data, dict):
            return ("invalid_reply",)
        if data.get("error") == "sensor_error":
            return ("sensor_error",)
        t, h, p = (data[key] for key in ("T", "H", "P"))
        if any(type(value) not in (int, float) for value in (t, h, p)):
            return ("invalid_reply",)
        if not (-40 <= t <= 85 and 0 <= h <= 100 and 30000 <= p <= 110000):
            return ("out_of_range",)
        return ("ok", round(t, 2), round(h, 2), round(p / 100, 2))
    except (KeyError, ValueError):
        return ("invalid_reply",)


def write_row(writer, utc, source, reply):
    result = decode(reply)
    status = result[0]
    measurements = result[1:] if status == "ok" else ("", "", "")
    writer.writerow((utc.isoformat(timespec="seconds"), source, status, *measurements))


class SimulatedCabinet:
    def __init__(self, index):
        self.index = index
        phase = 2 * math.pi * index / 288
        self.temperature = 24 + 2 * math.sin(phase)
        self.pressure = 1014 + 1.5 * math.cos(phase)
        self.humidity = 52 - 4 * math.sin(phase) + (12 if 72 <= index < 84 else 0)

    @property
    def relative_humidity(self):
        if self.index == 100:
            raise OSError("injected sensor read failure")
        return 101 if self.index == 200 else self.humidity


def demo(writer):
    start = datetime(2026, 11, 18, tzinfo=timezone.utc)
    for index in range(288):
        reply = json.dumps(read_channels(SimulatedCabinet(index)))
        write_row(writer, start + timedelta(minutes=5 * index), "simulation", reply)


def capture(writer, args):
    import serial

    with serial.Serial(args.port, 115200, timeout=2, write_timeout=2) as port:
        port.write(b"\n")
        time.sleep(0.25)
        for index in count(1):
            start = time.monotonic()
            port.reset_input_buffer()
            port.write(b"GJSON\n")
            reply = port.read_until(b"\n", size=512)
            write_row(writer, datetime.now(timezone.utc), "usb", reply)
            sys.stdout.flush()
            if index == args.count:
                break
            time.sleep(max(0, args.interval - (time.monotonic() - start)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("demo", help="emit one deterministic day of simulated records")
    live = sub.add_parser("capture", help="poll a Pico data port or USB-PA")
    live.add_argument("port")
    live.add_argument("--interval", type=float, default=300, help="seconds between polls")
    live.add_argument("--count", type=int, default=0, help="polls to capture, zero for continuous")
    args = parser.parse_args()
    if args.action == "capture" and (args.count < 0 or not math.isfinite(args.interval) or args.interval <= 0):
        parser.error("capture needs a positive finite interval and a nonnegative count")
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(COLUMNS)
    if args.action == "demo":
        demo(writer)
    else:
        capture(writer, args)


if __name__ == "__main__":
    main()
