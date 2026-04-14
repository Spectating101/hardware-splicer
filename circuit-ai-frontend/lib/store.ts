import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  WorkspaceNode,
  WorkspaceEdge,
  WorkspaceNodeData,
  JarvisMessage,
  FileNodeData,
  ValidationNodeData,
} from "./node-types";

let _nodeCounter = 0;
let _edgeCounter = 0;

export function newNodeId(kind: string): string {
  return `${kind}-${++_nodeCounter}`;
}

export function newEdgeId(source: string, target: string): string {
  return `edge-${source}-${target}-${++_edgeCounter}`;
}

export interface JarvisStrip {
  message: string;
  nodeId?: string;
  action?: { label: string; onAction: () => void };
}

export interface DrawerState {
  nodeId: string;
  tab: string;
}

interface HistorySnapshot {
  nodes: WorkspaceNode[];
  edges: WorkspaceEdge[];
}

interface WorkspaceState {
  nodes: WorkspaceNode[];
  edges: WorkspaceEdge[];
  jarvisMessages: JarvisMessage[];
  jarvisStrip: JarvisStrip | null;
  isJarvisThinking: boolean;
  drawer: DrawerState | null;
  history: HistorySnapshot[];
  canUndo: boolean;
  focusNodeId: string | null;

  // Node actions
  addNode: (node: WorkspaceNode) => void;
  updateNode: (id: string, patch: Partial<WorkspaceNodeData>) => void;
  updateNodePosition: (id: string, position: { x: number; y: number }) => void;
  addEdge: (edge: WorkspaceEdge) => void;

  // JARVIS actions
  addJarvisMessage: (message: Omit<JarvisMessage, "id" | "timestamp">) => void;
  showJarvisStrip: (strip: JarvisStrip) => void;
  dismissJarvisStrip: () => void;
  setJarvisThinking: (thinking: boolean) => void;

  // Drawer actions
  openDrawer: (nodeId: string, tab?: string) => void;
  closeDrawer: () => void;
  setDrawerTab: (tab: string) => void;

  // Workspace mutations
  removeNode: (nodeId: string) => void;
  acknowledgeIssue: (nodeId: string, issueId: string) => void;

  // History
  undo: () => void;

  // Camera
  setFocusNodeId: (id: string | null) => void;

  // Project actions
  clearProject: () => void;
}

let _msgCounter = 0;

function bumpCountersFromNodes(nodes: WorkspaceNode[]) {
  nodes.forEach((n) => {
    const m = n.id.match(/-(\d+)$/);
    if (m) _nodeCounter = Math.max(_nodeCounter, parseInt(m[1], 10));
  });
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      nodes: [],
      edges: [],
      jarvisMessages: [],
      jarvisStrip: null,
      isJarvisThinking: false,
      drawer: null,
      history: [],
      canUndo: false,
      focusNodeId: null,

      addNode: (node) =>
        set((state) => ({
          history: [...state.history, { nodes: state.nodes, edges: state.edges }].slice(-20),
          canUndo: true,
          nodes: [...state.nodes, node],
        })),

      updateNode: (id, patch) =>
        set((state) => ({
          nodes: state.nodes.map((n) =>
            n.id === id ? { ...n, data: { ...n.data, ...patch } as WorkspaceNodeData } : n
          ),
        })),

      updateNodePosition: (id, position) =>
        set((state) => ({
          nodes: state.nodes.map((n) => (n.id === id ? { ...n, position } : n)),
        })),

      addEdge: (edge) =>
        set((state) => ({ edges: [...state.edges, edge] })),

      addJarvisMessage: (message) =>
        set((state) => ({
          jarvisMessages: [
            ...state.jarvisMessages,
            { ...message, id: `msg-${++_msgCounter}`, timestamp: Date.now() },
          ],
        })),

      showJarvisStrip: (strip) => set({ jarvisStrip: strip }),
      dismissJarvisStrip: () => set({ jarvisStrip: null }),
      setJarvisThinking: (thinking) => set({ isJarvisThinking: thinking }),

      openDrawer: (nodeId, tab = "overview") =>
        set({ drawer: { nodeId, tab } }),

      closeDrawer: () => set({ drawer: null }),

      setDrawerTab: (tab) =>
        set((state) =>
          state.drawer ? { drawer: { ...state.drawer, tab } } : {}
        ),

      removeNode: (nodeId) =>
        set((state) => ({
          history: [...state.history, { nodes: state.nodes, edges: state.edges }].slice(-20),
          canUndo: true,
          nodes: state.nodes.filter((n) => n.id !== nodeId),
          edges: state.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
          drawer: state.drawer?.nodeId === nodeId ? null : state.drawer,
        })),

      acknowledgeIssue: (nodeId, issueId) =>
        set((state) => ({
          nodes: state.nodes.map((n) => {
            if (n.id !== nodeId || n.kind !== "validation") return n;
            const data = n.data as ValidationNodeData;
            return {
              ...n,
              data: {
                ...data,
                issues: data.issues.map((issue) =>
                  issue.id === issueId ? { ...issue, acknowledged: true } : issue
                ),
              },
            };
          }),
        })),

      undo: () =>
        set((state) => {
          if (state.history.length === 0) return {};
          const prev = state.history[state.history.length - 1];
          const newHistory = state.history.slice(0, -1);
          return {
            nodes: prev.nodes,
            edges: prev.edges,
            history: newHistory,
            canUndo: newHistory.length > 0,
            drawer: null,
          };
        }),

      setFocusNodeId: (id) => set({ focusNodeId: id }),

      clearProject: () =>
        set({
          nodes: [],
          edges: [],
          jarvisMessages: [],
          jarvisStrip: null,
          drawer: null,
          history: [],
          canUndo: false,
        }),
    }),
    {
      name: "circuit-ai-workspace-v1",
      // Only persist the durable parts; strip File objects (not serializable)
      partialize: (state) => ({
        nodes: state.nodes.map((n) => {
          if (n.kind !== "file") return n;
          // rawFile is a browser File object — can't be serialized
          const { rawFile: _rawFile, ...fileData } = n.data as FileNodeData;
          return { ...n, data: fileData };
        }),
        edges: state.edges,
        jarvisMessages: state.jarvisMessages,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.nodes) bumpCountersFromNodes(state.nodes);
        if (state?.jarvisMessages) {
          _msgCounter = state.jarvisMessages.reduce((max, m) => {
            const match = m.id.match(/-(\d+)$/);
            return match ? Math.max(max, parseInt(match[1], 10)) : max;
          }, 0);
        }
      },
    }
  )
);
