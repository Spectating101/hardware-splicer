import { describe, expect, it } from "vitest";
import {
  classifyExternalArtifact, parseCircuitJsonArtifact,
  parseBomCsvArtifact, reconcileExternalBomProposal, inspectBinaryStlArtifact, validateExternalFile,
} from "./externalArtifactIntake.js";

describe("read-only upstream artifact intake", () => {
  it("recognizes interoperable sources without claiming proprietary integration", () => {
    expect(classifyExternalArtifact("board.json")).toBe("circuit-json");
    expect(classifyExternalArtifact("PCB.NET")).toBe("kicad-netlist");
    expect(classifyExternalArtifact("bom.csv")).toBe("bom-csv");
    expect(classifyExternalArtifact("mount.step")).toBe("mechanical-reference");
    expect(classifyExternalArtifact("enclosure.stl")).toBe("mechanical-reference");
    expect(classifyExternalArtifact("firmware.ino")).toBe("firmware-reference");
    expect(classifyExternalArtifact("secrets.txt")).toBe("unsupported");
  });
  it("accepts a real tscircuit-style source graph without inventing physical truth", () => {
    const original = [{type:"source_component",source_component_id:"source_component_0",name:"R1"},
      {type:"source_net",source_net_id:"source_net_0",name:"POWER"}];
    expect(parseCircuitJsonArtifact(JSON.stringify(original))).toEqual(original);
    expect(parseCircuitJsonArtifact(JSON.stringify({documents:original}))).toEqual(original);
    expect(parseCircuitJsonArtifact(JSON.stringify({circuit_json:original}))).toEqual(original);
  });
  it("rejects malformed document types, JSON, empty and oversized submissions", () => {
    expect(() => parseCircuitJsonArtifact("not json")).toThrow(/syntax/);
    expect(() => parseCircuitJsonArtifact("{}")).toThrow(/documents/);
    expect(() => parseCircuitJsonArtifact('[{"source_component_id":"R1"}]')).toThrow(/string type/);
    expect(() => parseCircuitJsonArtifact('[]')).toThrow(/documents/);
    expect(() => parseCircuitJsonArtifact("x".repeat(4*1024*1024 + 1))).toThrow(/4 MB/);
  });
  it("accepts standard CSV, prices, double quotes and embedded commas", () => {
    const result = parseBomCsvArtifact('Name,Qty,Unit Cost (USD)\r\n"DC motor, recovered",2,0\r\n"PCB ""donor""",1,3.5\r\n');
    expect(result.itemCount).toBe(3);
    expect(result.parts).toHaveLength(2);
    expect(result.parts[0].name).toBe("DC motor, recovered");
    expect(result.parts[0].quantity).toBe(2);
    expect(result.parts[1].name).toBe('PCB "donor"');
  });
  it("accepts OpenBlueprint BOM's summary TOTAL footer as a non-part", () => {
    const result = parseBomCsvArtifact("Name,Role,Category,Domain,Qty,Unit Cost (USD),Subtotal (USD)\nMotor,Drive,actuator,electrical,2,0,0\nTOTAL,,,,,,0\n");
    expect(result.parts).toHaveLength(1);
    expect(result.itemCount).toBe(2);
  });
  it("rejects quantity guessing, missing identification and invalid row shape", () => {
    expect(() => parseBomCsvArtifact("Name,Qty\nMotor,0\n")).toThrow(/quantity/);
    expect(() => parseBomCsvArtifact("Name,Qty\nMotor,2.5\n")).toThrow(/quantity/);
    expect(() => parseBomCsvArtifact("Thing,Cost\nMotor,2\n")).toThrow(/quantity column/);
    expect(() => parseBomCsvArtifact("Name,Qty\nMotor,2,EXTRA\n")).toThrow(/column count/);
  });
  it("catches the two-motor versus one-motor regression without guessing part identity", () => {
    const upstream = parseBomCsvArtifact("Name,Qty\nDC motor,2\nESP32,1\n");
    const compared = reconcileExternalBomProposal(upstream, [
      {description:"DC motor",qty:1},
      {description:"ESP32",qty:1},
    ]);
    expect(compared.status).toBe("review_required");
    expect(compared.matches).toBe(1);
    expect(compared.conflicts).toEqual([{part:"DC motor",externalQuantity:2,hsQuantity:1}]);
  });
  it("preserves authority gaps when product BOM is absent or aliases do not match", () => {
    const upstream = parseBomCsvArtifact("Name,Qty\nRecovered motor,2\n");
    const absent = reconcileExternalBomProposal(upstream, null);
    expect(absent.status).toBe("unavailable");
    const unknown = reconcileExternalBomProposal(upstream, [{description:"Motor, donor A",qty:2}]);
    expect(unknown.status).toBe("review_required");
    expect(unknown.unmatched).toContain("Recovered motor");
    expect(unknown.missing).toContain("Motor, donor A");
  });
  it("does not turn matching quantities into engineering validation", () => {
    const result = reconcileExternalBomProposal(parseBomCsvArtifact("Name,Qty\nMotor,2\n"), [
      {description:"Motor",qty:2},
    ]);
    expect(result.status).toBe("exact_label_parity");
    expect(result.note).toContain("unverified");
  });
  it("reads real binary STL triangle geometry without inventing length units", () => {
    const bytes = new ArrayBuffer(134);
    const view = new DataView(bytes);
    view.setUint32(80, 1, true);
    const vertices = [[1,2,3],[4,2,3],[1,8,3]];
    vertices.flat().forEach((n,i) => view.setFloat32(96+i*4,n,true));
    const mesh = inspectBinaryStlArtifact(bytes);
    expect(mesh.triangles).toBe(1);
    expect(mesh.bounds.extent).toEqual([3,6,0]);
    expect(mesh.units).toContain("unknown");
    expect(mesh.manufacturable).toBe(false);
    expect(mesh.physicallyVerified).toBe(false);
  });
  it("rejects malformed, truncated or infinite STL geometry", () => {
    expect(() => inspectBinaryStlArtifact(new ArrayBuffer(5))).toThrow(/84-byte/);
    const incomplete = new ArrayBuffer(134);
    const view = new DataView(incomplete);
    view.setUint32(80, 2, true);
    expect(() => inspectBinaryStlArtifact(incomplete)).toThrow(/triangle count/);
    view.setUint32(80, 1, true);
    view.setFloat32(96,Infinity,true);
    expect(() => inspectBinaryStlArtifact(incomplete)).toThrow(/nonfinite/);
  });
  it("refuses unsupported, empty or too large files", () => {
    expect(() => validateExternalFile({name:"design.exe",size:10})).toThrow(/Supported/);
    expect(() => validateExternalFile({name:"design.json",size:0})).toThrow(/nonempty/);
    expect(() => validateExternalFile({name:"design.json",size:4*1024*1024+1})).toThrow(/4 MB/);
    expect(validateExternalFile({name:"board.json",size:100})).toBe("circuit-json");
  });
});
