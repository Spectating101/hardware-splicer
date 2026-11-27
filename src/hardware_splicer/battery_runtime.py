"""How long a device that sleeps and wakes runs on a battery: average current from its duty cycle, then days.

    python -m hardware_splicer.battery_runtime --capacity-mah 2600 --period-s 600 \
        --phase "LoRa transmit:120:0.5" --phase "MCU awake:31:3" --sleep-ua 10

Each phase is label:mA:seconds per wake-up. The average current is the charge of the phases plus the sleep current over the
rest of the period. Runtime is given as a range:

* ``ceiling``: the usable share of the capacity divided by that average, with no self-discharge;
* ``with self-discharge``: the cell also loses a share of its charge every month (cited for Li-ion below).

Every input says where it came from: given by you, cited (with the datasheet line), or assumed. Nothing is measured, and a
development board's regulator, USB bridge and LEDs usually draw far more in sleep than the chip itself: measure the board
asleep before trusting a figure in months.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

SCHEMA = "hardware_splicer.battery_runtime.v1"

# Primary figures, quoted from the documents named; extend only with a source.
CITED: dict[str, dict[str, Any]] = {
    "esp32_deep_sleep_ua": {"value": 10.0, "unit": "uA", "source": "Espressif ESP32 Series Datasheet v5.3, power modes table",
                            "quote": "Deep-sleep ... RTC timer + RTC memory 10 µA"},
    "esp32_modem_sleep_80mhz_ma": {"value": (20.0, 31.0), "unit": "mA", "source": "Espressif ESP32 Series Datasheet v5.3, power modes table",
                                   "quote": "Modem-sleep ... Normal speed: 80 MHz ... Dual-core chip(s) 20 mA ~ 31 mA"},
    "esp32_wifi_tx_ma": {"value": 240.0, "unit": "mA", "source": "Espressif ESP32 Series Datasheet v5.3, RF power-consumption table",
                         "quote": "Transmit 802.11b, DSSS 1 Mbps, POUT = +19.5 dBm ... 240 mA"},
    "sx127x_tx_20dbm_ma": {"value": 120.0, "unit": "mA", "source": "Semtech SX1276/77/78/79 datasheet, Table 6 Power Consumption Specification",
                           "quote": "IDDT Supply current in Transmit mode ... RFOP = +20 dBm, on PA_BOOST 120 mA"},
    "sx127x_rx_ma": {"value": (10.8, 12.0), "unit": "mA", "source": "Semtech SX1276/77/78/79 datasheet, Table 6",
                     "quote": "IDDR Supply current in Receive mode ... 10.8 / 11.5 / 12.0 mA"},
    "sx127x_sleep_ua": {"value": 0.2, "unit": "uA", "source": "Semtech SX1276/77/78/79 datasheet, Table 6",
                        "quote": "IDDSL Supply current in Sleep mode 0.2 uA typ, 1 uA max"},
    "li_ion_self_discharge_pct_month": {"value": (4.0, 5.0), "unit": "% per month", "source":
                                        "Battery University BU-802b, https://batteryuniversity.com/article/bu-802b-what-does-elevated-self-discharge-do",
                                        "quote": "Li-ion self-discharges about 5 percent in the first 24 hours and then loses 1–2 percent per month; "
                                                 "the protection circuit adds another 3 percent per month."},
}
ASSUMED_USABLE = (0.8, 0.9)  # share of rated capacity a device can draw before its cut-off; assumed, not cited
HOURS_PER_MONTH = 730.0


def runtime(capacity_mah: float, period_s: float, phases: list[dict[str, Any]], sleep_ua: float,
            self_discharge_pct_month: tuple[float, float] | None = None, usable: tuple[float, float] = ASSUMED_USABLE,
            sleep_basis: str = "given") -> dict[str, Any]:
    if capacity_mah <= 0 or period_s <= 0:
        raise ValueError("capacity and period must be positive")
    awake_s = sum(float(p["seconds"]) for p in phases)
    if awake_s > period_s:
        raise ValueError(f"the phases last {awake_s:g} s, longer than the {period_s:g} s period")
    charge_mas = sum(float(p["ma"]) * float(p["seconds"]) for p in phases) + sleep_ua / 1000 * (period_s - awake_s)
    average_ma = charge_mas / period_s
    loss = self_discharge_pct_month or CITED["li_ion_self_discharge_pct_month"]["value"]
    # Self-discharge as an extra drain: a share of the rated capacity per month.
    leak = [capacity_mah * pct / 100 / HOURS_PER_MONTH for pct in loss]
    ceiling_h = [capacity_mah * u / average_ma for u in usable]
    with_leak_h = [capacity_mah * usable[0] / (average_ma + leak[1]), capacity_mah * usable[1] / (average_ma + leak[0])]
    days = lambda hours: [round(h / 24, 1) for h in hours]  # noqa: E731
    return {
        "schema_version": SCHEMA,
        "average_ma": round(average_ma, 4),
        "awake_share": round(awake_s / period_s, 5),
        "charge_per_wake_mas": round(charge_mas, 2),
        "runtime_days": {"ceiling": days(ceiling_h), "with_self_discharge": days(with_leak_h)},
        "inputs": {
            "capacity_mah": {"value": capacity_mah, "basis": "given"},
            "period_s": {"value": period_s, "basis": "given"},
            "phases": phases,
            "sleep_ua": {"value": sleep_ua, "basis": sleep_basis},
            "usable_share": {"value": list(usable), "basis": "assumed"},
            "self_discharge_pct_month": {"value": list(loss), "basis": "given" if self_discharge_pct_month else "cited",
                                         **({} if self_discharge_pct_month else {"source": CITED["li_ion_self_discharge_pct_month"]["source"]})},
        },
        "limits": [
            "Sleep current is the chip's unless you measured the board: a development board's regulator, USB bridge and LEDs often add far more.",
            "Radio airtime depends on spreading factor, bandwidth and payload; retries and lost packets add to it.",
            "Cold cuts usable capacity; Battery University's table shows self-discharge rising with temperature and charge.",
        ],
        "claim_boundary": "An estimate from the stated inputs. Not a measurement.",
    }


def _phase(text: str) -> dict[str, Any]:
    label, ma, seconds = text.rsplit(":", 2)
    return {"label": label, "ma": float(ma), "seconds": float(seconds), "basis": "given"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--capacity-mah", type=float, required=True)
    parser.add_argument("--period-s", type=float, required=True)
    parser.add_argument("--phase", action="append", default=[], help="label:mA:seconds per wake-up (repeatable)")
    parser.add_argument("--sleep-ua", type=float, required=True)
    parser.add_argument("--self-discharge", type=float, nargs=2, default=None, metavar=("LOW", "HIGH"), help="% per month")
    args = parser.parse_args(argv)
    result = runtime(args.capacity_mah, args.period_s, [_phase(p) for p in args.phase], args.sleep_ua,
                     tuple(args.self_discharge) if args.self_discharge else None)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
