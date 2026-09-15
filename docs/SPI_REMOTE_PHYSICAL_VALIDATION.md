# SPI remote physical validation

Hardware Splicer can prepare a revision-bound test request for a contract laboratory or PCBA
test service when the project owner has no local bench.  The remote service supplies hands,
instruments, and a physical site; it does not become a second evidence or authorization
authority.

The lane is provider-neutral.  A named provider is a proposed target, not an endorsement or a
claim that the provider has accepted the work.

## Boundary

```text
canonical project revision
  -> project physical-validation packet
  -> remote provider handoff
  -> provider work order and physical test article
  -> original raw return files + measurements + calibration identities
  -> remote-return audit
  -> existing server-attested physical-evidence envelopes
  -> existing project physical-validation submission
  -> separate human authorization ledger
```

The remote-return audit checks transport and attribution.  Passing it means only
`eligible_for_physical_evidence_import`; it is not itself physical evidence and cannot grant
fabrication, bench-power, or physical authority.

## Prepare a handoff

First export a current project physical-validation packet from:

```text
GET /v1/projects/{project_id}/engineering/physical-validation/packet
```

Then run:

```bash
PYTHONPATH=src python scripts/prepare_spi_remote_physical_handoff.py \
  --physical-packet /path/to/PHYSICAL_VALIDATION_PACKET.json \
  --out-dir /tmp/hs-remote-spi \
  --provider-id proposed-contract-lab \
  --provider-name "Proposed Contract Lab" \
  --engagement-mode pcba_production_and_test
```

The output contains:

- `REMOTE_TEST_REQUEST.json` — exact project, candidate, provider target, artifacts and gates;
- `REMOTE_TEST_PLAN.md` — readable ordered procedure and safety boundary;
- `EVIDENCE_RETURN_MANIFEST.template.json` — the provider return structure;
- `REMOTE_PHYSICAL_HANDOFF.zip` — byte-deterministic quote attachment;
- `PREPARATION_SUMMARY.json` — preparation status and archive hash.

Personal contact details are deliberately excluded.  They belong in the provider's account or
quote portal, not in a public or durable engineering artifact.

The same handoff is available through the canonical product and MCP surface:

```text
POST /v1/projects/{project_id}/engineering/physical-validation/remote-handoff
```

The request fixes the expected project revision, provider target, engagement mode, requested
capabilities, and any hash-bound manufacturing artifacts.  Preparing a handoff is read-only: it
does not revise the project or engage the provider.

## Production artifacts

The handoff can be sent for capability review and quotation before a design is released.  For a
PCBA production-and-test engagement, it reports the still-required artifact roles:

- schematic;
- fabrication archive;
- BOM;
- pick-and-place file;
- assembly drawing;
- test firmware.

Even when that set is complete, `fabrication_release_ready` remains false until a human decision
authorizes the exact revision and artifact hashes.

## What the provider must return

A summary certificate saying `PASS` is insufficient.  Each executed gate must retain:

- the work order, physical site, assembly revision and serial number;
- the direct operator identity and capture time;
- measured values and explicit acceptance criteria;
- original raw files with SHA-256 and byte size;
- instrument and calibration identities for instrumented gates;
- a provider attestation that the named operators observed the physical test article.

Failed tests are useful and must return their raw captures too.  No provider report may
self-declare HS physical authority.

Submit the provider manifest plus the exact base64-encoded raw return files to:

```text
POST /v1/projects/{project_id}/engineering/physical-validation/remote-return/audit
```

The canonical endpoint rebuilds the handoff from the current project revision before auditing
it.  It rejects stale or altered handoffs, duplicate/unsafe raw paths, incorrect hashes or byte
sizes, missing instrument/calibration identities, missing gate prerequisites, summary-only
claims, and provider self-authorization.  It does not persist the return.  An accepted result is
only eligible for the existing server-attested evidence import path.

## Current SPI project status

The existing W25Q128JW/TXU0304 project has a deterministic eight-gate physical packet, but it
does not yet contain a released schematic, PCB, BOM, placement set, or test firmware.  The new
remote lane therefore makes the project quote-ready, not fabrication-ready.  Completing those
production artifacts is the next engineering tranche before any service should manufacture or
energize a board.

That historical family-level state is preserved in PR #99. The later exact reference design
adds a separate campaign bridge rather than rewriting the old candidate identity. Build it from
`hardware/reference_designs/spi_flash_adapter_v1/build_remote_fct_campaign.py`. Its outer
archive includes and byte-verifies the actual six required production roles, while the embedded
remote-handoff metadata still has no authority effect. The MCU-less adapter's historical
`test_firmware` role is fulfilled by explicitly identified bounded **host test software**; the
package does not imply firmware is installed on the board.
