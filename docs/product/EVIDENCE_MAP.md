# Hardware Splicer evidence map

The same candidate may have strong evidence at one layer and no authority at the next. Review the layers independently.

```text
Frozen source identity
  commit + tag + release hash
            |
            v
Software and interface evidence
  unit/integration tests + exact-head CI + API/MCP behavior
            |
            v
Model/agent evidence
  frozen scenarios + traces + bounded primary-source demonstration
            |
            v
CAD and package evidence
  editable KiCad + ERC/DRC/parity + deterministic fabrication/FCT ZIP
            |
            v
Physical evidence                         CURRENT STOP
  fabricated identity + inspection + measurements   <--- NOT PRESENT
            |
            v
Operational/production evidence
  repeated units + environmental/reliability data    <--- NOT PRESENT
```

## Authority table

| Question | Current answer | Authoritative object |
|---|---|---|
| Which source revision? | frozen | commit `f892facd67c5124e2362860ebc999625afedc5d5` |
| Which public package? | frozen and reproducible | tag `gauntlet-spi-flash-adapter-v1-20260916` and package SHA-256 |
| Does software execute as tested? | internally supported | exact-head CI and local targeted tests |
| Can an agent complete every scenario reliably? | not established | full frozen-corpus result is pending |
| Is the CAD internally consistent? | internally supported | reference-design verification receipts |
| Is the manufacturing handoff complete? | packaged | deterministic remote-FCT ZIP and audit |
| Does fabricated hardware work? | unproven | no revision-bound physical measurements exist |
| Is it independently validated? | no | no external verdict/receipt exists |
| Is it production-ready? | not claimed | qualification evidence does not exist |

## Review rule

Never use evidence from an earlier row to answer a later row. In particular, a green workflow, clean DRC, package checksum, or model trace cannot establish physical correctness.
