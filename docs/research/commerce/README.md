# Taiwan commerce donor-source inventory, 2026-10-19

Purpose: gather concrete, individually linked, damaged/incomplete/surplus
devices sold in Taiwan that Hardware Splicer might investigate. This is
NOT an arbitrage ranking, confirmed stock, a purchase decision, a
verified component bill of materials or a physical donor contract.

## Coverage and inputs

17 unique Ruten Taiwan item URLs, 10 device families:

- Barcode scanners: 2 (cut-cable Symbol LS2208; untested Unitech MS920)
- Thermal/portable label printers: 4 (Sewoo, Zebra, MAX and POSTEK)
- Dot-matrix printer: 1 (Epson without printhead and accessories)
- NAS computing board: 1 (QNAP board-only)
- NAS chassis: 1 (Thecus without drives/power supply)
- Network AP: 1 (faulty Cisco Meraki MR32)
- Keyboard/mouse: 1 (working-button claim, failed optical movement)
- Laptop: 1 (broken BenQ with DVD-ROM)
- Robot vacuums: 4 (Neato, Narwal and LG; battery hazards)
- Robot LDS replacement parts: 1 (Xiaomi/Roborock variants, NOT e-waste)

Advertised ask range across sampled item/variants: NT$50-3,606.
This is NOT a statistically representative frequency distribution or
confirmed in-stock market depth. Variant listing minimums may be for
individual spares, rather than the entire item in the photograph.

Some revealing listing-specific source observations:

1. Symbol Motorola LS2208 1D barcode scanner, NT$50, Tainan:
   cut cable, untested; 5V/0.2A label asserted.
   https://www.ruten.com.tw/item/22623851402690/
2. Unitech MS920, NT$100-200, Changhua: 22 stock claimed across
   variants, battery and dock presence uncertain.
   https://www.ruten.com.tw/item/22535705728769/
3. Epson LQ-680/680C printer NT$300, Changhua: broken, no printhead,
   consumables, cover or wiring; possible gears/motors only.
   https://www.ruten.com.tw/item/21447795842755/
4. Thecus N2200 NAS NT$350, Kaohsiung pickup only; no PSU/disks,
   no successful boot claimed.
   https://www.ruten.com.tw/item/22622803064195/
5. QNAP TS-219P II PCB and SATA daughterboard NT$650, New Taipei:
   seller claims minimal boot/Qfinder network; no PSU, disks or case.
   https://www.ruten.com.tw/item/22606139676402/
6. Apple A1314 keyboard/mouse set NT$500, Changhua: mouse buttons
   claimed responsive, optical movement not working.
   https://www.ruten.com.tw/item/22613329448846/
7. Neato Botvac D NT$2,000, Taoyuan, battery failed, wheel/brush
   assemblies reportedly still look intact. No sensor proof.
   https://www.ruten.com.tw/item/22048094434606/
8. Xiaomi/Roborock LDS spare assembly/motor NT$520-1,320,
   listed as replacement PARTS, not a broken donor machine.
   https://www.ruten.com.tw/item/22507753741654/

## Dataset formats

- tw_salvage_donor_listings_2026-10-19.json: original seller-claim
  research records with exact item URL, asking range, exclusions,
  preliminary subsystem hypotheses and next information needed.
- tw_donor_discovery_2026-10-19.json: normalized HS-readable
  discovery packet with source/authority boundary preserved.
- tw_donor_discovery_2026-10-19.csv: flat one-listing-per-row export.

Regenerate:

    PYTHONPATH=src python -m scripts.export_commerce_donor_inventory

Validate:

    PYTHONPATH=src python -m pytest -q tests/test_commerce_donor_inventory.py

## Strict provenance and usage

Every observed record is a marketplace seller claim, not measured or
authenticated evidence. Subsystem lists are hypotheses only. We have
not contacted any sellers, inspected their hardware, confirmed that
items are still stocked, or validated pinouts, electrical limits,
firmware, functions, battery safety or legal ownership.

For a buyer to make a listing into a real Hardware Splicer donor,
first confirm the exact specimen and purchase rights. A later,
separate evidence workflow must identify and verify actual modules,
interfaces, condition, physical safety and human approvals.
No commerce record may authorize purchasing, fabrication, flashing
or power-on, nor be automatically upgraded to a verified donor.
Network-device/cloud locks and prior owners' private data must not
be bypassed or retained. Batteries/laser optics/mains equipment
require suitably qualified physical inspection.

Broaden the inventory using exact listing IDs from searches, retaining
the same caution for stock, condition and variants:

- https://www.ruten.com.tw/search/%E6%AE%BA%E8%82%89/?cateid=0011
- https://www.ruten.com.tw/search/%E9%9B%B6%E4%BB%B6%E6%A9%9F/?cateid=00110028
- https://www.ruten.com.tw/search/%E6%95%85%E9%9A%9C%E7%AD%86%E9%9B%BB/
- https://www.ruten.com.tw/search/%E6%95%85%E9%9A%9C/?cateid=00110028

Next capability: map commerce listings into unverified *donor candidates*
after a specific item is acquired and independently checked, never
directly into a fabricated physical engineering contract.
