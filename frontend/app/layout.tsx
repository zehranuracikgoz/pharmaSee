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
    <html lang="tr" className="dark">
      <head />
      <body className="min-h-screen bg-[#0f1117] text-gray-100">
        <Navbar />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">{children}</main>
      </body>
      
    </html>
  );
}
