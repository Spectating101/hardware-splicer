# Hardware Splicer packaging QA — 2026-09-17

## Result

**Current package state:** `READY_FOR_INTERNAL_REVIEW`  
**External publication/submission:** not authorized  
**Physical state:** `PACKAGED_NOT_PHYSICAL`

The new product front door is internally coherent and is bound to the frozen release. Several older Q3 documents remain historical evidence sources and must not be used as the current first page without the new product package.

## Checks completed

### Authority and download identity

- frozen commit is stated consistently as `f892facd67c5124e2362860ebc999625afedc5d5`;
- release tag and URL resolve to the published prerelease;
- published ZIP identity is stated as `6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd`;
- a fresh deterministic rebuild produced the same SHA-256;
- all 24 outer ZIP members passed integrity testing;
- rebuild audit reports zero blockers and retains `physical_authority_granted=false` and `physical_correctness=UNPROVEN`.

### Product comprehension

The product package now answers, on its first screen:

- what Hardware Splicer is;
- why hardware needs an evidence/authority boundary;
- what concrete SPI artifact exists;
- what is proven;
- what remains unproven;
- how an evaluator can inspect and reproduce it;
- which view applies to an engineer, reviewer, provider, researcher, or conference evaluator.

### Route packaging

- Embedded World official public requirements were inspected live;
- the proposed abstract is 1,074 characters against a 1,500-character limit;
- the proposed CV is 243 characters against a 300-character limit;
- account, address, physical-presence, originality, terms, and final-submit gates are explicit;
- no account was created and no portal data was entered.

### Research/evaluation

- the existing core research protocol is retained rather than rewritten;
- the execution freeze binds it to the frozen release;
- corpus validation/listing succeeds for all ten named cases without a provider call;
- no paid model run or result claim was created.

### Media

- the selected hero visual is generated from the frozen canonical design package, not an unrelated golden-real case;
- hero rendering SHA-256 is `bf7685d26c956bcc1886715301d19885b4b4357612ce63f269079d1e39025bc0`;
- older screenshots showing `production_repair`, `power allowed`, `authority 1.00`, or the SparkFun CH340C case are deliberately excluded from the SPI product front door because they could imply the wrong candidate or physical state;
- the primary demonstration has a complete offline path.

### Licensing and archive

- repository-wide third-party concentrations are identified;
- vendor datasheet PDFs are excluded from the proposed initial archive;
- citation metadata is drafted without inventing an ORCID, DOI, OSHWA UID, or license decision;
- hardware and documentation license choices remain explicit human gates.

## Reconciled inconsistencies

### Old package authority

The Q3 assessment README still identifies historical branch and checkpoint SHAs. Both Q3 entry documents now point to `docs/product/README.md` as the current front door instead of silently presenting those checkpoints as current authority.

### Live-model wording

Historical documents correctly state that the full unchanged ten-case live-model evaluation remains pending. Newer release material also records one bounded primary-source Astra run as an existence demonstration. The current package preserves both facts:

- one bounded primary-source agent demonstration exists;
- full cross-case/cross-condition reliability remains unproven.

### Software versus physical state

The package consistently separates green CI, deterministic CAD checks, model/simulation evidence, fabrication packaging, and physical measurement. None is allowed to inherit the authority of the next layer.

## Remaining internal-review decisions

1. Confirm the public creator name and whether to add an ORCID.
2. Approve hardware and documentation license scopes.
3. Confirm the public affiliation/occupation wording used for external routes.
4. Decide whether Nuremberg physical attendance is feasible before Embedded World submission.
5. Decide whether provider quotations may be requested and establish a maximum budget.
6. Approve archive publication only after the final include/exclude manifest is reviewed.

## Acceptance rule

This package may be used to prepare external forms. It does not authorize public archive publication, relicensing, provider contact, procurement, travel commitment, legal/originality attestations, or final submission.
