'use client';

import React, { useState, useEffect } from 'react';
import { Play, Sparkles, AlertCircle, RefreshCw, BarChart3, HelpCircle } from 'lucide-react';
import AnalyticalHeader, { VideoData } from '../components/AnalyticalHeader';
import ChatConsole, { ChatMessage } from '../components/ChatConsole';

export default function Home() {
  const [urlA, setUrlA] = useState('');
  const [urlB, setUrlB] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Scraped metrics data
  const [videoA, setVideoA] = useState<VideoData | null>(null);
  const [videoB, setVideoB] = useState<VideoData | null>(null);
  
  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);

  // Generate a unique session ID on component mount
  useEffect(() => {
    setSessionId('session_' + Math.random().toString(36).substring(2, 11));
  }, []);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlA || !urlB) {
      setError('Please input both video URLs to compare.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setVideoA(null);
    setVideoB(null);
    setChatMessages([]);

    try {
      const response = await fetch('http://127.0.0.1:8000/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url_a: urlA,
          url_b: urlB,
          session_id: sessionId
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to analyze videos. Check backend logs.');
      }

      const data = await response.json();
      setVideoA(data.video_a);
      setVideoB(data.video_b);
      
      // Load initial chat messages from backend (which includes the hook audit)
      if (data.chat_history) {
        setChatMessages(data.chat_history);
      }
    } catch (err: any) {
      console.error("Ingestion failed: ", err);
      setError(err.message || 'An unexpected error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatLoading) return;

    const userMessageContent = chatInput.trim();
    setChatInput('');
    setIsChatLoading(true);

    // Add user message to UI immediately
    const updatedMessages: ChatMessage[] = [
      ...chatMessages,
      { role: 'user', content: userMessageContent }
    ];
    setChatMessages(updatedMessages);

    try {
      // Establish SSE connection for streaming the AI response
      const response = await fetch('http://127.0.0.1:8000/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessageContent
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message to AI.');
      }

      // Add empty assistant message that we will stream into
      setChatMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantReply = '';

      if (reader) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          // SSE events are formatted as "data: { ... }\n\n"
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6).trim();
              if (dataStr === '[DONE]') {
                break;
              }
              try {
                const parsed = JSON.parse(dataStr);
                if (parsed.chunk) {
                  assistantReply += parsed.chunk;
                  // Update the last message content in the list
                  setChatMessages(prev => {
                    const next = [...prev];
                    if (next.length > 0) {
                      next[next.length - 1] = {
                        role: 'assistant',
                        content: assistantReply
                      };
                    }
                    return next;
                  });
                }
              } catch (e) {
                // Ignore parsing errors for partial/malformed JSON chunks
              }
            }
          }
        }
      }
    } catch (err: any) {
      console.error(err);
      setChatMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${err.message || 'Could not stream response.'}` }
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col selection:bg-indigo-500/30 selection:text-indigo-200">
      {/* Header navbar */}
      <header className="border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-md sticky top-0 z-50 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-tr from-indigo-500 to-purple-500 p-2 rounded-xl shadow-lg shadow-indigo-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
              CreatorJoy <span className="text-xs px-2 py-0.5 ml-1.5 font-medium border border-indigo-500/30 rounded bg-indigo-500/10 text-indigo-400">Replica</span>
            </h1>
            <p className="text-[10px] text-zinc-500 font-medium">Viral YouTube Script Doctor & Data Co-Pilot</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs font-semibold text-zinc-400">
          <a href="#diagnostics" className="hover:text-white transition-colors">Diagnostics</a>
          <a href="#scrapers" className="hover:text-white transition-colors">Integrations</a>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <span className="text-[10px] text-zinc-500 font-mono">v0.1.0-beta</span>
        </div>
      </header>

      {/* Main Workspace Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8 space-y-8">
        
        {/* Input deck */}
        <section className="bg-zinc-900/20 border border-zinc-900 rounded-3xl p-6 md:p-8 backdrop-blur-xl shadow-2xl">
          <div className="max-w-2xl mb-6">
            <h2 className="text-xl font-extrabold text-white mb-2 tracking-tight">Audit Social Video Performance</h2>
            <p className="text-sm text-zinc-400">
              Input two video URLs below. Our scraping service extracts the raw transcripts and engagement rates, indexes the semantic segments, and loads the script doctor state machine.
            </p>
          </div>

          <form onSubmit={handleIngest} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* URL A Field */}
              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold uppercase tracking-wider text-indigo-400">Video A (Control URL)</label>
                <input
                  type="url"
                  required
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={urlA}
                  onChange={(e) => setUrlA(e.target.value)}
                  disabled={isLoading}
                  className="h-12 px-4 rounded-xl bg-zinc-900/50 border border-zinc-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none text-sm placeholder-zinc-655 text-zinc-200 transition-all"
                />
              </div>

              {/* URL B Field */}
              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold uppercase tracking-wider text-purple-400">Video B (Competitor/Variant URL)</label>
                <input
                  type="url"
                  required
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={urlB}
                  onChange={(e) => setUrlB(e.target.value)}
                  disabled={isLoading}
                  className="h-12 px-4 rounded-xl bg-zinc-900/50 border border-zinc-800 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 focus:outline-none text-sm placeholder-zinc-655 text-zinc-200 transition-all"
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full md:w-auto h-12 px-8 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-bold text-white shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 transition-all hover:scale-[1.01]"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Scraping & Indexing Video Transcripts...
                </>
              ) : (
                <>
                  <BarChart3 className="w-4 h-4" />
                  Perform Diagnostic Comparison
                </>
              )}
            </button>
          </form>
        </section>

        {/* Analytics Workspace Dashboard */}
        {(videoA || videoB || isLoading) && (
          <section className="space-y-8 animate-fade-in">
            {/* KPI metrics comparison */}
            <AnalyticalHeader videoA={videoA} videoB={videoB} />

            {/* Split Screen Chat / Details */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Left Column: Diagnostics Information */}
              <div className="lg:col-span-5 space-y-6">
                <div className="p-6 rounded-2xl bg-zinc-900/30 border border-zinc-800 h-full flex flex-col">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400 mb-4 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    Doctor's Diagnostics Summary
                  </h3>
                  
                  {isLoading ? (
                    <div className="flex-1 flex flex-col items-center justify-center py-12 text-center text-zinc-500">
                      <RefreshCw className="w-8 h-8 animate-spin mb-3 text-indigo-500" />
                      <p className="text-sm font-medium">Assembling RAG Context & Chunking...</p>
                    </div>
                  ) : (
                    <div className="flex-1 space-y-6 text-sm text-zinc-300">
                      <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-850">
                        <h4 className="text-xs font-bold text-indigo-400 mb-2 uppercase">Isolated Hook Diagnostics</h4>
                        <p className="text-xs leading-relaxed text-zinc-400">
                          The first 15 seconds have been isolated into a high-priority context block. Ask the Script Doctor specifically about the hook pacing or curiosity loops to get instant feedback.
                        </p>
                      </div>

                      <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-850">
                        <h4 className="text-xs font-bold text-purple-400 mb-2 uppercase">RAG Optimization Parameters</h4>
                        <p className="text-xs leading-relaxed text-zinc-400">
                          Transcripts were divided into semantic blocks of 400-600 tokens with a 10% overlap and indexed in ChromaDB. Conversation memory checkpointer is active.
                        </p>
                      </div>

                      <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-850">
                        <h4 className="text-xs font-bold text-emerald-400 mb-2 uppercase">Scraper Integrity</h4>
                        <div className="flex flex-col gap-2 mt-2">
                          <div className="flex justify-between text-xs">
                            <span className="text-zinc-500">Video A Captions:</span>
                            <span className={videoA?.whisper_stubbed ? 'text-amber-400 font-medium' : 'text-emerald-400 font-medium'}>
                              {videoA?.whisper_stubbed ? 'Whisper Mocked' : 'Scraped Successfully'}
                            </span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-zinc-500">Video B Captions:</span>
                            <span className={videoB?.whisper_stubbed ? 'text-amber-400 font-medium' : 'text-emerald-400 font-medium'}>
                              {videoB?.whisper_stubbed ? 'Whisper Mocked' : 'Scraped Successfully'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Chat Console */}
              <div className="lg:col-span-7">
                <ChatConsole
                  messages={chatMessages}
                  input={chatInput}
                  setInput={setChatInput}
                  onSendMessage={handleSendMessage}
                  isLoading={isChatLoading}
                  disabled={!videoA || !videoB}
                />
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
