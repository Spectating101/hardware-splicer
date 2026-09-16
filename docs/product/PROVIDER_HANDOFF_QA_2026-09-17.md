# Provider and fabrication handoff QA — 2026-09-17

**State:** `QUOTE_PACKET_READY_AFTER_CONTACT_AND_BUDGET_AUTHORITY`  
**External contact:** none  
**Order/payment:** none

## Frozen package checked

```text
out/gauntlet/spi-flash-adapter-v1-remote-fct-main-f892fac.zip
SHA-256 6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd
```

QA performed on 2026-09-17:

- outer archive contains 24 members;
- ZIP integrity test passes for all 24 members;
- archive hash matches the published release;
- package includes schematic, assembly drawing, BOM, pick-and-place, fabrication archive, canonical design package, host-test software, acceptance criteria, ordered provider test plan, evidence-return template, native ERC/DRC reports, and Gauntlet state;
- ignored PCB quotation and independent-review packets remain local outputs and are not canonical release assets;
- package state remains `PACKAGED_NOT_PHYSICAL`.

## Quotation questions

A quotation request should obtain explicit answers for:

- supported two-layer stackup and copper weight;
- minimum 0.15 mm neck-down, 0.20 mm clearance, and 0.30 mm drill capability;
- soldermask/paste handling and castellated/edge assumptions, if any;
- exact component sourcing and whether customer-supplied parts are supported;
- proposed substitutions, with manufacturer part number and rationale;
- DNP handling for R1 and R4;
- through-hole handling for J1 and JP1, with no enable shunt fitted;
- orientation/marking inspection and photo evidence;
- whether cold continuity/resistance checks can be performed;
- whether controlled-power and read-only functional testing can be performed;
- instruments, current-limit capability, waveform/raw-data export, calibration information, and evidence format;
- quantity, unit price, tooling/setup fees, shipping, tax, lead time, and quote validity;
- treatment of failed units and whether raw failure evidence is returned.

## Acceptance boundary

A provider quotation, DFM review, or fabrication completion is not an engineering PASS. Physical evidence is accepted only through the revision-bound return contract and staged procedure.

## Protected actions

Require human authority before:

- sending personal/contact/address data;
- accepting terms or a quotation;
- selecting substitutions;
- placing an order or payment;
- authorizing fabrication, assembly, power, or test;
- treating a provider certificate as evidence beyond what its raw measurements support.
