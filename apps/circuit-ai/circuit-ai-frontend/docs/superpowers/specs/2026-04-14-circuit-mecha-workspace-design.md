# Circuit-Mecha Workspace — Design Spec
**Date:** 2026-04-14  
**Status:** Approved, ready for implementation planning

---

## 1. Problem Statement

The Circuit-AI + Mecha-Splicer backends form a complete electromechanical product pipeline — from PCB validation through enclosure design, BOM generation, and manufacturing packaging. The existing frontend exposes none of this depth. It is a marketing website with some route stubs. Worse, it assumes the user already knows what a KiCAD netlist is.

The target user is anyone who wants to build real hardware — from a first-timer who doesn't know the vocabulary, to a contractor who needs to move fast. The design must serve both without making either feel stupid or limited.

---

## 2. Design Philosophy

**JARVIS-first.** The AI is the primary interface. The canvas is the output surface. The user says what they want; JARVIS figures out which backend calls to make, does the work, and narrates the result in plain English. The user never needs to know what a gerber file is to receive one.

**Progressive depth.** Everything starts simple. Complexity reveals itself only when the user is ready for it — either because they clicked into a node, or because JARVIS surfaced it as relevant.

**Canvas as project memory.** The canvas is not a tool the user operates. It is a living record of what JARVIS built. Each node is an artifact. Connections show how artifacts relate. The canvas grows as work gets done.

---

## 3. Information Architecture

Drop the marketing page for now. The product is the workspace.

| Route | Purpose |
|---|---|
| `/workspace` | The entire product — canvas + JARVIS |
| `/workspace/[project-id]` | A named, saved project loaded onto the canvas |
| `/docs` | API reference for developers |
| `/status` | Backend health — what is live, what is mocked |
| `/dashboard/keys` | API key management |
| `/pricing` | Plans |

No account required to start. API key unlocks persistence and advanced features.

---

