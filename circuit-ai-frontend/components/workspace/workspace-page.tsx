"use client";

import { CommandBar } from "@/components/jarvis/command-bar";
import { NotificationStrip } from "@/components/jarvis/notification-strip";
import { ConversationDrawer } from "@/components/jarvis/conversation-drawer";
import { WorkspaceCanvas } from "./canvas";
import { NodeDrawer } from "@/components/drawer/node-drawer";
import { useWorkspaceStore } from "@/lib/store";

export default function WorkspacePage() {
  const { drawer } = useWorkspaceStore();

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
