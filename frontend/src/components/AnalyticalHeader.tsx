import React from 'react';
import { Play, ThumbsUp, MessageSquare, Percent, TrendingUp, Sparkles } from 'lucide-react';

export interface VideoMetrics {
  views: number;
  likes: number;
  comments: number;
  duration: number;
}

export interface VideoData {
  video_id: string;
  platform: string;
  title: string;
  metrics: VideoMetrics;
  engagement_rate: number;
  whisper_stubbed?: boolean;
  is_estimated_views?: boolean;
  transcript?: Array<{ text: string; start: number; duration: number }>;
}

interface AnalyticalHeaderProps {
  videoA: VideoData | null;
  videoB: VideoData | null;
}

export default function AnalyticalHeader({ videoA, videoB }: AnalyticalHeaderProps) {
  if (!videoA && !videoB) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-dashed border-zinc-800 rounded-2xl bg-zinc-950 text-zinc-400">
        <Sparkles className="w-8 h-8 mb-3 text-sky-500 animate-pulse" />
        <p className="text-sm font-medium">Input two video URLs above to start the deep analytical audit</p>
      </div>
    );
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  };

  const getMetricDiff = (valA: number, valB: number) => {
    if (!valA || !valB || valA === valB) return null;
    const diff = valA - valB;
    const percent = ((diff) / valB) * 100;
    if (Math.abs(percent) < 0.01) return null;
    return {
      diff,
      percent: percent.toFixed(1),
      isPositive: diff > 0
    };
  };

  const renderKPICards = (title: string, data: VideoData, otherData: VideoData | null, colorClass: string) => {
    const metrics = data.metrics;
    
    return (
      <div className="flex flex-col flex-1 p-6 rounded-2xl bg-zinc-900/40 border border-zinc-800/60 backdrop-blur-md shadow-xl animate-fade-in-up">
        <div className="flex items-center justify-between mb-4">
          <span className={`px-3 py-1 text-xs font-semibold uppercase tracking-wider rounded-full ${colorClass}`}>
            {title}: {data.platform}
          </span>
          {data.whisper_stubbed && (
            <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-500/20 text-amber-300 rounded border border-amber-500/30">
              {data.platform === 'youtube' ? 'Whisper Fallback' : 'Caption Fallback'}
            </span>
          )}
        </div>
        <h3 className="text-lg font-bold text-white mb-6 line-clamp-2 min-h-[3.5rem] leading-snug">
          {data.title}
        </h3>

        <div className="grid grid-cols-2 gap-4">
          {/* Views Card */}
          <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 hover:-translate-y-1 hover:border-zinc-700 hover:shadow-lg transition-all animate-slide-up delay-100">
            <div className="flex items-center gap-2 text-zinc-400 mb-1 text-xs font-medium">
              <Play className="w-3.5 h-3.5" />
              Views
            </div>
            <div className="text-xl font-bold text-white">
              {data.is_estimated_views ? '~' : ''}{formatNumber(metrics.views)}
            </div>
            {data.is_estimated_views && (
              <div className="text-[9px] text-zinc-500 mt-0.5">estimated</div>
            )}
            {otherData && (
              <div className="mt-1">
                {(() => {
                  const diffInfo = getMetricDiff(metrics.views, otherData.metrics.views);
                  if (!diffInfo) return <span className="text-[10px] text-zinc-600">—</span>;
                  return (
                    <span className={`text-[10px] font-bold ${diffInfo.isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {diffInfo.isPositive ? '+' : ''}{diffInfo.percent}% vs other
                    </span>
                  );
                })()}
              </div>
            )}
          </div>

          {/* Likes Card */}
          <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 hover:-translate-y-1 hover:border-zinc-700 hover:shadow-lg transition-all animate-slide-up delay-150">
            <div className="flex items-center gap-2 text-zinc-400 mb-1 text-xs font-medium">
              <ThumbsUp className="w-3.5 h-3.5" />
              Likes
            </div>
            <div className="text-xl font-bold text-white">{formatNumber(metrics.likes)}</div>
            {otherData && (
              <div className="mt-1">
                {(() => {
                  const diffInfo = getMetricDiff(metrics.likes, otherData.metrics.likes);
                  if (!diffInfo) return <span className="text-[10px] text-zinc-600">—</span>;
                  return (
                    <span className={`text-[10px] font-bold ${diffInfo.isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {diffInfo.isPositive ? '+' : ''}{diffInfo.percent}% vs other
                    </span>
                  );
                })()}
              </div>
            )}
          </div>

          {/* Comments Card */}
          <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 hover:-translate-y-1 hover:border-zinc-700 hover:shadow-lg transition-all animate-slide-up delay-200">
            <div className="flex items-center gap-2 text-zinc-400 mb-1 text-xs font-medium">
              <MessageSquare className="w-3.5 h-3.5" />
              Comments
            </div>
            <div className="text-xl font-bold text-white">{formatNumber(metrics.comments)}</div>
            {otherData && (
              <div className="mt-1">
                {(() => {
                  const diffInfo = getMetricDiff(metrics.comments, otherData.metrics.comments);
                  if (!diffInfo) return <span className="text-[10px] text-zinc-600">—</span>;
                  return (
                    <span className={`text-[10px] font-bold ${diffInfo.isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {diffInfo.isPositive ? '+' : ''}{diffInfo.percent}% vs other
                    </span>
                  );
                })()}
              </div>
            )}
          </div>

          {/* Engagement Rate Card */}
          <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 hover:-translate-y-1 hover:border-zinc-700 hover:shadow-lg transition-all animate-slide-up delay-300">
            <div className="flex items-center gap-2 text-zinc-400 mb-1 text-xs font-medium">
              <Percent className="w-3.5 h-3.5" />
              Engagement
            </div>
            <div className="flex items-baseline gap-2">
              <div className="text-xl font-bold text-white">{data.engagement_rate}%</div>
              <span 
                title="1-3% Average | 4-6% Excellent | >10% Extremely Rare (viral/hyper-loyal)"
                className={`cursor-help text-[10px] px-1.5 py-0.5 rounded border ${
                data.engagement_rate > 10 ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' :
                data.engagement_rate >= 4 ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
                'bg-zinc-500/10 border-zinc-500/20 text-zinc-400'
              }`}>
                {data.engagement_rate > 10 ? 'Rare' : data.engagement_rate >= 4 ? 'Excellent' : 'Average'}
              </span>
            </div>
            {otherData && (
              <div className="mt-1">
                {(() => {
                  const diff = data.engagement_rate - otherData.engagement_rate;
                  if (Math.abs(diff) < 0.01) return <span className="text-[10px] text-zinc-600">—</span>;
                  const isPositive = diff > 0;
                  return (
                    <span className={`text-[10px] font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isPositive ? '+' : ''}{diff.toFixed(2)}% margin
                    </span>
                  );
                })()}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col md:flex-row gap-6 w-full mb-8">
      {videoA && renderKPICards("Video A", videoA, videoB, "bg-sky-500/10 text-sky-400 border border-sky-500/20")}
      {videoB && renderKPICards("Video B", videoB, videoA, "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20")}
    </div>
  );
}
