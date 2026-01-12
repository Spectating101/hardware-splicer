# Handoff to ChatGPT/Gemini for Frontend Implementation

**Task:** Build Electron desktop app for Circuit-AI PCB validator

**What's Done:** Backend API (Flask, Python) - fully functional
**What Needs Building:** Frontend desktop app (Electron + React + Three.js)

---

## Quick Start for ChatGPT

**Read these files in order:**

1. **INTERFACE_SPECIFICATION.md** - What to build (UI mockups, features, strategy)
2. **API_DOCUMENTATION.md** - Backend endpoints, request/response formats
3. **FRONTEND_IMPLEMENTATION_GUIDE.md** - Step-by-step code examples

---

## What You're Building

**Desktop app with 4 panels:**

```
┌──────────────────────────────────────────────┐
│ Toolbar (File, Validate, Export)            │
├────┬───────────────────────┬─────────────────┤
│Left│      Center           │ Right           │
│    │                       │                 │
│Tree│   3D PCB Viewer       │ Validation      │
│    │   (Three.js)          │ Results         │
│    │                       │                 │
├────┴───────────────────────┴─────────────────┤
│ Console (AI chat)                            │
└──────────────────────────────────────────────┘
```

---

## Tech Stack

```
Desktop: Electron
Frontend: React + TypeScript
3D: Three.js (@react-three/fiber)
UI: Ant Design or shadcn/ui
State: Zustand
API: Fetch/Axios
```

---

## Key Files to Create

```
circuit-ai-app/
├── src/main/index.ts          # Electron main
├── src/renderer/
│   ├── App.tsx                # Main layout
│   ├── components/
│   │   ├── Toolbar.tsx        # Top bar
│   │   ├── ComponentTree.tsx  # Left panel
│   │   ├── Canvas3D.tsx       # Center (Three.js)
│   │   ├── ValidationPanel.tsx# Right panel
│   │   └── Console.tsx        # Bottom
│   ├── lib/
│   │   ├── api-client.ts      # Backend API calls
│   │   ├── types.ts           # TypeScript interfaces
│   │   └── store.ts           # Zustand state
│   └── styles/
│       └── globals.css        # Dark theme
├── package.json
└── vite.config.ts
```

---

## Backend API (Already Built)

**Base URL:** `http://localhost:5000` (dev) or `https://circuit-ai.railway.app` (prod)

**Main Endpoint:**
```typescript
POST /api/v2/workflow/validate-kicad
// Upload KiCad `.kicad_pcb` (preferred) or `.net` → Get validation results (+ optional geometry)
```

**Response includes:**
- `validation.issues[]` - Validation problems to display
- `pcb_geometry.footprints[]` - Footprint refs + 2D positions (only for `.kicad_pcb`)
- `pcb_geometry.segments[]` - Copper segment geometry (only for `.kicad_pcb`)

**See API_DOCUMENTATION.md for complete API reference.**

---

## Implementation Steps

### 1. Setup (30 min)
```bash
npm create vite@latest circuit-ai-app -- --template react-ts
cd circuit-ai-app
npm install electron three @react-three/fiber antd axios zustand
```

### 2. Electron Config (15 min)
- Create `src/main/index.ts`
- Update `package.json` with Electron scripts
- Copy from FRONTEND_IMPLEMENTATION_GUIDE.md Step 2

### 3. API Client (20 min)
- Create `src/renderer/lib/api-client.ts`
- Copy code from FRONTEND_IMPLEMENTATION_GUIDE.md Step 4
- Test with `apiClient.validateKiCAD(file)`

### 4. State Management (15 min)
- Create `src/renderer/lib/store.ts`
- Copy Zustand store from Step 5
- Manage file upload, validation results, UI state

### 5. Layout (30 min)
- Create `src/renderer/App.tsx`
- 4-panel layout (toolbar, tree, canvas, validation, console)
- Copy CSS from Step 6

### 6. Components (2-3 hours)
- **Toolbar.tsx** - File upload button, validate, export
- **ComponentTree.tsx** - List components from API response
- **Canvas3D.tsx** - Three.js 3D board + traces + components
- **ValidationPanel.tsx** - Show issues with [Apply Fix] buttons
- **Console.tsx** - Chat interface (optional for MVP)

### 7. 3D Rendering (1-2 hours)
- Parse `validationResult.validation.components`
- Render board substrate (green box)
- Render traces (lines with thickness)
- Render components (simple boxes for MVP)
- Highlight issues in red
- Add camera controls (rotate, zoom, pan)

### 8. Test & Package (1 hour)
```bash
npm run electron:dev  # Test
npm run electron:build  # Build .dmg/.exe
```

**Total time:** 1-2 days for MVP, 1 week for polished

---

## Key Interactions

**User uploads file:**
```typescript
// 1. User drops file
const file = event.target.files[0];

// 2. Send to backend
const result = await apiClient.validateKiCAD(file);

// 3. Store in state
setValidationResult(result);

// 4. Render 3D model from result.validation.components
// 5. Show issues in right panel from result.validation.issues
```

**User clicks component:**
```typescript
// 1. Click component in tree
setSelectedComponent(comp.id);

// 2. Highlight in 3D
const mesh = scene.getObjectByName(comp.id);
mesh.material.color = 0x00ff00;

// 3. Show details in panel
```

**User applies fix:**
```typescript
// 1. Click [Apply Fix] button
const issueId = issue.component_id;

// 2. Apply fix locally (update 3D model)
trace.width_mm = issue.fix.parameters.new_width_mm;
updateMesh(trace);

// 3. Mark as fixed
issue.fixed = true;
```

