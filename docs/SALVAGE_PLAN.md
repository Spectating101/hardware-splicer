# Take-apart (salvage) plan

The build sequence run the other way over the same retained board: `GET /v1/projects/{id}/revisions/{rev}/salvage-plan`, shown in the
Assemble tab as **Take apart**. It is a rule-of-thumb plan read from the board's file. It measures nothing and approves nothing:
the condition of every part is unknown until it is tested, and a verdict is advice about effort and reuse.

## What it gives

A safety step, then removal in a sensible order (connectors and electrolytic capacitors, then chips from easy packages to hard, then
the rest), then sorting and testing. Each part has a verdict with the rule behind it: worth taking, take it and test first, read the
marking, cheap to buy new, leave it. Parts the design marks do-not-populate have nothing to take.

## Hazards it names

A battery cell is never planned for removal (take it out by hand, never with heat); a holder keeps the warning. Polarised,
tantalum and supercapacitors, and any capacitor rated 100 V or more (including X2/Y2 and AC ratings), carry a discharge warning,
and the high-voltage ones are left alone. Mains and switching-supply parts (transformers, relays, varistors, fuses and fuse
holders, mains inlets, common-mode chokes, terminal blocks of 5 mm pitch or more) carry a mains warning and are never "worth
taking". Names are matched on whole name parts, so a word that merely contains a keyword (Electronic, MOVEMENT, OnePiece) does not
match. This is a rule list, not a guarantee: a part it does not recognise gets no warning, so the general safety step still applies.

## Stated limits

- It needs the board's file. A physical board with no file cannot be planned from; there is no capture path yet.
- A chip is named only as far as the file names it (its part number). Otherwise the verdict is "read the marking", never a guess.
- Whether a part still works is unknown until it is tested. A capacitor is never called good.

## Not yet

Boards identified from a photo, prices, and the repo's functional-salvage fixtures (donor blocks with evidence gates) shown in 3D.
