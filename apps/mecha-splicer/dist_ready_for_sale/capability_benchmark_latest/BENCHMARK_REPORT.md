# Capability Benchmark Report

- Cases: 24
- Passed: 22
- Failed: 2
- Pass rate: 91.7%
- Simulation severities: info=56, warn=2, block=2

## Top Fail Reasons
- `pt_02`: dfm:warn:Tilt payload moment is high relative to servo; reduce payload/offset or use stronger servo. || simulation:block:Tilt torque safety-factor≈1.10x (stall/reference).
- `pt_03`: dfm:warn:Tilt payload moment is high relative to servo; reduce payload/offset or use stronger servo. || simulation:block:Tilt torque safety-factor≈0.78x (stall/reference).
