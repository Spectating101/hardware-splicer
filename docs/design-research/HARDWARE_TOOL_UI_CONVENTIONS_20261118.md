# Hardware engineering tool interface conventions (2026-11-18)

Research by a Claude Sonnet researcher from public product pages and documentation, captured headlessly with no logins. Tags: [img] UI image or live page seen, [doc] documentation text fetched, [snip] search snippet only, [mem] model memory. Real UI was seen for KiCad, Onshape, Altium BOM Portal, InvenTree, Interactive HTML BOM, AllSpice and OpenBOM; Fusion, SolidWorks, Flux, Arena, Duro, Fusion Manage and the Altium 365 web viewer are from documentation, snippets or memory.

## Per tool

| Tool | Home and main layout | Checks and findings | Revision compare | Part change and status |
|---|---|---|---|---|
| KiCad 9 PCB editor [img] | Opens on the board canvas. Layers/Objects/Nets panel right, selection filter below, tool columns on both edges, counts bar at the bottom. | DRC dialog with tabs Violations, Unconnected, Schematic Parity, Ignored; error/warning filters with counts; violations can be excluded; markers on the board. Click-to-jump confirmed in 6.0 docs [doc]. | Footprint-vs-library compare with Summary and Visual tabs. | Update-from-schematic dialog. No lifecycle labels. |
| Onshape [img, doc] | Part Studio, feature tree left; versions/history panel with a coloured branch graph. | Rebuild errors on the tree [mem]. | Base blue, Target red. Feature list shows only differences by default with ≠ < > icons. A slider on the 3D view blends Base and Target. Swap button. Versions immutable and branchable. | Releases are a separate workflow [mem]. |
| Fusion, SolidWorks [snip, mem] | Browser tree left; Fusion timeline strip at the bottom; SolidWorks FeatureManager with rollback bar. | SolidWorks "What's Wrong" list; clicking selects the tree item [snip]. | Timeline rollback. | n/a |
| Altium BOM Portal [img, doc] | Home is a BOM table. Tabs: Main View, Supply Chain, Issues, Releases, Dashboard. | Issues tab groups findings by category and filters the table; affected cells tinted, warning icon on the row; health score out of 10. | BOM Compare: Added / Removed / Modified / Not Modified with colour. | Extra MPNs become Alternate sub-rows under the line; Alternates tab (Part Choices, Suggested). Lifecycle column. |
| Altium 365 project and web viewer [doc, snip] | Project tabs: Design, Releases, Tasks, History, Design Reviews, Assembly. Viewer sub-views: schematic, 2D, 3D, BOM. | Comment pins on the design plus a Comments panel with resolve; deep links zoom to the object. | History timeline, release BOM compare. | Releases are the immutable state. |
| Flux [snip] | Editor canvas, AI chat panel, object tree and inspector on the right. | Copilot answers in chat. | n/a | n/a |
| AllSpice [img, doc] | Left nav: Design, Reviews, DRCY, Issues, History, Releases. A review is a pull request with Conversation / Commits / Changes tabs and a changed-file tree. | Comments anchored to schematic or PCB regions. The AI checker posts a comment with a per-pin table (pin, net, correct?, analysis) citing the datasheet [img]. | Diff filter tree by object type with counts; red/green overlay [img]. | Review closes by merge or revert. |
| Arena, Duro, Fusion Manage [snip, doc] | BOM and item records. | n/a | Duro compares one other revision; Fusion Manage compares pending against latest released. | Change order with an Affected Items tab (From, To). Release applies the lifecycle change to every item; approved change orders are frozen. States: Working, Pending release, Released. |
| OpenBOM [img] | Spreadsheet-style BOM with an Item Revisions side panel. | n/a | Two revisions side by side, differences in colour. | Change request attached to a change order, approved, then the revision increments. |
| InvenTree [img] | Part page with a left tab rail (Details, Stock, BOM, Used In, Suppliers). Header chips In Stock / Available / Required. | BOM banner "BOM validated by X on date", reverts to "Not Validated" on edit. | BOM compare. | Part is the archetype, stock item the physical lot. Substitutes per BOM line; their stock counts toward the line. |
| Interactive HTML BOM [img] | BOM table left, board right. | Selecting a row highlights the part on the board; clicking a footprint finds its row [doc]. | n/a | Sourced / Placed checkboxes per row. |

## Shared conventions engineers expect

1. Navigator left, canvas centre, properties/inspector right.
2. The BOM table is the shared spine; selecting a row selects the part on the design and the reverse.
3. Findings live in two places: a list with severity counts, and markers on the design; clicking the list jumps to the object; findings can be filtered, excluded or waived (KiCad keeps exclusions in their own tab).
4. Compare is Base against Target, differences only by default, per-item added/removed/changed icons, two colours, a swap button.
5. Alternates belong to a BOM line as ranked sub-rows or an Alternates tab, not a global replacement.
6. Changing a released part goes through a change order listing affected items From/To, frozen once approved; design-stage items edit freely.
7. Status is a process state a person sets (working, in review, released); software health is shown separately as counts or scores. Closest precedent for authority labels: InvenTree's "validated by X on date" that resets on change.
8. History is a tab, not the home screen.

## Verdict on the conventional three-pane proposal

Matches convention: three columns; Single/Compare with two colours; alternates next to the part; no "ready" badge.
Differs: a narrow list cannot hold a BOM (it is a table); requirements and parts mixed; 3D alone is a weak compare surface (pair with a differences list); blockers at the bottom of a pane get missed (use persistent counts); evidence only in a side list (convention is list plus markers).

Screenshots (scratchpad ui-research/): kicad-pcb-ui, kicad-drc-violations, onshape-compare-flyout, onshape-compare-graphic, onshape-version-graph, altium-bomportal-main-supply, altium-bomportal-issues, allspice-hub-pr-files, allspice-diff-filters, allspice-drcy, inventree-part-overview, inventree-bom-substitute-validated, inventree-bom-compare, openbom-montage, ihtmlbom-picprog, ihtmlbom-picprog-selected.
