import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ProjectStudioLauncher } from "@/components/project-studio-launcher";
import { StudioRuntimeProvider } from "@/components/studio-runtime";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Hardware Splicer",
  description: "Evidence-governed AI engineering for reviewable hardware design, validation, repair, and controlled physical bring-up.",
  keywords: ["hardware engineering", "PCB", "robotics", "validation", "AI", "evidence", "engineering workflow"],
  authors: [{ name: "Hardware Splicer" }],
  openGraph: {
    title: "Hardware Splicer Project Studio",
    description: "Turn project intent and evidence into reviewable candidates, deterministic checks, and controlled engineering handoffs.",
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
        <StudioRuntimeProvider>
          {children}
          <ProjectStudioLauncher />
        </StudioRuntimeProvider>
      </body>
    </html>
  );
}
