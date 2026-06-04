# Circuit-Mecha Workspace — Implementation Plan 1 (Foundation + Core Demo Loop)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the JARVIS workspace — drop a file, JARVIS narrates, nodes appear on an interactive canvas, validation results surface in plain English with no jargon.

**Architecture:** React Flow powers the infinite dark canvas with custom node types. Zustand holds project state (nodes, connections, JARVIS messages, drawer). JARVIS has three presence zones: top command bar, notification strip (slides in when something happens), conversation drawer (bottom). Clicking a node opens a right-side detail drawer.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind v4, @xyflow/react v12 (canvas), Zustand v5 (state), Framer Motion (animations), Radix UI Tabs (drawer tabs)

**Spec:** `docs/superpowers/specs/2026-04-14-circuit-mecha-workspace-design.md`

**Dev server:** `cd circuit-ai-frontend && npm run dev` → http://localhost:3000

---

## File Map

### New files
```
lib/utils.ts                                  ← cn helper (currently missing — breaks everything)
lib/store.ts                                  ← Zustand project state
lib/jarvis.ts                                 ← JARVIS message formatting + file type detection
lib/node-types.ts                             ← Node type registry + type definitions

app/workspace/page.tsx                        ← Workspace shell page
app/workspace/[project-id]/page.tsx           ← Saved project loader
app/api/proxy/validate/route.ts               ← Circuit-AI validation proxy
app/api/proxy/extract/route.ts                ← Circuit-AI board extraction proxy

components/workspace/canvas.tsx               ← React Flow canvas wrapper
components/workspace/empty-state.tsx          ← Starter tiles shown on empty canvas
components/workspace/nodes/base-node.tsx      ← Shared node card shell
components/workspace/nodes/file-node.tsx      ← File Node
components/workspace/nodes/board-node.tsx     ← Board Node
components/workspace/nodes/validation-node.tsx ← Validation Node
components/workspace/nodes/node-registry.ts   ← nodeTypes map for React Flow

components/jarvis/command-bar.tsx             ← Top bar: logo + input + status
components/jarvis/notification-strip.tsx      ← Slide-in strip when JARVIS speaks
components/jarvis/conversation-drawer.tsx     ← Bottom history panel

components/drawer/node-drawer.tsx             ← Right-side drawer shell
components/drawer/board-drawer.tsx            ← Board node detail (Overview/Issues/Structure/Parts/Manufacture)
components/drawer/validation-drawer.tsx       ← Validation node detail

components/ui/tabs.tsx                        ← Radix Tabs wrapper (currently missing)
components/ui/badge.tsx                       ← Status badge component
```

### Modified files
```
app/globals.css                               ← Add workspace color tokens
app/layout.tsx                                ← Wrap with Zustand-compatible provider (none needed — Zustand is store-only)
next.config.ts                                ← Add CIRCUIT_AI_API_URL + MECHA_API_URL rewrites
```

---

## Task 1: Fix the build — create lib/utils.ts and missing UI components

`WorkbenchCanvas`, `StudioShell`, and other existing components all import `cn` from `@/lib/utils`. This file does not exist. The build is broken. Fix this first.

**Files:**
- Create: `lib/utils.ts`
- Create: `components/ui/tabs.tsx`
- Create: `components/ui/badge.tsx`

- [ ] **Step 1: Create lib/utils.ts**

```typescript
// lib/utils.ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 2: Check clsx and tailwind-merge are installed**

```bash
cd circuit-ai-frontend && cat package.json | grep -E "clsx|tailwind-merge"
```

Expected: both present. If missing, run:
```bash
npm install clsx tailwind-merge
```

- [ ] **Step 3: Create components/ui/tabs.tsx**

```typescript
// components/ui/tabs.tsx
'use client';

import * as TabsPrimitive from '@radix-ui/react-tabs';
import { cn } from '@/lib/utils';

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        'flex gap-1 border-b border-white/8 px-4',
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'pb-2.5 pt-2 text-xs font-semibold uppercase tracking-wider text-slate-500 transition-colors',
        'border-b-2 border-transparent',
        'data-[state=active]:border-cyan-400 data-[state=active]:text-cyan-300',
        'hover:text-slate-300',
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn('flex-1 overflow-y-auto', className)}
      {...props}
    />
  );
}
```

- [ ] **Step 4: Create components/ui/badge.tsx**

```typescript
// components/ui/badge.tsx
import { cn } from '@/lib/utils';

type BadgeVariant = 'critical' | 'error' | 'warning' | 'success' | 'info' | 'muted' | 'processing';

const variantStyles: Record<BadgeVariant, string> = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/20',
  error: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  warning: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  info: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
  muted: 'bg-white/5 text-slate-400 border-white/8',
  processing: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/15 animate-pulse',
};

type BadgeProps = {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
};

