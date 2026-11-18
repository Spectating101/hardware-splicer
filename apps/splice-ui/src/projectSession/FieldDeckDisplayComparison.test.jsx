import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import reference from "../../../../docs/status/generated/fielddeck-display-swap-20261118.json";
import { SavedDisplayComparison } from "./FieldDeckDisplayComparison.jsx";

afterEach(() => vi.unstubAllGlobals());

it("retries a failed artifact and renders the saved calculation for the selected revision", async () => {
  const power = structuredClone(reference.power);
  power.scenarios[0].variant_5inch.runtime_h = [2.55, 3.60];
  const reports = { power, geometry: reference.geometry, connections: reference.connections };
  const request = vi.fn(async (url) => ({
    ok: true, json: async () => reports[url.split("/").at(-1)],
  })).mockResolvedValueOnce({ ok: false, status: 503 });
  vi.stubGlobal("fetch", request);
  const artifacts = Object.fromEntries(Object.keys(reports).map((key) => [`revision/${key}.json`, `/revisions/2/${key}`]));
  render(<SavedDisplayComparison study={{ revision: 2, artifacts }} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("503");
  expect(screen.queryByText("3.17–4.47 h")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry comparison" }));
  expect(await screen.findByText("2.55–3.60 h")).toBeVisible();
  expect(screen.getByRole("link", { name: /power calculations/ }).getAttribute("href")).toMatch(/\/revisions\/2\/power$/);
});
