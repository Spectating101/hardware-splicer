# Submission Claim Update Protocol

When new external evidence appears, update submission packets from the canonical evidence state rather than editing each venue document ad hoc.

## Trigger events

- live external-model corpus run completes;
- fresh SPI physical proof completes;
- independent human-operator protocol completes;
- external partner/industrial case produces measurable evidence.

## Update order

1. verify the exact artifact/revision/result;
2. update `../EVIDENCE_LEDGER.md`;
3. update `../CLAIMS_AND_NONCLAIMS.md`;
4. update `../README.md` / root evaluator summary if the claim ceiling changed;
5. project the changed state into active submission packets;
6. do not rewrite frozen cases, thresholds, or earlier failures to improve presentation.

## Rule

A venue packet is a view of the evidence core, not an independent truth source.
