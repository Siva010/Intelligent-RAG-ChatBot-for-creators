"use client";

import React, { useState } from 'react';
import { Sparkles, Copy, Check, ChevronDown, ChevronUp, Wand2 } from 'lucide-react';

interface ScriptRewriterAccordionProps {
  originalText?: string;
}

export default function ScriptRewriterAccordion({ originalText }: ScriptRewriterAccordionProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const variants = [
    {
      style: "High Stakes / Curiosity",
      score: 94,
      text: "If you don't implement this exact strategy by tomorrow, you're leaving a million dollars on the table. Here's exactly how it works."
    },
    {
      style: "Story-Driven",
      score: 88,
      text: "I spent 5 years and $50,000 figuring out this framework. Today, I'm giving you the entire blueprint for free in just 5 minutes."
    },
    {
      style: "Direct & Punchy",
      score: 82,
      text: "This is the single most important metric for your channel. Ignore it, and your channel dies. Master it, and you go viral."
    }
  ];

  return (
    <div className="bg-[#0D182A]/80 border border-white/5 rounded-2xl p-6 mt-6 transition-all">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between group"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/20 rounded-lg group-hover:bg-indigo-500/30 transition-colors">
            <Sparkles className="w-5 h-5 text-indigo-400" />
          </div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 text-left">
            Advanced Script-Rewriting Agent
            <span className="ml-2 text-xs font-bold uppercase tracking-wider text-amber-500 bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded">Pro</span>
            <span className="ml-2 text-[10px] px-2 py-0.5 font-bold border border-amber-500/30 rounded-full bg-amber-500/10 text-amber-500 tracking-widest uppercase hidden sm:inline-block">🚧 Under Construction</span>
          </h2>
        </div>
        <div className="p-2 text-zinc-500 group-hover:text-white transition-colors">
          {isOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </div>
      </button>

      {isOpen && (
        <div className="mt-8 pt-6 border-t border-white/5 animate-in slide-in-from-top-4 fade-in duration-200">
          
          <div className="flex justify-center mb-10">
            <button className="h-14 px-10 rounded-full bg-gradient-to-r from-sky-400 to-cyan-500 text-sm font-black tracking-widest text-[#09111E] uppercase shadow-[0_0_30px_rgba(56,189,248,0.3)] flex items-center justify-center gap-3 cursor-default">
              <Wand2 className="w-5 h-5 text-[#09111E]" />
              <span>Auto-Rewrite Scripts (Mock)</span>
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <h3 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">Original Hook</h3>
              <div className="p-4 bg-[#11223B] border border-white/10 rounded-xl text-zinc-300 text-sm italic h-full">
                "{originalText || "In this video we are going to talk about how to grow your channel using a few tips and tricks that I have learned."}"
              </div>
            </div>

            <div className="lg:col-span-2 space-y-4">
              <h3 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider">Generated Variants Optimized for Retention</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {variants.map((variant, index) => (
                  <div key={index} className="bg-[#09111E] border border-white/10 rounded-xl p-5 hover:border-indigo-500/50 transition-colors group">
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium text-sm">{variant.style}</span>
                        <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase rounded border border-emerald-500/20">
                          Score: {variant.score}
                        </span>
                      </div>
                      <button 
                        onClick={(e) => { e.stopPropagation(); handleCopy(variant.text, index); }}
                        className="p-1.5 text-zinc-500 hover:text-white hover:bg-zinc-700 rounded-md transition-colors"
                      >
                        {copiedIndex === index ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                    <p className="text-zinc-300 text-sm leading-relaxed">
                      "{variant.text}"
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
