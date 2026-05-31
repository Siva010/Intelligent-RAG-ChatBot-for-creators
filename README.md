# Viral Script Doctor & RAG Intelligence Engine

Welcome to the Viral Script Doctor—a production-grade, highly-tuned Retrieval-Augmented Generation (RAG) application. It is designed to act as your ultimate social media strategist. By comparing video transcripts, analyzing performance metrics, and pinpointing the exact psychology behind a viral hook, it helps creators understand why a video succeeds. With memory-aware conversations and grounded, clickable citations, it feels less like a tool and more like having an elite scriptwriter right by your side.

---

## ✨ What's New? (Current State)

We've evolved from a simple local demo to a robust, scalable system that respects your compute resources:
- **Parallel Ingestion**: Sped up data crunching with ThreadPool-based parallel video ingestion.
- **Resilient AI Pipelines**: Granular LLM progress streaming via SSE (Server-Sent Events) with Redis-backed reconnection logic, keeping you updated every step of the way.
- **Smart Resource Management**: If you close your browser tab, our Celery workers immediately halt processing (revoking tasks on disconnect) to save precious compute and LLM credits.
- **Interactive UI**: Citations aren't just text anymore—timestamp badges are now fully clickable and instantly seek to the exact moment in the embedded YouTube iframes.
- **Robust Memory**: We've introduced robust SQLite checkpointer singletons for memory-aware conversational flows, alongside ChromaDB vector fallbacks.

---

## 🏗️ System Architecture

The application is decoupled into a lightning-fast, async **FastAPI** backend and a sleek, premium dark-themed **Next.js** dashboard.

```text
[ Next.js Frontend (Tailwind) ]
               │
      (HTTP / SSE Stream)
               │
               ▼
   [ FastAPI Backend (Python) ] ◄──► [ MemoryCache & Redis SSE ]
               │
      ┌────────┴──────────────────────────┐
      ▼                                   ▼
[Scrapers / APIs]                 [LangGraph Agent] ◄──► [SQLite Checkpointer]
 - yt-dlp                           - State graph
 - youtube-transcript-api           - Prompt engineering
 - Whisper fallback stub            - Vector database router tool
                                          │
                                          ▼
                              [Vector DB: Chroma / NumPy Fallback]
                              - Hook isolation (first 15s)
                              - Semantic chunking (350 words, 10% overlap)
                              - 3072-dim Google Embeddings
```

---

## 🛠️ Getting Started

### Prerequisites
- Python 3.13+
- Node.js 20+ & npm
- (Optional but recommended) Redis for robust SSE stream reconnections.

### Backend Setup
1. Open a terminal, navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Activate the python virtual environment:
   - **Windows**: `.\venv\Scripts\activate`
   - **macOS/Linux**: `source venv/bin/activate`
3. Create a `.env` file in the `backend/` directory and configure your Google Gemini API Key (we also have mock fallbacks if you're just testing the UI):
   ```env
   GOOGLE_API_KEY=your_google_ai_studio_api_key_here
   ```
4. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *Note: For full background processing, ensure your Celery worker is running.*

### Frontend Setup
1. Open a new terminal, navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Start the Next.js dev server:
   ```bash
   npm run dev
   ```
   The frontend dashboard will be waiting for you at `http://localhost:3000`.

---

## 📈 Roadmap for Scale

As we aim to empower 10,000+ creators daily, here is where we are heading next:

### 1. Cost & Context Window Optimization
- **Caching Tier**: Moving from in-memory dictionaries to a dedicated Redis cluster for 24-hour video caching to cut scraper/API costs on repeat audits.
- **Model Tiering**: Using faster models (`gemini-2.5-flash`) for simple retrievals and reserving heavier models (`gemini-2.5-pro`) for complex script rewriting.
- **Strict Vector Routing**: Supplying the LLM with only the most semantically relevant transcript chunks (top 6) to keep the context window small, accurate, and cheap.

### 2. Distributed Infrastructure
- **Hosted Vector DB**: Transitioning to Pinecone or Milvus with tenant partitioning for robust cross-tenant security.
- **Advanced Scraping**: Leveraging Proxy rotation (ScrapeOps/Bright Data) to bypass platform limits, and Serverless Whisper GPU containers (RunPod/Replicate) for robust fallback transcription.
- **Serverless Scaling**: Auto-scaling FastAPI on AWS ECS/Fargate and serving the UI via Vercel for instantaneous global delivery.
