import logging
import uuid
import numpy as np
from typing import List, Dict, Any, Tuple
from app.config import settings

logger = logging.getLogger(__name__)

# Fallback vector store in case chromadb installation/import fails
class SimpleVectorStore:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        logger.info("Initialized Simple In-Memory Vector Store Fallback")

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        for text, meta, doc_id in zip(texts, metadatas, ids):
            self.documents.append({
                "id": doc_id,
                "text": text,
                "metadata": meta
            })
        logger.info(f"Added {len(texts)} documents to Simple Vector Store")

    def query(self, query_text: str, n_results: int = 3) -> Dict[str, Any]:
        # Simple TF-IDF/Term Match vector similarity simulation for offline/local testing
        # Split query into words
        query_words = set(query_text.lower().split())
        
        scored_docs = []
        for doc in self.documents:
            doc_words = doc["text"].lower().split()
            # Calculate simple word overlap score (intersection over union or frequency)
            intersection = query_words.intersection(set(doc_words))
            score = len(intersection) / (len(query_words) + 1e-5)
            
            # Simple TF frequency boost
            for word in query_words:
                score += doc["text"].lower().count(word) * 0.05
                
            scored_docs.append((score, doc))
            
        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored_docs[:n_results]
        
        return {
            "ids": [[doc["id"] for _, doc in top_docs]],
            "documents": [[doc["text"] for _, doc in top_docs]],
            "metadatas": [[doc["metadata"] for _, doc in top_docs]]
        }

# Try to import chromadb, fall back to SimpleVectorStore if not installed or fails
CHROMA_AVAILABLE = False
try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    logger.warning("chromadb not installed. Falling back to SimpleVectorStore.")

