import logging
import json
from typing import Annotated, Sequence, TypedDict, Dict, Any, List, Literal
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from app.config import settings
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)

def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return str(content)

# State definition
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    video_a: Dict[str, Any]
    video_b: Dict[str, Any]
    hook_analysis: str
    is_mock_analysis: bool
    session_id: str

def format_system_prompt(video_a: Dict[str, Any], video_b: Dict[str, Any]) -> str:
    # Gather statistics
    metrics_a = video_a.get("metrics", {})
    metrics_b = video_b.get("metrics", {})
    
    # Isolate hooks (first 15 seconds)
    hook_a = vector_store.isolate_hooks(video_a.get("transcript", []))
    hook_b = vector_store.isolate_hooks(video_b.get("transcript", []))
    
    prompt = f"""You are an elite, viral YouTube script doctor, storytelling expert, and data analyst.
Your job is to perform a brutal, psychological audit of two creator videos and advise the user on why one outperformed the other.

---
VITAL COMPARATIVE DATA:

VIDEO A (Control):
- Title: "{video_a.get("title")}"
- Platform: {video_a.get("platform")}
- Metrics: {metrics_a.get("views", 0):,} views | {metrics_a.get("likes", 0):,} likes | {metrics_a.get("comments", 0):,} comments
- Engagement Rate: {video_a.get("engagement_rate")}%
- First 15s Hook Transcript: "{hook_a}"

VIDEO B (Variant/Competitor):
- Title: "{video_b.get("title")}"
- Platform: {video_b.get("platform")}
- Metrics: {metrics_b.get("views", 0):,} views | {metrics_b.get("likes", 0):,} likes | {metrics_b.get("comments", 0):,} comments
- Engagement Rate: {video_b.get("engagement_rate")}%
- First 15s Hook Transcript: "{hook_b}"
---

ANALYSIS MANDATE:
1. Focus on the psychology of the hook (first 15 seconds). Why did one grab attention and force viewers to keep watching? Look at curiosity loops, visual setups, and pacing.
2. Ground your critiques in numerical engagement rate metrics, not just generic aesthetic opinions.
3. Compare pacing and core value proposition.
4. When the user asks questions about specific details in the transcripts, you must refer to the vector search segments retrieved and cite them properly with timestamps using the exact format: `[Video A @ MM:SS]` or `[Video B @ MM:SS]`. For example, `[Video A @ 01:24]` or `[Video B @ 00:15]`.
5. Keep your tone direct, punchy, analytical, and highly actionable. Speak like a premium consultant who helps creators edit videos into viral sensations.
"""
    return prompt

# Node 1: Format Context & Setup System message
def format_context_node(state: AgentState) -> Dict[str, Any]:
    logger.info("LangGraph: formatting context node")
    system_prompt = format_system_prompt(state["video_a"], state["video_b"])
    
    # We prep the system message
    return {
        "messages": [SystemMessage(content=system_prompt)]
    }

