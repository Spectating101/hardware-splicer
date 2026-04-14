"use client";

import { useEffect } from "react";
import { CommandBar } from "@/components/jarvis/command-bar";
import { NotificationStrip } from "@/components/jarvis/notification-strip";
import { ConversationDrawer } from "@/components/jarvis/conversation-drawer";
import { WorkspaceCanvas } from "./canvas";
import { NodeDrawer } from "@/components/drawer/node-drawer";
import { useWorkspaceStore } from "@/lib/store";
import { jarvis } from "@/lib/jarvis";
import type { BoardNodeData, ValidationNodeData, ManufacturingNodeData } from "@/lib/node-types";

export default function WorkspacePage() {
  const { drawer, nodes, edges, jarvisMessages, addJarvisMessage, showJarvisStrip } = useWorkspaceStore();

  // JARVIS greeting — fresh start or resumption summary
  useEffect(() => {
    if (nodes.length === 0 && jarvisMessages.length === 0) {
      // Completely fresh workspace
      const msg = "JARVIS online. Drop a `.kicad_pcb` file to begin — I'll parse the board, run electrical rules checks, and guide you through to manufacture.";
      addJarvisMessage({ role: "jarvis", text: msg });
      showJarvisStrip({ message: msg });
      return;
    }

    if (nodes.length > 0 && jarvisMessages.length > 0) {
      // Returning to an existing session — summarize current state
      const boardNode = nodes.find((n) => n.kind === "board");
      if (!boardNode) return;
      const bd = boardNode.data as BoardNodeData;
      const valEdge = edges.find((e) => e.source === boardNode.id);
      const valNode = valEdge ? nodes.find((n) => n.id === valEdge.target && n.kind === "validation") : null;
      const valData = valNode?.data as ValidationNodeData | undefined;
      const hasMfg = nodes.some(
        (n) => n.kind === "manufacturing" && (n.data as ManufacturingNodeData).status === "done"
      );
      const activeIssues = valData ? valData.issues.filter((i) => !i.acknowledged) : undefined;
      const criticals = activeIssues ? activeIssues.filter((i) => i.severity === "critical").length : undefined;

      const msg = jarvis.resumeProject(
        bd.boardName,
        valData?.healthScore,
        activeIssues?.length,
        criticals,
        hasMfg
      );
      addJarvisMessage({ role: "jarvis", text: msg });
      showJarvisStrip({ message: msg });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col h-screen bg-[#080e1a] overflow-hidden">
      {/* Top bar */}
      <CommandBar />

      {/* JARVIS notification strip */}
      <NotificationStrip />

      {/* Main content: canvas + optional right drawer */}
      <div className="flex-1 flex overflow-hidden relative">
        <WorkspaceCanvas />
        <NodeDrawer />
      </div>

      {/* Bottom conversation history */}
      <ConversationDrawer />
    </div>
  );
}
