"use client";

import { useState, useRef, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronUp, ChevronDown, Zap, User } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";

/** Renders **bold** and `code` inline markdown */
function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**"))
          return <strong key={i} className="font-semibold text-cyan-200">{part.slice(2, -2)}</strong>;
        if (part.startsWith("`") && part.endsWith("`"))
          return <code key={i} className="font-mono text-cyan-300 bg-cyan-950/60 px-0.5 rounded text-[10px]">{part.slice(1, -1)}</code>;
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

function MessageBubble({ role, text, nodeId, onFocusNode }: {
  role: "user" | "jarvis";
  text: string;
  nodeId?: string;
  onFocusNode: (id: string) => void;
}) {
  // Split on line breaks for multiline JARVIS messages
  const lines = text.split(/\n/);

  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="flex items-start gap-1.5 max-w-[82%]">
          <div className="bg-white/10 border border-white/10 text-white/80 rounded-xl px-3 py-2 text-xs leading-relaxed">
            {text}
          </div>
          <User size={12} className="text-white/20 flex-shrink-0 mt-1.5" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-1.5 max-w-[82%]">
        <Zap size={12} className="text-cyan-400/60 flex-shrink-0 mt-1.5" />
        <div className="bg-cyan-950/50 border border-cyan-500/15 text-cyan-100/80 rounded-xl px-3 py-2 text-xs leading-relaxed">
          {lines.map((line, i) => (
            <p key={i} className={i > 0 ? "mt-1" : ""}>
              <InlineMarkdown text={line} />
            </p>
          ))}
          {nodeId && (
            <button
              onClick={() => onFocusNode(nodeId)}
              className="mt-1.5 block text-cyan-400 hover:text-cyan-200 transition-colors font-medium"
            >
              Show on canvas →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

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
        {lastMessage && !isOpen && (
          <span className="text-xs text-white/25 truncate ml-2">
            {lastMessage.text.replace(/\*\*(.*?)\*\*/g, "$1").slice(0, 90)}
          </span>
        )}
        {jarvisMessages.length > 0 && (
          <span className="ml-auto text-[10px] text-white/20 flex-shrink-0">
            {jarvisMessages.length} msg{jarvisMessages.length === 1 ? "" : "s"}
          </span>
        )}
      </button>

      {/* Expanded panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 300 }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div
              ref={listRef}
              className="h-[300px] overflow-y-auto px-4 py-3 flex flex-col gap-2.5"
            >
              {jarvisMessages.length === 0 ? (
                <p className="text-xs text-white/20 text-center mt-10">
                  No messages yet. Drop a file or type a prompt.
                </p>
              ) : (
                jarvisMessages.map((msg) => (
                  <MessageBubble
                    key={msg.id}
                    role={msg.role}
                    text={msg.text}
                    nodeId={msg.nodeId}
                    onFocusNode={handleFocusNode}
                  />
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
