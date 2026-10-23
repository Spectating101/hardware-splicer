import { describe, expect, it } from "vitest";
import {
  compareWokwiCandidateToHsBom, isWokwiDiagramObject, parseWokwiDiagramArtifact,
} from "./wokwiInterop.js";

const diagram = () => ({
  version: 1, author: "HS independent challenge", editor: "wokwi",
  parts: [
    { id: "esp", type: "wokwi-esp32-devkit-v1", top: 0, left: 0, attrs: {} },
    { id: "temperature", type: "wokwi-dht22", attrs: { temperature: "24" }},
    { id: "display", type: "board-ssd1306", attrs: { i2cAddress: "0x3c" } },
  ],
  connections: [
    ["temperature:VCC", "esp:3V3", "red", []],
    ["temperature:GND", "esp:GND.1", "black", []],
    ["temperature:SDA", "esp:D4", "green", []],
    ["display:VCC", "esp:3V3", "red", []],
    ["display:GND", "esp:GND.2", "black", []],
    ["display:SCL", "esp:D22", "blue", []],
    ["display:SDA", "esp:D21", "yellow", []],
  ],
});

describe("documented Wokwi-to-HS provider bridge", () => {
  it("reads genuine v1 diagram schema preserving 3 distinct components and 7 pin connections", () => {
    const original = diagram();
    expect(isWokwiDiagramObject(original)).toBe(true);
    const x = parseWokwiDiagramArtifact(JSON.stringify(original));
    expect(x.original_part_count).toBe(3);
    expect(x.mapped_part_count).toBe(3);
    expect(x.original_connection_count).toBe(7);
    expect(x.mapped_connection_count).toBe(7);
    expect(x.status).toBe("family_mapping_only");
    expect(x.nodes.map(n=>n.source_part_id)).toEqual(["esp", "temperature", "display"]);
    expect(x.connections.find(w=>w.from.source_endpoint==="temperature:SDA").from.hs_pin_candidate).toBe("DATA");
    expect(x.connections.find(w=>w.to.source_endpoint==="esp:D21").to.hs_pin_candidate).toBe("GPIO21");
    expect(x.nodes[1].source_attributes.temperature).toBe("24");
    expect(x.authority).toBe("external_simulation_proposal");
  });

  it("compares same-count recognized Wokwi parts to existing HS BOM, not fabricated measured truth",()=>{
    const x=parseWokwiDiagramArtifact(JSON.stringify(diagram()));
    const comparison=compareWokwiCandidateToHsBom(x, [
      {module_id:"esp32-devkit",qty:1},
      {module_id:"dht22",qty:1},
      {module_id:"ssd1306-128x64",qty:1},
    ]);
    expect(comparison.status).toBe("family_quantity_parity");
    expect(comparison.matches).toHaveLength(3);
    expect(comparison.note).toContain("Physical donor identity");
  });

  it("detects two-vs-one quantity conflict for equivalent families while not inventing missing parts",()=>{
    const doc=diagram();
    doc.parts.push({id:"temperature2",type:"wokwi-dht22"});
    const x=parseWokwiDiagramArtifact(JSON.stringify(doc));
    const r=compareWokwiCandidateToHsBom(x,[{module_id:"dht22",qty:1}]);
    expect(r.status).toBe("review_required");
    expect(r.excess).toContainEqual({module:"dht22",wokwi:2,hs:1});
    expect(r.excess).toContainEqual({module:"esp32-devkit",wokwi:1,hs:0});
    expect(r.excess).toContainEqual({module:"ssd1306-128x64",wokwi:1,hs:0});
  });

  it("preserves unsupported components and unmapped pin references, never silently removes wires",()=>{
    const doc=diagram();
    doc.parts.push({id:"mysterious_driver",type:"custom-donor-h-bridge"});
    doc.connections.push(["mysterious_driver:OUT_A","temperature:NC","green",[]]);
    const x=parseWokwiDiagramArtifact(JSON.stringify(doc));
    expect(x.status).toBe("partial_mapping");
    expect(x.nodes).toHaveLength(4);
    expect(x.connections).toHaveLength(8);
    expect(x.unmapped_part_ids).toEqual(["mysterious_driver"]);
    expect(x.unmapped_connections).toHaveLength(1);
    expect(x.mapped_connection_count).toBe(7);
    expect(x.nodes[3].hs_module_candidate).toBeNull();
  });

  it("fails closed for duplicate IDs, dangling connection, invalid shape and untyped pins",()=>{
    const d=diagram();d.parts.push({...d.parts[1]});
    expect(()=>parseWokwiDiagramArtifact(JSON.stringify(d))).toThrow(/Duplicate/);
    const d2=diagram();d2.connections.push(["ghost:A","esp:GND.1","black",[]]);
    expect(()=>parseWokwiDiagramArtifact(JSON.stringify(d2))).toThrow(/unknown part/);
    expect(()=>parseWokwiDiagramArtifact("{}")).toThrow(/Not a Wokwi/);
    expect(()=>parseWokwiDiagramArtifact("{bad")).toThrow(/syntax/);
    expect(()=>parseWokwiDiagramArtifact(JSON.stringify({...diagram(),parts:[]}))).toThrow(/no parts/);
  });

  it("does not mistake Wokwi JSON for tscircuit Circuit JSON and reports unknown HS BOM",()=>{
    const x=parseWokwiDiagramArtifact(JSON.stringify(diagram()));
    expect(compareWokwiCandidateToHsBom(x,null).status).toBe("unavailable");
    expect(isWokwiDiagramObject([{type:"source_component"}])).toBe(false);
  });
  it("accepts documented Wokwi virtual serial monitor endpoints and preserves unmapped GPIO14",()=>{
    const doc = {
      version:1, author:"public Wokwi format", editor:"wokwi",
      parts:[
        {type:"wokwi-esp32-devkit-v1",id:"esp",attrs:{}},
        {type:"wokwi-dht22",id:"dht1",attrs:{}},
      ],
      connections:[
        ["esp:TX0","$serialMonitor:RX","",[]],
        ["esp:RX0","$serialMonitor:TX","",[]],
        ["dht1:GND","esp:GND.1","black",[]],
        ["dht1:VCC","esp:3V3","red",[]],
        ["dht1:SDA","esp:D14","green",[]],
      ],
    };
    const result=parseWokwiDiagramArtifact(JSON.stringify(doc));
    expect(result.original_part_count).toBe(2);
    expect(result.mapped_part_count).toBe(2);
    expect(result.original_connection_count).toBe(5);
    expect(result.mapped_connection_count).toBe(2);
    expect(result.connections[0].to.source_endpoint_kind).toBe("wokwi_serial_monitor_virtual");
    expect(result.unmapped_connections).toHaveLength(3);
    expect(result.connections[4].to.hs_pin_candidate).toBeNull(); // GPIO14 lacks an HS verified pad mapping
    expect(result.status).toBe("partial_mapping");
  });

});
