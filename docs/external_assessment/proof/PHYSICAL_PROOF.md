# Physical Validation Proof

**Status: PENDING**

A software workflow, simulated capture or CI job name is not physical proof.

## Required setup

- fresh checkout from the chosen frozen/proof revision;
- actual component identities and source provenance;
- normal Hardware-Splicer Engineering Package;
- exact candidate revision and artifact hashes preserved before physical work;
- no hidden local patch treated as repository evidence.

## Evidence to preserve where applicable

- component identities and datasheets/source provenance;
- generated schematic/netlist/BOM;
- DRC/ERC and relevant deterministic checks;
- fabricated or assembled artifact;
- powered-off continuity/resistance checks;
- supply rails;
- current draw;
- controlled power-up procedure;
- programming/flashing results;
- signals/waveforms where relevant;
- actuator/functional test;
- every observed failure;
- repairs and resulting revision changes;
- final outcome;
- operator identity;
- instrument/calibration metadata where appropriate;
- exact candidate revision and artifact hashes;
- raw evidence files and hashes.

## Canonical evidence path

Bench capture is only the collection surface. Durable proof should pass through:

1. `hardware_splicer.physical_evidence.v1`;
2. `hardware_splicer.physical_evidence_envelope.v1` with content-bound hashes;
3. audited persistence against exact `expected_revision`;
4. explicit human authorization where appropriate;
5. authorization-ledger revalidation against revision, artifact hashes, evidence kinds and scope.

Real capture evidence must explicitly declare `simulated: false`.

## Failure policy

Never delete a failure because it weakens the demo.

A correctly caught blocker, failed bring-up or revision-triggered revalidation can be stronger evidence of the system's safety architecture than an unrealistically perfect run.

## Completion record

- Project/case:
- Exact source revision:
- Candidate revision:
- Artifact hashes:
- Assembly/fabrication description:
- Instruments/calibration:
- Powered-off checks:
- Power-up evidence:
- Functional evidence:
- Failures:
- Repairs/revisions:
- Physical evidence record/envelope IDs:
- Authorization result:
- Final outcome:
- Claim change supported:

Until this is backed by real revision-bound artifacts, status remains `PENDING`.
