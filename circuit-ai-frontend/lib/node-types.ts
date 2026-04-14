export type NodeKind = "file" | "board" | "validation" | "manufacturing";
export type NodeStatus = "idle" | "processing" | "done" | "error";
export type IssueSeverity = "critical" | "error" | "warning";

export interface ValidationIssue {
  id: string;
  severity: IssueSeverity;
  what: string;
  why: string;
  fix: string;
  acknowledged?: boolean;
}

export interface FileNodeData {
  kind: "file";
  status: NodeStatus;
  filename: string;
  fileKind: string;
  sizeBytes: number;
  rawFile?: File;
}

export interface BoardNodeData {
  kind: "board";
  status: NodeStatus;
  boardName: string;
  componentCount: number;
  layerCount: number;
  sourceFileNodeId: string;
}

export interface ValidationNodeData {
  kind: "validation";
  status: NodeStatus;
  healthScore: number;
  issues: ValidationIssue[];
  sourceBoardNodeId: string;
}

export interface ManufacturingNodeData {
  kind: "manufacturing";
  status: NodeStatus;
  packageName: string;
}

export type WorkspaceNodeData =
  | FileNodeData
  | BoardNodeData
  | ValidationNodeData
  | ManufacturingNodeData;

export interface WorkspaceNode {
  id: string;
  kind: NodeKind;
  position: { x: number; y: number };
  data: WorkspaceNodeData;
}

export interface WorkspaceEdge {
  id: string;
  source: string;
  target: string;
}

export interface JarvisMessage {
  id: string;
  role: "user" | "jarvis";
  text: string;
  nodeId?: string;
  timestamp: number;
}
