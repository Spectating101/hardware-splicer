import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProductReview from "../components/ProductReview.jsx";
import { createEmptySession } from "./projectSession.js";

afterEach(cleanup);

describe("product-first engineering review", () => {
  it("shows all disciplines using the same real package, with unknowns explicit", async () => {
    const user = userEvent.setup();
    const session = createEmptySession({
      projectId: "project-a",
      goal: "Build a motor controller",
      intakeComplete: true,
      projectPackage: {
        info: { project_name: "Controller" },
        bom: { lines: [{ ref: "U1", description: "Motor driver", qty: 1 }] },
        firmware_scaffold: { filename: "main.cpp", source: "void setup() {}" },
        gates: { compile_ok: true, blockers: ["Stall current unknown"] },
      },
    });
    render(<ProductReview session={session} />);
    expect(screen.getByText("Build a motor controller")).toBeInTheDocument();
    expect(screen.getByText("Stall current unknown")).toBeInTheDocument();
    expect(screen.getByText(/physical measurements/i)).toBeInTheDocument();

    await user.click(screen.getByTestId("review-tab-parts"));
    expect(screen.getByText("Motor driver")).toBeInTheDocument();
    await user.click(screen.getByTestId("review-tab-mechanical"));
    expect(screen.getByText(/No mechanical design or measured donor dimensions/i)).toBeInTheDocument();
    await user.click(screen.getByTestId("review-tab-code"));
    expect(screen.getByText("main.cpp")).toBeInTheDocument();
    await user.click(screen.getByTestId("review-tab-build"));
    expect(screen.getByText(/No build instructions are available/i)).toBeInTheDocument();
    await user.click(screen.getByTestId("review-tab-verify"));
    expect(screen.getByText(/not a physical clearance/i)).not.toBeInTheDocument();
    expect(screen.getByText(/does not verify physical safety/i)).toBeInTheDocument();
  });

  it("does not invent package data when the project has only an intake", async () => {
    const user = userEvent.setup();
    render(<ProductReview session={createEmptySession({
      projectId: "project-b", goal: "Repair an old controller", intakeComplete: true, mode: "salvage",
    })} />);
    expect(screen.getByText(/Nothing is fabricated for this view/i)).toBeInTheDocument();
    await user.click(screen.getByTestId("review-tab-wiring"));
    expect(screen.getByText(/absent wiring guide is not an approved pinout/i)).toBeInTheDocument();
    await user.click(screen.getByTestId("review-tab-verify"));
    expect(screen.getByText(/not a physical clearance/i)).toBeInTheDocument();
  });
});
