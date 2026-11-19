# DC measurement station

See station-design.json for calculations, checks and remaining physical work; parts.csv and wiring.csv are the assembly interface.

The source must be externally isolated. INA228 itself and a direct I2C host connection provide no isolation.
This is an unbuilt candidate equipment design. The parts, thermal behavior, wiring and calibration have not been verified.
The logger records actual triggered conversions when manually run on a configured Linux I2C bus. It does not switch or disconnect load power.

Primary component source: https://www.ti.com/lit/ds/symlink/ina228.pdf
