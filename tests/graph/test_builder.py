"""Tests for graph.builder module."""

from typing import Any
from unittest.mock import MagicMock, patch

from graph.builder import (
    build_review_graph,
    create_review_workflow,
    has_suggestions,
    should_continue_chunks,
    should_publish,
)
from graph.state import ChunkInfo, ReviewConfig, ReviewMetadata, ReviewState, Suggestion
from models.events import PRAction, PREvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pr_event(**overrides: Any) -> PREvent:
    defaults = {
        "provider": "github",
        "repo_owner": "myorg",
        "repo_name": "myrepo",
        "pr_number": 42,
        "action": PRAction.OPENED,
        "branch": "feature/x",
        "target_branch": "main",
        "commit_sha": "abc123",
    }
    defaults.update(overrides)
    return PREvent(**defaults)


def _make_config(**overrides: Any) -> ReviewConfig:
    defaults: dict[str, Any] = {
        "max_suggestions": 50,
        "severity_threshold": "suggestion",
        "enable_agents": {"security": True, "style": True, "logic": True, "pattern": True},
        "custom_rules": {},
    }
    defaults.update(overrides)
    return ReviewConfig(**defaults)


def _make_metadata(**overrides: Any) -> ReviewMetadata:
    from datetime import datetime

    defaults: dict[str, Any] = {
        "review_id": "test-review-1",
        "started_at": datetime.now(),
        "completed_at": None,
        "current_step": "init",
        "agent_results": {},
        "error_count": 0,
    }
    defaults.update(overrides)
    return ReviewMetadata(**defaults)


def _make_suggestion(**overrides: Any) -> Suggestion:
    defaults: dict[str, Any] = {
        "file_path": "src/main.py",
        "line_number": 10,
        "message": "Some issue",
        "severity": "warning",
        "suggestion": None,
        "agent_type": "security",
        "confidence": 0.9,
        "category": "security",
    }
    defaults.update(overrides)
    return Suggestion(**defaults)


def _make_state(**overrides: Any) -> ReviewState:
    defaults: dict[str, Any] = {
        "pr_event": _make_pr_event(),
        "config": _make_config(),
        "pr_diff": "",
        "agnets_md": None,
        "chunks": [],
        "current_chunk_index": 0,
        "suggestions": [],
        "raw_agent_outputs": {},
        "validated_suggestions": [],
        "rejected_suggestions": [],
        "comments": [],
        "summary": "",
        "passed": True,
        "metadata": _make_metadata(),
        "error": None,
        "should_stop": False,
    }
    defaults.update(overrides)
    return ReviewState(**defaults)


def _make_chunk(**overrides: Any) -> ChunkInfo:
    defaults: dict[str, Any] = {
        "file_path": "src/main.py",
        "start_line": 1,
        "end_line": 10,
        "content": "+code",
        "language": "python",
    }
    defaults.update(overrides)
    return ChunkInfo(**defaults)


# ===========================================================================
# should_continue_chunks
# ===========================================================================
class TestShouldContinueChunks:
    """Tests for the should_continue_chunks conditional edge function."""

    def test_returns_aggregate_when_should_stop_true(self):
        state = _make_state(
            should_stop=True,
            chunks=[_make_chunk()],
            current_chunk_index=0,
        )
        assert should_continue_chunks(state) == "aggregate"

    def test_returns_parallel_agents_when_more_chunks(self):
        state = _make_state(
            chunks=[_make_chunk(), _make_chunk()],
            current_chunk_index=0,
        )
        assert should_continue_chunks(state) == "parallel_agents"

    def test_returns_parallel_agents_when_at_middle_chunk(self):
        state = _make_state(
            chunks=[_make_chunk(), _make_chunk(), _make_chunk()],
            current_chunk_index=1,
        )
        assert should_continue_chunks(state) == "parallel_agents"

    def test_returns_aggregate_when_all_chunks_processed(self):
        state = _make_state(
            chunks=[_make_chunk()],
            current_chunk_index=1,
        )
        assert should_continue_chunks(state) == "aggregate"

    def test_returns_aggregate_when_index_equals_length(self):
        state = _make_state(
            chunks=[_make_chunk(), _make_chunk()],
            current_chunk_index=2,
        )
        assert should_continue_chunks(state) == "aggregate"

    def test_returns_aggregate_when_index_past_end(self):
        state = _make_state(
            chunks=[_make_chunk()],
            current_chunk_index=5,
        )
        assert should_continue_chunks(state) == "aggregate"

    def test_returns_aggregate_when_no_chunks(self):
        state = _make_state(
            chunks=[],
            current_chunk_index=0,
        )
        assert should_continue_chunks(state) == "aggregate"

    def test_handles_missing_should_stop_key(self):
        """When should_stop is not in state (uses .get default False)."""
        state = _make_state(
            chunks=[_make_chunk()],
            current_chunk_index=0,
        )
        state.pop("should_stop", None)
        assert should_continue_chunks(state) == "parallel_agents"

    def test_handles_missing_chunks_key(self):
        """When chunks is not in state (uses .get default [])."""
        state = _make_state(current_chunk_index=0)
        state.pop("chunks", None)
        assert should_continue_chunks(state) == "aggregate"

    def test_handles_missing_index_key(self):
        """When current_chunk_index is not in state (defaults to 0)."""
        state = _make_state(chunks=[_make_chunk()])
        state.pop("current_chunk_index", None)
        assert should_continue_chunks(state) == "parallel_agents"

    def test_should_stop_takes_precedence_over_remaining_chunks(self):
        """Even if there are chunks remaining, should_stop=True forces aggregate."""
        state = _make_state(
            should_stop=True,
            chunks=[_make_chunk(), _make_chunk(), _make_chunk()],
            current_chunk_index=0,
        )
        assert should_continue_chunks(state) == "aggregate"

    def test_last_chunk_boundary(self):
        """When on the last valid index, should still return parallel_agents."""
        state = _make_state(
            chunks=[_make_chunk(), _make_chunk(), _make_chunk()],
            current_chunk_index=2,
        )
        assert should_continue_chunks(state) == "parallel_agents"


