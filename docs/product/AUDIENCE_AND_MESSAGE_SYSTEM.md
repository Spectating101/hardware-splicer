# Hardware Splicer audience and message system

This file is the copy source for product pages, demonstrations, applications, talks, provider handoffs, and research packages. Route-specific copy may change emphasis and length; it may not change the evidence state.

## Category

Primary category:

> **Evidence-gated agentic hardware engineering workbench**

Concrete category for audiences unfamiliar with agent governance:

> **An open hardware-engineering workbench where AI can propose work but deterministic checks and physical evidence decide what is trusted.**

## Core value proposition

Hardware Splicer helps an AI agent make useful progress on hardware work without letting plausible language silently become verified component identity, fabrication readiness, physical evidence, or permission to power hardware.

## Thirty-second explanation

Hardware Splicer is an open workbench for AI-assisted hardware engineering. The agent can inspect sources, propose changes, use CAD and testing tools, and prepare a manufacturing package. Exact revisions, deterministic checks, provenance-bearing evidence, and explicit human authorization remain outside the model. The frozen SPI-flash-adapter case is packaged and reproducible, but still clearly reports that no board has been fabricated or physically tested.

## Two-minute explanation

General-purpose AI can produce convincing engineering output before the underlying component identity, voltage compatibility, evidence source, revision, or physical behavior is known. In software, that may cause a bad answer. In hardware, it may become a fabricated or powered mistake.

Hardware Splicer separates model reasoning from engineering authority. An agent operates the project through normal API/MCP/tool surfaces. Deterministic systems preserve exact project revisions, component and source identity, electrical constraints, evidence provenance, and the difference between simulated and real measurements. Consequential steps remain blocked until their required evidence and human authorization exist.

The public SPI-flash-adapter case includes editable KiCad sources, a routed PCB, BOM, placement and fabrication data, verification receipts, bounded read-only host-test software, and a provider-neutral FCT package. The package is deterministic and independently inspectable. Its current state remains `PACKAGED_NOT_PHYSICAL`: software and CAD checks are not presented as physical correctness.

## Ten-minute narrative spine

1. Begin with the failure: fluent agent output can outrun evidence.
2. Show the four separated objects: proposal, deterministic state, evidence, authority.
3. Introduce the SPI case and its conflicting voltage domains.
4. Show source and component identities.
5. Show the derived virtual lab and manufacturer-model boundary.
6. Show editable KiCad design and deterministic ERC/DRC/parity receipts.
7. Show the fabrication/FCT package and evidence-return contract.
8. Tamper with or stale a copied evidence object and show rejection.
9. Show `PACKAGED_NOT_PHYSICAL` remaining closed.
10. End with what must happen next: independent review, fabrication, cold checks, controlled power, and read-only `0x9F` evidence.

## Audience matrix

| Audience | Lead with | Show | Ask | Avoid |
|---|---|---|---|---|
| Open-source user | reproducibility and inspectability | quickstart, source, release hash, license map | clone, replay, report friction | governance jargon |
| Embedded engineer | concrete SPI failure boundary | voltage domains, CS/OE controls, timing, CAD receipts | inspect assumptions and procedure | generic AI claims |
| Hardware reviewer | exact candidate and unresolved physical risks | schematic, PCB, BOM, DNP state, acceptance plan | identify defects before fabrication | claiming CAD checks prove hardware |
| Fabricator/FCT provider | bounded deliverable and test request | manufacturing archive, substitutions, test sequence, return schema | quote/capability response | project philosophy |
| Conference reviewer | audience problem and reusable engineering lesson | one case, failure modes, open tools, demo | select a technical talk/demo | product pitch language |
| Research reviewer | intervention and measurable outcomes | frozen protocol, conditions, scenarios, metrics, traces | evaluate method/results | treating one demo as reliability |
| Resource program | bounded experiment and requested resource | run matrix, cost, safety boundary, outputs | credits/access for the experiment | implying provider endorsement |

## Short copy bank

### 100 characters

AI-assisted hardware engineering where deterministic evidence—not model confidence—controls authority.

### 280 characters

Hardware Splicer lets AI agents perform bounded hardware-engineering work while exact revisions, deterministic checks, provenance-bearing evidence, and explicit human authorization remain independently authoritative. The public SPI candidate is packaged but not physically validated.

### 75-word description

Hardware Splicer is an open workbench for evidence-gated agentic hardware engineering. General-purpose agents can inspect sources, propose changes, use engineering tools, and prepare artifacts, while exact project revisions, deterministic constraints, provenance-bearing evidence, and human authority remain outside the model. Its frozen SPI-flash-adapter case includes editable CAD, fabrication outputs, verification receipts, and a remote-FCT handoff. It remains explicitly `PACKAGED_NOT_PHYSICAL` until real revision-bound measurements exist.

## Language rules

Prefer:

- “The agent proposed…”
- “The deterministic check accepted/rejected…”
- “The evidence supports…”
- “The human authorized…”
- “No physical measurement exists yet.”

Avoid:

- “The AI verified the hardware.”
- “Production-ready.”
- “Autonomous hardware certification.”
- “Safe hardware automatically.”
- “Industry validated.”
- “Open-hardware certified” before an OSHWA UID exists.

Internal terms such as FIRE, G4, conversion, authority gate, and canonicalization belong in Gauntlet—not in outward-facing form copy unless independently natural for the audience.
