import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACTIONS, createEmptySession, projectSessionReducer } from "../projectSession/projectSession.js";
import ProjectStatusHeader from "./ProjectStatusHeader.jsx";

const MISMATCH = {
  status: "mismatch",
  missing_parts: [
    { module_id: "sg90", names: ["SG90 pan servo", "SG90 tilt servo"], requested: 2, in_design: 1 },
  ],
};

describe("ProjectStatusHeader with a design that leaves out a requested part", () => {
  it("shows a failing chip that says so and explains which part", () => {
    const session = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: "job_1",
      result: {
        build_dir: "/tmp/b",
        ok: false,
        design_quality_gate: { build_ready: false, request_fidelity: MISMATCH },
        project_package: { build_dir: "/tmp/b", gates: { compile_ok: false } },
      },
    });

    render(<ProjectStatusHeader session={session} />);

    const chip = screen.getByTestId("chip-drc");
    expect(chip).toHaveTextContent("Missing requested part");
    expect(chip).toHaveClass("status-chip--fail");
    expect(chip).toHaveAttribute("title", expect.stringContaining("requested 2, design has 1"));
  });
});
