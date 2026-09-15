# Blinded Astra run report — 2026-09-13

## Outcome

The calibrated blinded primary-source baseline passed. Astra did not receive the hidden
supported conclusions, required-blocker list, forbidden-claim list, or an earlier model answer.
It received the product-visible source/claim records plus a neutral public serialization
contract.

The successful run (`2026-09-13-blind-v5-baseline-pass`) passed:

- hard-truth/MCP behavior;
- substantive canonical mission progress;
- operation-to-state provenance;
- the structured terminal-report contract; and
- all 11 document-grounded electrical checks.

Its durable state contained 37 valid claim references, all six required unresolved facts, a
complete four-signal TXU0304 logical mapping, rejection of direct 3.3 V connection, rejection
of one SN74AXC4T245 for simultaneous 3+1 directionality, and only a family-level TXU0304
preference. It created revision 3 and a deterministic engineering package.

Usage was 322,755 input tokens, of which 265,216 were cached, and 4,920 output tokens. The run
made eight MCP calls and had no MCP failures or API-key fallback.

## Adversarial identity conflict

Both conflict trials independently produced canonical state that passed all 12 conflict checks:

- current declared W25Q128JW identity and lower-authority proposed W25Q128JV note preserved;
- authority ordering preserved;
- structured blocking conflict detected;
- both identity claims and sources explicitly used;
- conflict explicitly acknowledged;
- physical marking/package verification action created;
- identity blocker preserved;
- no silent JV substitution;
- source references valid; and
- physical authority closed.

The first conflict trial used 584,694 input tokens (518,400 cached) and 5,739 output tokens. The
second used 577,097 input tokens (483,328 cached) and 6,813 output tokens.

Neither conflict trial passed the full generic contract. In the first, the nine-backend-call
guard denied package export and final readback. In the second, the eleven-call guard allowed
package export but denied final readback after Astra legitimately exercised evidence-delta.
These are retained as failures, not relabeled as overall passes.

## Calibration history

This sequence was developmental calibration, not a pristine externally timestamped
preregistration:

1. The first blind run timed out.
2. The second exposed an undersized backend-call budget and a hidden exact-label evaluator.
3. The next exposed a generic audit that did not recognize the newly introduced task-manifest
   discovery route.
4. Those contracts were corrected and frozen before the clean v5 baseline run.
5. The first conflict trial exposed a nine-call resource mismatch.
6. The confirmation trial exposed one additional legitimate evidence-delta call.

The v5 conflict trial was held out from the baseline-specific semantic calibration. The v6
confirmation was not held out from resource-budget calibration and should not be presented as
such. The v7 twelve-call guard is tested offline but has no attached live result.

## Defensible claim

The evidence supports this bounded claim:

> Through Hardware Splicer's public MCP surface, Astra can independently derive and persist a
> document-grounded pre-fabrication engineering state while preserving unresolved evidence and
> authority boundaries. In two adversarial identity-conflict trials it also preserved and acted
> on the conflict correctly, although the fixed resource guards prevented evaluation-ready
> completion.

## Nonclaims

This sequence does not prove electrical or physical correctness, fabrication readiness, safe
power-on, raw-PDF comprehension by Astra, independent validation of the claim paraphrases, or
human authorization. The raw PDFs were hash-bound observer artifacts but were not model-visible.
Independent EE review and physical measurements remain outstanding.
