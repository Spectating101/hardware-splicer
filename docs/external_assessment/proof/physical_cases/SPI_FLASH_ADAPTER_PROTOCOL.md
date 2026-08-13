# SPI Flash Adapter — Physical-Proof Protocol

**Status: PREPARED / NOT EXECUTED**  
**Parent unseen-case head:** `0004b644b8d6e2632fd8d87a24c6d1fec9953626`

This protocol defines how the fresh SPI-flash case can become a real physical-evidence case **after** the source-blind engineering run. It deliberately does not prescribe a translator architecture, pin mapping, regulator choice, PCB topology, or expected answer.

The physical case must validate the actual candidate produced through the normal Hardware-Splicer path rather than retrofitting the unseen case to a hand-authored solution.

## 1. Contamination rule

Before the live/unseen engineering result is frozen:

- do not add a preferred translator to the experiment;
- do not add a golden schematic or expected netlist;
- do not replace unresolved package/pinout facts with assumptions;
- do not tune the challenge cases to make a particular model answer succeed;
- do not use this protocol as hidden operator context.

This document is an **outer physical-evaluation protocol**, not an embedded-agent answer key.

## 2. Entry gate

Physical work may begin only from a named candidate revision with a preserved Engineering Package.

Record:

- source repository commit;
- project ID;
- candidate revision;
- Engineering Package path/ID;
- schematic/netlist/BOM hashes as applicable;
- exact component identities actually intended for assembly;
- unresolved items remaining at the candidate boundary.

If the candidate still lacks the exact physical DUT package/orderable identity needed for pinout verification, physical authority stays closed until the actual part is identified from defensible evidence.

## 3. Identity/evidence gate

For every component whose identity affects electrical safety or pin mapping, preserve:

- manufacturer;
- exact orderable part number or an explicit unresolved state;
- package;
- authoritative source locator/version;
- captured source hash or evidence-envelope reference;
- relevant limits/requirements actually used by the candidate;
- any source conflict or stale source that was rejected/superseded.

A family-level name is not automatically sufficient for package-specific pin mapping.

## 4. Pre-assembly deterministic gate

Run the normal repository/toolchain checks applicable to the candidate and persist their artifacts. Examples may include:

- schematic/netlist consistency;
- ERC/DRC where applicable;
- BOM/part identity checks;
- interface/voltage constraints;
- required protection/translation evidence;
- unresolved blocker report.

A green software gate does not open physical authority by itself.

## 5. Assembly record

If/when an artifact is assembled or fabricated, create a physical assembly record containing:

- candidate revision and design-artifact hashes;
- board/fixture identifier;
- actual installed component markings/orderable parts;
- substitutions, if any;
- assembly date;
- operator;
- photographs or equivalent traceable artifact references;
- deviations from the candidate BOM/netlist.

Any material substitution that changes identity/electrical assumptions requires revalidation before power-on.

## 6. Powered-off checks

Before applying power, record measurements appropriate to the generated candidate. At minimum consider:

- supply-to-ground resistance / short check;
- continuity of critical ground paths;
- continuity of DUT supply path;
- connector orientation and pin mapping verification;
- absence of unintended shorts between host-side and DUT-side supply domains;
- translator direction/control wiring against the candidate design;
- any candidate-specific protection paths.

The protocol does not specify expected numeric values unless the candidate/evidence package itself provides defensible limits. Raw readings, units, instrument, operator and method must be recorded.

## 7. Controlled power-up gate

Only after powered-off evidence is accepted for the exact candidate:

1. keep the DUT/fixture in the candidate-defined safe initial state;
2. use current-limited power where appropriate;
3. start from the candidate-defined controlled supply procedure;
4. record supply voltage(s), current draw and unexpected thermal/behavioral observations;
5. stop on a blocker, over-current event, unexpected rail value, smoke/odor/heat, or other unsafe observation;
6. preserve the failure rather than retrying silently.

This protocol intentionally does not invent a current limit or voltage tolerance. Those must come from the candidate's defensible engineering evidence and the actual instruments/setup.

## 8. Signal/function evidence

After safe static bring-up, test only functions that the candidate actually claims and for which authority is open. Possible evidence for an SPI programming/validation adapter includes:

- idle rail levels;
- host-side and DUT-side logic levels;
- SCLK/CS/data behavior where measurable;
- read-identification transaction or another non-destructive functional operation;
- programming/readback only if the candidate/procedure explicitly permits it;
- observed timing/logic anomalies;
- translator direction/control behavior.

Do not invent acceptance thresholds that are absent from authoritative evidence.

## 9. Failure / repair loop

For every failure:

- preserve raw evidence;
- identify the candidate revision on which it occurred;
- record the diagnosed cause as proposal vs verified fact;
- create a new candidate revision for any design-affecting repair;
- invalidate/revalidate evidence and authorization across the changed artifact boundary;
- rerun the relevant deterministic and physical gates.

A repaired artifact is not the same evidence object as the failed revision.

## 10. Canonical evidence persistence

Bench observations are collection surfaces only. Durable physical proof should be represented through the existing canonical chain:

```text
raw bench evidence
      ↓
PhysicalEvidenceRecord
      ↓
PhysicalEvidenceEnvelope + content hashes
      ↓
exact expected_revision audited persistence
      ↓
human AuthorizationDecision (if appropriate)
      ↓
authorization ledger + revalidation
```

Real capture evidence must explicitly declare `simulated: false`.

## 11. Completion bar

This case becomes **physical proof** only when the evidence package can answer all of these without narrative substitution:

- What exact candidate revision was built/tested?
- Which exact design artifacts and component identities were involved?
- What powered-off checks were actually performed?
- What power-up measurements were actually observed?
- What functional behavior was actually observed?
- What failed, if anything?
- What changed after repair, if anything?
- Which evidence files/hashes bind those observations to the candidate?
- What human authorization, if any, was issued and for what scope?

Until those are artifact-backed, the status remains **PREPARED / NOT EXECUTED**.
