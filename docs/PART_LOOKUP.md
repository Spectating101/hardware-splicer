# Looking a marking up

`GET /v1/parts/lookup?marking=NE555P` (and the panel on **Salvage a board**) looks a marking up in **KiCad's own libraries**, read from
the KiCad install on the server. No internet is needed and nothing is stored.

## What is in the library, and what a hit means

About 22,000 symbols (KiCad 9.0 here), each with a description, a datasheet link, a default footprint, keywords and every pin's name
and type. A marking is matched in three tiers, and each answer says which:

| Tier | Means |
|------|-------|
| **Same name** | the library has a part with exactly this name |
| **Variant** | the library has a part whose name starts or ends the same way: probably the same chip in another package or grade |
| **Same family** | the library has parts from the same family and not this one: it says what kind of chip it probably is, no more |

A hit is **a part with that name, not proof that the chip you hold is that part**: a marking can be a house code, worn or fake. A family
match gets no package and no measurements, because those would be another chip's. A marking the library does not know gets "nothing under
this marking, which does not mean it is fake", a datasheet search, and, for a short code, a link to a community top-mark database
(`s-manuals.com/smd/<code>`). Those databases have no open dataset to copy, so they are links only.

## Measure first

For a chip that matches by name or variant, the pin names and types give the measurements to make before trusting it: supply against
ground, and whether they are shorted. They say what and where, **never what the reading should be**: that is the datasheet's to say. The
pin names come from the library's entry, not from the chip in hand, and the plan says so. You write each reading down; the plan counts
how many are recorded and lists the chips still to measure. A recorded reading is **a number written down, not a pass**.
Pin 1 guidance ("the corner with the dot or notch, counting anticlockwise from above") is given only for DIP, SO, QFP and QFN packages.

## Sizes

Package sizes on the capture page are the **courtyards of real KiCad footprints** (exact for that footprint, a little larger than the
part), with the footprint named. Only a bare cell, a pouch cell and "other" have no library footprint and stay typical, and say so. A
guard test fails if a footprint name that does not exist in the library is ever used.

## Optional online lookup

`online=true` asks the repo's existing parts providers (the offline catalog, and jlcsearch when `HARDWARE_SPLICER_JLC_ENRICH` enables it).
jlcsearch's free community API needs no key; every record carries its source and date.

## Teardowns

`GET /v1/teardowns/search?q=roku stick` finds [iFixit](https://www.ifixit.com) guides. iFixit's search is public and free for
non-commercial use, and its teardowns are CC BY-NC-SA, so only titles and links are returned, with their credit, and only links on
`www.ifixit.com`. A teardown often names the chips on a board.

## Looked at and not used

- **Chip detection from a photo** (open YOLO models and CC BY 4.0 datasets exist for capacitors, ICs, connectors and so on): needs a heavy
  ML stack, and a detector's boxes are guesses. A box you draw over your own photo is measured, so that is what the page offers.
- **SMD marking-code databases** (embedeo, smd.yooneed.one, RepairCompanion): web only, no open data, so linked, not copied.
- **iFixit content**: licensed non-commercial; linked, not copied.