export function Badge({ variant = 'muted', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 5: Add workspace color tokens to globals.css**

Add inside the existing `@theme inline {` block in `app/globals.css`, just before the closing `}`:

```css
  /* Workspace tokens */
  --color-ws-base: #080e1a;
  --color-ws-canvas: #0d1421;
  --color-ws-node: #141e2e;
  --color-ws-drawer: #0f172a;
  --color-ws-border: rgba(255, 255, 255, 0.08);
```

- [ ] **Step 6: Verify the dev server starts without errors**

```bash
cd circuit-ai-frontend && npm run dev 2>&1 | head -20
```

Expected: `✓ Ready` with no module-not-found errors about `@/lib/utils`.

- [ ] **Step 7: Commit**

```bash
cd circuit-ai-frontend && git add lib/utils.ts components/ui/tabs.tsx components/ui/badge.tsx app/globals.css && git commit -m "fix: add missing lib/utils.ts, tabs, badge — unblocks build"
```

---

## Task 2: Install new dependencies

**Files:** `package.json`, `package-lock.json`

- [ ] **Step 1: Install @xyflow/react and zustand**

```bash
cd circuit-ai-frontend && npm install @xyflow/react@^12 zustand@^5
```

- [ ] **Step 2: Verify versions**

```bash
cd circuit-ai-frontend && cat package.json | grep -E "xyflow|zustand"
```

Expected:
```
"@xyflow/react": "^12.x.x",
"zustand": "^5.x.x"
```

- [ ] **Step 3: Commit**

```bash
cd circuit-ai-frontend && git add package.json package-lock.json && git commit -m "chore: add @xyflow/react and zustand"
```

---

## Task 3: Project state store

All workspace state lives here. Nodes, connections, JARVIS messages, drawer state.

**Files:**
- Create: `lib/store.ts`
- Create: `lib/node-types.ts`

- [ ] **Step 1: Create lib/node-types.ts — type definitions**

```typescript
// lib/node-types.ts

export type NodeStatus = 'idle' | 'processing' | 'done' | 'error';

export type NodeKind =
  | 'file'
  | 'board'
  | 'validation'
  | 'manufacturing'
  | 'mecha-bundle'
  | 'recipe'
  | 'system';

// Per-kind data shapes
export type FileNodeData = {
  kind: 'file';
  filename: string;
  detectedType: string; // e.g. "KiCAD board file"
  sizeKb: number;
  rawFile?: File;
};

export type BoardNodeData = {
  kind: 'board';
  name: string;
  componentCount: number;
  layerCount: number;
  thumbnailUrl?: string;
  sourceFileNodeId: string;
};

export type ValidationIssue = {
  severity: 'critical' | 'error' | 'warning' | 'info';
  what: string;      // plain English description
  why: string;       // consequence if ignored
  fix: string;       // specific action to take
  raw?: string;      // original backend message, hidden from user
};

export type ValidationNodeData = {
  kind: 'validation';
  healthScore: number;         // 0-100
  critical: number;
  errors: number;
  warnings: number;
  issues: ValidationIssue[];
  sourceBoardNodeId: string;
};

export type ManufacturingFile = {
  type: 'gerber' | 'bom' | 'pnp' | 'dfm' | 'assembly';
  label: string;     // plain English: "Gerber files", "Parts list", etc.
  filename: string;
  downloadUrl?: string;
};

export type ManufacturingNodeData = {
  kind: 'manufacturing';
  files: ManufacturingFile[];
  estimatedCostUsd?: number;
  boardCount?: number;
  sourceBoardNodeId: string;
};

export type NodeData =
  | FileNodeData
  | BoardNodeData
  | ValidationNodeData
  | ManufacturingNodeData;

export type WorkspaceNode = {
  id: string;
  kind: NodeKind;
  status: NodeStatus;
  position: { x: number; y: number };
  data: NodeData;
};

export type WorkspaceEdge = {
  id: string;
  source: string;
  target: string;
};

export type JarvisMessage = {
  id: string;
  role: 'jarvis' | 'user';
  body: string;
  nodeId?: string;    // links message to a canvas node
  timestamp: number;
  actions?: Array<{ label: string; nodeId: string }>; // "→ Show me" buttons
};
```

- [ ] **Step 2: Create lib/store.ts — Zustand store**

```typescript
// lib/store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { WorkspaceNode, WorkspaceEdge, JarvisMessage, NodeData, NodeKind, NodeStatus } from './node-types';

type DrawerState = {
  nodeId: string | null;
  tab: string;
};

type ProjectStore = {
  projectId: string;
  projectName: string;

  // Canvas
  nodes: WorkspaceNode[];
  edges: WorkspaceEdge[];
  viewport: { x: number; y: number; zoom: number };

  // JARVIS
  jarvisMessages: JarvisMessage[];
  jarvisStrip: JarvisMessage | null;   // currently displayed notification
  isJarvisThinking: boolean;

  // Drawer
  drawer: DrawerState;

  // Actions
  setProjectName: (name: string) => void;
  addNode: (node: WorkspaceNode) => void;
  updateNode: (id: string, patch: Partial<Pick<WorkspaceNode, 'status' | 'data'>>) => void;
  addEdge: (edge: WorkspaceEdge) => void;
  setViewport: (viewport: { x: number; y: number; zoom: number }) => void;

  addJarvisMessage: (msg: Omit<JarvisMessage, 'id' | 'timestamp'>) => void;
  showJarvisStrip: (msg: JarvisMessage) => void;
  dismissJarvisStrip: () => void;
  setJarvisThinking: (thinking: boolean) => void;

  openDrawer: (nodeId: string, tab?: string) => void;
  closeDrawer: () => void;
  setDrawerTab: (tab: string) => void;

  clearProject: () => void;
};

let nodeCounter = 0;
let edgeCounter = 0;
let msgCounter = 0;

export const useProjectStore = create<ProjectStore>()(
  persist(
    (set, get) => ({
      projectId: 'default',
      projectName: 'Untitled project',
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      jarvisMessages: [],
      jarvisStrip: null,
      isJarvisThinking: false,
      drawer: { nodeId: null, tab: 'overview' },

      setProjectName: (name) => set({ projectName: name }),

      addNode: (node) =>
        set((state) => ({ nodes: [...state.nodes, node] })),

      updateNode: (id, patch) =>
        set((state) => ({
          nodes: state.nodes.map((n) =>
            n.id === id ? { ...n, ...patch } : n,
          ),
        })),

      addEdge: (edge) =>
        set((state) => ({ edges: [...state.edges, edge] })),

      setViewport: (viewport) => set({ viewport }),

      addJarvisMessage: (msg) => {
        const full: JarvisMessage = {
          ...msg,
          id: `msg-${++msgCounter}`,
          timestamp: Date.now(),
        };
        set((state) => ({
          jarvisMessages: [...state.jarvisMessages, full],
          jarvisStrip: full,
        }));
      },

      showJarvisStrip: (msg) => set({ jarvisStrip: msg }),
      dismissJarvisStrip: () => set({ jarvisStrip: null }),
      setJarvisThinking: (thinking) => set({ isJarvisThinking: thinking }),

      openDrawer: (nodeId, tab = 'overview') =>
        set({ drawer: { nodeId, tab } }),

      closeDrawer: () =>
        set({ drawer: { nodeId: null, tab: 'overview' } }),

      setDrawerTab: (tab) =>
        set((state) => ({ drawer: { ...state.drawer, tab } })),

      clearProject: () =>
        set({
          nodes: [],
          edges: [],
          jarvisMessages: [],
          jarvisStrip: null,
          drawer: { nodeId: null, tab: 'overview' },
        }),
    }),
    {
      name: 'circuit-workspace',
      partialize: (state) => ({
        projectId: state.projectId,
        projectName: state.projectName,
        nodes: state.nodes,
        edges: state.edges,
        viewport: state.viewport,
        jarvisMessages: state.jarvisMessages,
      }),
    },
  ),
);

// Helpers for generating IDs outside the store
export function newNodeId(kind: NodeKind) {
  return `${kind}-${++nodeCounter}-${Date.now()}`;
}

export function newEdgeId(source: string, target: string) {
  return `edge-${source}-${target}-${++edgeCounter}`;
}
```

- [ ] **Step 3: Create lib/jarvis.ts — JARVIS message helpers**

```typescript
// lib/jarvis.ts

export type FileKind = 'kicad-pcb' | 'kicad-netlist' | 'kicad-schematic' | 'json' | 'unknown';

export function detectFileKind(filename: string): FileKind {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.kicad_pcb')) return 'kicad-pcb';
  if (lower.endsWith('.net') || lower.endsWith('.netlist')) return 'kicad-netlist';
  if (lower.endsWith('.kicad_sch')) return 'kicad-schematic';
  if (lower.endsWith('.json')) return 'json';
  return 'unknown';
}

export function fileKindLabel(kind: FileKind): string {
  switch (kind) {
    case 'kicad-pcb': return 'KiCAD board file';
    case 'kicad-netlist': return 'KiCAD netlist';
    case 'kicad-schematic': return 'KiCAD schematic';
    case 'json': return 'Spec file';
    default: return 'File';
  }
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function healthLabel(score: number): string {
  if (score >= 90) return 'Ready to manufacture';
  if (score >= 70) return 'Minor issues';
  if (score >= 40) return 'Needs attention';
  return 'Critical issues found';
}

// JARVIS narration templates — keep these in plain English
export const jarvis = {
  fileDropped: (filename: string, kind: string) =>
    `Got it — I can see this is a ${kind}. Parsing it now.`,

  boardFound: (name: string, components: number, layers: number) =>
    `Found your board. ${components} components across ${layers} layers. Want me to check it for issues?`,

  validationStart: () =>
    `Checking your board for issues…`,

  validationClean: () =>
    `Your board looks clean — no critical issues. Ready to generate the manufacturing files.`,

  validationIssues: (critical: number, total: number) =>
    critical > 0
      ? `Found ${total} issue${total !== 1 ? 's' : ''}, including ${critical} critical. ${critical === 1 ? 'This one' : 'These'} need${critical === 1 ? 's' : ''} fixing before you can manufacture.`
      : `Found ${total} minor issue${total !== 1 ? 's' : ''}. These won't block manufacturing but are worth fixing.`,

  validationError: (message: string) =>
    `Something went wrong checking your board: ${message}. Try re-uploading the file.`,

  thinkingStart: () =>
    `On it…`,
};
```

- [ ] **Step 4: Commit**

```bash
cd circuit-ai-frontend && git add lib/node-types.ts lib/store.ts lib/jarvis.ts && git commit -m "feat: add Zustand project store and node type definitions"
```

---

## Task 4: API proxy routes

Next.js route handlers that forward requests to Circuit-AI and Mecha-Splicer. The backend URLs come from environment variables.

**Files:**
- Create: `app/api/proxy/validate/route.ts`
- Create: `app/api/proxy/extract/route.ts`
- Modify: `next.config.ts`

- [ ] **Step 1: Update next.config.ts to expose env vars**

```typescript
// next.config.ts
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  devIndicators: false,
  eslint: {
    ignoreDuringBuilds: true,
  },
  env: {
    CIRCUIT_AI_API_URL: process.env.CIRCUIT_AI_API_URL ?? 'http://localhost:5000',
    MECHA_API_URL: process.env.MECHA_API_URL ?? 'http://localhost:8085',
  },
};

export default nextConfig;
```

- [ ] **Step 2: Create app/api/proxy/validate/route.ts**

```typescript
// app/api/proxy/validate/route.ts
import { NextRequest, NextResponse } from 'next/server';

