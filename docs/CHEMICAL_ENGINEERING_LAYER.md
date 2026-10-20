# Chemical engineering — bounded initial slice

Hardware Splicer represents chemical alongside mechanical, electrical, firmware
and other disciplines in the canonical MachineProject. The chemical engine is not
a second project store and does not create independent release state.

## Actually implemented

- GET /v1/engineering/chemical/engines — read-only optional-engine discovery.
- POST /v1/engineering/chemical/molecule/inspect — RDKit molecule parse, canonical
  SMILES, formula, molecular weight, atom count and formal charge; optional package.
- POST /v1/engineering/chemical/properties/inspect — thermo correlation/property
  inspection at declared temperature and pressure; optional package.
- POST /v1/engineering/chemical/process/mass-balance — deterministic
  steady-state overall mass balance and nonreactive component flow checks.
- These endpoints are automatically discoverable/callable through the existing
  canonical HS backend MCP gateway and are tagged chemical in OpenAPI.

Install optional engines separately with: pip install -e '.[chemical]'
Without them, molecule and property endpoints return explicit HTTP 503; no fabricated
fallback values are generated. The mass-balance endpoint uses no external engines.

Example benign nonreactive balance:

    POST /v1/engineering/chemical/process/mass-balance
    {
      "streams": [
        {"stream_id":"feed","direction":"inlet","mass_flow_kg_h":10,
         "components_kg_h":{"water":10}},
        {"stream_id":"product","direction":"outlet","mass_flow_kg_h":10,
         "components_kg_h":{"water":10}}
      ]
    }

## Planning, not completed

- Cantera: reaction systems, transport, equilibria and kinetics. Catalog only.
- PyBaMM: battery electrochemistry. Catalog only.
- pymatgen: solid-state materials. Catalog only.
- DWSIM: external process flowsheets; treat as a separate GPLv3 program.
- Open Reaction Database: source-attributed experimental reaction records;
  distinguish source data CC-BY-SA-4.0 from schema/code Apache-2.0.
- Materials compatibility, hazardous-substance screening, stoichiometry, phase
  calculations and physical verification have not been implemented.

## Engineering evidence boundary

None of the routes certifies material compatibility, exposure safety,
chemical identity, product quality, experimental repeatability or operational
readiness. Input source references are merely caller-declared pointers, not
independently verified sources. Models return their engine, input conditions,
schema version, uncertainty caveats and explicit false authorization flags.

Do not use any computational output by itself to justify laboratory procedures,
chemical synthesis, pressurized systems, battery intervention, manufacturing,
commercial release or physical actuation.

No scientific tool is invoked automatically by the HS agent; agents must
select an operation and supply its bounded inputs through the canonical gateway.
