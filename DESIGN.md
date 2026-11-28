---
name: Hardware Splicer Workbench
description: A docked engineering editor on a near-black ground. The pipeline sits in the middle, and every label comes from the engine.
colors:
  ground: "#0f1114"
  panel: "#181b1f"
  raised: "#20242a"
  hover: "#262b32"
  line: "#2a2f36"
  line-strong: "#363c45"
  text: "#e4e7eb"
  text-2: "#aab2bc"
  text-3: "#98a1ac"
  accent: "#3ebd86"
  accent-bright: "#52cc97"
  accent-ink: "#062014"
  accent-soft: "rgba(62, 189, 134, 0.14)"
  accent-line: "rgba(62, 189, 134, 0.55)"
  clean: "#3ebd86"
  failed: "#f0645c"
  recorded: "#c3cad3"
  not-run: "#8a939e"
  unknown: "#e0a43e"
typography:
  title:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0"
  headline:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.45
  station-title:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 600
    lineHeight: 1.25
  body:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  section-head:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 600
  meta:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.35
  prop-label:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "11.5px"
    fontWeight: 400
  mono:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
  mono-tag:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "11px"
    fontWeight: 500
rounded:
  xs: "4px"
  sm: "5px"
  md: "6px"
  panel: "8px"
  overlay: "10px"
  pill: "10px"
spacing:
  gap: "6px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  topbar: "44px"
  explorer: "256px"
  inspector: "340px"
  console: "112px"
components:
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.panel}"
  button:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    height: "30px"
    padding: "0 12px"
  button-hover:
    backgroundColor: "{colors.hover}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.md}"
    height: "30px"
    padding: "0 12px"
  button-primary-hover:
    backgroundColor: "{colors.accent-bright}"
  button-ghost:
    textColor: "{colors.text-2}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
  button-ghost-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.text}"
  input-field:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "6px 8px"
  search-field:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    height: "30px"
    padding: "0 8px"
  tab:
    textColor: "{colors.text-2}"
    height: "30px"
    padding: "0 12px"
  tab-active:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
  tree-row:
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    height: "26px"
    padding: "3px 8px 3px 26px"
  tree-row-selected:
    backgroundColor: "{colors.accent-soft}"
  chip:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    typography: "{typography.meta}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
  row-tag:
    textColor: "{colors.text-3}"
    typography: "{typography.mono-tag}"
    rounded: "{rounded.xs}"
    padding: "0 5px"
  status-pill:
    textColor: "{colors.text-2}"
    typography: "{typography.meta}"
    rounded: "{rounded.pill}"
    padding: "1px 8px"
  station-number:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    padding: "0 7px"
  station-number-selected:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
  command-palette:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.overlay}"
    width: "min(640px, calc(100vw - 24px))"
---

# Design System: Hardware Splicer Workbench

## Overview

**Creative North Star: "The Docked Bench"**

Hardware Splicer opens straight into the tool, as Unity, Premiere or a JetBrains IDE do. It has no front door and no dashboard of cards. The screen is one docked editor: rounded panel islands sit on a darker ground, and the gaps between the islands are the resize handles. The explorer is on the left, the pipeline view in the middle, the inspector on the right and the console under the middle. The pipeline, HS's fourteen-step board spine, is drawn as stations on two lines with the gates marked. A user should feel they are at a working instrument, not being shown a presentation.

Density is set for a large desk screen: 13px body text, 26px tree rows and 6px gutters. There is a single accent. Colour on the screen mostly means state. The engine decides every state: the UI shows outcomes as the backend records them, and "not run" and "not recorded" are drawn as clearly as "clean" or "failed". Phones get one panel at a time, for status checks.

**Scope.** This world currently covers the Workbench (`apps/splice-ui/src/bench/`, the `/` route) and is the app's direction from here on. The older screens (Projects, Library, Advanced and the project bench) still use the earlier light theme in `apps/splice-ui/src/styles.css`. They have not been migrated and are not part of this system. Do not borrow tokens from them, and do not treat their look as precedent.

