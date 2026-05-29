"""
Unit tests for app/services/agent.py

Tests cover:
  - format_system_prompt  — content correctness, formatting rules
  - retrieve_relevant_segments — vector store delegation, citation formatting
  - _generate_mock_hook_analysis — winner logic, engagement delta
  - _generate_mock_chat_response — citation extraction, truncation
  - astream_session  — yields hook_chunk events and done payload (LLM mocked)
  - stream_chat_message_sse — streams chunk events and terminates with [DONE]

All LLM and vector-store calls are mocked.
No Google / OpenAI API calls are made.

Run with: pytest tests/test_agent.py -v
"""
import sys
import os
import asyncio
import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# Shared minimal video fixtures (inline so the file is self-contained)
VIDEO_A = {
    "video_id": "vid_a",
    "title": "How I 10x My Revenue",
    "platform": "youtube",
    "creator": "Creator Alpha",
    "follower_count": 500_000,
    "hashtags": ["#business"],
    "upload_date": "2024-01-15",
    "metrics": {"views": 1_200_000, "likes": 48_000, "comments": 1_800, "duration": 720},
    "engagement_rate": 4.15,
    "transcript": [
        {"text": "Welcome back to the channel", "start": 0.0, "duration": 3.0},
        {"text": "Today I share the one trick", "start": 3.0, "duration": 4.0},
        {"text": "Body content starts here", "start": 15.0, "duration": 5.0},
    ],
}

VIDEO_B = {
    "video_id": "vid_b",
    "title": "Secret Growth Hack Revealed",
    "platform": "youtube",
    "creator": "Creator Beta",
    "follower_count": 120_000,
    "hashtags": ["#growth"],
    "upload_date": "2024-02-20",
    "metrics": {"views": 300_000, "likes": 24_000, "comments": 600, "duration": 480},
    "engagement_rate": 8.20,
    "transcript": [
        {"text": "This secret will shock you", "start": 0.0, "duration": 4.0},
        {"text": "Nobody discusses this", "start": 4.0, "duration": 5.0},
        {"text": "Main content follows here", "start": 15.0, "duration": 6.0},
    ],
}


# ---------------------------------------------------------------------------
# format_system_prompt
# ---------------------------------------------------------------------------

class TestFormatSystemPrompt:
    def test_contains_video_titles(self):
        from app.services.agent import format_system_prompt
        prompt = format_system_prompt(VIDEO_A, VIDEO_B)
        assert "How I 10x My Revenue" in prompt
        assert "Secret Growth Hack Revealed" in prompt

    def test_contains_engagement_rates(self):
        from app.services.agent import format_system_prompt
        prompt = format_system_prompt(VIDEO_A, VIDEO_B)
        assert "4.15" in prompt
        assert "8.2" in prompt or "8.20" in prompt

    def test_contains_view_counts(self):
        from app.services.agent import format_system_prompt
        prompt = format_system_prompt(VIDEO_A, VIDEO_B)
        assert "1,200,000" in prompt
        assert "300,000" in prompt

    def test_contains_hook_text(self):
        from app.services.agent import format_system_prompt
        prompt = format_system_prompt(VIDEO_A, VIDEO_B)
        # Hook = first 15s
        assert "Welcome back to the channel" in prompt
        assert "This secret will shock you" in prompt

    def test_contains_creator_names(self):
        from app.services.agent import format_system_prompt
        prompt = format_system_prompt(VIDEO_A, VIDEO_B)
        assert "Creator Alpha" in prompt
        assert "Creator Beta" in prompt

    def test_follower_count_formatted_as_k(self):
        from app.services.agent import format_system_prompt
        prompt = format_system_prompt(VIDEO_A, VIDEO_B)
        assert "500.0K" in prompt or "500K" in prompt

    def test_follower_count_zero_shows_na(self):
        from app.services.agent import format_system_prompt
        video_no_followers = {**VIDEO_A, "follower_count": 0}
        prompt = format_system_prompt(video_no_followers, VIDEO_B)
        assert "N/A" in prompt

    def test_contains_platform(self):
        from app.services.agent import format_system_prompt
        prompt = format_system_prompt(VIDEO_A, VIDEO_B)
        assert "youtube" in prompt.lower()

    def test_contains_hashtags(self):
        from app.services.agent import format_system_prompt
        prompt = format_system_prompt(VIDEO_A, VIDEO_B)
        assert "#business" in prompt
        assert "#growth" in prompt


# ---------------------------------------------------------------------------
# retrieve_relevant_segments
# ---------------------------------------------------------------------------

