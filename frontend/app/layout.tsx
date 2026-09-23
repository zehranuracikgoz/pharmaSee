import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "PharmaSee — Pharma & Biotech Intelligence",
  description:
    "FDA onay verileri ve biyoteknoloji hisse performansını takip edin.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr">
      <head />
      <body className="min-h-screen bg-slate-50 text-slate-700 font-sans">
        <Navbar />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">{children}</main>
      </body>
      
    </html>
  );
}
