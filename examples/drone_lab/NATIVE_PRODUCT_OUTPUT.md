# HS native product output: 65 / custom 70 / 75 mm micro-quadcopter designs

**This is an executable engineering product generator, not a pass-count benchmark.** Hardware Splicer now creates its own full quadcopter frame geometry and battery channel using the original Mecha-Splicer engine and first-party `AerialFrameSpec`, rather than borrowing a pre-built aircraft CAD file or delegating frame authoring to Atech.

## Run the product generator

```bash
# From the HS repository on Linux:
bash examples/drone_lab/produce_with_hs.sh 65
bash examples/drone_lab/produce_with_hs.sh 70
bash examples/drone_lab/produce_with_hs.sh 75

# Or supply your own explicitly sourced dimensions/components:
python -m hardware_splicer.drone_product_delivery \
  --design-request examples/drone_lab/design_requests/hs_native_70mm_custom.json \
  --out /tmp/hs-custom-whoop \
  --openscad-bin /path/to/openscad \
  --flight-source /path/to/gym-pybullet-drones
```

The single launcher downloads dependencies to an isolated cache and uses published upstream OpenSCAD solely for rendering the **original HS CSG** into an STL. OpenSCAD does not create the frame design. For physical flight the actual airframe must be printed, weighed, inspected, assembled and piloted by an operator.

## User-facing artifacts — not just test reports

Every product package contains:

- `HS_ORIGINAL_MECHANICAL/aerial_frame.scad`: original parametric whole-airframe with 4 ring-cage guards, 4 3-hole M1.4 at 6.6mm-PCD motor mounts, center support struts and 26x26mm FC mount pattern rotated 45°
- `HS_ORIGINAL_MECHANICAL/aerial_frame.stl`: watertight printable mesh generated from those native HS dimensions
- `HS_ORIGINAL_MECHANICAL/battery_cradle.scad` and `.stl`: a separate printable battery channel sized to the declared pack cross-section
- `FRAME_PREVIEW.png`: actual geometry preview, not an image-generation fantasy
- `HS_PRODUCT_SCENE.glb`: a reusable, viewable 3D model including the separate battery cradle
- `REAL_PARTS_BOM.csv`: named motor, prop, battery, Matrix 1S controller and radio/charger components with supplier/spec references
- `HS_ROBOT_TOPOLOGY.json`: native HS proposed rotor, motor, firmware-channel and IMU identities
- `ASSEMBLY.md` and `START_HERE.md`: instructions leading to actual physical printing and assembly
- `CRAZYFLIE_SIM_NOT_THIS_AIRFRAME/`: upstream flight physics recording, explicitly **not** a calibrated digital twin of any generated aircraft

| Generated design | Prop | Declared motors | Frame bounding box | PETG frame mass estimate |
| --- | --- | --- | --- | --- |
| HS65 original | 31mm | RCinPower 0702 27000KV | 82.96 × 82.96 × 16mm | 9.04g |
| HS70 **custom** | 35mm | BETAFPV 0802SE 19500KV | varies with actual 70mm CAD | ~10.33g |
| HS75 original | 40mm | BETAFPV 0802SE 19500KV | 99.23 × 99.23 × 17.5mm | 11.68g |

These are **computed solid-PETG mass estimates only**. They have not been weighed or printed; actual material, infill/slicer/perimeters and supporting bridges can change weight and print strength considerably.

## Truth and engineering gates

1. **Native design capability demonstrated:** changing the actual request changes the frame, duct size, physical motor pads, battery channel, BOM and 3D view. All three requests generated real single watertight STL solids on the connected Optiplex.
2. **Bounded electrical compatibility:** only 1S supplies and four brushless motors, exact nominal motor/prop shaft size, selected prop diameter and board mounting pattern are accepted. The native Mecha-Splicer geometry engine rejects collision-producing ducts and poor clearances.
3. **No false certification:** source motor current figures and component claims are preliminary; especially the 75/70 0802 motor's max-current figure is not verified. Fit, battery dimensions, strength, center of gravity, prop clearance under load, failsafe and measured thrust remain open.
4. **Simulation is not a flight proof:** the included existing Crazyflie/PyBullet controller simulation is not calibrated for HS65/70/75 mass, ESCs, motors, thrust and aerodynamic properties; it cannot validate real flightability.
5. **External source reuse is deliberate and attributed:** we reuse **hardware manufacturer specifications** and open-source OpenSCAD renderer, not the 65mm frame geometry. Mecha-Splicer itself writes the aircraft CAD.

Sources: [BETAFPV Matrix 1S controller](https://betafpv.com/products/matrix-1s-brushless-flight-controller), [BETAFPV 0702](https://betafpv.com/products/0702-brushless-motors), [BETAFPV 0802SE](https://betafpv.com/products/0802se-22000kv-brushless-motors), [Meteor75 40mm assembly](https://betafpv.com/products/meteor75-brushless-whoop-quadcopter-1s).

**Next actual physical step:** use a printer to make the frame and cradle, measure real hardware before assembly, verify receiver and electronics props-off, and do a guarded first hover. There is no connected physical drone or printer in this execution; physical build remains **unproven**.
