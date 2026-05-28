import React, { useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, PlayCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatConsoleProps {
  messages: ChatMessage[];
  input: string;
  setInput: (val: string) => void;
  onSendMessage: (e: React.FormEvent) => void;
  isLoading: boolean;
  disabled: boolean;
}

export default function ChatConsole({
  messages,
  input,
  setInput,
  onSendMessage,
  isLoading,
  disabled
}: ChatConsoleProps) {
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Custom parser to format citations like [Video A @ 01:24] or [Video B @ 00:15] into premium badges
  const parseCitations = (text: string) => {
    const citationRegex = /\[(Video [A|B])\s*@\s*(\d{1,2}:\d{2})\]/g;

    // Check if there are matches. If not, just return text.
    if (!citationRegex.test(text)) return text;

    // Reset regex index
    citationRegex.lastIndex = 0;

    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = citationRegex.exec(text)) !== null) {
      const startIndex = match.index;
      // Add text before match
      if (startIndex > lastIndex) {
        parts.push(text.substring(lastIndex, startIndex));
      }

      const videoLabel = match[1]; // "Video A" or "Video B"
      const timestamp = match[2];  // "01:24"
      const isVideoA = videoLabel.endsWith('A');

      parts.push(
        <span
          key={startIndex}
          className={`inline-flex items-center gap-1 px-2 py-0.5 mx-1 text-[10px] uppercase font-black tracking-widest rounded-md border cursor-pointer select-none transition-all hover:scale-105 duration-200 ${isVideoA
            ? 'bg-sky-500/10 text-sky-300 border-sky-500/30 hover:bg-sky-500/20'
            : 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/20'
            }`}
          title={`Jump to ${videoLabel} at ${timestamp}`}
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

    return parts;
  };

  // Helper component to render markdown with support for inline citations
  const MarkdownRenderer = ({ content }: { content: string }) => {
    return (
      <ReactMarkdown
        components={{
          p: ({ children }) => {
            if (typeof children === 'string') {
              return <p className="mb-3 last:mb-0 leading-relaxed text-zinc-300 text-sm">{parseCitations(children)}</p>;
            }
            return <p className="mb-3 last:mb-0 leading-relaxed text-zinc-300 text-sm">{children}</p>;
          },
          li: ({ children }) => {
            if (typeof children === 'string') {
              return <li className="leading-relaxed text-zinc-300 text-sm">{parseCitations(children)}</li>;
            }
            return <li className="leading-relaxed text-zinc-300 text-sm">{children}</li>;
          },
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

      {/* Messages Console */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-sm mx-auto">
            <Bot className="w-10 h-10 text-sky-500 mb-4 stroke-[1.5]" />
            <h3 className="text-md font-bold text-white mb-2">Ask the Content RAG Chatbot</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Compare the hooks, pacing, retention triggers, and structure. Ask anything about how Video A compares to Video B.
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => (
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
        <div ref={chatEndRef} />
      </div>

      {/* Input Console */}
      <form onSubmit={onSendMessage} className="p-4 border-t border-zinc-800 bg-zinc-950/60">
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
