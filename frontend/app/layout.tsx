import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import ServerWakeBanner from "@/components/ServerWakeBanner";

export const metadata: Metadata = {
  title: "PharmaSee — Pharma & Biotech Intelligence",
  description:
    "Track FDA drug approvals and biotech stock performance.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head />
      <body className="min-h-screen flex flex-col bg-bg text-text font-sans">
        <ServerWakeBanner />
        <Navbar />
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 py-6">{children}</main>
        <footer className="border-t border-border">
          <p className="max-w-7xl mx-auto px-4 sm:px-6 py-5 text-center text-xs text-muted">
            PharmaSee is for informational purposes only and does not constitute investment advice.
          </p>
        </footer>
      </body>
      
    </html>
  );
}
