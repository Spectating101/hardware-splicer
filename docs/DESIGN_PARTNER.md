# Design partner program — Hardware-Splicer

**Quota:** **3 slots** this quarter (then pause and deliver).  
**Vertical focus:** salvage / donor / repair-café / robot bring-up first; prototype labs second.  
**Doctrine:** [`CONVERSION_DOCTRINE.md`](CONVERSION_DOCTRINE.md)

---

## Who qualifies

You have a **real next board or donor** within ~30 days, and can run Linux or WSL2 with KiCad 9+.

| Fit | Not a fit |
|-----|-----------|
| Repair café / robot lab / salvage bring-up | “Curious about AI PCB” with no board |
| 2–15 person prototype / EMS-adjacent team | Need Altium-class editor as the product |
| Uni embedded lab with scheduled power-on | Want multi-tenant SaaS |

---

## What you get

| Deliverable | Notes |
|-------------|--------|
| Splice Sprint | Intake → compile → `PROJECT_PACKAGE` + gate review ([`OFFER_SPLICE_BENCH_KIT_v1.md`](OFFER_SPLICE_BENCH_KIT_v1.md)) |
| Partner pricing | Lower half of published band **or** case-rights trade for slot #1 |
| Optional | Architon `rv` scan after compose ([`integrations/ARCHITON_GATE.md`](integrations/ARCHITON_GATE.md)) |

## What we ask

- Redacted case note permission (board identity can stay private)
- One quote we can use publicly
- One intro to a peer lab when the Sprint goes well
- Honest feedback via Issues (`[Design partner]` / dry-run templates)

---

## How to apply

**Preferred:** GitHub Issue titled:

```text
[Design partner] <lab or project name>
```

Include:

1. Segment (repair café / prototype / uni lab)  
2. Board or donor description (photos OK)  
3. Target intake week  
4. Machine: Linux / WSL2 + KiCad version  
5. Pricing preference: paid Sprint vs case-rights  

**Or:** contact the maintainer via the GitHub profile.

---

## Slots tracker

| Slot | Status | Partner | Target week |
|------|--------|---------|-------------|
| 1 | **OPEN** | — | — |
| 2 | **OPEN** | — | — |
| 3 | **OPEN** | — | — |

Maintainer updates this table when a slot is held or filled.

---

## Liability (same as offer)

Vendor provides software-assisted compile artifacts and gate workflow. **You** own donor condition, physical wiring, and final power-on authorization. See [`SUPPORT_AND_LIABILITY_v1.md`](SUPPORT_AND_LIABILITY_v1.md).
