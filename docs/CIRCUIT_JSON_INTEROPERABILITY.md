# Circuit JSON interoperability

Hardware Splicer accepts the source-level graph defined by the tscircuit Circuit JSON ecosystem rather than requiring a Hardware-Splicer-specific simplified export.

## Supported source documents

The importer currently understands:

- `source_component` — stable component ID, reference name, part/value metadata;
- `source_port` — stable port ID, component association, pin number/name/hints;
- `source_net` — named shared electrical net and power/ground metadata;
- `source_trace` — port-to-net or port-to-port electrical connectivity;
- upstream `*_warning` and `*_error` documents as import diagnostics;
- legacy Hardware Splicer `schematic_trace` and `REF.PIN` references for compatibility.

Rendered schematic, PCB, and CAD documents remain attached to the source package but are not used to infer electrical connectivity. The source graph is the authority for interchange.

## Product flow

Circuit JSON intake is part of a larger review workflow:

1. inspect the source graph;
2. compile accepted connectivity into the Hardware Splicer/KiCad spine;
3. open the resulting build in Design Preview;
4. run deterministic engineering review when the optional analyzer is configured;
5. disposition findings before fabrication or bench release.

The interface distinguishes:

- `ready` — structurally compilable with no importer or upstream diagnostics;
- `review_required` — compilable, but unresolved/incomplete references or upstream warnings require disposition;
- `blocked` — no components or no multi-pin electrical nets can be resolved.

A compilable graph has `proposed` authority. Import and compile do not make it verified or fabrication-authorized. External engineering analysis is capped at `observed` authority and also cannot authorize release.

## Inspection API

```http
POST /v1/interchange/circuit-json/inspect
Content-Type: application/json

{
  "source_label": "my-tscircuit-export",
  "documents": [
    {
      "type": "source_component",
      "source_component_id": "source_component_0",
      "name": "R1",
      "ftype": "simple_resistor",
      "resistance": 1000
    }
  ]
}
```

The response includes:

- normalized components and nets;
- a complete Hardware Splicer netlist IR;
- counts and acceptance status;
- unresolved source ports and trace references;
- ambiguous multi-net traces;
- single-pin nets omitted from compilation;
- upstream warnings/errors;
- preserved source IDs and part metadata.

## Connectivity mapping

For named nets, multiple `source_trace` documents that reference the same `source_net_id` are aggregated into one Hardware Splicer net. This is required because Circuit JSON commonly represents each component-to-net connection as a separate trace.

A direct port-to-port `source_trace` with no `connected_source_net_ids` becomes an independent net using its trace name, display name, or stable trace ID.

Unresolved references are recorded in diagnostics and never replaced with invented pins or connections.

## Current boundary

This establishes interoperable electrical source intake. It does not yet project every rendered PCB geometry, simulation object, STEP asset, or glTF object into canonical Hardware Splicer discipline models. Those objects remain in the original Circuit JSON artifact for later viewer, routing, simulation, and mechanical adapters without changing the electrical identity mapping.
