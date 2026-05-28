"use client";

import React, { useState } from 'react';
import { Camera, Image as ImageIcon, Zap, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';

export default function MultiModalMockup() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="bg-[#0D182A]/80 border border-white/5 rounded-2xl p-6 mt-6 transition-all">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between group"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/20 rounded-lg group-hover:bg-indigo-500/30 transition-colors">
            <Camera className="w-5 h-5 text-indigo-400" />
          </div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            Multi-Modal Frame Analysis
            <span className="ml-2 text-xs font-bold uppercase tracking-wider text-amber-500 bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded">Pro</span>
            <span className="ml-2 text-[10px] px-2 py-0.5 font-bold border border-amber-500/30 rounded-full bg-amber-500/10 text-amber-500 tracking-widest uppercase hidden sm:inline-block">🚧 Under Construction</span>
          </h2>
        </div>
        <div className="p-2 text-zinc-500 group-hover:text-white transition-colors">
          {isOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </div>
      </button>

      {isOpen && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 animate-in slide-in-from-top-4 fade-in duration-200">
          {/* Visual Hook Analysis */}
          <div className="bg-[#09111E] border border-white/5 rounded-xl p-5">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" /> Visual Hook (First 3 Seconds)
            </h3>
            <p className="text-zinc-400 text-sm mb-4">
              OpenCV & CLIP embeddings detected high-contrast motion and a human face in the center third of the frame.
            </p>
            <div className="flex gap-2">
              <div className="flex-1 bg-[#11223B] h-24 rounded-lg border border-white/5 flex items-center justify-center relative overflow-hidden group">
                <ImageIcon className="w-6 h-6 text-zinc-700" />
                <div className="absolute inset-0 bg-emerald-500/10 border-2 border-emerald-500/50 scale-95 opacity-0 group-hover:opacity-100 transition-opacity"></div>
              </div>
              <div className="flex-1 bg-[#11223B] h-24 rounded-lg border border-white/5 flex items-center justify-center">
                <ImageIcon className="w-6 h-6 text-zinc-700" />
              </div>
              <div className="flex-1 bg-[#11223B] h-24 rounded-lg border border-white/5 flex items-center justify-center">
                <ImageIcon className="w-6 h-6 text-zinc-700" />
              </div>
            </div>
            <div className="mt-4 flex justify-between items-center text-xs">
              <span className="text-zinc-500">Frame Density Score:</span>
              <span className="text-emerald-400 font-bold">92 / 100</span>
            </div>
          </div>

          {/* Thumbnail Quality */}
          <div className="bg-[#09111E] border border-white/5 rounded-xl p-5">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" /> B-Roll Pacing
            </h3>
            <p className="text-zinc-400 text-sm mb-4">
              Visual cut frequency drops significantly between 0:45 and 1:12. This correlates strongly with historical retention dips.
            </p>

            <div className="w-full bg-[#11223B] rounded-full h-2 mb-1 mt-6 flex">
              <div className="bg-emerald-500 h-2 rounded-l-full w-1/3"></div>
              <div className="bg-amber-500 h-2 w-1/4"></div>
              <div className="bg-red-500 h-2 w-1/6"></div>
              <div className="bg-emerald-500 h-2 rounded-r-full flex-1"></div>
            </div>
            <div className="flex justify-between text-[10px] text-zinc-500 uppercase font-bold tracking-wider mb-4">
              <span>Fast Cuts</span>
              <span>Slow</span>
              <span>Static</span>
              <span>Fast Cuts</span>
            </div>

            <div className="mt-auto pt-2 flex justify-between items-center text-xs">
              <span className="text-zinc-500">Action Required:</span>
              <span className="text-amber-400 font-medium">Add B-Roll at 0:45</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
