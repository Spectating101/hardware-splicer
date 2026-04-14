"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";
import type { BoardNodeData, ValidationNodeData } from "@/lib/node-types";
import { BoardDrawer } from "./board-drawer";
import { ValidationDrawer } from "./validation-drawer";

const kindLabel: Record<string, string> = {
  file: "File",
  board: "PCB Board",
  validation: "Validation",
  manufacturing: "Manufacturing",
};

export function NodeDrawer() {
  const { drawer, closeDrawer, nodes } = useWorkspaceStore();

  const node = drawer ? nodes.find((n) => n.id === drawer.nodeId) : null;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeDrawer();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeDrawer]);

  return (
    <AnimatePresence>
      {drawer && node && (
        <motion.aside
          key={drawer.nodeId}
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", stiffness: 320, damping: 32 }}
          className="absolute right-0 top-0 h-full w-[400px] bg-[#0f172a] border-l border-white/10 flex flex-col z-20 overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 flex-shrink-0">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-white/40 uppercase tracking-wide">
                {kindLabel[node.kind] ?? node.kind}
              </p>
              <p className="text-sm text-white font-medium truncate mt-0.5">
                {node.kind === "board"
                  ? (node.data as BoardNodeData).boardName
                  : node.kind === "file"
                    ? (node.data as import("@/lib/node-types").FileNodeData).filename
                    : node.id}
              </p>
            </div>
            <button
              onClick={closeDrawer}
              className="text-white/30 hover:text-white/70 transition-colors flex-shrink-0"
              aria-label="Close drawer"
            >
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-hidden flex flex-col">
            {node.kind === "board" && (
              <BoardDrawer
                nodeId={node.id}
                data={node.data as BoardNodeData}
                defaultTab={drawer.tab}
              />
            )}
            {node.kind === "validation" && (
              <ValidationDrawer
                data={node.data as ValidationNodeData}
                defaultTab={drawer.tab}
              />
            )}
            {node.kind === "file" && (
              <div className="flex-1 flex items-center justify-center p-6">
                <div className="text-center">
                  <p className="text-white/40 text-sm">File details</p>
                  <p className="text-white/25 text-xs mt-1">
                    Parse the board to see more information.
                  </p>
                </div>
              </div>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
