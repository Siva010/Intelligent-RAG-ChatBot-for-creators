import asyncio
import logging
import json
import re as _re
from typing import Annotated, Sequence, TypedDict, Dict, Any, List, Optional
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.sqlite import SqliteSaver
import aiosqlite
import sqlite3
from app.config import settings
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared SQLite checkpoint connection
# ---------------------------------------------------------------------------
# A single aiosqlite connection shared across all requests within the process.
# Opened once at app startup (via init_checkpointer) and closed at shutdown
# (via close_checkpointer). This replaces per-request connect/close calls that
# caused SQLite write-lock contention under concurrent requests.
_sqlite_conn: Optional[aiosqlite.Connection] = None
_checkpointer: Optional[AsyncSqliteSaver] = None


async def init_checkpointer() -> None:
    """Open the shared SQLite connection. Call once at application startup."""
    global _sqlite_conn, _checkpointer
    _sqlite_conn = await aiosqlite.connect("checkpoints.sqlite")
    _checkpointer = AsyncSqliteSaver(_sqlite_conn)
    await _checkpointer.setup()
    logger.info("SQLite checkpoint connection opened (shared).")


async def close_checkpointer() -> None:
    """Close the shared SQLite connection. Call once at application shutdown."""
    global _sqlite_conn, _checkpointer
    if _sqlite_conn:
        await _sqlite_conn.close()
        _sqlite_conn = None
        _checkpointer = None
        logger.info("SQLite checkpoint connection closed.")


def get_checkpointer() -> AsyncSqliteSaver:
    """Return the shared checkpointer. Raises if init_checkpointer() was not called."""
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not initialised. "
            "Ensure init_checkpointer() is called during app startup."
        )
    return _checkpointer


# ---------------------------------------------------------------------------
# Shared Synchronous SQLite checkpoint connection (for worker)
# ---------------------------------------------------------------------------
_sync_sqlite_conn: Optional[sqlite3.Connection] = None
_sync_checkpointer: Optional[SqliteSaver] = None

def init_sync_checkpointer() -> None:
    """Open the sync SQLite connection. Call once per worker process."""
    global _sync_sqlite_conn, _sync_checkpointer
    _sync_sqlite_conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
    _sync_sqlite_conn.execute("PRAGMA journal_mode=WAL;")
    _sync_checkpointer = SqliteSaver(_sync_sqlite_conn)
    _sync_checkpointer.setup()
    logger.info("Sync SQLite checkpoint connection opened (WAL mode).")

def close_sync_checkpointer() -> None:
    """Close the sync SQLite connection."""
    global _sync_sqlite_conn, _sync_checkpointer
    if _sync_sqlite_conn:
        _sync_sqlite_conn.close()
        _sync_sqlite_conn = None
        _sync_checkpointer = None
        logger.info("Sync SQLite checkpoint connection closed.")

def get_sync_checkpointer() -> SqliteSaver:
    if _sync_checkpointer is None:
        raise RuntimeError("Sync Checkpointer not initialised.")
    return _sync_checkpointer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return str(content)


