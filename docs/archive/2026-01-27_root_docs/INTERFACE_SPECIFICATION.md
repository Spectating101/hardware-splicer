# Circuit-AI Interface Specification
## For Implementation by Frontend Developer / LLM

**Goal:** Build a professional CAD-like desktop application, NOT a chatbot.

**Key Differentiator:** ChatGPT can only describe circuits with text. Circuit-AI shows you the actual PCB in 3D with interactive validation.

---

## 1. Core Philosophy: Visual-First CAD Tool

**NOT THIS (Chatbot):**
```
┌────────────────────────────┐
│ Upload file...             │
│                            │
│ [Drop file here]           │
│                            │
│ ↓                          │
│                            │
│ Results:                   │
│ - Trace too thin           │
│ - Resistor wrong value     │
└────────────────────────────┘
```

**YES THIS (Professional CAD Interface):**
```
┌─────────────────────────────────────────────────────────┐
│ File  Edit  View  Validate  Export  Help          [🔌] │
├──────┬──────────────────────────────────┬───────────────┤
│      │                                  │ 📋 ISSUES (2) │
│ 📁   │     ┌──────────────────┐        │               │
│ Tree │     │  3D PCB Render   │        │ ⚠️ Trace T1   │
│      │     │                  │        │   0.5mm @2A   │
│ ├─ U1│     │    [PCB Visual]  │        │   → 1.2mm ✓   │
│ ├─ R1│     │                  │        │               │
│ ├─ C1│     │  [Rotate] [Zoom] │        │ ⚠️ Resistor   │
│ ├─ T1│     └──────────────────┘        │   R1 1/4W     │
│ └─ VCC     Hover: Trace T1             │   → 1/2W ✓    │
│            Width: 0.5mm ⚠️              │               │
│            Current: 2A                  │ [Fix All] [→] │
│            Drop: 0.45V                  │               │
├──────┴──────────────────────────────────┴───────────────┤
│ > circuit-ai: Trace T1 is underpowered  [Type command]  │
└──────────────────────────────────────────────────────────┘
```

**Think:**
- **Figma** for design (not "design chatbot")
- **Blender** for 3D (not "3D description bot")
- **KiCAD** for PCB (not "circuit helper")

---

## 2. Technology Stack Recommendation

### **Option A: Electron + Three.js (Recommended)**
```
Frontend: React + TypeScript
3D Renderer: Three.js (WebGL)
UI Framework: Ant Design / Material-UI
Desktop: Electron
Backend: Our Flask API (already built)
```

**Why:**
- Three.js = Professional 3D rendering (like Tinkercad, Fusion 360)
- Electron = Desktop app (not web-constrained)
- React = Modern, maintainable

### **Option B: Tauri + Three.js (Lighter)**
Same as above but Tauri instead of Electron (3MB vs 80MB download)

### **Option C: Native (Future)**
- C++ + Qt (like real KiCAD)
- Only if we get serious traction

**Start with Option A or B.**

---

## 3. UI Layout (CAD-Style Interface)

### **Main Window Components:**

```
┌──────────────────────────────────────────────────────────────┐
│ ████ Menu Bar ████████████████████████████████████████  [🔌] │
├────────┬────────────────────────────────────┬─────────────────┤
│        │                                    │                 │
│  LEFT  │          CENTER CANVAS             │  RIGHT PANEL    │
│  TREE  │                                    │                 │
│        │      (3D PCB Viewer)              │  (Validation)   │
│        │                                    │                 │
├────────┴────────────────────────────────────┴─────────────────┤
│                    BOTTOM CONSOLE                             │
└──────────────────────────────────────────────────────────────┘
```

### **A. Top Menu Bar**
```
File  Edit  View  Validate  Export  Help                    [Settings ⚙️]
```

**File Menu:**
- Open KiCAD File (.kicad_pcb, .net)
- Open Gerber Files (.gbr)
- Open Image (for vision analysis)
- Recent Files
- Exit

