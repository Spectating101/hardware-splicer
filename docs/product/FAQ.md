# Hardware Splicer FAQ

## Is this a finished physical product?

No. The frozen candidate is `PACKAGED_NOT_PHYSICAL`. The software, editable design, fabrication outputs, checks, and test handoff exist, but no board has been fabricated, assembled, powered, or measured.

## What does the AI agent control?

It may inspect evidence, propose work, call engineering tools, and assemble artifacts. It does not independently establish component identity, revision freshness, physical correctness, or permission to fabricate or power hardware.

## What has actually been reproduced?

The published remote-FCT package can be rebuilt deterministically from frozen commit `f892facd67c5124e2362860ebc999625afedc5d5`. A fresh rebuild matched published SHA-256 `6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd`, and its 24 outer ZIP members passed integrity testing.

## Do ERC and DRC prove that the circuit works?

No. They establish bounded CAD consistency. Simulation/model evidence, fabrication data, cold inspection, powered measurements, and application suitability are separate evidence layers.

## Has an external reviewer validated it?

No independent engineering review, manufacturer validation, user deployment, peer review, or production qualification is claimed.

## Why use the SPI-flash-adapter case?

It gives the evidence boundary a concrete test: a 3.3 V host must interact with a 1.8 V flash device without letting a plausible part match, stale revision, incomplete source, or unsupported physical assumption become permission to act.

## Can I fabricate it now?

The package is suitable for quotation and technical review. Fabrication, substitutions, shipping data, payment, controlled power-on, and physical test authority remain explicit human decisions.

## Is the project open source and open hardware?

The software is distributed under the repository's MIT license. Hardware-design and documentation scopes are being inventoried for an explicit license decision. No OSHWA certification or UID exists yet.

## Can I cite it?

Use the frozen release tag, commit, and package SHA today. A `CITATION.cff` draft exists, but no DOI should be cited until a real archive record is published.

## Does one model demonstration establish reliability?

No. One bounded primary-source Astra run exists as an existence demonstration. The unchanged ten-case cross-condition reliability evaluation remains pending.

## What would change the physical status?

Only revision-bound physical evidence: fabricated-unit identity, cold inspection, continuity, controlled power and OE bring-up, and the defined read-only identification test with raw evidence. That evidence would create a new version rather than rewrite the frozen candidate.
