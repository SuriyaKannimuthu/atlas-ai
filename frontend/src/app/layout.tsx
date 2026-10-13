import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Suspense } from "react";

import { UserCard } from "@/components/shell";
import { Sidebar } from "@/components/sidebar";
import { Skeleton } from "@/components/ui";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-mono-face", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Atlas AI", template: "%s · Atlas AI" },
  description:
    "Multi-agent incident investigation with evidence-based root-cause analysis and human-approved remediation.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} antialiased`}>
      <body className="min-h-screen">
        <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col lg:flex-row">
          <Sidebar
            userCard={
              <Suspense fallback={<Skeleton className="h-[60px]" />}>
                <UserCard />
              </Suspense>
            }
          />
          <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
