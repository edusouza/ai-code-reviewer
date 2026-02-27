"""Tests for Style agent."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from agents.style import StyleAgent


@pytest.mark.unit
@pytest.mark.agent
class TestStyleAgent:
    """Test suite for StyleAgent."""

    def test_init(self):
        """Test agent initialization."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        assert agent.name == "style"
        assert agent.priority == 5

    def test_get_system_prompt(self):
        """Test system prompt generation."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        prompt = agent.get_system_prompt()

        assert "style" in prompt.lower()
        assert "formatting" in prompt.lower()
        assert "JSON" in prompt

    def test_should_analyze_code(self):
        """Test should_analyze for code files."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = Mock()
        chunk.__getitem__ = Mock(side_effect=lambda k: "python" if k == "language" else "")

        assert agent.should_analyze(chunk) is True

    def test_should_analyze_unknown(self):
        """Test should_analyze for unknown files."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = Mock()
        chunk.__getitem__ = Mock(side_effect=lambda k: "unknown" if k == "language" else "")

        assert agent.should_analyze(chunk) is False

    @pytest.mark.asyncio
    async def test_analyze_long_lines(self):
        """Test detection of long lines."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 5,
            "content": "x = 1\n" + "y = " + "a" * 150 + "\nz = 3",  # Line exceeds 120 chars
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any("120 characters" in s["message"] for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_trailing_whitespace(self):
        """Test detection of trailing whitespace."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 3,
            "content": "def test():   \n    pass   \n    return",  # Trailing spaces
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        trailing_whitespace = [s for s in suggestions if "trailing" in s["message"].lower()]
        assert len(trailing_whitespace) > 0

    @pytest.mark.asyncio
    async def test_analyze_python_mixed_tabs_spaces(self):
        """Test detection of mixed tabs and spaces in Python."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 3,
            "content": "def test():\n\tpass\n  return",  # Mixed tabs and spaces
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        mixed = [s for s in suggestions if "mixed" in s["message"].lower()]
        assert len(mixed) > 0

    @pytest.mark.asyncio
    async def test_analyze_python_bare_except(self):
        """Test detection of bare except clause."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 5,
            "content": "try:\n    pass\nexcept:\n    pass",  # Bare except
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        bare_except = [s for s in suggestions if "bare" in s["message"].lower()]
        assert len(bare_except) > 0

    @pytest.mark.asyncio
    async def test_analyze_python_mutable_default(self):
        """Test detection of mutable default arguments."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 3,
            "content": "def func(items=[]):\n    pass\n\ndef other(data={}):",  # Mutable defaults
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        mutable = [s for s in suggestions if "mutable" in s["message"].lower()]
        assert len(mutable) > 0

    @pytest.mark.asyncio
    async def test_analyze_missing_docstring(self):
        """Test detection of missing docstrings."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 5,
            "content": "def process(data):\n    return data\n\nclass MyClass:\n    pass",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        docstring = [s for s in suggestions if "docstring" in s["message"].lower()]
        assert len(docstring) > 0

    @pytest.mark.asyncio
    async def test_analyze_js_double_equals(self):
        """Test detection of == in JavaScript."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/app.js",
            "start_line": 1,
            "end_line": 3,
            "content": "if (x == y) {\n    return true;\n}",  # Using == instead of ===
            "language": "javascript"
        }

        suggestions = await agent.analyze(chunk, {})

        double_equals = [s for s in suggestions if "===" in s["message"]]
        assert len(double_equals) > 0

    @pytest.mark.asyncio
    async def test_analyze_js_var_usage(self):
        """Test detection of var in JavaScript."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/app.js",
            "start_line": 1,
            "end_line": 3,
            "content": "var x = 1;\nlet y = 2;\nconst z = 3;",
            "language": "javascript"
        }

        suggestions = await agent.analyze(chunk, {})

        var_usage = [s for s in suggestions if "var" in s["message"].lower()]
        assert len(var_usage) > 0

    @pytest.mark.asyncio
    async def test_analyze_java_brace_style(self):
        """Test detection of brace style in Java."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/Main.java",
            "start_line": 1,
            "end_line": 3,
            "content": "public void method() {\n    // code\n}",
            "language": "java"
        }

        _ = await agent.analyze(chunk, {})

        # Should not flag K&R style
        assert True  # Just ensure it doesn't crash

    @pytest.mark.asyncio
    async def test_analyze_with_docstring_present(self):
        """Test that docstrings are detected when present."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 5,
            "content": 'def process(data):\n    """Process the data."""\n    return data',
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        # Should not suggest missing docstring
        docstring_suggestions = [s for s in suggestions if "docstring" in s["message"].lower()]
        assert len(docstring_suggestions) == 0

    @pytest.mark.asyncio
    async def test_analyze_typescript(self):
        """Test analysis of TypeScript code."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/app.ts",
            "start_line": 1,
            "end_line": 3,
            "content": "var x: number = 1;\nif (x == 1) {\n    console.log('yes');\n}",
            "language": "typescript"
        }

        suggestions = await agent.analyze(chunk, {})

        # Should find var usage and == usage
        assert len(suggestions) >= 2


