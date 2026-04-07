'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Activity, Check, Copy, Eye, EyeOff, KeyRound, PlayCircle, ShieldCheck, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { PageIntro } from '@/components/page-intro';
import { BackendHealthCard } from '@/components/backend-health-card';
import { usePageTitle } from '@/components/use-page-title';

type ApiKeyRecord = {
  id: string;
  name: string;
  key: string;
  createdAt: string;
  lastUsed?: string;
  usageCount: number;
  isActive: boolean;
};

const storageKey = "circuit-ai-demo-keys";

function seedKeys(): ApiKeyRecord[] {
  return [
    {
      id: "key_dev",
      name: "Development key",
      key: "ckt_live_1234567890abcdef",
      createdAt: "2026-03-01T10:30:00Z",
      lastUsed: "2026-03-08T14:22:00Z",
      usageCount: 128,
      isActive: true,
    },
    {
      id: "key_ops",
      name: "Operator key",
      key: "ckt_live_fedcba0987654321",
      createdAt: "2026-02-24T09:15:00Z",
      lastUsed: "2026-03-09T08:45:00Z",
      usageCount: 412,
      isActive: true,
    },
  ];
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function maskKey(value: string) {
  return `${value.slice(0, 8)}••••••••••••${value.slice(-4)}`;
}

export default function APIKeysPage() {
  usePageTitle('API Keys | Circuit.AI');
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const raw = window.localStorage.getItem(storageKey);
    setKeys(raw ? JSON.parse(raw) : seedKeys());
  }, []);

  useEffect(() => {
    if (keys.length) {
      window.localStorage.setItem(storageKey, JSON.stringify(keys));
    }
  }, [keys]);

  const activeKeyCount = useMemo(() => keys.filter((key) => key.isActive).length, [keys]);

  const createKey = () => {
    if (!newKeyName.trim()) return;
    const next: ApiKeyRecord = {
      id: `key_${Date.now()}`,
      name: newKeyName.trim(),
      key: `ckt_live_${Math.random().toString(36).slice(2, 18)}`,
      createdAt: new Date().toISOString(),
      usageCount: 0,
      isActive: true,
    };
    setKeys((prev) => [next, ...prev]);
    setNewKeyName("");
  };

  const revokeKey = (id: string) => {
    setKeys((prev) => prev.map((item) => (item.id === id ? { ...item, isActive: false } : item)));
  };

  const copyKey = async (key: string, id: string) => {
    await navigator.clipboard.writeText(key);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  const toggleVisibility = (id: string) => {
    setVisibleKeys((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="API key workspace"
          title="Credential management should feel like part of the product, not an afterthought."
          description="Keys are where the frontend starts becoming operational. This page should make it easy to issue, inspect, revoke, and immediately use credentials in the rest of the stack."
          actions={
            <>
              <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                <Link href="/playground">
                  <PlayCircle className="mr-2 h-4 w-4" />
                  Use in playground
                </Link>
              </Button>
              <Button asChild variant="outline" className="rounded-full border-slate-300 bg-white/80">
                <Link href="/status">
                  <ShieldCheck className="mr-2 h-4 w-4" />
                  Check backend status
                </Link>
              </Button>
            </>
          }
          aside={<BackendHealthCard />}
        />

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="space-y-6">
              <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_22px_50px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle className="text-2xl text-slate-950">Create a new key</CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-600">
                    Use clear names so the rest of the system can preserve context between environments and operator flows.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Input
                    value={newKeyName}
                    onChange={(event) => setNewKeyName(event.target.value)}
                    placeholder="Example: playground, operator-demo, production-ingest…"
                    className="rounded-2xl border-slate-200 bg-white"
                  />
                  <Button onClick={createKey} className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                    <KeyRound className="mr-2 h-4 w-4" />
                    Create key
                  </Button>
                </CardContent>
              </Card>

              <div className="grid gap-4 sm:grid-cols-2">
                <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Active keys</CardDescription>
                    <CardTitle className="text-4xl text-slate-950">{activeKeyCount}</CardTitle>
                  </CardHeader>
                </Card>
                <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
                  <CardHeader className="pb-2">
                    <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Total recorded usage</CardDescription>
                    <CardTitle className="text-4xl text-slate-950">{keys.reduce((sum, item) => sum + item.usageCount, 0)}</CardTitle>
                  </CardHeader>
                </Card>
              </div>
            </div>

            <div className="space-y-4">
              {keys.map((apiKey) => (
                <Card key={apiKey.id} className={`rounded-[1.75rem] border-slate-200/80 bg-white/90 shadow-[0_20px_45px_rgba(15,23,42,0.05)] ${apiKey.isActive ? "" : "opacity-65"}`}>
                  <CardHeader>
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <CardTitle className="text-xl text-slate-950">{apiKey.name}</CardTitle>
                        <CardDescription className="mt-2 text-sm text-slate-500">
                          Created {formatDate(apiKey.createdAt)}
                        </CardDescription>
                      </div>
                      <div className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                        apiKey.isActive ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
                      }`}>
                        {apiKey.isActive ? "Active" : "Revoked"}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Key</div>
                      <div className="flex items-center gap-2">
                        <Input
                          readOnly
                          value={visibleKeys[apiKey.id] ? apiKey.key : maskKey(apiKey.key)}
                          className="rounded-2xl border-slate-200 bg-white font-mono text-sm"
                        />
                        <Button aria-label={visibleKeys[apiKey.id] ? "Hide API key" : "Show API key"} variant="outline" size="sm" onClick={() => toggleVisibility(apiKey.id)}>
                          {visibleKeys[apiKey.id] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                        <Button aria-label="Copy API key" variant="outline" size="sm" onClick={() => copyKey(apiKey.key, apiKey.id)}>
                          {copiedKey === apiKey.id ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-[1.25rem] bg-slate-50 p-4">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Usage</div>
                        <div className="mt-2 text-2xl font-semibold text-slate-950">{apiKey.usageCount}</div>
                      </div>
                      <div className="rounded-[1.25rem] bg-slate-50 p-4">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Last used</div>
                        <div className="mt-2 text-sm text-slate-700">{apiKey.lastUsed ? formatDate(apiKey.lastUsed) : "Never"}</div>
                      </div>
                      <div className="rounded-[1.25rem] bg-slate-50 p-4">
                        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">State</div>
                        <div className="mt-2 flex items-center gap-2 text-sm font-medium text-slate-900">
                          <Activity className="h-4 w-4" />
                          {apiKey.isActive ? "Operational" : "Revoked"}
                        </div>
                      </div>
                    </div>

                    {apiKey.isActive ? (
                      <div className="flex flex-wrap gap-3">
                        <Button asChild variant="outline" className="rounded-full">
                          <Link href="/playground">Use in playground</Link>
                        </Button>
                        <Button variant="outline" className="rounded-full text-rose-700 hover:bg-rose-50" onClick={() => revokeKey(apiKey.id)}>
                          <Trash2 className="mr-2 h-4 w-4" />
                          Revoke
                        </Button>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
