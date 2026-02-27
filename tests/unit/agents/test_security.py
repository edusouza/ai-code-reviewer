"""Tests for Security agent."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from agents.security import SecurityAgent


@pytest.mark.unit
@pytest.mark.agent
class TestSecurityAgent:
    """Test suite for SecurityAgent."""

    def test_init(self):
        """Test agent initialization."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        assert agent.name == "security"
        assert agent.priority == 1
        assert len(agent.patterns) > 0

    def test_get_system_prompt(self):
        """Test system prompt generation."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        prompt = agent.get_system_prompt()

        assert "security" in prompt.lower()
        assert "vulnerability" in prompt.lower()
        assert "JSON" in prompt

    def test_should_analyze_code(self):
        """Test should_analyze for code files."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = Mock()
        chunk.__getitem__ = Mock(side_effect=lambda k: "python" if k == "language" else "")

        assert agent.should_analyze(chunk) is True

    def test_should_analyze_unknown(self):
        """Test should_analyze for unknown files."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = Mock()
        chunk.__getitem__ = Mock(side_effect=lambda k: "unknown" if k == "language" else "")

        assert agent.should_analyze(chunk) is False

    def test_format_suggestion(self):
        """Test suggestion formatting."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        suggestion = agent.format_suggestion(
            file_path="src/main.py",
            line_number=42,
            message="Test security issue",
            severity="error",
            suggestion="Use safe method",
            category="security",
            confidence=0.95,
        )

        assert suggestion["file_path"] == "src/main.py"
        assert suggestion["line_number"] == 42
        assert suggestion["message"] == "Test security issue"
        assert suggestion["severity"] == "error"
        assert suggestion["suggestion"] == "Use safe method"
        assert suggestion["agent_type"] == "security"
        assert suggestion["category"] == "security"
        assert suggestion["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_analyze_sql_injection(self):
        """Test SQL injection detection."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/db.py",
            "start_line": 10,
            "end_line": 15,
            "content": "def query(user_id):\n    cursor.execute('SELECT * FROM users WHERE id = ' + user_id)\n    return cursor.fetchall()",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any("sql" in s["message"].lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_hardcoded_password(self):
        """Test hardcoded password detection."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/config.py",
            "start_line": 1,
            "end_line": 5,
            "content": "DB_PASSWORD = 'super_secret_123'\nAPI_KEY = 'sk-abc123'",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any(
            "credential" in s["message"].lower() or "secret" in s["message"].lower()
            for s in suggestions
        )

    @pytest.mark.asyncio
    async def test_analyze_eval_usage(self):
        """Test eval/exec usage detection."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/utils.py",
            "start_line": 1,
            "end_line": 5,
            "content": "def process(data):\n    result = eval(data)\n    return result",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any("eval" in s["message"].lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_pickle_usage(self):
        """Test pickle usage detection."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/cache.py",
            "start_line": 1,
            "end_line": 5,
            "content": "import pickle\n\ndef load_cache(data):\n    return pickle.loads(data)",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any("pickle" in s["message"].lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_xss_vulnerability(self):
        """Test XSS vulnerability detection in JS."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/app.js",
            "start_line": 1,
            "end_line": 5,
            "content": "function render(userInput) {\n    element.innerHTML = userInput;\n}",
            "language": "javascript",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any("xss" in s["message"].lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_shell_injection(self):
        """Test shell injection detection."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/tasks.py",
            "start_line": 1,
            "end_line": 5,
            "content": "import os\n\ndef cleanup(path):\n    os.system('rm -rf ' + path)",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any("shell" in s["message"].lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_insecure_hash(self):
        """Test insecure hash algorithm detection."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/auth.py",
            "start_line": 1,
            "end_line": 5,
            "content": "import hashlib\n\ndef hash_password(pwd):\n    return hashlib.md5(pwd.encode()).hexdigest()",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any("hash" in s["message"].lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_disabled_ssl(self):
        """Test disabled SSL verification detection."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/api.py",
            "start_line": 1,
            "end_line": 5,
            "content": "import requests\n\ndef fetch(url):\n    return requests.get(url, verify=False)",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) > 0
        assert any("ssl" in s["message"].lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_unsupported_language(self):
        """Test analysis of unsupported language."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "README.md",
            "start_line": 1,
            "end_line": 5,
            "content": "# Project\n\nThis is a markdown file.",
            "language": "markdown",
        }

        suggestions = await agent.analyze(chunk, {})

        # Should not find security issues in markdown
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_analyze_with_llm(self):
        """Test LLM-based analysis."""
        mock_llm = Mock()
        mock_llm.generate = AsyncMock(
            return_value='[{"line_number": 5, "message": "Complex vulnerability", "severity": "error", "suggestion": "Fix it", "confidence": 0.8}]'
        )

        with patch("agents.security.VertexAIClient", return_value=mock_llm):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/complex.py",
            "start_line": 1,
            "end_line": 20,
            "content": "def complex_function(data):\n"
            + "    pass\n" * 19,  # Make it long enough for LLM
            "language": "python",
        }

        _ = await agent.analyze(chunk, {})

        # Should include LLM suggestions
        mock_llm.generate.assert_called_once()


@pytest.mark.unit
@pytest.mark.agent
class TestSecurityAgentEdgeCases:
    """Test edge cases for SecurityAgent."""

    @pytest.mark.asyncio
    async def test_analyze_empty_chunk(self):
        """Test analysis of empty code chunk."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/empty.py",
            "start_line": 1,
            "end_line": 1,
            "content": "",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_analyze_llm_failure(self):
        """Test handling of LLM failure."""
        mock_llm = Mock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

        with patch("agents.security.VertexAIClient", return_value=mock_llm):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/test.py",
            "start_line": 1,
            "end_line": 20,
            "content": "def test():\n    password = 'secret'\n    return password\n" * 5,
            "language": "python",
        }

        # Should not raise exception, return pattern-based results
        suggestions = await agent.analyze(chunk, {})

        # Should still find hardcoded password via patterns
        assert any("credential" in s["message"].lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_analyze_line_number_calculation(self):
        """Test correct line number calculation."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        chunk = {
            "file_path": "src/test.py",
            "start_line": 10,  # Chunk starts at line 10
            "end_line": 15,
            "content": "line1\nline2\npassword = 'secret'\nline4\nline5",
            "language": "python",
        }

        suggestions = await agent.analyze(chunk, {})

        # Line number should be relative to chunk start
        hardcoded_suggestions = [s for s in suggestions if "credential" in s["message"].lower()]
        assert len(hardcoded_suggestions) > 0
        assert hardcoded_suggestions[0]["line_number"] == 12  # 10 + 2 (0-indexed line 2)

    def test_load_security_patterns(self):
        """Test that security patterns are loaded correctly."""
        with patch("agents.security.VertexAIClient"):
            agent = SecurityAgent()

        patterns = agent.patterns

        assert len(patterns) > 0

        # Check required patterns exist
        pattern_names = [p["name"] for p in patterns]
        assert "sql_injection" in pattern_names
        assert "hardcoded_password" in pattern_names
        assert "eval_usage" in pattern_names

        # Check pattern structure
        for pattern in patterns:
            assert "name" in pattern
            assert "pattern" in pattern
            assert "message" in pattern
            assert "severity" in pattern
            assert "languages" in pattern
