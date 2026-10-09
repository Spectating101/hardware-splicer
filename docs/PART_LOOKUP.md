# Looking a marking up

`GET /v1/parts/lookup?marking=NE555P` (and the panel on **Salvage a board**) looks a marking up in **KiCad's own libraries**, read from
the KiCad install on the server. No internet is needed and nothing is stored.

## What is in the library, and what a hit means

About 22,000 symbols (KiCad 9.0 here), each with a description, a datasheet link, a default footprint, keywords and every pin's name
and type. A marking is matched in three tiers, and each answer says which:

| Tier | Means |
|------|-------|
| **Same name** | the library has a part with exactly this name |
| **Variant** | the library has a part with this name plus or minus a short package or grade code (`NE555` and `NE555P`, `STM32F103C8T6` and KiCad's `STM32F103C8Tx`): probably the same chip in another package or grade. A different digit is a different function, so `LM35` is not offered `LM358`, and `74HC` offers nothing and asks for more of the marking |
| **Same family** | the library has parts that differ from the marking only in letters, and not this one: it says what kind of chip it probably is, no more |

A hit is **a part with that name, not proof that the chip you hold is that part**: a marking can be a house code, worn or fake. A family
match gets no package and no measurements, because those would be another chip's. A marking the library does not know gets "nothing under
this marking, which does not mean it is fake", a datasheet search, and, for a short code, a link to a community top-mark database
(`s-manuals.com/smd/<code>`). Those databases have no open dataset to copy, so they are links only.

## Measure first

For a chip that matches by name or variant, the pin names and types give the measurements to make before trusting it: supply against
ground, and whether they are shorted. Only supply *inputs* count (not a regulator's output, an exposed pad or a not-connected pin), the main supply is measured first, a negative supply such as VEE is a supply and not the ground, and a part with more than 64 pins gets no guessed measurements because choosing among its supplies takes its datasheet. They say what and where, **never what the reading should be**: the line is "write down what you see", and the datasheet says what is right. Each reading is stored against the chip it was taken from, so it cannot follow a new marking to another chip with the same pins. The
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

`GET /v1/teardowns/search?q=roku stick` finds [iFixit](https://www.ifixit.com) guides over HTTPS to `www.ifixit.com` only, following no redirect, with a bounded cache. iFixit's search is public and free for
non-commercial use, and its teardowns are CC BY-NC-SA, so only titles and links are returned, with their credit, and only links on
`www.ifixit.com`. A teardown often names the chips on a board.

## Looked at and not used

- **Chip detection from a photo** (open YOLO models and CC BY 4.0 datasets exist for capacitors, ICs, connectors and so on): needs a heavy
  ML stack, and a detector's boxes are guesses. A box you draw over your own photo is measured, so that is what the page offers.
- **SMD marking-code databases** (embedeo, smd.yooneed.one, RepairCompanion): web only, no open data, so linked, not copied.
- **iFixit content**: licensed non-commercial; linked, not copied.
