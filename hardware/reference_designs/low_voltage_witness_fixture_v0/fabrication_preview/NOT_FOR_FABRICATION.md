# REVIEW PREVIEW ONLY — NOT RELEASED FOR FABRICATION

The Gerber and Excellon files in this folder were exported by **KiCad 9.0.2** from the current native schematic/PCB design.

- They are suitable for verifying CAD generation and previewing geometry.
- They do **not** constitute authorization to manufacture, connect a power source, or use the apparatus as a calibrated reference.
- A qualified electrical review must first establish exact physical part compatibility, overcurrent protection, electrical isolation/grounding, connector ratings and shunt calibration, strain relief, and assembly documentation.
- A current BOM blocker is **Vishay 4-terminal WSK2512R0100FEA**, listed with zero Taiwan inventory. Substituting an ordinary 2-terminal 2512 resistor breaks the reference-sensing design.
- A cartridge fuse with proven appropriate DC interrupt rating has **not** been selected; the footprint is only for a holder.
- No measured prototype exists. Do not extrapolate the low-power traces/parts to 24V/120W.
- Full rationale: [BUILD_HOLD.md](../BUILD_HOLD.md).

Review native KiCad artifacts, source symbols, pin-net parity report, and assembly block list before sending manufacturing files to any board house.
