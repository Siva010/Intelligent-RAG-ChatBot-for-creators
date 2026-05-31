import React from 'react';
import { Play, ThumbsUp, MessageSquare, Percent, Calendar, Users } from 'lucide-react';

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
  creator?: string;
  follower_count?: number;
  hashtags?: string[];
  upload_date?: string;
  thumbnail_url?: string;
  metrics: VideoMetrics;
  engagement_rate: number;
  whisper_stubbed?: boolean;
  asr_method?: string;
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
        <Play className="w-8 h-8 mb-3 text-sky-500 animate-pulse" />
        <p className="text-sm font-medium">Input two video URLs above to start the deep analytical audit</p>
      </div>
    );
  }

  const formatNumber = (num: number) => {
    if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
    if (num >= 1_000) return (num / 1_000).toFixed(1) + 'K';
    return num.toString();
  };

  const formatFollowers = (count?: number) => {
    if (!count || count === 0) return 'N/A';
    if (count >= 1_000_000) return (count / 1_000_000).toFixed(1) + 'M';
    if (count >= 1_000) return (count / 1_000).toFixed(1) + 'K';
    return count.toString();
  };

  const getMetricDiff = (valA: number, valB: number) => {
    // Use explicit null checks — falsy would incorrectly suppress 0 values
    // (e.g. a video with 0 comments). Only skip when valB is 0 (div-by-zero).
    if (valA == null || valB == null || valB === 0 || valA === valB) return null;
    const diff = valA - valB;
    const percent = (diff / valB) * 100;
    if (Math.abs(percent) < 0.01) return null;
    return { diff, percent: percent.toFixed(1), isPositive: diff > 0 };
  };

  const getYouTubeEmbedUrl = (videoId: string, platform: string) => {
    if (platform === 'youtube') {
      return `https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1`;
    }
    return null;
  };

  const renderCard = (
    label: string,
    data: VideoData,
    otherData: VideoData | null,
    accentClass: string,
    borderClass: string
  ) => {
    const metrics = data.metrics;
    const embedUrl = getYouTubeEmbedUrl(data.video_id, data.platform);

    return (
      <div className={`flex flex-col flex-1 rounded-2xl bg-zinc-900/40 border ${borderClass} backdrop-blur-md shadow-xl overflow-hidden animate-fade-in-up`}>

        {/* Thumbnail / Embed */}
        <div className="relative w-full aspect-video bg-zinc-950 overflow-hidden">
          {embedUrl ? (
            <iframe
              src={embedUrl}
              title={data.title}
              className="w-full h-full"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          ) : data.thumbnail_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={data.thumbnail_url}
              alt={data.title}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Play className="w-10 h-10 text-zinc-700" />
            </div>
          )}
          {/* Platform badge */}
          <span className={`absolute top-3 left-3 px-2.5 py-1 text-[10px] font-black tracking-widest uppercase rounded-full ${accentClass}`}>
            {label} · {data.platform}
          </span>
          {data.whisper_stubbed && (
            <span className="absolute top-3 right-3 px-2 py-0.5 text-[10px] font-medium bg-amber-500/80 text-zinc-900 rounded">
              Caption Fallback
            </span>
          )}
          {!data.whisper_stubbed && data.asr_method === 'whisper' && (
            <span className="absolute top-3 right-3 px-2 py-0.5 text-[10px] font-medium bg-violet-500/80 text-white rounded">
              Whisper ASR
            </span>
          )}
          {!data.whisper_stubbed && data.asr_method === 'gemini' && (
            <span className="absolute top-3 right-3 px-2 py-0.5 text-[10px] font-medium bg-sky-500/80 text-white rounded">
              Gemini ASR
            </span>
          )}
        </div>

        {/* Card Body */}
        <div className="p-6 flex flex-col gap-5">

          {/* Title */}
          <h3 className="text-base font-bold text-white line-clamp-2 leading-snug">
            {data.title}
          </h3>

          {/* Creator row */}
          <div className="flex items-center justify-between text-xs text-zinc-400 gap-4">
            <div className="flex items-center gap-1.5 min-w-0">
              <Users className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" />
              <span className="font-semibold text-zinc-200 truncate">{data.creator || 'Unknown'}</span>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <span className="text-zinc-500">Followers:</span>
              <span className="font-bold text-zinc-300">{formatFollowers(data.follower_count)}</span>
            </div>
          </div>

          {/* Upload date + hashtags */}
          <div className="flex flex-wrap items-center gap-2">
            {data.upload_date && data.upload_date !== 'Unknown' && (
              <div className="flex items-center gap-1 text-[11px] text-zinc-500">
                <Calendar className="w-3 h-3" />
                <span>{data.upload_date}</span>
              </div>
            )}
            {data.hashtags && data.hashtags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {data.hashtags.slice(0, 3).map((tag, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* KPI grid */}
          <div className="grid grid-cols-2 gap-3">

            {/* Views */}
            <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800/80 hover:-translate-y-1 hover:border-zinc-700 hover:shadow-lg transition-all">
              <div className="flex items-center gap-1.5 text-zinc-400 mb-1 text-xs font-medium">
                <Play className="w-3.5 h-3.5" /> Views
              </div>
              <div className="text-lg font-bold text-white">
                {data.is_estimated_views ? '~' : ''}{formatNumber(metrics.views)}
              </div>
              {data.is_estimated_views && <div className="text-[9px] text-zinc-500">estimated</div>}
              {otherData && (() => {
                const d = getMetricDiff(metrics.views, otherData.metrics.views);
                if (!d) return <span className="text-[10px] text-zinc-600">—</span>;
                return <span className={`text-[10px] font-bold ${d.isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>{d.isPositive ? '+' : ''}{d.percent}% vs other</span>;
              })()}
            </div>

            {/* Likes */}
            <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800/80 hover:-translate-y-1 hover:border-zinc-700 hover:shadow-lg transition-all">
              <div className="flex items-center gap-1.5 text-zinc-400 mb-1 text-xs font-medium">
                <ThumbsUp className="w-3.5 h-3.5" /> Likes
              </div>
              <div className="text-lg font-bold text-white">{formatNumber(metrics.likes)}</div>
              {otherData && (() => {
                const d = getMetricDiff(metrics.likes, otherData.metrics.likes);
                if (!d) return <span className="text-[10px] text-zinc-600">—</span>;
                return <span className={`text-[10px] font-bold ${d.isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>{d.isPositive ? '+' : ''}{d.percent}% vs other</span>;
              })()}
            </div>

            {/* Comments */}
            <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800/80 hover:-translate-y-1 hover:border-zinc-700 hover:shadow-lg transition-all">
              <div className="flex items-center gap-1.5 text-zinc-400 mb-1 text-xs font-medium">
                <MessageSquare className="w-3.5 h-3.5" /> Comments
              </div>
              <div className="text-lg font-bold text-white">{formatNumber(metrics.comments)}</div>
              {otherData && (() => {
                const d = getMetricDiff(metrics.comments, otherData.metrics.comments);
                if (!d) return <span className="text-[10px] text-zinc-600">—</span>;
                return <span className={`text-[10px] font-bold ${d.isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>{d.isPositive ? '+' : ''}{d.percent}% vs other</span>;
              })()}
            </div>

            {/* Engagement Rate */}
            <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800/80 hover:-translate-y-1 hover:border-zinc-700 hover:shadow-lg transition-all">
              <div className="flex items-center gap-1.5 text-zinc-400 mb-1 text-xs font-medium">
                <Percent className="w-3.5 h-3.5" /> Engagement
              </div>
              <div className="flex items-baseline gap-2">
                <div className="text-lg font-bold text-white">{data.engagement_rate}%</div>
                <span
                  title="1-3% Average | 4-6% Excellent | >10% Extremely Rare (viral/hyper-loyal)"
                  className={`cursor-help text-[10px] px-1.5 py-0.5 rounded border ${data.engagement_rate > 10 ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' :
                    data.engagement_rate >= 4 ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
                      'bg-zinc-500/10 border-zinc-500/20 text-zinc-400'
                    }`}
                >
                  {data.engagement_rate > 10 ? 'Rare' : data.engagement_rate >= 4 ? 'Excellent' : 'Average'}
                </span>
              </div>
              {otherData && (() => {
                const diff = data.engagement_rate - otherData.engagement_rate;
                if (Math.abs(diff) < 0.01) return <span className="text-[10px] text-zinc-600">—</span>;
                return <span className={`text-[10px] font-bold ${diff > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{diff > 0 ? '+' : ''}{diff.toFixed(2)}% margin</span>;
              })()}
            </div>

          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col md:flex-row gap-6 w-full mb-8">
      {videoA && renderCard('Video A', videoA, videoB, 'bg-sky-500/10 text-sky-400 border border-sky-500/20', 'border-zinc-800/60')}
      {videoB && renderCard('Video B', videoB, videoA, 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20', 'border-zinc-800/60')}
    </div>
  );
}