class TestRetrieveRelevantSegments:
    def _make_state(self):
        """Build a minimal AgentState dict."""
        return {
            "video_a": VIDEO_A,
            "video_b": VIDEO_B,
            "hook_analysis": "",
            "is_mock_analysis": False,
            "session_id": "test_session",
            "messages": [],
        }

    @patch("app.services.agent.vector_store")
    def test_delegates_to_vector_store(self, mock_vs):
        mock_vs.query_vector_store.return_value = [
            {"text": "Relevant chunk A", "video_id": "vid_a", "start_time": 5.0},
            {"text": "Relevant chunk B", "video_id": "vid_b", "start_time": 32.0},
        ]
        from app.services.agent import retrieve_relevant_segments
        result = retrieve_relevant_segments("hook pacing", self._make_state(), n_results=6)

        mock_vs.query_vector_store.assert_called_once_with(
            "hook pacing", ["vid_a", "vid_b"], n_results=6
        )
        assert "Relevant chunk A" in result
        assert "Relevant chunk B" in result

    @patch("app.services.agent.vector_store")
    def test_citation_format_includes_timestamp(self, mock_vs):
        mock_vs.query_vector_store.return_value = [
            {"text": "Some spoken line", "video_id": "vid_a", "start_time": 90.0},
        ]
        from app.services.agent import retrieve_relevant_segments
        result = retrieve_relevant_segments("any query", self._make_state())
        assert "[Video A @ 01:30]" in result

    @patch("app.services.agent.vector_store")
    def test_empty_results_returns_warning_message(self, mock_vs):
        mock_vs.query_vector_store.return_value = []
        from app.services.agent import retrieve_relevant_segments
        result = retrieve_relevant_segments("query", self._make_state())
        assert "No relevant transcript segments" in result

    @patch("app.services.agent.vector_store")
    def test_video_b_labelled_correctly(self, mock_vs):
        mock_vs.query_vector_store.return_value = [
            {"text": "Video B content", "video_id": "vid_b", "start_time": 45.0},
        ]
        from app.services.agent import retrieve_relevant_segments
        result = retrieve_relevant_segments("query", self._make_state())
        assert "[Video B @ 00:45]" in result


# ---------------------------------------------------------------------------
# _generate_mock_hook_analysis
# ---------------------------------------------------------------------------

class TestGenerateMockHookAnalysis:
    def test_higher_engagement_video_declared_winner(self):
        from app.services.agent import _generate_mock_hook_analysis
        result = _generate_mock_hook_analysis(VIDEO_A, VIDEO_B)
        # VIDEO_B has 8.20% vs VIDEO_A's 4.15% → B wins
        assert "Video B" in result
        assert "Winner Verdict" in result

    def test_video_a_wins_when_higher_engagement(self):
        from app.services.agent import _generate_mock_hook_analysis
        video_a_strong = {**VIDEO_A, "engagement_rate": 15.0}
        result = _generate_mock_hook_analysis(video_a_strong, VIDEO_B)
        assert "Video A" in result
        assert "15.0%" in result

    def test_contains_three_sections(self):
        from app.services.agent import _generate_mock_hook_analysis
        result = _generate_mock_hook_analysis(VIDEO_A, VIDEO_B)
        assert "Psychological Curiosity Loop" in result
        assert "Pacing" in result
        assert "Winner Verdict" in result

    def test_engagement_delta_shown(self):
        from app.services.agent import _generate_mock_hook_analysis
        result = _generate_mock_hook_analysis(VIDEO_A, VIDEO_B)
        assert "8.2" in result or "8.20" in result


# ---------------------------------------------------------------------------
# _generate_mock_chat_response
# ---------------------------------------------------------------------------

class TestGenerateMockChatResponse:
    def _make_state(self):
        return {
            "video_a": VIDEO_A,
            "video_b": VIDEO_B,
            "hook_analysis": "some hook",
            "is_mock_analysis": True,
            "session_id": "test",
            "messages": [],
        }

    def test_includes_query_in_response(self):
        from app.services.agent import _generate_mock_chat_response
        result = _generate_mock_chat_response("compare hooks", self._make_state(), "context text")
        assert "compare hooks" in result

    def test_includes_video_titles(self):
        from app.services.agent import _generate_mock_chat_response
        result = _generate_mock_chat_response("query", self._make_state(), "context")
        assert "How I 10x My Revenue" in result
        assert "Secret Growth Hack Revealed" in result

    def test_extracts_citations_from_context(self):
        from app.services.agent import _generate_mock_chat_response
        context = "See [Video A @ 01:24] and [Video B @ 00:45] for details"
        result = _generate_mock_chat_response("query", self._make_state(), context)
        assert "[Video A @ 01:24]" in result or "[Video B @ 00:45]" in result

    def test_context_truncated_at_600_chars(self):
        from app.services.agent import _generate_mock_chat_response
        long_context = "x" * 1000
        result = _generate_mock_chat_response("q", self._make_state(), long_context)
        assert "..." in result


# ---------------------------------------------------------------------------
# astream_session — streaming init flow (LLM mocked)
# ---------------------------------------------------------------------------

