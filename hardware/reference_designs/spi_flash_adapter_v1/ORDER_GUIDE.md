# SPI flash adapter v1: prototype order

Prepared **2026-11-15**, revision **0.2-modeled**, KiCad **9.0.2**.
This is a first-article package: no board has been built or powered. The CAD
verifier's existing authority flags remain unchanged; exporting manufacturing data
does not constitute EE sign-off or physical proof.

## Choose one route first

| | A. Bare boards (default) | B. Partial assembly |
| --- | --- | --- |
| What JLCPCB does | Makes five bare PCBs | Makes five PCBs and places **11 parts** on some of them: U1, R2/R3/R5/R6/R7, C1/C3/C4/C5/C6 |
| What you solder | Everything fitted: U1 (0.65 mm pitch TSSOP-14), U2, U3, ten 0603 passives, C2, J1, JP1 | **U2, U3, C2, J1, JP1** |
| Upload | The Gerber ZIP only | The Gerber ZIP, `fab/JLCPCB_BOM.csv` and `fab/JLCPCB_CPL.csv` |
| Depends on | Your fine-pitch soldering | JLCPCB stock of four Extended parts, their fees, and your approval of U1's orientation |
| Order steps | 1–3 | 1, 2 and 4–7 |

Route A needs no placement file and no orientation decision. Route B saves the
fine-pitch U1 joint and the 0603 work, but U1's factory orientation must be approved
by you before assembly (step 6). R1/R4 stay unfitted and JP1 stays without a shunt
on either route.

## Regenerate and identify the order

From this directory, with KiCad 9 and its system Python installed:

```sh
/usr/bin/python3 verify_design.py
/usr/bin/python3 export_fab.py
(cd fab && sha256sum -c SHA256SUMS.txt)
```

`fab/` is checked in. Regeneration reads the routed, filled PCB; it does not reroute
or modify the CAD. `manifest.json` binds the PCB, schematic, project, procurement
BOM, exporter and procedures by SHA-256. The Gerber/drill header epoch and ZIP
timestamps are fixed for reproducibility; they are not measurement or sourcing dates.
`SHA256SUMS.txt` hashes the exact files from that export, including the ZIP and
`manifest.json`; these are upload-integrity hashes, not hashes of normalized data.
KiCad 9 patch/build versions remain truthful in the headers and manifest, so hashes
can differ between installations. The regeneration test normalizes only the version
in Gerber `%TF.GenerationSoftware` and `G04 Created by KiCad (PCBNEW …)` headers,
Excellon `; #@! TF.GenerationSoftware` and `; DRILL file {KiCad …}` headers, and
manifest `kicad_cli`. It compares all other artwork/drill bytes exactly, including
the fixed `TF.CreationDate` and comment dates. ZIP metadata and uncompressed members
are checked; CRCs, sizes and compressed bytes follow the version-bearing contents.
Each export's hashes are verified against its own unmodified files before comparing
checksum manifests with only digest fields masked; filenames, order and whitespace
must still match exactly.
Archive this manifest and the exact uploaded ZIP with the private order record.

## Board options

| Option | Choose |
| --- | --- |
| Material / layers | Rigid FR-4, 2 layers |
| Size / quantity | **90.00 × 50.00 mm**, 5 individual boards, one design |
| Thickness / copper | 1.6 mm, 1 oz outer copper |
| Finish | Lead-free HASL for lowest cost; ENIG optional for easier fine-pitch soldering |
| Mask / legend | Green mask, white silkscreen |
| Vias | Standard through vias, tented where the supplied masks cover them; no filling |
| Special processing | No impedance control, castellations, edge plating, blind/buried vias or V cuts |
| Testing | Flying-probe electrical test enabled |
| Panel / stencil | Single boards; no customer panel. No stencil for hand soldering |

The design uses 0.15 mm minimum track neck-down, 0.20 mm clearance and 0.30 mm
minimum via drill. Four **3.2 mm non-plated** M3 holes are mechanical features.
The drill set has **20 plated 0.30 mm vias, 8 plated 1.00 mm header holes and
4 non-plated 3.20 mm mounting holes**. Ask the fab to preserve that distinction if its import
does not infer it. For PCBA, let the fab propose tooling rails/fiducials; none are
provided as a customer panel. Any provider panel appears in the production file you
approve after payment (step 6), not before.

