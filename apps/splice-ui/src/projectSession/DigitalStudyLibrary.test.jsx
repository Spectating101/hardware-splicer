import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import DigitalStudyLibrary from "./DigitalStudyLibrary.jsx";
import { fetchDigitalCases } from "./digitalStudyApi.js";

vi.mock("./digitalStudyApi.js", () => ({ fetchDigitalCases: vi.fn() }));

it("retries discovery and opens the selected available design by its backend ID", async () => {
  const onStart = vi.fn();
  const cases = ["missing", "custom", "plotter"].map((case_id) => ({
    case_id, name: case_id, requirements: { drawing_width_mm: {} }, source_inputs_available: case_id !== "missing",
  }));
  fetchDigitalCases.mockRejectedValueOnce(new Error("Connection lost")).mockResolvedValueOnce({ cases, default_case_id: "missing" });
  render(<DigitalStudyLibrary online onStart={onStart} />);
  fireEvent.click(await screen.findByRole("button", { name: "Reload designs" }));
  expect(await screen.findByRole("radio", { name: /missing/ })).toBeDisabled();
  expect(screen.getByRole("radio", { name: /custom/ })).toBeChecked();
  fireEvent.click(screen.getByRole("radio", { name: /plotter/ }));
  fireEvent.click(screen.getByRole("button", { name: "Start digital design" }));
  expect(onStart).toHaveBeenCalledWith("plotter");
});

it("starts the selected FieldDeck study and leaves display comparison inside its evidence pane", async () => {
  const onStart = vi.fn();
  const cases = ["fielddeck-7", "fielddeck-5"].map((case_id) => ({
    case_id, name: case_id, requirements: {}, source_inputs_available: true,
  }));
  fetchDigitalCases.mockResolvedValueOnce({ cases, default_case_id: "fielddeck-7" });
  render(<DigitalStudyLibrary online onStart={onStart} />);
  fireEvent.click(await screen.findByRole("radio", { name: /FieldDeck 5/ }));
  expect(screen.getByRole("radio", { name: /FieldDeck 5/ })).toBeChecked();
  expect(screen.getByText("Reference preview: unknown. Open a study to inspect its saved design.")).toBeInTheDocument();
  expect(screen.queryByRole("img")).toBeNull();
  expect(screen.queryByLabelText("Power scenario")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Start digital design" }));
  expect(onStart).toHaveBeenCalledWith("fielddeck-5");
});