const CIRCUIT_AI_URL = process.env.CIRCUIT_AI_API_URL ?? 'http://localhost:5000';

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const apiKey = req.headers.get('x-api-key') ?? '';

    const upstream = await fetch(`${CIRCUIT_AI_URL}/api/v2/workflow/validate-kicad`, {
      method: 'POST',
      headers: apiKey ? { 'X-API-Key': apiKey } : {},
      body: formData,
    });

    const data = await upstream.json().catch(() => ({ error: 'Invalid JSON from backend' }));

    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Proxy error';
    return NextResponse.json(
      { error: message, proxy_error: true },
      { status: 502 },
    );
  }
}
```

- [ ] **Step 3: Create app/api/proxy/extract/route.ts**

```typescript
// app/api/proxy/extract/route.ts
import { NextRequest, NextResponse } from 'next/server';

const CIRCUIT_AI_URL = process.env.CIRCUIT_AI_API_URL ?? 'http://localhost:5000';

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const apiKey = req.headers.get('x-api-key') ?? '';

    const upstream = await fetch(`${CIRCUIT_AI_URL}/api/v2/system/extract-board`, {
      method: 'POST',
      headers: apiKey ? { 'X-API-Key': apiKey } : {},
      body: formData,
    });

    const data = await upstream.json().catch(() => ({ error: 'Invalid JSON from backend' }));

    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Proxy error';
    return NextResponse.json(
      { error: message, proxy_error: true },
      { status: 502 },
    );
  }
}
```

- [ ] **Step 4: Commit**

```bash
cd circuit-ai-frontend && git add app/api/proxy/ next.config.ts && git commit -m "feat: add validate and extract API proxy routes"
```

---

## Task 5: Workspace page shell

The page at `/workspace`. Sets up the layout: top bar, canvas area, bottom bar. No content yet.

**Files:**
- Create: `app/workspace/page.tsx`
- Create: `app/workspace/[project-id]/page.tsx`

- [ ] **Step 1: Create app/workspace/page.tsx**

```typescript
// app/workspace/page.tsx
import { WorkspacePage } from '@/components/workspace/workspace-page';

export const metadata = { title: 'Workspace | Circuit.AI' };

export default function Workspace() {
  return <WorkspacePage />;
}
```

- [ ] **Step 2: Create app/workspace/[project-id]/page.tsx**

```typescript
// app/workspace/[project-id]/page.tsx
import { WorkspacePage } from '@/components/workspace/workspace-page';

export const metadata = { title: 'Workspace | Circuit.AI' };

export default function WorkspaceProject({
  params,
}: {
  params: Promise<{ 'project-id': string }>;
}) {
  // params.project-id is used by WorkspacePage via the store
  return <WorkspacePage />;
}
```

- [ ] **Step 3: Create components/workspace/workspace-page.tsx — the full shell**

```typescript
// components/workspace/workspace-page.tsx
'use client';

import { useCallback, useEffect, useRef } from 'react';
import { CommandBar } from '@/components/jarvis/command-bar';
import { NotificationStrip } from '@/components/jarvis/notification-strip';
import { ConversationDrawer } from '@/components/jarvis/conversation-drawer';
import { WorkspaceCanvas } from '@/components/workspace/canvas';
import { NodeDrawer } from '@/components/drawer/node-drawer';
import { useProjectStore } from '@/lib/store';

export function WorkspacePage() {
  const drawer = useProjectStore((s) => s.drawer);

  return (
    <div
      className="flex h-screen flex-col overflow-hidden"
      style={{ background: '#080e1a' }}
    >
      {/* Top command bar */}
      <CommandBar />

      {/* JARVIS notification strip — appears below command bar */}
      <NotificationStrip />

      {/* Canvas + optional right drawer */}
      <div className="relative flex min-h-0 flex-1">
        <WorkspaceCanvas />

        {/* Right detail drawer */}
        {drawer.nodeId && <NodeDrawer />}
      </div>

      {/* Bottom conversation drawer */}
      <ConversationDrawer />
    </div>
  );
}
```

- [ ] **Step 4: Create stub files so the page compiles**

Create each of these as minimal stubs — they'll be fleshed out in later tasks.

`components/jarvis/command-bar.tsx`:
```typescript
'use client';
export function CommandBar() {
  return (
    <div className="flex h-12 items-center border-b border-white/8 bg-[#0d1421] px-4">
      <span className="text-xs text-slate-500">Command bar — Task 7</span>
    </div>
  );
}
```

`components/jarvis/notification-strip.tsx`:
```typescript
'use client';
export function NotificationStrip() { return null; }
```

`components/jarvis/conversation-drawer.tsx`:
```typescript
'use client';
export function ConversationDrawer() {
  return (
    <div className="flex h-8 items-center border-t border-white/8 bg-[#0d1421] px-4">
      <span className="text-xs text-slate-500">JARVIS — Task 9</span>
    </div>
  );
}
```

`components/workspace/canvas.tsx`:
```typescript
'use client';
export function WorkspaceCanvas() {
  return (
    <div className="flex-1" style={{ background: '#0d1421' }}>
      <div className="flex h-full items-center justify-center">
        <span className="text-sm text-slate-500">Canvas — Task 6</span>
      </div>
    </div>
  );
}
```

`components/drawer/node-drawer.tsx`:
```typescript
'use client';
export function NodeDrawer() { return null; }
```

- [ ] **Step 5: Verify `/workspace` loads in browser**

```bash
cd circuit-ai-frontend && npm run dev
```

Open http://localhost:3000/workspace — expect a dark screen with stub text in the right places.

- [ ] **Step 6: Commit**

```bash
cd circuit-ai-frontend && git add app/workspace/ components/workspace/workspace-page.tsx components/jarvis/ components/drawer/node-drawer.tsx && git commit -m "feat: workspace shell page and layout structure"
```

---

## Task 6: React Flow canvas with empty state

Replace the canvas stub with a real React Flow canvas: dark background, dot grid, zoom/pan, and empty state starter tiles.

**Files:**
- Modify: `components/workspace/canvas.tsx`
- Create: `components/workspace/empty-state.tsx`

- [ ] **Step 1: Create components/workspace/empty-state.tsx**

```typescript
// components/workspace/empty-state.tsx
'use client';

import { useProjectStore } from '@/lib/store';
import { jarvis, detectFileKind, fileKindLabel, formatFileSize } from '@/lib/jarvis';
import { newNodeId } from '@/lib/store';
import type { WorkspaceNode } from '@/lib/node-types';

const starters = [
  {
    id: 'validate',
    icon: '⚡',
    title: 'Check a PCB design',
    body: 'I have a KiCAD file and want to know if it\'s ready to manufacture.',
  },
  {
    id: 'recipe',
    icon: '🔧',
    title: 'See what I can build',
    body: 'I have spare electronics parts and want to find profitable projects.',
  },
  {
    id: 'enclosure',
    icon: '📦',
    title: 'Design an enclosure',
    body: 'I have a PCB and want to 3D-print a custom housing for it.',
  },
];

export function EmptyState() {
  const addJarvisMessage = useProjectStore((s) => s.addJarvisMessage);

  const handleStarter = (id: string) => {
    const starter = starters.find((s) => s.id === id);
    if (!starter) return;
    addJarvisMessage({ role: 'user', body: starter.body });
    addJarvisMessage({
      role: 'jarvis',
      body:
        id === 'validate'
          ? 'Drop your KiCAD board file (.kicad_pcb or .net) anywhere on the canvas and I\'ll check it.'
          : id === 'recipe'
          ? 'Tell me what parts you have — for example "Arduino Uno, BME280 sensor, 16x2 LCD" — and I\'ll find the best projects for your inventory.'
          : 'Drop your KiCAD file first so I can read the board dimensions, then I\'ll spec the enclosure.',
    });
  };

  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <div className="pointer-events-auto flex flex-col items-center gap-6">
        <div className="text-center">
          <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
            Circuit.AI Workspace
          </div>
          <div className="mt-2 text-lg font-semibold text-white">
            Drop a file or choose a starting point
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {starters.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => handleStarter(s.id)}
              className="w-60 rounded-2xl border border-white/8 bg-[#141e2e] p-4 text-left transition-all hover:border-cyan-400/30 hover:bg-[#1a2840]"
            >
              <div className="mb-2 text-2xl">{s.icon}</div>
              <div className="text-sm font-semibold text-white">{s.title}</div>
              <div className="mt-1 text-xs leading-5 text-slate-400">{s.body}</div>
            </button>
          ))}
        </div>
        <div className="text-xs text-slate-600">
          or drag a .kicad_pcb / .net / .json file here
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build the real canvas component**

