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
  title: "RAG Social Chatbot",
  description: "Viral Social Script Doctor Dashboard",
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
                <div className="flex items-baseline space-x-2 sm:space-x-6 md:ml-16 overflow-x-auto">
                  <Link href="/" className="text-zinc-300 hover:text-white px-2 py-2 text-xs font-bold uppercase tracking-widest transition-colors whitespace-nowrap">A/B Testing</Link>
                  <Link href="/dashboard" className="text-zinc-300 hover:text-white px-2 py-2 text-xs font-bold uppercase tracking-widest transition-colors whitespace-nowrap">Channel Analytics</Link>
                </div>
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
