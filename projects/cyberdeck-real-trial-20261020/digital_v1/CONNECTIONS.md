# Fielddeck 7 connections

This is the complete module connection plan for the selected device. The CAD includes rigid parts, not flexible cable routing, fasteners or a detailed plug model. The rear USB service loops extend beyond the 285 mm case depth; reserve roughly 40–60 mm behind the case, pending actual plug/bend measurements.

| From | To | Selected connection | Notes |
| --- | --- | --- | --- |
| Anker A1259 separate USB-C output | Pi 4 USB-C power input | StarTech USB2CC50CM, 0.5 m, 3 A | Use one bank output. No PD trigger: Pi receives nominal 5 V. The bank's 30 W headline does not apply at 5 V. |
| Pi connector marked DISPLAY | Touch Display 2 DSI | Adafruit 1648, 15-way to 15-way, 300 mm | Carries image and touch data; do not use the camera connector. |
| Pi physical pin 2, 5 V | Supplied display lead's red conductor, then display J1 | One red Adafruit 824 male/female 300 mm extension | Male end into the supplied lead's red-wire socket; female end onto Pi pin 2. |
| Pi physical pin 6, GND | Supplied display lead's black conductor, then J1 | One black Adafruit 824 male/female 300 mm extension | Male end into black-wire socket; female onto Pi pin 6. The supplied middle socket is unused; do not bridge it. |
| Keyboard USB plug | One rear black USB 2 port | Keyboard's integral cable | Route the keyboard tail through the centre face notch; loop rear plug back through the return portion of the I/O opening. |
| Noctua fan | Other black USB 2 port | Supplied **NA-AC7** adapter | Full-speed operation. This adapter is included with the selected **5V PWM** model. |
| microSD card | Pi underside card slot | Selected SanDisk 32GB card | Fit before the top/display installation. Access requires service disassembly; no external card hatch is claimed. |

Connect the display end with its contacts facing away from the display, and the Pi end facing the Pi USB/Ethernet ports, as shown in [Raspberry Pi's illustrated connection guide](https://www.raspberrypi.com/news/getting-started-with-raspberry-pi-touch-display-2/). Physical pin numbers are header positions, not BCM GPIO numbers. Route cables and fit FFC latches with all power disconnected.

The source confirms Adafruit 824 uses **28 AWG** wire, 300 mm. Two extension conductors add about **0.128 Ω** of copper loop resistance at 20°C, approximately **77 mV** at a 0.6 A display allocation, before the original lead and contacts. The connector's current/retention rating is unpublished. Insulate each male/female join separately, label 5 V/GND, retain the lead to a tie mount and confirm continuity/polarity and loaded voltage in any eventual physical prototype. This is the main provisional cable choice, not a validated production harness.

Keep the display ribbon in the open centre cavity, above the seam plates and clear of the fan, screw shafts and sharp edges. Use broad curves rather than folded creases. The 300 mm length provides routing allowance; exact minimum bend radii/strain relief are not established by this rigid CAD model. Keep the USB-C plug region at the Pi's right side clear; loosely retain excess power/keyboard cable below the keyboard toward the centre of the case. Bank port placement is unpublished, so its final orientation and cable exit must be checked against the actual A1259.

The two blue USB 3 ports and Ethernet stay accessible at the rear. Additional USB accessories are absent from this BOM. USB fan + assumed keyboard consume 0.17 A normally; all Pi USB ports share a manufacturer 1.2 A limit, while the complete device shares the bank's 3 A limit. Use self-powered accessories for high loads. Do not use simultaneous bank charging/pass-through as a UPS feature; it has not been validated here. Shut down Linux, disconnect the bank, remove and recharge it externally.
