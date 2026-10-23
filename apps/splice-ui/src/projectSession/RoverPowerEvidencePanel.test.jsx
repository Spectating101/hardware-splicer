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
    expect(screen.getByText("2")).toBeTruthy();
    expect(container.querySelector("button")).toBeNull();
    expect(screen.getByRole("link", { name: /ST L298 datasheet/ }).getAttribute("href"))
      .toBe(report.sources.l298_datasheet);
  });

  it("does not decorate an unrelated logger with rover power claims", () => {
    const { container } = render(<RoverPowerEvidencePanel report={{status:"not_applicable"}} />);
    expect(container.firstChild).toBeNull();
  });
  it("compares L298 with package-specific driver alternatives without selecting either", () => {
    const evidence = {
      ...report,
      driver_options: {
        options: [
          { id: "l298n_existing", part: "L298 existing",
            reference_url: "https://www.st.com/resource/en/datasheet/l298.pdf",
            max_current_continuous_a_at_reference: 2,
            supply_nominal_within_spec: null, selection: "conditional_incumbent" },
          { id: "ti_drv8833_pwp_rty", part: "DRV8833 PWP/RTY",
            reference_url: "https://www.ti.com/lit/ds/symlink/drv8833.pdf",
            max_current_continuous_a_at_reference: 1.5,
            supply_nominal_within_spec: true, selection: "candidate_for_validation" },
          { id: "ti_drv8833_pw", part: "DRV8833 PW",
            reference_url: "https://www.ti.com/lit/ds/symlink/drv8833.pdf",
            max_current_continuous_a_at_reference: 0.5,
            supply_nominal_within_spec: true, selection: "needs_continuous_load_evidence" },
        ],
        recommended_next_evaluation: "Measure the motor current and voltage under safe conditions.",
      },
    };
    const { container } = render(<RoverPowerEvidencePanel report={evidence} />);
    expect(screen.getByTestId("motor-driver-comparison")).toBeTruthy();
    expect(screen.getByText("DRV8833 PWP/RTY")).toBeTruthy();
    expect(screen.getByText("DRV8833 PW")).toBeTruthy();
    expect(container.textContent).toContain("needs continuous load evidence");
    expect(container.textContent).toContain("No candidate is selected");
    expect(container.querySelector("button")).toBeNull();
  });

});
