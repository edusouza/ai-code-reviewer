"""Tests for graph.nodes module."""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graph.nodes import (
    _create_summary,
    _detect_language,
    aggregate_results_node,
    chunk_analyzer_node,
    ingest_pr_node,
    llm_judge_node,
    parallel_agents_node,
    publish_comments_node,
    severity_filter_node,
)
from graph.state import ChunkInfo, ReviewConfig, ReviewMetadata, ReviewState, Suggestion
from models.events import PRAction, PREvent, ReviewComment

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


SAMPLE_DIFF = (
    "diff --git a/src/main.py b/src/main.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/main.py\n"
    "+++ b/src/main.py\n"
    "@@ -1,5 +1,10 @@\n"
    "+    password = 'secret'\n"
    "+    run(data)\n"
)

MULTI_FILE_DIFF = (
    "diff --git a/src/main.py b/src/main.py\n"
    "--- a/src/main.py\n"
    "+++ b/src/main.py\n"
    "@@ -1,5 +1,10 @@\n"
    "+added line python\n"
    "diff --git a/src/utils.js b/src/utils.js\n"
    "--- a/src/utils.js\n"
    "+++ b/src/utils.js\n"
    "@@ -10,3 +10,5 @@\n"
    "+added line js\n"
)


# ===========================================================================
# _detect_language
# ===========================================================================
class TestDetectLanguage:
    """Tests for the _detect_language helper function."""

    @pytest.mark.parametrize(
        "file_path, expected",
        [
            ("main.py", "python"),
            ("app.js", "javascript"),
            ("component.ts", "typescript"),
            ("component.tsx", "typescript"),
            ("component.jsx", "javascript"),
            ("Main.java", "java"),
            ("main.go", "go"),
            ("lib.rs", "rust"),
            ("core.cpp", "cpp"),
            ("core.c", "c"),
            ("header.h", "c"),
            ("app.rb", "ruby"),
            ("index.php", "php"),
            ("app.swift", "swift"),
            ("main.kt", "kotlin"),
            ("main.scala", "scala"),
        ],
    )
    def test_known_extensions(self, file_path: str, expected: str):
        assert _detect_language(file_path) == expected

    def test_unknown_extension(self):
        assert _detect_language("README.md") == "unknown"
        assert _detect_language("Makefile") == "unknown"
        assert _detect_language("data.csv") == "unknown"

    def test_nested_path(self):
        assert _detect_language("src/deep/module.py") == "python"


# ===========================================================================
# _create_summary
# ===========================================================================
class TestCreateSummary:
    """Tests for the _create_summary helper function."""

    def test_no_comments(self):
        summary = _create_summary([])
        assert "Errors:** 0" in summary
        assert "Warnings:** 0" in summary
        assert "Suggestions:** 0" in summary
        assert "All checks passed!" in summary

    def test_errors_present(self):
        comments = [
            ReviewComment(file_path="a.py", line_number=1, message="bad", severity="error"),
        ]
        summary = _create_summary(comments)
        assert "Errors:** 1" in summary
        assert "address the errors" in summary

    def test_warnings_only(self):
        comments = [
            ReviewComment(file_path="a.py", line_number=1, message="hmm", severity="warning"),
        ]
        summary = _create_summary(comments)
        assert "Warnings:** 1" in summary
        assert "consider addressing the warnings" in summary

    def test_suggestions_only(self):
        comments = [
            ReviewComment(file_path="a.py", line_number=1, message="maybe", severity="suggestion"),
        ]
        summary = _create_summary(comments)
        assert "Suggestions:** 1" in summary
        assert "All checks passed!" in summary

    def test_mixed_severities(self):
        comments = [
            ReviewComment(file_path="a.py", line_number=1, message="x", severity="error"),
            ReviewComment(file_path="b.py", line_number=2, message="y", severity="warning"),
            ReviewComment(file_path="c.py", line_number=3, message="z", severity="suggestion"),
        ]
        summary = _create_summary(comments)
        assert "Errors:** 1" in summary
        assert "Warnings:** 1" in summary
        assert "Suggestions:** 1" in summary
        # Errors take precedence in the message
        assert "address the errors" in summary


