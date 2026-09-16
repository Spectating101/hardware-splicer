# Hardware Splicer offline demonstration

**Target duration:** 5–7 minutes  
**Network dependency:** none after cloning/downloading the frozen release  
**Physical claim:** none

## Objective

Demonstrate that Hardware Splicer makes useful engineering artifacts while keeping evidence and physical authority separate from model confidence.

## Preparation

Use the frozen revision `f892facd67c5124e2362860ebc999625afedc5d5` or the published release package. Verify the release ZIP against:

```text
6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd
```

Open these local artifacts before presenting:

- `docs/product/README.md`;
- `hardware/reference_designs/spi_flash_adapter_v1/README.md`;
- `hardware/reference_designs/spi_flash_adapter_v1/verification.json`;
- `hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch`;
- `hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb`;
- the published remote-FCT package or a deterministic local rebuild;
- `docs/external_assessment/CLAIMS_AND_NONCLAIMS.md`.

## Demonstration

### 1. The engineering problem

Show that the host is 3.3 V and the W25Q128JW device domain is 1.8 V. Explain that a plausible connection diagram is not enough: exact package, pin direction, voltage, source, revision, and power sequencing matter.

### 2. Evidence before confidence

Show `design_manifest.json`. Point out that manufacturer documents are recorded by identity and URL rather than treating a model recollection as a source.

### 3. Editable artifact

Open the schematic and PCB. Show the fixed-direction translator, independent chip-select bias, default-disabled output enable, removable rail links, test points, and continuous ground-reference intent.

### 4. Deterministic acceptance

Open `verification.json`, then run when the local KiCad environment is available:

```bash
cd hardware/reference_designs/spi_flash_adapter_v1
python3 verify_design.py
```

Explain what the check establishes—ERC/DRC/parity and bound design rules—and what it does not establish: signal integrity under real loading, assembly correctness, rail behavior, or physical function.

### 5. Physical handoff without physical claim

Inspect the remote-FCT package. Show that it contains fabrication files, BOM, placement, host-test software, acceptance criteria, provider instructions, and an evidence-return schema.

Show `GAUNTLET_STATE.json` reporting `PACKAGED_NOT_PHYSICAL`.

### 6. Fail-closed conclusion

End on the next valid transition:

```text
independent review
-> fabrication
-> cold inspection
-> controlled power
-> read-only 0x9F
-> revision-bound evidence ingest
```

The successful demonstration is not that the AI “finished the board.” It is that a substantial engineering package exists without its software success being misrepresented as physical truth.

## Failure-safe fallback

If a live service, UI, or model is unavailable, continue with the frozen local files. The demonstration must not depend on producing a favorable fresh model response.
