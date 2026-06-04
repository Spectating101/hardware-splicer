# Circuit-AI Frontend Implementation Guide
## Step-by-Step Instructions for ChatGPT/Gemini

**Goal:** Build a professional desktop application (Electron) that visualizes PCB boards in 3D and shows validation results.

---

## Project Overview

**What we're building:**
- Desktop application (Electron + React)
- 3D PCB viewer (Three.js)
- CAD-like interface with panels
- Connects to existing Flask backend API

**What we're NOT building:**
- Backend API (already exists)
- KiCAD parser (backend handles it)
- Validation logic (backend handles it)

**Frontend only needs to:**
1. Upload files to backend
2. Display 3D visualization
3. Show validation results
4. Export reports

---

## Tech Stack

```
Desktop Framework: Electron or Tauri
Frontend Framework: React + TypeScript
3D Rendering: Three.js (via @react-three/fiber)
UI Components: Ant Design or shadcn/ui
State Management: Zustand or React Context
API Client: Fetch API or Axios
Build Tool: Vite
```

---

## Project Setup (Step 1)

### Initialize Project

```bash
# Create React + TypeScript project
npm create vite@latest circuit-ai-app -- --template react-ts

cd circuit-ai-app

# Install dependencies
npm install

# Install Electron
npm install --save-dev electron electron-builder concurrently wait-on cross-env

# Install Three.js
npm install three @react-three/fiber @react-three/drei

# Install UI library (choose one)
npm install antd  # Option A: Ant Design
# OR
npm install @radix-ui/react-dropdown-menu @radix-ui/react-dialog  # Option B: shadcn/ui

# Install utilities
npm install axios zustand lucide-react
```

### Project Structure

```
circuit-ai-app/
├── src/
│   ├── main/              # Electron main process
│   │   └── index.ts
│   ├── renderer/          # React app
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   │   ├── Canvas3D.tsx
│   │   │   ├── ComponentTree.tsx
│   │   │   ├── ValidationPanel.tsx
│   │   │   ├── Console.tsx
│   │   │   └── Toolbar.tsx
│   │   ├── lib/
│   │   │   ├── api-client.ts
│   │   │   ├── types.ts
│   │   │   └── store.ts
│   │   └── styles/
│   │       └── globals.css
│   └── assets/
├── package.json
├── tsconfig.json
├── vite.config.ts
└── electron-builder.json
```

---

## Step 2: Electron Setup

### package.json additions

```json
{
  "main": "dist-electron/main.js",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "electron:dev": "concurrently \"vite\" \"wait-on http://localhost:5173 && electron .\"",
    "electron:build": "npm run build && electron-builder"
  },
  "build": {
    "appId": "com.circuitai.app",
    "productName": "Circuit-AI",
    "directories": {
      "output": "release"
    },
    "files": [
      "dist/**/*",
      "dist-electron/**/*"
    ],
    "mac": {
      "target": ["dmg"]
    },
    "win": {
      "target": ["nsis"]
    },
    "linux": {
      "target": ["AppImage"]
    }
  }
}
```

### src/main/index.ts (Electron Main)

```typescript
import { app, BrowserWindow } from 'electron';
import * as path from 'path';

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    titleBarStyle: 'hidden', // For native look
    backgroundColor: '#1e1e1e'
  });

  // Load app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
```

---

## Step 3: TypeScript Types

### src/renderer/lib/types.ts

