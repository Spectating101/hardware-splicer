import {afterEach, describe, it, expect, vi} from "vitest";
import {cleanup, render, screen} from "@testing-library/react";
import DetailedAssemblyReference from "./DetailedAssemblyReference.jsx";
afterEach(()=>{cleanup();vi.unstubAllGlobals()});

const sourced={
  schema_version:"hardware_splicer.upstream_viewer_adapter.v1",
  viewer_origin:"upstream_unmodified",source_viewer_original:true,
  follower_parts:542,leader_parts:516,geometry_authored_by_hs:false,
  physical_motion_verified:false,hardware_license:"CERN-OHL-S-2.0",
  upstream_url:"https://github.com/Utsav92/openarm-3d-cad-assembly"
};

describe("Unmodified upstream viewer integration",()=>{
  it("does not replace missing source with a fabricated viewer",async()=>{
    vi.stubGlobal("fetch",vi.fn(async()=>({ok:false})));
    render(<DetailedAssemblyReference/>);
    expect(await screen.findByText(/not packaged in this build/)).toBeInTheDocument();
    expect(screen.queryByTitle("Original OpenArm mechanical CAD viewer")).not.toBeInTheDocument();
  });
  it("refuses to promote modified or HS-authored original CAD",async()=>{
    vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({
      ...sourced,viewer_origin:"hs_reimplementation",geometry_authored_by_hs:true
    })})));
    render(<DetailedAssemblyReference/>);
    expect(await screen.findByText(/not packaged in this build/)).toBeInTheDocument();
  });
  it("mounts original upstream HTML and credits its author",async()=>{
    vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>sourced})));
    render(<DetailedAssemblyReference/>);
    const frame=await screen.findByTitle("Original OpenArm mechanical CAD viewer");
    expect(frame).toHaveAttribute("src","/reference-assemblies/openarm/index.html");
    expect(frame).toHaveAttribute("sandbox","allow-scripts allow-same-origin");
    expect(screen.getByText("Open original viewer")).toHaveAttribute(
      "href","/reference-assemblies/openarm/index.html");
    expect(screen.getByText("Original source")).toHaveAttribute("href",sourced.upstream_url);
  });
});
