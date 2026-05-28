"use client";

import React, { useState } from 'react';
import { LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer } from 'recharts';
import { Search, TrendingUp, Activity, PlaySquare, AlertTriangle, Lock } from 'lucide-react';

export default function ChannelAnalytics() {
  const [channelId, setChannelId] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!channelId) return;

    setLoading(true);
    setError(null);
    setData(null);

    try {
      // URL-encode the channel ID so handles like @MrBeast don't break the URL path
      const response = await fetch(`http://127.0.0.1:8000/channel/${encodeURIComponent(channelId)}/analytics`);
      if (!response.ok) throw new Error('Failed to fetch analytics');
      const result = await response.json();
      setData(result);
    } catch (err: any) {
      setError(err.message || 'An error occurred while fetching data');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex justify-between items-start">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            Channel Analytics
            <span className="text-[10px] px-2 py-0.5 font-bold border border-amber-500/30 rounded-full bg-amber-500/10 text-amber-500 tracking-widest uppercase">🚧 Under Construction</span>
          </h1>
          <p className="text-zinc-400">Track hook effectiveness across a creator's catalog and benchmark against competitors.</p>
        </div>
        {data && (
          <div className="flex items-center gap-4 animate-in fade-in duration-500">
            <h2 className="text-xl font-bold text-white">{data.channel_name}</h2>
            {data.profile_pic && (
              <img 
                src={data.profile_pic} 
                alt={`${data.channel_name} Profile`} 
                className="w-14 h-14 rounded-full border-2 border-zinc-700 object-cover shadow-lg"
              />
            )}
          </div>
        )}
      </div>

      {/* Search Bar */}
      <form onSubmit={fetchAnalytics} className="flex gap-4">
        <div className="relative flex-1 max-w-xl">
          <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
            <Search className="w-5 h-5 text-zinc-500" />
          </div>
          <input
            type="text"
            className="block w-full p-4 pl-10 text-sm border rounded-lg bg-[#09111E] border-white/10 placeholder-zinc-500 text-white focus:ring-sky-500 focus:border-sky-500"
            placeholder="Enter YouTube Channel ID or Handle (e.g. @MrBeast)..."
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="text-[#09111E] bg-sky-500 hover:bg-sky-400 font-black tracking-widest uppercase rounded-lg text-sm px-6 py-4 focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-50"
        >
          {loading ? 'Analyzing...' : 'Analyze Channel'}
        </button>
      </form>

      {error && (
        <div className="p-4 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg">
          {error}
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
          
          <div className="bg-amber-950/30 border border-amber-900/50 rounded-2xl p-6 flex flex-col gap-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-6 h-6 text-amber-500 flex-shrink-0 mt-1" />
              <div className="flex flex-col gap-2">
                <h3 className="text-lg font-semibold text-amber-500">Prototype Warning: Mock Retention Data</h3>
                <p className="text-sm text-zinc-300 leading-relaxed">
                  The retention graphs below are currently populated with <strong>simulated mock data</strong> for demonstration purposes. YouTube's public API does not expose factual audience retention metrics for third-party videos.
                </p>
                <p className="text-sm text-zinc-300 leading-relaxed">
                  To view actual, factual retention curves, a creator must explicitly grant this application access to their private data using <strong>Google's OAuth 2.0</strong> and the <strong>YouTube Analytics API</strong>.
                </p>
              </div>
            </div>
            <div className="flex justify-end mt-2">
              <button 
                type="button"
                onClick={() => alert('This is a dummy button! In a production app, this would redirect the creator to the Google OAuth consent screen requesting the "yt-analytics.readonly" scope.')}
                className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
              >
                Connect YouTube Analytics (OAuth)
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Trend Detection Chart */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-sky-500/20 rounded-lg">
                  <TrendingUp className="w-5 h-5 text-sky-400" />
                </div>
                <h2 className="text-lg font-semibold text-white">Hook Retention Trend (12 Weeks)</h2>
              </div>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.trends} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                    <XAxis dataKey="week" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={(val) => `${val}%`} />
                    <RechartsTooltip 
                      contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px' }}
                      itemStyle={{ color: '#c7d2fe' }}
                    />
                    <Line type="monotone" dataKey="retention" stroke="#818cf8" strokeWidth={3} dot={{ r: 4, fill: '#818cf8' }} activeDot={{ r: 6 }} name="Retention (15s)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Benchmarking Chart */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-emerald-500/20 rounded-lg">
                  <Activity className="w-5 h-5 text-emerald-400" />
                </div>
                <h2 className="text-lg font-semibold text-white">Competitor Benchmarking</h2>
              </div>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.benchmarks} margin={{ top: 20, right: 20, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                    <XAxis dataKey="category" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={(val) => `${val}%`} />
                    <RechartsTooltip 
                      cursor={{fill: '#27272a'}}
                      contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px' }}
                    />
                    <Bar dataKey="retention" radius={[4, 4, 0, 0]} name="Avg Retention (15s)">
                      {
                        data.benchmarks.map((entry: any, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))
                      }
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Catalog Effectiveness List */}
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-pink-500/20 rounded-lg">
                <PlaySquare className="w-5 h-5 text-pink-400" />
              </div>
              <h2 className="text-lg font-semibold text-white">Catalog Effectiveness: Top Performing Hooks</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {data.top_hooks.map((hook: any) => (
                <div key={hook.id} className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 flex flex-col gap-3 transition-colors hover:border-zinc-700">
                  <div className="flex justify-between items-start">
                    <h3 className="font-medium text-zinc-100 line-clamp-2 text-sm">{hook.title}</h3>
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                      <Lock className="w-3 h-3" />
                      Locked
                    </span>
                  </div>
                  <p className="text-zinc-400 text-sm italic border-l-2 border-zinc-700 pl-3">"{hook.hook_text}"</p>
                  <div className="mt-auto pt-4 flex justify-between items-center text-xs text-zinc-500">
                    <span>Sentiment: <span className="text-zinc-300">{hook.sentiment}</span></span>
                    <span>{(hook.views / 1000000).toFixed(1)}M Views</span>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="mt-6 p-4 bg-sky-500/10 border border-sky-500/20 rounded-xl">
              <p className="text-sm text-sky-200"><strong className="text-sky-400 uppercase tracking-widest text-[10px]">AI Insight:</strong> {data.summary}</p>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
