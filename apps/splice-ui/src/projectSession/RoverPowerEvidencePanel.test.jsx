import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import RoverPowerEvidencePanel from "./RoverPowerEvidencePanel.jsx";

const report = {
  status: "blocked",
  declared: {
    battery_nominal_v: 7.4,
    battery_capacity_mah: 2200,
    motor_count: 2,
    simultaneous_stall_current_a: 1.8,
  },
  measured: { motor_rail_v: null },
  blockers: [
    { code: "motor_rail_not_derived", message: "Motor-terminal rail not established." },
    { code: "driver_current_thermal_unverified", message: "Driver thermal margin unknown." },
  ],
  next_actions: ["Obtain protected measurements at the intended operating load."],
  sources: { l298_datasheet: "https://www.st.com/resource/en/datasheet/l298.pdf" },
};

describe("evidence-first rover power review UI", () => {
  it("shows declared numbers distinctly from missing real measurements and stays non-interactive", () => {
    const { container } = render(<RoverPowerEvidencePanel report={report} />);
    expect(screen.getByTestId("rover-power-evidence").textContent).toContain("not authorized");
    expect(screen.getByText(/No authenticated measurement/)).toBeTruthy();
    expect(screen.getByText(/Motor-terminal rail not established/)).toBeTruthy();
    expect(screen.getByText(/1.8/)).toBeTruthy();
    expect(screen.getByText(/2/)).toBeTruthy();
    expect(container.querySelector("button")).toBeNull();
    expect(screen.getByRole("link", { name: /ST L298 datasheet/ }).getAttribute("href"))
      .toBe(report.sources.l298_datasheet);
  });

  it("does not decorate an unrelated logger with rover power claims", () => {
    const { container } = render(<RoverPowerEvidencePanel report={{status:"not_applicable"}} />);
    expect(container.firstChild).toBeNull();
  });
});