def _seconds_to_mmss(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def _get_llm(temperature: float = 0.15):
    """Returns a configured Gemini LLM instance."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.google_api_key,
        temperature=temperature,
        max_output_tokens=8192,
    )


# _invoke_llm_with_retry was removed — all LLM calls go through the async
# _astream_llm_with_retry path below.


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    video_a: Dict[str, Any]
    video_b: Dict[str, Any]
    hook_analysis: str
    is_mock_analysis: bool
    session_id: str


# ---------------------------------------------------------------------------
# System Prompt Builder
# ---------------------------------------------------------------------------
def _fmt_followers(count: int) -> str:
    """Format follower count to human-readable string."""
    if count == 0:
        return "N/A (not publicly available)"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def format_system_prompt(video_a: Dict[str, Any], video_b: Dict[str, Any]) -> str:
    metrics_a = video_a.get("metrics", {})
    metrics_b = video_b.get("metrics", {})
    hook_a = vector_store.isolate_hooks(video_a.get("transcript", []))
    hook_b = vector_store.isolate_hooks(video_b.get("transcript", []))

    hashtags_a = ", ".join(video_a.get("hashtags", [])[:5]) or "None"
    hashtags_b = ", ".join(video_b.get("hashtags", [])[:5]) or "None"

    return f"""## ROLE
You are an elite YouTube script doctor, storytelling strategist, and data analyst.
Your job is to deliver precise, data-backed analysis comparing two creator videos to identify exactly what made one outperform the other.
You speak like a seasoned creative director: direct, punchy, and highly actionable — zero fluff.

## FORMATTING RULES (STRICT)
1. NEVER output giant walls of text.
2. ALWAYS use double newlines (\\n\\n) between every paragraph and list item to ensure readable spacing.
3. Use bold text to highlight key phrases or inline headers so the text is easy to scan.

---

## VIDEO COMPARATIVE DATA

### Video A (Control)
- **Title**: "{video_a.get('title')}"
- **Platform**: {video_a.get('platform')}
- **Creator**: {video_a.get('creator', 'Unknown')}
- **Followers / Subscribers**: {_fmt_followers(video_a.get('follower_count', 0))}
- **Upload Date**: {video_a.get('upload_date', 'Unknown')}
- **Hashtags**: {hashtags_a}
- **Views**: {metrics_a.get('views', 0):,} | **Likes**: {metrics_a.get('likes', 0):,} | **Comments**: {metrics_a.get('comments', 0):,}
- **Duration**: {metrics_a.get('duration', 0)}s
- **Engagement Rate**: {video_a.get('engagement_rate')}%
- **Hook (first 15s)**: "{hook_a}"

### Video B (Variant / Competitor)
- **Title**: "{video_b.get('title')}"
- **Platform**: {video_b.get('platform')}
- **Creator**: {video_b.get('creator', 'Unknown')}
- **Followers / Subscribers**: {_fmt_followers(video_b.get('follower_count', 0))}
- **Upload Date**: {video_b.get('upload_date', 'Unknown')}
- **Hashtags**: {hashtags_b}
- **Views**: {metrics_b.get('views', 0):,} | **Likes**: {metrics_b.get('likes', 0):,} | **Comments**: {metrics_b.get('comments', 0):,}
- **Duration**: {metrics_b.get('duration', 0)}s
- **Engagement Rate**: {video_b.get('engagement_rate')}%
- **Hook (first 15s)**: "{hook_b}"

---

## BEHAVIOUR RULES
1. **Ground every claim in evidence.** Only reference transcript content that appears in the RETRIEVED SEGMENTS block you receive. Do not fabricate quotes or timestamps.
2. **Cite timestamps precisely.** When quoting a transcript segment, always use the format `[Video A @ MM:SS]` or `[Video B @ MM:SS]`.
3. **If evidence is insufficient**, say so clearly: "The retrieved segments don't cover this part of the video — try asking about a specific topic or timeframe."
4. **Focus on psychology and data.** Explain retention mechanics, curiosity loops, pacing, and value propositions. Back claims with the engagement rate numbers.
5. **Use rich Markdown.** Bold key terms, use bullet points for lists, keep paragraphs to 1–3 sentences.
"""


# ---------------------------------------------------------------------------
# Node 1: Format Context
# ---------------------------------------------------------------------------
def format_context_node(state: AgentState) -> Dict[str, Any]:
    logger.info("LangGraph: format_context node")
    system_prompt = format_system_prompt(state["video_a"], state["video_b"])
    return {"messages": [SystemMessage(content=system_prompt)]}


# ---------------------------------------------------------------------------
# Node 2: Generate Initial Hook Analysis
# ---------------------------------------------------------------------------
async def generate_hook_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    logger.info("LangGraph: generate_hook node")

    video_a = state["video_a"]
    video_b = state["video_b"]

    hook_prompt = """Perform a sharp, evidence-based hook audit comparing Video A and Video B.

Use only the hook transcripts and metrics provided in the system context.
Structure your response in clean Markdown with these three sections:

### 1. Psychological Curiosity Loop
Analyse which video opened a more compelling cognitive gap. Quote the hook text to support your case.

### 2. Pacing & Word Velocity
Estimate and compare the information density of the first 15 seconds. Which one respects viewer attention?

### 3. Winner Verdict
Declare a clear winner with one-sentence justification backed by the engagement rate delta.

Keep the whole response under 280 words. Be surgical — no filler."""

    reply_msg = await _astream_llm_with_retry(
        messages=[
            SystemMessage(content=format_system_prompt(video_a, video_b)),
            HumanMessage(content=hook_prompt),
        ],
        config=config,
        temperature=0.15,
    )

    if reply_msg:
        analysis_text = extract_text(reply_msg.content)
        return {
            "hook_analysis": analysis_text,
            "is_mock_analysis": False,
            "messages": [AIMessage(content=f"### Initial Hook Audit & Diagnostics\n\n{analysis_text}")],
        }

    # Fallback: mock analysis when LLM is unavailable
    analysis_text = _generate_mock_hook_analysis(video_a, video_b)
    return {
        "hook_analysis": analysis_text,
        "is_mock_analysis": True,
        "messages": [AIMessage(content=f"### Initial Hook Audit & Diagnostics\n\n{analysis_text}")],
    }


def _generate_mock_hook_analysis(video_a: Dict[str, Any], video_b: Dict[str, Any]) -> str:
    engagement_a = video_a.get("engagement_rate", 0)
    engagement_b = video_b.get("engagement_rate", 0)

    # Use >= so Video A wins ties — consistent with the frontend ChatConsole logic.
    winner = "Video A" if engagement_a >= engagement_b else "Video B"
    loser = "Video B" if winner == "Video A" else "Video A"
    win_data = video_a if winner == "Video A" else video_b
    lose_data = video_b if winner == "Video A" else video_a

    hook_win = vector_store.isolate_hooks(win_data.get("transcript", []))
    hook_lose = vector_store.isolate_hooks(lose_data.get("transcript", []))

    return f"""### 1. Psychological Curiosity Loop
- **{winner}**: Opened with a high-stakes curiosity loop — `"{hook_win[:90]}..."`. Creates an immediate cognitive gap that forces the viewer to keep watching.
- **{loser}**: Lead with `"{hook_lose[:90]}..."` — suffers from high ego-friction (talking about itself rather than the viewer's problem).

### 2. Pacing & Word Velocity
- **{winner}**: High information density in the opening 15 seconds. No throat-clearing.
- **{loser}**: Sluggish opening pacing. Viewers lose interest before the value proposition lands.

### 3. Winner Verdict
**{winner}** wins the hook phase. Engagement rate: **{win_data.get('engagement_rate')}%** vs **{lose_data.get('engagement_rate')}%** — a delta that traces directly to the first 15 seconds.
"""


# ---------------------------------------------------------------------------
# RAG Retrieval Helper
# ---------------------------------------------------------------------------
def retrieve_relevant_segments(query: str, state: AgentState, n_results: int = 6) -> str:
    """
    Fetches the top-N semantically relevant transcript chunks for the given query
    and formats them as a structured context block for the LLM.
    """
    video_ids = [state["video_a"]["video_id"], state["video_b"]["video_id"]]
    chunks = vector_store.query_vector_store(query, video_ids, n_results=n_results)

    if not chunks:
        return "⚠️ No relevant transcript segments found for this query. The vector index may still be empty — try re-ingesting the videos, or rephrase your question with specific keywords."

    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        video_label = "Video A" if chunk["video_id"] == state["video_a"]["video_id"] else "Video B"
        timestamp = _seconds_to_mmss(chunk["start_time"])
        context_parts.append(
            f"**[{i}] [{video_label} @ {timestamp}]**\n\"{chunk['text']}\""
        )

    return "\n\n---\n\n".join(context_parts)




async def _astream_llm_with_retry(
    messages: List[BaseMessage],
    config: RunnableConfig,
    temperature: float = 0.15,
    max_attempts: int = 2,
) -> BaseMessage | None:
    """
    Async streaming invocation of the LLM. 
    Yields chunks to LangGraph via the RunnableConfig.
    """
    if not settings.google_api_key:
        return None

    llm = _get_llm(temperature)
    for attempt in range(max_attempts):
        try:
            response_msg = None
            async for chunk in llm.astream(messages, config=config):
                if response_msg is None:
                    response_msg = chunk
                else:
                    response_msg += chunk
            return response_msg
        except Exception as e:
            err_str = str(e)
            logger.warning(f"LLM streaming attempt {attempt + 1}/{max_attempts} failed: {e}")
            if "429" in err_str and attempt < max_attempts - 1:
                delay_match = _re.search(r"retryDelay.*?'(\d+)s'", err_str)
                wait = int(delay_match.group(1)) if delay_match else 55
                wait = min(wait, 65)
                logger.info(f"Rate limited — waiting {wait}s before retry...")
                await asyncio.sleep(wait)
            else:
                logger.error(f"LLM streaming failed permanently: {e}")
                return None

    return None

# ---------------------------------------------------------------------------
# Node 3: Chat Assistant (RAG-powered)
# ---------------------------------------------------------------------------
async def chat_assistant_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    logger.info("LangGraph: chat_assistant node")
    messages = state["messages"]

    human_msgs = [m for m in messages if isinstance(m, HumanMessage)]
    if not human_msgs:
        logger.warning("chat_assistant_node: no HumanMessage found in state — returning fallback.")
        return {"messages": [AIMessage(content="No query found in the current session state. Please try sending your message again.")]}
    user_msg = human_msgs[-1]
    query = extract_text(user_msg.content)

    # Step 1: Retrieve semantically relevant transcript chunks (blocking call in thread)
    retrieved_context = await asyncio.to_thread(retrieve_relevant_segments, query, state, 6)

    # Step 2: Build enriched system prompt with retrieved context injected
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    base_system_content = extract_text(system_msgs[0].content) if system_msgs else format_system_prompt(
        state["video_a"], state["video_b"]
    )

    enriched_system = f"""{base_system_content}

---

## RETRIEVED TRANSCRIPT SEGMENTS (from Vector DB)

The following segments are the most semantically relevant to the user's current question.
These are your **only** source of truth for transcript content. Do not quote anything outside these segments.
Always cite using the exact format shown (e.g., `[Video A @ 01:24]`).

{retrieved_context}

---

## RESPONSE FORMAT
- Lead with the direct answer to the question.
- Support with specific quotes and timestamps from the segments above.
- Use **bold** for key terms and metrics.
- Bullet points for lists; short paragraphs (1–3 sentences) for prose.
- End with one concrete, actionable takeaway for the creator.
"""

    # Step 3: Assemble full message history (skip old system, use enriched one)
    llm_messages: List[BaseMessage] = [SystemMessage(content=enriched_system)]
    for m in messages[1:]:  # Skip the original system message at index 0
        llm_messages.append(m)

    # Step 4: Call LLM
    reply_msg = await _astream_llm_with_retry(llm_messages, config, temperature=0.15)

    if reply_msg:
        return {"messages": [reply_msg]}

    # Graceful mock fallback if LLM is completely unavailable
    mock_reply = _generate_mock_chat_response(query, state, retrieved_context)
    return {"messages": [AIMessage(content=mock_reply)]}


def _generate_mock_chat_response(query: str, state: AgentState, context: str) -> str:
    video_a_title = state["video_a"]["title"]
    video_b_title = state["video_b"]["title"]
    citations = _re.findall(r'\[Video [AB] @ \d{2}:\d{2}\]', context)
    cite_str = " " + ", ".join(citations[:3]) if citations else ""

    return f"""I analysed the retrieved transcript segments for your query: *"{query}"*

**Video A** — *{video_a_title}*
**Video B** — *{video_b_title}*

Based on the retrieved context{cite_str}:

{context[:600]}{'...' if len(context) > 600 else ''}

> ⚠️ *Note: The AI analysis engine is currently experiencing high demand. Showing raw extracted context instead.*
"""


# ---------------------------------------------------------------------------
# LangGraph Workflow
# ---------------------------------------------------------------------------
state_type: Any = AgentState
workflow = StateGraph(state_type)

workflow.add_node("format_context", format_context_node)
workflow.add_node("generate_hook", generate_hook_node)
workflow.add_node("chat_assistant", chat_assistant_node)


def route_start(state: AgentState) -> str:
    """Route to chat if session is already initialised, otherwise run full init flow."""
    return "chat_assistant" if state.get("hook_analysis") else "format_context"


workflow.add_conditional_edges(START, route_start)
workflow.add_edge("format_context", "generate_hook")
workflow.add_edge("generate_hook", END)
workflow.add_edge("chat_assistant", END)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def initialize_session(
    session_id: str, video_a: Dict[str, Any], video_b: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Initialises a new comparative analysis session and generates the initial hook audit.
    Now async — uses ainvoke so generate_hook_node can stream via LangGraph without
    blocking the FastAPI event loop.
    """
    memory = get_checkpointer()
    agent_graph = workflow.compile(checkpointer=memory)

    config = {"configurable": {"thread_id": session_id}}
    initial_state = {
        "messages": [HumanMessage(content="Start Comparative Analysis Audit")],
        "video_a": video_a,
        "video_b": video_b,
        "hook_analysis": "",
        "is_mock_analysis": False,
        "session_id": session_id,
    }

    res = await agent_graph.ainvoke(initial_state, config=config)

    return {
        "hook_analysis": res.get("hook_analysis", ""),
        "is_mock_analysis": res.get("is_mock_analysis", False),
        "messages": [
            {
                "role": "user" if m.type == "human" else "assistant",
                "content": extract_text(m.content),
            }
            for m in res.get("messages", [])
            if m.type in ("human", "ai")
        ],
    }


async def astream_session(
    session_id: str, video_a: Dict[str, Any], video_b: Dict[str, Any]
):
    """
    Async generator that streams the initial hook audit token-by-token.

    Yields tuples:
      ("hook_chunk", str)      — one LLM token at a time
      ("done",       dict)     — final session metadata after streaming completes

    Using astream_events lets the hook analysis appear in the chat as it's generated,
    satisfying the spec requirement that all responses must stream.
    """
    memory = get_checkpointer()
    agent_graph = workflow.compile(checkpointer=memory)

    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    # Check if this thread already has an initialized session
    state_info = await agent_graph.aget_state(config)
    if state_info and state_info.values and state_info.values.get("hook_analysis"):
        logger.info(f"Session {session_id} already exists. Returning cached chat history.")
        hook_analysis = state_info.values.get("hook_analysis", "")
        is_mock = state_info.values.get("is_mock_analysis", False)
        chat_history = []
        for m in state_info.values.get("messages", []):
            if m.type in ("human", "ai"):
                chat_history.append({
                    "role": "user" if m.type == "human" else "assistant",
                    "content": extract_text(m.content),
                })
        yield ("done", {
            "hook_analysis": hook_analysis,
            "is_mock_analysis": is_mock,
            "chat_history": chat_history,
        })
        return

    initial_state = {
        "messages": [HumanMessage(content="Start Comparative Analysis Audit")],
        "video_a": video_a,
        "video_b": video_b,
        "hook_analysis": "",
        "is_mock_analysis": False,
        "session_id": session_id,
    }

    # Yield the section header immediately so the chat feels responsive
    progress_msg = "> *Building analysis context & generating hook audit...*\n\n"
    yield ("hook_chunk", progress_msg)
    
    header = "### Initial Hook Audit & Diagnostics\n\n"
    yield ("hook_chunk", header)

    emitted_any = False
    async for event in agent_graph.astream_events(initial_state, config=config, version="v2"):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            token = event["data"]["chunk"].content
            if token and isinstance(token, str):
                emitted_any = True
                yield ("hook_chunk", token)

    # Collect final state for the complete event
    final = await agent_graph.aget_state(config)
    hook_analysis = ""
    is_mock = False
    chat_history: List[Dict[str, str]] = []

    if final and final.values:
        hook_analysis = final.values.get("hook_analysis", "")
        is_mock = final.values.get("is_mock_analysis", False)
        for m in final.values.get("messages", []):
            if m.type in ("human", "ai"):
                chat_history.append({
                    "role": "user" if m.type == "human" else "assistant",
                    "content": extract_text(m.content),
                })

    # If no tokens streamed (LLM unavailable → mock path), flush the mock text at once
    if not emitted_any and hook_analysis:
        yield ("hook_chunk", hook_analysis)

    yield ("done", {
        "hook_analysis": hook_analysis,
        "is_mock_analysis": is_mock,
        "chat_history": chat_history,
    })


def stream_session_sync(
    session_id: str, video_a: Dict[str, Any], video_b: Dict[str, Any]
):
    """
    Synchronous generator that streams the initial hook audit token-by-token.
    Used by the Celery worker to avoid async nested loops.
    """
    memory = get_sync_checkpointer()
    agent_graph = workflow.compile(checkpointer=memory)

    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    state_info = agent_graph.get_state(config)
    if state_info and state_info.values and state_info.values.get("hook_analysis"):
        logger.info(f"Session {session_id} already exists. Returning cached chat history.")
        hook_analysis = state_info.values.get("hook_analysis", "")
        is_mock = state_info.values.get("is_mock_analysis", False)
        chat_history = []
        for m in state_info.values.get("messages", []):
            if m.type in ("human", "ai"):
                chat_history.append({
                    "role": "user" if m.type == "human" else "assistant",
                    "content": extract_text(m.content),
                })
        yield ("done", {
            "hook_analysis": hook_analysis,
            "is_mock_analysis": is_mock,
            "chat_history": chat_history,
        })
        return

    initial_state = {
        "messages": [HumanMessage(content="Start Comparative Analysis Audit")],
        "video_a": video_a,
        "video_b": video_b,
        "hook_analysis": "",
        "is_mock_analysis": False,
        "session_id": session_id,
    }

    progress_msg = "> *Building analysis context & generating hook audit...*\n\n"
    yield ("hook_chunk", progress_msg)

    header = "### Initial Hook Audit & Diagnostics\n\n"
    yield ("hook_chunk", header)

    emitted_any = False
    
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        agen = agent_graph.astream_events(initial_state, config=config, version="v2")
        while True:
            try:
                event = loop.run_until_complete(agen.__anext__())
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    token = event["data"]["chunk"].content
                    if token and isinstance(token, str):
                        emitted_any = True
                        yield ("hook_chunk", token)
            except StopAsyncIteration:
                break
            except Exception as e:
                logger.warning(f"Error during async event streaming: {e}")
                break
        final = loop.run_until_complete(agent_graph.aget_state(config))
    finally:
        loop.close()

    hook_analysis = ""
    is_mock = False
    chat_history: List[Dict[str, str]] = []

    if final and final.values:
        hook_analysis = final.values.get("hook_analysis", "")
        is_mock = final.values.get("is_mock_analysis", False)
        for m in final.values.get("messages", []):
            if m.type in ("human", "ai"):
                chat_history.append({
                    "role": "user" if m.type == "human" else "assistant",
                    "content": extract_text(m.content),
                })

    if not emitted_any and hook_analysis:
        yield ("hook_chunk", hook_analysis)

    yield ("done", {
        "hook_analysis": hook_analysis,
        "is_mock_analysis": is_mock,
        "chat_history": chat_history,
    })


# send_chat_message (sync) was removed — the active code path uses
# stream_chat_message_sse (async SSE) exclusively.


async def stream_chat_message_sse(session_id: str, message: str):
    """
    Async generator that yields the AI response token-by-token for SSE streaming.
    Uses LangGraph's native astream_events (v2) to capture true LLM output chunks
    safely across different LangGraph versions.
    """
    memory = get_checkpointer()
    agent_graph = workflow.compile(checkpointer=memory)

    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    state_info = await agent_graph.aget_state(config)
    if state_info is None or state_info.values is None or not state_info.values.get("hook_analysis"):
        yield dict(data=json.dumps({"chunk": "**Error:** Session not found. Call /analyze first. "}))
        yield dict(data="[DONE]")
        return

    try:
        inputs = {"messages": [HumanMessage(content=message)]}

        emitted_any = False
        # astream_events is the safest way to extract streaming chunks in LangChain/LangGraph
        async for event in agent_graph.astream_events(inputs, config=config, version="v2"):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                chunk_content = event["data"]["chunk"].content
                if chunk_content and isinstance(chunk_content, str):
                    emitted_any = True
                    yield dict(data=json.dumps({"chunk": chunk_content}))

        if not emitted_any:
            # If no stream events fired (e.g. mock fallback was used), yield the final state's message
            final_state = await agent_graph.aget_state(config)
            if final_state and final_state.values and final_state.values.get("messages"):
                last_msg = final_state.values["messages"][-1]
                if last_msg.type == "ai" and getattr(last_msg, "content", ""):
                    yield dict(data=json.dumps({"chunk": last_msg.content}))

    except Exception as e:
        logger.error(f"Error in stream_chat_message_sse: {e}")
        yield dict(data=json.dumps({"chunk": f"**Error:** {str(e)} "}))

    yield dict(data="[DONE]")