## 4. Workspace Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo] [Project: untitled ▾]  [ What do you want to build? ]  [● Live] [⚿]  │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│  [JARVIS strip: "I found a critical power issue on your board. → Show me"]      │
├──────────────────────────────────────────────────┬──────────────┤
│                                                  │              │
│                  CANVAS                          │    DRAWER    │
│                                                  │  (slides in  │
│   [Board]──[Validation]──[Manufacturing Pkg]     │   on node    │
│       └──[Mecha Bundle]                          │    click)    │
│                                                  │              │
│                                    [mini-map]    │              │
├──────────────────────────────────────────────────┴──────────────┤
│  [Last JARVIS message]                         [Expand history ↑]│
└─────────────────────────────────────────────────────────────────┘
```

**Top bar:** Always visible. Left: logo + project name (clickable, opens project switcher). Center: JARVIS command input (hero element). Right: backend status dot + API key icon.

**JARVIS strip:** Appears below top bar when JARVIS speaks. Animated slide-in, holds 8s, has a "→ Show me" action that pans canvas to relevant node. Dismisses on interaction.

**Canvas:** Infinite, zoomable (scroll/pinch), pannable (click+drag on empty space). Dark navy background with subtle dot grid. Mini-map bottom-right for orientation.

**Drawer:** Right side, full height. Slides in when any node is clicked. Tabs are node-type-specific. ESC or clicking canvas closes it.

**Bottom bar:** Collapsed JARVIS conversation. Shows last message. "Expand ↑" reveals full conversation history.

---

## 5. First-Time Experience

When `/workspace` loads with no project:

1. Canvas is empty.
2. Center of canvas shows three starter tiles (not a modal, part of the canvas itself):
   - "I have a PCB design and want to check if it's ready to manufacture"
   - "I have spare electronics parts and want to build something profitable"
   - "I have a PCB and want to design an enclosure for it"
3. JARVIS command input has placeholder: *"What do you want to build?"*
4. Clicking a starter tile populates the command input and triggers the workflow automatically.

No onboarding modal. No tutorial overlay. The canvas IS the onboarding.

---

## 6. Node System

All nodes are 220px wide, height auto, placed on the canvas. Each has:
- Node type icon + accent color (top-left badge)
- Status dot (top-right): idle / processing (pulsing) / done / error
- Title (plain English name, not filename)
- 2–3 summary data points
- Hover reveals pill action buttons

### Node Types

**File Node** (slate)
- Triggered by: file drop or upload
- Shows: file name, detected type in plain English ("KiCAD board file"), file size
- Actions: Parse, Remove

**Board Node** (cyan)
- Triggered by: File Node parsed successfully
- Shows: board name, "X components across Y layers", board outline thumbnail
- Actions: Check for issues, List parts, Prepare for manufacturing

**Validation Node** (green if clean / red if critical issues)
- Triggered by: "Check for issues" on Board Node
- Shows: health score 0–100, severity bar (red/orange/yellow counts)
- Actions: See all issues (opens drawer), Package anyway, Fix and re-check

**Manufacturing Package Node** (emerald)
- Triggered by: "Prepare for manufacturing" on Board Node (after validation)
- Shows: files generated (Gerbers, BOM, Pick & Place, DFM report), cost estimate badge
- Actions: Download all, View parts list, Add enclosure

**Mecha Bundle Node** (orange)
- Triggered by: "Add enclosure" or "Build an enclosure" command
- Shows: enclosure dimensions (WxDxH mm), parts count, tiny 3D preview
- Actions: View 3D, Download files, See assembly guide

**Recipe Node** (sky)
- Triggered by: "What can I build?" or inventory input
- Shows: project name, ROI%, estimated build cost, difficulty dot (green/yellow/red)
- Actions: See build instructions, Get parts list, Start this project

**System Node** (purple)
- Triggered by: connecting two or more Board Nodes
- Shows: board count, inferred interface types (CAN, I2C, UART), mini topology diagram
- Actions: Engineer the system, Run simulation, View power tree

### Node Connections

- Bezier curves, not straight lines
- Color matches source node accent
- Dashed + pulsing animation while processing
- Solid when done
- Click a connection to see what data was passed (plain English summary)
- Drag from a node's output handle to create a new connection

---

## 7. JARVIS

JARVIS is the AI layer. It is not a chatbot. It is an ambient co-pilot that:
- Speaks when something happens
- Explains what it found in plain English
- Suggests what to do next
- Does the work when you confirm

### Language Rules

- No jargon unless immediately explained: "Your 5V rail (the power supply line for your main chip) is drawing too much current"
- No rhetorical questions: state observations, then offer next steps
- Short messages: one thing at a time, 1–2 sentences max per strip notification
- Confidence over hedging: "Your board is ready to manufacture" not "It seems like it might possibly be okay"

### JARVIS Message Examples

After file drop:
> "Found a KiCAD board file — 47 components, 4 layers. Looks like a motor controller. Want me to check it for issues?"

After validation finds critical issue:
> "Found 1 critical issue: your power supply can't handle the load. Here's the fix. → See it"

After validation passes:
> "Your board looks clean. Ready to generate the manufacturing files — takes about 30 seconds."

After manufacturing package generated:
> "Done. Gerber files, parts list, and assembly guide are ready. Estimated cost for 5 boards: $47. Want an enclosure too?"

After recipe recommendation:
> "With your parts, the Air Quality Monitor gives you the best return — about 60% ROI if you sell it. Build time: 2.5 hours. Want step-by-step instructions?"

### JARVIS Input

The top bar input accepts:
- Natural language: "validate my board", "what can I build with an Arduino and a BME280 sensor?", "package this for manufacturing"
- File drops directly onto the input bar (same as dropping on canvas)
- Context-aware: if a Board Node is selected, "validate" means validate that board
- No special syntax required

---

## 8. Detail Drawer

Slides in from the right when a node is clicked. Full height of canvas area. 400px wide on desktop, full-screen on mobile.

### Per Node Type

**Board Node**
Tabs: `Overview` | `Issues` | `Structure` | `Parts` | `Manufacture`
- **Overview**: board name, JARVIS summary, stats cards (components, layers, estimated cost)
- **Issues**: sorted by severity. Each issue shows: *What it is* (1 sentence) / *Why it matters* / *How to fix it*. No raw error codes.
- **Structure**: power rails as named cards, connectors with role labels, interfaces (I2C/UART/etc) as plain-language descriptions
- **Parts**: filterable BOM table — Name, Reference, Qty, Est. Cost, Supplier link
- **Manufacture**: big "Generate manufacturing files" CTA, progress indicator, download list when done

**Manufacturing Package Node**
Tabs: `Files` | `Parts List` | `Quality Report` | `Download`
- **Files**: each generated file as a card (icon, name, description in plain English)
- **Parts List**: full BOM with supplier links and total cost
- **Quality Report**: DFM issues and EE quality checks — same three-field format (what/why/fix)
- **Download**: single "Download everything" ZIP button, or individual file downloads

**Mecha Bundle Node**
Tabs: `3D Preview` | `How to Assemble` | `Parts` | `Cost Breakdown`
- **3D Preview**: Three.js viewer (reuse existing PcbViewport component), rotation + zoom
- **How to Assemble**: numbered step cards, each with description and illustration slot
- **Parts**: hardware + fasteners BOM, grouped by type
- **Cost Breakdown**: COGS estimate, digital pack value, per-unit vs bulk pricing

**Validation Node**
Tabs: `What's Wrong` | `Summary` | `What to Do Next`
- **What's Wrong**: issue list, severity sorted, each expandable
- **Summary**: health score ring, pass/fail counts, time-to-fix estimate
- **What to Do Next**: JARVIS recommendation card ("Fix 1 critical issue, then you're ready" with action button)

**Recipe Node**
Tabs: `Overview` | `Build Steps` | `Parts to Buy` | `Economics`
- **Overview**: project description, photos, key stats
- **Build Steps**: step-by-step wiring and assembly guide
- **Parts to Buy**: shopping list with prices and links
- **Economics**: ROI calculation breakdown, market price range, demand signal

---

## 9. Visual Design Language

### Color System

