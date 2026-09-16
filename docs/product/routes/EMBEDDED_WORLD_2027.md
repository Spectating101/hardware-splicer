# Embedded World Conference 2027 — prepared Hardware Splicer packet

**Route state:** `PREPARED_TO_ACCOUNT_AND_HUMAN_COMMITMENT_GATES`  
**Official deadline:** 2026-09-28, firm  
**Event:** 2027-03-16 through 2027-03-18, Nuremberg, Germany  
**Required topic:** `10.09 Eclipse Foundation`  
**Submission language:** English

## Live portal reconnaissance — 2026-09-17

Official submission entry:

```text
https://call-for-papers.componeers.net/frontend/index.php?sub=383
```

The public instructions state:

- title and topic are required;
- abstract is limited to 1,500 characters;
- presenter CV is limited to 300 characters;
- presentation slot is 30 minutes;
- slides are due 2027-03-01 if accepted;
- final paper is due 2027-03-08 if accepted and the author chooses to publish it;
- English is mandatory;
- marketing-oriented talks and pure product descriptions are rejected;
- one speaker only;
- the presenter guarantees physical presence;
- acceptance considers audience relevance, technical soundness, and absence of marketing content;
- originality/no-concurrent-presentation requirements require human attestation.

The portal requires an account. Public account fields include username, password/confirmation, email/confirmation, form of address, given/family name, optional academic titles, institution, department, occupation, street, postal code, location, optional phone, and country.

No account was created and no personal data was entered during reconnaissance.

## Proposed title

**Evidence-Gated AI Agents for Open-Source Hardware Engineering**

## Abstract — portal-ready draft

AI agents can accelerate hardware engineering, but a plausible answer can reach fabrication or power-on before component identity, evidence provenance, revision state, or physical behavior is established. This talk presents Hardware Splicer, an open-source engineering workbench that lets a general-purpose agent propose and assemble work while deterministic checks, revision-bound evidence, and explicit human authorization remain independently authoritative. A frozen SPI-flash-adapter case shows the boundary in practice: source evidence, a derived virtual lab, manufacturer-model checks, KiCad ERC/DRC, and fabrication outputs can be inspected and replayed, yet the system continues to report PACKAGED_NOT_PHYSICAL until real measurements exist. The talk demonstrates fail-closed handling of stale revisions, incomplete sources, tool failures, and attempted authority escalation. It focuses on design choices, failure modes, reproducibility, and what open-source embedded teams can reuse when integrating AI agents without treating model confidence as engineering proof.

## Presenter CV — portal-ready draft

Christopher Ongko is a master's student and research assistant at Yuan Ze University. He develops auditable research and engineering systems that separate AI-generated proposals from deterministic evidence, revision state, and human authority.

## Audience takeaways

1. A concrete architecture for separating agent proposals from engineering evidence and physical authority.
2. Failure modes that ordinary “AI generated a design” demonstrations hide, including stale revisions, incomplete sources, and tool failures.
3. A reusable open workflow for packaging CAD, verification receipts, manufacturing artifacts, and physical-test handoffs without overstating maturity.

## Thirty-minute structure

- 4 minutes — why hardware mistakes create a distinct authority problem;
- 6 minutes — architecture and evidence layers;
- 8 minutes — frozen SPI case and open-source toolchain;
- 6 minutes — fail-closed examples and tamper/stale-revision behavior;
- 4 minutes — physical handoff and `PACKAGED_NOT_PHYSICAL` boundary;
- 2 minutes — reusable lessons and transition to round-table questions.

## Evidence references

- frozen release and checksum;
- current product package under `docs/product/`;
- SPI reference-design README and verification receipt;
- external claims/nonclaims and evidence ledger;
- remote-FCT package and return contract;
- frozen research protocol.

## Human-required information and commitments

- preferred account username and password creation;
- preferred email identity;
- form of address;
- public institution, department, occupation, and postal address fields;
- confirmation that Christopher Ongko is the sole presenter;
- confirmation of willingness and ability to be physically present in Nuremberg if accepted;
- originality/concurrent-submission attestation after checking all active venue plans;
- privacy/terms acceptance;
- final submission.

Do not submit until physical-attendance feasibility and originality obligations are explicitly accepted.
