# SPI Physical Proof Operator Packet

Status: **pre-fabrication / quote-and-review only**  
Tracking: `Spectating101/hardware-splicer#105`  
Campaign manifest: `hardware/reference_designs/spi_flash_adapter_v1/physical_proof_campaign_v1.json`

This packet converts the frozen SPI reference design into an externally executable review and physical-proof sequence. It does **not** authorize fabrication, assembly acceptance, power-on, functional test, or release.

## Immutable subject

Use only the campaign manifest's canonical source identity unless a real evaluator/DFM/physical finding forces a successor revision.

A provider may suggest changes. Suggestions are findings, not silent edits. If a finding changes the schematic, PCB, BOM, stackup, assembly state, test points, power sequence, or bounded test procedure, stop and create a successor revision. Re-run all affected software evidence and invalidate any physical evidence that no longer applies.

## Provider / independent reviewer request

The first external contact is **quotation + engineering review**, not an order authorization.

Ask the reviewer/provider to return written answers to these questions:

1. Can you ingest and quote the exact supplied fabrication/assembly package without modifying design files silently?
2. What DFM, DFA, component-availability, footprint, drill, clearance, stackup, assembly, or panelization concerns do you identify?
3. Can the initial assembly preserve `R1=DNP`, `R4=DNP`, and `JP1=open` exactly as specified?
4. Can you perform or support unpowered continuity/resistance/isolation checks before any powered test? If yes, what raw results can be returned?
5. Can you perform staged current-limited power with the campaign's rail checks and return measured values rather than only pass/fail labels?
6. Can you execute a bounded read-only SPI JEDEC-ID transaction (`0x9F`, mode 0, 5 MHz) after the preceding gates pass, without issuing program/erase/status-write/reset commands?
7. What evidence can you return: measurement table, raw captures, photographs, test logs, timestamps, board/lot identifiers, operator/instrument identifiers, waveform files, or video?
8. What are the quotation, NRE/fixture charges, minimum quantity, expected lead time, test-engineering assumptions, and any steps that require customer approval?

Do not interpret a positive answer as proof that the service was executed or that the board is correct.

## Required provider return envelope

For every external review, quotation, DFM note, assembly result, or test result, preserve:

- provider / reviewer identity;
- date/time received;
- exact campaign and package revision referenced;
- exact files or package hash reviewed if available;
- finding category;
- raw provider wording or attached artifact reference;
- whether the finding changes design, manufacturing, assembly, or test assumptions;
- whether a successor revision is required;
- human disposition: `accept`, `revise`, `reject`, or `needs_followup`.

A provider's own pass/fail label never grants Hardware-Splicer authority automatically.

## Bench progression

### Gate P0 — independent review

Before fabrication decision:

- verify exact package and checksum;
- collect at least one independent EE/DFM/provider review;
- bind findings to the exact package/revision;
- resolve whether any finding requires a successor revision.

Output: a review record only. `fabrication_authorized` remains false.

### Gate P1 — fabrication decision

A human explicitly reviews provider, price, terms, DFM findings, package identity, and any required changes.

If approved, record all of:

- provider;
- exact package/revision;
- quantity/assembly variant;
- accepted provider assumptions;
- explicit human fabrication authorization;
- timestamp and authorizing person.

No purchase-page click, quote acceptance, or provider acknowledgement may be interpreted as authority unless the explicit HS authority record exists.

### Gate P2 — assembly identity

When physical boards exist, assign/record a physical board identity before electrical evidence is attached.

At minimum record:

- board ID / serial or locally assigned unique identifier;
- source revision/package;
- board/assembly revision markings;
- `R1` state;
- `R4` state;
- `JP1` state;
- flash marking/package;
- regulator/translator identities where visible/available;
- component orientation observations;
- photographs or provider inspection records where available.

Visual inspection proves identity/assembly observations only, not electrical correctness.

### Gate P3 — cold checks

No powered evidence is valid until the configured cold checks are completed against the same board identity.

Record raw values, units, operator, instrument identity where available, and `simulated:false` for real measurements.

At minimum cover the revision-bound short/resistance/continuity/isolation/polarity checks plus OE pull-down and CS-domain pull-up expectations from the canonical procedure.

Any relevant repair or component substitution creates a new physical/evidence state and may invalidate prior measurements.

### Gate P4 — controlled power

Power-on requires explicit authority after cold checks. Preserve current-limit settings and connection topology.

Capture the campaign-required rails and power behavior, including 3V3, 1V8/DUT_1V8, current/limit state, ramp/overshoot/timing where the procedure requires them.

A DC voltage reading alone must not be promoted into evidence for transient/ramp behavior.

### Gate P5 — bounded functional transaction

Only after the power gate passes and functional-test authority is explicit:

- preserve the prescribed JP1/OE/CS sequence;
- run only SPI mode 0 at 5 MHz;
- issue read-only `0x9F`;
- expected JEDEC ID: `EF6018`;
- preserve raw capture and observed result;
- preserve relevant current/temperature/supply observations.

A mismatch is a result to preserve, not a reason to rewrite history. Stop, bind the failure to the exact board/revision, and open a successor/repair investigation.

### Gate P6 — evidence closure

The final chain must be independently inspectable:

`source revision -> fabrication artifact -> board identity -> cold evidence -> power evidence -> functional evidence/failure -> human authority decision`

Only after this exists may paper/external-proof language be updated, and only to the exact claim scope supported by the captured evidence.

## Fail-closed rules

Stop progression when any of the following occurs:

- the reviewed/fabricated package cannot be tied to the canonical revision;
- provider changes are ambiguous or unrecorded;
- physical evidence lacks explicit real-vs-simulated state;
- board identity is unknown;
- a prerequisite gate is incomplete;
- a repair/substitution makes prior evidence stale;
- raw values/captures required by the procedure are replaced only by unsupported summary claims;
- requested action exceeds the explicit human authority scope.

A failed board with complete lineage is a valid campaign outcome. An apparently successful board with unbound or stale evidence is not campaign closure.
