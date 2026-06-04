# Risk Register

| Source | Severity | Risk | Suggested Mitigation |
|---|---|---|---|
| dfm | warn | Tilt payload moment is high relative to servo; reduce payload/offset or use stronger servo. | Adjust geometry/clearances per DFM note and re-run bundle. |
| simulation | block | Tilt torque safety-factor≈1.10x (stall/reference). | Reduce acceleration/load, increase reduction ratio, or choose higher-torque actuator. |
