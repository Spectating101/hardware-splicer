"""Metric cutting/drilling profiles for a pair of interchangeable switch holders."""

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class Switch:
    body: float
    button: float
    pitch_x: float
    pitch_y: float
    drill: float
    boss_pitch: float = 0


SWITCHES = {
    "B3F-1000": Switch(6, 3.5, 6.5, 4.5, 1.0),
    "B3F-4000": Switch(12, 7.1, 12.5, 5, 1.2, 9),
}
WIDTH, HEIGHT = 30, 24
APERTURE_ALLOWANCE = 1.4


def cutfile(switch, keeper=False, aperture_allowance=APERTURE_ALLOWANCE):
    """Return a true-scale SVG with one contour per cut. Origin is top left in mm."""
    svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width=f"{WIDTH}mm",
                     height=f"{HEIGHT}mm", viewBox=f"0 0 {WIDTH} {HEIGHT}")
    layer = ET.SubElement(svg, "g", fill="none", stroke="black", attrib={"stroke-width": "0.05"})
    ET.SubElement(layer, "rect", id="outline", x="0", y="0", width=str(WIDTH), height=str(HEIGHT))

    def drill(name, x, y, diameter):
        ET.SubElement(layer, "circle", id=name, cx=f"{WIDTH / 2 + x:g}",
                      cy=f"{HEIGHT / 2 + y:g}", r=f"{diameter / 2:g}")

    for i, x in enumerate((-11, 11), 1):
        drill(f"mount-{i}", x, 0, 3.2)
    drill("datum", -10, -7, 2.05)
    ET.SubElement(layer, "rect", id="datum-slot", x="23.65", y="3.975", width="2.7",
                  height="2.05", rx="1.025", ry="1.025")
    if keeper:
        drill("button", 0, 0, switch.button + aperture_allowance)
    else:
        for y, row in ((-switch.pitch_y / 2, "top"), (switch.pitch_y / 2, "bottom")):
            for x, column in ((-switch.pitch_x / 2, "left"), (switch.pitch_x / 2, "right")):
                drill(f"terminal-{row}-{column}", x, y, switch.drill)
        if switch.boss_pitch:
            for i, y in enumerate((-switch.boss_pitch / 2, switch.boss_pitch / 2), 1):
                drill(f"boss-{i}", 0, y, 1.8)
    ET.indent(svg)
    return ET.tostring(svg, encoding="unicode") + "\n"


def generate(folder):
    for name, switch in SWITCHES.items():
        for kind in ("carrier", "keeper"):
            (Path(folder) / f"{name}-{kind}.svg").write_text(
                cutfile(switch, keeper=kind == "keeper"), encoding="utf-8")
