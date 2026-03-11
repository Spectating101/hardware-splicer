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
    role: 'agent' | 'user' | 'system';
    body: string;
  }>;
  prompts: string[];
  links?: CopilotLink[];
  footer?: ReactNode;
};

export function CopilotDock({
  modeLabel,
  objective,
  status,
  messages,
  prompts,
  links = [],
  footer,
}: CopilotDockProps) {
  const { state } = useStudioRuntime();
  const [draft, setDraft] = useState('');
  const [activeTab, setActiveTab] = useState<'chat' | 'context' | 'actions'>('chat');

  return (
    <div className="grid h-full grid-rows-[auto_auto_minmax(0,1fr)_auto] gap-3">
      <div className="rounded-[1.2rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-200">{modeLabel}</div>
            <div className="mt-1 text-base font-semibold text-white">Agent dock</div>
          </div>
          <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-200">
            {status}
          </div>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-300">{objective}</p>
      </div>

      <div className="flex items-center gap-2 rounded-[1rem] border border-white/10 bg-[#08111f] p-2">
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
              'rounded-full px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-colors',
              activeTab === value
                ? 'bg-cyan-300/14 text-cyan-100'
                : 'text-slate-400 hover:bg-white/6 hover:text-white',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 overflow-y-auto rounded-[1.25rem] border border-white/10 bg-[linear-gradient(180deg,#091423,#07101c)] p-3">
        {activeTab === 'chat' ? (
          <>
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <MessageSquareText className="h-4 w-4 text-cyan-300" />
              Conversation
            </div>
            <div className="space-y-3">
              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={cn(
                    'rounded-[1rem] border px-3 py-3 text-sm leading-6',
                    message.role === 'agent' && 'border-cyan-300/14 bg-cyan-300/8 text-slate-100',
                    message.role === 'user' && 'border-white/10 bg-[#0b1628] text-slate-300',
                    message.role === 'system' && 'border-amber-300/14 bg-amber-300/8 text-amber-100',
                  )}
                >
                  <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]">
                    {message.role === 'agent' ? <Bot className="h-3.5 w-3.5 text-cyan-300" /> : null}
                    {message.role === 'user' ? <CornerDownLeft className="h-3.5 w-3.5 text-slate-400" /> : null}
                    {message.role}
                  </div>
                  <div>{message.body}</div>
                </div>
              ))}
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
              <div key={label} className="rounded-[1rem] border border-white/8 bg-[#081423] px-3 py-2.5">
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
                    className="rounded-[0.95rem] border border-white/10 bg-[#0b1628] px-3 py-3 text-sm text-slate-300 transition-colors hover:border-white/18 hover:text-white"
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
                    className="rounded-full border border-white/10 bg-[#0b1628] px-3 py-2 text-xs font-medium text-slate-300 transition-colors hover:border-white/18 hover:text-white"
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
                    className="rounded-[0.95rem] border border-white/10 bg-[#0b1628] px-3 py-3 text-sm text-slate-300 transition-colors hover:border-white/18 hover:text-white"
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

      <div className="rounded-[1.1rem] border border-white/10 bg-[#08111f] p-3">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Tell the agent what to change in the current board..."
          className="min-h-[96px] w-full resize-none rounded-[1rem] border border-white/10 bg-[#06101d] px-3 py-3 text-sm text-slate-100 outline-none transition-colors placeholder:text-slate-500 focus:border-cyan-300/30"
        />
        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="text-xs text-slate-500">Agent output should reshape the canvas first. Manual tools are fallback.</div>
          <button type="button" className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-100 transition-colors hover:bg-cyan-300/18">
            Dispatch
          </button>
        </div>
      </div>
    </div>
  );
}
