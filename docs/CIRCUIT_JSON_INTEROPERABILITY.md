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

## Browser workbench

After building and serving the product UI, open:

```text
/circuit-json-import.html
```

The workbench provides a deliberate two-step flow:

1. **Inspect source graph** — resolve components, ports, named nets, traces, and diagnostics.
2. **Compile accepted graph → KiCad** — send the original Circuit JSON through `/v1/netlist-compile` only after structural inspection.

The workbench distinguishes:

- `ready` — structurally compilable with no importer or upstream diagnostics;
- `review_required` — compilable, but unresolved/incomplete references or upstream warnings require disposition;
- `blocked` — no components or no multi-pin electrical nets can be resolved.

A compilable graph has `proposed` authority. It does not become verified or fabrication-authorized through import.

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

This change establishes interoperable electrical source intake. It does not yet preserve every rendered PCB geometry or simulation object in the Hardware Splicer IR. Those objects can remain in the original Circuit JSON artifact and be connected to later viewer, routing, simulation, STEP, and glTF adapters without changing the electrical identity mapping.