**Key Characteristics:**
- Near-black ground, slightly lighter panel islands and hairline rules. Depth comes from tone, not from shadows.
- One green accent, used for selection, gates and Run.
- Outcome marks: a filled, hollow or dashed circle, so a state reads without relying on colour.
- IBM Plex Sans for the interface. Plex Mono only for ids, paths, numbers, field names and keys.
- One drawn icon set: 16px grid, 1.5px stroke, round caps, inline SVG.

## Colors

A cool graphite neutral ramp with one HS green and a small set of outcome colours. Most of the screen is grey. When colour appears, it reports something.

### Primary
- **HS Green** (accent): the selection, the gates and the primary action, and nothing else. It is used for the selected tree row's tint and ring, the selected station's number and title, a gate station's number outline, the GATE tag, the active-tab underline, the Run button, links, the required-field mark, focus outlines and the resize-handle highlight.
- **Lit Green** (accent-bright): the primary button's hover fill only.
- **Green Ink** (accent-ink): text and glyphs placed on a solid green fill (the Run button, the brand mark, the selected station number).
- **Green Wash** (accent-soft) and **Green Rule** (accent-line): the translucent pair for selected rows, active segments, the active console row and the focus border on inputs.

### Neutral
- **Bench Ground** (ground): the window behind the panels. It is also used as the recessed fill inside panels, for text inputs, the JSON result tree and argument blocks.
- **Panel Island** (panel): the fill of every docked panel (explorer, viewport, inspector, console) and of the command palette.
- **Raised Slate** (raised): one step up inside a panel: buttons, the active tab, the explorer filter field, chips.
- **Hover Slate** (hover): the hover fill for rows, tabs and ghost buttons.
- **Hairline** (line) and **Strong Hairline** (line-strong): 1px dividers between panel regions, and the borders of inputs, buttons, tags and station numbers.
- **Bench White** (text): primary text.
- **Steel** (text-2): secondary text: descriptions, inactive tabs, section heads in the view.
- **Pewter** (text-3): tertiary text: counts, timestamps, field types, record paths, placeholders.

### Outcome colours
These colours are reserved for run outcomes and status, always paired with an outcome mark or a text label.
- **Clean** (clean, same hue as HS Green): the record shows a clean result. The engine dot shows "connected".
- **Failed Coral** (failed): failed runs, error text, the problem list (8% fill with a 28% border), invalid field borders, the "offline" engine dot.
- **Recorded Silver** (recorded): the record holds a result with no clean or failed verdict. It is also the "all tools" bar in comparisons.
- **Not-run Grey** (not-run): a step not run on this build. The mark is hollow.
- **Amber Unknown** (unknown): not recorded. The mark is dashed. Amber is also used for "candidate" tags and "problems" statuses.

### Named Rules
**The One Green Rule.** Green means selected, gate or the primary action. A second accent is never added, and green is never used for decoration. If something is green, the user should be able to say which of the three it is.

**The Verbatim State Rule.** Outcome colours appear only where the engine supplied an outcome. The UI never computes a state colour, and it never shows a "ready" or "build-ready" badge.

## Typography

**Body Font:** IBM Plex Sans (with system-ui, sans-serif), self-hosted at 400/500/600/700.
**Label/Mono Font:** IBM Plex Mono (with ui-monospace, monospace), self-hosted at 400/500.

**Character:** a technical grotesque with its mono sibling, the type of an engineering tool. There is no display face; the largest text on the screen is 16px. Tabular numerals are on everywhere.

### Hierarchy
- **Title** (600, 16px, 1.3): the inspector heading, which names what is selected.
- **Headline** (600, 15px): the run bar heading over the spine, and the heading of each measured record.
- **Station Title** (600, 13.5px, 1.25): step names on the spine.
- **Body** (400, 13px, 1.45): all interface text. Prose blocks are capped at 60ch; empty-state copy at 44ch.
- **Section Head** (600, 12.5px, Steel): sub-heads in the view, such as "How the run stops" and "Not checked on this run", and the console heading.
- **Meta** (400, 12px): runs lines, legends, chips, the last run, the engine state.
- **Prop Label** (400, 11.5px, Pewter): `dt` labels in the inspector, field help, palette kinds.
- **Mono** (400, 12px): ids, paths, revision tags and values.
- **Mono Tag** (500, 11px): row tags (example, integrated, candidate), counts, field names, `kbd`. The GATE tag is the one uppercase mono label, tracked at 0.04em.

