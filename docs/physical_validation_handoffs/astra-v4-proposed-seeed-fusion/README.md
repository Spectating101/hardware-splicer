# Astra v4 proposed remote PCBA/test handoff

This directory is a prepared, non-authorizing capability-review packet for the frozen
primary-source Astra v4 candidate.  Seeed Fusion PCBA is recorded only as a proposed
commercial target.  Hardware Splicer has not transmitted the packet, requested a quote,
placed an order, or represented that the provider accepted the work.

The source packet reproduces the published project boundary exactly:

- project: `hs-astra-rawdoc-v4-20260913-1`;
- source revision: `6`;
- packet: `physical-validation-fdd10770454d7a84`;
- candidate: `hs-astra-rawdoc-v4-20260913-1@b7c724e0561d4ec8`;
- snapshot: `sha256:b7c724e0561d4ec8ab21b7ad4e869256c5cca2f80416d1f07bd020164c152272`.

`REMOTE_PHYSICAL_HANDOFF.zip` is the deterministic attachment a provider can review.
Its SHA-256 is recorded in `PREPARATION_SUMMARY.json`.  The expanded JSON, test plan,
and return template are retained beside it for review and diffing.

The packet is ready for provider capability review and quotation, but it is not ready for
fabrication.  The candidate still lacks the exact schematic, fabrication archive, BOM,
pick-and-place file, assembly drawing, and test firmware.  Producing those artifacts requires
a separate design-closure tranche and an explicit human release of their final hashes.

Regenerate the handoff with:

```bash
PYTHONPATH=src python scripts/prepare_spi_remote_physical_handoff.py \
  --physical-packet docs/physical_validation_handoffs/astra-v4-proposed-seeed-fusion/SOURCE_PHYSICAL_VALIDATION_PACKET.json \
  --out-dir docs/physical_validation_handoffs/astra-v4-proposed-seeed-fusion \
  --provider-id proposed-seeed-fusion \
  --provider-name "Seeed Fusion PCBA" \
  --engagement-mode pcba_production_and_test \
  --service-url "https://www.seeedstudio.com/prototype-pcb-assembly.html"
```
