"""Design a DC station or manually capture from its configured INA228 bus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dc_measurement_station import StationSpec, write_design
from .ina228_logger import AcquisitionError, INA228, LinuxI2CBus, capture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("design", "capture"):
        option = sub.add_parser(command)
        option.add_argument("--spec", type=Path, help="JSON StationSpec; omitted values use stated candidate defaults")
        option.add_argument("--out", required=True, type=Path, help="New output directory")
        if command == "capture":
            option.add_argument("--bus", required=True, type=int)
            option.add_argument("--address", type=lambda x: int(x, 0), required=True)
            option.add_argument("--samples", type=int, default=183)
            option.add_argument("--period-seconds", type=float, default=1.0)
            option.add_argument("--clock-source", required=True, help="Actual host UTC source; recorded as an unverified declaration")
    args = parser.parse_args(argv)
    try:
        spec = StationSpec.from_dict(json.loads(args.spec.read_text())) if args.spec else StationSpec()
        if args.command == "design":
            result = write_design(args.out, spec)
            print(json.dumps({"out": str(args.out), "design_checks_passed": result["design_checks_passed"],
                              "physical_status": result["physical_status"]}))
            return 0 if result["design_checks_passed"] else 2
        bus = LinuxI2CBus(args.bus, args.address)
        try:
            result = capture(INA228(bus, spec), args.out, samples=args.samples, period_seconds=args.period_seconds,
                             clock_source=args.clock_source)
        finally:
            bus.close()
        print(json.dumps({"out": str(args.out), "status": result["status"], "samples": result["completed_samples"]}))
        return 0
    except (ValueError, OSError, AcquisitionError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
