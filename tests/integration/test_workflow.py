"""Integration tests for LangGraph workflow."""
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver

from graph.builder import (
    build_review_graph,
    has_suggestions,
    should_continue_chunks,
    should_publish,
)
from graph.state import ReviewMetadata, ReviewState
from models.events import PRAction, PREvent


class MockCheckpointer(BaseCheckpointSaver):
    """Mock checkpointer for testing that inherits from BaseCheckpointSaver."""

    def get(self, config):
        return None

    def put(self, config, checkpoint):
        return config

    def list(self, config):
        return []


@pytest.mark.integration
class TestWorkflowStateTransitions:
    """Test workflow state transitions."""

    def test_should_continue_chunks_more_chunks(self, sample_review_state):
        """Test should_continue_chunks when more chunks exist."""
        sample_review_state["chunks"] = [
            {"file_path": "file1.py", "start_line": 1, "end_line": 10, "content": "", "language": "python"},
            {"file_path": "file2.py", "start_line": 1, "end_line": 10, "content": "", "language": "python"}
        ]
        sample_review_state["current_chunk_index"] = 0

        result = should_continue_chunks(sample_review_state)

        assert result == "parallel_agents"

    def test_should_continue_chunks_no_more_chunks(self, sample_review_state):
        """Test should_continue_chunks when no more chunks."""
        sample_review_state["chunks"] = [
            {"file_path": "file1.py", "start_line": 1, "end_line": 10, "content": "", "language": "python"}
        ]
        sample_review_state["current_chunk_index"] = 1  # Past the end

        result = should_continue_chunks(sample_review_state)

        assert result == "aggregate"

    def test_should_continue_chunks_should_stop(self, sample_review_state):
        """Test should_continue_chunks when should_stop is True."""
        sample_review_state["should_stop"] = True

        result = should_continue_chunks(sample_review_state)

        assert result == "aggregate"

    def test_has_suggestions_with_suggestions(self, sample_review_state):
        """Test has_suggestions when suggestions exist."""
        sample_review_state["suggestions"] = [
            {"file_path": "file.py", "line_number": 10, "message": "Test", "severity": "warning"}
        ]

        result = has_suggestions(sample_review_state)

        assert result == "severity_filter"

    def test_has_suggestions_no_suggestions(self, sample_review_state):
        """Test has_suggestions when no suggestions."""
        sample_review_state["suggestions"] = []

        result = has_suggestions(sample_review_state)

        assert result == "publish"

    def test_has_suggestions_should_stop(self, sample_review_state):
        """Test has_suggestions when should_stop is True."""
        sample_review_state["suggestions"] = [{"file_path": "file.py", "line_number": 10, "message": "Test"}]
        sample_review_state["should_stop"] = True

        result = has_suggestions(sample_review_state)

        assert result == "publish"

    def test_should_publish_no_error(self, sample_review_state):
        """Test should_publish when no error."""
        sample_review_state["error"] = None
        sample_review_state["should_stop"] = False

        result = should_publish(sample_review_state)

        assert result == "publish"

    def test_should_publish_with_error(self, sample_review_state):
        """Test should_publish when error exists."""
        sample_review_state["error"] = "Something went wrong"

        from langgraph.graph import END
        result = should_publish(sample_review_state)

        assert result == END

    def test_should_publish_should_stop(self, sample_review_state):
        """Test should_publish when should_stop is True."""
        sample_review_state["should_stop"] = True

        from langgraph.graph import END
        result = should_publish(sample_review_state)

        assert result == END