**Validate Menu:**
- Run Full Validation
- DC Operating Point
- Power Tree Analysis
- Trace Width Check
- DRC (Design Rule Check)

**Export Menu:**
- Export Fixes (KiCAD patch)
- Export Report (PDF)
- Export Gerber (fixed)
- Export BOM

### **B. Left Panel: Component Tree**
```
📁 Components
  ├─ 🔲 U1: Arduino Nano
  ├─ 🔲 R1: 150Ω ⚠️
  ├─ 🔲 R2: 220Ω
  ├─ 🔲 C1: 10µF
  ├─ 🔲 LED1: Red
  └─ 🔲 J1: Header

📁 Nets
  ├─ 🔌 VCC (5V)
  ├─ 🔌 GND
  ├─ 🔌 D13
  └─ 🔌 RESET

📁 Traces
  ├─ ⚡ T1: VCC → U1 ⚠️
  ├─ ⚡ T2: GND → C1
  └─ ⚡ T3: D13 → LED1
```

**Interactions:**
- Click component → Highlight in 3D view
- Hover → Show specs
- Right-click → Context menu (properties, fix, isolate)

### **C. Center Canvas: 3D PCB Viewer**

**Rendering Features:**
```javascript
// What to render (Three.js)
- Board substrate (green/blue FR4)
- Copper layers (gold/silver)
- Components (3D models)
- Traces (with thickness visualization)
- Solder mask
- Silkscreen labels
- Drill holes
- Vias
```

**Interaction:**
```
Mouse Controls:
- Left drag: Rotate board
- Right drag: Pan
- Scroll: Zoom
- Click component: Select + show info
- Hover trace: Show current/voltage
- Double-click: Focus on component
```

**View Modes:**
- Top view (2D)
- Bottom view (2D)
- 3D perspective
- X-ray (see internal layers)
- Thermal map (show hot spots)

**Overlay Modes:**
- Show net names
- Show voltage levels
- Show current flow (animated)
- Show problem areas (red highlights)

### **D. Right Panel: Validation Results**

```
┌─────────────────────────┐
│ VALIDATION RESULTS      │
├─────────────────────────┤
│ Status: ⚠️ 2 Issues     │
│                         │
│ ━━━━━━━━━━━━━━━━━━━━━  │
│                         │
│ ⚠️ CRITICAL: Trace T1   │
│    Width: 0.5mm         │
│    Current: 2A          │
│    Voltage Drop: 0.45V  │
│                         │
│    💡 Fix:              │
│    Widen to 1.2mm       │
│    (IPC-2152 standard)  │
│                         │
│    [Apply Fix] [Ignore] │
│                         │
│ ━━━━━━━━━━━━━━━━━━━━━  │
│                         │
│ ⚠️ WARNING: Resistor R1 │
│    Rating: 1/4W         │
│    Power: 0.31W (124%)  │
│                         │
│    💡 Fix:              │
│    Use 1/2W resistor    │
│                         │
│    [Apply Fix] [Ignore] │
│                         │
│ ━━━━━━━━━━━━━━━━━━━━━  │
│                         │
│ ✅ All other checks OK  │
│    - DC convergence ✓   │
│    - Power tree ✓       │
│    - Clearances ✓       │
│                         │
│ [Export Report]         │
└─────────────────────────┘
```

**Features:**
- Color-coded severity (🔴 Critical, 🟡 Warning, 🟢 OK)
- Expandable details
- One-click fixes
- Links to components in 3D view

### **E. Bottom Console: AI Assistant**

```
┌──────────────────────────────────────────────────────────┐
│ > circuit-ai: Trace T1 is underpowered for 2A current   │
│ > circuit-ai: Suggested fix applied. Validate again?     │
│ > you: What if I reduce current to 1A?                   │
│ > circuit-ai: At 1A, 0.5mm trace is adequate (0.11V drop)│
│ > circuit-ai: Do you want to simulate at 1A? [Yes] [No]  │
│                                                          │
│ [Type your question...]                       [Send 🚀] │
└──────────────────────────────────────────────────────────┘
```

