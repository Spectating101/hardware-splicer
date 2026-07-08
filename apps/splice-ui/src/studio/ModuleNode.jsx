import { Handle, Position } from "@xyflow/react";

const CAT_BADGE = {
  mcu: "MCU",
  power: "PWR",
  radio: "RF",
  sensor: "SNS",
  display: "DSP",
  actuator: "ACT",
  interface: "IF",
  passive: "PAS",
};

const ROLE_COLOR = {
  gnd: "#475569",
  power_in: "#ef4444",
  power_out: "#f59e0b",
  digital_io: "#a78bfa",
  digital_in: "#a78bfa",
  digital_out: "#a78bfa",
  analog_in: "#34d399",
  pwm: "#f472b6",
  uart_tx: "#22d3ee",
  uart_rx: "#22d3ee",
  i2c_sda: "#38bdf8",
  i2c_scl: "#38bdf8",
  spi_mosi: "#2dd4bf",
  spi_miso: "#2dd4bf",
  spi_sck: "#2dd4bf",
  spi_cs: "#2dd4bf",
  reset: "#fb7185",
  other: "#94a3b8",
};

const PIN_ROW_H = 22;
const MODULE_W = 240;

export default function ModuleNode({ data, selected }) {
  const spec = data?.spec;
  const moduleId = data?.moduleId;
  if (!spec) {
    return (
      <div className="module-node module-node--missing">
        Unknown module: {moduleId}
      </div>
    );
  }

  const leftPins = spec.pins.slice(0, Math.ceil(spec.pins.length / 2));
  const rightPins = spec.pins.slice(Math.ceil(spec.pins.length / 2));
  const bodyH = Math.max(leftPins.length, rightPins.length) * PIN_ROW_H + 12;
  const badge = CAT_BADGE[spec.category] || "MOD";

  return (
    <div className={`module-node ${selected ? "module-node--selected" : ""}`} style={{ width: MODULE_W }}>
      <div className="module-node__body">
        <div className="module-node__header">
          <span className="module-node__badge">{badge}</span>
          <div className="module-node__titles">
            <div className="module-node__label">{spec.label}</div>
            <div className="module-node__category">{spec.category}</div>
          </div>
        </div>

        <div className="module-node__pins" style={{ height: bodyH }}>
          <div className="module-node__pin-col module-node__pin-col--left">
            {leftPins.map((pin) => {
              const color = ROLE_COLOR[pin.role] || ROLE_COLOR.other;
              return (
                <div key={pin.id} className="module-node__pin-row" style={{ height: PIN_ROW_H }}>
                  <Handle
                    id={pin.id}
                    type="target"
                    position={Position.Left}
                    className="module-node__handle"
                    style={{ background: color, borderColor: "#020617", boxShadow: `0 0 4px ${color}` }}
                  />
                  <span className="module-node__pad" style={{ background: color, boxShadow: `0 0 3px ${color}` }} />
                  <span className="module-node__pin-label" title={pin.label}>
                    {pin.label}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="module-node__pin-col module-node__pin-col--right">
            {rightPins.map((pin) => {
              const color = ROLE_COLOR[pin.role] || ROLE_COLOR.other;
              return (
                <div key={pin.id} className="module-node__pin-row module-node__pin-row--right" style={{ height: PIN_ROW_H }}>
                  <span className="module-node__pin-label" title={pin.label}>
                    {pin.label}
                  </span>
                  <span className="module-node__pad" style={{ background: color, boxShadow: `0 0 3px ${color}` }} />
                  <Handle
                    id={pin.id}
                    type="source"
                    position={Position.Right}
                    className="module-node__handle"
                    style={{ background: color, borderColor: "#020617", boxShadow: `0 0 4px ${color}` }}
                  />
                </div>
              );
            })}
          </div>
        </div>

        <div className="module-node__footer">{spec.pins.length} pins</div>
      </div>
    </div>
  );
}
