import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DigitalStudyPanel from "./DigitalStudyPanel.jsx";
import { fetchDigitalJob, fetchDigitalStudy, submitDigitalRun } from "./digitalStudyApi.js";

vi.mock("./digitalStudyApi.js", () => ({
  fetchDigitalStudy: vi.fn(), fetchDigitalJob: vi.fn(), submitDigitalRun: vi.fn(), cancelDigitalJob: vi.fn(),
  digitalArtifactUrl: (path) => path,
}));

function study(revision, mass = 234.9, passed = true) {
  return {
    revision, run_id: `run-${revision}`, parent_revision: revision > 1 ? revision - 1 : null,
    change_request: revision === 1 ? "Verified baseline" : "Add 10 g of payload",
    artifacts: { "VIEWER.html": `/revision-${revision}/VIEWER.html`, "nominal.csv": `/revision-${revision}/nominal.csv` },
    summary: {
      mass_g: mass, mass_margin_g: 250 - mass, centre_of_mass_mm: [revision, 0, -1],
      requirements_met: passed, requirements: { payload_mass_g: mass - 234.9, gust_scale: 1, max_mass_g: 250 },
      metrics: { tracking_rms_m: .02, gust_recovery_error_m: .01, peak_current_a_est: 3, consumed_mah_est: 10 },
      constraints: [{ id: "nominal_mass", label: "Nominal mass", actual: mass, limit: 250, unit: "g", passed }],
      scope_limits: ["Ideal full-state feedback"], note: "Digital model",
    },
  };
}

const session = { projectId: "digital-test", projectName: "Saved drone", snapshotRevision: 1 };
const baseline = study(1);
const data = (current = baseline, jobs = []) => ({
  study: current, history: current.revision === 1 ? [baseline] : [current, baseline], jobs,
  runtime: { available: true, setup_hint: "" },
});

beforeEach(() => { vi.resetAllMocks(); fetchDigitalStudy.mockResolvedValue(data()); });

describe("Saved digital requirement revisions", () => {
  it("submits the change against the saved revision, then reloads the completed project", async () => {
    const reload = vi.fn();
    submitDigitalRun.mockResolvedValue({ job: { job_id: "native-run", status: "queued" } });
    fetchDigitalJob.mockImplementation(async () => {
      fetchDigitalStudy.mockResolvedValue(data(study(2, 244.9)));
      return { job_id: "native-run", status: "succeeded" };
    });
    render(<DigitalStudyPanel session={session} onProjectReload={reload} />);
    fireEvent.click(await screen.findByRole("button", { name: "Run and save new revision" }));
    await waitFor(() => expect(submitDigitalRun).toHaveBeenCalledWith("digital-test", expect.objectContaining({
      base_revision: 1, change_request: "Add 10 g of payload", requirements: { gust_scale: 1, max_mass_g: 250 },
    })));
    await waitFor(() => expect(reload).toHaveBeenCalledWith("digital-test"));
    expect(await screen.findByText("244.90")).toBeInTheDocument();
    expect(screen.getByText(/Run completed and revision saved/)).toBeInTheDocument();
  });

  it("shows a saved failed requirement and allows comparing the earlier revision", async () => {
    fetchDigitalStudy.mockResolvedValue(data(study(2, 264.9, false)));
    render(<DigitalStudyPanel session={session} />);
    expect(await screen.findByText("Requirements not met")).toBeInTheDocument();
    expect(screen.getByText(/264.90 g exceeds 250.00 g/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("View revision"), { target: { value: "1" } });
    expect(screen.getByRole("button", { name: "Run and save new revision" })).toBeDisabled();
    expect(screen.getByText("Viewing history.")).toBeInTheDocument();
    expect(screen.getByTitle("Selected design 3D assembly revision 1")).toHaveAttribute("src", "/revision-1/VIEWER.html?embed=1");
  });

  it("restores an in-flight job and reports its failure without replacing the saved model", async () => {
    fetchDigitalStudy.mockResolvedValue(data(baseline, [{ job_id: "restored", status: "running" }]));
    fetchDigitalJob.mockResolvedValue({ job_id: "restored", status: "failed", error: { message: "Independent verification failed" } });
    render(<DigitalStudyPanel session={session} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Independent verification failed");
    expect(screen.getByTitle("Selected design 3D assembly revision 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run and save new revision" })).toBeEnabled();
  });
});
