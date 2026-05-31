import React, { useRef, useEffect, useState } from 'react';
import { Send, Bot, User, Loader2, PlayCircle, Zap } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { VideoData } from './AnalyticalHeader';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatConsoleProps {
  messages: ChatMessage[];
  input: string;
  setInput: (val: string) => void;
  onSendMessage: (e: React.FormEvent, overrideMessage?: string) => void;
  isLoading: boolean;
  disabled: boolean;
  videoA?: VideoData | null;
  videoB?: VideoData | null;
}

export default function ChatConsole({
  messages,
  input,
  setInput,
  onSendMessage,
  isLoading,
  disabled,
  videoA,
  videoB
}: ChatConsoleProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);

  // Auto-scroll logic: only scroll if the user hasn't manually scrolled up
  useEffect(() => {
    if (isAutoScroll && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [messages, isLoading, isAutoScroll]);

  // Detect if user scrolled up
  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    // If they are within 100px of the bottom, re-enable auto-scroll
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
    setIsAutoScroll(isAtBottom);
  };

  const engA = videoA?.engagement_rate || 0;
  const engB = videoB?.engagement_rate || 0;
  const winner = engA >= engB ? 'Video A' : 'Video B';
  const loser = engA >= engB ? 'Video B' : 'Video A';

  const dynamicPrompts = [
    `Why did ${winner} get more engagement than ${loser}?`,
    "What's the engagement rate of each video?",
    "Compare the hooks in the first 5 seconds.",
    `Who's the creator of ${loser} and what's their follower count?`,
    `Suggest improvements for ${loser} based on what worked in ${winner}.`,
  ];

  const seekVideo = (videoLabel: string, timestamp: string) => {
    // Determine which video to target
    const isVideoA = videoLabel.endsWith('A');
    const videoData = isVideoA ? videoA : videoB;
    
    // Only YouTube supports this simple iframe seek method
    if (videoData?.platform !== 'youtube') return;

    // Parse MM:SS to seconds
    const [mins, secs] = timestamp.split(':').map(Number);
    const totalSeconds = mins * 60 + secs;

    // Find the iframe added in AnalyticalHeader.tsx
    const iframeId = `yt-embed-video-${isVideoA ? 'a' : 'b'}`;
    const iframe = document.getElementById(iframeId) as HTMLIFrameElement;
    
    if (iframe && iframe.src) {
      // Create a URL object to safely modify query params
      const url = new URL(iframe.src);
      url.searchParams.set('start', totalSeconds.toString());
      url.searchParams.set('autoplay', '1');
      // Updating the src forces the iframe to reload at the specified timestamp
      iframe.src = url.toString();
    }
  };

  // Recursively process React node tree, replacing citation text with styled badges.
  // This handles citations that appear inside bold, italic, code, or other inline elements.
  const processCitationsInNode = (node: React.ReactNode, keyPrefix: string): React.ReactNode => {
    if (typeof node === 'string') {
      return parseCitations(node, keyPrefix);
    }
    if (Array.isArray(node)) {
      return node.map((child, i) => {
        const processed = processCitationsInNode(child, `${keyPrefix}-${i}`);
        if (React.isValidElement(processed) && !processed.key) {
          return React.cloneElement(processed, { key: `${keyPrefix}-${i}` } as React.Attributes);
        }
        return processed;
      });
    }
    if (React.isValidElement(node)) {
      const el = node as React.ReactElement<{ children?: React.ReactNode }>;
      const newChildren = processCitationsInNode(el.props.children, keyPrefix);
      return React.cloneElement(el, { key: el.key || keyPrefix } as React.Attributes, newChildren);
    }
    return node;
  };

  // Custom parser to format citations like [Video A @ 01:24] or [Video B @ 00:15] into premium badges.
  // Returns an array of strings and JSX elements (badges).
  const parseCitations = (text: string, keyPrefix: string = 'cit'): React.ReactNode => {
    const citationRegex = /\[(Video [AB])\s*@\s*(\d{1,2}:\d{2})\]/g;

    if (!citationRegex.test(text)) return text;
    citationRegex.lastIndex = 0;

    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = citationRegex.exec(text)) !== null) {
      const startIndex = match.index;
      if (startIndex > lastIndex) {
        parts.push(text.substring(lastIndex, startIndex));
      }

      const videoLabel = match[1]; // "Video A" or "Video B"
      const timestamp = match[2];  // "01:24"
      const isVideoA = videoLabel.endsWith('A');

      parts.push(
        <span
          key={`${keyPrefix}-${startIndex}`}
          onClick={() => seekVideo(videoLabel, timestamp)}
          className={`inline-flex items-center gap-1 px-2 py-0.5 mx-1 text-[10px] uppercase font-black tracking-widest rounded-md border cursor-pointer select-none transition-all hover:scale-105 duration-200 ${isVideoA
            ? 'bg-sky-500/10 text-sky-300 border-sky-500/30 hover:bg-sky-500/20'
            : 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/20'
            }`}
          title={`Click to jump to ${videoLabel} at ${timestamp}`}
        >
          <PlayCircle className="w-3 h-3 text-sky-400" />
          {videoLabel} @ {timestamp}
        </span>
      );

      lastIndex = citationRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length === 1 ? parts[0] : parts;
  };

  // Helper component to render markdown with support for inline citations in all contexts
  const MarkdownRenderer = ({ content }: { content: string }) => {
    return (
      <ReactMarkdown
        components={{
          p: ({ children }) => (
            <p className="mb-4 last:mb-0 leading-relaxed text-zinc-300 text-sm whitespace-pre-wrap">
              {processCitationsInNode(children, 'p')}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-bold text-zinc-100">{children}</strong>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed text-zinc-300 text-sm">
              {processCitationsInNode(children, 'li')}
            </li>
          ),
          h1: ({ children }) => <h1 className="text-xl font-bold text-white mt-4 mb-2 first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-bold text-white mt-3 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-md font-bold text-white mt-2 mb-1">{children}</h3>,
          code: ({ children }) => (
            <code className="bg-zinc-950 px-1.5 py-0.5 rounded text-[10px] tracking-wider text-sky-400 font-mono border border-zinc-800">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="bg-zinc-950 p-4 rounded-xl text-xs text-zinc-300 font-mono border border-zinc-850 overflow-x-auto my-3">
              {children}
            </pre>
          )
        }}
      >
        {content}
      </ReactMarkdown>
    );
  };


  return (
    <div className="flex flex-col h-[70vh] md:h-[600px] border border-zinc-800 rounded-2xl bg-zinc-900/40 backdrop-blur-md overflow-hidden shadow-2xl animate-fade-in-up delay-200">
      {/* Console Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/60">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <h2 className="text-sm font-semibold text-white tracking-wide">Content RAG Chatbot</h2>
        </div>
        <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-500">Active Session</span>
      </div>

      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-6 space-y-6"
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-sm mx-auto gap-5">
            <Bot className="w-10 h-10 text-sky-500 mb-1 stroke-[1.5]" />
            <div>
              <h3 className="text-md font-bold text-white mb-1">Ask the Content RAG Chatbot</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Ingest two videos above, then tap a question or type your own.
              </p>
            </div>
          </div>
        ) : (
          messages
            .filter(msg => msg.content !== "Start Comparative Analysis Audit")
            .map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-4 max-w-3xl animate-slide-up ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''
                  }`}
              >
                {/* Avatar */}
                <div
                  className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center border ${msg.role === 'user'
                    ? 'bg-zinc-800 border-zinc-700 text-zinc-200'
                    : 'bg-sky-500/10 border-sky-500/20 text-sky-400'
                    }`}
                >
                  {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Bubble */}
                <div
                  className={`flex-1 p-4 rounded-2xl border ${msg.role === 'user'
                    ? 'bg-zinc-800/40 border-zinc-700/50 text-zinc-200 rounded-tr-none'
                    : 'bg-zinc-900/40 border-zinc-800 text-zinc-300 rounded-tl-none'
                    }`}
                >
                  <MarkdownRenderer content={msg.content} />
                </div>
              </div>
            ))
        )}

        {/* Quick prompt chips - shown when chat is empty or just has the initial audit */}
        {messages.length <= 2 && !disabled && (
          <div className="flex flex-col gap-2 w-full max-w-3xl animate-fade-in-up delay-300">
            <div className="flex items-center gap-1.5 justify-center mb-2 mt-4">
              <Zap className="w-3 h-3 text-sky-400" />
              <span className="text-[10px] font-black uppercase tracking-widest text-sky-400">Quick Prompts</span>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {dynamicPrompts.map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => {
                    // Call onSendMessage directly with the prompt text as an override,
                    // bypassing the React state update cycle entirely — no race condition.
                    const syntheticEvent = { preventDefault: () => {} } as React.FormEvent;
                    onSendMessage(syntheticEvent, prompt);
                  }}
                  disabled={isLoading}
                  className="text-left flex-1 min-w-[250px] px-3 py-2.5 rounded-xl bg-zinc-900/60 border border-zinc-800 hover:border-sky-500/40 hover:bg-zinc-900 text-xs text-zinc-300 hover:text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {isLoading && (
          <div className="flex gap-4 max-w-3xl">
            <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center border bg-sky-500/10 border-sky-500/20 text-sky-400">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
            <div className="flex-1 p-4 rounded-2xl border bg-zinc-900/40 border-zinc-800 text-zinc-400 rounded-tl-none flex items-center gap-2">
              <span className="text-xs">Analyzing vector space & typing response</span>
              <span className="flex gap-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-650 animate-bounce delay-100" />
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-650 animate-bounce delay-200" />
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-650 animate-bounce delay-300" />
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input Console */}
      <form id="chat-form" onSubmit={onSendMessage} className="p-4 border-t border-zinc-800 bg-zinc-950/60">
        <div className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={disabled || isLoading}
            placeholder={
              disabled
                ? 'Ingest video URLs first to start chatting'
                : 'Ask: "Why did Video A outperform B?" or "Compare the hooks..."'
            }
            className="w-full h-12 pl-4 pr-12 rounded-xl bg-zinc-900/80 border border-zinc-800 focus:border-sky-500 focus:ring-1 focus:ring-sky-500 focus:shadow-[0_0_20px_rgba(56,189,248,0.15)] focus:outline-none text-sm text-zinc-100 placeholder-zinc-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          />
          <button
            type="submit"
            disabled={disabled || isLoading || !input.trim()}
            className="absolute right-2 p-2 rounded-lg bg-sky-500 text-[#09111E] hover:bg-sky-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
