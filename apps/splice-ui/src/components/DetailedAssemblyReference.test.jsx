import {afterEach, describe, it, expect, vi} from "vitest";
import {cleanup, render, screen} from "@testing-library/react";
import DetailedAssemblyReference from "./DetailedAssemblyReference.jsx";
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
describe("Complex CAD reference publishing",()=>{
 it("never replaces a missing assembly with fake primitive geometry",async()=>{
   vi.stubGlobal("fetch",vi.fn(async()=>({ok:false})));
   render(<DetailedAssemblyReference/>);
   expect(await screen.findByText(/not packaged in this build/)).toBeInTheDocument();
   expect(screen.queryByTitle("Complete OpenArm CAD interactive explorer")).not.toBeInTheDocument();
 });
 it("requires many real named glTF meshes and external provenance",async()=>{
   vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({
     schema_version:"hardware_splicer.external_assembly_browser_proof.v1",
     actual_glb_nodes_mapped:3,full_model_visible:true,
     geometry_authored_by_hs:false,physical_motion_verified:false
   })})));
   render(<DetailedAssemblyReference/>);
   expect(await screen.findByText(/not packaged in this build/)).toBeInTheDocument();
   expect(screen.queryByTitle("Complete OpenArm CAD interactive explorer")).not.toBeInTheDocument();
 });
 it("opens sourced complex reference inside isolated iframe with actual proof",async()=>{
   vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({
     schema_version:"hardware_splicer.external_assembly_browser_proof.v1",
     actual_glb_nodes_mapped:542,full_model_visible:true,
     geometry_authored_by_hs:false,physical_motion_verified:false
   })})));
   render(<DetailedAssemblyReference/>);
   const iframe=await screen.findByTitle("Complete OpenArm CAD interactive explorer");
   expect(iframe).toHaveAttribute("src","/reference-assemblies/openarm/machine.html");
   expect(iframe).toHaveAttribute("sandbox","allow-scripts");
 });
});
