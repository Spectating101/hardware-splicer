'use client';

import { useState, type ReactNode } from 'react';
import Link from 'next/link';
import { Bot, CornerDownLeft, MessageSquareText, Sparkles } from 'lucide-react';
import { useStudioRuntime } from '@/components/studio-runtime';
import { cn } from '@/lib/utils';

type CopilotLink = {
  href: string;
  label: string;
};

type CopilotDockProps = {
  modeLabel: string;
  objective: string;
  status: string;
  messages: Array<{
    role: 'agent' | 'assistant' | 'user' | 'system';
    body: string;
  }>;
  prompts: string[];
  links?: CopilotLink[];
  footer?: ReactNode;
  onDispatch?: (draft: string) => void;
};

export function CopilotDock({
  modeLabel,
  objective,
  status,
  messages,
  prompts,
  links = [],
  footer,
  onDispatch,
}: CopilotDockProps) {
  const { state } = useStudioRuntime();
  const [draft, setDraft] = useState('');
  const [activeTab, setActiveTab] = useState<'chat' | 'context' | 'actions'>('chat');

  return (
    <div className="grid h-full grid-rows-[auto_auto_minmax(0,1fr)_auto] gap-3">
      <div className="circuit-card rounded-[1.3rem] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-200">{modeLabel}</div>
            <div className="mt-1 text-lg font-semibold tracking-tight text-white">Review channel</div>
          </div>
          <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-emerald-200">
            {status}
          </div>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-300">{objective}</p>
      </div>

      <div className="flex items-center gap-2 rounded-[1.1rem] border border-white/10 bg-[#050d19] p-1.5">
        {[
          ['chat', 'Chat'],
          ['context', 'Context'],
          ['actions', 'Actions'],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setActiveTab(value as 'chat' | 'context' | 'actions')}
            className={cn(
              'flex-1 rounded-[0.9rem] px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-colors',
              activeTab === value
                ? 'bg-cyan-300/14 text-cyan-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]'
                : 'text-slate-400 hover:bg-white/6 hover:text-white',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 overflow-y-auto rounded-[1.3rem] border border-white/10 bg-[linear-gradient(180deg,#081524,#050c17)] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]">
        {activeTab === 'chat' ? (
          <>
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <MessageSquareText className="h-4 w-4 text-cyan-300" />
              Conversation
            </div>
            <div className="space-y-3">
              {messages.map((message, index) => {
                const isAssistantMessage = message.role === 'agent' || message.role === 'assistant';

                return (
                  <div
                    key={`${message.role}-${index}`}
                    className={cn(
                      'rounded-[1.05rem] border px-3.5 py-3 text-sm leading-6 shadow-[0_16px_38px_rgba(2,6,23,0.18)]',
                      isAssistantMessage && 'border-cyan-300/16 bg-cyan-300/8 text-slate-100',
                      message.role === 'user' && 'border-white/10 bg-[#0b1628] text-slate-300',
                      message.role === 'system' && 'border-amber-300/16 bg-amber-300/9 text-amber-100',
                    )}
                  >
                    <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]">
                      {isAssistantMessage ? <Bot className="h-3.5 w-3.5 text-cyan-300" /> : null}
                      {message.role === 'user' ? <CornerDownLeft className="h-3.5 w-3.5 text-slate-400" /> : null}
                      {isAssistantMessage ? 'assistant' : message.role}
                    </div>
                    <div>{message.body}</div>
                  </div>
                );
              })}
            </div>
          </>
        ) : null}

        {activeTab === 'context' ? (
          <div className="grid gap-2">
            {[
              ['Board', state.artifactName || 'No artifact'],
              ['Inspect', state.analysisMode || 'Awaiting mode'],
              ['Parts', state.focusedComponent ? state.focusedComponent.replaceAll('_', ' ') : 'No focus'],
              ['Route', state.focusedProject || 'No path'],
            ].map(([label, value]) => (
              <div key={label} className="rounded-[1rem] border border-white/8 bg-[#081423] px-3.5 py-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
                <div className="mt-1 truncate text-sm font-semibold text-white">{value}</div>
              </div>
            ))}

            {links.length ? (
              <div className="grid gap-2 pt-2">
                {links.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="rounded-[1rem] border border-white/10 bg-[#0b1628] px-3.5 py-3 text-sm font-medium text-slate-300 transition-colors hover:border-cyan-300/20 hover:text-white"
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            ) : null}

            {footer}
          </div>
        ) : null}

        {activeTab === 'actions' ? (
          <div className="space-y-4">
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <Sparkles className="h-4 w-4 text-cyan-300" />
                Quick intents
              </div>
              <div className="flex flex-wrap gap-2">
                {prompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setDraft(prompt)}
                    className="rounded-full border border-white/10 bg-[#0b1628] px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-cyan-300/22 hover:bg-cyan-300/8 hover:text-cyan-100"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            {links.length ? (
              <div className="grid gap-2">
                {links.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="rounded-[1rem] border border-white/10 bg-[#0b1628] px-3.5 py-3 text-sm font-medium text-slate-300 transition-colors hover:border-cyan-300/20 hover:text-white"
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            ) : null}

            {footer}
          </div>
        ) : null}
      </div>

      <div className="rounded-[1.2rem] border border-white/10 bg-[#050d19] p-3">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={onDispatch ? 'Tell the assistant what to change in the current board…' : 'Prompt staging only. Wire an assistant endpoint to enable dispatch.'}
          className="min-h-[104px] w-full resize-none rounded-[1rem] border border-white/10 bg-[#030a14] px-3.5 py-3 text-sm text-slate-100 transition-colors placeholder:text-slate-500 focus:border-cyan-300/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/35"
        />
        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="text-xs text-slate-500">
            {onDispatch ? 'Dispatch sends the staged prompt to the configured assistant endpoint.' : 'No hidden fake execution: this dock explains context until an assistant endpoint is connected.'}
          </div>
          <button
            type="button"
            disabled={!onDispatch || !draft.trim()}
            onClick={() => onDispatch?.(draft)}
            className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-100 transition-colors hover:bg-cyan-300/18 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[0.03] disabled:text-slate-500"
          >
            {onDispatch ? 'Dispatch' : 'Connect endpoint'}
          </button>
        </div>
      </div>
    </div>
  );
}