class TestAstreamSession:
    @pytest.fixture(autouse=True)
    def reset_agent_graph(self):
        """Each test gets a fresh MemorySaver so sessions don't bleed."""
        from langgraph.checkpoint.memory import MemorySaver
        from app.services import agent as agent_module
        old_memory = agent_module.memory
        agent_module.memory = MemorySaver()
        # Recompile the graph with the fresh checkpointer
        agent_module.agent_graph = agent_module.workflow.compile(
            checkpointer=agent_module.memory
        )
        yield
        agent_module.memory = old_memory

    @pytest.mark.asyncio
    async def test_streams_header_chunk_first(self):
        """The header 'Initial Hook Audit' must be the very first yield."""
        with patch("app.services.agent._astream_llm_with_retry") as mock_llm:
            # Simulate LLM unavailable → mock fallback path
            mock_llm.return_value = None

            from app.services.agent import astream_session
            events = []
            async for evt_type, payload in astream_session("s_header", VIDEO_A, VIDEO_B):
                events.append((evt_type, payload))

        assert events[0][0] == "hook_chunk"
        assert "Hook Audit" in events[0][1]

    @pytest.mark.asyncio
    async def test_always_emits_done_event(self):
        with patch("app.services.agent._astream_llm_with_retry", return_value=None):
            from app.services.agent import astream_session
            events = []
            async for evt_type, payload in astream_session("s_done", VIDEO_A, VIDEO_B):
                events.append((evt_type, payload))

        event_types = [e[0] for e in events]
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_done_payload_has_required_keys(self):
        with patch("app.services.agent._astream_llm_with_retry", return_value=None):
            from app.services.agent import astream_session
            done_payload = None
            async for evt_type, payload in astream_session("s_keys", VIDEO_A, VIDEO_B):
                if evt_type == "done":
                    done_payload = payload

        assert done_payload is not None
        assert isinstance(done_payload, dict)
        assert "hook_analysis" in done_payload
        assert "is_mock_analysis" in done_payload
        assert "chat_history" in done_payload

    @pytest.mark.asyncio
    async def test_mock_fallback_sets_is_mock_true(self):
        """When LLM is unavailable, is_mock_analysis should be True."""
        with patch("app.services.agent._astream_llm_with_retry", return_value=None):
            from app.services.agent import astream_session
            done_payload = None
            async for evt_type, payload in astream_session("s_mock", VIDEO_A, VIDEO_B):
                if evt_type == "done":
                    done_payload = payload

        assert isinstance(done_payload, dict)
        assert done_payload["is_mock_analysis"] is True

    @pytest.mark.asyncio
    async def test_hook_analysis_non_empty_in_done(self):
        with patch("app.services.agent._astream_llm_with_retry", return_value=None):
            from app.services.agent import astream_session
            done_payload = None
            async for evt_type, payload in astream_session("s_nonempty", VIDEO_A, VIDEO_B):
                if evt_type == "done":
                    done_payload = payload

        assert isinstance(done_payload, dict)
        hook_analysis = done_payload["hook_analysis"]
        assert isinstance(hook_analysis, str)
        assert len(hook_analysis) > 0


# ---------------------------------------------------------------------------
# stream_chat_message_sse
# ---------------------------------------------------------------------------

class TestStreamChatMessageSse:
    @pytest.fixture(autouse=True)
    def fresh_session(self):
        """Initialize a session so chat tests have a valid state to operate on."""
        from langgraph.checkpoint.memory import MemorySaver
        from app.services import agent as agent_module
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

        agent_module.memory = MemorySaver()
        agent_module.agent_graph = agent_module.workflow.compile(
            checkpointer=agent_module.memory
        )

        # Pre-seed the graph state so chat won't 404
        config = {"configurable": {"thread_id": "chat_session"}}
        initial_state = {
            "messages": [
                SystemMessage(content="system prompt"),
                HumanMessage(content="Start Comparative Analysis Audit"),
                AIMessage(content="### Hook Audit\n\nVideo B wins."),
            ],
            "video_a": VIDEO_A,
            "video_b": VIDEO_B,
            "hook_analysis": "Video B wins.",
            "is_mock_analysis": True,
            "session_id": "chat_session",
        }
        # Directly update state (no LLM call needed)
        agent_module.agent_graph.update_state(config, initial_state)
        yield

    @pytest.mark.asyncio
    async def test_unknown_session_yields_error_then_done(self):
        from app.services.agent import stream_chat_message_sse
        events = []
        async for event in stream_chat_message_sse("nonexistent_session", "hello"):
            events.append(event)

        raw_data = [e["data"] for e in events]
        assert any("Error" in d or "error" in d.lower() for d in raw_data)
        assert any(d == "[DONE]" for d in raw_data)

    @pytest.mark.asyncio
    async def test_always_ends_with_done_sentinel(self):
        with patch("app.services.agent._astream_llm_with_retry", return_value=None):
            from app.services.agent import stream_chat_message_sse
            events = []
            async for event in stream_chat_message_sse("chat_session", "compare hooks"):
                events.append(event)

        assert events[-1]["data"] == "[DONE]"

    @pytest.mark.asyncio
    async def test_chunk_events_are_valid_json(self):
        with patch("app.services.agent._astream_llm_with_retry", return_value=None):
            from app.services.agent import stream_chat_message_sse
            chunk_events = []
            async for event in stream_chat_message_sse("chat_session", "what is the hook?"):
                data = event["data"]
                if data != "[DONE]":
                    parsed = json.loads(data)
                    chunk_events.append(parsed)

        # Every non-DONE event must have a "chunk" key
        for e in chunk_events:
            assert "chunk" in e
