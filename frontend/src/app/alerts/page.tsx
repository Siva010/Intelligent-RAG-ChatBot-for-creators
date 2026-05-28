"use client";

import React, { useState } from 'react';
import { Bell, Mail, MessageSquare, Zap, Clock, Plus } from 'lucide-react';

export default function TrendAlertsPage() {
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [slackEnabled, setSlackEnabled] = useState(false);

  return (
    <div className="w-full max-w-5xl mx-auto py-8 px-4 sm:px-6">
      <div className="flex items-center gap-3 mb-8">
        <div className="p-3 bg-amber-500/20 rounded-xl">
          <Bell className="w-8 h-8 text-amber-500" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            Trend Alert Engine
            <span className="text-[10px] px-2 py-0.5 font-bold border border-amber-500/30 rounded-full bg-amber-500/10 text-amber-500 tracking-widest uppercase">🚧 Under Construction</span>
          </h1>
          <p className="text-zinc-400">Monitor viral content automatically and receive personalized creator briefings.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Main Configuration */}
        <div className="lg:col-span-2 space-y-6">
          
          <div className="bg-[#0D182A]/80 border border-white/5 rounded-2xl p-6">
            <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-indigo-400" /> Active Monitors
            </h2>
            
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-[#09111E] border border-white/5 rounded-xl">
                <div>
                  <h3 className="text-white font-medium">Finance & Crypto Niche</h3>
                  <p className="text-sm text-zinc-500">Tracking: "investing", "crypto", "@AlexHormozi"</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-medium rounded border border-emerald-500/20">Active</span>
                </div>
              </div>
              
              <div className="flex items-center justify-between p-4 bg-[#09111E] border border-white/5 rounded-xl">
                <div>
                  <h3 className="text-white font-medium">Tech Reviews</h3>
                  <p className="text-sm text-zinc-500">Tracking: "apple vision pro", "M3 macbook"</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 bg-zinc-500/10 text-zinc-400 text-xs font-medium rounded border border-zinc-600">Paused</span>
                </div>
              </div>

              <button className="w-full py-3 border border-dashed border-zinc-700 text-zinc-400 rounded-xl hover:text-white hover:border-zinc-500 transition-colors flex items-center justify-center gap-2">
                <Plus className="w-4 h-4" /> Create New Monitor
              </button>
            </div>
          </div>

        </div>

        {/* Sidebar Configuration */}
        <div className="space-y-6">
          <div className="bg-[#0D182A]/80 border border-white/5 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Delivery Methods</h2>
            
            <div className="space-y-4">
              {/* Email Toggle */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${emailEnabled ? 'bg-indigo-500/20 text-indigo-400' : 'bg-[#11223B] text-zinc-500'}`}>
                    <Mail className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-white font-medium text-sm">Email Briefing</p>
                    <p className="text-zinc-500 text-xs">Daily at 9:00 AM</p>
                  </div>
                </div>
                <button 
                  onClick={() => setEmailEnabled(!emailEnabled)}
                  className={`w-12 h-6 rounded-full relative transition-colors ${emailEnabled ? 'bg-indigo-600' : 'bg-zinc-700'}`}
                >
                  <span className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${emailEnabled ? 'left-7' : 'left-1'}`} />
                </button>
              </div>

              {/* Slack Toggle */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${slackEnabled ? 'bg-amber-500/20 text-amber-400' : 'bg-zinc-800 text-zinc-500'}`}>
                    <MessageSquare className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-white font-medium text-sm">Slack Integration</p>
                    <p className="text-zinc-500 text-xs">Instant alerts</p>
                  </div>
                </div>
                <button 
                  onClick={() => setSlackEnabled(!slackEnabled)}
                  className={`w-12 h-6 rounded-full relative transition-colors ${slackEnabled ? 'bg-amber-500' : 'bg-zinc-700'}`}
                >
                  <span className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${slackEnabled ? 'left-7' : 'left-1'}`} />
                </button>
              </div>
            </div>
          </div>

          <div className="bg-indigo-900/20 border border-indigo-500/20 rounded-2xl p-6">
            <div className="flex items-center gap-2 text-indigo-400 mb-2">
              <Clock className="w-5 h-5" />
              <h3 className="font-semibold">Next Briefing</h3>
            </div>
            <p className="text-indigo-200 text-sm">Your next daily trend briefing will be generated and delivered in <strong>14 hours, 22 minutes</strong>.</p>
          </div>
        </div>

      </div>
    </div>
  );
}