# ===========================================================================
# ingest_pr_node
# ===========================================================================
@pytest.mark.asyncio
class TestIngestPrNode:
    """Tests for the ingest_pr_node function."""

    async def test_happy_path_with_agents_md(self):
        mock_provider = AsyncMock()
        mock_provider.get_pr_diff = AsyncMock(return_value="diff content")
        mock_provider.get_file_content = AsyncMock(return_value="# AGENTS.md content")

        state = _make_state()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await ingest_pr_node(state)

        assert result["pr_diff"] == "diff content"
        assert result["agnets_md"] == "# AGENTS.md content"
        assert result["error"] is None
        assert result["should_stop"] is False
        assert result["current_chunk_index"] == 0
        assert result["chunks"] == []
        assert result["suggestions"] == []
        assert result["raw_agent_outputs"] == {}
        assert result["validated_suggestions"] == []
        assert result["rejected_suggestions"] == []
        assert result["comments"] == []
        assert "metadata" in result
        assert result["metadata"]["current_step"] == "ingest_pr"

    async def test_agents_md_not_found(self):
        """When AGENTS.md does not exist, agnets_md should be None."""
        mock_provider = AsyncMock()
        mock_provider.get_pr_diff = AsyncMock(return_value="diff content")
        mock_provider.get_file_content = AsyncMock(side_effect=FileNotFoundError("not found"))

        state = _make_state()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await ingest_pr_node(state)

        assert result["pr_diff"] == "diff content"
        assert result["agnets_md"] is None
        assert result["error"] is None

    async def test_config_initialized_when_missing(self):
        """When state has no config, default config is created."""
        mock_provider = AsyncMock()
        mock_provider.get_pr_diff = AsyncMock(return_value="diff")
        mock_provider.get_file_content = AsyncMock(side_effect=Exception())

        state = _make_state()
        # Remove config to trigger default initialisation
        state["config"] = None  # type: ignore[typeddict-item]

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await ingest_pr_node(state)

        assert result["config"]["max_suggestions"] == 50
        assert result["config"]["severity_threshold"] == "suggestion"
        assert result["config"]["enable_agents"]["security"] is True

    async def test_config_preserved_when_present(self):
        custom_config = _make_config(max_suggestions=10, severity_threshold="error")
        state = _make_state(config=custom_config)

        mock_provider = AsyncMock()
        mock_provider.get_pr_diff = AsyncMock(return_value="diff")
        mock_provider.get_file_content = AsyncMock(side_effect=Exception())

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await ingest_pr_node(state)

        assert result["config"]["max_suggestions"] == 10
        assert result["config"]["severity_threshold"] == "error"

    async def test_metadata_review_id_format(self):
        mock_provider = AsyncMock()
        mock_provider.get_pr_diff = AsyncMock(return_value="d")
        mock_provider.get_file_content = AsyncMock(side_effect=Exception())

        state = _make_state()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await ingest_pr_node(state)

        rid = result["metadata"]["review_id"]
        assert rid.startswith("github_myorg_myrepo_42_")

    async def test_error_on_provider_failure(self):
        """When get_pr_diff fails, error is captured and should_stop is True."""
        state = _make_state()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.side_effect = RuntimeError("boom")
            result = await ingest_pr_node(state)

        assert "Failed to ingest PR" in result["error"]
        assert result["should_stop"] is True

    async def test_provider_called_with_correct_args(self):
        """Verify provider is called with correct repo info."""
        mock_provider = AsyncMock()
        mock_provider.get_pr_diff = AsyncMock(return_value="diff")
        mock_provider.get_file_content = AsyncMock(side_effect=Exception())

        pr_event = _make_pr_event(
            repo_owner="org", repo_name="repo", pr_number=7, commit_sha="sha1"
        )
        state = _make_state(pr_event=pr_event)

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            await ingest_pr_node(state)

        mock_provider.get_pr_diff.assert_awaited_once_with("org", "repo", 7)
        mock_provider.get_file_content.assert_awaited_once_with("org", "repo", "AGENTS.md", "sha1")


