# Project-bound physical validation

Hardware Splicer can carry a bounded `preFabricationPlan` into the same audited
physical-evidence system used by full engineering plans. The bridge is deliberately
fail-closed: it creates an executable bench packet, not a claim that hardware exists
or works.

## What the packet binds

`GET /v1/projects/{project_id}/engineering/physical-validation/packet` returns:

- the canonical project ID and source revision;
- a SHA-256 boundary over the engineering snapshot;
- a stable candidate revision derived from that hash;
- exact physical gate IDs, procedures, prerequisites, and required capture fields;
- the required instrument classes and safety ordering;
- the attested-envelope and project submission routes.

Physical-evidence history and generated package listings are excluded from the
candidate hash. Adding evidence therefore does not stale the candidate it measures,
while any source, requirement, decision, action, constraint, or review change does.

## SPI flash adapter sequence

The SPI profile is split into four bounded transitions:

1. Unpowered identity capture: photograph and record the exact DUT, programmer, and
   assembled adapter/translator identities.
2. Cold electrical capture: verify net mapping, ground continuity, rail resistance,
   shorts, and voltage-domain isolation with all supplies disconnected.
3. Human bench-power decision: use the normal authorization ledger to authorize only
   `bench_power`, with a current-limited operating envelope.
4. Powered capture: measure rails/current/backfeed, logic levels and timing, execute
   only the read-only JEDEC `0x9F` transaction, and complete a bounded thermal dwell.

The packet expressly forbids WREN, status writes, program, and erase operations. A
later firmware-flash authorization is a separate human decision.

## Capturing evidence

First configure a server evidence-signing key of at least 32 bytes. Keep the value out
of project JSON and version control.

```bash
export HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY='replace-with-a-secret-lab-key'
export HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID='lab-key-2026'
```

For each gate, create a `PhysicalEvidenceRecord` using the packet's project ID,
candidate revision, artifact hashes, gate ID, procedure ID, and evidence kind. A real
capture must also include this metadata:

```json
{
  "simulated": false,
  "public_web": false,
  "capture_origin": "physical_test_article",
  "direct_operator_observation": true
}
```

Send the record and base64 raw capture bytes to:

```text
POST /v1/engineering/physical-evidence/envelopes/build-attested
```

The server hashes the bytes and HMAC-attests the complete file reference. Raw bytes
are not retained by this endpoint, so the laboratory must retain the original files at
the declared references.

Submit the complete append-only envelope and authorization history to:

```text
POST /v1/projects/{project_id}/engineering/physical-validation/evidence
```

The request must include the current store revision and packet ID. HS rejects stale
packets, altered/omitted history, unrecognized gates, wrong procedures, mismatched
candidate hashes, missing required fields/media, and passed gates whose prerequisites
are absent.

## Authority boundary

Instrument capture creates measured evidence. It never creates broad physical
authority. The API keeps all global authority flags false and reports
`physical_correctness=UNPROVEN`; an applicable, revision/hash-scoped human ledger
decision can expose only its explicitly authorized operations.

For the published raw-document Astra v4 run, the generated packet is:

```text
project:              hs-astra-rawdoc-v4-20260913-1
source revision:      6
packet:               physical-validation-fdd10770454d7a84
candidate:            hs-astra-rawdoc-v4-20260913-1@b7c724e0561d4ec8
snapshot SHA-256:     b7c724e0561d4ec8ab21b7ad4e869256c5cca2f80416d1f07bd020164c152272
profile / gate count: spi_flash_adapter / 8
```

Those identifiers prove that the procedure was generated for the published canonical
state. They are not physical test results. On the host used to create this packet, no
bench supply, DMM, programmer, serial instrument, USBTMC instrument, or logic analyzer
was connected; no readings were fabricated or inferred.
