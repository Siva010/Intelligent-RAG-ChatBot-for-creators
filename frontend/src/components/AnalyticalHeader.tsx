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
  platform: 'youtube' | 'tiktok' | 'instagram';
  title: string;
  metrics: VideoMetrics;
  engagement_rate: number;
  whisper_stubbed?: boolean;
}

interface AnalyticalHeaderProps {
  videoA: VideoData | null;
  videoB: VideoData | null;
}

export default function AnalyticalHeader({ videoA, videoB }: AnalyticalHeaderProps) {
  if (!videoA && !videoB) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-dashed border-zinc-800 rounded-2xl bg-zinc-950 text-zinc-400">
        <Sparkles className="w-8 h-8 mb-3 text-indigo-500 animate-pulse" />
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
    if (!valA || !valB) return null;
    const diff = valA - valB;
    const percent = ((diff) / valB) * 100;
    return {
      diff,
      percent: percent.toFixed(1),
      isPositive: diff > 0
    };
  };

  const renderKPICards = (title: string, data: VideoData, otherData: VideoData | null, colorClass: string) => {
    const metrics = data.metrics;
    
    return (
      <div className="flex flex-col flex-1 p-6 rounded-2xl bg-zinc-900/50 border border-zinc-800 backdrop-blur-md">
        <div className="flex items-center justify-between mb-4">
          <span className={`px-3 py-1 text-xs font-semibold uppercase tracking-wider rounded-full ${colorClass}`}>
            {title}: {data.platform}
          </span>
          {data.whisper_stubbed && (
            <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-500/20 text-amber-300 rounded border border-amber-500/30">
              Whisper Fallback
            </span>
          )}
        </div>
        <h3 className="text-lg font-bold text-white mb-6 line-clamp-2 min-h-[3.5rem] leading-snug">
          {data.title}
        </h3>

        <div className="grid grid-cols-2 gap-4">
          {/* Views Card */}
          <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/80">
            <div className="flex items-center gap-2 text-zinc-400 mb-1 text-xs font-medium">
              <Play className="w-3.5 h-3.5" />
              Views
            </div>
            <div className="text-xl font-bold text-white">{formatNumber(metrics.views)}</div>
            {otherData && (
              <div className="mt-1">
                {(() => {
                  const diffInfo = getMetricDiff(metrics.views, otherData.metrics.views);
                  if (!diffInfo) return null;
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
          <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/80">
            <div className="flex items-center gap-2 text-zinc-400 mb-1 text-xs font-medium">
              <ThumbsUp className="w-3.5 h-3.5" />
              Likes
            </div>
            <div className="text-xl font-bold text-white">{formatNumber(metrics.likes)}</div>
            {otherData && (
              <div className="mt-1">
                {(() => {
                  const diffInfo = getMetricDiff(metrics.likes, otherData.metrics.likes);
                  if (!diffInfo) return null;
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
          <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/80">
            <div className="flex items-center gap-2 text-zinc-400 mb-1 text-xs font-medium">
              <MessageSquare className="w-3.5 h-3.5" />
              Comments
            </div>
            <div className="text-xl font-bold text-white">{formatNumber(metrics.comments)}</div>
            {otherData && (
              <div className="mt-1">
                {(() => {
                  const diffInfo = getMetricDiff(metrics.comments, otherData.metrics.comments);
                  if (!diffInfo) return null;
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
          <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/80">
            <div className="flex items-center gap-2 text-zinc-400 mb-1 text-xs font-medium">
              <Percent className="w-3.5 h-3.5" />
              Engagement
            </div>
            <div className="text-xl font-bold text-white">{data.engagement_rate}%</div>
            {otherData && (
              <div className="mt-1">
                {(() => {
                  const diff = data.engagement_rate - otherData.engagement_rate;
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
      {videoA && renderKPICards("Video A", videoA, videoB, "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20")}
      {videoB && renderKPICards("Video B", videoB, videoA, "bg-violet-500/10 text-violet-400 border border-violet-500/20")}
    </div>
  );
}
