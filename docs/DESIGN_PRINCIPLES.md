# Hardware-Splicer — design principles

The original project statement, kept verbatim. The README now opens with a plain description;
this is the fuller account of the authority model behind it.

[![Splice Agent v1](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml/badge.svg)](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Auditable agentic hardware engineering under bounded physical authority.**

> **AI proposes → deterministic systems constrain → bench evidence decides → human authorizes.**

Bounded Astra projects can now cross into the audited bench workflow through a
revision/hash-bound [project physical-validation packet](docs/PROJECT_PHYSICAL_VALIDATION.md).
Real captures persist into the same canonical project history; simulated or public-web
captures, stale candidates, and out-of-order powered tests fail closed.

The frozen SPI case now also has a complete, independently checkable
[KiCad reference design](hardware/reference_designs/spi_flash_adapter_v1/README.md): exact BOM,
manufacturer-specific symbols, routed two-layer PCB, 18 testpoints, default-disabled translator,
independent chip-select biasing, removable rail-isolation links, continuous ground reference,
Gerber package, and a clean ERC/DRC/schematic-parity receipt. It remains deliberately
pre-fabrication and physically unproven.

Hardware-Splicer lets a general-purpose AI agent perform bounded hardware-engineering work while deterministic constraints, provenance-bearing evidence, exact revision state and scoped human authority remain independently authoritative.

It is **not** a claim that an LLM can safely replace a hardware engineer. The design goal is narrower and more defensible:

> **When the AI is uncertain or wrong, that uncertainty should not silently acquire physical authority.**
