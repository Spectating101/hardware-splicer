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
- What you chose for a part (its kind) decides how it is treated, not its label: a part you call `J9` but mark as a chip is a chip.
- The hazard rules are the same as for a file (batteries, stored charge, mains parts). They are a rule list, not a guarantee.

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

Recognising parts from the photo, the repo's donor *blocks* with their own evidence gates ("measure VMOTOR at J_LOGIC") as steps, and a
way to move from a described board to a build that uses what you reclaimed.
