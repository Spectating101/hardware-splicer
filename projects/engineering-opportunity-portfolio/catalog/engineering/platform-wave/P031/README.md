# P031 · Shallow-water tethered camera ROV

The first design question for a pond camera is whether the fully equipped vehicle will return to the surface in still freshwater when thrust stops. Across 64 corner cases, the two smaller assumed floats gave a worst net reserve equivalent to **−210.58 g**. The revised 220 × 40 × 25 mm pair gave **+42.66 g** at the worst corner. The high-buoyancy corner leaves 179.56 g equivalent downward thrust from the assumed 420 g budget.

The model counts only displaced, sealed volume and external foam. Its input mass includes the foam, battery, mounts and camera. The tether load is the effective downward load transmitted to the vehicle. Weights, flotation tolerances, absorbed water and actual thrust have not been measured. An extra 43 g of submerged load at the worst corner consumes the entire revised reserve.

This is a hydrostatic screen for a shallow, contained tank. Stability, sealing, pressure response, propulsion, dynamic tether forces, video and recovery need separate evidence. The catalog's full-machine costing covers those subsystems. We have no basis to assign it the commercial comparator's depth rating.

[Edit the mass and float assumptions](../cases.json) · [Inspect every corner case](buoyancy.csv) · [Results](results.json) · [Replay](../verify.py)