| Token | Hex | Usage |
|---|---|---|
| `bg-base` | `#080E1A` | Canvas and page background |
| `bg-node` | `#141E2E` | Node card background |
| `bg-drawer` | `#0F172A` | Drawer background |
| `border-subtle` | `rgba(255,255,255,0.08)` | Node borders, drawer dividers |
| `accent-cyan` | `#22D3EE` | Electronics, boards, validation |
| `accent-orange` | `#F97316` | Mechanical, enclosures, bundles |
| `accent-emerald` | `#10B981` | Ready / success / manufacturing |
| `accent-red` | `#EF4444` | Critical issues / blocked |
| `accent-amber` | `#F59E0B` | Warnings / attention needed |
| `accent-sky` | `#38BDF8` | Recipes / learning / discovery |
| `accent-purple` | `#A78BFA` | System / multi-board / simulation |
| `text-primary` | `#F8FAFC` | Main labels |
| `text-secondary` | `#94A3B8` | Supporting text, metadata |

### Nodes

- Width: 220px fixed
- Border radius: 16px
- Border: 1px `rgba(255,255,255,0.08)`
- Shadow: `0 4px 24px rgba(0,0,0,0.5)`
- Padding: 14px
- Status dot: 8px circle, top-right, color matches status

### Connections

- Bezier curves, 2px stroke
- Color: source node accent at 60% opacity when idle
- Animated dashed stroke while processing
- Solid on completion

### Typography

- Font: Inter (existing)
- Node title: 13px / 500 weight / `text-primary`
- Node data: 12px / 400 / `text-secondary`
- JARVIS strip: 14px / 400 / `text-primary`
- Drawer tab: 12px / 500 / uppercase / tracking-wide
- Issue "what it is": 14px / 500
- Issue "why/fix": 13px / 400 / `text-secondary`

---

## 10. Data Flow & State

### API Proxy Routes (Next.js `/app/api/`)

| Proxy route | Backend target |
|---|---|
| `/api/proxy/validate` | Circuit-AI `/api/v2/workflow/validate-kicad` |
| `/api/proxy/extract` | Circuit-AI `/api/v2/system/extract-board` |
| `/api/proxy/bom` | Circuit-AI `/api/v2/manufacture/bom` |
| `/api/proxy/manufacture` | Circuit-AI `/api/v2/manufacture/package` |
| `/api/proxy/bundle` | Mecha-Splicer `/v1/bundle` |
| `/api/proxy/recipes` | Circuit-AI `/api/recipes/generate` |
| `/api/proxy/learning` | Circuit-AI `/api/learning-paths` |
| `/api/proxy/diagnose` | Circuit-AI `/api/diagnose` |

### Client State (Zustand)

```typescript
type ProjectState = {
  id: string;
  name: string;
  nodes: Node[];          // position, type, data, status
  connections: Edge[];    // from, to
  jarvis: {
    messages: JarvisMessage[];   // role, body, nodeId, timestamp
    isThinking: boolean;
  };
  drawer: {
    nodeId: string | null;
    tab: string;
  };
  viewport: { x: number; y: number; zoom: number };
};
```

### Data persistence

- localStorage for anonymous users (project survives page refresh)
- Circuit-AI project API (`/api/v2/projects`) for users with API key
- Project state serializes to JSON — shareable via URL param

### Long-running operations

Operations that take >2s (manufacturing package, simulation, Mecha bundle):
1. Node status → `processing` (pulsing animation)
2. JARVIS strip shows progress ("Generating your manufacturing files… 40%")
3. On completion → node status → `done`, JARVIS narrates result
4. On error → node status → `error`, JARVIS explains in plain English what went wrong

---

## 11. What's NOT in Scope (v1)

- Real-time collaboration (no multiplayer editing)
- Firmware code generation (JARVIS hints at it, but doesn't generate main.cpp)
- Automated supply chain / obsolescence tracking
- Mobile-first layout (desktop-first, responsive later)
- The marketing landing page (separate effort)
- Payment/Stripe UI (API key management stays, full checkout deferred)

---

## 12. Existing Code to Reuse

From the current `circuit-ai-frontend`:

| Existing component | How it maps to new design |
|---|---|
| `WorkbenchCanvas` | Canvas node rendering — extend to support node types above |
| `CopilotDock` | Becomes the bottom JARVIS conversation drawer |
| `StudioCommandBar` | Becomes the top JARVIS command input |
| `components/cad/PcbViewport` | Powers the "3D Preview" tab in Mecha Bundle drawer |
| `components/cad/IssuesPanel` | Powers the "Issues" tab in Board drawer |
| `components/cad/TreePanel` | Powers the "Structure" tab in Board drawer |
| `lib/proxy-client.ts` | Keep and extend with new proxy routes |
| `lib/cad-project.ts` | Migrate into Zustand project state |
| `components/ui/` | Keep all 4 existing shadcn components, add tabs + dialog |

**Missing pieces to add:**
- `lib/utils.ts` (the `cn` helper — currently missing, breaks everything that uses StudioShell)
- `components/ui/tabs.tsx` (Radix installed, wrapper missing)
- `components/ui/dialog.tsx` (Radix installed, wrapper missing)
- Zustand for project state
- Node-specific drawer tab components
- JARVIS message formatting + strip component
