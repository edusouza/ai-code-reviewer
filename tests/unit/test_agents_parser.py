"""Tests for AGENTS.md parser."""

from unittest.mock import AsyncMock, Mock

import pytest

from config.agents_parser import AgentsParser, ParsedConfig


@pytest.mark.unit
class TestAgentsParser:
    """Test suite for AgentsParser."""

    def test_init(self):
        """Test parser initialization."""
        parser = AgentsParser()

        assert parser.default_config is not None
        assert "style_rules" in parser.default_config
        assert "security_priorities" in parser.default_config

    def test_init_with_llm(self):
        """Test parser initialization with LLM client."""
        mock_llm = Mock()
        parser = AgentsParser(llm_client=mock_llm)

        assert parser.llm_client == mock_llm

    @pytest.mark.asyncio
    async def test_parse_empty_content(self):
        """Test parsing empty AGENTS.md content."""
        parser = AgentsParser()

        config = await parser.parse("")

        assert isinstance(config, ParsedConfig)
        # Should return default config
        assert config.style_rules == parser.default_config["style_rules"]

    @pytest.mark.asyncio
    async def test_parse_none_content(self):
        """Test parsing None AGENTS.md content."""
        parser = AgentsParser()

        config = await parser.parse(None)

        assert isinstance(config, ParsedConfig)
        # Should return default config
        assert config.style_rules == parser.default_config["style_rules"]

    @pytest.mark.asyncio
    async def test_parse_style_rules(self, sample_agents_md):
        """Test parsing style rules."""
        parser = AgentsParser()

        config = await parser.parse(sample_agents_md)

        assert "python" in config.style_rules or "general" in config.style_rules
        # Check if line length was extracted
        has_line_length = any("max_line_length" in rules for rules in config.style_rules.values())
        assert has_line_length

    @pytest.mark.asyncio
    async def test_parse_security_priorities(self, sample_agents_md):
        """Test parsing security priorities."""
        parser = AgentsParser()

        config = await parser.parse(sample_agents_md)

        assert "high" in config.security_priorities
        assert "medium" in config.security_priorities
        assert "low" in config.security_priorities

        # Check if high priorities were extracted
        assert len(config.security_priorities["high"]) > 0

    @pytest.mark.asyncio
    async def test_parse_ignore_patterns(self, sample_agents_md):
        """Test parsing ignore patterns."""
        parser = AgentsParser()

        config = await parser.parse(sample_agents_md)

        assert len(config.ignore_patterns) > 0
        assert any("tests" in p for p in config.ignore_patterns)

    @pytest.mark.asyncio
    async def test_parse_code_patterns(self, sample_agents_md):
        """Test parsing code patterns."""
        parser = AgentsParser()

        config = await parser.parse(sample_agents_md)

        # Should have some patterns
        assert len(config.code_patterns) > 0

    @pytest.mark.asyncio
    async def test_parse_review_settings(self, sample_agents_md):
        """Test parsing review settings."""
        parser = AgentsParser()

        config = await parser.parse(sample_agents_md)

        assert "max_suggestions_per_file" in config.review_settings
        assert config.review_settings["max_suggestions_per_file"] == 10

    @pytest.mark.asyncio
    async def test_parse_custom_rules(self, sample_agents_md):
        """Test parsing custom rules."""
        parser = AgentsParser()

        config = await parser.parse(sample_agents_md)

        assert len(config.custom_rules) > 0

    def test_extract_sections(self):
        """Test section extraction from markdown."""
        parser = AgentsParser()

        content = """
# Title

Some intro text.

## Section 1
Content for section 1.
More content.

## Section 2
Content for section 2.

### Subsection
Subsection content.
"""

        sections = parser._extract_sections(content)

        assert "section 1" in sections
        assert "section 2" in sections
        assert "subsection" in sections

    def test_extract_sections_no_headers(self):
        """Test section extraction with no headers."""
        parser = AgentsParser()

        content = "Just some text without headers."

        sections = parser._extract_sections(content)

        assert "general" in sections
        assert sections["general"] == content

    def test_extract_style_rules(self):
        """Test style rules extraction."""
        parser = AgentsParser()

        sections = {
            "python style": "Max line length: 120\nUse type hints: yes",
            "javascript style": "Max line length: 100",
        }

        style_rules = parser._extract_style_rules(sections)

        assert "python" in style_rules
        assert style_rules["python"]["max_line_length"] == 120

    def test_extract_style_rules_no_style_section(self):
        """Test style rules extraction without style section."""
        parser = AgentsParser()

        sections = {"general": "Some content"}

        style_rules = parser._extract_style_rules(sections)

        # Should return defaults
        assert style_rules == parser.default_config["style_rules"]

    def test_parse_style_content_line_length(self):
        """Test parsing line length from style content."""
        parser = AgentsParser()

        content = "Max line length: 120\nSome other text."
        rules = parser._parse_style_content(content)

        assert rules["max_line_length"] == 120

    def test_parse_style_content_type_hints(self):
        """Test parsing type hints preference from style content."""
        parser = AgentsParser()

        content = "Use type hints: yes"
        rules = parser._parse_style_content(content)

        assert rules["use_type_hints"] is True

    def test_extract_security_priorities(self):
        """Test security priorities extraction."""
        parser = AgentsParser()

        sections = {
            "security": """
### High
- SQL injection
- XSS

### Medium
- Insecure hash
"""
        }

        priorities = parser._extract_security_priorities(sections)

        assert len(priorities["high"]) >= 2
        assert len(priorities["medium"]) >= 1

    def test_extract_ignore_patterns(self):
        """Test ignore patterns extraction."""
        parser = AgentsParser()

        sections = {
            "ignore": """
- tests/**
- **/*.pyc
- node_modules/**
"""
        }

        patterns = parser._extract_ignore_patterns(sections)

        assert any("tests" in p for p in patterns)
        assert any("node_modules" in p for p in patterns)

    def test_extract_review_settings(self):
        """Test review settings extraction."""
        parser = AgentsParser()

        sections = {
            "review settings": """
Max suggestions per file: 10
Total max suggestions: 50
Severity threshold: warning
Require tests for new features: yes
"""
        }

        settings = parser._extract_review_settings(sections)

        assert settings["max_suggestions_per_file"] == 10
        assert settings["max_suggestions_total"] == 50
        assert settings["severity_threshold"] == "warning"

    def test_is_config_sparse_true(self):
        """Test sparse config detection - true case."""
        parser = AgentsParser()

        config = ParsedConfig(
            style_rules={},
            security_priorities={"high": [], "medium": [], "low": []},
            ignore_patterns=[],
            code_patterns={},
            review_settings={},
            custom_rules={},
            raw_sections={},
        )

        assert parser._is_config_sparse(config) is True

    def test_is_config_sparse_false(self):
        """Test sparse config detection - false case."""
        parser = AgentsParser()

        config = ParsedConfig(
            style_rules={"python": {"max_line_length": 120}},
            security_priorities={"high": ["SQL injection"], "medium": [], "low": []},
            ignore_patterns=["tests/**"],
            code_patterns={},
            review_settings={},
            custom_rules={},
            raw_sections={},
        )

        assert parser._is_config_sparse(config) is False

    def test_create_default_config(self):
        """Test default config creation."""
        parser = AgentsParser()

        config = parser._create_default_config()

        assert isinstance(config, ParsedConfig)
        assert config.style_rules == parser.default_config["style_rules"]
        assert config.security_priorities == parser.default_config["security_priorities"]

    def test_should_ignore_file_exact_match(self):
        """Test file ignore with exact match."""
        parser = AgentsParser()

        patterns = ["tests/test_main.py"]

        assert parser.should_ignore_file("tests/test_main.py", patterns) is True
        assert parser.should_ignore_file("src/main.py", patterns) is False

    def test_should_ignore_file_wildcard(self):
        """Test file ignore with wildcard."""
        parser = AgentsParser()

        patterns = ["**/*.pyc", "*.test.js"]

        assert parser.should_ignore_file("src/__pycache__/module.pyc", patterns) is True
        assert parser.should_ignore_file("test.unit.test.js", patterns) is True

    def test_should_ignore_file_directory(self):
        """Test file ignore with directory pattern."""
        parser = AgentsParser()

        patterns = ["node_modules/**"]

        assert parser.should_ignore_file("node_modules/lodash/index.js", patterns) is True
        assert parser.should_ignore_file("src/node_modules_helper.py", patterns) is False

    @pytest.mark.asyncio
    async def test_parse_with_llm_fallback(self):
        """Test LLM fallback parsing."""
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "style_rules": {"python": {"max_line_length": 100}},
                "security_priorities": {"high": [], "medium": [], "low": []},
                "ignore_patterns": [],
                "code_patterns": {},
                "review_settings": {},
            }
        )

        parser = AgentsParser(llm_client=mock_llm)

        content = """
# Very minimal content
Just a basic file.
"""

        config = await parser.parse(content)

        # Should use LLM for sparse content
        mock_llm.generate_json.assert_called_once()
        assert config.style_rules["python"]["max_line_length"] == 100

    @pytest.mark.asyncio
    async def test_parse_with_llm_error(self):
        """Test handling of LLM parsing error."""
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(side_effect=Exception("LLM Error"))

        parser = AgentsParser(llm_client=mock_llm)

        content = """
# Minimal content that triggers LLM fallback
"""

        # Should not raise, fall back to defaults
        config = await parser.parse(content)

        assert isinstance(config, ParsedConfig)
        assert config.style_rules == parser.default_config["style_rules"]


@pytest.mark.unit
class TestParsedConfig:
    """Test suite for ParsedConfig dataclass."""

    def test_dataclass_creation(self):
        """Test ParsedConfig creation."""
        config = ParsedConfig(
            style_rules={"python": {"max_line_length": 120}},
            security_priorities={"high": ["SQL injection"], "medium": [], "low": []},
            ignore_patterns=["tests/**"],
            code_patterns={"python": {"good_patterns": [], "anti_patterns": []}},
            review_settings={"max_suggestions": 50},
            custom_rules={},
            raw_sections={},
        )

        assert config.style_rules["python"]["max_line_length"] == 120
        assert len(config.security_priorities["high"]) == 1
