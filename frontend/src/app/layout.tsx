import type { Metadata } from "next";
import Link from 'next/link';
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CJ Replica",
  description: "Viral Social Content RAG Chatbot Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[#09111E] relative overflow-x-hidden text-zinc-100">
        {/* Ambient background glows & noise */}
        <div className="absolute inset-0 bg-noise pointer-events-none mix-blend-overlay opacity-50 z-0" />
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-cyan-600/5 blur-[120px] mix-blend-screen pointer-events-none animate-blob z-0" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-sky-600/5 blur-[120px] mix-blend-screen pointer-events-none animate-blob delay-200 z-0" />
        
        <nav className="border-b border-white/5 bg-[#09111E]/80 backdrop-blur-xl sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-20">
              <div className="flex items-center w-full justify-between md:justify-start">
                <div className="flex-shrink-0 flex items-center gap-2">
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-[#00B2FF] stroke-current stroke-[3]"><path d="M21 12C21 16.9706 16.9706 21 12 21C9.69494 21 7.59227 20.1334 6 18.7083L3 21L5.29168 18C3.86656 16.4077 3 14.3051 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z"/></svg>
                  <span className="text-white font-black text-2xl tracking-wide">CJ<span className="text-[#00B2FF]">.COM</span></span>
                </div>
                <div className="hidden md:block">
                  <div className="ml-10 flex items-baseline space-x-4">
                    <Link href="/" className="text-zinc-300 hover:bg-zinc-800 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors">A/B Testing</Link>
                    <Link href="/dashboard" className="text-zinc-300 hover:bg-[#0D182A] hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors">🚧 Channel Analytics</Link>
                    <Link href="/alerts" className="text-zinc-300 hover:bg-[#0D182A] hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors">🚧 Trend Alerts</Link>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <Link href="/pricing" className="flex h-10 items-center justify-center px-6 rounded-full bg-gradient-to-r from-sky-400 to-cyan-500 hover:from-sky-300 hover:to-cyan-400 text-[10px] font-black tracking-widest text-[#09111E] uppercase shadow-[0_0_15px_rgba(56,189,248,0.3)] hover:shadow-[0_0_20px_rgba(56,189,248,0.5)] transition-all hover:-translate-y-0.5 active:translate-y-0">
                  Upgrade to Pro
                </Link>
              </div>
            </div>
          </div>
        </nav>
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 relative z-10">
          {children}
        </main>
      </body>
    </html>
  );
}