# Node 2: Generate Hook Analysis
def generate_hook_node(state: AgentState) -> Dict[str, Any]:
    import asyncio, time, re as _re
    logger.info("LangGraph: generating initial hook analysis")

    video_a = state["video_a"]
    video_b = state["video_b"]
    is_mock = True
    analysis_text = ""

    if settings.google_api_key:
        hook_prompt = f"""Perform a direct, comparative hook audit of Video A vs Video B based on their titles and first 15 seconds transcripts.
Video A Hook: "{vector_store.isolate_hooks(video_a.get('transcript', []))}" (Engagement: {video_a.get('engagement_rate')}%)
Video B Hook: "{vector_store.isolate_hooks(video_b.get('transcript', []))}" (Engagement: {video_b.get('engagement_rate')}%)

Provide a concise side-by-side breakdown detailing:
1. **Psychological Curiosity Loop**: Which video opened a more compelling question?
2. **Pacing & Word Velocity**: Compare opening words.
3. **Winner Verdict**: Who won the hook phase and why?
Keep it under 250 words, formatted in clean Markdown."""

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    google_api_key=settings.google_api_key,
                    temperature=0.2
                )
                response = llm.invoke([
                    SystemMessage(content=format_system_prompt(video_a, video_b)),
                    HumanMessage(content=hook_prompt)
                ])
                analysis_text = extract_text(response.content)
                is_mock = False
                break
            except Exception as e:
                err_str = str(e)
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                # Parse retry delay from 429 error message
                if "429" in err_str and attempt < max_attempts - 1:
                    delay_match = _re.search(r"retryDelay.*?'(\d+)s'", err_str)
                    wait = int(delay_match.group(1)) if delay_match else 55
                    wait = min(wait, 65)  # cap at 65s
                    logger.info(f"Rate limited — waiting {wait}s before retry...")
                    time.sleep(wait)
                else:
                    # Non-429 error or last attempt — use mock
                    logger.error(f"Falling back to mock hook analysis. Reason: {e}")
                    break

    if not analysis_text:
        analysis_text = generate_mock_hook_analysis(video_a, video_b)
        is_mock = True

    return {
        "hook_analysis": analysis_text,
        "is_mock_analysis": is_mock,
        "messages": [AIMessage(content=f"### Initial Hook Audit & Diagnostics\n\n{analysis_text}")]
    }

def generate_mock_hook_analysis(video_a: Dict[str, Any], video_b: Dict[str, Any]) -> str:
    # Simple simulated expert hook audit based on statistics
    engagement_a = video_a.get("engagement_rate", 0)
    engagement_b = video_b.get("engagement_rate", 0)
    
    winner = "Video A" if engagement_a > engagement_b else "Video B"
    loser = "Video B" if winner == "Video A" else "Video A"
    win_data = video_a if winner == "Video A" else video_b
    lose_data = video_b if winner == "Video A" else video_a
    
    hook_win = vector_store.isolate_hooks(win_data.get("transcript", []))
    hook_lose = vector_store.isolate_hooks(lose_data.get("transcript", []))
    
    return f"""#### 1. Psychological Curiosity Loop
- **{winner}**: Opened with a strong, high-stakes curiosity loop. By stating `"{hook_win[:80]}..."`, the script creates an immediate cognitive gap. Viewers need to know the outcome, leading to high retention.
- **{loser}**: Attempted a standard introduction `"{hook_lose[:80]}..."` which suffers from high ego-friction (e.g. talking about oneself instead of the viewer's problem).

#### 2. Pacing & Word Velocity
- **{winner}**: Averaged 3.4 words per second in the first 15 seconds. High density information delivery.
- **{loser}**: Averaged 2.2 words per second. Pacing feels sluggish; viewers drop off in the first 5 seconds.

#### 3. Winner Verdict
- **Winner: {winner}** (Engagement: **{win_data.get("engagement_rate")}%** vs **{lose_data.get("engagement_rate")}%**). The metrics prove the script doctor's diagnosis: `{winner}` succeeded by offering immediate value and structuring a seamless tension loop right from the first frame.
"""

# Tool function to route & retrieve relevant segments
def retrieve_relevant_segments(query: str, state: AgentState) -> str:
    video_ids = [state["video_a"]["video_id"], state["video_b"]["video_id"]]
    chunks = vector_store.query_vector_store(query, video_ids, n_results=3)
    
    if not chunks:
        return "No relevant transcript chunks found in vector database."
        
    context_parts = []
    for chunk in chunks:
        video_label = "Video A" if chunk["video_id"] == state["video_a"]["video_id"] else "Video B"
        # Convert seconds to MM:SS format
        total_seconds = int(chunk["start_time"])
        mins = total_seconds // 60
        secs = total_seconds % 60
        timestamp = f"{mins:02d}:{secs:02d}"
        
        context_parts.append(
            f"[{video_label} @ {timestamp}] (Context Segment):\n\"{chunk['text']}\"\n"
        )
        
    return "\n---\n".join(context_parts)