---

## What NOT to Implement (Backend Handles)

❌ **Don't parse KiCAD files** - Backend does this
❌ **Don't run circuit validation** - Backend MNA solver
❌ **Don't calculate trace widths** - Backend IPC-2152
❌ **Don't generate Gerber** - Backend handles export

**Frontend only:**
✅ Upload files
✅ Display 3D visualization
✅ Show validation results
✅ Export reports

---

## Testing

**1. Start backend:**
```bash
cd circuit-ai
python3 api_server.py
# Runs on http://localhost:5000
```

**2. Test API manually:**
```bash
curl http://localhost:5000/api/health
# Should return: {"status": "healthy"}
```

**3. Create test KiCAD file:**
```
echo '(export (version D))' > test.net
```

**4. Upload via frontend and check:**
- 3D model renders
- Components appear in tree
- Issues appear in right panel

---

## MVP Feature Checklist

**Must Have:**
- [ ] File upload button
- [ ] 3D board rendering (simple box)
- [ ] Component tree list
- [ ] Validation results panel
- [ ] Issue highlighting in 3D (red color)
- [ ] Export report button

**Nice to Have:**
- [ ] 3D component models (can use simple shapes)
- [ ] Thermal visualization
- [ ] Current flow animation
- [ ] AI chat console
- [ ] Auto-apply fixes

**Polish:**
- [ ] Dark theme (VS Code style)
- [ ] Smooth animations
- [ ] Keyboard shortcuts
- [ ] Recent files menu

---

## Common Issues & Solutions

**Issue: CORS error when calling API**
```typescript
// Add to api-client.ts
const client = axios.create({
  baseURL: 'http://localhost:5000',
  headers: {
    'Content-Type': 'multipart/form-data'
  }
});
```

**Issue: 3D model not rendering**
```typescript
// Check camera position
<Canvas camera={{ position: [0, 0, 50], fov: 50 }}>
```

**Issue: File upload not working**
```html
<!-- Use label wrapper for custom styling -->
<label htmlFor="file-upload">
  <button>Upload</button>
</label>
<input
  id="file-upload"
  type="file"
  accept=".kicad_pcb,.net"
  style={{ display: 'none' }}
/>
```

---

## Performance Tips

**For large boards (>100 components):**
- Use `React.memo()` for component lists
- Implement virtualization (react-window)
- Simplify 3D models (use instancing)
- Lazy load component details

**3D Optimization:**
```typescript
// Use InstancedMesh for repeated components
const mesh = new THREE.InstancedMesh(geometry, material, count);
```

---

## Deployment

**Mac:**
```bash
npm run electron:build
# Output: release/Circuit-AI.dmg
```

**Windows:**
```bash
npm run electron:build
# Output: release/Circuit-AI.exe
```

**Linux:**
```bash
npm run electron:build
# Output: release/Circuit-AI.AppImage
```

**Auto-update setup (later):**
- Use electron-updater
- Configure GitHub Releases
- Add update check on startup

---

## Resources

**Three.js Examples:**
- https://threejs.org/examples/
- https://docs.pmnd.rs/react-three-fiber/

**Electron Docs:**
- https://www.electronjs.org/docs/latest/

**UI Inspiration:**
- Figma (dark theme)
- VS Code (panels)
- Blender (3D viewport)
- KiCAD (component tree)

---

## Questions for User (Ask if unclear)

1. **UI Library:** Ant Design or shadcn/ui?
2. **3D Detail:** Simple boxes or detailed component models?
3. **Chat Feature:** Include AI console in MVP or later?
4. **Auto-fixes:** Apply fixes automatically or manually?
5. **Platform:** Build for Mac, Windows, or both?

---

## Success Criteria

**MVP is done when:**
- ✅ User can upload KiCAD file
- ✅ 3D board renders with components
- ✅ Issues show in right panel with red highlights
- ✅ Can export validation report
- ✅ Electron app runs without crashes

**Ready to ship when:**
- ✅ Professional dark theme
- ✅ Smooth animations
- ✅ All interactions work
- ✅ Builds for Mac/Windows
- ✅ No console errors

---

## Final Notes

**This is a visualization layer for our backend.**

Backend does all the heavy lifting:
- Parses KiCAD files
- Runs circuit validation
- Calculates fixes

Frontend just:
- Shows data beautifully in 3D
- Lets user interact
- Applies fixes visually

**Keep it simple. Ship fast. Iterate based on feedback.**

---

## Start Here

**Copy this prompt to ChatGPT/Gemini:**

```
I need you to build an Electron desktop app for PCB validation.

Tech stack:
- Electron + React + TypeScript
- Three.js for 3D rendering
- Ant Design for UI
- Zustand for state management

Backend API is already built (Flask, Python) at http://localhost:5000

Main endpoint: POST /api/v2/workflow/validate-kicad
- Upload KiCAD file
- Returns validation results + 3D data

Please read these files:
1. INTERFACE_SPECIFICATION.md - UI design
2. API_DOCUMENTATION.md - API reference
3. FRONTEND_IMPLEMENTATION_GUIDE.md - Code examples

Build a 4-panel interface:
- Top: Toolbar (file upload)
- Left: Component tree
- Center: 3D PCB viewer (Three.js)
- Right: Validation results

Start with Step 1 in FRONTEND_IMPLEMENTATION_GUIDE.md and implement all components.

Focus on MVP first (file upload, 3D rendering, validation display).
```

**Then share this folder with ChatGPT.**

---

**You've got everything documented. Good luck! 🚀**
