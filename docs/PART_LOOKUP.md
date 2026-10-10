# Looking a marking up

`GET /v1/parts/lookup?marking=NE555P` (and the panel on **Salvage a board**) looks a marking up in **KiCad's own libraries**, read from
the KiCad install on the server. No internet is needed and nothing is stored.

## What is in the library, and what a hit means

About 22,000 symbols (KiCad 9.0 here), each with a description, a datasheet link, a default footprint, keywords and every pin's name
and type. A marking is matched in three tiers, and each answer says which:

| Tier | Means |
|------|-------|
| **Same name** | the library has a part with exactly this name |
| **Variant** | the library has a part whose name is this name plus a code (`NE555` and `NE555P`, `STM32F103C8T6` and KiCad's `STM32F103C8Tx`). The code may be a package, a grade or a different chip, so check the datasheet. A different digit is a different function, so `LM35` is not offered `LM358`, and `74HC` offers nothing and asks for more of the marking |
| **Same family** | the library has parts that differ from the marking only in letters, and not this one: it says what kind of chip it probably is, no more |

A hit is **a part with that name, not proof that the chip you hold is that part**: a marking can be a house code, worn or fake. A family
match gets no package and no measurements, because those would be another chip's. A marking the library does not know gets "nothing under
this marking, which does not mean it is fake", a datasheet search, and, for a short code, a link to a community top-mark database
(`s-manuals.com/smd/<code>`). Those databases have no open dataset to copy, so they are links only.

## Measure first

For a chip that matches by name or variant, and whose library footprint family fits the package you chose, the pin names and types
give measurements to write down. Family matches get none. If the closest library entry is in another package, the plan still names
that entry but emits **no pin numbers**, because those pins would not be yours. If the library entry has no footprint and you chose
a package, the pin *names* are still shown, with a note that the library does not say which package those pin numbers belong to:
take them from the datasheet drawing of the package in front of you.

`GET /v1/parts/lookup` accepts an optional `package` query (validated like `marking`). The capture panel sends the selected part's
package and asks again when it changes, using the same package-aware pick as the plan. The answer includes `gates_from` and
`package_note`.

The checks are ordered so the board stays unpowered first. Fluke 87V MAX: "disconnect power and discharge all high-voltage
capacitors before you measure resistance, continuity, capacitance, or a diode junction." First: diode mode both ways between the
named pins. Then ohms both ways. Fluke, same section: "the resistance reading represents the total resistance of all paths between
the probes." A chip's protection diodes can read low in one probe direction (TI SCDA039: ESD diodes from a pin to VCC and to
ground), so both directions are written down and compared with the datasheet or a known-good chip — not treated as "shorted".
Only after those notes, a **bench supply with a current limit** set to the datasheet voltage for that pin pair (not the board's
own supply and not anything connected to the mains without isolation). Write down the voltage and the current it draws. Connect a
supply the right way round: reversing the supply on a chip can destroy it. Meter-lead polarity on a DC voltage measurement is not
that warning.

Supply *inputs* are the pairs (not an exposed pad or a not-connected pin). A regulator output is not treated as the supply, and an
input reading does not show what the output is doing. Dual-supply parts with V+ / V− and no ground are gated between those two
pins. Names such as `V_{SS}` are read as VSS. Exact internal names (VINT, VCAP, VCAP1, VCAP2, VBYP, VREG) and the SENSE / VREF
prefixes are not treated as rails. VREGIN is a regulator input and is kept. A part whose only supply-like pins are VREF (for
example PCA9306) gets no gates, by design. Isolated domains are paired with the ground of the same domain (VCC1/GND1, VCC2/GND2,
VCCA/GNDA); a supply whose domain cannot be matched gets no gate. Numbered pins of one rail (VM1, VM2, VM3) collapse to one VM
gate. Up to six voltage gates are emitted; isolation stays per rail, at most three rails. PGND is a ground, ranked after GND/VSS.
Motor rails (VM, VMOT, VS) are included. Two rails such as VCCA and VCCB each get an isolation check as separate pins to check
each on its own. A part with more than 64 pins gets no guessed measurements. They say what and where, **never what the reading
should be**. Each reading is stored against the chip it was taken from. On a step that covers several refs, each measure check
says per ref (`U1: 5.02 V; U2: not recorded`) and the recorded count is the number of (ref, gate) pairs. A recorded reading is
**a note, not a pass**, and none of them shows a removed chip works.

Pin-1 wording for DIP, SO, QFP and QFN follows JEDEC SPP-012: the dot or notch marks the pin-1 end; pin 1 is the first leg
counter-clockwise from it seen from the top for standard-bend leads; from the underside the order appears reversed. For TO-220,
SOT-23 and other TO/SOT outlines the lead order is taken from the datasheet's package drawing, not from the package name (7805 vs
LM317). BGA balls are named by row and column. RF modules have numbered contacts around the edge from the pin-1 mark in the
datasheet drawing.

## Sizes

Package sizes on the capture page are the **courtyards of the KiCad footprint named, which may not be your exact package**. Only a
bare cell, a pouch cell and "other" have no library footprint and stay typical, and say so. A guard test fails if a footprint name
that does not exist in the library is ever used.

## Optional online lookup

`online=true` asks the repo's existing parts providers (the offline catalog, and jlcsearch when `HARDWARE_SPLICER_JLC_ENRICH` enables it).
jlcsearch's free community API needs no key; every record carries its source and date.

## Teardowns

`GET /v1/teardowns/search?q=roku stick` finds [iFixit](https://www.ifixit.com) guides over HTTPS to `www.ifixit.com` only, following no redirect, with a bounded cache. iFixit's search is public and free for
non-commercial use, and its teardowns are CC BY-NC-SA, so only titles and links are returned, with their credit, and only links on
`www.ifixit.com`. A teardown often names the chips on a board.

## Looked at and not used

- **Chip detection from a photo** (open YOLO models and CC BY 4.0 datasets exist for capacitors, ICs, connectors and so on): needs a heavy
  ML stack, and a detector's boxes are guesses. A box you draw over your own photo is measured, so that is what the page offers.
- **SMD marking-code databases** (embedeo, smd.yooneed.one, RepairCompanion): web only, no open data, so linked, not copied.
- **iFixit content**: licensed non-commercial; linked, not copied.
