# First physical session: one real desktop, start to finish

Run this only on a unit you have the right to handle and resell (see `rights` gates in `unit.template.json`). It
turns one machine into a casefile that `casefile.py` can evaluate, and it measures the real hands-on minutes that
replace the assumed ones in `scenarios.json`. Anything marked **DESTRUCTIVE** is a human decision, never run by HS.

## Equipment (nothing to buy if you already own these)
Debian/Ubuntu live USB with network (or persistent); a second USB stick for the bundle; known-good mains lead and
monitor cable; anti-static wrist strap or touch bare chassis metal first; a phone for photos; a stopwatch (phone).
**Do not open, probe or repair a mains power supply. Do not power a unit with swollen capacitors, burn marks, liquid
residue or a smell of burning; record it and stop (that is a REJECT, not a repair).**

## 0. Intake (start the stopwatch: `inspection`)
1. Photograph the unit all sides, label side, internals. Keep photos that show serial numbers private (not in git).
2. Save the transfer receipt/invoice and the seller's written data-release into `evidence/` (rights gates).
3. Copy `unit.template.json` to `unit.json`; fill `unit_id`, `claimed` (what the seller said), `acquisition`.
4. Open the case unplugged. Look for: bulging/leaking capacitors, corrosion, burnt traces, missing CPU cooler,
   loose parts, pet/insect residue, a swollen CMOS battery. Any of these: record and decide REJECT.
5. Note installed RAM sticks, storage devices, GPU. **Do not read user files.** If the unit has data on a disk, do not
   boot its original OS; you only ever boot your live USB.

## 1. Power and POST (`power_post`)
Plug mains, keyboard, monitor, live USB. Press power. Record: time to BIOS screen, beep codes, fan behavior, any
error text (photo). No display after 2 minutes: reseat RAM, try the other RAM slot, one known-good stick; if still
nothing, stop (the NUC pilot's decision tree applies: do not invent a repair).

## 2. Bench bundle (`bench_hands_on` + `bench_unattended`)
```bash
sudo apt update && sudo apt install -y smartmontools memtester stress-ng dmidecode nvme-cli pciutils usbutils python3
# plug in a LAN cable first (the network gate needs an address)
sudo python3 bench_collect.py --out ./bundle --role target --selftest \
     --memtest-mb -1 --memtest-loops 2 --stress-seconds 1200
```
This is read-only for disks; memory and CPU load stay in RAM. It takes roughly 1.5 hours and needs no operator once
started (that is the "unattended" time in the model: it occupies a bench slot, not you). Watch the first minute for a
crash; a hang or reboot is itself a result: note it and mark the unit REJECT_OR_REPAIR.

## 3. Sanitize storage (`completion_wipe_install`): **DESTRUCTIVE, owner-authorized, per disk**
Confirm the device name three times against `lsblk -o NAME,MODEL,SIZE`. Prefer the drive's own erase:
* NVMe: `sudo nvme format /dev/nvme0n1 --ses=1` (user-data erase; use `--ses=2` if crypto-erase is supported)
* SATA SSD: ATA Secure Erase via `hdparm` (drive must not be "frozen"; suspend/resume or hot-plug if it is)
* HDD: one full overwrite pass (NIST SP 800-88 "Clear"): `sudo shred -n 1 -z -v /dev/sdX`
Then verify, declaring the method (this is a read-only check and does not wipe anything):
```bash
sudo HS_WIPE_METHOD="nvme format --ses=1" python3 bench_collect.py --out ./wipe_sda --role target --verify-wipe /dev/sda
```
Sampling detects an unwiped or partly wiped disk. It cannot prove unread sectors are clean; the casefile says so.

## 4. Install, clean, final checks (still `completion_wipe_install`)
Dust the heatsink and fans; replace failed RAM/SSD only after the unit's gates say which part failed. Install a
Linux image or ship without an OS. **Do not ship Windows unless the original COA sticker is photographed**
(`licence.os_to_ship = windows_with_coa`); refurbished-PC Windows licensing through Microsoft's refurbisher program
is aimed at large volumes, so it is not a route for a small shop.
Fill `operator_checklist` (USB ports, video output, power button/front panel, fans, cosmetic grade photos).

## 5. Evaluate and review
```bash
python3 casefile.py unit.json --out casefile_report.json
```
Expected: `READY_FOR_INDEPENDENT_REVIEW`. Any `unknown` means a missing measurement, not a pass. A second person then
reads the bundle and report, writes `review` (their name, the `bench_manifest_sha256` from the report, the date),
and the owner confirms the four `owner_legal_confirmations`. Only then does the report say `APPROVED_FOR_SALE`.
If the unit failed but components passed on their own, `bridge_salvage_engine.ingest_partout` records the good parts
in the Circuit-AI asset ledger.

## 6. Time sheet (this is the real output of session one)
Fill `timing_minutes_actual` in `unit.json`. The model's NT$ per hands-on hour depends on those minutes more than on
anything else you can control; replace the assumed minutes in `scenarios.json` with these and re-run
`python3 staged_economics.py`.

## 7. Listing disclosures (before any listing goes up)
State: tested items and results (memory loops, SMART status, burn-in minutes), what was replaced, the OS/licence,
cosmetic grade, return/warranty terms, and that data was sanitized (method). Under Taiwan's consumer protection law
distance-selling buyers by a business generally have a 7-day withdrawal right with only narrow exceptions, and
second-hand goods are not among the listed exceptions in the sources found: price returns in, do not assume an exemption.
