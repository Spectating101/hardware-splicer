# Optimization Report: tight_fit_test

**Specification ID**: tight_fit_test
**Total Iterations**: 2
**Total Time**: 0.2s
**Success**: No

## Functional Requirements

- **drop_protection**: F1

## Final Results

**Overall Score**: 0.844
**All Tests Passed**: False

### Test Results

- **envelope_constraint**: ✅ PASS (score: 1.000)
  - Envelope: 45.5x30.5x9.5mm (limit: 50.0x35.0x12.0mm)
- **board_clearance**: ✅ PASS (score: 1.000)
  - Board clearance: 2.73mm (target: 1.0mm)
- **mount_accessibility_0**: ✅ PASS (score: 1.000)
  - Mount 0 accessibility: 10.23mm clearance (required: 2.25mm)
- **mesh_watertight**: ✅ PASS (score: 1.000)
  - Mesh is watertight
- **mesh_manifold**: ✅ PASS (score: 1.000)
  - Mesh is manifold
- **mesh_degenerate**: ✅ PASS (score: 1.000)
  - Degenerate faces: 0
- **overhang_angles**: ❌ FAIL (score: 0.500)
  - Overhang ratio: 50.00%, worst angle: 90.0° (limit: 55.0°)
- **wall_thickness**: ✅ PASS (score: 1.000)
  - Shell thickness: 1.72mm (minimum: 1.60mm, nozzle: 0.80mm, walls: 2)
- **minimum_features**: ✅ PASS (score: 1.000)
  - Smallest dimension: 9.50mm (minimum: 0.40mm)
- **drop_protection_energy**: ✅ PASS (score: 1.000)
  - Energy absorption: 3.21J (target: 1.50J)
- **io_alignment_0**: ❌ FAIL (score: 0.000)
  - IO 0 alignment: x_error=0.00mm, y_error=2.72mm (tolerance: 1.0mm)
- **io_clearance_0**: ❌ FAIL (score: 0.873)
  - IO 0 clearance: slot=12.0x5.0mm, required=12.5x5.5mm, margin=-9.1%

## Iteration History

| Iteration | Score | Passed | Time (s) | Key Changes |
|-----------|-------|--------|----------|-------------|
| 1 | 0.844 | ❌ | 0.1 | - |
| 2 | 0.844 | ❌ | 0.1 | - |