```typescript
// API Response types
export interface ValidationResult {
  success: boolean;
  validation: {
    circuit_valid: boolean;
    issues_found: number;
    issues: Issue[];
    components: Component[];
    traces: Trace[];
    nets: Net[];
    dc_analysis: DCAnalysis;
    power_tree: PowerTree;
  };
  board_info: BoardInfo;
}

export interface Issue {
  severity: 'critical' | 'warning' | 'info';
  type: string;
  component_id: string;
  message: string;
  details: {
    current_width_mm?: number;
    required_width_mm?: number;
    current_a?: number;
    voltage_drop_v?: number;
    [key: string]: any;
  };
  fix: {
    action: string;
    parameters: Record<string, any>;
    reasoning: string;
  };
  location: {
    x?: number;
    y?: number;
    from?: { x: number; y: number };
    to?: { x: number; y: number };
  };
}

export interface Component {
  id: string;
  type: string;
  value?: string;
  position: {
    x: number;
    y: number;
    rotation: number;
  };
  nets: Record<string, string>;
}

export interface Trace {
  id: string;
  net: string;
  width_mm: number;
  length_mm: number;
  layer: string;
  current_a: number;
  voltage_drop_v: number;
  path: Array<{ x: number; y: number }>;
}

export interface Net {
  id: string;
  name: string;
  voltage_v: number;
  components: string[];
  traces: string[];
}

export interface DCAnalysis {
  converged: boolean;
  iterations: number;
  node_voltages: Record<string, number>;
  branch_currents: Record<string, number>;
}

export interface PowerTree {
  valid: boolean;
  total_current_a: number;
  issues: string[];
}

export interface BoardInfo {
  width_mm: number;
  height_mm: number;
  layers: string[];
  thickness_mm: number;
}
```

---

## Step 4: API Client

### src/renderer/lib/api-client.ts

```typescript
import axios, { AxiosInstance } from 'axios';
import { ValidationResult } from './types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

class CircuitAIAPI {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      timeout: 30000, // 30 second timeout for large files
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
  }

  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await this.client.get('/api/health');
    return response.data;
  }

  async validateKiCAD(file: File): Promise<ValidationResult> {
    const formData = new FormData();
    formData.append('kicad_file', file);

    const response = await this.client.post(
      '/api/v2/workflow/validate-kicad',
      formData
    );

    return response.data;
  }

  async generateBOM(file: File, includePricing: boolean = true) {
    const formData = new FormData();
    formData.append('netlist_file', file);
    formData.append('include_pricing', includePricing.toString());
    formData.append('format', 'json');

    const response = await this.client.post(
      '/api/v2/manufacture/bom',
      formData
    );

    return response.data;
  }

  async exportGerber(file: File, applyFixes: boolean = false) {
    const formData = new FormData();
    formData.append('kicad_file', file);
    formData.append('apply_fixes', applyFixes.toString());

    const response = await this.client.post(
      '/api/v2/manufacture/gerber',
      formData
    );

    return response.data;
  }

  async downloadGerber(filename: string): Promise<Blob> {
    const response = await this.client.get(
      `/api/v2/manufacture/download-gerber/${filename}`,
      { responseType: 'blob' }
    );

    return response.data;
  }
}

export const apiClient = new CircuitAIAPI();
```

---

## Step 5: State Management

### src/renderer/lib/store.ts

```typescript
import { create } from 'zustand';
import { ValidationResult, Issue, Component, Trace } from './types';

interface AppState {
  // File state
  currentFile: File | null;
  setCurrentFile: (file: File | null) => void;

  // Validation state
  validationResult: ValidationResult | null;
  setValidationResult: (result: ValidationResult | null) => void;

  // UI state
  selectedComponent: string | null;
  setSelectedComponent: (id: string | null) => void;

  selectedTrace: string | null;
  setSelectedTrace: (id: string | null) => void;

  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;

  error: string | null;
  setError: (error: string | null) => void;

  // View state
  viewMode: '2d' | '3d' | 'xray';
  setViewMode: (mode: '2d' | '3d' | 'xray') => void;

  showIssuesOnly: boolean;
  setShowIssuesOnly: (show: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // File state
  currentFile: null,
  setCurrentFile: (file) => set({ currentFile: file }),

  // Validation state
  validationResult: null,
  setValidationResult: (result) => set({ validationResult: result }),

  // UI state
  selectedComponent: null,
  setSelectedComponent: (id) => set({ selectedComponent: id }),

  selectedTrace: null,
  setSelectedTrace: (id) => set({ selectedTrace: id }),

  isLoading: false,
  setIsLoading: (loading) => set({ isLoading: loading }),

  error: null,
  setError: (error) => set({ error: error }),

  // View state
  viewMode: '3d',
  setViewMode: (mode) => set({ viewMode: mode }),

  showIssuesOnly: false,
  setShowIssuesOnly: (show) => set({ showIssuesOnly: show }),
}));
```

