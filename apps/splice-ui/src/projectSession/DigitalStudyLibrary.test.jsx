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

it("switches scenario and starts the exact display selected in the comparison", async () => {
  const onStart = vi.fn();
  const cases = ["fielddeck-7", "fielddeck-5"].map((case_id) => ({
    case_id, name: case_id, requirements: {}, source_inputs_available: true,
  }));
  fetchDigitalCases.mockResolvedValueOnce({ cases, default_case_id: "fielddeck-7" });
  render(<DigitalStudyLibrary online onStart={onStart} />);
  expect(await screen.findByText("3.17–4.47 h")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Power scenario"), { target: { value: "high_keyboard_demand" } });
  expect(screen.getAllByText("0.08 A")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "5-inch" }));
  expect(screen.getByRole("radio", { name: /FieldDeck 5/ })).toBeChecked();
  fireEvent.click(screen.getByText("What changes with the 5-inch display?"));
  expect(screen.getByText(/4 × display spacer/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Start digital design" }));
  expect(onStart).toHaveBeenCalledWith("fielddeck-5");
});