### Named Rules
**The Mono-for-Machine Rule.** Plex Mono marks things a machine wrote or reads: ids, paths, numbers, schema field names and shortcut keys. Prose, labels and headings are in Plex Sans.

**The No Display Rule.** The bench has no hero text. Hierarchy comes from weight (400/500/600) and the steps between 11px and 16px, not from size jumps.

## Layout

The layout is a five-track grid under a 44px top bar: explorer (256px by default), a 6px gutter, the centre (minimum 360px), a 6px gutter and the inspector (340px by default). The centre column is split again into the viewport and a console (112px by default). Every gutter is a drag handle. When hovered or focused, it shows a 2px green line along its middle stretch. The window has a 6px margin on the sides and bottom. Pane sizes persist per browser.

The spine is a seven-column station grid, giving two lines of seven. It is container-queried on the viewport: five columns below 740px and two below 620px. Each station is at least 112px tall. A 1px rail runs through the station heads, and the rail turns into a 2px green line on the selected station.

The spacing rhythm is 4/6/8/12/16. Panel headers are padded at 14px 16px. Tree rows are indented at 26px, and nested rows at 38px.

Below 1360px the top-bar links are hidden and the spine notes stack into one column. Below 860px (phone) the top bar grows to 48px, the jump box shrinks to an icon, and a pane switcher (Explorer, View, Inspector, Console) shows one panel at a time.

## Elevation & Depth

The bench is flat. Depth is tonal: ground, then panel, then raised, then hover, each step slightly lighter. Selection is drawn with a 1px inset green ring and a green wash, never with a lift. The only floating surface is the command palette (Ctrl K). It sits over a 55% near-black scrim, carries one ambient shadow, and rises 6px as it fades in.

### Shadow Vocabulary
- **Palette Float** (`box-shadow: 0 18px 44px rgba(0, 0, 0, 0.3)`): the command palette only.
- **Selection Ring** (`box-shadow: inset 0 0 0 1px` Green Rule): selected tree rows. This is a ring, not elevation.
- **Field Focus Halo** (`box-shadow: 0 0 0 2px` Green Wash): focused text inputs, together with a Green Rule border.

### Named Rules
**The Islands Rule.** Panels have no border and no shadow. They separate from the ground by tone alone, and the 6px gap between them is the handle. Only the command palette may float above them.

## Shapes

Corners are gently rounded and scale with the size of the object: 4px on tags, kbd keys and the focus outline; 5px on rows, chips, segments and ghost buttons; 6px on buttons, inputs, the jump box and inner blocks; 8px on panels; 10px on the command palette. Station numbers and status labels are 10px pills. Outcome marks and dots are circles. Tabs round only their top corners (6px 6px 0 0) and sit on the hairline under the tab strip. Keys in `kbd` have a 2px bottom border, so they read as a physical key.

## Components

### Buttons
The buttons are quiet and compact; the only loud one is Run.
- **Shape:** 30px tall, 6px corners, 0 12px padding, weight 500.
- **Default:** Raised Slate fill with a Strong Hairline border. On hover it moves to Hover Slate with a slightly lighter border.
- **Primary (Run):** HS Green fill and border, Green Ink text, weight 600; Lit Green on hover. There is one per inspector, at the bottom right of the inspector footer.
- **Ghost:** no fill, Steel text, 12px. On hover it gets a Hover Slate fill and Bench White text. Used for console actions such as Clear.
- **Disabled:** 55% opacity, default cursor.
- **Focus:** a 2px green outline with a 1px offset, everywhere in the bench.

### Chips and Tags
- **Chip:** Raised Slate fill, 5px corners, 12px text. Linked chips (the outside tool a step runs) get a Green Rule border on hover.
- **Row tag:** 11px mono, 4px corners, Strong Hairline border, Pewter text. "integrated" is green, "candidate" amber and "reference" Steel.
- **Status pill:** 12px/500 on a 10px pill with a border tinted by state (ok green, problems amber, error coral, running white).

### Cards / Containers
- **Corner Style:** 8px panels.
- **Background:** Panel Island. Recessed blocks inside a panel (JSON tree, args) use Bench Ground with 6px corners.
- **Shadow Strategy:** none (see the Islands Rule).
- **Border:** none on panels. Hairlines divide the header, body and footer inside them.
- **Internal Padding:** 14px 16px for panel heads and bodies; 10px 12px for the footer.

