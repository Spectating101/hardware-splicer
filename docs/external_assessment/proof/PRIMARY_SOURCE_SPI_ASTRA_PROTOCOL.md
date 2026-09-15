# Primary-source SPI Astra protocol

This experiment follows the structured-fact baseline with a document-grounded case. It
does not ask Astra to browse and it does not present PDF bytes as model-readable text.
Instead, three complete manufacturer documents are captured outside the model-visible
workspace, identified by byte hash, and represented by bounded page-addressed paraphrases.

The pinned case definition is
`src/hardware_splicer/data/astra_primary_source_spi.json`. The runtime case ID is
`spi-flash-adapter-primary-sources-v1`.

## Documents

- Winbond W25Q128JW, Revision G, July 29 2021.
- Texas Instruments TXU0304, SCES935A, Revision A.
- Texas Instruments SN74AXC4T245, SCES877B, Revision B.

The TI product symlinks are mutable. Reproduction therefore requires both the URL and the
captured SHA-256. A changed remote document is a new evidence revision, not an acceptable
substitute for the frozen case.

## What this closes

- manufacturer-document byte identity;
- page/section traceability for the claims shown to Astra;
- the W25Q128JW any-pin absolute-maximum boundary;
- the candidates' documented direction-control topology;
- preregistered expected conclusions, unresolved facts, forbidden claims, and metrics.

## What remains open

- independent human/EE signoff of the adjudication;
- the exact physical DUT marking, suffix, package and pinout;
- programmer identity and measured electrical behavior;
- a complete timing/load/power/protection design;
- schematic, ERC, PCB, DRC and physical bench evidence;
- raw-PDF interpretation by the model itself.

Passing this case can establish document-grounded engineering progress. It cannot establish
physical correctness, fabrication readiness, power-on readiness or human authorization.