# ===========================================================================
# has_suggestions
# ===========================================================================
class TestHasSuggestions:
    """Tests for the has_suggestions conditional edge function."""

    def test_returns_severity_filter_when_suggestions_exist(self):
        state = _make_state(suggestions=[_make_suggestion()])
        assert has_suggestions(state) == "severity_filter"

    def test_returns_publish_when_no_suggestions(self):
        state = _make_state(suggestions=[])
        assert has_suggestions(state) == "publish"

    def test_returns_publish_when_should_stop(self):
        state = _make_state(
            suggestions=[_make_suggestion()],
            should_stop=True,
        )
        assert has_suggestions(state) == "publish"

    def test_returns_publish_when_should_stop_and_no_suggestions(self):
        state = _make_state(
            suggestions=[],
            should_stop=True,
        )
        assert has_suggestions(state) == "publish"

    def test_handles_missing_suggestions_key(self):
        state = _make_state()
        state.pop("suggestions", None)
        assert has_suggestions(state) == "publish"

    def test_handles_missing_should_stop_key(self):
        state = _make_state(suggestions=[_make_suggestion()])
        state.pop("should_stop", None)
        assert has_suggestions(state) == "severity_filter"

    def test_multiple_suggestions(self):
        state = _make_state(
            suggestions=[
                _make_suggestion(message="a"),
                _make_suggestion(message="b"),
            ]
        )
        assert has_suggestions(state) == "severity_filter"


# ===========================================================================
# should_publish
# ===========================================================================
class TestShouldPublish:
    """Tests for the should_publish conditional edge function."""

    def test_returns_end_when_error(self):
        from langgraph.graph import END

        state = _make_state(error="something went wrong")
        assert should_publish(state) == END

    def test_returns_end_when_should_stop(self):
        from langgraph.graph import END

        state = _make_state(should_stop=True)
        assert should_publish(state) == END

    def test_returns_end_when_both_error_and_stop(self):
        from langgraph.graph import END

        state = _make_state(error="err", should_stop=True)
        assert should_publish(state) == END

    def test_returns_publish_when_no_error_and_not_stopped(self):
        state = _make_state(error=None, should_stop=False)
        assert should_publish(state) == "publish"

    def test_handles_missing_error_key(self):
        state = _make_state(should_stop=False)
        state.pop("error", None)
        assert should_publish(state) == "publish"

    def test_handles_missing_should_stop_key(self):
        state = _make_state(error=None)
        state.pop("should_stop", None)
        assert should_publish(state) == "publish"

    def test_empty_string_error_is_falsy(self):
        """Empty string for error is falsy and should not trigger END."""
        state = _make_state(error="", should_stop=False)
        assert should_publish(state) == "publish"

    def test_nonempty_error_triggers_end(self):
        from langgraph.graph import END

        state = _make_state(error="Network failure", should_stop=False)
        assert should_publish(state) == END


