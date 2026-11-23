# Salvage a board that has no file

**Salvage a board** (`/engineering/donor`) is for a physical board nobody has a KiCad file for. You describe it, and get the same
take-apart advice as for a board with a file (`docs/SALVAGE_PLAN.md`), played in 3D.

## How

1. Give the board a size (width and length in mm). Optionally put a photo under it: it stays in your browser and is never uploaded.
2. Click the board to place each part you care about, or **Add at the centre** and drag. For each part choose its kind and package,
   type the marking printed on it (or leave it empty), and, if you measured it, its size and which way it is turned.
3. **Plan the take-apart in 3D.** The plan is made again each time you ask; the page says when you have changed the board since.

Your work is kept in this browser as you go; **Save** writes a JSON file and **Open** reads one back. Nothing is stored on a server.

## What it will and will not claim

- Everything in the plan is what you typed or placed. It says so, in the footer, in the limits and in every verdict that rests on a marking.
- A marking is **what you read**, never proof of what the part is: it can be a house code, worn or fake. A marking that looks like a part
  number gets "worth taking" together with a reminder to check a datasheet; anything else is "read the marking".
- Sizes are **typical for the package** unless you typed them, and the page and viewer say so. A wrong size only changes the picture.
- The chosen kind decides ordinary handling, regardless of its reference label. Hazard markings override it: choosing “other”
  or “chip” does not hide a magnetron, CRT flyback transformer, CCFL or thermal fuse warning.
- Type hazard words that you can read, even when the package menu has no matching entry. “Something else” accepts markings such
  as magnetron (also magnatron, magentron or magnetrons), MOT, CRT, anode cap, aquadag, EHT, LOPT, flyback transformer,
  TV flyback, CCFL, backlight, fluorescent, mercury, cold cathode, lamp inverter, photoflash, heater, fuser, thermal fuse, TCO or HV/HVC;
  those parts are left in place. Common anode, flyback diode, LED lamp, white LED lamp and lamp driver labels do not trigger
  CRT or CCFL wording. Heater/fuser labels apply only to “other” and “mains or power part”; “10k heater sense” on a resistor
  does not become a fuser.
  A typed XT60 marking warns that the battery pack may still be live. No cell chemistry or capacitor rating is guessed.
  Supercapacitor and tantalum markings also add their handling warnings with “something else”; no new package size is assumed.
- Film boxes and ceramic discs without readable voltage stay optional with a warning that they might be mains safety
  capacitors. kV, WV, V, VAC, VDC, kVDC, kVAC, WVDC and WVAC markings are read with or without a space; the voltage policy
  and HV/HVC/high voltage/microwave/flash capacitor context trigger the leave-in-place rule. Wide terminal
  blocks are optional, never “worth taking”.
- The hazard rules are shared with file plans. Before any iron work, preparation names fitted parts with mains or high-voltage
  context, including parts left on the board, and warns against a wrist strap near high voltage. Ordinary boards retain resistor
  discharge, meter proof-of-zero and a check again after a wait. The high-voltage tier replaces those instructions: these circuits
  can hold a lethal charge that a hand meter and an ordinary resistor are not made for. The tool gives no discharge procedure;
  leave the part in place and the case closed, and leave it to someone trained. This includes every part skipped for voltage
  reasons and explicit microwave, CRT, photoflash, CCFL or lamp inverter context. An unmarked film cap or optocoupler alone
  does not get an appliance-circuit disclaimer. See [the hazard rules and their sources](SALVAGE_PLAN.md#hazards-it-names).
- The rule list depends on what you enter: a missing warning proves nothing. The plan approves no powering or reuse.

## Looking things up, measuring, reclaiming

- **Marking lookup.** Type a chip's marking and the page shows what KiCad's library holds under it, with its datasheet, and offers the
  library's package in one click. See `docs/PART_LOOKUP.md` for what a hit does and does not mean.
- **Measure first.** A recognised chip comes with the measurements to make, a box for each reading, and a count of how many are
  recorded. A recorded reading is a number you wrote down, not a pass.
- **Draw a box.** With a photo under the board, *Draw a box* sets a part's size and place from the photo instead of from the typical
  size.
- **Where did it come from?** A teardown search finds iFixit pages for the device, with their credit.
- **What you could reclaim.** After planning, a table and a spreadsheet list the parts worth taking, the advice, the readings and the
  datasheet. Spreadsheet cells that a program would run as a formula get a leading apostrophe.
- **Parts you may have on hand.** Reclaim rows whose typed marking matches a whole name, explicit MPN or sourced chip marking in the device planner's
  library (exact/variant only) link to **Build a device**, which shows an advisory list. Chip matches say what the library lists **on**
  its module: the SSD1306 display controller or ESP32-WROOM-32E Wi-Fi/Bluetooth radio module. The chip alone is not that module;
  it does not come with its board, pins, regulator or wiring rules. Both pages distinguish `chip_on_module` from `module` matches.
  The markings and kinds come from the
  current capture plan; stale plans offer no handoff links. A name match does not identify your chip or establish compatibility,
  and the planner's data remains the library's. See `docs/DEVICE_PLAN.md`.

## What is cleaned and refused

Names, labels and markings may not contain control or invisible characters (zero-width spaces, right-to-left overrides): they can make
text on screen read differently from what it is. Ordinary non-English text is welcome. A board opened from a file or read back from this
browser is cleaned to the same limits the server enforces (sizes finite and in range, at most 300 parts) and what cannot be read is
reported, not silently dropped. A plan that is still on its way when you start again or open another board never lands on the new one.

## API (stateless)

`GET /v1/donors/options` lists the kinds and packages with the typical size of each. `POST /v1/donors/salvage-plan` takes the
description (`hardware_splicer.donor_capture.v1`: `name`, `board.width_mm`, `board.length_mm`, `parts[]` with `kind`, `package`,
`marking`, `x_mm`, `y_mm`, optional `width_mm`, `length_mm`, `rotation_deg` 0/90/180/270, `side`) and returns a plan, 422 with a reason
when it cannot, 413 over 128 KB (read a piece at a time and refused as soon as it is too big, in the page's proxy and the backend).
At most 300 parts, markings of at most 40 printable characters, parts whose centre is on the board.

## Not yet

Recognising parts from the photo, the repo's donor *blocks* with their own evidence gates ("measure VMOTOR at J_LOGIC") as steps, and
planning wiring or qualifying a build around a reclaimed part. The name-match handoff is advisory only.
