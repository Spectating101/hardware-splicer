// Deliberately passive integration smoke: checks compiler and connectivity.
// Not an electrically useful or approved standalone gadget.
export default () => (
  <board width="20mm" height="12mm">
    <resistor name="R1" resistance="1k" footprint="0402" pcbX={-4} />
    <resistor name="R2" resistance="2.2k" footprint="0402" pcbX={4} />
    <trace name="R1_to_R2" from=".R1 > .pin2" to=".R2 > .pin1" />
  </board>
)
