import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectReviewPanel from "./ProjectReviewPanel.jsx";
import {
  decideProjectReview,
  listProjectReviews,
  listProjectRevisions,
  loadProjectReview,
} from "../projectSession/projectReviewApi.js";

vi.mock("../projectSession/projectReviewApi.js", () => ({
  decideProjectReview: vi.fn(),
  listProjectReviews: vi.fn(),
  listProjectRevisions: vi.fn(),
  loadProjectReview: vi.fn(),
}));

const summary = {
  review_id: "review-1",
  project_id: "robot",
  base_revision: 1,
  created_at: "2026-07-20T10:00:00Z",
  created_by: "agent",
  note: "Raise motor authority",
  status: "pending",
  summary: { added: 0, removed: 0, modified: 1, project_fields_changed: 0, review_required: true },
};

const detail = {
  ...summary,
  candidate_snapshot: { machineProject: { project_id: "robot" } },
  diff: {
    review_flags: [],
    object_changes: [
      {
        collection: "components",
        object_id: "motor-driver",
        change_type: "modified",
        field_changes: [{ path: "authority", before: "declared", after: "verified" }],
        review_flags: [
          {
            code: "authority_escalation",
            severity: "required",
            message: "components 'motor-driver' escalates authority from declared to verified",
            object_id: "motor-driver",
            path: "authority",
          },
        ],
      },
    ],
  },
};

describe("ProjectReviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listProjectReviews.mockResolvedValue({ reviews: [summary] });
    listProjectRevisions.mockResolvedValue({
      revisions: [
        { revision: 1, current_stage: "design", review_id: null, review_actor: null },
      ],
    });
    loadProjectReview.mockResolvedValue({ review: detail });
    decideProjectReview.mockResolvedValue({
      review: {
        ...detail,
        status: "accepted",
        decision: {
          decision: "accepted",
          actor: "owner",
          accepted_revision: 2,
          decided_at: "2026-07-20T11:00:00Z",
        },
      },
    });
  });

  it("renders pending semantic risks and accepts the candidate", async () => {
    const onToast = vi.fn();
    render(<ProjectReviewPanel projectId="robot" currentRevision={1} onToast={onToast} />);

    expect(await screen.findByText("Raise motor authority")).toBeInTheDocument();
    expect(await screen.findByText("authority escalation")).toBeInTheDocument();
    expect(screen.getByText(/declared to verified/)).toBeInTheDocument();
    expect(screen.getByText("Direct workspace save")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Decision note"), {
      target: { value: "Bench evidence checked" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Accept as next revision" }));

    await waitFor(() =>
      expect(decideProjectReview).toHaveBeenCalledWith("robot", "review-1", {
        decision: "accepted",
        actor: "owner",
        note: "Bench evidence checked",
      }),
    );
    expect(onToast).toHaveBeenCalledWith(
      "Review accepted as revision 2. Reopen the project to load it.",
    );
  });

  it("resumes a journaled acceptance with the original reviewer", async () => {
    const accepting = {
      ...detail,
      status: "accepting",
      decision: {
        decision: "accepting",
        actor: "reviewer-a",
        accepted_revision: 2,
        decided_at: "2026-07-20T10:30:00Z",
      },
    };
    listProjectReviews.mockResolvedValue({ reviews: [{ ...summary, status: "accepting" }] });
    loadProjectReview.mockResolvedValue({ review: accepting });
    render(<ProjectReviewPanel projectId="robot" currentRevision={1} onToast={() => {}} />);

    expect(await screen.findByTestId("review-acceptance-recovery")).toHaveTextContent(
      "Acceptance was journaled but not finalized",
    );
    expect(screen.getByLabelText("Reviewer")).toHaveValue("reviewer-a");
    expect(screen.getByLabelText("Reviewer")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Reject candidate" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resume acceptance" }));

    await waitFor(() =>
      expect(decideProjectReview).toHaveBeenCalledWith("robot", "review-1", {
        decision: "accepted",
        actor: "reviewer-a",
        note: "",
      }),
    );
  });

  it("stays hidden until a durable revision exists", () => {
    const { container } = render(
      <ProjectReviewPanel projectId="robot" currentRevision={0} onToast={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
    expect(listProjectReviews).not.toHaveBeenCalled();
  });
});
