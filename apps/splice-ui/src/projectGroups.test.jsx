import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { groupProjectsByName, ProjectsHome } from "./App.jsx";

const project = (id, name, saved) => ({ project_id: id, name, saved_at: saved, created_at: saved });

describe("groupProjectsByName", () => {
  it("groups names case- and underscore-insensitively, newest first within and across groups", () => {
    const groups = groupProjectsByName([
      project("aaaa1111", "pen plotter", "2026-11-01T10:00:00Z"),
      project("bbbb2222", "Fielddeck", "2026-11-03T10:00:00Z"),
      project("cccc3333", "Pen_plotter", "2026-11-05T10:00:00Z"),
      project("dddd4444", "pen plotter", null),
    ]);
    expect(groups.map(({ name }) => name)).toEqual(["Pen plotter", "Fielddeck"]);
    expect(groups[0].latest.project_id).toBe("cccc3333");
    expect(groups[0].older.map(({ project_id: id }) => id)).toEqual(["aaaa1111", "dddd4444"]);
    expect(groups[1].older).toEqual([]);
  });

  it("keeps every project reachable: group members add up to the input", () => {
    const input = Array.from({ length: 9 }, (_, i) => project(`id${i}xxxxxx`, ["A", "B", "a"][i % 3], `2026-11-0${i + 1}T00:00:00Z`));
    const groups = groupProjectsByName(input);
    expect(groups.flatMap(({ latest, older }) => [latest, ...older])).toHaveLength(9);
  });
});

describe("Projects list grouping", () => {
  it("shows the newest of a repeated name and folds the older copies, each still openable", async () => {
    const opened = [];
    render(<ProjectsHome online projects={[
      project("aaaa1111-old", "Drone", "2026-11-01T10:00:00Z"),
      project("cccc3333-solo", "Pen plotter", "2026-11-03T10:00:00Z"),
      project("bbbb2222-new", "drone", "2026-11-02T10:00:00Z"),
    ]} onOpen={(id) => opened.push(id)} onStart={() => {}} onLibrary={() => {}} onRetry={() => {}} />);
    const group = screen.getByTestId("project-group");
    const fold = within(group).getByText("1 more named “Drone”");
    expect(within(group).getAllByRole("button")[0]).toHaveAttribute("data-project-id", "bbbb2222-new");
    // A name used once is a plain row, without the id tail.
    expect(screen.getByText("Pen plotter").closest("button")).toHaveAttribute("data-project-id", "cccc3333-solo");
    expect(screen.queryByText(/· cccc3333/)).toBeNull();
    await userEvent.click(fold);
    await userEvent.click(group.querySelector('[data-project-id="aaaa1111-old"]'));
    await userEvent.click(group.querySelector('[data-project-id="bbbb2222-new"]'));
    expect(opened).toEqual(["aaaa1111-old", "bbbb2222-new"]);
  });
});
