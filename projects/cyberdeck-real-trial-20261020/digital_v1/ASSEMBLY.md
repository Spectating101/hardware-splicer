# Fielddeck 7 assembly and service plan

This documents an eventual prototype assembly matching the delivered solids. The present work stops at a digital prototype. No parts have been bought, printed, assembled or powered.

## Coordinate and fastener reference

All dimensions are millimetres. X runs left to right, Y from the keyboard/front toward the display/rear, Z up from the case floor. Main case: 310 × 285 × 64; feet add 6 mm below, fan guard adds 2 mm above. Main tray/face seams are X=155 and Y=140 with a 0.30 mm gap. Each STL is shifted to a local print origin; the STEP assembly retains world placement.

`cad/geometry_report.json` contains every display, Pi, lid and seam fastener centre. Four display case mounts are at X=85/225, Y=174.645/245.355, with a seat at Z=52.54. These are the display's outer case lugs, not its separate Pi mounting posts. Pi mounting is the manufacturer 58 × 49 mm pattern, world centres (56.5,201.5), (56.5,259.5), (7.5,201.5), (7.5,259.5), PCB bottom Z=7. Keyboard supports end at Z=38; eight compressed 2 mm pad pairs give the intended underside Z=40. Bank envelope occupies X=16–68.3, Y=25–129, Z=4–30.

## Print preparation

Print the **20** listed custom parts: four trays, four face pieces, six seam plates, fan duct, fan guard and four feet. All fit a nominal 220 × 220 mm bed individually; the largest footprint is approximately 155 × 145 mm. Millimetres must be selected when importing STL. Do not print purchased module models.

Use PETG, 0.2 mm layers, four perimeters, eight top/bottom layers and 30% infill as starting settings. Tray floors, seam plates and feet lie flat. Faces print underside down; the shallow screen recess needs short bridges under the retaining lip. The display posts bridge a 6 mm underside tool shaft. Review those bridges and nut-pocket roofs in the slicer; supports and settings are not validated. Exported solid volume gives a **100% solid mass upper bound near 840 g**. Actual sliced mass, supports and print time have not been calculated; do not multiply by 30% to estimate filament use.

Before a complete print, the eventual operator should make a small hole/nut coupon with 2.8/3.2 mm clearance holes and 5.2/5.8 mm hex pockets. Adjust for the actual printer. Allowance values are explicit design choices, not calibrated fit tolerances. Files are authored in `author_cad.py`; coordinate changes need rerunning the complete geometry checks, not merely stretching an STL.

## Assembly order

1. Deburr/inspect printed pieces. Join the four tray quarters using six internal seam plates, **24 M3×10 screws and 24 M3 nuts**. Screws enter from below the 3 mm floor, nuts above the 3 mm plates. Seat the four adhesive feet to keep heads clear of the bench. The seams remain serviceable; no glue is required to close them.
2. Place four M2.5 nuts in underside Pi pockets. Install the prepared microSD in the Pi. Seat the Pi on its 4 mm printed standoffs, connectors toward the rear opening; use **four M2.5×10** screws from above. The board must sit on its four seats, with no force on connectors. The wide rear opening intentionally also leaves cable-return space next to USB/Ethernet.
3. Thread the two 20 mm bank straps through their four floor slots. Cut the 1 mm EPDM pad to 52×104 mm and place below the bank to match its Z=4 seat; confirm compressed thickness. Seat the unchanged commercial bank in the nest, leave buttons and plugs unobstructed, and retain it. No pressure against its display or integrated cable. Confirm physical orientation/plug reach before securing other modules.
4. Place the Touch Display 2 on the four outer-lug supports, glass toward Z=62. Use **four M2.5×6** screws upward through the underside tool shafts. The nominal 3 mm seats leave about 3 mm engagement; confirm the actual lug thread and safe depth. These screws must not bottom into the panel. Keep the display's own four Pi posts unused. Tighten only enough to seat it; the bezel is not a glass clamp.
5. Connect the module cables using `CONNECTIONS.md`. Insulate and retain both display power extension joins. Keep wire loops away from the posts, seams, fan blades and screw tips. Do not crease the FFC. The keyboard/fan USB plugs use rear external service loops returning through the open portion beside the ports.
6. Insert **12 M3 nuts** into the top boss pockets. Install the four face pieces with **12 M3×10** screws. The screen pocket leaves nominal 0.3 mm vertical clearance under the bezel and 0.6 mm radial clearance around the glass. The opening covers only the inactive border in the vendor reference geometry. There must be no face pressure on the active glass.
7. Orient the Noctua fan for air into the case, down the duct toward the Pi. Tape the duct's 0.5 mm clearance sleeve around the bottom of the fan frame. Seat the fan below the rear-left face, guard above it; use **four M3×20 screws and four M3 nuts**. Route the supplied USB adapter clear of the rotor. Right-side slots provide exhaust. This geometry does not establish actual airflow or CPU temperature.
8. Apply eight 10×10 mm hook-loop pad pairs above the keyboard columns. Confirm **2 mm compressed thickness** or adjust/shim the supports. Place the keyboard in its 287×125 mm opening, tail through the centre notch. No edge clamp overlaps the keys. Lift it from the rear service gap to reach the bank; unplug/allow slack in its cable before lifting.

## Service and unresolved fits

Shut down Linux and disconnect the bank before opening. The keyboard is removable for bank access; full display/Pi access uses the bolted face pieces. The bank recharges outside the device. There is no sealed enclosure, waterproofing, drop rating, hinge, built-in charger/UPS or exposed GPIO instrumentation port.

The display uses an approximate manufacturer STEP with its own fit disclaimer. Keyboard, bank, Pi connectors and fan use nominal envelope models; plug positions, keyboard underside curvature/feet, compressed pad thickness and ribbon bends need eventual measurement. The current digital solid check establishes geometric consistency for those models. It cannot establish a first-print fit or a working powered device.