# ===========================================================================
# build_review_graph
# ===========================================================================
class TestBuildReviewGraph:
    """Tests for the build_review_graph function."""

    def test_graph_compiles_without_checkpointer(self):
        """Graph should compile and return a runnable object."""
        graph = build_review_graph()
        assert graph is not None

    def test_graph_compiles_with_checkpointer(self):
        """Graph should accept an optional checkpointer."""
        mock_checkpointer = MagicMock(spec=True)
        with patch("graph.builder.StateGraph.compile") as mock_compile:
            mock_compile.return_value = MagicMock()
            graph = build_review_graph(checkpointer=mock_checkpointer)
        assert graph is not None
        mock_compile.assert_called_once_with(checkpointer=mock_checkpointer)

    def test_graph_has_expected_nodes(self):
        """The compiled graph should contain all expected node names."""
        graph = build_review_graph()
        # LangGraph compiled objects store node info; check get_graph() nodes
        graph_data = graph.get_graph()
        node_ids = {node.id for node in graph_data.nodes.values()}

        expected_nodes = {
            "ingest_pr",
            "chunk_analyzer",
            "parallel_agents",
            "aggregate",
            "severity_filter",
            "llm_judge",
            "publish",
        }

        for node_name in expected_nodes:
            assert node_name in node_ids, f"Missing node: {node_name}"

    def test_graph_entry_point(self):
        """The graph should start at ingest_pr."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        # __start__ node should have edge to ingest_pr
        start_edges = [edge for edge in graph_data.edges if edge.source == "__start__"]
        assert len(start_edges) == 1
        assert start_edges[0].target == "ingest_pr"

    def test_ingest_pr_to_chunk_analyzer_edge(self):
        """There should be a direct edge from ingest_pr to chunk_analyzer."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        edges = [
            edge
            for edge in graph_data.edges
            if edge.source == "ingest_pr" and edge.target == "chunk_analyzer"
        ]
        assert len(edges) == 1

    def test_chunk_analyzer_to_parallel_agents_edge(self):
        """There should be a direct edge from chunk_analyzer to parallel_agents."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        edges = [
            edge
            for edge in graph_data.edges
            if edge.source == "chunk_analyzer" and edge.target == "parallel_agents"
        ]
        assert len(edges) == 1

    def test_parallel_agents_conditional_edges(self):
        """parallel_agents should have conditional edges to itself and aggregate."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        pa_edges = [edge for edge in graph_data.edges if edge.source == "parallel_agents"]
        pa_targets = {edge.target for edge in pa_edges}
        assert "parallel_agents" in pa_targets, "Missing loop edge to parallel_agents"
        assert "aggregate" in pa_targets, "Missing edge to aggregate"

    def test_aggregate_conditional_edges(self):
        """aggregate should have conditional edges to severity_filter and publish."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        agg_edges = [edge for edge in graph_data.edges if edge.source == "aggregate"]
        agg_targets = {edge.target for edge in agg_edges}
        assert "severity_filter" in agg_targets, "Missing edge to severity_filter"
        assert "publish" in agg_targets, "Missing edge to publish"

    def test_severity_filter_to_llm_judge_edge(self):
        """There should be a direct edge from severity_filter to llm_judge."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        edges = [
            edge
            for edge in graph_data.edges
            if edge.source == "severity_filter" and edge.target == "llm_judge"
        ]
        assert len(edges) == 1

    def test_llm_judge_to_publish_edge(self):
        """There should be a direct edge from llm_judge to publish."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        edges = [
            edge
            for edge in graph_data.edges
            if edge.source == "llm_judge" and edge.target == "publish"
        ]
        assert len(edges) == 1

    def test_publish_conditional_edge_to_end(self):
        """publish should have a conditional edge to __end__."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        pub_edges = [edge for edge in graph_data.edges if edge.source == "publish"]
        pub_targets = {edge.target for edge in pub_edges}
        assert "__end__" in pub_targets, "Missing edge from publish to __end__"

    def test_total_node_count(self):
        """Verify the total number of defined workflow nodes (excluding __start__/__end__)."""
        graph = build_review_graph()
        graph_data = graph.get_graph()

        workflow_nodes = {
            node.id for node in graph_data.nodes.values() if not node.id.startswith("__")
        }
        assert len(workflow_nodes) == 7


# ===========================================================================
# create_review_workflow
# ===========================================================================
class TestCreateReviewWorkflow:
    """Tests for the create_review_workflow function."""

    def test_returns_dict_with_graph_and_config(self):
        result = create_review_workflow(thread_id="test-thread-123")

        assert "graph" in result
        assert "config" in result
        assert result["config"]["configurable"]["thread_id"] == "test-thread-123"

    def test_graph_is_compiled(self):
        result = create_review_workflow(thread_id="t1")
        graph = result["graph"]
        # A compiled graph should have a get_graph method
        assert hasattr(graph, "get_graph")

    def test_different_thread_ids(self):
        r1 = create_review_workflow(thread_id="thread-1")
        r2 = create_review_workflow(thread_id="thread-2")

        assert r1["config"]["configurable"]["thread_id"] == "thread-1"
        assert r2["config"]["configurable"]["thread_id"] == "thread-2"

    def test_with_checkpointer(self):
        mock_cp = MagicMock(spec=True)
        with patch("graph.builder.StateGraph.compile") as mock_compile:
            mock_compile.return_value = MagicMock()
            result = create_review_workflow(thread_id="t", checkpointer=mock_cp)
        assert result["graph"] is not None

    def test_without_checkpointer(self):
        result = create_review_workflow(thread_id="t")
        assert result["graph"] is not None
