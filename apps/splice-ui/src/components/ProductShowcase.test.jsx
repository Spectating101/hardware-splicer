import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import ProductShowcase from "./ProductShowcase.jsx";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("ProductShowcase publication gate", () => {
  it("does not create a viewer iframe without matching, completed engineering evidence", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok:false, status:404 })));
    render(<ProductShowcase />);
    expect(await screen.findByText("Verified viewer is not in this build")).toBeInTheDocument();
    expect(screen.queryByTitle("Hardware-Splicer native CAD interactive explorer")).not.toBeInTheDocument();
  });

  it("refuses a manifest that promotes unverified physical manufacturing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok:true, json:async () => ({
      schema_version:"hardware_splicer.showcase_bundle.v1",
      native_browser_executed:true, physical_release_authorized:true,
      source_spec_sha256:"a".repeat(64)
    }) })));
    render(<ProductShowcase />);
    expect(await screen.findByText("Verified viewer is not in this build")).toBeInTheDocument();
    expect(screen.queryByTitle("Hardware-Splicer native CAD interactive explorer")).not.toBeInTheDocument();
  });

  it("renders the actual offline HTML iframe only after a valid visual evidence receipt", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok:true, json:async () => ({
      schema_version:"hardware_splicer.showcase_bundle.v1",
      product_id:"source_bound_machine",parts:4,
      native_browser_executed:true,physical_release_authorized:false,
      source_spec_sha256:"b".repeat(64)
    }) })));
    render(<ProductShowcase />);
    const iframe=await screen.findByTitle("Hardware-Splicer native CAD interactive explorer");
    expect(iframe).toHaveAttribute("src", "/showcase/machine.html");
    expect(iframe).toHaveAttribute("sandbox", "allow-scripts");
    expect(screen.getByText(/source_bound_machine/)).toBeInTheDocument();
  });
});
