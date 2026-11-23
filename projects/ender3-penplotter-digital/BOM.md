# Virtual donor and additional materials

Nothing in this list is owned, ordered or purchased. The donor column means retained in the **virtual** original Ender-3 design. Manufacturer identifiers and quantities come from `sources/Ender-3 BOM.XLS`, sheet `sheet1`; the original workbook is unmodified. Physical variants require identification and measurement before this design could apply.

| Virtual retained subsystem | Manufacturer identifier / specification | Quantity used |
| --- | --- | ---: |
| X/Y/Z motion motors | 400201001, 42-34 JK42HS34-0844YA-03F | 3 |
| X belt and Y belt | 400212037, 2M-W6-L786; 400212038, 2M-W6-L743 | 1 each |
| X/Y pulleys | 400211009, 2GT-d5-20-6mm | 2 |
| Z screw, nut and coupler | 400206017 T8*8-L365; 400205111 T8*8; 400208004 D5*8 | 1 each |
| Frame including top 2020 rail | 400102065..072 (top rail 20*20-L330) | Complete donor set |
| Carriage E plate | 400101002, 6061 plate 2.5mm, detailed source STEP/PDF | 1 |
| Bed and Y carriage | 400302026 235*235mm bed, 400101129 Y plate | 1 each |
| Controller and LCD | 200101027 1284P; 200102010 LCD | 1 each |
| PSU, switch, covers and wiring | 400301008 24V15A; original intact enclosed assembly | 1 set |
| Temperature sensors | 400303006 hotend; 400303022 bed | 1 each |
| Intact parked heating unit | 400105008 radiator; 400104004 heat block; 400107006 catheter; 400106003 nozzle; 400308002 heater | 1 functional set |
| Parked and secured stock fans/shroud | 400309032, 400309044, 400101029, 400402023 | Original set |
| Controller case fan, limit switches and motor/display cables | Original source BOM and harness | Original set |

The extrusion motor/feeder, Bowden tube and spool holder are removed from the active tool path and kept in a labeled virtual reversion kit. No extrusion stepper or extruder command is needed. No mains wiring or PSU enclosure change is part of this study. Bed/heater outputs stay commanded off. Both thermistors remain connected in the digital conversion specification.

| New design material or consumable | Exact design specification | Quantity |
| --- | --- | ---: |
| Pen adapter | `exports/pen_adapter.stl`, 40mm-wide rear web, 6mm thick, material model E=1400MPa | 1 |
| Pen cap | `exports/pen_clamp.stl`, matching parameterized bore | 1 |
| Heating-unit parking plate | `exports/hotend_parking_plate.stl`, 80*95*4mm before holes/slots | 1 |
| Mount screws | ISO metric M3*10 pan/socket head, steel, no washer in 6mm attachment stack | 2 |
| Pen clamp screws | M3*40 socket head, steel; cap front w=44.9mm | 2 |
| Captive pen nuts | ISO M3 steel hex, nominal AF5.5mm, thickness2.4mm; model clearance AF5.7 | 2 |
| Parking radiator screws and nuts | M3*20 steel screws + ISO M3 hex nuts | 2 each |
| Parking frame screws | M4*10 steel socket/pan head | 2 |
| Parking frame T nuts | Geometry matching manufacturer `M4 T-Slot Nut.step`, 6*9.5mm envelope, M4 | 2 |
| Fan/shroud retention ties | 2.5mm-wide nylon ties, 150mm length, passed through four 4*12mm plate slots | 4 |
| Grip liner | EPDM sheet0.5mm thick,20mm wide; cut length pi*pen_diameter+2mm (33.42mm default) | 1 strip |
| Pen | Cylindrical grip of selected8..12mm diameter;100mm maximum tip-to-top envelope; default10mm | 1 |
| Paper |180*180mm flat sheet, nominal0.1mm thickness | 1 |
| Masking tape | Thin paper tape, ≤1mm total raised obstruction height; keep outside plotted strokes | 4 short strips |

No purchase links or supplier prices are supplied. The polymer modulus, density1.27g/cm3 and thin-tape bound are design assumptions. Material, layer strength, nut insertion fit, clamp holding and actual pen dimensions have not been tested. The heating unit must be supported by the parking plate rather than suspended from wires. A retained live heater is an electrical integration question that remains subject to a separate future hardware review; zero commands alone are not hardware isolation.