---

## Step 6: Main Layout

### src/renderer/App.tsx

```typescript
import React from 'react';
import { Toolbar } from './components/Toolbar';
import { ComponentTree } from './components/ComponentTree';
import { Canvas3D } from './components/Canvas3D';
import { ValidationPanel } from './components/ValidationPanel';
import { Console } from './components/Console';
import './styles/globals.css';

export default function App() {
  return (
    <div className="app-container">
      <Toolbar />

      <div className="main-content">
        <aside className="left-panel">
          <ComponentTree />
        </aside>

        <main className="center-canvas">
          <Canvas3D />
        </main>

        <aside className="right-panel">
          <ValidationPanel />
        </aside>
      </div>

      <footer className="bottom-console">
        <Console />
      </footer>
    </div>
  );
}
```

### src/renderer/styles/globals.css

```css
:root {
  --bg-primary: #1e1e1e;
  --bg-secondary: #252526;
  --bg-tertiary: #2d2d30;

  --text-primary: #cccccc;
  --text-secondary: #888888;

  --accent-blue: #007acc;
  --accent-green: #4ec9b0;
  --accent-red: #f48771;
  --accent-orange: #ce9178;

  --border-color: #3e3e42;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  overflow: hidden;
}

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.left-panel {
  width: 280px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
}

.center-canvas {
  flex: 1;
  background: var(--bg-primary);
  position: relative;
}

.right-panel {
  width: 320px;
  background: var(--bg-secondary);
  border-left: 1px solid var(--border-color);
  overflow-y: auto;
}

.bottom-console {
  height: 200px;
  background: var(--bg-tertiary);
  border-top: 1px solid var(--border-color);
}
```

---

## Step 7: Components

### src/renderer/components/Toolbar.tsx

```typescript
import React from 'react';
import { Upload, Play, FileDown, Settings } from 'lucide-react';
import { useAppStore } from '../lib/store';
import { apiClient } from '../lib/api-client';

export function Toolbar() {
  const { setCurrentFile, setValidationResult, setIsLoading, setError } = useAppStore();

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setCurrentFile(file);
    setIsLoading(true);
    setError(null);

    try {
      const result = await apiClient.validateKiCAD(file);
      setValidationResult(result);
    } catch (error) {
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <header className="toolbar">
      <div className="toolbar-left">
        <button className="toolbar-button">
          <label htmlFor="file-upload">
            <Upload size={18} />
            <span>Open</span>
          </label>
        </button>
        <input
          id="file-upload"
          type="file"
          accept=".kicad_pcb,.net"
          onChange={handleFileUpload}
          style={{ display: 'none' }}
        />

        <button className="toolbar-button">
          <Play size={18} />
          <span>Validate</span>
        </button>

        <button className="toolbar-button">
          <FileDown size={18} />
          <span>Export</span>
        </button>
      </div>

      <div className="toolbar-right">
        <button className="toolbar-button">
          <Settings size={18} />
        </button>
      </div>
    </header>
  );
}
```

### src/renderer/components/ComponentTree.tsx