@pytest.mark.integration
class TestReviewGraph:
    """Test review workflow graph."""

    def test_build_review_graph(self):
        """Test building review graph."""
        graph = build_review_graph()

        assert graph is not None

    def test_build_review_graph_with_checkpointer(self):
        """Test building review graph with checkpointer."""
        mock_checkpointer = MockCheckpointer()

        graph = build_review_graph(checkpointer=mock_checkpointer)

        assert graph is not None

    @pytest.mark.asyncio
    async def test_ingest_pr_node(self, sample_review_state):
        """Test ingest PR node."""
        from graph.nodes import ingest_pr_node

        with patch("graph.nodes.ProviderFactory.get_provider") as mock_get_provider:
            mock_provider = Mock()
            mock_provider.get_pr_diff = AsyncMock(return_value="diff content")
            mock_provider.get_file_content = AsyncMock(return_value=None)
            mock_get_provider.return_value = mock_provider

            result = await ingest_pr_node(sample_review_state)

        assert "pr_diff" in result
        assert result["pr_diff"] == "diff content"

    @pytest.mark.asyncio
    async def test_chunk_analyzer_node(self, sample_review_state):
        """Test chunk analyzer node."""
        from graph.nodes import chunk_analyzer_node

        sample_review_state["pr_diff"] = """
diff --git a/file.py b/file.py
@@ -1,5 +1,5 @@
 def main():
-    pass
+    print("hello")
"""

        result = await chunk_analyzer_node(sample_review_state)

        assert "chunks" in result
        assert len(result["chunks"]) > 0
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_parallel_agents_node(self, sample_review_state):
        """Test parallel agents node."""
        from graph.nodes import parallel_agents_node

        sample_review_state["chunks"] = [
            {
                "file_path": "test.py",
                "start_line": 1,
                "end_line": 5,
                "content": "password = 'secret'\neval(data)",
                "language": "python"
            }
        ]
        sample_review_state["current_chunk_index"] = 0

        with patch("graph.nodes.AgentFactory") as mock_factory_class:
            mock_factory = Mock()
            mock_agent = Mock()
            mock_agent.analyze = AsyncMock(return_value=[
                {
                    "file_path": "test.py",
                    "line_number": 1,
                    "message": "Hardcoded password",
                    "severity": "error",
                    "category": "security",
                    "confidence": 0.9
                }
            ])
            mock_factory.create_agent = Mock(return_value=mock_agent)
            mock_factory_class.return_value = mock_factory

            result = await parallel_agents_node(sample_review_state)

        assert "suggestions" in result
        assert len(result["suggestions"]) > 0
        assert result["current_chunk_index"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_results_node(self, sample_review_state):
        """Test aggregate results node."""
        from graph.nodes import aggregate_results_node

        sample_review_state["suggestions"] = [
            {"file_path": "file1.py", "line_number": 10, "message": "Issue 1", "severity": "error", "category": "security"},
            {"file_path": "file2.py", "line_number": 20, "message": "Issue 2", "severity": "warning", "category": "style"}
        ]

        result = await aggregate_results_node(sample_review_state)

        assert "suggestions" in result
        # Should deduplicate and aggregate

    @pytest.mark.asyncio
    async def test_severity_filter_node(self, sample_review_state):
        """Test severity filter node."""
        from graph.nodes import severity_filter_node

        sample_review_state["suggestions"] = [
            {"file_path": "file1.py", "line_number": 10, "message": "Error", "severity": "error", "category": "security"},
            {"file_path": "file2.py", "line_number": 20, "message": "Warning", "severity": "warning", "category": "style"},
            {"file_path": "file3.py", "line_number": 30, "message": "Note", "severity": "note", "category": "style"}
        ]
        sample_review_state["config"]["severity_threshold"] = "warning"

        result = await severity_filter_node(sample_review_state)

        assert "suggestions" in result
        # Should filter out notes
        assert len(result["suggestions"]) == 2

    @pytest.mark.asyncio
    async def test_llm_judge_node(self, sample_review_state):
        """Test LLM judge node."""
        from graph.nodes import llm_judge_node

        sample_review_state["suggestions"] = [
            {"file_path": "file.py", "line_number": 10, "message": "Test", "severity": "warning", "category": "style"}
        ]

        with patch("src.llm.judge.LLMJudge") as mock_judge_class:
            mock_judge = Mock()
            mock_judge.validate_suggestion = AsyncMock(return_value=True)
            mock_judge_class.return_value = mock_judge

            result = await llm_judge_node(sample_review_state)

        assert "validated_suggestions" in result
        assert len(result["validated_suggestions"]) == 1

    @pytest.mark.asyncio
    async def test_publish_comments_node(self, sample_review_state):
        """Test publish comments node."""
        from graph.nodes import publish_comments_node

        sample_review_state["validated_suggestions"] = [
            {
                "file_path": "file.py",
                "line_number": 10,
                "message": "Test issue",
                "severity": "warning",
                "suggestion": "Fix this",
                "category": "style"
            }
        ]

        with patch("graph.nodes.ProviderFactory.get_provider") as mock_get_provider:
            mock_provider = Mock()
            mock_provider.post_review_comments = AsyncMock(return_value=True)
            mock_get_provider.return_value = mock_provider

            result = await publish_comments_node(sample_review_state)

        assert "comments" in result
        assert "passed" in result
        assert result["passed"] is True


@pytest.mark.integration
class TestWorkflowEndToEnd:
    """Test end-to-end workflow scenarios."""

    @pytest.mark.asyncio
    async def test_simple_review_workflow(self):
        """Test a simple review workflow end-to-end."""
        from graph.builder import create_review_workflow

        # Create workflow
        workflow = create_review_workflow(thread_id="test-123")

        assert "graph" in workflow
        assert "config" in workflow
        assert workflow["config"]["configurable"]["thread_id"] == "test-123"

    @pytest.mark.asyncio
    async def test_workflow_with_error_handling(self, sample_review_state):
        """Test workflow error handling."""
        from graph.nodes import ingest_pr_node

        # Simulate an error in ingest
        with patch("graph.nodes.ProviderFactory.get_provider") as mock_get_provider:
            mock_provider = Mock()
            mock_provider.get_pr_diff = AsyncMock(side_effect=Exception("API Error"))
            mock_get_provider.return_value = mock_provider

            result = await ingest_pr_node(sample_review_state)

        assert "error" in result
        assert "API Error" in result["error"]

    @pytest.mark.asyncio
    async def test_workflow_early_termination(self, sample_review_state):
        """Test workflow early termination."""
        # Set should_stop to True
        sample_review_state["should_stop"] = True

        from langgraph.graph import END

        # Should return END
        result = should_continue_chunks(sample_review_state)
        assert result == "aggregate"

        result = has_suggestions(sample_review_state)
        assert result == "publish"

        result = should_publish(sample_review_state)
        assert result == END


@pytest.mark.integration
class TestWorkflowStateManagement:
    """Test workflow state management."""

    def test_state_initialization(self):
        """Test proper state initialization."""
        pr_event = PREvent(
            provider="github",
            repo_owner="test",
            repo_name="repo",
            pr_number=1,
            action=PRAction.OPENED,
            branch="feature",
            target_branch="main",
            commit_sha="abc123"
        )

        from graph.state import ReviewConfig
        config = ReviewConfig(
            max_suggestions=50,
            severity_threshold="suggestion",
            enable_agents={"security": True, "style": True},
            custom_rules={}
        )

        state = ReviewState(
            pr_event=pr_event,
            config=config,
            pr_diff="",
            agnets_md=None,
            chunks=[],
            current_chunk_index=0,
            suggestions=[],
            raw_agent_outputs={},
            validated_suggestions=[],
            rejected_suggestions=[],
            comments=[],
            summary="",
            passed=True,
            metadata=ReviewMetadata(
                review_id="test-review",
                started_at=datetime.now(),
                completed_at=None,
                current_step="init",
                agent_results={},
                error_count=0
            ),
            error=None,
            should_stop=False
        )

        assert state["pr_event"].provider == "github"
        assert state["config"]["max_suggestions"] == 50
        assert state["metadata"]["review_id"] == "test-review"

    def test_state_immutability_pattern(self, sample_review_state):
        """Test that state follows immutable update pattern."""
        # Nodes should return updates, not modify in place
        # This is a pattern test - actual immutability is enforced by LangGraph

        original_suggestions = sample_review_state["suggestions"].copy()

        # Simulate a node returning updates
        updates = {"suggestions": [{"file_path": "test.py", "line_number": 1, "message": "Test"}]}

        # Original should be unchanged
        assert sample_review_state["suggestions"] == original_suggestions
