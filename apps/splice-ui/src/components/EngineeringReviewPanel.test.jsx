import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { downloadBuildArtifact } from "../api.js";
import {
  fetchEngineeringReviewStatus,
  runEngineeringReview,
} from "../engineeringReviewApi.js";
import EngineeringReviewPanel from "./EngineeringReviewPanel.jsx";

vi.mock("../api.js", () => ({
  downloadBuildArtifact: vi.fn(),
}));

vi.mock("../engineeringReviewApi.js", () => ({
  fetchEngineeringReviewStatus: vi.fn(),
  runEngineeringReview: vi.fn(),
}));

const availableStatus = {
  ok: true,
  can_run: true,
  adapter: {
    id: "kicad-happy",
    name: "kicad-happy",
    available: true,
    authority_ceiling: "observed",
  },
  supported_inputs: ["schematic", "pcb"],
  inputs: [],
  latest_review: null,
};

const review = {
  ok: true,
  cached: false,
  summary: {
    status: "blocked",
    headline: "1 engineering blocker(s) require review before release.",
    blocker_count: 1,
    warning_count: 2,
    analysis_count: 2,
    provenance_coverage_pct: 92,
  },
  findings: [
    {
      finding_id: "schematic:PW-001:1",
      rule_id: "PW-001",
      analyzer_type: "schematic",
      severity: "blocker",
      title: "Power rail mismatch",
      recommendation: "Verify the regulator feedback network.",
      confidence: "deterministic",
      components: ["U1"],
      nets: ["+3V3"],
    },
  ],
  failures: [],
};

describe("EngineeringReviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a concrete setup path when the adapter is missing", async () => {
    fetchEngineeringReviewStatus.mockResolvedValue({
      ...availableStatus,
      can_run: false,
      adapter: {
        name: "kicad-happy",
        available: false,
        authority_ceiling: "observed",
        setup: {
          instruction: "Clone aklofas/kicad-happy locally and configure the checkout.",
        },
      },
      supported_inputs: [],
    });

    render(<EngineeringReviewPanel buildDir="/tmp/build" />);

    expect(await screen.findByText("Analyzer not configured")).toBeInTheDocument();
    expect(screen.getByText(/HARDWARE_SPLICER_KICAD_HAPPY_ROOT/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run engineering review" })).toBeDisabled();
  });

  it("turns analyzer output into release-oriented findings", async () => {
    const user = userEvent.setup();
    fetchEngineeringReviewStatus.mockResolvedValue(availableStatus);
    runEngineeringReview.mockResolvedValue(review);

    render(<EngineeringReviewPanel buildDir="/tmp/build" />);
    await user.click(await screen.findByRole("button", { name: "Run engineering review" }));

    expect(await screen.findByText("Power rail mismatch")).toBeInTheDocument();
    expect(screen.getByText(/require review before release/i)).toBeInTheDocument();
    expect(screen.getByText(/component U1/)).toBeInTheDocument();
    expect(screen.getByText(/net \+3V3/)).toBeInTheDocument();
    expect(screen.getByText("Observed evidence only")).toBeInTheDocument();
    expect(runEngineeringReview).toHaveBeenCalledWith("/tmp/build", { force: false });
  });

  it("downloads the normalized review artifact", async () => {
    const user = userEvent.setup();
    fetchEngineeringReviewStatus.mockResolvedValue({
      ...availableStatus,
      latest_review: review,
    });
    downloadBuildArtifact.mockResolvedValue(undefined);

    render(<EngineeringReviewPanel buildDir="/tmp/build" />);
    await user.click(await screen.findByRole("button", { name: "Download review JSON" }));

    await waitFor(() => {
      expect(downloadBuildArtifact).toHaveBeenCalledWith(
        "/tmp/build",
        "build_compilation/ENGINEERING_REVIEW.json",
      );
    });
  });
});
