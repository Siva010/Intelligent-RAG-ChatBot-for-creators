# Viral Script Doctor & RAG Intelligence Engine

Precisely designed production-grade RAG (Retrieval-Augmented Generation) application built to compare social media video transcripts and performance metrics, isolate viral hook psychology, and support memory-aware conversations with grounded-citations.

---

## 🏗️ System Architecture

The application is decoupled into a fast, async **FastAPI** backend and a premium dark-themed **Next.js** dashboard.

```
[ Next.js Frontend (Tailwind) ]
               │
      (HTTP / SSE Stream)
               │
               ▼
   [ FastAPI Backend (Python) ] ◄──► [ MemoryCache (TTL/Size Limit) ]
               │
      ┌────────┴──────────────────────────┐
      ▼                                   ▼
[Scrapers / APIs]                 [LangGraph Agent] ◄──► [MemorySaver Checkpointer]
 - yt-dlp                           - State graph
 - youtube-transcript-api           - Prompt engineering
 - Whisper fallback stub            - Vector database router tool
                                          │
                                          ▼
                              [Vector DB: Chroma / NumPy Fallback]
                              - Hook isolation (first 15s)
                              - Semantic chunking (350 words, 10% overlap)
                              - 3072-dim Google Embeddings
                              - Server-Sent Events (SSE) Streaming
```

---

## 🛠️ Step-by-Step Installation & Run Guide

### Prerequisites
- Python 3.13+
- Node.js 20+ & npm

### Backend Setup
1. Open a terminal, navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Activate the python virtual environment:
   - **Windows**: `.\venv\Scripts\activate`
   - **macOS/Linux**: `source venv/bin/activate`
3. Create a `.env` file in the `backend/` directory and configure your Google Gemini API Key (optional; fallbacks to high-fidelity mock engines if no key is provided):
   ```env
   GOOGLE_API_KEY=your_google_ai_studio_api_key_here
   ```
4. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   The backend will be available at `http://127.0.0.1:8000`. Swagger documentation can be viewed at `http://127.0.0.1:8000/docs`.

### Frontend Setup
1. Open a new terminal, navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Start the Next.js dev server:
   ```bash
   npm run dev
   ```
   The frontend dashboard will be running at `http://localhost:3000`.

---

## 📈 10,000+ Creators Daily Scalability Roadmap

To scale this application from a local demo to supporting 10,000+ creators daily with elite performance and cost efficiency, we propose the following production roadmap:

### 1. Cost & Context Window Optimization
- **Caching Tier**: Transition from in-memory dictionary to a dedicated **Redis** cluster with a 24-hour TTL keyed by hashed video URLs. Ingested data is served instantly, dropping API/Scraper bills to zero for repeat audits.
- **Model Tiering**: Route simple semantic retrieval queries and hook comparison requests to fast, cost-efficient models (e.g., `gemini-2.5-flash`). Escalate to larger models (e.g., `gemini-2.5-pro`) only when complex script rewriting or psychological pacing improvements are requested.
- **Strict Vector Routing & Chat State**: Instead of sending the full transcript of two 20-minute videos (30k+ tokens) into the context window, the LangGraph setup uses a vector database to fetch only the top 6 semantic transcript blocks (approx 3,000 tokens) alongside a normalized metrics JSON. Our conditional state routing allows the chat agent to answer dynamically without restarting the graph pipeline.

### 2. Distributed Vector Compute
- **Hosted Vector DB**: Migrate from local ChromaDB to a hosted, auto-scaling vector database such as **Pinecone** (serverless) or **Milvus**. 
- **Partitioning**: Shard collections by creator ID or organization namespace to restrict search indexes, accelerating queries and preventing cross-tenant leakage.

### 3. Scraping & Pipeline Resiliency
- **Asynchronous Worker Queue**: Re-scrape and download operations are slow and error-prone. We will offload scraping to a **Celery** or **Argo Workflows** runner pool backed by **RabbitMQ**. The FastAPI API returns a task ID, and the frontend polls or listens to a WebSocket for completion.
- **Proxy Rotation**: Integrate proxies (e.g. ScrapeOps or Bright Data) inside `yt-dlp` headers to bypass rate limits and anti-bot captchas on YouTube, TikTok, and Instagram Reels.
- **Audio Whisper Pipelines**: Host an auto-scaling Whisper endpoint on serverless GPU containers (e.g., RunPod or Replicate) to transcribe videos that lack closed captions.

### 4. Infrastructure & Hosting
- **Serverless Backend**: Deploy the FastAPI backend on containerized auto-scaling runners (AWS ECS/Fargate or GCP Cloud Run) configured to scale out when HTTP request queues spike.
- **Global Edge Delivery**: Host the Next.js frontend on **Vercel** or behind **CloudFront CDN** for instant edge rendering of UI code.
