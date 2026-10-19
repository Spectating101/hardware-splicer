# Hardware Splicer: unattended public-source investigation

Executed 2026-10-20 on Optiplex. This work responds to the operator's
explicit preference that source-checking and evaluation should be completed
automatically, not delegated back for manual inspection.

The bounded controller executed **seven distinct HTTP source checks**,
selected subsequent information-gathering actions, deduplicated the
repeated scanner listing, reassessed evidence coverage and proposed two
conservative engineering revisions. All actions were read-only.

## Live sources inspected

| Source | Family | Public record, not physical verification |
| --- | --- | --- |
| Ruten 22623851402690 | LS2208 barcode scanner | Seller cut cable, untested; asking NT$50; stock claim 1 |
| Zebra official LS2208 specs | Scanner family | USB, RS232, keyboard wedge; family power range 4.5 to 5.5 VDC |
| Ruten 21447795842755 | Epson LQ-680 | Broken/parts, asking NT$300, stock claim 5 |
| Ruten 22606139676402 | QNAP TS-219P II bare motherboard | Asking NT$650, stock claim 1 |
| Ruten 22613329448846 | Apple A1314 keyboard/mouse parts | Asking NT$500, stock claim 1 |
| Epson LQ-680 official manual index | Printer family | Confirms exact model's guide exists, not motor or driver values |
| QNAP TS-219P II official hardware specs | Complete NAS family | USB, Ethernet and eSATA options; NOT tested ports on stripped board |

Exact URLs:
- https://www.ruten.com.tw/item/22623851402690/
- https://www.zebra.com/us/en/products/spec-sheets/scanners/general-purpose-scanners/ls2208.html
- https://www.ruten.com.tw/item/21447795842755/
- https://www.ruten.com.tw/item/22606139676402/
- https://www.ruten.com.tw/item/22613329448846/
- https://support2.epson.net/manuals/english/sidm/lq_680/index.html
- https://www.qnap.com/en-in/product/ts-219p%20ii/specs/hardware

The archived JSON records exact model-match status, dated observed source
URLs, bounded SHA-256 response digests, advertised seller price and
stock claims, and manufacturer-family attributes. No actual sold price,
true inventory stock, specimen pinout, continuity or power test was
established.

## Changes to repair reasoning

The current seller title still describes a cut cable, while Zebra
documentation supports multiple host interface arrangements. The
controller therefore proposes a **conditional exact-model compatible
interface cable replacement route**, rather than unsourced wire-splicing
instructions. Internal electronic failure, interface mismatch and
configuration remain alternative hypotheses. Repair success is FALSE.

The ability to choose a next candidate approach from a retrieved source
is a real software advance, but a manufacturer specification is not a
diagnosis of a secondhand scanner.

## Changes to new-product splicing reasoning

HS generated a revised reference architecture:
1. LS2208 decoding is optional until the exact cable/decoder function is verified.
2. Epson mechanical indexing remains conditional on actual usable motor,
   driver, limit sensors, motion travel and physical geometry.
3. QNAP bare board is optional: the family has host ports, but the
   offered board lacks its original supply and verified OS/host interface.
   The already available authorized Linux computer is a fallback for
   software-only development.
4. Salvaged mouse switches can be ordinary UI buttons, **never treated
   as a safety-rated machine stop**. A separately verified emergency-stop
   architecture remains necessary.

All three planned cross-device connections are still BLOCKED. Listing
model matches are not component/electrical compatibility proof.

## How HS now executes this unattended

- autonomous_source_observer.py: strict canonical-URL allowlist,
  GET-only, bounded data and time budgets, title/model matching, status,
  redirects, HTML metadata, safe extraction and source hashes.
- autonomous_evidence_controller.py: capped conditional source actions,
  duplicate receipt caching, evidence updates, interface and function
  gap analysis, and explicit stop at the public-research frontier.
- autonomous_engineering_revision.py: conditional repair route plus
  novel-product functional architecture revisions.
- scripts/run_autonomous_donor_evidence.py: complete runnable CLI.
- SDK function investigate_public_donor_sources: agent-callable without
  direct manual source inspection.
- MCP tool hs_investigate_public_donors: accessible to connected agents
  with bundled default cases or explicitly provided mission intakes.

Reproduce with:

    PYTHONPATH=src python -m scripts.run_autonomous_donor_evidence --out /tmp/hs-autonomous-evidence

The dated machine-readable source and reasoning artifact is
AUTONOMOUS_PUBLIC_DONOR_INVESTIGATION_2026-10-20.json.

## Safety and completion boundaries

No purchase, seller message, device power-on, USB observation, physical
inspection, soldering, fabrication or motion control occurred. Manufacturer
pages identify family capabilities, not physical ports/pinouts in any
specific secondhand specimen. All source text is untrusted input and never
confers physical, repair or payment authority.

Automatic page-rechecking and engineering hypothesis revision are now
demonstrated. Independent field diagnosis, component electrical proof
and a working new machine remain unproven, and the controller stops rather
than asking the user to manually fabricate missing observations.
