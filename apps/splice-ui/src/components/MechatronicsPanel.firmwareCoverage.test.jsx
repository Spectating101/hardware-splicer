import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MechatronicsPanel from "./MechatronicsPanel.jsx";

const firmware = {
  filename: "generic_low_voltage_build.ino",
  pins: { servo_pan: 15, servo_tilt: 16 },
  source: "void loop() { digitalWrite(LED_BUILTIN, 1); }",
};

function packageWith(coverage) {
  return { firmware_scaffold: firmware, firmware_coverage: coverage };
}

describe("MechatronicsPanel firmware coverage", () => {
  it("says which wired pins the firmware never uses, and what each drives", () => {
    render(
      <MechatronicsPanel
        pkg={packageWith({
          status: "gaps",
          required_pins: [],
          uncovered_pins: [
            { pin: "GPIO15", drives: "sg90.SIG" },
            { pin: "GPIO16", drives: "sg90.SIG" },
          ],
          claim_boundary: "Checks only that the firmware names each pin.",
        })}
      />
    );

    const note = screen.getByTestId("firmware-coverage");
    expect(note).toHaveAttribute("data-status", "gaps");
    expect(note).toHaveTextContent("Firmware does not use GPIO15");
    expect(note).toHaveTextContent("GPIO16");
    expect(note).toHaveTextContent("sg90.SIG");
  });

  it("says plainly that covering the pins is not proof the firmware works", () => {
    render(
      <MechatronicsPanel
        pkg={packageWith({ status: "covers", required_pins: [{ pin: "GPIO15" }], uncovered_pins: [] })}
      />
    );

    const note = screen.getByTestId("firmware-coverage");
    expect(note).toHaveAttribute("data-status", "covers");
    expect(note).toHaveTextContent(/not (a )?proof|does not (show|prove)/i);
  });

  it("does not report a pass when the check could not be made", () => {
    render(<MechatronicsPanel pkg={packageWith({ status: "not_assessable", required_pins: [], uncovered_pins: [] })} />);

    expect(screen.getByTestId("firmware-coverage")).toHaveAttribute("data-status", "not_assessable");
    expect(screen.getByTestId("firmware-coverage")).not.toHaveTextContent(/covers every|all wired pins/i);
  });

  it("shows nothing when a build never produced a coverage result", () => {
    render(<MechatronicsPanel pkg={{ firmware_scaffold: firmware }} />);

    expect(screen.queryByTestId("firmware-coverage")).toBeNull();
  });
});