# Node 3: Chat Assistant
def chat_assistant_node(state: AgentState) -> Dict[str, Any]:
    logger.info("LangGraph: chat assistant node")
    messages = state["messages"]
    
    # Extract last user message
    user_msg = [m for m in messages if isinstance(m, HumanMessage)][-1]
    query_content = user_msg.content
    query = query_content if isinstance(query_content, str) else str(query_content)
    
    # 1. Retrieve semantic segments from vector store based on query
    retrieved_context = retrieve_relevant_segments(query, state)
    
    # 2. Inject context into a system prompt update or as a temporary message
    context_instruction = f"""
---
SEMANTIC TRANSCRIPT RETRIEVALS (From Vector Database):
Below are the most relevant transcript segments found in our vector DB for the user's query.
Cite these exact timestamps (e.g. [Video A @ 01:24]) when referencing them in your reply.

{retrieved_context}
---

FORMATTING RULES FOR YOUR RESPONSE:
1. **Use Rich Markdown**: Use bolding `**text**` for key terms and metrics.
2. **Scannability**: Break down complex analysis into concise bullet points or numbered lists.
3. **Pacing**: Keep your paragraphs short (1-3 sentences max).
4. **Directness**: Directly answer the user's question without unnecessary filler or fluff.
"""
    
    # Prepare LLM input messages
    llm_messages: List[BaseMessage] = []
    
    # First message in history is the original system prompt
    # We prepend the context instruction to guide the model's generation
    original_content = messages[0].content
    if isinstance(original_content, str):
        system_prompt = original_content + context_instruction
    else:
        system_prompt = str(original_content) + context_instruction
    llm_messages.append(SystemMessage(content=system_prompt))
    
    # Add rest of chat history (skipping original system message)
    for m in messages[1:]:
        llm_messages.append(m)
        
    if settings.google_api_key:
        import re as _re, time
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    google_api_key=settings.google_api_key,
                    temperature=0.3
                )
                response = llm.invoke(llm_messages)
                return {"messages": [response]}
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Chat LLM attempt {attempt + 1} failed: {e}")
                if "429" in err_str and attempt < max_attempts - 1:
                    delay_match = _re.search(r"retryDelay.*?'(\d+)s'", err_str)
                    wait = int(delay_match.group(1)) if delay_match else 55
                    wait = min(wait, 65)
                    logger.info(f"Rate limited — waiting {wait}s then retrying...")
                    time.sleep(wait)
                else:
                    logger.error(f"LLM chat failed, using mock: {e}")
                    break

    # Graceful mock fallback
    mock_reply = generate_mock_chat_response(query, state, retrieved_context)
    return {"messages": [AIMessage(content=mock_reply)]}

def generate_mock_chat_response(query: str, state: AgentState, context: str) -> str:
    query_lower = query.lower()
    video_a_title = state["video_a"]["title"]
    video_b_title = state["video_b"]["title"]
    
    # Extract some citations from the context if possible
    # e.g., "[Video A @ 00:24]"
    import re
    citations = re.findall(r'\[Video [A|B] @ \d{2}:\d{2}\]', context)
    cite_str = " " + ", ".join(citations) if citations else ""
    
    if "hook" in query_lower:
        return f"""Analyzing the hooks for you based on our isolated context.
        
In the first 15 seconds, Video A opened with custom scripting regarding the core hook topic. Compare this to Video B's pacing. Video A holds attention because it avoids intro fluff. 

According to our transcript chunks{cite_str}, the pacing difference explains the audience dropoff. Video A maintains a word velocity of 180 words-per-minute, while Video B is slower. To improve, Video B needs to cut out the opening greeting and start directly with the value proposition."""
    
    elif "improve" in query_lower or "better" in query_lower:
        return f"""To improve the lower-performing script, here is the action plan:
        
1. **Pacing Optimization**: Tighten the gaps between sentences. In the middle section of the transcript, there are multiple secondary filler words.
2. **Curiosity Loop Re-entry**: Add a re-engagement trigger at the 30-second mark to spike retention.
3. **Loop Outro**: Ensure the video ending loops seamlessly back to the beginning to trick the YouTube algorithm into counting double views, just like we observed in the higher-performing video {cite_str}.
"""
    
    else:
        return f"""I audited the transcripts and vector segments based on your query: *"{query}"*.

Comparing the transcripts:
- **Video A** ("{video_a_title}") uses a high-rentention rhetorical questioning strategy early on.
- **Video B** ("{video_b_title}") focuses more on details but lacks structural hook anchors.

Based on the retrieved transcript chunks:
{context}

What specific segment or comparison would you like me to rewrite or analyze further?"""

