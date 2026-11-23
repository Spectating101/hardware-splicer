"""Print low-fidelity mockups of the HS browser app. Brackets represent buttons."""

import argparse


def screen(title, rows):
    width = 78
    print("┌" + "─" * width + "┐")
    print("│" + title.ljust(width) + "│")
    print("├" + "─" * width + "┤")
    for row in rows:
        print("│" + row.ljust(width) + "│")
    print("└" + "─" * width + "┘")


def projects():
    screen(" Hardware Splicer   /   Projects", [
        " Projects                                                 [+ New project]",
        " [ Find a project…                       ]",
        "",
        " Project                              Stage                   Revision",
        " ────────────────────────────────────────────────────────────────────────────",
        " Ender-3 pen plotter                  Design review                2     ›",
        " FieldDeck cyberdeck                  Design review                1     ›",
    ])


def new_project():
    screen(" Hardware Splicer   /   Projects   /   New project", [
        " How would you like to start?",
        "",
        " (●) Build from a goal     ( ) Use parts I have     ( ) Adapt a reference",
        "",
        " What do you want to build?",
        " ┌──────────────────────────────────────────────────────────────────────────┐",
        " │ A pen plotter that can draw a 140 mm square.                             │",
        " └──────────────────────────────────────────────────────────────────────────┘",
        "                                             [Cancel]    [Create project]",
    ])


def bench(compare=False):
    left = ["PARTS & REQUIREMENTS", "", "Parts", "  Donor mount", "  Pen clamp", "",
            "Requirements", "› Drawing width", "  Pen lift"]
    center = (["REVISION COMPARISON", "", "             R1       R2", "Width      100 mm   140 mm",
               "Height      80 mm   140 mm", "", " [Open revision 2]"]
              if compare else
              ["ASSEMBLY", "", "      ┌──────▣──────┐", "      │      ↓      │", "      │  ┌───────┐  │",
               "      └──┴───────┴──┘", "         ←140 mm→", "", " [Orbit]  [Zoom]  [Fit]"])
    right = ["DRAWING WIDTH", "", "Target    140 mm", "Model     140 mm", "", "Evidence",
             "Simulated · Rev 2", "Physical calibration", "unverified", "", "[View calculation]"]
    lines = [" Assembly   Parts   Wiring   Checks                       [Close compare]" if compare else
             " Assembly   Parts   Wiring   Checks                   [Compare revisions]",
             "─" * 78]
    for i in range(max(len(left), len(center), len(right))):
        cells = [column[i] if i < len(column) else "" for column in (left, center, right)]
        lines.append(f" {cells[0]:<22}│ {cells[1]:<29}│ {cells[2]}")
    screen(" Hardware Splicer   /   Projects   /   Ender-3 pen plotter      Rev 2", lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", choices=("all", "projects", "new", "bench", "compare"), default="all")
    parser.add_argument("--snapshot", action="store_true", help="render just the revision comparison")
    args = parser.parse_args()
    selected = "compare" if args.snapshot else args.screen
    for name, render in [("projects", projects), ("new", new_project), ("bench", bench), ("compare", lambda: bench(True))]:
        if selected in ("all", name):
            render()
            print()
