# Fielddeck 5c: compact layout (proposal, 23 November 2026)

This is a proposed revision of the 5-inch Fielddeck, authored in CadQuery by `projects/cyberdeck-real-trial-20261020/compact/build.py` from the 5-inch revision's own solids. It follows the layout probe in `device-design-review-20261123.md`. Nothing has been printed or assembled, and the physical fit is untested.

## What changed

- **Power bank.** It moves from under the keyboard to the empty rear-right bay: x 217–269.3, y 171–275, 1 mm above the floor as before. A new open, removable nest with the same 1 mm allowance, 8 mm walls and two strap slots is authored there. The old nest walls are removed and their strap slots filled; the keyboard columns stay.
- **Case trays.** An 11.6 mm band (z 26.3–37.9) is taken out of the trays, which shortens these features together:
  - the walls, 61 → 49.4 mm;
  - the keyboard support columns, top 38 → 26.4;
  - the display posts;
  - the face fastener bosses, with their nut pockets kept.
- **Openings.** The exhaust slots and the rear I/O window are re-cut at their 5-inch sizes.
- **Lowered parts.** The keyboard, display, display spacers, fan, fan guard and faces drop 11.6 mm. The fan duct sleeve loses the same band, so its flange still meets the fan.
- **Unchanged:** the Pi, its connectors and standoffs, the display aperture, seams, seam plates and feet.

## Measured on the authored CAD

| | 5-inch | 5c compact |
|---|---|---|
| Case height | 64.0 mm | 52.4 mm |
| Overall size including feet and fan guard | 310 × 285.7 × 72.0 mm | 310 × 285.7 × 60.4 mm |
| Solid overlaps between CAD solids (OCC, every pair) | 0 | 0 |
| Fit engine on the GLB: real overlaps / stand-in overlaps | 0 / 0 | 0 / 0 |
| Power bank to nearest part | touching the front-left tray nest | 1.0 mm from the rear-right nest (the designed allowance) |
| Printable solid volume, all printed parts | 697.4 cm³ | 633.0 cm³ |

The 64.3 cm³ saving is about 82 g of solid PETG at 1.27 g/cm³; printed mass depends on infill and walls. It comes from the trays (−20.4, −16.2, −14.6 and −10.1 cm³) and the fan duct (−3.0 cm³).

Fit reports are in `fielddeck-compact-20261123-fit-5.json` and `-fit-5c.json`. Captures are in `review-ui/fielddeck-compact-20261123/`; the comparison opens at `/devices/cyberdeck-real-trial-20261020?compare=5,5c`.

## Not verified

These are recorded as blockers on the revision:

- Power bank port, button and cable access from the new bay. The bank's ports are not dimensioned.
- Heat from the bank beside the Pi and the fan intake.
- Centre of mass moved rearward, and stability on the feet.
- The printed nest and strap retention in the new position.
- Keyboard and fan cable lengths for the lowered layout.

The 5-inch revision's own open questions (display lugs, ribbon routing, GPIO power) carry over unchanged.