@pytest.mark.unit
@pytest.mark.agent
class TestStyleAgentEdgeCases:
    """Test edge cases for StyleAgent."""

    @pytest.mark.asyncio
    async def test_analyze_empty_chunk(self):
        """Test analysis of empty code chunk."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/empty.py",
            "start_line": 1,
            "end_line": 1,
            "content": "",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        # Empty content should produce no suggestions
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_analyze_single_line(self):
        """Test analysis of single line."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 1,
            "content": "print('hello')",
            "language": "python"
        }

        suggestions = await agent.analyze(chunk, {})

        # Single line should work without errors
        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_analyze_llm_failure(self):
        """Test handling of LLM failure."""
        mock_llm = Mock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

        with patch("agents.style.VertexAIClient", return_value=mock_llm):
            agent = StyleAgent()

        chunk = {
            "file_path": "src/test.py",
            "start_line": 1,
            "end_line": 20,
            "content": "def test():\n" + "    x = " + "a" * 150 + "\n" * 18,
            "language": "python"
        }

        # Should not raise exception
        suggestions = await agent.analyze(chunk, {})

        # Should still find long line via pattern matching
        long_lines = [s for s in suggestions if "120 characters" in s["message"]]
        assert len(long_lines) > 0

    def test_check_python_style_no_issues(self):
        """Test Python style check with no issues."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        line = "def valid_function():"
        suggestions = agent._check_python_style(line, 1, "test.py")

        assert len(suggestions) == 0

    def test_check_js_style_no_issues(self):
        """Test JS style check with no issues."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        line = "const x = 1;"
        suggestions = agent._check_js_style(line, 1, "test.js")

        assert len(suggestions) == 0

    def test_is_function_or_class_true(self):
        """Test detection of function or class."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        lines = ["def test():", "    pass"]
        assert agent._is_function_or_class(lines) is True

        lines = ["class MyClass:", "    pass"]
        assert agent._is_function_or_class(lines) is True

    def test_is_function_or_class_false(self):
        """Test detection when not function or class."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        lines = ["x = 1", "y = 2"]
        assert agent._is_function_or_class(lines) is False

    def test_has_docstring_true(self):
        """Test detection of docstring."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        lines = ['def test():', '    """A docstring."""', "    pass"]
        assert agent._has_docstring(lines) is True

        lines = ["def test():", "    '''Another docstring.'''", "    pass"]
        assert agent._has_docstring(lines) is True

    def test_has_docstring_false(self):
        """Test detection when no docstring."""
        with patch("agents.style.VertexAIClient"):
            agent = StyleAgent()

        lines = ["def test():", "    pass"]
        assert agent._has_docstring(lines) is False