### Inputs / Fields
- **Style:** Bench Ground fill, 1px Hairline border, 6px corners, 6px 8px padding. Values that are paths or ids are set in mono 12px.
- **Focus:** Green Rule border plus a 2px Green Wash halo. No outline.
- **Error:** a coral border at 60%, with an 11.5px coral message below. The field label row shows the mono field name, a green "required" mark and the type in Pewter on the right.
- **Explorer filter:** a 30px Raised Slate field with an icon. While focused it has a Green Rule border.

### Navigation
- **Top bar:** the HS monogram (a 24px green square with ink letters), the product name, a slash breadcrumb and the jump box (up to 420px wide, with a `kbd` hint). It also holds plain text links to the older screens and the engine state dot.
- **Explorer tree:** 26px rows with a chevron that rotates 90° over 140ms. Each section head is 600 weight with a mono count. Rows carry a step number, a label, a trailing outcome mark or tag, and a green "gate" sub-label. On hover a row gets a Hover Slate fill; when selected it gets the Green Wash with an inset ring.
- **View tabs:** 30px. Inactive tabs are Steel; the active tab gets a Raised Slate fill and a 2px green underline inset 8px. A pulsing 6px green dot marks a tab that is busy.
- **Command palette:** 640px wide, rows in three columns (kind, label, hint), the active row in Green Wash.

### Spine Station (signature)
Each pipeline step is a station on a rail. The head holds a numbered pill (two-digit mono-width number, with a green outline when the step is a gate and a solid green fill when it is selected), a GATE tag when it is a gate, and the outcome mark on the right. Below come the title, a line naming the tool that ran the step and its owner, and a foot line above a hairline giving what the record measured. A failed foot line is coral, an unrecorded one amber, and one not run on this build is Steel.

### Outcome Mark (signature)
A 10px circle with a 1.5px stroke. It is filled for a recorded result (clean, failed or recorded), hollow for not run, and dashed (2/1.6) for not recorded. A legend over the spine names all five states. Labels come verbatim from the engine.

### Console
The console has a 34px header with an All/Problems segmented control and a ghost Clear button. Below it are 12.5px log rows: a mono timestamp, a 7px status dot, the tool and the text, truncated with an ellipsis, and the duration. A new row arrives with a green wash that fades over 900ms. A running row's dot pulses.

### Result Tree
The engine's JSON is shown as a collapsible tree on Bench Ground, with a hairline guide on each child level. The tree has its own syntax palette: keys soft blue (#9cc3ff), strings pale olive (#d7e0a3), numbers apricot (#f2b37a), booleans and null aqua (#7fd6d1). These four hues appear only in the result tree.

## Do's and Don'ts

### Do:
- **Do** put every new panel on Panel Island (#181b1f) with 8px corners and a 6px ground gap. The gap is the separator.
- **Do** keep HS Green for selection, gates and the one primary action per panel.
- **Do** pair every outcome colour with its filled, hollow or dashed mark or its text label, and show "not run" and "not recorded" as clearly as "clean" and "failed".
- **Do** set ids, paths, numbers and schema field names in IBM Plex Mono 12px or 11px, and everything else in IBM Plex Sans.
- **Do** draw new icons on the 16px grid with a 1.5px stroke and round caps, inline as SVG in currentColor.
- **Do** cap prose at 60ch inside wide panels.
- **Do** respect reduced motion: every animation and transition in the bench is switched off under `prefers-reduced-motion`.

### Don't:
- **Don't** build a marketing front door, a hero or a dashboard of cards. The first thing on screen is the docked editor.
- **Don't** compute, upgrade or decorate a state in the UI. Never show a "ready" or "build-ready" badge; states and labels come from the engine verbatim.
- **Don't** add a second accent colour, or use the outcome colours for decoration.
- **Don't** put borders or drop shadows on docked panels. Only the command palette floats.
- **Don't** add small uppercase eyebrow or kicker labels above headings. The GATE tag on a station is a state marker, not a section label.
- **Don't** take tokens or patterns from the older light screens in `styles.css`. They have not been migrated and are not part of this system.
