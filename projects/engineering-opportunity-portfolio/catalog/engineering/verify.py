"""Replay every registered digital engineering study using isolated working copies."""

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_CAD = Path.home() / ".local/share/hardware-splicer/cad-venv/bin/python"


def study_digest(folder):
    h = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and not path.name.startswith(".")
        ):
            h.update(path.relative_to(folder).as_posix().encode() + b"\0")
            h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def same_result(actual, expected):
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(same_result(actual[k], v) for k, v in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(same_result(a, b) for a, b in zip(actual, expected))
        )
    if isinstance(expected, float):
        return math.isclose(actual, expected, abs_tol=1e-6, rel_tol=1e-9)
    return actual == expected and type(actual) is type(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad-python", type=Path, default=DEFAULT_CAD)
    native_default = next(
        (
            p / ".cache/hardware-splicer/digital-native-venv/bin/python"
            for p in HERE.parents
            if p.parent != p
            if (p / ".cache/hardware-splicer/digital-native-venv/bin/python").is_file()
        ),
        DEFAULT_CAD,
    )
    parser.add_argument(
        "--native-python",
        type=Path,
        default=native_default,
        help="Python with CadQuery, trimesh and numpy for the two frozen design releases",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        help="write the verified product IDs and input hashes after successful replay",
    )
    args = parser.parse_args()
    cad = args.cad_python.expanduser().absolute()
    if not cad.is_file():
        parser.error("Set --cad-python to a Python environment with CadQuery 2.8")
    env = dict(
        os.environ,
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        PYTHONDONTWRITEBYTECODE="1",
        HS_CAD_PYTHON=str(args.native_python.expanduser().absolute()),
        HS_ROBOT_CAD_PYTHON=str(cad),
    )
    studies = {
        "P028": [(sys.executable, "study.py", "--verify")],
        "P010": [(sys.executable, "build.py", "--stl"), (sys.executable, "verify.py")],
        "P217": [(sys.executable, "study.py")],
        "P047": [(str(cad), "trial.py")],
    }
    with tempfile.TemporaryDirectory(prefix="hs-catalog-studies-") as tmp:
        groups = {}
        for ident, commands in studies.items():
            source = HERE / ident
            work = Path(tmp) / ident
            shutil.copytree(source, work, ignore=shutil.ignore_patterns("__pycache__"))
            if (
                ident != "P028"
            ):  # P028's --verify regenerates and compares in its own temp directory.
                generated = ["*.svg", "*.stl", "verification.json", "results.json"]
                if ident == "P047":
                    generated.append("*.step")
                for pattern in generated:
                    for f in work.glob(pattern):
                        if f.name != "reference-pallet.step":
                            f.unlink()
            for command in commands:
                completed = subprocess.run(
                    command, cwd=work, env=env, capture_output=True, text=True
                )
                if completed.returncode:
                    raise SystemExit(
                        f"{ident} failed: {completed.stdout}\n{completed.stderr}"
                    )
            for f in source.iterdir():
                if not f.is_file() or f.suffix not in {
                    ".step",
                    ".svg",
                    ".stl",
                    ".json",
                }:
                    continue
                replay = work / f.name
                if not replay.is_file() or not replay.stat().st_size:
                    raise ValueError(f"{ident} failed to produce {f.name}")
                if f.suffix == ".json":
                    if not same_result(
                        json.loads(replay.read_text()), json.loads(f.read_text())
                    ):
                        raise ValueError(f"{ident} changed result in {f.name}")
                elif f.suffix == ".step" or (ident == "P047" and f.suffix == ".svg"):
                    # The CAD kernel timestamps STEP headers and may reorder projected edges.
                    # trial.py reimports and validates the exported solids and assembly.
                    continue
                elif replay.read_bytes() != f.read_bytes():
                    raise ValueError(f"{ident} changed geometry in {f.name}")
            print(f"{ident}: replay matched published trial")
            groups[ident] = {"ids": [ident], "study_sha256": study_digest(source)}
        verified = set(studies)
        for manifest in sorted(HERE.glob("*-wave/manifest.csv")):
            source = manifest.parent
            work = Path(tmp) / source.name
            shutil.copytree(source, work, ignore=shutil.ignore_patterns("__pycache__"))
            with manifest.open(newline="") as f:
                ids = [row["id"] for row in csv.DictReader(f)]
            if not ids or len(set(ids)) != len(ids) or verified.intersection(ids):
                raise ValueError(f"Empty or duplicated registration in {source.name}")
            result = subprocess.run(
                [sys.executable, "verify.py"],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise SystemExit(
                    f"{source.name} failed: {result.stdout}\n{result.stderr}"
                )
            verified.update(ids)
            groups[source.name] = {
                "ids": sorted(ids),
                "study_sha256": study_digest(source),
            }
            print(f"{source.name}: {len(ids)} products replayed", flush=True)
        with (HERE / "coverage.csv").open(newline="") as f:
            registered = {
                r["id"]
                for r in csv.DictReader(f)
                if r["published_digital_trial"] == "yes"
            }
        if verified != registered:
            raise ValueError(
                f"Coverage and verified IDs differ: {verified ^ registered}"
            )
        if args.receipt:
            args.receipt.write_text(
                json.dumps(
                    {
                        "scope": "Offline digital engineering replay",
                        "offers_verified": len(verified),
                        "physical_tests": 0,
                        "groups": groups,
                    },
                    indent=2,
                )
                + "\n"
            )
        print(f"{len(verified)} distinct product offers verified")


if __name__ == "__main__":
    main()
