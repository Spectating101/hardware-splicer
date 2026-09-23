# Donor, salvage and remanufacture supply routes

Hardware Splicer Product Factory is not limited to a clean-sheet PCB assembled from newly purchased components.

A Product Factory run may use:

- `NEW_BUILD` — conventional new components/PCB/assembly;
- `DONOR_RETROFIT` — keep most of an existing device and modify its function;
- `MODULE_REUSE` — reuse an intact tested subassembly;
- `COMPONENT_HARVEST` — recover individual parts;
- `HYBRID` — combine donor hardware with a new HS-designed carrier/protection/control layer.

The preference order is not ideological. It is empirical.

## Why whole-module reuse comes before component harvesting

A cheap used device is not a cheap BOM.

The factory therefore prices:

```text
acquisition
+ inbound logistics
+ inspection of every donor
+ yield loss
+ reject disposal - residual recovery credit
+ rework labor
+ new material
+ final QA
+ warranty reserve
-------------------------------------------
effective COGS per sellable unit
```

A donor route must beat the all-new reference by a declared savings floor *after* those costs.

This means a $10 donor unit with poor yield or 90 minutes of desoldering/test work can correctly lose to a $30 clean new build.

## Identity and variability

Every donor route must preserve at minimum:

- exact donor model or approved variant;
- board/revision identity where relevant;
- a variant-specific acceptance test;
- observed usable-yield evidence;
- observed supply depth relative to the intended lot.

A marketplace title such as "old router" or "used laptop board" is not a stable engineering identity.

## Safety boundary

The v1 economics gate deliberately fails closed for routes that require:

- opening/modifying mains-voltage sections;
- modifying lithium battery packs;
- unknown contamination/hazard state.

Those routes require a separate qualified safety process before Product Factory may treat them as ordinary supply.

Reusing an intact certified external power adapter can be modeled as module reuse, but its certification applicability and condition still require review.

## What HS adds

Donor economics become especially interesting when HS can do more than salvage components:

```text
abundant existing artifact
        |
 reverse/identify interfaces
        |
retain valuable working subsystem
        |
custom carrier / adapter / protection
        |
firmware / mechanical transformation
        |
variant-specific verification
        |
new bounded product
```

That is closer to **remanufacturing by splicing** than to parts scavenging.

The Product Factory should therefore compare clean-sheet, donor-retrofit and hybrid architectures for the same product objective whenever an abundant donor population exists.