# ===========================================================================
# chunk_analyzer_node
# ===========================================================================
@pytest.mark.asyncio
class TestChunkAnalyzerNode:
    """Tests for the chunk_analyzer_node function."""

    async def test_empty_diff(self):
        state = _make_state(pr_diff="")
        result = await chunk_analyzer_node(state)
        assert result["should_stop"] is True
        assert "No PR diff" in result["error"]

    async def test_none_diff(self):
        state = _make_state()
        # pr_diff defaults to "" via .get()
        result = await chunk_analyzer_node(state)
        assert result["should_stop"] is True

    async def test_single_file_single_hunk(self):
        state = _make_state(pr_diff=SAMPLE_DIFF)
        result = await chunk_analyzer_node(state)

        assert "chunks" in result
        assert len(result["chunks"]) == 1

        chunk = result["chunks"][0]
        assert chunk["file_path"] == "src/main.py"
        assert chunk["language"] == "python"
        assert "+    password" in chunk["content"]

    async def test_multi_file_diff(self):
        state = _make_state(pr_diff=MULTI_FILE_DIFF)
        result = await chunk_analyzer_node(state)

        assert len(result["chunks"]) == 2
        paths = {c["file_path"] for c in result["chunks"]}
        assert "src/main.py" in paths
        assert "src/utils.js" in paths

        # Check language detection
        langs = {c["file_path"]: c["language"] for c in result["chunks"]}
        assert langs["src/main.py"] == "python"
        assert langs["src/utils.js"] == "javascript"

    async def test_hunk_header_line_number_extraction(self):
        diff = "diff --git a/f.py b/f.py\n@@ -5,3 +42,7 @@\n+new line\n"
        state = _make_state(pr_diff=diff)
        result = await chunk_analyzer_node(state)

        chunk = result["chunks"][0]
        assert chunk["start_line"] == 42

    async def test_hunk_header_bad_format(self):
        """Malformed hunk header should not crash."""
        diff = "diff --git a/f.py b/f.py\n@@ BADFORMAT @@\n+new line\n"
        state = _make_state(pr_diff=diff)
        result = await chunk_analyzer_node(state)

        # Should still produce a chunk, start_line stays at 0
        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["start_line"] == 0

    async def test_context_lines_ignored(self):
        """Lines not starting with + or - (context) are ignored in chunk content,
        except hunk headers which are included."""
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1,5 +1,5 @@\n"
            " context line\n"
            "+added line\n"
            "-removed line\n"
            " another context\n"
        )
        state = _make_state(pr_diff=diff)
        result = await chunk_analyzer_node(state)

        content = result["chunks"][0]["content"]
        assert "context line" not in content
        assert "+added line" in content
        assert "-removed line" in content

    async def test_metadata_updated(self):
        state = _make_state(pr_diff=SAMPLE_DIFF)
        result = await chunk_analyzer_node(state)

        assert result["metadata"]["current_step"] == "chunk_analyzer"

    async def test_end_line_calculation(self):
        diff = "diff --git a/f.py b/f.py\n@@ -1,5 +10,5 @@\n+line1\n+line2\n+line3\n"
        state = _make_state(pr_diff=diff)
        result = await chunk_analyzer_node(state)

        chunk = result["chunks"][0]
        # start_line=10, hunk header + 3 added lines = 4 content lines total
        # end_line = start_line + (len(content) - 1) = 10 + 3 = 13
        assert chunk["start_line"] == 10
        assert chunk["end_line"] == 10 + 3  # 4 content items, end = 10 + 3

    async def test_diff_with_only_removals(self):
        diff = "diff --git a/f.py b/f.py\n@@ -1,5 +1,2 @@\n-removed1\n-removed2\n"
        state = _make_state(pr_diff=diff)
        result = await chunk_analyzer_node(state)

        assert len(result["chunks"]) == 1
        content = result["chunks"][0]["content"]
        assert "-removed1" in content
        assert "-removed2" in content

    async def test_diff_no_changes_no_chunks(self):
        """A diff header with no +/- lines produces no chunks."""
        diff = "diff --git a/f.py b/f.py\nindex 123..456 100644\n"
        state = _make_state(pr_diff=diff)
        result = await chunk_analyzer_node(state)

        assert result["chunks"] == []


