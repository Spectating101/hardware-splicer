"""Generate an open-top placement study. All dimensions are in millimetres."""

from pathlib import Path

import cadquery as cq


def block(x, y, z, dx, dy, dz):
    return cq.Solid.makeBox(dx, dy, dz, cq.Vector(x, y, z))


def build():
    # Only the outer dimensions come from the PW-3 listing.
    shell = block(0, 0, 0, 125, 60, 40).cut(block(2, 2, 2, 121, 56, 39))
    shell = shell.cut(block(-1, 23, 6, 4, 14, 10))
    for y in (18, 24, 30, 36, 42):
        shell = shell.cut(block(122, y, 7, 4, 2, 14))
    assembly = cq.Assembly(name="cabinet_logger_placement")
    assembly.add(shell, name="assumed_shell_and_openings", color=cq.Color("gray"))
    assembly.add(block(3, 19.5, 5, 51, 21, 11), name="pico_h_reserved_space", color=cq.Color("green"))
    assembly.add(block(86, 19, 5, 25, 22, 12), name="sensor_reserved_space", color=cq.Color("orange"))
    return assembly


if __name__ == "__main__":
    build().export(str(Path(__file__).with_name("layout.step")))
