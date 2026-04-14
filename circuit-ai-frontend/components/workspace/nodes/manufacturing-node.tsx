"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Package, FileCode, FileText, ExternalLink, X, AlertCircle } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { ManufacturingNodeData, ManufacturingFile } from "@/lib/node-types";

function FileTypeIcon({ type }: { type: ManufacturingFile["type"] }) {
  if (type === "gerber" || type === "drill") return <FileCode size={11} className="text-purple-400" />;
  return <FileText size={11} className="text-purple-300/60" />;
}

export function ManufacturingNodeComponent({ id, data: rawData }: NodeProps) {
  const data = rawData as unknown as ManufacturingNodeData;
  const { openDrawer, removeNode } = useWorkspaceStore();

  const isProcessing = data.status === "processing";
  const isDone = data.status === "done";
  const isError = data.status === "error";

  const gerbers = data.files?.filter((f) => f.type === "gerber" || f.type === "drill") ?? [];
  const otherFiles = data.files?.filter((f) => f.type !== "gerber" && f.type !== "drill") ?? [];

  return (
    <div
      className={cn(
        "group w-[220px] rounded-2xl border bg-[#141e2e] p-3 flex flex-col gap-2 transition-all duration-500 relative",
        isProcessing
          ? "border-purple-500/60 shadow-[0_0_0_2px_rgba(168,85,247,0.2),0_4px_24px_rgba(0,0,0,0.5)] animate-pulse"
          : isDone
            ? "border-emerald-500/40 shadow-[0_0_20px_rgba(16,185,129,0.25),0_4px_24px_rgba(0,0,0,0.5)]"
            : isError
              ? "border-red-500/40 shadow-[0_4px_24px_rgba(0,0,0,0.5)]"
              : "border-white/10 shadow-[0_4px_24px_rgba(0,0,0,0.5)]"
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-purple-500 !border-purple-700" />
      <button
        onClick={() => removeNode(id)}
        className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-[#1e293b] border border-white/15 text-white/30 hover:text-white/80 hover:border-white/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
        title="Remove"
      >
        <X size={10} />
      </button>

      <div className="flex items-start gap-2">
        <Package size={16} className={cn("flex-shrink-0 mt-0.5", isDone ? "text-emerald-400" : isError ? "text-red-400" : "text-purple-400")} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-white/90 font-medium truncate">{data.packageName}</p>
          <p className="text-xs text-white/30 mt-0.5">Manufacturing Package</p>
        </div>
        {isDone && (
          <button
            onClick={() => openDrawer(id, "files")}
            className="text-white/30 hover:text-white/70 transition-colors"
          >
            <ExternalLink size={12} />
          </button>
        )}
      </div>

      {/* Status badges */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {isProcessing && <Badge variant="info">Generating…</Badge>}
        {isDone && (
          <>
            <Badge variant="success">Ready</Badge>
            {data.gerberCount != null && (
              <Badge variant="default">{data.gerberCount} Gerbers</Badge>
            )}
            {data.hasBom && <Badge variant="info">BOM</Badge>}
          </>
        )}
        {isError && <Badge variant="error">Failed</Badge>}
      </div>

      {/* File list when done */}
      {isDone && data.files && data.files.length > 0 && (
        <div className="flex flex-col gap-1 pt-1 border-t border-white/5">
          {gerbers.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-white/40">
              <FileCode size={11} className="text-purple-400" />
              <span>{gerbers.length} Gerber/drill files</span>
            </div>
          )}
          {otherFiles.map((f) => (
            <div key={f.name} className="flex items-center gap-1.5 text-xs text-white/40">
              <FileTypeIcon type={f.type} />
              <span className="truncate">{f.name}</span>
            </div>
          ))}
        </div>
      )}

      {/* Error message */}
      {isError && data.errorMessage && (
        <div className="flex items-start gap-1.5 pt-1 border-t border-white/5">
          <AlertCircle size={11} className="text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-red-300/70 leading-snug">{data.errorMessage}</p>
        </div>
      )}
    </div>
  );
}