**This is where ChatGPT functionality goes**, but it's **NOT the main interface**.

---

## 4. Key Features That Beat ChatGPT

### **A. 3D Visualization**
ChatGPT: "Your trace is too thin"
Circuit-AI: Shows you the exact trace in 3D, highlights it red, shows current flow animation

### **B. Interactive Editing**
ChatGPT: "You should widen trace T1 to 1.2mm"
Circuit-AI: [Apply Fix] button → Instantly updates 3D model → Shows new validation

### **C. Real-Time Simulation**
ChatGPT: "Calculate voltage drop"
Circuit-AI: Live thermal map showing hot spots, animated current flow, voltage levels on each net

### **D. Visual Component Detection**
ChatGPT: Can't see images well
Circuit-AI: Drag & drop PCB photo → Instant 3D reconstruction with bounding boxes

### **E. KiCAD Integration**
ChatGPT: "Export to KiCAD format..."
Circuit-AI: One-click export with fixes already applied

---

## 5. User Workflows

### **Workflow 1: Upload & Validate**
```
1. User drops KiCAD file into app
2. 3D model renders (1-2 seconds)
3. Validation runs automatically in background
4. Issues appear in right panel with red highlights in 3D
5. User clicks [Apply Fix] → 3D updates instantly
6. User exports fixed KiCAD file
```

### **Workflow 2: Visual Analysis**
```
1. User takes photo of PCB with phone
2. Drags photo into app
3. AI detects components (YOLOv8)
4. App reconstructs circuit topology
5. Shows 3D approximation of board
6. Validates power tree, identifies issues
```

### **Workflow 3: Interactive Design**
```
1. User opens schematic
2. Asks in console: "Can I use a 100Ω resistor instead?"
3. App updates component, re-runs validation
4. Shows new voltage drop, power dissipation
5. User iterates until design is correct
```

---

## 6. Technical Implementation Details

### **A. 3D Rendering (Three.js)**

**Parse KiCAD file:**
```javascript
// Parse .kicad_pcb format
const board = parseKiCAD(fileContent);

// Create Three.js scene
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, width/height, 0.1, 1000);

// Render board substrate
const boardGeometry = new THREE.BoxGeometry(board.width, board.height, 1.6);
const boardMaterial = new THREE.MeshStandardMaterial({ color: 0x2d5016 }); // FR4 green
const boardMesh = new THREE.Mesh(boardGeometry, boardMaterial);
scene.add(boardMesh);

// Render traces
board.traces.forEach(trace => {
  const tracePath = new THREE.Path(trace.points);
  const traceGeometry = new THREE.ExtrudeGeometry(tracePath, {
    depth: trace.width,
    bevelEnabled: false
  });
  const traceMaterial = new THREE.MeshStandardMaterial({
    color: 0xFFD700, // Copper gold
    metalness: 0.8,
    roughness: 0.2
  });
  const traceMesh = new THREE.Mesh(traceGeometry, traceMaterial);
  scene.add(traceMesh);
});

// Render components (simplified 3D models)
board.components.forEach(comp => {
  const compModel = load3DModel(comp.type); // Load from library
  compModel.position.set(comp.x, comp.y, comp.z);
  scene.add(compModel);
});
```

### **B. Issue Highlighting**

```javascript
// Highlight problematic trace in red
function highlightIssue(traceId, severity) {
  const trace = scene.getObjectByName(traceId);

  if (severity === 'critical') {
    trace.material.color.setHex(0xFF0000); // Red
    trace.material.emissive.setHex(0xFF0000);
    trace.material.emissiveIntensity = 0.5;

    // Add pulsing animation
    animatePulse(trace);
  } else if (severity === 'warning') {
    trace.material.color.setHex(0xFFAA00); // Orange
  }

  // Add tooltip on hover
  trace.userData.tooltip = {
    issue: "Trace too thin",
    current: "2A",
    fix: "Widen to 1.2mm"
  };
}
```

