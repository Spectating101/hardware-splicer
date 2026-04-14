"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

export const Tabs = RadixTabs.Root;

export function TabsList({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <RadixTabs.List
      className={cn(
        "flex border-b border-white/10 bg-transparent",
        className
      )}
    >
      {children}
    </RadixTabs.List>
  );
}

export function TabsTrigger({
  value,
  children,
  className,
}: {
  value: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <RadixTabs.Trigger
      value={value}
      className={cn(
        "px-4 py-2 text-sm text-white/50 border-b-2 border-transparent",
        "data-[state=active]:text-white data-[state=active]:border-cyan-500",
        "hover:text-white/80 transition-colors cursor-pointer",
        className
      )}
    >
      {children}
    </RadixTabs.Trigger>
  );
}

export function TabsContent({
  value,
  children,
  className,
}: {
  value: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <RadixTabs.Content
      value={value}
      className={cn("flex-1 overflow-y-auto", className)}
    >
      {children}
    </RadixTabs.Content>
  );
}
