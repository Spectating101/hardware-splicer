# SPI physical-proof provider contact plan — 2026-09-23

Status: **send both / no fabrication authority**  
Tracking: `Spectating101/hardware-splicer#105`

## Current move

Send the same `PROVIDER_QUOTE_REQUEST.md` and the same frozen SPI package to both candidates in parallel. Do not select a provider before both have either replied or one has explicitly declined the required evidence workflow.

### JLCPCB

Public contact route:
- FCT service: Standard PCBA -> Advanced Options -> Function Test
- support email listed on the official FCT page: `support@jlcpcb.com`
- live support: Mon-Fri 24h, Sat 09:00-18:00 GMT+8

Current public commercial baseline:
- FCT engineering fee: approximately USD 16
- operator labor: approximately USD 8/hour
- first-board test video is typically returned for confirmation

What the public page does **not** establish:
- raw cold-measurement return;
- raw rail/current data;
- oscilloscope captures;
- exact board/revision traceability in the report;
- bounded SPI-log return;
- no-silent-rework/change-control behavior.

### PCBWay

Public contact route:
- service email: `service@pcbway.com`
- contact/sales form and online PCBA quote are available on the official site
- published email service hours: 09:00-23:00 daily GMT+8

Current public capability baseline:
- custom electrical + functional test;
- power-on testing;
- communication testing;
- power-consumption measurement;
- customer-supplied test plan, procedure and acceptance criteria;
- fixture/jig review;
- engineering support for workflow/report preparation.

What the public pages do **not** establish:
- exact NRE/labor cost for this campaign;
- exact raw-measurement format;
- oscilloscope evidence availability;
- exact board/revision traceability;
- bounded SPI-log return;
- no-silent-rework/change-control behavior.

## Selection principle

The first provider is **not** the cheapest quote. It is the first provider that can preserve the exact artifact and return enough raw evidence to satisfy the campaign.

Minimum acceptable response:

1. frozen package accepted or every required change enumerated;
2. R1 DNP / R4 DNP / JP1 open preserved;
3. raw unpowered measurements can be returned;
4. staged current-limited power is supported;
5. measured rail/current values can be returned;
6. 0x9F-only first transaction is supported;
7. observed JEDEC result can be returned;
8. board/revision identity survives into the report;
9. rework/substitution/procedure deviations are disclosed before evidence is accepted;
10. quote, MOQ, NRE/fixture/labor and lead time are explicit.

A provider that cannot satisfy items 1-9 is not eligible regardless of price.

## Contact order

**Parallel dual quote.** There is no evidence-based reason to serialize these inquiries.

- Send JLCPCB the neutral inquiry.
- Send PCBWay the identical neutral inquiry.
- Record replies in one `PROVIDER_REVIEW_RECORD` per provider.
- Compare only after both records are populated or a provider declines.

## Authority

This plan authorizes **contact and quotation/engineering review only**.

It does not authorize:
- fabrication;
- component purchase;
- assembly;
- power-on;
- functional test;
- rework;
- release.