### **C. Backend API Integration**

```typescript
// API client
class CircuitAIClient {
  async validateBoard(file: File): Promise<ValidationResult> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('https://circuit-ai.railway.app/api/v2/workflow/validate-kicad', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`
      },
      body: formData
    });

    return await response.json();
  }

  async applyFix(issueId: string): Promise<FixResult> {
    // Call backend to generate fix
    const response = await fetch(`/api/v2/fixes/${issueId}/apply`, {
      method: 'POST'
    });

    return await response.json();
  }
}
```

### **D. Component Library (3D Models)**

```
assets/
  components/
    resistors/
      ├── resistor_0402.glb
      ├── resistor_0603.glb
      └── resistor_1206.glb
    capacitors/
      ├── cap_ceramic_0805.glb
      └── cap_electrolytic.glb
    ics/
      ├── atmega328p.glb
      ├── esp32.glb
      └── stm32.glb
    connectors/
      └── header_2x3.glb
```

Load on demand:
```javascript
const loader = new GLTFLoader();
loader.load(`assets/components/${componentType}.glb`, (gltf) => {
  scene.add(gltf.scene);
});
```

---

## 7. Professional UI Polish

### **Color Scheme (Dark Mode Default)**
```css
:root {
  --bg-primary: #1e1e1e;     /* VS Code dark */
  --bg-secondary: #252526;
  --bg-tertiary: #2d2d30;

  --text-primary: #cccccc;
  --text-secondary: #888888;

  --accent-blue: #007acc;    /* Primary actions */
  --accent-green: #4ec9b0;   /* Success */
  --accent-red: #f48771;     /* Errors */
  --accent-orange: #ce9178;  /* Warnings */

  --copper: #FFD700;         /* PCB copper */
  --fr4: #2d5016;           /* PCB green */
}
```

### **Typography**
```css
font-family:
  'Inter', /* UI text */
  'JetBrains Mono', /* Code/console */
  system-ui, sans-serif;
```

### **Icons**
Use **Lucide Icons** or **Heroicons** (clean, professional)

### **Animations**
```css
/* Smooth transitions */
* {
  transition: all 0.2s ease-in-out;
}

/* Hover effects */
.component-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

/* Issue pulse animation */
@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1.0; }
}

.issue-critical {
  animation: pulse 2s infinite;
}
```

---

## 8. File Structure

```
circuit-ai-app/
├── src/
│   ├── main/
│   │   ├── index.ts              # Electron main process
│   │   └── menu.ts               # App menu
│   ├── renderer/
│   │   ├── App.tsx               # Main React app
│   │   ├── components/
│   │   │   ├── Canvas3D.tsx      # Three.js viewer
│   │   │   ├── ComponentTree.tsx # Left panel
│   │   │   ├── ValidationPanel.tsx # Right panel
│   │   │   ├── Console.tsx       # Bottom panel
│   │   │   └── Toolbar.tsx       # Top menu
│   │   ├── lib/
│   │   │   ├── kicad-parser.ts   # Parse KiCAD files
│   │   │   ├── api-client.ts     # Backend API
│   │   │   └── 3d-renderer.ts    # Three.js logic
│   │   └── styles/
│   │       └── globals.css
│   └── assets/
│       └── components/           # 3D models
├── package.json
├── electron-builder.json
└── README.md
```

---

## 9. API Integration Points

**Backend (our Flask API) provides:**
```
POST /api/v2/workflow/validate-kicad
  → Upload KiCAD file
  → Returns: components, issues, fixes

POST /api/v2/validate
  → Circuit validation
  → Returns: DC analysis, power tree

POST /api/v2/fixes/apply
  → Apply specific fix
  → Returns: updated circuit