# ===========================================================================
# parallel_agents_node
# ===========================================================================
@pytest.mark.asyncio
class TestParallelAgentsNode:
    """Tests for the parallel_agents_node function."""

    async def test_no_chunks_stops(self):
        state = _make_state(chunks=[], current_chunk_index=0)
        result = await parallel_agents_node(state)
        assert result["should_stop"] is True

    async def test_index_past_end_stops(self):
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+x",
            "language": "python",
        }
        state = _make_state(chunks=[chunk], current_chunk_index=1)
        result = await parallel_agents_node(state)
        assert result["should_stop"] is True

    async def test_agents_run_concurrently(self):
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+code",
            "language": "python",
        }
        suggestion = _make_suggestion()

        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "SecurityAgent"
        mock_agent.analyze = AsyncMock(return_value=[suggestion])

        state = _make_state(
            chunks=[chunk],
            current_chunk_index=0,
            config=_make_config(
                enable_agents={"security": True, "style": False, "logic": False, "pattern": False}
            ),
        )

        with patch("graph.nodes.AgentFactory") as mock_factory_cls:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create_agent.return_value = mock_agent
            mock_factory_cls.return_value = mock_factory_instance

            result = await parallel_agents_node(state)

        assert len(result["suggestions"]) == 1
        assert result["current_chunk_index"] == 1
        assert "chunk_0" in result["metadata"]["agent_results"]

    async def test_agent_exception_handled_gracefully(self):
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+code",
            "language": "python",
        }

        mock_agent_good = MagicMock()
        mock_agent_good.__class__.__name__ = "StyleAgent"
        mock_agent_good.analyze = AsyncMock(
            return_value=[_make_suggestion(agent_type="style", category="style")]
        )

        mock_agent_bad = MagicMock()
        mock_agent_bad.__class__.__name__ = "SecurityAgent"
        mock_agent_bad.analyze = AsyncMock(side_effect=RuntimeError("agent crash"))

        state = _make_state(
            chunks=[chunk],
            current_chunk_index=0,
            config=_make_config(
                enable_agents={"security": True, "style": True, "logic": False, "pattern": False}
            ),
        )

        with patch("graph.nodes.AgentFactory") as mock_factory_cls:
            mock_factory_instance = MagicMock()
            # Return bad agent for security, good agent for style
            mock_factory_instance.create_agent.side_effect = [mock_agent_bad, mock_agent_good]
            mock_factory_cls.return_value = mock_factory_instance

            result = await parallel_agents_node(state)

        # The good agent's suggestion should still be present
        assert len(result["suggestions"]) >= 1
        # No error key (handled gracefully)
        assert "error" not in result or result.get("error") is None

    async def test_all_agents_disabled(self):
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+code",
            "language": "python",
        }

        state = _make_state(
            chunks=[chunk],
            current_chunk_index=0,
            config=_make_config(
                enable_agents={"security": False, "style": False, "logic": False, "pattern": False}
            ),
        )

        with patch("graph.nodes.AgentFactory") as mock_factory_cls:
            mock_factory_instance = MagicMock()
            mock_factory_cls.return_value = mock_factory_instance

            result = await parallel_agents_node(state)

        assert result["suggestions"] == []
        assert result["current_chunk_index"] == 1

    async def test_suggestions_accumulate_across_chunks(self):
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+code",
            "language": "python",
        }
        existing_suggestion = _make_suggestion(message="existing")
        new_suggestion = _make_suggestion(message="new")

        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "SecurityAgent"
        mock_agent.analyze = AsyncMock(return_value=[new_suggestion])

        state = _make_state(
            chunks=[chunk],
            current_chunk_index=0,
            suggestions=[existing_suggestion],
            config=_make_config(
                enable_agents={"security": True, "style": False, "logic": False, "pattern": False}
            ),
        )

        with patch("graph.nodes.AgentFactory") as mock_factory_cls:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create_agent.return_value = mock_agent
            mock_factory_cls.return_value = mock_factory_instance

            result = await parallel_agents_node(state)

        assert len(result["suggestions"]) == 2

    async def test_raw_outputs_stored_by_agent_type(self):
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+code",
            "language": "python",
        }
        suggestion = _make_suggestion()

        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "SecurityAgent"
        mock_agent.analyze = AsyncMock(return_value=[suggestion])

        state = _make_state(
            chunks=[chunk],
            current_chunk_index=0,
            config=_make_config(
                enable_agents={"security": True, "style": False, "logic": False, "pattern": False}
            ),
        )

        with patch("graph.nodes.AgentFactory") as mock_factory_cls:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create_agent.return_value = mock_agent
            mock_factory_cls.return_value = mock_factory_instance

            result = await parallel_agents_node(state)

        # "SecurityAgent" -> lower + replace "agent" -> "security"
        assert "security" in result["raw_agent_outputs"]
        assert len(result["raw_agent_outputs"]["security"]) == 1

    async def test_error_increments_chunk_index(self):
        """On top-level error, chunk_index still advances to avoid infinite loop."""
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+code",
            "language": "python",
        }
        state = _make_state(
            chunks=[chunk, chunk, chunk],
            current_chunk_index=2,
        )

        with patch("graph.nodes.AgentFactory") as mock_factory_cls:
            mock_factory_cls.side_effect = RuntimeError("factory boom")
            result = await parallel_agents_node(state)

        # chunk index should have been incremented past the failing chunk
        assert result["current_chunk_index"] == 3
        assert "Failed to run agents" in result["error"]

    async def test_agnets_md_passed_in_context(self):
        """Verify that agnets_md is passed to agents through context."""
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+code",
            "language": "python",
        }

        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "SecurityAgent"
        mock_agent.analyze = AsyncMock(return_value=[])

        state = _make_state(
            chunks=[chunk],
            current_chunk_index=0,
            agnets_md="# Custom rules",
            config=_make_config(
                enable_agents={"security": True, "style": False, "logic": False, "pattern": False}
            ),
        )

        with patch("graph.nodes.AgentFactory") as mock_factory_cls:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create_agent.return_value = mock_agent
            mock_factory_cls.return_value = mock_factory_instance

            await parallel_agents_node(state)

        # Verify context passed to analyze
        call_args = mock_agent.analyze.call_args
        context = call_args[0][1]
        assert context["agnets_md"] == "# Custom rules"
        assert context["chunk_index"] == 0
        assert context["total_chunks"] == 1

    async def test_multiple_agents_enabled(self):
        chunk: ChunkInfo = {
            "file_path": "a.py",
            "start_line": 1,
            "end_line": 5,
            "content": "+code",
            "language": "python",
        }

        mock_agents = []
        for name in ["SecurityAgent", "StyleAgent", "LogicAgent", "PatternAgent"]:
            agent = MagicMock()
            agent.__class__.__name__ = name
            agent.analyze = AsyncMock(
                return_value=[_make_suggestion(agent_type=name.lower().replace("agent", ""))]
            )
            mock_agents.append(agent)

        state = _make_state(
            chunks=[chunk],
            current_chunk_index=0,
            config=_make_config(
                enable_agents={"security": True, "style": True, "logic": True, "pattern": True}
            ),
        )

        with patch("graph.nodes.AgentFactory") as mock_factory_cls:
            mock_factory_instance = MagicMock()
            mock_factory_instance.create_agent.side_effect = mock_agents
            mock_factory_cls.return_value = mock_factory_instance

            result = await parallel_agents_node(state)

        assert len(result["suggestions"]) == 4
        assert result["metadata"]["agent_results"]["chunk_0"]["agents_run"] == 4
        assert result["metadata"]["agent_results"]["chunk_0"]["suggestions_found"] == 4