```typescript
// components/workspace/canvas.tsx
'use client';

import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { EmptyState } from './empty-state';
import { useProjectStore, newNodeId, newEdgeId } from '@/lib/store';
import { detectFileKind, fileKindLabel, formatFileSize, jarvis } from '@/lib/jarvis';
import type { FileNodeData } from '@/lib/node-types';

// Node type components (stubs for now — replaced in Task 7)
import { FileNodeComponent } from './nodes/file-node';
import { BoardNodeComponent } from './nodes/board-node';
import { ValidationNodeComponent } from './nodes/validation-node';

const nodeTypes = {
  file: FileNodeComponent,
  board: BoardNodeComponent,
  validation: ValidationNodeComponent,
};

export function WorkspaceCanvas() {
  const storeNodes = useProjectStore((s) => s.nodes);
  const storeEdges = useProjectStore((s) => s.edges);
  const addNode = useProjectStore((s) => s.addNode);
  const addEdge = useProjectStore((s) => s.addEdge);
  const addJarvisMessage = useProjectStore((s) => s.addJarvisMessage);
  const setJarvisThinking = useProjectStore((s) => s.setJarvisThinking);

  // Convert store nodes to React Flow nodes
  const rfNodes: Node[] = storeNodes.map((n) => ({
    id: n.id,
    type: n.kind,
    position: n.position,
    data: { ...n.data, status: n.status },
  }));

  const rfEdges: Edge[] = storeEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: false,
    style: { stroke: 'rgba(34,211,238,0.4)', strokeWidth: 2 },
  }));

  const [nodes, , onNodesChange] = useNodesState(rfNodes);
  const [edges, , onEdgesChange] = useEdgesState(rfEdges);

  const handleFileDrop = useCallback(
    async (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (!file) return;

      const kind = detectFileKind(file.name);
      const label = fileKindLabel(kind);
      const nodeId = newNodeId('file');

      // Drop position relative to canvas
      const rect = (e.target as HTMLDivElement).getBoundingClientRect();
      const position = {
        x: e.clientX - rect.left - 110,
        y: e.clientY - rect.top - 40,
      };

      const fileData: FileNodeData = {
        kind: 'file',
        filename: file.name,
        detectedType: label,
        sizeKb: Math.round(file.size / 1024),
        rawFile: file,
      };

      addNode({
        id: nodeId,
        kind: 'file',
        status: 'done',
        position,
        data: fileData,
      });

      addJarvisMessage({
        role: 'jarvis',
        body: jarvis.fileDropped(file.name, label),
        nodeId,
      });
    },
    [addNode, addJarvisMessage],
  );

  const isEmpty = storeNodes.length === 0;

  return (
    <div
      className="relative h-full w-full"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleFileDrop}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView={!isEmpty}
        colorMode="dark"
        style={{ background: '#0d1421' }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1.2}
          color="rgba(255,255,255,0.06)"
        />
        <Controls
          className="[&>button]:border-white/8 [&>button]:bg-[#141e2e] [&>button]:text-slate-400"
          showInteractive={false}
        />
        <MiniMap
          nodeColor="#22d3ee22"
          maskColor="rgba(8,14,26,0.8)"
          style={{ background: '#141e2e', border: '1px solid rgba(255,255,255,0.08)' }}
        />
      </ReactFlow>

      {isEmpty && <EmptyState />}
    </div>
  );
}
```

- [ ] **Step 3: Create node stub files so canvas compiles**

`components/workspace/nodes/file-node.tsx`:
```typescript
'use client';
import type { NodeProps } from '@xyflow/react';
export function FileNodeComponent({ data }: NodeProps) {
  return (
    <div className="rounded-2xl border border-white/8 bg-[#141e2e] p-3 text-xs text-slate-300 shadow-lg" style={{ width: 220 }}>
      <div className="font-semibold text-white">📄 {(data as any).filename}</div>
      <div className="mt-1 text-slate-400">{(data as any).detectedType}</div>
    </div>
  );
}
```

`components/workspace/nodes/board-node.tsx`:
```typescript
'use client';
import type { NodeProps } from '@xyflow/react';
export function BoardNodeComponent({ data }: NodeProps) {
  return (
    <div className="rounded-2xl border border-cyan-400/20 bg-[#141e2e] p-3 text-xs text-slate-300 shadow-lg" style={{ width: 220 }}>
      <div className="font-semibold text-cyan-300">⚡ {(data as any).name ?? 'Board'}</div>
      <div className="mt-1 text-slate-400">{(data as any).componentCount} components</div>
    </div>
  );
}
```

`components/workspace/nodes/validation-node.tsx`:
```typescript
'use client';
import type { NodeProps } from '@xyflow/react';
export function ValidationNodeComponent({ data }: NodeProps) {
  const score = (data as any).healthScore ?? 0;
  const color = score >= 80 ? 'text-emerald-300 border-emerald-400/20' : score >= 50 ? 'text-amber-300 border-amber-400/20' : 'text-red-300 border-red-400/20';
  return (
    <div className={`rounded-2xl border bg-[#141e2e] p-3 text-xs shadow-lg ${color}`} style={{ width: 220 }}>
      <div className="font-semibold">✓ Validation</div>
      <div className="mt-1 text-slate-400">Health score: {score}/100</div>
    </div>
  );
}
```

- [ ] **Step 4: Add React Flow base styles to globals.css**

Add at the bottom of `app/globals.css`:
```css
/* React Flow overrides */
.react-flow__renderer {
  background: transparent !important;
}
```

- [ ] **Step 5: Verify canvas renders at /workspace**

Start dev server, open http://localhost:3000/workspace. Expect: dark canvas with dot grid, empty state starter tiles centered, zoom/pan controls bottom-left, minimap bottom-right.

- [ ] **Step 6: Verify file drop creates a node**

Drag any file (e.g. a `.kicad_pcb` or even just a text file renamed to `.kicad_pcb`) onto the canvas. Expect a stub node to appear at the drop position.

- [ ] **Step 7: Commit**

```bash
cd circuit-ai-frontend && git add components/workspace/ && git commit -m "feat: React Flow canvas with dot grid, empty state, and file drop"
```

---

## Task 7: JARVIS command bar

The top bar: logo left, command input center, backend status + key icon right. The input is the primary interface — file drops here too.

**Files:**
- Modify: `components/jarvis/command-bar.tsx`

- [ ] **Step 1: Replace command-bar.tsx stub with full implementation**

```typescript
// components/jarvis/command-bar.tsx
'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import { CircuitBoard, KeyRound, Loader2, Zap } from 'lucide-react';
import { useProjectStore } from '@/lib/store';
import { jarvis, detectFileKind, fileKindLabel } from '@/lib/jarvis';
import type { FileNodeData } from '@/lib/node-types';
import { newNodeId } from '@/lib/store';