class VectorStoreManager:
    def __init__(self):
        self.chroma_client = None
        self.collection = None
        self.simple_store = None
        self.collection_name = "creatorjoy_replica_chunks"

        if CHROMA_AVAILABLE:
            try:
                # Initialize persistent ChromaDB client
                self.chroma_client = chromadb.PersistentClient(path=settings.chroma_db_dir)
                # Create or get collection
                self.collection = self.chroma_client.get_or_create_collection(
                    name=self.collection_name
                )
                logger.info(f"ChromaDB initialized collection: {self.collection_name}")
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB client: {e}. Falling back to SimpleVectorStore.")
                self.simple_store = SimpleVectorStore()
        else:
            self.simple_store = SimpleVectorStore()

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Check if OpenAI API key is configured
        if settings.openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.openai_api_key)
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts
                )
                return [data.embedding for data in response.data]
            except Exception as e:
                logger.error(f"OpenAI Embeddings error: {e}. Falling back to mock embeddings.")
        
        # Fallback to mock embedding vectors (random float vectors of dimension 1536)
        # We ensure they are deterministic based on text hash to maintain consistent results
        embeddings = []
        for text in texts:
            # Seed based on text hash
            seed = hash(text) % (2**32 - 1)
            rng = np.random.default_rng(seed)
            vector = rng.random(1536).tolist()
            embeddings.append(vector)
        return embeddings

    def isolate_hooks(self, transcript: List[Dict[str, Any]]) -> str:
        """
        Isolates the first 15 seconds of the transcript.
        """
        hook_texts = []
        for entry in transcript:
            if entry.get("start", 0.0) < 15.0:
                hook_texts.append(entry.get("text", ""))
            else:
                break
        return " ".join(hook_texts)

    def chunk_transcript(self, transcript: List[Dict[str, Any]], video_id: str) -> List[Dict[str, Any]]:
        """
        Chunks the transcript (excluding first 15 seconds) into 400-600 tokens (approx. 300-450 words)
        with a 10% overlap, retaining metadata.
        """
        # Filter out hook (first 15 seconds)
        remaining_entries = [entry for entry in transcript if entry.get("start", 0.0) >= 15.0]
        
        if not remaining_entries:
            return []

        chunks = []
        words_buffer: List[str] = []
        start_time = remaining_entries[0].get("start", 15.0)
        
        # Word counts: 300-450 words maps well to 400-600 tokens
        target_words = 350
        overlap_words = int(target_words * 0.10) # 10% overlap (35 words)
        
        entries_in_chunk = []
        
        for entry in remaining_entries:
            entry_words = entry.get("text", "").split()
            if not entry_words:
                continue
                
            # If current buffer is empty, update the start time
            if not words_buffer:
                start_time = entry.get("start", 15.0)
                
            words_buffer.extend(entry_words)
            entries_in_chunk.append(entry)
            
            # When buffer size exceeds target
            while len(words_buffer) >= target_words:
                chunk_words = words_buffer[:target_words]
                chunk_text = " ".join(chunk_words)
                
                chunks.append({
                    "video_id": video_id,
                    "start": start_time,
                    "text": chunk_text
                })
                
                # Apply overlap by keeping the last 'overlap_words' words
                words_buffer = words_buffer[target_words - overlap_words:]
                
                # Find start time for the next overlap chunk
                # Find the entry in entries_in_chunk that contains the new start word
                # Let's estimate it based on entry indexes
                if entries_in_chunk:
                    # Clear out fully consumed entries
                    # Keep entries that overlap
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

        # Add remaining text in buffer as final chunk
        if words_buffer:
            chunks.append({
                "video_id": video_id,
                "start": start_time,
                "text": " ".join(words_buffer)
            })
            
        return chunks

    def index_transcript(self, video_id: str, transcript: List[Dict[str, Any]]) -> None:
        """
        Chunks the transcript and adds it to the vector database.
        """
        chunks = self.chunk_transcript(transcript, video_id)
        if not chunks:
            logger.info(f"No chunks to index for video {video_id}")
            return

        texts = [c["text"] for c in chunks]
        metadatas = [{"video_id": c["video_id"], "start_time": c["start"]} for c in chunks]
        ids = [f"{video_id}_chunk_{i}" for i in range(len(chunks))]

        logger.info(f"Indexing {len(chunks)} chunks for video {video_id}")

        if self.simple_store:
            self.simple_store.add_documents(texts, metadatas, ids)
        else:
            try:
                embeddings = self.get_embeddings(texts)
                self.collection.add(
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids
                )
            except Exception as e:
                logger.error(f"ChromaDB add failed: {e}. Falling back to simple store.")
                if not self.simple_store:
                    self.simple_store = SimpleVectorStore()
                self.simple_store.add_documents(texts, metadatas, ids)

    def query_vector_store(self, query: str, video_ids: List[str], n_results: int = 4) -> List[Dict[str, Any]]:
        """
        Queries the vector store, filtering by video_ids, and returns matched chunks.
        """
        logger.info(f"Querying vector store: '{query}' for videos {video_ids}")
        results = []

        if self.simple_store:
            raw_results = self.simple_store.query(query, n_results=10)
        else:
            try:
                embeddings = self.get_embeddings([query])
                # We filter in-memory because some ChromaDB versions/setups have bugs with where clauses in small datasets
                raw_results = self.collection.query(
                    query_embeddings=embeddings,
                    n_results=15
                )
            except Exception as e:
                logger.error(f"ChromaDB query failed: {e}. Querying simple store.")
                if not self.simple_store:
                    return []
                raw_results = self.simple_store.query(query, n_results=10)

        # Parse and filter by video_ids
        if raw_results and "documents" in raw_results and raw_results["documents"]:
            docs = raw_results["documents"][0]
            metas = raw_results["metadatas"][0]
            
            for doc, meta in zip(docs, metas):
                if meta and meta.get("video_id") in video_ids:
                    results.append({
                        "text": doc,
                        "video_id": meta.get("video_id"),
                        "start_time": meta.get("start_time")
                    })
                    if len(results) >= n_results:
                        break
                        
        return results

# Singleton instance of vector store manager
vector_store = VectorStoreManager()
