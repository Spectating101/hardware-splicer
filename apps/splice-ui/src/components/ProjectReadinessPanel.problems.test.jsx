import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACTIONS, createEmptySession, projectSessionReducer } from "../projectSession/projectSession.js";
import ProjectReadinessPanel from "./ProjectReadinessPanel.jsx";

const CLASH = {
  level: "error",
  code: "i2c_address_clash",
  message: "2 devices on one I2C bus would all answer at 0x77: BME280 (n2), BME280 (n5). They cannot both work.",
  repairs: [
    {
      kind: "strap_alternate_address",
      summary: "Set BME280 (n5) to answer at 0x76 instead of 0x77.",
      requires_person: true,
      physical_steps: ["Set the address pin on BME280 (n5).", "How this is done depends on your board."],
    },
    { kind: "second_i2c_bus", summary: "Move BME280 (n5) to a second I2C bus on GPIO18 and GPIO23.", requires_person: false },
  ],
};

function sessionWith(gate) {
  return projectSessionReducer(createEmptySession(), {
    type: ACTIONS.HYDRATE_CURRENT_RESULT,
    jobId: "job_1",
    result: { build_dir: "/tmp/b", ok: false, design_quality_gate: gate, project_package: { build_dir: "/tmp/b", gates: { compile_ok: false } } },
  });
}

describe("ProjectReadinessPanel problems", () => {
  it("lists each electrical problem in plain view, with no hover needed", () => {
    render(<ProjectReadinessPanel session={sessionWith({ build_ready: false, summary: { electrical_issues: [CLASH] } })} />);

    const list = screen.getByTestId("design-problems");
    expect(list).toHaveTextContent("would all answer at 0x77");
    expect(list).toHaveTextContent("They cannot both work");
  });

  it("says which repairs HS can make and which need a person, and the person's steps", () => {
    render(<ProjectReadinessPanel session={sessionWith({ build_ready: false, summary: { electrical_issues: [CLASH] } })} />);

    const hs = screen.getByTestId("repair-hs");
    expect(hs).toHaveTextContent("second I2C bus");
    expect(hs).toHaveTextContent(/HS can/i);
    const person = screen.getByTestId("repair-person");
    expect(person).toHaveTextContent("0x76");
    expect(person).toHaveTextContent(/needs you/i);
    expect(person).toHaveTextContent("depends on your board");
  });

  it("lists a missing requested part the same way", () => {
    const mismatch = {
      status: "mismatch",
      missing_parts: [{ module_id: "sg90", names: ["pan", "tilt"], requested: 2, in_design: 1, unknown_module_id: false, did_you_mean: [] }],
    };
    render(<ProjectReadinessPanel session={sessionWith({ build_ready: false, request_fidelity: mismatch, summary: {} })} />);

    expect(within(screen.getByTestId("design-problems")).getByText(/requested 2, design has 1/)).toBeInTheDocument();
  });

  it("colours the design chip as a failure for these states, not neutral grey", () => {
    render(<ProjectReadinessPanel session={sessionWith({ build_ready: false, summary: { electrical_issues: [CLASH] } })} />);

    expect(screen.getByTestId("ready-design")).toHaveClass("status-chip--fail");
  });

  it("shows no problem list for a clean design", () => {
    const session = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: "job_1",
      result: {
        build_dir: "/tmp/b",
        design_quality: { kicad_drc_errors: 0 },
        design_quality_gate: { build_ready: true, summary: { electrical_issues: [{ level: "info", message: "confirm pull-ups" }] } },
        project_package: { build_dir: "/tmp/b", gates: { compile_ok: true } },
      },
    });
    render(<ProjectReadinessPanel session={session} />);

    expect(screen.queryByTestId("design-problems")).toBeNull();
  });
});