export function CommandBar() {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const isThinking = useProjectStore((s) => s.isJarvisThinking);
  const addNode = useProjectStore((s) => s.addNode);
  const addJarvisMessage = useProjectStore((s) => s.addJarvisMessage);
  const projectName = useProjectStore((s) => s.projectName);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    addJarvisMessage({ role: 'user', body: trimmed });
    addJarvisMessage({
      role: 'jarvis',
      body: 'Got it. Drop your board file on the canvas and I\'ll take it from there.',
    });
    setInput('');
  };

  const handleFileDrop = (e: React.DragEvent<HTMLFormElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;

    const kind = detectFileKind(file.name);
    const label = fileKindLabel(kind);
    const nodeId = newNodeId('file');

    const fileData: FileNodeData = {
      kind: 'file',
      filename: file.name,
      detectedType: label,
      sizeKb: Math.round(file.size / 1024),
      rawFile: file,
    };

    addNode({
      id: nodeId,
      kind: 'file',
      status: 'done',
      position: { x: 200, y: 200 },
      data: fileData,
    });

    addJarvisMessage({
      role: 'jarvis',
      body: jarvis.fileDropped(file.name, label),
      nodeId,
    });
  };

  return (
    <div className="flex h-12 shrink-0 items-center gap-3 border-b border-white/8 bg-[#0d1421] px-4">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2 shrink-0">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-400/10">
          <CircuitBoard className="h-4 w-4 text-cyan-400" />
        </div>
        <span className="hidden text-sm font-semibold text-white sm:block">Circuit.AI</span>
      </Link>

      {/* Project name */}
      <div className="hidden h-5 w-px bg-white/8 sm:block" />
      <span className="hidden max-w-[120px] truncate text-xs text-slate-400 sm:block">
        {projectName}
      </span>

      {/* Command input */}
      <form
        onSubmit={handleSubmit}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleFileDrop}
        className="flex flex-1 items-center"
      >
        <div className="relative flex w-full max-w-xl items-center gap-2 rounded-full border border-white/8 bg-white/4 px-3 py-1.5 transition-colors focus-within:border-cyan-400/30 focus-within:bg-white/6">
          {isThinking ? (
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-cyan-400" />
          ) : (
            <Zap className="h-3.5 w-3.5 shrink-0 text-slate-500" />
          )}
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="What do you want to build?"
            className="flex-1 bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
          />
        </div>
      </form>

      {/* Right: backend status + key */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="hidden text-xs text-slate-400 sm:block">Live</span>
        </div>
        <Link
          href="/dashboard/keys"
          className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/8 bg-white/4 text-slate-400 transition-colors hover:text-white"
        >
          <KeyRound className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify command bar renders correctly**

Open http://localhost:3000/workspace. Expect: dark top bar with Circuit.AI logo left, centered input with placeholder "What do you want to build?", green status dot and key icon right.

- [ ] **Step 3: Commit**

```bash
cd circuit-ai-frontend && git add components/jarvis/command-bar.tsx && git commit -m "feat: JARVIS command bar with file drop and text input"
```

---

## Task 8: JARVIS notification strip

Slides in below the command bar when JARVIS has something to say. Auto-dismisses after 8 seconds. Has a "→ Show me" action.

**Files:**
- Modify: `components/jarvis/notification-strip.tsx`

- [ ] **Step 1: Replace stub with full implementation**

```typescript
// components/jarvis/notification-strip.tsx
'use client';

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Zap } from 'lucide-react';
import { useProjectStore } from '@/lib/store';

export function NotificationStrip() {
  const strip = useProjectStore((s) => s.jarvisStrip);
  const dismiss = useProjectStore((s) => s.dismissJarvisStrip);
  const openDrawer = useProjectStore((s) => s.openDrawer);

  useEffect(() => {
    if (!strip) return;
    const timer = setTimeout(dismiss, 8000);
    return () => clearTimeout(timer);
  }, [strip, dismiss]);

  return (
    <AnimatePresence>
      {strip && (
        <motion.div
          key={strip.id}
          initial={{ opacity: 0, y: -8, height: 0 }}
          animate={{ opacity: 1, y: 0, height: 'auto' }}
          exit={{ opacity: 0, y: -8, height: 0 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          className="shrink-0 overflow-hidden border-b border-cyan-400/10 bg-cyan-400/5"
        >
          <div className="flex items-center gap-3 px-4 py-2">
            <Zap className="h-3.5 w-3.5 shrink-0 text-cyan-400" />
            <span className="flex-1 text-sm text-slate-200">{strip.body}</span>
            {strip.nodeId && (
              <button
                type="button"
                onClick={() => {
                  openDrawer(strip.nodeId!);
                  dismiss();
                }}
                className="shrink-0 text-xs font-semibold text-cyan-400 hover:text-cyan-300"
              >
                Show me →
              </button>
            )}
            <button
              type="button"
              onClick={dismiss}
              className="shrink-0 text-slate-500 hover:text-slate-300"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 2: Test — trigger a notification**

In the browser, drop a file on the canvas. The notification strip should slide in below the command bar with JARVIS's message. It should auto-dismiss after 8s.

- [ ] **Step 3: Commit**

```bash
cd circuit-ai-frontend && git add components/jarvis/notification-strip.tsx && git commit -m "feat: JARVIS notification strip with auto-dismiss"
```

---

## Task 9: JARVIS conversation drawer (bottom)

Collapsed by default — shows last message. Expands to show full history. Messages are linked to nodes.

**Files:**
- Modify: `components/jarvis/conversation-drawer.tsx`

- [ ] **Step 1: Replace stub with full implementation**

```typescript
// components/jarvis/conversation-drawer.tsx
'use client';

import { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronUp, ChevronDown, Zap, User } from 'lucide-react';
import { useProjectStore } from '@/lib/store';

export function ConversationDrawer() {
  const [expanded, setExpanded] = useState(false);
  const messages = useProjectStore((s) => s.jarvisMessages);
  const openDrawer = useProjectStore((s) => s.openDrawer);
  const last = messages[messages.length - 1];

  return (
    <div className="shrink-0 border-t border-white/8 bg-[#0d1421]">
      {/* Collapsed bar */}
      <div className="flex items-center gap-3 px-4 py-2">
        <Zap className="h-3.5 w-3.5 shrink-0 text-cyan-400" />
        <span className="flex-1 truncate text-xs text-slate-400">
          {last?.role === 'jarvis' ? last.body : 'What do you want to build?'}
        </span>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300"
        >
          {expanded ? (
            <><ChevronDown className="h-3.5 w-3.5" /> Collapse</>
          ) : (
            <><ChevronUp className="h-3.5 w-3.5" /> History</>
          )}
        </button>
      </div>

      {/* Expanded history */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 280 }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="overflow-hidden border-t border-white/8"
          >
            <div className="h-[280px] space-y-1 overflow-y-auto p-4">
              {messages.length === 0 && (
                <div className="py-8 text-center text-sm text-slate-600">
                  No conversation yet. Drop a file or type a question above.
                </div>
              )}
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                    msg.role === 'jarvis'
                      ? 'bg-cyan-400/10 text-cyan-400'
                      : 'bg-white/8 text-slate-400'
                  }`}>
                    {msg.role === 'jarvis' ? (
                      <Zap className="h-3 w-3" />
                    ) : (
                      <User className="h-3 w-3" />
                    )}
                  </div>
                  <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-xs leading-5 ${
                    msg.role === 'jarvis'
                      ? 'bg-white/4 text-slate-200'
                      : 'bg-cyan-400/10 text-cyan-200'
                  }`}>
                    {msg.body}
                    {msg.nodeId && (
                      <button
                        type="button"
                        onClick={() => openDrawer(msg.nodeId!)}
                        className="ml-2 font-semibold text-cyan-400 hover:text-cyan-300"
                      >
                        Show →
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
```

- [ ] **Step 2: Verify — expand history panel**

Drop a file on the canvas. Click "History ↑" in the bottom bar. Expect the history panel to expand showing the JARVIS narration and file message.

- [ ] **Step 3: Commit**

```bash
cd circuit-ai-frontend && git add components/jarvis/conversation-drawer.tsx && git commit -m "feat: JARVIS conversation history drawer"
```

---

## Task 10: Real node components

Replace the stub node components with proper, styled implementations.

**Files:**
- Modify: `components/workspace/nodes/file-node.tsx`
- Modify: `components/workspace/nodes/board-node.tsx`
- Modify: `components/workspace/nodes/validation-node.tsx`

- [ ] **Step 1: Real file-node.tsx**

```typescript
// components/workspace/nodes/file-node.tsx
'use client';

import { Handle, Position, type NodeProps } from '@xyflow/react';
import { FileText, Zap } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { useProjectStore } from '@/lib/store';
import { newNodeId, newEdgeId } from '@/lib/store';
import { jarvis } from '@/lib/jarvis';
import type { FileNodeData, BoardNodeData } from '@/lib/node-types';

export function FileNodeComponent({ id, data }: NodeProps) {
  const d = data as FileNodeData & { status: string };
  const addNode = useProjectStore((s) => s.addNode);
  const addEdge = useProjectStore((s) => s.addEdge);
  const addJarvisMessage = useProjectStore((s) => s.addJarvisMessage);
  const updateNode = useProjectStore((s) => s.updateNode);
  const nodes = useProjectStore((s) => s.nodes);
  const thisNode = nodes.find((n) => n.id === id);

  const handleParse = async () => {
    if (!d.rawFile) {
      addJarvisMessage({ role: 'jarvis', body: 'I don\'t have the file content. Try dropping the file again.', nodeId: id });
      return;
    }

    updateNode(id, { status: 'processing' });
    addJarvisMessage({ role: 'jarvis', body: jarvis.boardFound('your board', 47, 4), nodeId: id });

    // Create a Board node immediately (with placeholder data — real parsing in Task 13)
    const boardId = newNodeId('board');
    const boardData: BoardNodeData = {
      kind: 'board',
      name: d.filename.replace(/\.(kicad_pcb|net|netlist)$/i, ''),
      componentCount: 47,
      layerCount: 4,
      sourceFileNodeId: id,
    };

    addNode({
      id: boardId,
      kind: 'board',
      status: 'done',
      position: {
        x: (thisNode?.position.x ?? 0) + 280,
        y: thisNode?.position.y ?? 0,
      },
      data: boardData,
    });

    addEdge({ id: newEdgeId(id, boardId), source: id, target: boardId });
    updateNode(id, { status: 'done' });
  };

  return (
    <div
      className="rounded-2xl border border-white/8 bg-[#141e2e] shadow-[0_4px_24px_rgba(0,0,0,0.5)]"
      style={{ width: 220 }}
    >
      <Handle type="source" position={Position.Right} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', width: 8, height: 8 }} />

      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/5">
              <FileText className="h-3.5 w-3.5 text-slate-400" />
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">File</div>
              <div className="text-xs font-semibold text-white truncate max-w-[110px]">{d.filename}</div>
            </div>
          </div>
          <Badge variant={d.status === 'processing' ? 'processing' : 'muted'}>
            {d.status === 'processing' ? 'Reading…' : d.detectedType}
          </Badge>
        </div>

        <div className="mt-2 text-[11px] text-slate-500">{d.sizeKb} KB</div>

        {d.status !== 'processing' && (
          <button
            type="button"
            onClick={handleParse}
            className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl border border-cyan-400/20 bg-cyan-400/8 py-1.5 text-xs font-semibold text-cyan-300 transition-colors hover:bg-cyan-400/15"
          >
            <Zap className="h-3 w-3" />
            Parse board
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Real board-node.tsx**

```typescript
// components/workspace/nodes/board-node.tsx
'use client';

import { Handle, Position, type NodeProps } from '@xyflow/react';
import { CircuitBoard, CheckCircle, AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { useProjectStore, newNodeId, newEdgeId } from '@/lib/store';
import { jarvis } from '@/lib/jarvis';
import type { BoardNodeData, ValidationNodeData, ValidationIssue } from '@/lib/node-types';

export function BoardNodeComponent({ id, data }: NodeProps) {
  const d = data as BoardNodeData & { status: string };
  const addNode = useProjectStore((s) => s.addNode);
  const addEdge = useProjectStore((s) => s.addEdge);
  const addJarvisMessage = useProjectStore((s) => s.addJarvisMessage);
  const updateNode = useProjectStore((s) => s.updateNode);
  const openDrawer = useProjectStore((s) => s.openDrawer);
  const nodes = useProjectStore((s) => s.nodes);
  const thisNode = nodes.find((n) => n.id === id);

  const handleValidate = async () => {
    updateNode(id, { status: 'processing' });
    addJarvisMessage({ role: 'jarvis', body: jarvis.validationStart(), nodeId: id });

    // Find the source file node to get the raw file
    const sourceFile = nodes.find((n) => n.id === d.sourceFileNodeId);
    const rawFile = (sourceFile?.data as any)?.rawFile as File | undefined;

    try {
      let result: any = null;

      if (rawFile) {
        const form = new FormData();
        form.append('file', rawFile);
        const res = await fetch('/api/proxy/validate', { method: 'POST', body: form });
        result = await res.json();
      }

      // Parse issues from backend or use demo data if backend is offline
      const issues: ValidationIssue[] = result?.validation?.issues?.map((i: any) => ({
        severity: i.severity ?? 'warning',
        what: i.issue ?? i.message ?? 'Unknown issue',
        why: i.explanation ?? 'Could affect manufacturing or reliability.',
        fix: i.solution ?? i.fix ?? 'Review the design and consult the datasheet.',
        raw: JSON.stringify(i),
      })) ?? [
        {
          severity: 'warning' as const,
          what: 'Backend offline — showing demo validation',
          why: 'The Circuit-AI backend is not reachable at the configured URL.',
          fix: 'Start the backend with `python api_server.py` and set CIRCUIT_AI_API_URL.',
        },
      ];

      const critical = issues.filter((i) => i.severity === 'critical').length;
      const errors = issues.filter((i) => i.severity === 'error').length;
      const warnings = issues.filter((i) => i.severity === 'warning').length;
      const healthScore = Math.max(0, 100 - critical * 30 - errors * 10 - warnings * 3);

      const validationId = newNodeId('validation');
      const validationData: ValidationNodeData = {
        kind: 'validation',
        healthScore,
        critical,
        errors,
        warnings,
        issues,
        sourceBoardNodeId: id,
      };

      addNode({
        id: validationId,
        kind: 'validation',
        status: 'done',
        position: {
          x: (thisNode?.position.x ?? 0) + 280,
          y: thisNode?.position.y ?? 0,
        },
        data: validationData,
      });

      addEdge({ id: newEdgeId(id, validationId), source: id, target: validationId });
      updateNode(id, { status: 'done' });

      addJarvisMessage({
        role: 'jarvis',
        body: critical > 0 ? jarvis.validationIssues(critical, issues.length) : jarvis.validationClean(),
        nodeId: validationId,
        actions: [{ label: 'Show me', nodeId: validationId }],
      });
    } catch (err) {
      updateNode(id, { status: 'error' });
      addJarvisMessage({
        role: 'jarvis',
        body: jarvis.validationError(err instanceof Error ? err.message : 'Unknown error'),
        nodeId: id,
      });
    }
  };

  return (
    <div
      className="rounded-2xl border border-cyan-400/15 bg-[#141e2e] shadow-[0_4px_24px_rgba(0,0,0,0.5)]"
      style={{ width: 220 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: 'rgba(34,211,238,0.3)', border: 'none', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} style={{ background: 'rgba(34,211,238,0.3)', border: 'none', width: 8, height: 8 }} />

      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-400/10">
              <CircuitBoard className="h-3.5 w-3.5 text-cyan-400" />
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-cyan-500">Board</div>
              <div className="text-xs font-semibold text-white truncate max-w-[100px]">{d.name}</div>
            </div>
          </div>
          <Badge variant={d.status === 'processing' ? 'processing' : 'info'}>
            {d.status === 'processing' ? 'Checking…' : `${d.layerCount}L`}
          </Badge>
        </div>

        <div className="mt-2 text-[11px] text-slate-500">{d.componentCount} components</div>

        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={handleValidate}
            disabled={d.status === 'processing'}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-cyan-400/20 bg-cyan-400/8 py-1.5 text-xs font-semibold text-cyan-300 transition-colors hover:bg-cyan-400/15 disabled:opacity-40"
          >
            <CheckCircle className="h-3 w-3" />
            Check issues
          </button>
          <button
            type="button"
            onClick={() => openDrawer(id)}
            className="flex items-center justify-center rounded-xl border border-white/8 bg-white/4 px-2 py-1.5 text-slate-400 transition-colors hover:text-white"
          >
            <AlertTriangle className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Real validation-node.tsx**

```typescript
// components/workspace/nodes/validation-node.tsx
'use client';

import { Handle, Position, type NodeProps } from '@xyflow/react';
import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { useProjectStore } from '@/lib/store';
import { healthLabel } from '@/lib/jarvis';
import type { ValidationNodeData } from '@/lib/node-types';

export function ValidationNodeComponent({ id, data }: NodeProps) {
  const d = data as ValidationNodeData & { status: string };
  const openDrawer = useProjectStore((s) => s.openDrawer);

  const scoreColor =
    d.healthScore >= 80
      ? 'text-emerald-400'
      : d.healthScore >= 50
      ? 'text-amber-400'
      : 'text-red-400';

  const borderColor =
    d.healthScore >= 80
      ? 'border-emerald-400/15'
      : d.healthScore >= 50
      ? 'border-amber-400/15'
      : 'border-red-400/15';

  return (
    <div
      className={`rounded-2xl border bg-[#141e2e] shadow-[0_4px_24px_rgba(0,0,0,0.5)] ${borderColor}`}
      style={{ width: 220 }}
    >
      <Handle type="target" position={Position.Left} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', width: 8, height: 8 }} />

      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${
              d.healthScore >= 80 ? 'bg-emerald-400/10' : d.healthScore >= 50 ? 'bg-amber-400/10' : 'bg-red-400/10'
            }`}>
              {d.healthScore >= 80 ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              ) : d.healthScore >= 50 ? (
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
              ) : (
                <XCircle className="h-3.5 w-3.5 text-red-400" />
              )}
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Validation</div>
              <div className={`text-xs font-semibold ${scoreColor}`}>{d.healthScore}/100</div>
            </div>
          </div>
          {d.critical > 0 && <Badge variant="critical">{d.critical} critical</Badge>}
          {d.critical === 0 && d.errors > 0 && <Badge variant="error">{d.errors} error{d.errors !== 1 ? 's' : ''}</Badge>}
          {d.critical === 0 && d.errors === 0 && <Badge variant="success">Clean</Badge>}
        </div>

        <div className="mt-2 text-[11px] text-slate-500">{healthLabel(d.healthScore)}</div>

        {/* Mini severity bars */}
        <div className="mt-2 flex gap-1">
          {d.critical > 0 && (
            <div className="flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] text-red-400">
              <XCircle className="h-2.5 w-2.5" /> {d.critical}
            </div>
          )}
          {d.errors > 0 && (
            <div className="flex items-center gap-1 rounded-full bg-orange-500/10 px-2 py-0.5 text-[10px] text-orange-400">
              <AlertTriangle className="h-2.5 w-2.5" /> {d.errors}
            </div>
          )}
          {d.warnings > 0 && (
            <div className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-400">
              {d.warnings}w
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => openDrawer(id, 'issues')}
          className="mt-3 w-full rounded-xl border border-white/8 bg-white/4 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:bg-white/8"
        >
          See details →
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify full demo flow in browser**

1. Open http://localhost:3000/workspace
2. Drag a `.kicad_pcb` file onto canvas → File Node appears
3. Click "Parse board" → Board Node appears to the right, connected
4. Click "Check issues" → Validation Node appears, JARVIS notification strips fires
5. Click "See details →" on Validation Node → Drawer opens (still stub at this point)

- [ ] **Step 5: Commit**

```bash
cd circuit-ai-frontend && git add components/workspace/nodes/ && git commit -m "feat: real File, Board, Validation node components with workflow"
```

---

## Task 11: Node detail drawer

Right-side drawer that slides in when a node is clicked. Tabs are specific to node type.

**Files:**
- Modify: `components/drawer/node-drawer.tsx`
- Create: `components/drawer/board-drawer.tsx`
- Create: `components/drawer/validation-drawer.tsx`

- [ ] **Step 1: Real node-drawer.tsx — the shell**

```typescript
// components/drawer/node-drawer.tsx
'use client';

import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { X } from 'lucide-react';
import { useProjectStore } from '@/lib/store';
import { BoardDrawer } from './board-drawer';
import { ValidationDrawer } from './validation-drawer';

export function NodeDrawer() {
  const drawer = useProjectStore((s) => s.drawer);
  const closeDrawer = useProjectStore((s) => s.closeDrawer);
  const nodes = useProjectStore((s) => s.nodes);

  const node = nodes.find((n) => n.id === drawer.nodeId);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDrawer();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [closeDrawer]);

  if (!node) return null;

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 28, stiffness: 280 }}
      className="absolute right-0 top-0 z-20 flex h-full w-[400px] flex-col border-l border-white/8 bg-[#0f172a] shadow-[-20px_0_60px_rgba(0,0,0,0.5)]"
    >
      {/* Drawer header */}
      <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            {node.kind}
          </div>
          <div className="text-sm font-semibold text-white">
            {(node.data as any).name ?? (node.data as any).filename ?? node.kind}
          </div>
        </div>
        <button
          type="button"
          onClick={closeDrawer}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-500 hover:bg-white/8 hover:text-white"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Drawer content — routed by node kind */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {node.kind === 'board' && <BoardDrawer node={node} />}
        {node.kind === 'validation' && <ValidationDrawer node={node} />}
        {node.kind === 'file' && (
          <div className="p-4 text-sm text-slate-400">
            This is your uploaded file. Click "Parse board" on the node to continue.
          </div>
        )}
        {!['board', 'validation', 'file'].includes(node.kind) && (
          <div className="p-4 text-sm text-slate-400">
            Drawer for <strong className="text-white">{node.kind}</strong> nodes coming in Plan 2.
          </div>
        )}
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 2: Create components/drawer/board-drawer.tsx**

```typescript
// components/drawer/board-drawer.tsx
'use client';

import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useProjectStore } from '@/lib/store';
import type { WorkspaceNode, BoardNodeData } from '@/lib/node-types';
import { CircuitBoard, Layers, Package, Wrench } from 'lucide-react';

type Props = { node: WorkspaceNode };

export function BoardDrawer({ node }: Props) {
  const d = node.data as BoardNodeData;
  const drawer = useProjectStore((s) => s.drawer);
  const setTab = useProjectStore((s) => s.setDrawerTab);
  const nodes = useProjectStore((s) => s.nodes);

  // Find any connected validation node
  const validationNode = nodes.find(
    (n) => n.kind === 'validation' && (n.data as any).sourceBoardNodeId === node.id,
  );

  return (
    <Tabs value={drawer.tab} onValueChange={setTab} className="flex flex-1 flex-col overflow-hidden">
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="issues">Issues</TabsTrigger>
        <TabsTrigger value="structure">Structure</TabsTrigger>
        <TabsTrigger value="parts">Parts</TabsTrigger>
        <TabsTrigger value="manufacture">Manufacture</TabsTrigger>
      </TabsList>

      <TabsContent value="overview">
        <div className="space-y-4 p-4">
          <div className="grid grid-cols-2 gap-3">
            {[
              { icon: CircuitBoard, label: 'Components', value: String(d.componentCount) },
              { icon: Layers, label: 'Layers', value: String(d.layerCount) },
            ].map((stat) => (
              <div key={stat.label} className="rounded-2xl border border-white/8 bg-white/4 p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">{stat.label}</div>
                <div className="mt-1 text-xl font-semibold text-white">{stat.value}</div>
              </div>
            ))}
          </div>
          {validationNode ? (
            <div className="rounded-2xl border border-cyan-400/15 bg-cyan-400/5 p-3 text-sm text-slate-300">
              Validation has been run.{' '}
              <button
                type="button"
                onClick={() => setTab('issues')}
                className="font-semibold text-cyan-400 hover:text-cyan-300"
              >
                See issues →
              </button>
            </div>
          ) : (
            <div className="rounded-2xl border border-white/8 bg-white/4 p-3 text-sm text-slate-400">
              Validation hasn't been run yet. Click "Check issues" on the board node to check this design.
            </div>
          )}
        </div>
      </TabsContent>

      <TabsContent value="issues">
        <div className="p-4 text-sm text-slate-400">
          {validationNode ? (
            <button
              type="button"
              onClick={() => useProjectStore.getState().openDrawer(validationNode.id, 'issues')}
              className="text-cyan-400 hover:text-cyan-300"
            >
              View validation results →
            </button>
          ) : (
            'Run validation first — click "Check issues" on the board node.'
          )}
        </div>
      </TabsContent>

      <TabsContent value="structure">
        <div className="p-4 text-sm text-slate-400">
          Board structure extraction coming in Plan 2 (requires backend connection).
        </div>
      </TabsContent>

      <TabsContent value="parts">
        <div className="p-4 text-sm text-slate-400">
          BOM generation coming in Plan 2.
        </div>
      </TabsContent>

      <TabsContent value="manufacture">
        <div className="p-4">
          <div className="rounded-2xl border border-white/8 bg-white/4 p-4 text-center">
            <Wrench className="mx-auto mb-2 h-6 w-6 text-slate-500" />
            <div className="text-sm font-semibold text-white">Manufacturing package</div>
            <div className="mt-1 text-xs text-slate-400">
              Run validation first, then generate Gerbers, BOM, and DFM report in one click.
            </div>
            <div className="mt-3 text-xs text-slate-500">Coming in Plan 2</div>
          </div>
        </div>
      </TabsContent>
    </Tabs>
  );
}
```

- [ ] **Step 3: Create components/drawer/validation-drawer.tsx**

```typescript
// components/drawer/validation-drawer.tsx
'use client';

import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { useProjectStore } from '@/lib/store';
import type { WorkspaceNode, ValidationNodeData, ValidationIssue } from '@/lib/node-types';
import { healthLabel } from '@/lib/jarvis';
import { XCircle, AlertTriangle, Info, ChevronDown } from 'lucide-react';
import { useState } from 'react';

type Props = { node: WorkspaceNode };

const severityIcon = {
  critical: <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0 mt-0.5" />,
  error: <AlertTriangle className="h-3.5 w-3.5 text-orange-400 shrink-0 mt-0.5" />,
  warning: <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />,
  info: <Info className="h-3.5 w-3.5 text-cyan-400 shrink-0 mt-0.5" />,
};

const severityBadge: Record<string, React.ComponentProps<typeof Badge>['variant']> = {
  critical: 'critical',
  error: 'error',
  warning: 'warning',
  info: 'info',
};

function IssueCard({ issue }: { issue: ValidationIssue }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-white/6 bg-white/3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-2 p-3 text-left"
      >
        {severityIcon[issue.severity]}
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-white leading-4">{issue.what}</div>
        </div>
        <Badge variant={severityBadge[issue.severity]}>{issue.severity}</Badge>
        <ChevronDown className={`h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="border-t border-white/6 px-3 pb-3 pt-2 space-y-2">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">Why it matters</div>
            <div className="text-xs text-slate-300 leading-5">{issue.why}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">How to fix it</div>
            <div className="text-xs text-emerald-300 leading-5">{issue.fix}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export function ValidationDrawer({ node }: Props) {
  const d = node.data as ValidationNodeData;
  const drawer = useProjectStore((s) => s.drawer);
  const setTab = useProjectStore((s) => s.setDrawerTab);

  const sorted = [...d.issues].sort((a, b) => {
    const order = { critical: 0, error: 1, warning: 2, info: 3 };
    return (order[a.severity] ?? 4) - (order[b.severity] ?? 4);
  });

  const scoreColor =
    d.healthScore >= 80 ? 'text-emerald-400' : d.healthScore >= 50 ? 'text-amber-400' : 'text-red-400';

  return (
    <Tabs value={drawer.tab} onValueChange={setTab} className="flex flex-1 flex-col overflow-hidden">
      <TabsList>
        <TabsTrigger value="issues">What's wrong</TabsTrigger>
        <TabsTrigger value="summary">Summary</TabsTrigger>
        <TabsTrigger value="next">What to do</TabsTrigger>
      </TabsList>

      <TabsContent value="issues">
        <div className="space-y-2 p-4">
          {sorted.length === 0 ? (
            <div className="py-6 text-center text-sm text-emerald-400">
              No issues found — your board is clean.
            </div>
          ) : (
            sorted.map((issue, i) => <IssueCard key={i} issue={issue} />)
          )}
        </div>
      </TabsContent>

      <TabsContent value="summary">
        <div className="space-y-4 p-4">
          <div className="flex items-center gap-4">
            <div className={`text-5xl font-bold ${scoreColor}`}>{d.healthScore}</div>
            <div>
              <div className="text-xs text-slate-500">Health score</div>
              <div className="text-sm font-semibold text-white">{healthLabel(d.healthScore)}</div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'Critical', count: d.critical, variant: 'critical' as const },
              { label: 'Errors', count: d.errors, variant: 'error' as const },
              { label: 'Warnings', count: d.warnings, variant: 'warning' as const },
            ].map((row) => (
              <div key={row.label} className="rounded-xl border border-white/6 bg-white/3 p-3 text-center">
                <div className="text-2xl font-bold text-white">{row.count}</div>
                <Badge variant={row.variant} className="mt-1">{row.label}</Badge>
              </div>
            ))}
          </div>
        </div>
      </TabsContent>

      <TabsContent value="next">
        <div className="p-4">
          {d.critical > 0 ? (
            <div className="rounded-2xl border border-red-400/15 bg-red-400/5 p-4">
              <div className="text-sm font-semibold text-red-300">Fix {d.critical} critical issue{d.critical !== 1 ? 's' : ''} before manufacturing</div>
              <div className="mt-1 text-xs text-slate-400">Critical issues will prevent the board from functioning. Address these first.</div>
              <button type="button" onClick={() => setTab('issues')} className="mt-3 text-xs font-semibold text-red-400 hover:text-red-300">
                See the issues →
              </button>
            </div>
          ) : d.errors > 0 ? (
            <div className="rounded-2xl border border-orange-400/15 bg-orange-400/5 p-4">
              <div className="text-sm font-semibold text-orange-300">Resolve errors before manufacturing</div>
              <div className="mt-1 text-xs text-slate-400">Your board may function but these errors could cause reliability issues.</div>
            </div>
          ) : (
            <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/5 p-4">
              <div className="text-sm font-semibold text-emerald-300">Your board is ready to manufacture</div>
              <div className="mt-1 text-xs text-slate-400">No blocking issues found. You can generate manufacturing files now.</div>
              <div className="mt-3 text-xs text-slate-500">Manufacturing package generation coming in Plan 2.</div>
            </div>
          )}
        </div>
      </TabsContent>
    </Tabs>
  );
}
```

- [ ] **Step 4: Verify full drawer flow**

1. Drop file → parse → validate
2. Click "See details →" on Validation Node
3. Drawer slides in from right
4. "What's wrong" tab shows issues with what/why/fix expandable cards
5. "Summary" shows health score number + counts
6. "What to do next" gives plain-English recommendation
7. ESC closes the drawer

- [ ] **Step 5: Commit**

```bash
cd circuit-ai-frontend && git add components/drawer/ && git commit -m "feat: node detail drawer with board and validation views"
```

---

## Task 12: Playwright visual verification

Verify the workspace looks right and the core demo flow works end-to-end.

**Prerequisite:** Dev server running on http://localhost:3000

- [ ] **Step 1: Open workspace and take a screenshot of empty state**

Using the available Playwright MCP tools, navigate to http://localhost:3000/workspace and take a screenshot. Verify:
- Dark navy background (#080e1a)
- Three starter tiles centered
- Command bar at top with "What do you want to build?" placeholder
- JARVIS bottom bar visible

If any of these are missing, fix before proceeding.

- [ ] **Step 2: Take a screenshot after dropping a file**

Simulate a file drop (or click a starter tile). Take a screenshot. Verify:
- File Node appears on canvas as a dark card
- JARVIS notification strip slides in below the command bar
- Bottom bar shows the JARVIS message

- [ ] **Step 3: Take a screenshot after parse + validate flow**

Click "Parse board" → then "Check issues". Take a screenshot. Verify:
- Three nodes connected on canvas: File → Board → Validation
- Validation node shows the health score and severity counts
- JARVIS narrated the result in the notification strip

- [ ] **Step 4: Take a screenshot of the open drawer**

Click the Validation Node's "See details →". Take a screenshot. Verify:
- Right-side drawer is visible (400px wide)
- Tabs are readable (What's wrong / Summary / What to do)
- Issues are listed with expandable cards
- Dark navy drawer background, clean typography

- [ ] **Step 5: Check mobile viewport**

Resize viewport to 375px width. Take a screenshot. Note any layout breaks — record them as follow-up items in the plan notes section below.

- [ ] **Step 6: Commit Playwright findings**

If any visual fixes were made during verification:
```bash
cd circuit-ai-frontend && git add -A && git commit -m "fix: visual corrections from Playwright verification"
```

---

## Plan Notes

**Follow-up for Plan 2:**
- Manufacturing Package Node + drawer (Gerber, BOM, PnP, DFM)
- Mecha Bundle Node + 3D preview drawer
- Recipe Node + learning path nodes
- Real file parsing (replace placeholder 47-component board data with actual backend response)
- Board extraction (`/api/proxy/extract`) wired to Structure tab in Board Drawer
- BOM generation wired to Parts tab in Board Drawer
- Mobile layout adjustments (noted during Playwright step 5)
- Zustand store sync to Circuit-AI projects API (`/api/v2/projects`) for users with API keys
- Project switcher in command bar
- Multi-board System Node (connect two Board Nodes → System Node inference)

**Environment variables needed for full backend wiring:**
```
CIRCUIT_AI_API_URL=http://localhost:5000
MECHA_API_URL=http://localhost:8085
```
