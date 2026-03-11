import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { StudioRuntimeProvider } from "@/components/studio-runtime";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Circuit.AI",
  description: "Enterprise-grade AI API for PCB component detection, analysis, and insights. Built for developers, integrated by teams.",
  keywords: ["API", "PCB", "electronics", "AI", "component detection", "circuit analysis", "developer tools"],
  authors: [{ name: "Circuit.AI Team" }],
  openGraph: {
    title: "Circuit.AI - PCB Analysis API Platform",
    description: "Enterprise-grade AI API for PCB component detection and analysis.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen bg-background text-foreground antialiased`}>
        <StudioRuntimeProvider>{children}</StudioRuntimeProvider>
      </body>
    </html>
  );
}