# ===========================================================================
# aggregate_results_node
# ===========================================================================
@pytest.mark.asyncio
class TestAggregateResultsNode:
    """Tests for the aggregate_results_node function."""

    async def test_empty_suggestions(self):
        state = _make_state(suggestions=[])
        with patch("graph.nodes.Deduplicator") as mock_cls:
            mock_cls.return_value.deduplicate.return_value = []
            result = await aggregate_results_node(state)

        assert result["suggestions"] == []
        assert result["metadata"]["current_step"] == "aggregate"

    async def test_deduplication_called(self):
        suggestions = [_make_suggestion(message="dup"), _make_suggestion(message="dup")]
        state = _make_state(suggestions=suggestions)

        with patch("graph.nodes.Deduplicator") as mock_cls:
            mock_dedup = MagicMock()
            mock_dedup.deduplicate.return_value = [suggestions[0]]
            mock_cls.return_value = mock_dedup

            result = await aggregate_results_node(state)

        mock_dedup.deduplicate.assert_called_once_with(suggestions)
        assert len(result["suggestions"]) == 1

    async def test_error_handling(self):
        state = _make_state(suggestions=[_make_suggestion()])

        with patch("graph.nodes.Deduplicator") as mock_cls:
            mock_cls.side_effect = RuntimeError("boom")
            result = await aggregate_results_node(state)

        assert "Failed to aggregate" in result["error"]


