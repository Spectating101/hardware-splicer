"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { CircuitBoard, KeyRound, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Overview" },
  { href: "/analyze", label: "Workbench" },
  { href: "/docs", label: "Docs" },
  { href: "/playground", label: "Playground" },
  { href: "/status", label: "Status" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#0f172a,#2563eb,#f97316)] text-white shadow-[0_14px_34px_rgba(37,99,235,0.28)]">
            <CircuitBoard className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">Circuit.AI</div>
            <div className="truncate text-sm text-slate-700">Vision, validation, minting, and fabrication workflows</div>
          </div>
        </Link>

        <nav className="ml-auto hidden items-center gap-2 lg:flex">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                isActive(pathname, item.href)
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 lg:flex">
          <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600">
            Workbench + Trust + Ops
          </div>
          <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
            <Link href="/dashboard/keys">
              <KeyRound className="mr-2 h-4 w-4" />
              API Keys
            </Link>
          </Button>
        </div>

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="ml-auto flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-700 lg:hidden"
          aria-label="Toggle navigation"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-slate-200 bg-white px-4 py-4 lg:hidden">
          <div className="mx-auto flex max-w-7xl flex-col gap-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "rounded-2xl px-4 py-3 text-sm font-medium transition-colors",
                  isActive(pathname, item.href)
                    ? "bg-slate-900 text-white"
                    : "bg-slate-50 text-slate-700 hover:bg-slate-100",
                )}
              >
                {item.label}
              </Link>
            ))}
            <Button asChild className="mt-2 rounded-2xl bg-slate-900 text-white hover:bg-slate-800">
              <Link href="/dashboard/keys" onClick={() => setOpen(false)}>
                <KeyRound className="mr-2 h-4 w-4" />
                API Keys
              </Link>
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}