```typescript
import React from 'react';
import { useAppStore } from '../lib/store';
import { Component } from '../lib/types';

export function ComponentTree() {
  const { validationResult, selectedComponent, setSelectedComponent } = useAppStore();

  if (!validationResult) {
    return (
      <div className="component-tree">
        <div className="empty-state">
          <p>Upload a KiCAD file to see components</p>
        </div>
      </div>
    );
  }

  const { components } = validationResult.validation;

  return (
    <div className="component-tree">
      <div className="tree-header">
        <h3>Components ({components.length})</h3>
      </div>

      <div className="tree-list">
        {components.map((comp) => (
          <div
            key={comp.id}
            className={`tree-item ${selectedComponent === comp.id ? 'selected' : ''}`}
            onClick={() => setSelectedComponent(comp.id)}
          >
            <span className="component-icon">🔲</span>
            <span className="component-name">{comp.id}</span>
            <span className="component-type">{comp.type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### src/renderer/components/Canvas3D.tsx

```typescript
import React, { useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import { useAppStore } from '../lib/store';
import * as THREE from 'three';

function Board() {
  const { validationResult } = useAppStore();

  if (!validationResult) return null;

  const { width_mm, height_mm } = validationResult.board_info;

  return (
    <mesh position={[0, 0, 0]}>
      <boxGeometry args={[width_mm / 10, height_mm / 10, 0.16]} />
      <meshStandardMaterial color="#2d5016" roughness={0.8} />
    </mesh>
  );
}

function Traces() {
  const { validationResult, selectedTrace } = useAppStore();

  if (!validationResult) return null;

  const { traces } = validationResult.validation;

  return (
    <>
      {traces.map((trace) => {
        const points = trace.path.map(
          (p) => new THREE.Vector3(p.x / 10, p.y / 10, 0.1)
        );

        const geometry = new THREE.BufferGeometry().setFromPoints(points);

        const isSelected = selectedTrace === trace.id;
        const hasIssue = validationResult.validation.issues.some(
          (issue) => issue.component_id === trace.id
        );

        const color = hasIssue ? '#ff0000' : isSelected ? '#00ff00' : '#ffd700';

        return (
          <line key={trace.id} geometry={geometry}>
            <lineBasicMaterial color={color} linewidth={trace.width_mm} />
          </line>
        );
      })}
    </>
  );
}

export function Canvas3D() {
  const { isLoading } = useAppStore();

  if (isLoading) {
    return (
      <div className="canvas-loading">
        <div className="spinner" />
        <p>Rendering 3D model...</p>
      </div>
    );
  }

  return (
    <Canvas camera={{ position: [0, 0, 50], fov: 50 }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 10]} intensity={1} />

      <Board />
      <Traces />

      <Grid args={[100, 100]} />
      <OrbitControls />
    </Canvas>
  );
}
```

### src/renderer/components/ValidationPanel.tsx

```typescript
import React from 'react';
import { AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';
import { useAppStore } from '../lib/store';

export function ValidationPanel() {
  const { validationResult } = useAppStore();

  if (!validationResult) {
    return (
      <div className="validation-panel">
        <div className="empty-state">
          <p>No validation results yet</p>
        </div>
      </div>
    );
  }

  const { issues, circuit_valid } = validationResult.validation;

  return (
    <div className="validation-panel">
      <div className="panel-header">
        <h3>Validation Results</h3>
        <span className={`status ${circuit_valid ? 'valid' : 'invalid'}`}>
          {circuit_valid ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {circuit_valid ? 'All OK' : `${issues.length} Issues`}
        </span>
      </div>

      <div className="issues-list">
        {issues.map((issue, index) => (
          <div key={index} className={`issue-card severity-${issue.severity}`}>
            <div className="issue-header">
              {issue.severity === 'critical' && <AlertTriangle size={16} />}
              {issue.severity === 'warning' && <AlertCircle size={16} />}
              <span className="issue-type">{issue.type}</span>
            </div>

            <div className="issue-body">
              <p className="issue-message">{issue.message}</p>

              <div className="issue-details">
                {Object.entries(issue.details).map(([key, value]) => (
                  <div key={key} className="detail-row">
                    <span>{key}:</span>
                    <span>{value}</span>
                  </div>
                ))}
              </div>

              {issue.fix && (
                <div className="issue-fix">
                  <p className="fix-label">💡 Fix:</p>
                  <p>{issue.fix.reasoning}</p>
                  <button className="apply-fix-btn">Apply Fix</button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Step 8: Run & Build

### Development

```bash
# Start Vite dev server + Electron
npm run electron:dev
```

### Production Build

```bash
# Build for macOS
npm run electron:build

# Output: release/Circuit-AI.dmg
```

---

## Summary

**What ChatGPT/Gemini needs to do:**

1. **Setup project** (Step 1-2)
2. **Copy API client** (Step 4)
3. **Copy state management** (Step 5)
4. **Build UI components** (Step 6-7)
   - Toolbar (file upload)
   - Component tree (left panel)
   - 3D canvas (center)
   - Validation panel (right)
5. **Add styling** (CSS from Step 6)
6. **Test with backend** (API must be running)

**Total time:** 1-2 days for basic version, 1 week for polished.

**The backend is already built. Frontend just displays data.**