# ===========================================================================
# severity_filter_node
# ===========================================================================
@pytest.mark.asyncio
class TestSeverityFilterNode:
    """Tests for the severity_filter_node function."""

    async def test_filters_by_threshold(self):
        suggestions = [
            _make_suggestion(severity="error"),
            _make_suggestion(severity="warning"),
            _make_suggestion(severity="suggestion"),
        ]
        state = _make_state(
            suggestions=suggestions,
            config=_make_config(severity_threshold="warning"),
        )

        with patch("graph.nodes.SeverityClassifier") as mock_cls:
            mock_inst = MagicMock()
            # Only return the first two (error and warning pass threshold)
            mock_inst.filter_by_threshold.return_value = suggestions[:2]
            mock_cls.return_value = mock_inst

            result = await severity_filter_node(state)

        mock_inst.filter_by_threshold.assert_called_once_with(suggestions, "warning")
        assert len(result["suggestions"]) == 2

    async def test_max_suggestions_limit(self):
        suggestions = [_make_suggestion(message=f"s{i}") for i in range(100)]
        state = _make_state(
            suggestions=suggestions,
            config=_make_config(max_suggestions=5),
        )

        with patch("graph.nodes.SeverityClassifier") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.filter_by_threshold.return_value = suggestions
            mock_cls.return_value = mock_inst

            result = await severity_filter_node(state)

        assert len(result["suggestions"]) == 5

    async def test_default_threshold_used(self):
        state = _make_state(
            suggestions=[_make_suggestion()],
            config=_make_config(),
        )

        with patch("graph.nodes.SeverityClassifier") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.filter_by_threshold.return_value = [_make_suggestion()]
            mock_cls.return_value = mock_inst

            await severity_filter_node(state)

        mock_inst.filter_by_threshold.assert_called_once_with(state["suggestions"], "suggestion")

    async def test_metadata_updated(self):
        state = _make_state(suggestions=[])

        with patch("graph.nodes.SeverityClassifier") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.filter_by_threshold.return_value = []
            mock_cls.return_value = mock_inst

            result = await severity_filter_node(state)

        assert result["metadata"]["current_step"] == "severity_filter"

    async def test_error_handling(self):
        state = _make_state(suggestions=[_make_suggestion()])

        with patch("graph.nodes.SeverityClassifier") as mock_cls:
            mock_cls.side_effect = RuntimeError("boom")
            result = await severity_filter_node(state)

        assert "Failed to filter by severity" in result["error"]

    async def test_max_less_than_filtered(self):
        """When max_suggestions < filtered count, results are truncated."""
        suggestions = [_make_suggestion(message=f"s{i}") for i in range(10)]
        state = _make_state(
            suggestions=suggestions,
            config=_make_config(max_suggestions=3),
        )

        with patch("graph.nodes.SeverityClassifier") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.filter_by_threshold.return_value = suggestions
            mock_cls.return_value = mock_inst

            result = await severity_filter_node(state)

        assert len(result["suggestions"]) == 3
        # Verify the first 3 are returned (order preserved)
        assert result["suggestions"][0]["message"] == "s0"
        assert result["suggestions"][2]["message"] == "s2"