The top legend follows [JLCPCB's published limits](https://jlcpcb.com/capabilities/pcb-capabilities)
(read 2026-11-15): every stroke is 0.15 mm, all text is 1.0 mm high, and each test
pad's circle has a 1.00 mm centerline radius, 0.175 mm clear of its 1.5 mm pad.

## Upload and preview

1. Upload **only** `fab/spi_flash_adapter_v1-jlcpcb-gerbers.zip` to the PCB quote.
   It contains nine Gerbers and two separate Excellon drill files, at the ZIP root.
   The naming follows [JLCPCB's layer table](https://jlcpcb.com/help/article/gerber-files-preparation):

   | Extension | Layer |
   | --- | --- |
   | GTL / GBL | Top / bottom copper |
   | GTS / GBS | Top / bottom solder mask |
   | GTO / GBO | Top / bottom silkscreen (bottom is intentionally empty) |
   | GTP / GBP | Top / bottom paste (bottom is intentionally empty) |
   | GKO | One board outline |
   | -PTH.XLN / -NPTH.XLN | Plated / non-plated metric drills |

2. Check that the preview detects **two copper layers**, a single closed rectangular
   90 × 50 mm outline, four corner mounting holes and no duplicate outline. Copper
   fills must appear on both sides. Check drill holes align with header pads and vias;
   there must be no global shift, mirror or 25.4× unit error. Inspect U1's 0.65 mm
   pitch pads for mask clearance, exposed test pads and readable J1 pin-order text.
   Paste is stencil data, not another copper layer. An empty bottom paste/legend is normal.
3. For bare boards (route A), leave assembly off. Buy all fitted BOM parts and solder one board,
   leaving **R1/R4 absent** and **JP1 without a shunt**. Use the exact U1/U2/U3 packages.
4. For partial assembly (route B), select **top side only**, quantity 2 assembled out
   of 5 if offered (otherwise quote 5). Upload `fab/JLCPCB_BOM.csv` and `fab/JLCPCB_CPL.csv`.
   These follow the documented [BOM](https://jlcpcb.com/help/article/bill-of-materials-for-pcb-assembly)
   and [CPL](https://jlcpcb.com/help/article/pick-place-file-for-pcb-assembly) formats.
   There are **4 BOM lines and 11 placements**. All are on Top. Coordinates are in mm,
   KiCad absolute/Gerber frame (+Y up, so these Y values are negative), with unmodified
   KiCad rotation modulo 360. No supplier-specific rotation correction is applied,
   because none has been proven (see "Why U2 and U3 are hand-soldered").
   Paste Gerbers follow the full PCB pad artwork, including unpopulated pads. Tell
   the assembler to omit paste at R1/R4 and at hand-soldered C2, U2 and U3 when
   preparing its assembly stencil; no solder bridge may replace an absent link.
5. **Before paying, only your own checks have happened.** Match every assembly MPN
   and package to `BOM.csv` and click confirm for each of the four lines; do not
   accept an automatic substitute. Then look at the placement preview. It is
   generated automatically and is for reference only. JLCPCB's
   [assembly FAQ, section 9](https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2)
   states that assembly orders do **not** support Review Before Payment, so no
   JLCPCB engineer has looked at these files when you pay. In the preview:
   - The ten passives are unpolarized; 0° and 180° are equivalent. Each must lie
     along its two pads, not across them.
   - **U1** is the only oriented part. Its pin 1 pad is the upper-left pad at
     **(142.1375, 86.05) mm** in KiCad's +Y-down board frame (the CPL uses the
     opposite Y sign); the body center is (145, 88). The legend has a pin-1 mark
     beside that pad. The preview's red dot is an orientation mark on JLCPCB's
     library drawing, not necessarily pin 1 (FAQ section 1): compare the drawn body
     and pad rows with the board's pads, and compare the dot with the legend mark.
   - The CPL gives U1 as 0°, which matches TI's tape orientation for TXU0304PWR
     (quadrant 1) under the rule in FAQ section 3. The EasyEDA/LCSC library footprint
     for C4364118 is drawn a quarter turn away from that. Expect the preview to show
     U1 rotated. That is a reason to use the hold in step 6. It is not a reason to
     guess a new angle. If you do edit the CPL rotation as FAQ section 2 allows,
     record the angle and the preview screenshot with the private order record.
6. **Hold assembly for your orientation approval.** When ordering, select
   **Confirm Parts Placement** (a small paid option, [listed at $0.45 in October 2026](https://jlcpcb.com/blog/reduce-pcb-assembly-cost-prototype);
   read the live price). Add an order remark: "Do not assemble until I approve the
   placement file. U1 pin 1 is the upper-left pad next to the silkscreen mark, toward
   C3." Then pay. After payment JLCPCB's engineers prepare the production file from
   your files and the legend; by default they set rotation and polarity from the
   silkscreen marks, and follow the legend if it disagrees with the CPL (FAQ sections
   2 and 10). They email when the file is ready. Open it from the order history and
   check U1 pad by pad, as in step 5. Approve only if pin 1 is correct; otherwise
   reject it with the pad coordinates above. Answer inside the time stated in that
   email: JLCPCB's order page says an unanswered confirmation goes to production.
   Keep the approved placement image with the private order record.
7. **U2, U3, J1, JP1 and C2 must be hand-soldered** after partial assembly; see
   `fab/HAND_SOLDER.csv`. U2 pin 1 (CS#) goes to the pad at (166.4125, 86.095) and
   U3 pin 1 (IN) to the pad at (123.8625, 67.05), both upper-left beside the legend
   mark. R1/R4 are loose bring-up parts, never factory fitted.
   TP1–TP18 are bare board pads; H1–H4 are holes, not purchased components.
   Obtain a removable 2.54 mm shunt separately for the later enable step; keep it off
   during initial assembly. Complete U2, U3 and C2 before applying power.

### Why U2 and U3 are hand-soldered

JLCPCB turns each part from its own zero orientation by the CPL angle,
counterclockwise. Its stated rule (FAQ section 3) is that zero is the part's
orientation in its tape. Its preview draws the EasyEDA/LCSC library footprint. An
angle was to be written into `export_fab.py` only if exact-part evidence proved it.
Checked on 2026-11-15, it does not:

| Part | Tape-and-reel drawing | Exact-part library footprint | Angles implied for this board |
| --- | --- | --- | --- |
| U2, [C7150045](https://jlcpcb.com/partdetail/Winbond-W25Q128JWSIQTR/C7150045) | The Winbond W25Q128JW datasheet gives no tape orientation for this part | `SOIC-8_L5.3-W5.3-P1.27-LS8.0-BL`: pin 1 lower left, pins 1–4 along the bottom edge | Tape: unknown. Footprint: 270° |
| U3, [C2877863](https://jlcpcb.com/partdetail/TexasInstruments-TLV75518PDBVR/C2877863) | [TI TLV755P](https://www.ti.com/lit/ds/symlink/tlv755p.pdf) package materials: TLV75518PDBVR, pin 1 in quadrant 3 | `SOT-23-5_L2.9-W1.6-P0.95-LS2.8-BR`: pin 1 lower right, pins 1–3 up the right edge | Tape: 270°. Footprint: 180° |

The footprint column is the pad data EasyEDA serves for each LCSC number
(`https://easyeda.com/api/products/<LCSC number>/components`), compared with the
board's footprints, which have pin 1 upper left. For U3 the two sources give
different angles. For U2 there is one source and no way to confirm, without an
authenticated placement preview, that the preview applies the angle to that drawing
as assumed. Neither is proof, so no angle is encoded and both parts are absent from
the BOM and CPL uploads. Both are leaded packages that are practical to solder by hand.
U1 has the same disagreement (tape 0°, footprint 270°); it stays in the upload at
the unmodified 0° because its 0.65 mm pitch is the main reason to choose assembly,
and steps 5 and 6 are the control.

The root `BOM.csv` is the procurement authority, with each exact MPN's public
source, check date, stock status or explicit `hand-solder` disposition. Public LCSC
pages were checked on **2026-11-15** for part identity/package. Their current
rendered pages did **not expose stock counts**; stock is recorded as unconfirmed,
not zero or reserved. LCSC retail inventory also does not guarantee JLCPCB PCBA
availability. Recheck all four assembly lines in the order picker, including attrition,
and choose economic/standard service as the picker permits. If one is unavailable,
either wait for that exact MPN or remove it from **both** upload files and arrange
hand soldering; retain a private record of that variant. The default bare-board
route does not depend on assembly inventory. C2 has no established exact LCSC
mapping, and both Samtec through-hole headers are deliberately hand-solder items.

### Extended parts and their fee

JLCPCB's public part pages, read 2026-11-15, class **all six** LCSC-mapped parts as
**Extended**; none is Basic.

| Refs | LCSC number | Part | In the partial-assembly upload |
| --- | --- | --- | --- |
| U1 | [C4364118](https://jlcpcb.com/partdetail/TexasInstruments-TXU0304PWR/C4364118) | TXU0304PWR | Yes |
| R2 R3 R5 R6 R7 | [C98220](https://jlcpcb.com/partdetail/YAGEO-RC0603FR_0710KL/C98220) | RC0603FR-0710KL | Yes |
| C1 C6 | [C97888](https://jlcpcb.com/partdetail/Murata-GRM188R71A105KA61D/C97888) | GRM188R71A105KA61D | Yes |
| C3 C4 C5 | [C45000](https://jlcpcb.com/partdetail/MurataElectronics-GRM188R71C104KA01D/C45000) | GRM188R71C104KA01D | Yes |
| U2 | [C7150045](https://jlcpcb.com/partdetail/Winbond-W25Q128JWSIQTR/C7150045) | W25Q128JWSIQ | No, hand-solder |
| U3 | [C2877863](https://jlcpcb.com/partdetail/TexasInstruments-TLV75518PDBVR/C2877863) | TLV75518PDBVR | No, hand-solder |

[JLCPCB's assembly price list](https://jlcpcb.com/help/article/pcb-assembly-price)
(last updated 2026-10-22) charges a feeder loading fee of **$3.07 per Extended part
number per order** on Economic PCBA, and $1.53 per part number, Basic or Extended,
on Standard PCBA. The four uploaded lines therefore add **4 × $3.07 = $12.28** on
Economic (all six would be $18.42), on top of the $8.18 setup fee, $1.53 stencil,
per-joint charges and the parts themselves, which carry minimum or attrition
quantities. Read the itemized quote; these are list figures, not a quote. U2 and U3
are bought separately for hand soldering and carry no JLCPCB loading fee.

## Budget on 2026-11-15

These are **planning estimates in USD, not live quotes**:

| Route | Expected range |
| --- | --- |
| Five bare boards, before shipping/tax | $2–15 |
| Route A: parts for two hand-built boards, including small-quantity overhead/spares | $15–40 |
| Route B: five boards with two partially assembled, before shipping/tax and hand-solder parts | $35–100 |
| Shipping allowance per order, destination-dependent | $10–35 |
| FT232H USB-SPI board, if needed | About $15–25 plus cable/shipping |

[JLCPCB advertises a $2 starting price for five standard small boards](https://jlcpcb.com/help/article/how-do-i-place-an-order).
[Assembly charges](https://jlcpcb.com/help/article/pcb-assembly-price) add setup,
stencil, component/feeder, placement and possible panel costs. Every assembly line
is an Extended part (see the fee table above); standard assembly or special sourcing
can exceed this estimate. Shipping, duty/tax, coupons and tools are excluded from the
PCB/PCBA rows. Read the itemized quote before paying. That quote is the only
pre-payment check of cost; the engineering check of placement comes after payment
(step 6). No quote or order was submitted for this package.

After delivery, follow [BRING_UP_TEST.md](BRING_UP_TEST.md). Keep shipping labels,
payment details, operator identities and raw bench records outside this public repo.
