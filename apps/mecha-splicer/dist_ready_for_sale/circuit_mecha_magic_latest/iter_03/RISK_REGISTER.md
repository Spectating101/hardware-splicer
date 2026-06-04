# Risk Register

| Source | Severity | Risk | Suggested Mitigation |
|---|---|---|---|
| dfm | warn | Tilt payload moment is high relative to servo; reduce payload/offset or use stronger servo. | Adjust geometry/clearances per DFM note and re-run bundle. |
| simulation | block | Tilt torque safety-factor≈0.98x (stall/reference). | Reduce acceleration/load, increase reduction ratio, or choose higher-torque actuator. |
| safety | warn | Outdoor profile: validate ingress sealing, connector strain relief, and corrosion plan. | Add sealing strategy, glanded connectors, and corrosion-resistant hardware. |