# ===========================================================================
# llm_judge_node
# ===========================================================================
@pytest.mark.asyncio
class TestLlmJudgeNode:
    """Tests for the llm_judge_node function."""

    async def test_empty_suggestions(self):
        state = _make_state(suggestions=[])
        result = await llm_judge_node(state)

        assert result["validated_suggestions"] == []
        assert result["rejected_suggestions"] == []

    async def test_all_validated(self):
        suggestions = [_make_suggestion(message="ok1"), _make_suggestion(message="ok2")]
        state = _make_state(suggestions=suggestions)

        with patch("src.llm.judge.LLMJudge") as mock_cls:
            mock_judge = MagicMock()
            mock_judge.validate_suggestion = AsyncMock(return_value=True)
            mock_cls.return_value = mock_judge

            result = await llm_judge_node(state)

        assert len(result["validated_suggestions"]) == 2
        assert len(result["rejected_suggestions"]) == 0
        assert result["suggestions"] == result["validated_suggestions"]

    async def test_some_rejected(self):
        suggestions = [
            _make_suggestion(message="good"),
            _make_suggestion(message="bad"),
        ]
        state = _make_state(suggestions=suggestions)

        async def validate_side_effect(s):
            return s["message"] == "good"

        with patch("src.llm.judge.LLMJudge") as mock_cls:
            mock_judge = MagicMock()
            mock_judge.validate_suggestion = AsyncMock(side_effect=validate_side_effect)
            mock_cls.return_value = mock_judge

            result = await llm_judge_node(state)

        assert len(result["validated_suggestions"]) == 1
        assert len(result["rejected_suggestions"]) == 1
        assert result["validated_suggestions"][0]["message"] == "good"
        assert result["rejected_suggestions"][0]["message"] == "bad"

    async def test_all_rejected(self):
        suggestions = [_make_suggestion()]
        state = _make_state(suggestions=suggestions)

        with patch("src.llm.judge.LLMJudge") as mock_cls:
            mock_judge = MagicMock()
            mock_judge.validate_suggestion = AsyncMock(return_value=False)
            mock_cls.return_value = mock_judge

            result = await llm_judge_node(state)

        assert len(result["validated_suggestions"]) == 0
        assert len(result["rejected_suggestions"]) == 1
        assert result["suggestions"] == []

    async def test_metadata_updated(self):
        suggestions = [_make_suggestion()]
        state = _make_state(suggestions=suggestions)

        with patch("src.llm.judge.LLMJudge") as mock_cls:
            mock_judge = MagicMock()
            mock_judge.validate_suggestion = AsyncMock(return_value=True)
            mock_cls.return_value = mock_judge

            result = await llm_judge_node(state)

        assert result["metadata"]["current_step"] == "llm_judge"

    async def test_error_falls_back_to_accepting(self):
        """On error, all existing suggestions are validated."""
        suggestions = [_make_suggestion(), _make_suggestion(message="s2")]
        state = _make_state(suggestions=suggestions)

        with patch("src.llm.judge.LLMJudge") as mock_cls:
            mock_cls.side_effect = RuntimeError("judge is down")
            result = await llm_judge_node(state)

        assert "Failed to validate suggestions" in result["error"]
        assert result["validated_suggestions"] == suggestions
        assert result["rejected_suggestions"] == []

    async def test_each_suggestion_validated_individually(self):
        """Verify validate_suggestion is called once per suggestion."""
        suggestions = [
            _make_suggestion(message="a"),
            _make_suggestion(message="b"),
            _make_suggestion(message="c"),
        ]
        state = _make_state(suggestions=suggestions)

        with patch("src.llm.judge.LLMJudge") as mock_cls:
            mock_judge = MagicMock()
            mock_judge.validate_suggestion = AsyncMock(return_value=True)
            mock_cls.return_value = mock_judge

            await llm_judge_node(state)

        assert mock_judge.validate_suggestion.await_count == 3


