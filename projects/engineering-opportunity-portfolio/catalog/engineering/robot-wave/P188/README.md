# P188 · Camera calibration target tripod cradle

Size the jaw opening and pivot preload. A single effective friction surface balances gravity with an explicit torque factor. The drawing shows the open jaw in section and a separate effective-radius detail. Clamp force and friction are assumptions.

[Full-scale layout](layout.svg) · [Model outputs](results.json) · [Editable design inputs](../designs.json)

| Modeled quantity | Result |
|---|---|
| required torque Nm including factor | 0.3361 |
| torque margin Nm | 0.0439 |
| low preload 55N margin Nm | -0.1161 |
| max board gap margin mm | 0.45 |
| old gap margin mm | -0.55 |

**Physical acceptance.** Fit both board thicknesses and measure angular creep after 30 minutes under the maximum eccentric load.

**3D tooling.** [max thickness seat STEP](solids/max-thickness-seat.step), [original seat STEP](solids/original-seat.step). [Fit measurements from reopened solids](solids/fit.json).
