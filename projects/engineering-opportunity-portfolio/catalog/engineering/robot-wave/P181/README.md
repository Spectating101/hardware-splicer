# P181 · Robot teaching conveyor

Move the stop sensor upstream. A constant-speed approach, a fixed controller delay and constant braking bound the distance to the belt edge. The model omits belt slip and article sliding.

[Full-scale layout](layout.svg) · [Model outputs](results.json) · [Editable design inputs](../designs.json)

| Modeled quantity | Result |
|---|---|
| stop margin mm at requested speeds | 36.8, 27.6, 14.4 |
| old fast margin mm | -13.6 |

**Physical acceptance.** Run the 80 g article through 100 passes at each speed and measure the longest stop, including a slipping belt.