# ===========================================================================
# publish_comments_node
# ===========================================================================
@pytest.mark.asyncio
class TestPublishCommentsNode:
    """Tests for the publish_comments_node function."""

    async def test_happy_path_no_errors(self):
        suggestions = [
            _make_suggestion(severity="suggestion", suggestion="fix it"),
        ]
        state = _make_state(validated_suggestions=suggestions)

        mock_provider = AsyncMock()
        mock_provider.post_review_comments = AsyncMock()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await publish_comments_node(state)

        assert result["passed"] is True
        assert len(result["comments"]) == 1
        assert "All checks passed!" in result["summary"]
        assert result["metadata"]["current_step"] == "publish"
        assert result["metadata"]["completed_at"] is not None
        mock_provider.post_review_comments.assert_awaited_once()

    async def test_with_errors_fails_passed(self):
        suggestions = [
            _make_suggestion(severity="error"),
        ]
        state = _make_state(validated_suggestions=suggestions)

        mock_provider = AsyncMock()
        mock_provider.post_review_comments = AsyncMock()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await publish_comments_node(state)

        assert result["passed"] is False
        assert "address the errors" in result["summary"]

    async def test_falls_back_to_suggestions_when_no_validated(self):
        """If validated_suggestions is absent, falls back to suggestions."""
        suggestions = [_make_suggestion(severity="warning")]
        state = _make_state(suggestions=suggestions)
        # Remove validated_suggestions by not including it
        state.pop("validated_suggestions", None)

        mock_provider = AsyncMock()
        mock_provider.post_review_comments = AsyncMock()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await publish_comments_node(state)

        assert len(result["comments"]) == 1

    async def test_converts_suggestions_to_review_comments(self):
        suggestion = _make_suggestion(
            file_path="x.py",
            line_number=42,
            message="fix this",
            severity="warning",
            suggestion="better code",
        )
        state = _make_state(validated_suggestions=[suggestion])

        mock_provider = AsyncMock()
        mock_provider.post_review_comments = AsyncMock()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await publish_comments_node(state)

        comment = result["comments"][0]
        assert comment.file_path == "x.py"
        assert comment.line_number == 42
        assert comment.message == "fix this"
        assert comment.severity == "warning"
        assert comment.suggestion == "better code"

    async def test_suggestion_field_none_when_absent(self):
        suggestion = _make_suggestion(suggestion=None)
        state = _make_state(validated_suggestions=[suggestion])

        mock_provider = AsyncMock()
        mock_provider.post_review_comments = AsyncMock()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await publish_comments_node(state)

        assert result["comments"][0].suggestion is None

    async def test_error_on_publish_failure(self):
        suggestion = _make_suggestion()
        state = _make_state(validated_suggestions=[suggestion])

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.side_effect = RuntimeError("post failed")
            result = await publish_comments_node(state)

        assert "Failed to publish comments" in result["error"]
        assert result["should_stop"] is True

    async def test_empty_suggestions_published(self):
        state = _make_state(validated_suggestions=[])

        mock_provider = AsyncMock()
        mock_provider.post_review_comments = AsyncMock()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await publish_comments_node(state)

        assert result["passed"] is True
        assert result["comments"] == []
        assert "All checks passed!" in result["summary"]

    async def test_provider_called_with_correct_args(self):
        suggestion = _make_suggestion()
        pr_event = _make_pr_event(repo_owner="owner", repo_name="repo", pr_number=99)
        state = _make_state(pr_event=pr_event, validated_suggestions=[suggestion])

        mock_provider = AsyncMock()
        mock_provider.post_review_comments = AsyncMock()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            await publish_comments_node(state)

        mock_provider.post_review_comments.assert_awaited_once()
        call_args = mock_provider.post_review_comments.call_args
        assert call_args[0][0] == "owner"
        assert call_args[0][1] == "repo"
        assert call_args[0][2] == 99

    async def test_multiple_suggestions_converted(self):
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=1, severity="error"),
            _make_suggestion(file_path="b.py", line_number=2, severity="warning"),
            _make_suggestion(file_path="c.py", line_number=3, severity="suggestion"),
        ]
        state = _make_state(validated_suggestions=suggestions)

        mock_provider = AsyncMock()
        mock_provider.post_review_comments = AsyncMock()

        with patch("graph.nodes.ProviderFactory") as mock_factory:
            mock_factory.get_provider.return_value = mock_provider
            result = await publish_comments_node(state)

        assert len(result["comments"]) == 3
        assert result["passed"] is False  # has errors
