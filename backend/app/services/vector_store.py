import logging
import uuid
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding Mode Detection
# We tag each ChromaDB collection with which embedding model was used.
# If the tag changes (e.g. from "mock" to "google"), we auto-wipe and re-index.
# ---------------------------------------------------------------------------
EMBEDDING_MODE_METADATA_KEY = "__embedding_mode__"

def _current_embedding_mode() -> str:
    """Returns a string identifier for the currently active embedding backend."""
    if settings.google_api_key:
        return "google-gemini-embedding-001"
    if settings.openai_api_key:
        return "openai-text-embedding-3-small"
    return "mock"


# ---------------------------------------------------------------------------
# Fallback vector store (in-memory, keyword overlap) — used when ChromaDB
# is not installed or fails to initialise.
# ---------------------------------------------------------------------------
class SimpleVectorStore:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        logger.info("Initialized Simple In-Memory Vector Store Fallback")

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        for text, meta, doc_id in zip(texts, metadatas, ids):
            self.documents.append({"id": doc_id, "text": text, "metadata": meta})
        logger.info(f"Added {len(texts)} documents to Simple Vector Store")

    def query(self, query_text: str, n_results: int = 6, video_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Simple word-overlap similarity search (TF-style), optionally filtered by video_ids."""
        query_words = set(query_text.lower().split())
        scored_docs = []
        for doc in self.documents:
            # Apply video_id filter if provided — mirrors the ChromaDB code path
            if video_ids and doc["metadata"].get("video_id") not in video_ids:
                continue
            doc_words = doc["text"].lower().split()
            intersection = query_words.intersection(set(doc_words))
            score = len(intersection) / (len(query_words) + 1e-5)
            for word in query_words:
                score += doc["text"].lower().count(word) * 0.05
            scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored_docs[:n_results]

        return {
            "ids": [[doc["id"] for _, doc in top_docs]],
            "documents": [[doc["text"] for _, doc in top_docs]],
            "metadatas": [[doc["metadata"] for _, doc in top_docs]],
        }


# ---------------------------------------------------------------------------
# Try to import Pinecone; fall back to SimpleVectorStore if unavailable
PINECONE_AVAILABLE = False
try:
    from pinecone import Pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    logger.warning("pinecone-client not installed. Falling back to SimpleVectorStore.")


# ---------------------------------------------------------------------------
# VectorStoreManager
# ---------------------------------------------------------------------------
class VectorStoreManager:
    def __init__(self):
        self.pinecone_client: Any = None
        self.index: Any = None
        self.simple_store: Optional[SimpleVectorStore] = None
        
        # We don't wipe pinecone automatically as it's a shared stateful resource
        
        if PINECONE_AVAILABLE and settings.pinecone_api_key:
            try:
                self.pinecone_client = Pinecone(api_key=settings.pinecone_api_key)
                self.index = self.pinecone_client.Index(settings.pinecone_index_name)
                logger.info(f"Pinecone initialised targeting index: {settings.pinecone_index_name}")
            except Exception as e:
                logger.error(f"Failed to initialise Pinecone: {e}. Falling back to SimpleVectorStore.")
                self.simple_store = SimpleVectorStore()
        else:
            self.simple_store = SimpleVectorStore()

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Returns dense vector embeddings for a list of texts.
        Priority:
          1. Google text-embedding-004 (uses existing GOOGLE_API_KEY)
          2. OpenAI text-embedding-3-small (uses OPENAI_API_KEY)
          3. Mock deterministic random vectors (dev fallback only)
        """
        # Helper for Tenacity exponential backoff on 429s
        def _is_429(e: Exception) -> bool:
            return "429" in str(e)

        # 1. Google Embeddings (preferred — uses the new google-genai SDK)
        if settings.google_api_key:
            try:
                from google import genai as google_genai
                from google.genai import types as genai_types
                client = google_genai.Client(api_key=settings.google_api_key)
                
                @retry(
                    wait=wait_exponential(multiplier=1, min=2, max=60),
                    stop=stop_after_attempt(6),
                    retry=retry_if_exception(_is_429),
                    reraise=True
                )
                def _do_embed(text: str):
                    return client.models.embed_content(
                        model="gemini-embedding-001",
                        contents=text,
                        config=genai_types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT"
                        ),
                    )

                EMBED_DIM = 3072
                embeddings = []
                for text in texts:
                    stripped = text.strip() if text else ""
                    if not stripped:
                        # Use a zero vector for empty/whitespace chunks
                        embeddings.append([0.0] * EMBED_DIM)
                        logger.warning("Skipped empty chunk — inserted zero vector placeholder.")
                        continue
                        
                    response = _do_embed(stripped)
                    emb: list[float] = (response.embeddings[0].values if response.embeddings else None) or [0.0] * EMBED_DIM
                    embeddings.append(emb)

                logger.debug(f"Google embeddings generated for {len(texts)} texts")
                return embeddings
            except Exception as e:
                logger.error(f"Google Embeddings error: {e}. Trying OpenAI fallback.")

        # 2. OpenAI Embeddings
        if settings.openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.openai_api_key)
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts,
                )
                return [data.embedding for data in response.data]
            except Exception as e:
                logger.error(f"OpenAI Embeddings error: {e}. Falling back to mock embeddings.")

        # 3. Mock / deterministic random vectors (dev/test only — semantic search won't work)
        logger.warning(
            "Using MOCK embeddings — semantic search will not reflect actual meaning. "
            "Set GOOGLE_API_KEY or OPENAI_API_KEY for real retrieval."
        )
        embeddings = []
        for text in texts:
            seed = hash(text) % (2**32 - 1)
            rng = np.random.default_rng(seed)
            # Must match the real Google gemini-embedding-001 output dimension (3072).
            # Using a different dimension here would silently fail Pinecone's validation.
            embeddings.append(rng.random(3072).tolist())
        return embeddings

    def get_query_embedding(self, query: str) -> List[List[float]]:
        """
        Returns embeddings for a query string. Uses RETRIEVAL_QUERY task type
        for Google embeddings, which is semantically distinct from doc embeddings
        and improves retrieval quality.
        """
        if settings.google_api_key:
            try:
                from google import genai as google_genai
                from google.genai import types as genai_types
                client = google_genai.Client(api_key=settings.google_api_key)
                response = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=query,
                    config=genai_types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY"
                    ),
                )
                EMBED_DIM = 3072
                emb: list[float] = (response.embeddings[0].values if response.embeddings else None) or [0.0] * EMBED_DIM
                embeddings = [emb]
                return embeddings
            except Exception as e:
                logger.error(f"Google query embedding error: {e}. Falling back to get_embeddings.")

        # Fallback: use the same method as doc embeddings
        return self.get_embeddings([query])

    # ------------------------------------------------------------------
    # Transcript helpers
    # ------------------------------------------------------------------
    def isolate_hooks(self, transcript: List[Dict[str, Any]]) -> str:
        """Extracts the first 15 seconds of a transcript as a single string.
        Uses a filter (not break) so unsorted transcripts are handled correctly.
        """
        hook_texts = [
            entry.get("text", "")
            for entry in transcript
            if entry.get("start", 0.0) < 15.0
        ]
        return " ".join(hook_texts)

    def chunk_transcript(
        self, transcript: List[Dict[str, Any]], video_id: str
    ) -> List[Dict[str, Any]]:
        """
        Chunks the transcript into overlapping segments of ~350 words with 10% overlap,
        preserving start timestamps.

        The first 15s (hook) is always included as a dedicated high-priority chunk
        tagged with `is_hook=True` in metadata. The body (>=15s) is then chunked
        into overlapping 350-word segments.
        """
        chunks = []

        # --- Hook chunk (first 15 seconds) ---
        hook_entries = [e for e in transcript if e.get("start", 0.0) < 15.0]
        if hook_entries:
            hook_text = " ".join(e.get("text", "") for e in hook_entries).strip()
            if hook_text:
                chunks.append({
                    "video_id": video_id,
                    "start": 0.0,
                    "text": hook_text,
                    "is_hook": True,
                })

        # --- Body chunks (>= 15 seconds) ---
        remaining_entries = [
            entry for entry in transcript if entry.get("start", 0.0) >= 15.0
        ]
        if not remaining_entries:
            return chunks

        words_buffer: List[str] = []
        start_time = remaining_entries[0].get("start", 15.0)

        target_words = 350
        overlap_words = int(target_words * 0.10)  # 35 words overlap

        entries_in_chunk = []

        for entry in remaining_entries:
            entry_words = entry.get("text", "").split()
            if not entry_words:
                continue

            if not words_buffer:
                start_time = entry.get("start", 15.0)

            words_buffer.extend(entry_words)
            entries_in_chunk.append(entry)

            while len(words_buffer) >= target_words:
                chunk_words = words_buffer[:target_words]
                chunk_text = " ".join(chunk_words)
                chunks.append({"video_id": video_id, "start": start_time, "text": chunk_text, "is_hook": False})

                words_buffer = words_buffer[target_words - overlap_words:]

                if entries_in_chunk:
                    consumed_word_count = target_words - overlap_words
                    running_count = 0
                    keep_index = 0
                    for idx, ent in enumerate(entries_in_chunk):
                        running_count += len(ent.get("text", "").split())
                        if running_count > consumed_word_count:
                            keep_index = idx
                            break
                    entries_in_chunk = entries_in_chunk[keep_index:]
                    if entries_in_chunk:
                        start_time = entries_in_chunk[0].get("start", start_time)

        if words_buffer:
            chunks.append({
                "video_id": video_id,
                "start": start_time,
                "text": " ".join(words_buffer),
                "is_hook": False,
            })

        return chunks


    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def index_transcript(
        self, video_id: str, transcript: List[Dict[str, Any]]
    ) -> None:
        """Chunks the transcript and upserts it into the vector database."""
        chunks = self.chunk_transcript(transcript, video_id)
        if not chunks:
            logger.info(f"No chunks to index for video {video_id}")
            return

        texts = [c["text"] for c in chunks]
        embedding_mode = _current_embedding_mode()
        metadatas = [
            {
                "video_id": c["video_id"],
                "start_time": c["start"],
                "is_hook": c.get("is_hook", False),
                EMBEDDING_MODE_METADATA_KEY: embedding_mode,
            }
            for c in chunks
        ]
        ids = [f"{video_id}_chunk_{i}" for i in range(len(chunks))]

        logger.info(
            f"Indexing {len(chunks)} chunks for video {video_id} "
            f"using embedding mode: {embedding_mode}"
        )

        if self.simple_store:
            self.simple_store.add_documents(texts, metadatas, ids)
        else:
            try:
                embeddings = self.get_embeddings(texts)
                
                # Dimension validation
                if embeddings:
                    expected_dim = None
                    try:
                        stats = self.index.describe_index_stats()
                        expected_dim = stats.get("dimension")
                    except Exception as stats_e:
                        logger.warning(f"Could not fetch Pinecone index stats: {stats_e}")
                        
                    actual_dim = len(embeddings[0])
                    if expected_dim and actual_dim != expected_dim:
                        err_msg = f"Embedding dimension mismatch: Pinecone index expects {expected_dim}-dim, but embeddings are {actual_dim}-dim."
                        logger.error(err_msg)
                        raise ValueError(err_msg)

                # For Pinecone, we must store the text inside the metadata
                vectors_to_upsert = []
                for i in range(len(chunks)):
                    # Merge the text into metadata for Pinecone retrieval
                    meta = metadatas[i].copy()
                    meta["text"] = texts[i]
                    
                    vectors_to_upsert.append({
                        "id": ids[i],
                        "values": embeddings[i],
                        "metadata": meta
                    })
                
                # Upsert to Pinecone
                self.index.upsert(vectors=vectors_to_upsert)
            except Exception as e:
                logger.error(f"Pinecone upsert failed: {e}. Falling back to simple store.")
                if not self.simple_store:
                    self.simple_store = SimpleVectorStore()
                self.simple_store.add_documents(texts, metadatas, ids)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------
    def query_vector_store(
        self, query: str, video_ids: List[str], n_results: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Semantically searches the vector store for chunks relevant to `query`,
        filtering results to only the specified `video_ids`.
        Returns up to `n_results` matched chunks, sorted by relevance.
        """
        logger.info(f"Querying vector store: '{query[:80]}' for videos {video_ids}")
        results = []

        if self.simple_store:
            raw_results = self.simple_store.query(query, n_results=n_results * 3, video_ids=video_ids)
            
            if raw_results and "documents" in raw_results and raw_results["documents"]:
                docs = raw_results["documents"][0]
                metas = raw_results["metadatas"][0]

                for doc, meta in zip(docs, metas):
                    if meta and meta.get("video_id") in video_ids:
                        results.append({
                            "text": doc,
                            "video_id": meta.get("video_id"),
                            "start_time": meta.get("start_time"),
                        })
                        if len(results) >= n_results:
                            break
        else:
            try:
                query_embeddings = self.get_query_embedding(query)
                
                # Pinecone query
                response = self.index.query(
                    vector=query_embeddings[0],
                    top_k=n_results * 2,  # Fetch extra to be safe
                    filter={"video_id": {"$in": video_ids}},
                    include_metadata=True
                )
                
                for match in response.matches:
                    meta = match.metadata
                    if meta:
                        results.append({
                            "text": meta.get("text", ""),
                            "video_id": meta.get("video_id"),
                            "start_time": meta.get("start_time"),
                        })
                        if len(results) >= n_results:
                            break

            except Exception as e:
                logger.error(f"Pinecone query failed: {e}.")
                if self.simple_store:
                    raw_results = self.simple_store.query(query, n_results=n_results * 3, video_ids=video_ids)
                    if raw_results and "documents" in raw_results and raw_results["documents"]:
                        docs = raw_results["documents"][0]
                        metas = raw_results["metadatas"][0]
                        for doc, meta in zip(docs, metas):
                            if meta and meta.get("video_id") in video_ids:
                                results.append({
                                    "text": doc,
                                    "video_id": meta.get("video_id"),
                                    "start_time": meta.get("start_time"),
                                })
                                if len(results) >= n_results:
                                    break
                else:
                    return []

        logger.info(f"Vector store returned {len(results)} relevant chunks.")
        return results

# Singleton — shared across the entire backend process.
vector_store = VectorStoreManager()
