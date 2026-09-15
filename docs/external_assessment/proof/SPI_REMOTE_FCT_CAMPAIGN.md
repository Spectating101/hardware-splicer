# SPI Remote FCT Campaign

**Campaign:** `spi-flash-adapter-v1-remote-fct-r1`  
**PCB design:** `spi-flash-adapter-v1` revision `0.2-modeled`  
**Current state:** `PACKAGED_NOT_PHYSICAL`

This is the Gauntlet handoff for the first exact Hardware Splicer implementation-validation
campaign. It is deliberately separate from the earlier source-blind Astra evaluation: that
evaluation tested whether an external model could reason under the evidence boundary; this
campaign tests a later exact schematic/PCB implementation against physical measurements.

## Build

```bash
cd hardware/reference_designs/spi_flash_adapter_v1
python3 build_remote_fct_campaign.py \
  --output /tmp/spi-flash-adapter-v1-remote-fct.zip
```

The deterministic archive contains:

- canonical KiCad design package and standalone schematic/assembly PDFs;
- Gerber/drill fabrication archive, BOM and placement data;
- normalized native KiCad ERC/DRC reports and toolchain identity;
- bounded host software that exposes only one full-duplex `9F 00 00 00` transaction;
- numerical/procedural acceptance criteria and ordered provider test plan;
- the unmodified historical source-evaluation physical packet;
- a separate implementation-specific candidate boundary and physical packet;
- provider request, evidence-return template and remote-return contract;
- a machine-readable Gauntlet state projection.

Every production role resolves to included bytes with SHA-256 and size. The archive audit
rejects missing/tampered bytes, unsafe paths, role drift and attempted authority elevation.

## What Gauntlet may record

- exact reference implementation packaging: complete;
- production artifact byte set: complete and locally verified;
- provider capability/quotation packet: prepared, provider-neutral;
- external provider engaged: no;
- order or payment: no;
- fabrication/assembly/power: no;
- physical gates: not run;
- physical correctness: `UNPROVEN`;
- source-blind independent-design claim from this package: false;
- fabrication, bench-power and physical authority: false.

## Next valid transition

After exact-head CI publishes the deterministic archive, a human may review that exact hash
and decide whether to authorize a provider capability/quotation submission. Quote review,
legal/terms acceptance, payment and fabrication release remain protected human actions.

If a provider returns physical work, import only original raw files and measurements through
the revision-bound remote-return audit and physical-evidence envelope path. A provider PASS
certificate or matching JEDEC ID alone is insufficient.
