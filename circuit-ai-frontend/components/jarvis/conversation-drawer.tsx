"use client";

import { useState, useRef, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronUp, ChevronDown } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";

export function ConversationDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const { jarvisMessages, openDrawer, setFocusNodeId } = useWorkspaceStore();
  const listRef = useRef<HTMLDivElement>(null);
  const lastMessage = jarvisMessages[jarvisMessages.length - 1];

  useEffect(() => {
    if (isOpen && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [jarvisMessages, isOpen]);

  function handleFocusNode(nodeId: string) {
    // Pan canvas to the node, then open its drawer
    setFocusNodeId(nodeId);
    setTimeout(() => openDrawer(nodeId), 700);
  }

  return (
    <div className="flex-shrink-0 border-t border-white/5 bg-[#080e1a] z-10">
      {/* Collapsed bar */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="w-full h-8 flex items-center px-4 gap-2 hover:bg-white/5 transition-colors"
      >
        {isOpen ? (
          <ChevronDown size={14} className="text-white/40" />
        ) : (
          <ChevronUp size={14} className="text-white/40" />
        )}
        <span className="text-xs text-white/40 flex-shrink-0">History</span>
        {lastMessage && (
          <span className="text-xs text-white/30 truncate ml-2">
            {lastMessage.text.replace(/\*\*(.*?)\*\*/g, "$1").slice(0, 80)}
          </span>
        )}
      </button>

      {/* Expanded panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 280 }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div
              ref={listRef}
              className="h-[280px] overflow-y-auto px-4 py-3 flex flex-col gap-2"
            >
              {jarvisMessages.length === 0 ? (
                <p className="text-xs text-white/20 text-center mt-8">
                  No messages yet. Drop a file or type a prompt.
                </p>
              ) : (
                jarvisMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
                        msg.role === "user"
                          ? "bg-white/10 text-white/80"
                          : "bg-cyan-950/60 text-cyan-100/80 border border-cyan-500/20"
                      }`}
                    >
                      <p>
                        {msg.text
                          .replace(/\*\*(.*?)\*\*/g, "$1")
                          .replace(/`(.*?)`/g, "$1")}
                      </p>
                      {msg.role === "jarvis" && msg.nodeId && (
                        <button
                          onClick={() => handleFocusNode(msg.nodeId!)}
                          className="mt-1 text-cyan-400 hover:text-cyan-200 transition-colors"
                        >
                          Show →
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
