import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/navbar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Circuit.AI - Enterprise PCB Analysis API Platform",
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
      <body className={inter.className}>
        <div className="min-h-screen bg-slate-50">
          {children}
        </div>
      </body>
    </html>
  );
}
