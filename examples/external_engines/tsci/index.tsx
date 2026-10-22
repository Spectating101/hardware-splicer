export default () => (
  <board width="18mm" height="12mm">
    <resistor name="R1" resistance="1k" footprint="0402" pcbX={-4} />
    <led name="D1" color="red" footprint="0603" pcbX={4} />
    <trace from=".R1 > .pin2" to=".D1 > .anode" />
    <trace from=".D1 > .cathode" to=".R1 > .pin1" />
  </board>
)