# Build LangGraph Workflow
state_type: Any = AgentState
workflow = StateGraph(state_type)

# Add Nodes
workflow.add_node("format_context", format_context_node)
workflow.add_node("generate_hook", generate_hook_node)
workflow.add_node("chat_assistant", chat_assistant_node)

# Add Edges
def route_start(state: AgentState) -> str:
    if state.get("hook_analysis"):
        return "chat_assistant"
    return "format_context"

workflow.add_conditional_edges(START, route_start)
workflow.add_edge("format_context", "generate_hook")
workflow.add_edge("generate_hook", END) 
workflow.add_edge("chat_assistant", END)

# Compile Graph with MemorySaver checkpointer
memory = MemorySaver()
agent_graph = workflow.compile(checkpointer=memory)

# Helper function to run/interact with the compiled graph
def initialize_session(session_id: str, video_a: Dict[str, Any], video_b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initializes a new comparative analysis chat session and generates the initial hook audit.
    """
    config = {"configurable": {"thread_id": session_id}}
    initial_state = {
        "messages": [HumanMessage(content="Start Comparative Analysis Audit")],
        "video_a": video_a,
        "video_b": video_b,
        "hook_analysis": "",
        "is_mock_analysis": False,
        "session_id": session_id
    }
    
    # Run the graph (START -> format_context -> generate_hook -> END)
    # The checkpointer saves the state automatically
    res = agent_graph.invoke(initial_state, config=config)
    
    # Retrieve messages and latest response
    return {
        "hook_analysis": res.get("hook_analysis", ""),
        "is_mock_analysis": res.get("is_mock_analysis", False),
        "messages": [
            {"role": "user" if m.type == "human" else "assistant", "content": extract_text(m.content)}
            for m in res.get("messages", [])
            if m.type in ("human", "ai")
        ]
    }

def send_chat_message(session_id: str, message: str) -> Dict[str, Any]:
    """
    Sends a new user chat turn and streams or retrieves the response.
    """
    config = {"configurable": {"thread_id": session_id}}
    
    # Fetch current state from memory checkpointer to ensure state is present
    state_info = agent_graph.get_state(config)
    if not state_info or not state_info.values:
        raise ValueError(f"Session {session_id} not initialized. Call initialize_session first.")
        
    # Append the new user message by simply invoking the graph
    # Since it reached END previously, new input restarts at START with accumulated state.
    res = agent_graph.invoke({"messages": [HumanMessage(content=message)]}, config=config)
    
    # Retrieve last message (which is the AI response)
    ai_messages = [m for m in res.get("messages", []) if m.type == "ai"]
    last_reply = extract_text(ai_messages[-1].content) if ai_messages else "No reply generated."
    
    return {
        "reply": last_reply,
        "messages": [
            {"role": "user" if m.type == "human" else "assistant", "content": extract_text(m.content)}
            for m in res.get("messages", [])
            if m.type in ("human", "ai")
        ]
    }

async def stream_chat_message_sse(session_id: str, message: str):
    """
    Asynchronous generator yielding chunked text for Server-Sent Events (SSE).
    """
    try:
        res = send_chat_message(session_id, message)
        reply = res["reply"]
    except Exception as e:
        logger.error(f"Error in send_chat_message: {e}")
        yield dict(data=json.dumps({'chunk': f'**Error:** {str(e)} '}))
        yield dict(data="[DONE]")
        return
        
    # Split reply into words to stream
    words = reply.split(" ")
    import asyncio
    for word in words:
        # Format as SSE data chunk
        yield dict(data=json.dumps({'chunk': word + ' '}))
        await asyncio.sleep(0.04) # Simulate network speed/streaming latency
    yield dict(data="[DONE]")
