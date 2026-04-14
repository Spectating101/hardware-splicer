"use client";

import { useEffect } from "react";
import { CommandBar } from "@/components/jarvis/command-bar";
import { NotificationStrip } from "@/components/jarvis/notification-strip";
import { ConversationDrawer } from "@/components/jarvis/conversation-drawer";
import { WorkspaceCanvas } from "./canvas";
import { NodeDrawer } from "@/components/drawer/node-drawer";
import { useWorkspaceStore } from "@/lib/store";

export default function WorkspacePage() {
  const { drawer, nodes, jarvisMessages, addJarvisMessage, showJarvisStrip } = useWorkspaceStore();

  // JARVIS greeting — fires once if the workspace is completely fresh
  useEffect(() => {
    if (nodes.length === 0 && jarvisMessages.length === 0) {
      const msg = "JARVIS online. Drop a `.kicad_pcb` file to begin — I'll parse the board, run electrical rules checks, and guide you through to manufacture.";
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
