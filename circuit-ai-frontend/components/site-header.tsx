"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Boxes, Camera, CircuitBoard, Menu, Wrench, X, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const primaryNav = [
  { href: "/scan", label: "Scan", icon: Camera },
  { href: "/build", label: "Build", icon: Wrench },
  { href: "/parts", label: "Parts", icon: Boxes },
];

const secondaryNav = [
  { href: "/cad", label: "Advanced" },
  { href: "/docs", label: "Docs" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-[#0a0f1a]/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#0f172a,#2563eb,#f97316)] text-white shadow-[0_10px_30px_rgba(37,99,235,0.24)]">
            <CircuitBoard className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold tracking-tight text-white">Circuit.AI</div>
            <div className="hidden truncate text-[11px] text-slate-400 md:block">Build electronics from anything</div>
          </div>
        </Link>

        <nav className="ml-auto hidden items-center gap-1 lg:flex">
          {primaryNav.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-white text-slate-900"
                    : "text-slate-300 hover:bg-white/5 hover:text-white",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
          <div className="mx-2 h-5 w-px bg-white/10" />
          {secondaryNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded-full px-3 py-1.5 text-sm transition-colors",
                isActive(pathname, item.href)
                  ? "text-white"
                  : "text-slate-400 hover:text-white",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 lg:flex">
          <Button asChild size="sm" className="rounded-full bg-white text-slate-900 hover:bg-slate-100">
            <Link href="/scan">
              <Zap className="mr-1.5 h-3.5 w-3.5" />
              Start
            </Link>
          </Button>
        </div>

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="ml-auto flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-200 lg:hidden"
          aria-label="Toggle navigation"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-white/5 bg-[#0a0f1a] px-4 py-4 lg:hidden">
          <div className="mx-auto flex max-w-7xl flex-col gap-2">
            {primaryNav.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium transition-colors",
                    isActive(pathname, item.href)
                      ? "bg-white text-slate-900"
                      : "bg-white/5 text-slate-200 hover:bg-white/10",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
            <div className="mt-2 h-px bg-white/10" />
            {secondaryNav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-2xl px-4 py-2.5 text-sm text-slate-400 hover:bg-white/5 hover:text-white"
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </header>
  );
}