POST /api/v2/manufacture/bom
  → Generate BOM
  → Returns: component list with pricing

POST /api/v2/manufacture/gerber
  → Export Gerber files
  → Returns: ZIP file
```

**Frontend calls these APIs** and visualizes results in 3D.

---

## 10. MVP Feature Priority

### **Phase 1: MVP (Launch - 1 week)**
- [x] File upload (KiCAD)
- [x] 3D board rendering (basic)
- [x] Component tree view
- [x] Validation results panel
- [x] Issue highlighting in 3D
- [x] Export report

### **Phase 2: Enhanced (Month 1)**
- [ ] Image upload (PCB photo analysis)
- [ ] Interactive editing (click to fix)
- [ ] Thermal visualization
- [ ] Current flow animation
- [ ] AI console chat

### **Phase 3: Professional (Month 2-3)**
- [ ] DRC (Design Rule Check)
- [ ] Multi-layer visualization
- [ ] Component 3D models library
- [ ] Gerber file export
- [ ] KiCAD plugin integration

---

## 11. Why This Beats ChatGPT

| Feature | ChatGPT | Circuit-AI |
|---------|---------|------------|
| **Text Q&A** | ✅ Great | ✅ Same |
| **Upload Files** | ⚠️ Limited | ✅ Full KiCAD |
| **3D Visualization** | ❌ No | ✅ Real-time |
| **Interactive Editing** | ❌ No | ✅ Click to fix |
| **Professional UI** | ❌ Chat-only | ✅ CAD interface |
| **Circuit Simulation** | ❌ No | ✅ MNA solver |
| **Gerber Export** | ❌ No | ✅ Yes |
| **Offline Use** | ❌ No | ✅ Desktop app |
| **Accuracy** | ⚠️ Generic | ✅ IPC-2152 standard |

**Circuit-AI is a tool. ChatGPT is a chatbot.**

---

## 12. Instructions for Frontend Developer

**To implement this:**

1. **Set up Electron + React + TypeScript**
   ```bash
   npm create vite@latest circuit-ai -- --template react-ts
   npm install electron electron-builder three @react-three/fiber
   ```

2. **Implement 3D viewer first**
   - Use Three.js or React Three Fiber
   - Parse KiCAD file format (XML-like)
   - Render board substrate + traces + components

3. **Build UI layout**
   - Use Ant Design or Material-UI components
   - Left panel: Tree view
   - Right panel: Results cards
   - Bottom: Console

4. **Connect to backend API**
   - Use our Flask API (already deployed)
   - Handle file uploads
   - Display validation results

5. **Add interactions**
   - Click component → highlight + show info
   - Hover trace → show specs
   - Apply fix → update 3D model

6. **Package as desktop app**
   ```bash
   npm run build
   npm run electron:build
   ```

---

## 13. Design References (Inspiration)

**Look at these for UI inspiration:**
- **Figma** - Clean, professional, visual-first
- **Blender** - 3D viewport + panels
- **KiCAD** - Component tree + canvas
- **VS Code** - Dark theme, panels
- **Fusion 360** - 3D CAD interface

**Don't look at:**
- ChatGPT interface (too chat-focused)
- Generic web forms (not professional enough)

---

## 14. Summary for LLM Implementation

**Build a desktop app (Electron/Tauri) that:**
1. Loads KiCAD files and renders them in 3D (Three.js)
2. Shows component tree on left, validation results on right
3. Highlights issues in 3D with interactive fixes
4. Has console at bottom for AI chat (but NOT main interface)
5. Looks like a professional CAD tool, not a chatbot

**Stack:**
- Electron or Tauri
- React + TypeScript
- Three.js (3D rendering)
- Ant Design or Material-UI
- Our Flask API backend

**Time estimate:** 1-2 weeks for MVP, 4-6 weeks for polished v1.0

---

**This is a professional PCB validation tool, not a chat interface.**

**The 3D visualization is what beats ChatGPT.**
