import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/navbar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Circuit.AI - Transform E-Waste into Educational Opportunities",
  description: "AI-powered PCB analysis platform for transforming e-waste into educational opportunities. Detect components, analyze capabilities, and get project recommendations.",
  keywords: ["AI", "PCB", "electronics", "education", "e-waste", "component analysis", "circuit board"],
  authors: [{ name: "Circuit.AI Team" }],
  openGraph: {
    title: "Circuit.AI - AI-Powered PCB Analysis",
    description: "Transform e-waste into educational opportunities with AI-powered component detection and analysis.",
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
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
          <Navbar />
          <main className="container mx-auto px-4 py-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
