import { create } from "zustand";
import type {
  WorkspaceNode,
  WorkspaceEdge,
  WorkspaceNodeData,
  JarvisMessage,
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

interface WorkspaceState {
  nodes: WorkspaceNode[];
  edges: WorkspaceEdge[];
  jarvisMessages: JarvisMessage[];
  jarvisStrip: JarvisStrip | null;
  isJarvisThinking: boolean;
  drawer: DrawerState | null;

  // Node actions
  addNode: (node: WorkspaceNode) => void;
  updateNode: (id: string, patch: Partial<WorkspaceNodeData>) => void;
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

  // Project actions
  clearProject: () => void;
}

let _msgCounter = 0;

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  nodes: [],
  edges: [],
  jarvisMessages: [],
  jarvisStrip: null,
  isJarvisThinking: false,
  drawer: null,

  addNode: (node) =>
    set((state) => ({ nodes: [...state.nodes, node] })),

  updateNode: (id, patch) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...patch } as WorkspaceNodeData } : n
      ),
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
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      drawer: state.drawer?.nodeId === nodeId ? null : state.drawer,
    })),

  acknowledgeIssue: (nodeId, issueId) =>
    set((state) => ({
      nodes: state.nodes.map((n) => {
        if (n.id !== nodeId || n.kind !== "validation") return n;
        const data = n.data as import("./node-types").ValidationNodeData;
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

  clearProject: () =>
    set({
      nodes: [],
      edges: [],
      jarvisMessages: [],
      jarvisStrip: null,
      drawer: null,
    }),
}));
