'use client';

import React, { useState, useEffect } from 'react';
import { ArrowRight, AlertCircle, RefreshCw, BarChart3, Search, Sparkles, Wand2 } from 'lucide-react';
import ChatConsole, { ChatMessage } from '../components/ChatConsole';
import AnalyticalHeader, { VideoData } from '../components/AnalyticalHeader';
import MultiModalMockup from '../components/MultiModalMockup';
import ScriptRewriterAccordion from '../components/ScriptRewriterAccordion';

export default function Home() {
  const [urlA, setUrlA] = useState('');
  const [urlB, setUrlB] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMockAnalysis, setIsMockAnalysis] = useState(false);
  
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
    setIsMockAnalysis(false);
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
      setIsMockAnalysis(data.is_mock_analysis || false);
      
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
        <div className="flex items-center gap-3 text-xs font-semibold text-zinc-400">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-9 h-9 text-[#00B2FF] stroke-current stroke-[3]"><path d="M21 12C21 16.9706 16.9706 21 12 21C9.69494 21 7.59227 20.1334 6 18.7083L3 21L5.29168 18C3.86656 16.4077 3 14.3051 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z"/></svg>
          <div>
            <h1 className="text-lg font-black tracking-widest uppercase text-white">
              CJ <span className="text-[10px] px-2 py-0.5 ml-1.5 font-bold border border-[#00B2FF]/30 rounded-full bg-[#00B2FF]/10 text-[#00B2FF] align-middle">REPLICA</span>
            </h1>
            <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest mt-0.5">Viral Social Content RAG Chatbot</p>
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
        <section className="bg-[#0D182A]/80 border border-white/5 rounded-3xl p-6 md:p-10 backdrop-blur-xl shadow-2xl animate-fade-in-up">
          <div className="max-w-4xl mb-10 text-center mx-auto">
            <div className="inline-block px-4 py-1.5 mb-8 rounded-full bg-[#11223B] border border-sky-900/50 text-[10px] font-bold tracking-widest text-sky-400 uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400 inline-block mr-2 align-middle"></span>
              2026 UPDATE: RAG CHATBOT ENGINE NOW LIVE
            </div>
            <h2 className="text-4xl md:text-6xl lg:text-7xl font-black text-white mb-6 tracking-tighter uppercase leading-[0.9]">
              Audit Social Video<br/><span className="text-sky-400">Performance.</span>
            </h2>
            <p className="text-sm md:text-base font-semibold text-zinc-400 max-w-2xl mx-auto">
              Input two video URLs below. Supports YouTube, Instagram Reels, and TikTok. Our scraping service extracts the raw transcripts and engagement rates, indexes the semantic segments, and loads the script doctor state machine.
            </p>
          </div>

          <form onSubmit={handleIngest} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* URL A Field */}
              <div className="flex flex-col gap-2 group">
                <label className="text-[10px] font-black uppercase tracking-widest text-sky-400 group-focus-within:text-sky-300 transition-colors">Video A (Control URL)</label>
                <input
                  type="url"
                  required
                  placeholder="https://www.youtube.com/... or https://www.instagram.com/reel/..."
                  value={urlA}
                  onChange={(e) => setUrlA(e.target.value)}
                  disabled={isLoading}
                  className="h-14 px-5 rounded-2xl bg-[#09111E] border border-white/10 focus:border-sky-500 focus:ring-1 focus:ring-sky-500 focus:outline-none text-sm placeholder-zinc-600 text-zinc-200 transition-all hover:bg-[#0A1322] hover:border-white/20"
                />
              </div>

              {/* URL B Field */}
              <div className="flex flex-col gap-2 group">
                <label className="text-[10px] font-black uppercase tracking-widest text-cyan-400 group-focus-within:text-cyan-300 transition-colors">Video B (Competitor/Variant URL)</label>
                <input
                  type="url"
                  required
                  placeholder="https://www.youtube.com/... or https://www.instagram.com/reel/..."
                  value={urlB}
                  onChange={(e) => setUrlB(e.target.value)}
                  disabled={isLoading}
                  className="h-14 px-5 rounded-2xl bg-[#09111E] border border-white/10 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none text-sm placeholder-zinc-600 text-zinc-200 transition-all hover:bg-[#0A1322] hover:border-white/20"
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="flex justify-center mt-8">
              <button
                type="submit"
                disabled={isLoading}
                className="w-full md:w-auto h-14 px-10 rounded-full bg-gradient-to-r from-sky-400 to-cyan-500 hover:from-sky-300 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-black tracking-widest text-[#09111E] uppercase shadow-[0_0_30px_rgba(56,189,248,0.3)] hover:shadow-[0_0_40px_rgba(56,189,248,0.5)] flex items-center justify-center gap-3 transition-all hover:-translate-y-0.5 active:translate-y-0"
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
            </div>
          </form>
        </section>

        {/* Analytics Workspace Dashboard */}
        {(videoA || videoB || isLoading) && (
          <section className="space-y-8 animate-fade-in-up delay-150">
            {/* Mock analysis banner */}
            {isMockAnalysis && (
              <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <div>
                  <strong>AI Fallback Mode Active</strong> — The Gemini API rate limit was reached (free tier: 20 req/day). The initial hook audit and chat responses are using an intelligent rule-based fallback instead of live AI. Wait ~1 minute and re-submit to get a real AI analysis.
                </div>
              </div>
            )}
            {/* KPI metrics comparison */}
            <AnalyticalHeader videoA={videoA} videoB={videoB} />

            {/* Split Screen Chat / Details */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Left Column: Diagnostics Information */}
              <div className="lg:col-span-5 space-y-6">
                <div className="p-6 rounded-3xl bg-[#0D182A]/80 border border-white/5 h-full flex flex-col">
                  <h3 className="text-[10px] font-black uppercase tracking-widest text-sky-400 mb-6 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-sky-400" />
                    Doctor's Diagnostics Summary
                  </h3>
                  
                  {isLoading ? (
                    <div className="flex-1 flex flex-col items-center justify-center py-12 text-center text-zinc-500">
                      <RefreshCw className="w-8 h-8 animate-spin mb-3 text-indigo-500" />
                      <p className="text-sm font-medium">Assembling RAG Context & Chunking...</p>
                    </div>
                  ) : (
                    <div className="flex-1 space-y-6 text-sm text-zinc-300">
                      <div className="p-5 rounded-2xl bg-[#09111E] border border-white/5">
                        <h4 className="text-[10px] font-black text-sky-400 mb-2 uppercase tracking-widest">Isolated Hook Diagnostics</h4>
                        <p className="text-xs leading-relaxed text-zinc-400">
                          The first 15 seconds have been isolated into a high-priority context block. Ask the Content RAG Chatbot specifically about the hook pacing or curiosity loops to get instant feedback.
                        </p>
                      </div>

                      <div className="p-5 rounded-2xl bg-[#09111E] border border-white/5">
                        <h4 className="text-[10px] font-black text-cyan-400 mb-2 uppercase tracking-widest">RAG Optimization Parameters</h4>
                        <p className="text-xs leading-relaxed text-zinc-400">
                          Transcripts were divided into semantic blocks of 350 words (~450-500 tokens) with a 10% overlap and indexed in ChromaDB (3072-dim Google Embeddings). The chatbot retrieves 6 chunks (~2,800-3,000 tokens) per query. Conversation memory checkpointer is active.
                        </p>
                      </div>

                      <div className="p-5 rounded-2xl bg-[#09111E] border border-white/5">
                        <h4 className="text-[10px] font-black text-emerald-400 mb-2 uppercase tracking-widest">Scraper Integrity</h4>
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

            {/* Multi-Modal Pro Feature Mockup */}
            <MultiModalMockup />

            {/* Script Rewriter Integration Accordion */}
            <ScriptRewriterAccordion originalText={videoA?.transcript?.[0]?.text || ""} />

            <div className="pb-8"></div>
          </section>
        )}
      </main>
    </div>
  );
}
