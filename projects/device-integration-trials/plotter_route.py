"""Reorder complete strokes of an HS digital plot using vpype 1.15."""

import argparse
from collections import defaultdict, deque
import re
from zipfile import ZipFile
from pathlib import Path

import vpype
import vpype_cli


def reorder(source):
    lines = source.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith("G0 X")]
    end = lines.index("M400\n")
    groups = defaultdict(deque)
    paths = []
    for start, stop in zip(starts, starts[1:] + [end]):
        block = lines[start:stop]
        if not block[1].startswith("G1 Z0.") or not block[-1].startswith("G0 Z"):
            raise ValueError("Expected a complete pen-down and pen-up stroke")
        points = []
        for line in [block[0], *block[2:-1]]:
            match = re.fullmatch(r"G[01] X(-?[\d.]+) Y(-?[\d.]+) F\d+\s*", line)
            if not match:
                raise ValueError(f"Unexpected XY motion: {line}")
            points.append(complex(float(match[1]), float(match[2])))
        groups[tuple(points)].append(block)
        paths.append(points)

    # Preserve pen direction and exact source commands, including feeds and lifts.
    doc = vpype_cli.execute("linesort --no-flip",
                            vpype.Document(vpype.LineCollection(paths)))
    reordered = []
    for path in doc.layers[1]:
        reordered.extend(groups[tuple(path)].popleft())
    if any(groups.values()):
        raise ValueError("The planner dropped strokes")
    return "".join(lines[:starts[0]] + reordered + lines[end:])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with ZipFile(args.study) as archive:
        candidate = reorder(archive.read("simulation/example.gcode").decode())
    args.output.write_text(candidate)
