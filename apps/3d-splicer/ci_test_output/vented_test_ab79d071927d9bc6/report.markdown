# Optimization Report: vented_test

**Specification ID**: vented_test
**Total Iterations**: 2
**Total Time**: 0.2s
**Success**: No

## Functional Requirements

- **thermal_clearance**: F1

## Final Results

**Overall Score**: 0.691
**All Tests Passed**: False

### Test Results

- **envelope_constraint**: ✅ PASS (score: 1.000)
  - Envelope: 68.0x48.0x12.0mm (limit: 70.0x50.0x15.0mm)
- **board_clearance**: ✅ PASS (score: 1.000)
  - Board clearance: 4.00mm (target: 1.0mm)
- **mount_accessibility_0**: ✅ PASS (score: 1.000)
  - Mount 0 accessibility: 14.00mm clearance (required: 2.50mm)
- **mount_accessibility_1**: ❌ FAIL (score: 0.000)
  - Mount 1 accessibility: -16.00mm clearance (required: 2.50mm)
- **mesh_watertight**: ✅ PASS (score: 1.000)
  - Mesh is watertight
- **mesh_manifold**: ✅ PASS (score: 1.000)
  - Mesh is manifold
- **mesh_degenerate**: ✅ PASS (score: 1.000)
  - Degenerate faces: 0
- **overhang_angles**: ❌ FAIL (score: 0.501)
  - Overhang ratio: 49.90%, worst angle: 90.0° (limit: 55.0°)
- **wall_thickness**: ✅ PASS (score: 1.000)
  - Shell thickness: 3.00mm (minimum: 1.60mm, nozzle: 0.80mm, walls: 2)
- **minimum_features**: ✅ PASS (score: 1.000)
  - Smallest dimension: 12.00mm (minimum: 0.40mm)
- **thermal_air_gap**: ❌ FAIL (score: 0.500)
  - Air gap: 1.00mm (target: 2.00mm)
- **thermal_ventilation**: ❌ FAIL (score: 0.125)
  - Ventilation area: 53.9mm² (minimum: 431.4mm²)
- **io_alignment_0**: ❌ FAIL (score: 0.000)
  - IO 0 alignment: x_error=0.00mm, y_error=4.00mm (tolerance: 1.0mm)
- **io_clearance_0**: ❌ FAIL (score: 0.873)
  - IO 0 clearance: slot=12.0x5.0mm, required=12.5x5.5mm, margin=-9.1%

## Iteration History

| Iteration | Score | Passed | Time (s) | Key Changes |
|-----------|-------|--------|----------|-------------|
| 1 | 0.691 | ❌ | 0.1 | - |
| 2 | 0.690 | ❌ | 0.1 | - |