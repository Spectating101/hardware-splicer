# HS native SPI within-job checkpoints — November 15, 2026

## Scope

Opt-in, software-only engineering experiment built on the existing HS SPI
reference and PR #315's verified workshop operator. No autonomous code agent,
robot operations, fabrication, physical measurements, public deployment or
model-provider failover.

Stages:

1. Source: stage exact Git-tracked inputs and preserve their SHA-256, including
   the historical reference receipt in the SOURCE FINGERPRINT but never as a
   reusable verification output.
2. Netlist: run the real KiCad schematic netlist export.
3. ERC: run the real KiCad schematic rules check; retain JSON and stdout.
4. DRC: run the real KiCad PCB design-rules and schematic-parity checks;
   retain JSON and stdout.
5. Verification: run the original source's topology/BOM/pad/ground consistency
   and native-report validation. Reuse netlist/ERC/DRC only after all five
   artifact hashes, source hashes and KiCad/pcbnew versions match. The final
   stage does not issue a second KiCad ERC/DRC subprocess.

## Reproduce on an authorized KiCad 9 workstation

Use a fresh, previously nonexistent output directory:

    PYTHONDONTWRITEBYTECODE=1 python3 scripts/hs_spi_checkpoint.py run \
      --out /private/hs-checkpoints/fresh-spi

For a controlled interruption in a DIFFERENT new directory:

    PYTHONDONTWRITEBYTECODE=1 python3 scripts/hs_spi_checkpoint.py run \
      --out /private/hs-checkpoints/interrupted-spi \
      --interrupt-after erc

The deliberate crash-like exit code is 77, after source/netlist/ERC receipts
have been committed and fsynced. Launch a NEW Python process:

    PYTHONDONTWRITEBYTECODE=1 python3 scripts/hs_spi_checkpoint.py resume \
      --out /private/hs-checkpoints/interrupted-spi

Expected: 3 stages reused and 2 newly executed, with byte-identical
canonical verification.json relative to the normal uninterrupted run.
Repeated resume after completion does not run native checks, but validates
the completed source and artifacts. Read-only checkpoint inspection:

    PYTHONDONTWRITEBYTECODE=1 python3 scripts/hs_spi_checkpoint.py status \
      --out /private/hs-checkpoints/interrupted-spi

## Acceptance and limitations

- Exact local Git HEAD, complete tracked-source digest map, KiCad CLI version
  and pcbnew version must match across restarts.
- Every completed native output is hashed and checked before reuse.
- Changed source/report bytes, malformed stage order, missing evidence,
  target symlinks and concurrent runs fail closed.
- A stage interrupted BEFORE checkpoint commit is untrusted and rerun; its
  partial output must never become a green receipt.
- Local checkpoint evidence assumes the operator and local filesystem are
  trusted. An attacker who can rewrite both artifacts and checkpoint is
  outside scope. No independently signed provenance is claimed.
- It checkpoints native KiCad tool stages, not partially completed LLM
  internal reasoning or hidden state. Provider auth/quota/budget readiness
  requires a separately reviewed policy for model-dependent jobs.
- A successful CAD report does not prove physical correctness or authorize
  fabrication or power-on.

## Source-custody and verification

The existing standalone verify_design.py CLI still runs fresh KiCad netlist,
ERC and DRC by default. The new internal reuse API requires an explicit
complete five-file hash map, then runs original topology/BOM/board and
ground verification without re-running native ERC/DRC.

The canonical native reference receipt and original workshop operator pilot
were regenerated and source-hash-bound to the modified verifier, preserving
all original source-integrity regression checks.

Native Optiplex acceptance and an offline CI suite are separate:
generic GitHub Actions runners must not claim native KiCad passes when
KiCad and pcbnew are unavailable.

## Next boundary

The merged HS remote dispatcher already proves job-level recovery; this
new operator covers within-job native stage recovery. Do not duplicate
remote scheduling. Merge into the existing approved worker path only after
review of exact-source and native evidence. Long-horizon model-provider
readiness and transfer of inspectable LLM intermediate outputs are separate.
