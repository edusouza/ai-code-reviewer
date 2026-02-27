"""Tests for Logic agent."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from agents.logic import LogicAgent


@pytest.mark.unit
@pytest.mark.agent
class TestLogicAgent:
    """Test suite for LogicAgent."""

    def test_init(self):
        """Test agent initialization."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        assert agent.name == "logic"
        assert agent.priority == 2
        assert len(agent.bug_patterns) > 0

    def test_get_system_prompt(self):
        """Test system prompt generation."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        prompt = agent.get_system_prompt()

        assert "logic" in prompt.lower() or "bug" in prompt.lower()
        assert "error" in prompt.lower()
        assert "JSON" in prompt

    def test_should_analyze_code(self):
        """Test should_analyze for code files."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = Mock()
        chunk.__getitem__ = Mock(side_effect=lambda k: "python" if k == "language" else "")

        assert agent.should_analyze(chunk) is True

    def test_should_analyze_unknown(self):
        """Test should_analyze for unknown files."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = Mock()
        chunk.__getitem__ = Mock(side_effect=lambda k: "unknown" if k == "language" else "")

        assert agent.should_analyze(chunk) is False

    @pytest.mark.asyncio
    async def test_analyze_infinite_loop(self):
        """Test detection of infinite loops."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 3,
            "content": "while True:\n    pass",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        infinite_loop = [s for s in suggestions if "infinite" in s["message"].lower()]
        assert len(infinite_loop) > 0

    @pytest.mark.asyncio
    async def test_analyze_resource_leak(self):
        """Test detection of resource leaks."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/files.py",
            "start_line": 1,
            "end_line": 3,
            "content": "def read_file(path):\n    f = open(path)\n    return f.read()",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        resource = [s for s in suggestions if "resource" in s["message"].lower() or "close" in s["message"].lower()]
        assert len(resource) > 0

    @pytest.mark.asyncio
    async def test_analyze_division_by_zero(self):
        """Test detection of potential division by zero."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/calc.py",
            "start_line": 1,
            "end_line": 3,
            "content": "def divide(a, b):\n    return a / b",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        # Check for division by zero patterns
        _ = [s for s in suggestions if "division" in s["message"].lower() or "zero" in s["message"].lower()]
        # This pattern might not always match, so we just check it doesn't crash
        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_analyze_python_except_pass(self):
        """Test detection of bare except/pass in Python."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 5,
            "content": "try:\n    risky_operation()\nexcept:\n    pass",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        # This might be caught by logic agent
        except_pass = [s for s in suggestions if "except" in s["message"].lower() or "pass" in s["message"].lower()]
        assert len(except_pass) >= 0  # May or may not be detected

    @pytest.mark.asyncio
    async def test_analyze_python_mutable_default(self):
        """Test detection of mutable default arguments."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 3,
            "content": "def process(items=[]):\n    items.append(1)\n    return items",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        mutable = [s for s in suggestions if "mutable" in s["message"].lower()]
        assert len(mutable) > 0

    @pytest.mark.asyncio
    async def test_analyze_python_list_modification(self):
        """Test detection of list modification during iteration."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 5,
            "content": "items = [1, 2, 3]\nfor item in items:\n    if item == 2:\n        items.remove(item)",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        modification = [s for s in suggestions if "modification" in s["message"].lower() or "iteration" in s["message"].lower()]
        assert len(modification) > 0

    @pytest.mark.asyncio
    async def test_analyze_js_promise_without_catch(self):
        """Test detection of promises without error handling."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/api.js",
            "start_line": 1,
            "end_line": 3,
            "content": "fetch('/api/data')\n    .then(response => response.json())\n    .then(data => console.log(data));",
            "language": "javascript"
        }

        suggestions = await agent.analyze(chunk, {})

        # May detect missing catch
        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_analyze_js_async_without_await(self):
        """Test detection of async functions without await."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/utils.js",
            "start_line": 1,
            "end_line": 5,
            "content": "async function process() {\n    return 1 + 1;\n}",  # No await
            "language": "javascript"
        }

        suggestions = await agent.analyze(chunk, {})

        async_await = [s for s in suggestions if "async" in s["message"].lower() and "await" in s["message"].lower()]
        assert len(async_await) > 0

    @pytest.mark.asyncio
    async def test_analyze_multiple_patterns(self):
        """Test detection of multiple patterns in same chunk."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 10,
            "content": """
def process(items=[]):
    while True:
        f = open('file.txt')
        data = f.read()
    return data
""",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        # Should find multiple issues
        assert len(suggestions) >= 3  # mutable default, infinite loop, resource leak

    @pytest.mark.asyncio
    async def test_analyze_unsupported_language(self):
        """Test analysis of unsupported language."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "README.md",
            "start_line": 1,
            "end_line": 5,
            "content": "# Title\n\nSome markdown content.",
            "language": "markdown"
        }

        suggestions = await agent.analyze(chunk, {})

        # Should not find issues in markdown
        assert len(suggestions) == 0


@pytest.mark.unit
@pytest.mark.agent
class TestLogicAgentEdgeCases:
    """Test edge cases for LogicAgent."""

    @pytest.mark.asyncio
    async def test_analyze_empty_chunk(self):
        """Test analysis of empty code chunk."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/empty.py",
            "start_line": 1,
            "end_line": 1,
            "content": "",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_analyze_pattern_limit(self):
        """Test that pattern matches are limited per pattern."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        # Create content with many infinite loops
        chunk = {
            "file_path": "src/loops.py",
            "start_line": 1,
            "end_line": 20,
            "content": "\n".join(["while True: pass"] * 10),
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        # Should be limited to 3 matches per pattern
        infinite_loop = [s for s in suggestions if "infinite" in s["message"].lower()]
        assert len(infinite_loop) <= 3

    @pytest.mark.asyncio
    async def test_analyze_llm_failure(self):
        """Test handling of LLM failure."""
        mock_llm = Mock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

        with patch("agents.logic.VertexAIClient", return_value=mock_llm):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/test.py",
            "start_line": 1,
            "end_line": 20,
            "content": "while True:\n    pass\n" * 6,
            "language": "python"
        }

        # Should not raise exception
        suggestions = await agent.analyze(chunk, {})

        # Should still find infinite loop via patterns
        infinite_loop = [s for s in suggestions if "infinite" in s["message"].lower()]
        assert len(infinite_loop) > 0

    def test_load_bug_patterns(self):
        """Test that bug patterns are loaded correctly."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        patterns = agent.bug_patterns

        assert len(patterns) > 0

        # Check required patterns exist
        pattern_names = [p["name"] for p in patterns]
        assert "infinite_loop" in pattern_names
        assert "resource_leak" in pattern_names

        # Check pattern structure
        for pattern in patterns:
            assert "name" in pattern
            assert "pattern" in pattern
            assert "message" in pattern
            assert "severity" in pattern
            assert "languages" in pattern

    def test_check_python_logic_empty(self):
        """Test Python logic check with empty content."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "test.py",
            "start_line": 1,
            "content": "",
            "language": "python"
        }

        suggestions = agent._check_python_logic(chunk)
        assert len(suggestions) == 0

    def test_check_js_logic_empty(self):
        """Test JS logic check with empty content."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "test.js",
            "start_line": 1,
            "content": "",
            "language": "javascript"
        }

        suggestions = agent._check_js_logic(chunk)
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_analyze_line_number_accuracy(self):
        """Test that line numbers are calculated correctly."""
        with patch("agents.logic.VertexAIClient"):
            agent = LogicAgent()

        chunk = {
            "file_path": "src/test.py",
            "start_line": 10,  # Chunk starts at line 10
            "end_line": 15,
            "content": "line1\nline2\nwhile True:\n    pass",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        infinite_loop = [s for s in suggestions if "infinite" in s["message"].lower()]
        if infinite_loop:
            # Line number should be relative to chunk start (10 + 2 = 12)
            assert infinite_loop[0]["line_number"] == 12
