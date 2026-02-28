"""AGENTS.md parser for extracting configuration from markdown files."""

import logging
import re
from dataclasses import dataclass
from typing import Any, cast

from config.default_agents import get_default_config
from llm.client import VertexAIClient

logger = logging.getLogger(__name__)


@dataclass
class ParsedConfig:
    """Structured configuration parsed from AGENTS.md."""

    style_rules: dict[str, Any]
    security_priorities: dict[str, list[str]]
    ignore_patterns: list[str]
    code_patterns: dict[str, dict[str, list[str]]]
    review_settings: dict[str, Any]
    custom_rules: dict[str, Any]
    raw_sections: dict[str, str]


class AgentsParser:
    """Parser for AGENTS.md markdown files."""

    def __init__(self, llm_client: VertexAIClient | None = None):
        """
        Initialize the parser.

        Args:
            llm_client: Optional LLM client for parsing natural language
        """
        self.llm_client = llm_client
        self.default_config = get_default_config()

    async def parse(self, agents_md_content: str | None) -> ParsedConfig:
        """
        Parse AGENTS.md content into structured configuration.

        Args:
            agents_md_content: Raw markdown content from AGENTS.md, or None

        Returns:
            ParsedConfig with all extracted settings
        """
        if not agents_md_content or not agents_md_content.strip():
            logger.info("AGENTS.md not found or empty, using defaults")
            return self._create_default_config()

        try:
            # First, try structured parsing
            config = await self._parse_structured(agents_md_content)

            # If structured parsing fails or yields minimal results, use LLM
            if self._is_config_sparse(config):
                logger.debug("Using LLM for AGENTS.md parsing")
                config = await self._parse_with_llm(agents_md_content)

            return config

        except Exception as e:
            logger.error(f"Error parsing AGENTS.md: {e}, falling back to defaults")
            return self._create_default_config()

    async def _parse_structured(self, content: str) -> ParsedConfig:
        """
        Parse AGENTS.md using structured rules and regex.

        Args:
            content: Markdown content

        Returns:
            ParsedConfig
        """
        sections = self._extract_sections(content)

        return ParsedConfig(
            style_rules=self._extract_style_rules(sections),
            security_priorities=self._extract_security_priorities(sections),
            ignore_patterns=self._extract_ignore_patterns(sections),
            code_patterns=self._extract_code_patterns(sections),
            review_settings=self._extract_review_settings(sections),
            custom_rules=self._extract_custom_rules(sections),
            raw_sections=sections,
        )

    def _extract_sections(self, content: str) -> dict[str, str]:
        """
        Extract sections from markdown based on headers.

        Args:
            content: Markdown content

        Returns:
            Dictionary mapping section names to content
        """
        sections: dict[str, str] = {}
        current_section = "general"
        current_content: list[str] = []

        for line in content.split("\n"):
            # Match markdown headers
            header_match = re.match(r"^#{1,3}\s+(.+)$", line, re.IGNORECASE)

            if header_match:
                # Save previous section
                if current_content:
                    sections[current_section.lower()] = "\n".join(current_content).strip()

                # Start new section
                current_section = header_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section.lower()] = "\n".join(current_content).strip()

        return sections

    def _extract_style_rules(self, sections: dict[str, str]) -> dict[str, Any]:
        """Extract style rules from sections."""
        style_rules = {}
        style_section_content = ""

        # Look for style-related sections
        for section_name, content in sections.items():
            if "style" in section_name.lower():
                style_section_content += content + "\n"
                # Try to parse language-specific rules
                for language in ["python", "javascript", "typescript", "java", "go", "rust"]:
                    if language in section_name.lower() or language in content.lower():
                        style_rules[language] = self._parse_style_content(content)

                # If no specific language found in this section, add to general
                if not any(lang in style_rules for lang in ["python", "javascript", "typescript"]):
                    style_rules["general"] = self._parse_style_content(content)

        # Also check for language-specific subsections that might be separate
        for language in ["python", "javascript", "typescript", "java", "go", "rust"]:
            if language not in style_rules:
                for section_name, content in sections.items():
                    if language in section_name.lower():
                        style_rules[language] = self._parse_style_content(content)
                        break

        return style_rules if style_rules else self.default_config["style_rules"]

    def _parse_style_content(self, content: str) -> dict[str, Any]:
        """Parse style content into structured rules."""
        rules: dict[str, Any] = {}

        # Extract line length
        line_length_match = re.search(
            r"(?:max.?line.?length|line.?limit):?\s*(\d+)", content, re.IGNORECASE
        )
        if line_length_match:
            rules["max_line_length"] = int(line_length_match.group(1))

        # Extract boolean flags
        if re.search(r"use\s+type\s+hints?", content, re.IGNORECASE):
            rules["use_type_hints"] = (
                "no" not in content.lower() or "disable" not in content.lower()
            )

        # Extract naming conventions from lists
        naming_section = re.search(
            r"naming\s*(?:convention|standard)s?:?(.*?)(?=\n\n|\Z)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if naming_section:
            naming_rules: dict[str, str] = {}
            for line in naming_section.group(1).split("\n"):
                if ":" in line and ("-" in line or "*" in line):
                    parts = line.replace("-", "").replace("*", "").strip().split(":")
                    if len(parts) == 2:
                        naming_rules[parts[0].strip()] = parts[1].strip()
            if naming_rules:
                rules["naming_conventions"] = naming_rules

        # Extract preferred patterns from lists
        patterns = []
        in_patterns = False
        for line in content.split("\n"):
            if re.search(r"prefer(?:red)?\s*patterns?", line, re.IGNORECASE):
                in_patterns = True
                continue
            if in_patterns and line.strip().startswith(("-", "*")):
                patterns.append(line.strip()[1:].strip())
            elif in_patterns and line.strip() and not line.strip().startswith(("-", "*")):
                in_patterns = False

        if patterns:
            rules["preferred_patterns"] = patterns

        return rules

    def _extract_security_priorities(self, sections: dict[str, str]) -> dict[str, list[str]]:
        """Extract security priorities from sections."""
        priorities: dict[str, list[str]] = {"high": [], "medium": [], "low": []}

        for section_name, content in sections.items():
            if "security" in section_name.lower():
                # Try to find priority subsections
                current_priority = None
                for line in content.split("\n"):
                    # Check for priority headers
                    if re.search(r"^#{1,4}\s*(high|critical)", line, re.IGNORECASE):
                        current_priority = "high"
                    elif re.search(r"^#{1,4}\s*(medium|moderate)", line, re.IGNORECASE):
                        current_priority = "medium"
                    elif re.search(r"^#{1,4}\s*(low|minor)", line, re.IGNORECASE):
                        current_priority = "low"
                    # Check for list items with priority markers
                    elif current_priority and line.strip().startswith(("-", "*")):
                        item = line.strip()[1:].strip()
                        if item:
                            priorities[current_priority].append(item)
                    # Check for inline priority markers
                    elif re.search(r"\[high\]|\(high\)|priority:\s*high", line, re.IGNORECASE):
                        item = re.sub(r"\[.*?\]|\(.*?\)", "", line).strip()
                        if item and item.startswith(("-", "*")):
                            priorities["high"].append(item[1:].strip())

        # Merge with defaults if empty
        for priority in priorities:
            if not priorities[priority]:
                priorities[priority] = self.default_config["security_priorities"].get(priority, [])

        return priorities

    def _extract_ignore_patterns(self, sections: dict[str, str]) -> list[str]:
        """Extract ignore patterns from sections."""
        patterns = []

        for section_name, content in sections.items():
            if any(keyword in section_name.lower() for keyword in ["ignore", "exclude", "skip"]):
                # Extract patterns from lists or code blocks
                for line in content.split("\n"):
                    line = line.strip()
                    # Match list items
                    if line.startswith(("-", "*")):
                        pattern = line[1:].strip()
                        if pattern and not pattern.startswith("#"):
                            patterns.append(pattern)
                    # Match code block content
                    elif not line.startswith("#") and ("*" in line or "/" in line):
                        patterns.append(line)

        # Merge with defaults
        if patterns:
            return list(set(self.default_config["ignore_patterns"] + patterns))

        return cast(list[str], self.default_config["ignore_patterns"])

    def _extract_code_patterns(self, sections: dict[str, str]) -> dict[str, dict[str, list[str]]]:
        """Extract good/bad code patterns from sections."""
        patterns: dict[str, dict[str, list[str]]] = {}

        for section_name, content in sections.items():
            if any(
                keyword in section_name.lower() for keyword in ["pattern", "example", "practice"]
            ):
                # Determine language
                language = None
                for lang in ["python", "javascript", "typescript", "java", "go", "rust"]:
                    if lang in section_name.lower():
                        language = lang
                        break

                if not language:
                    language = "general"

                if language not in patterns:
                    patterns[language] = {"good_patterns": [], "anti_patterns": []}

                # Extract good patterns
                good_section = re.search(
                    r"(?:good|best|preferred).*?(?:\n\n|\Z)", content, re.IGNORECASE | re.DOTALL
                )
                if good_section:
                    for line in good_section.group().split("\n"):
                        if line.strip().startswith(("-", "*")):
                            patterns[language]["good_patterns"].append(line.strip()[1:].strip())

                # Extract anti-patterns
                bad_section = re.search(
                    r"(?:bad|avoid|don\'t|anti).*?(?:\n\n|\Z)", content, re.IGNORECASE | re.DOTALL
                )
                if bad_section:
                    for line in bad_section.group().split("\n"):
                        if line.strip().startswith(("-", "*")):
                            patterns[language]["anti_patterns"].append(line.strip()[1:].strip())

        # Merge with defaults
        for lang in self.default_config["code_patterns"]:
            if lang not in patterns:
                patterns[lang] = self.default_config["code_patterns"][lang]
            else:
                patterns[lang]["good_patterns"] = list(
                    set(
                        patterns[lang].get("good_patterns", [])
                        + self.default_config["code_patterns"][lang].get("good_patterns", [])
                    )
                )
                patterns[lang]["anti_patterns"] = list(
                    set(
                        patterns[lang].get("anti_patterns", [])
                        + self.default_config["code_patterns"][lang].get("anti_patterns", [])
                    )
                )

        return patterns

    def _extract_review_settings(self, sections: dict[str, str]) -> dict[str, Any]:
        """Extract review settings from sections."""
        settings: dict[str, Any] = {}

        for section_name, content in sections.items():
            if any(keyword in section_name.lower() for keyword in ["review", "setting", "config"]):
                # Extract numeric settings
                max_match = re.search(
                    r"max(?:imum)?\s*suggestions(?:\s*per\s*file)?:?\s*(\d+)",
                    content,
                    re.IGNORECASE,
                )
                if max_match:
                    settings["max_suggestions_per_file"] = int(max_match.group(1))

                total_match = re.search(
                    r"total\s*max(?:imum)?\s*suggestions?:?\s*(\d+)", content, re.IGNORECASE
                )
                if total_match:
                    settings["max_suggestions_total"] = int(total_match.group(1))

                # Extract severity threshold
                severity_match = re.search(
                    r"severity\s*(?:threshold|minimum):?\s*(error|warning|suggestion|note)",
                    content,
                    re.IGNORECASE,
                )
                if severity_match:
                    settings["severity_threshold"] = severity_match.group(1).lower()

                # Extract boolean settings
                if re.search(r"require\s*tests", content, re.IGNORECASE):
                    settings["require_tests_for_new_features"] = "no" not in content.lower()

                if re.search(r"check\s*documentation", content, re.IGNORECASE):
                    settings["check_documentation_for_public_apis"] = "no" not in content.lower()

        # Merge with defaults
        for key, value in self.default_config["review_settings"].items():
            if key not in settings:
                settings[key] = value

        return settings

    def _extract_custom_rules(self, sections: dict[str, str]) -> dict[str, Any]:
        """Extract any custom rules defined in AGENTS.md."""
        custom_rules = {}

        for section_name, content in sections.items():
            if "custom" in section_name.lower() or "rule" in section_name.lower():
                # Store the entire section as a custom rule
                rule_name = section_name.lower().replace(" ", "_").replace("-", "_")
                custom_rules[rule_name] = {"title": section_name, "content": content}

        return custom_rules

    async def _parse_with_llm(self, content: str) -> ParsedConfig:
        """
        Use LLM to parse AGENTS.md when structured parsing is insufficient.

        Args:
            content: Raw markdown content

        Returns:
            ParsedConfig
        """
        if not self.llm_client:
            logger.warning("LLM client not available, using default config")
            return self._create_default_config()

        prompt = f"""Parse the following AGENTS.md file and extract structured configuration.

The AGENTS.md file contains coding guidelines, style rules, security priorities, and review preferences.

Extract and return a JSON object with these fields:
- style_rules: Object with language keys (python, javascript, typescript) containing style preferences
- security_priorities: Object with 'high', 'medium', 'low' arrays of security concerns
- ignore_patterns: Array of file patterns to ignore (globs, extensions, paths)
- code_patterns: Object with 'good_patterns' and 'anti_patterns' arrays
- review_settings: Object with review configuration

AGENTS.md content:
---
{content[:8000]}  # Limit content to avoid token limits
---

Respond with valid JSON only."""

        try:
            response = await self.llm_client.generate_json(
                prompt=prompt,
                system_prompt="You are a configuration parser. Extract structured data from markdown documentation.",
                temperature=0.1,
            )

            return ParsedConfig(
                style_rules=response.get("style_rules", self.default_config["style_rules"]),
                security_priorities=response.get(
                    "security_priorities", self.default_config["security_priorities"]
                ),
                ignore_patterns=response.get(
                    "ignore_patterns", self.default_config["ignore_patterns"]
                ),
                code_patterns=response.get("code_patterns", self.default_config["code_patterns"]),
                review_settings=response.get(
                    "review_settings", self.default_config["review_settings"]
                ),
                custom_rules={},
                raw_sections={},
            )

        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return self._create_default_config()

    def _is_config_sparse(self, config: ParsedConfig) -> bool:
        """
        Check if the parsed config is too sparse and needs LLM enhancement.

        Args:
            config: Parsed configuration

        Returns:
            True if config needs LLM parsing
        """
        # Check if we have meaningful content beyond defaults
        default = self.default_config

        has_style = bool(
            config.style_rules and config.style_rules != default.get("style_rules", {})
        )
        has_security = bool(
            config.security_priorities
            and config.security_priorities != default.get("security_priorities", {})
        )
        has_patterns = bool(
            config.code_patterns and config.code_patterns != default.get("code_patterns", {})
        )

        # If we have less than 2 major sections populated, consider it sparse
        populated_sections = sum([has_style, has_security, has_patterns])
        return populated_sections < 2

    def _create_default_config(self) -> ParsedConfig:
        """Create a ParsedConfig from defaults."""
        return ParsedConfig(
            style_rules=self.default_config["style_rules"],
            security_priorities=self.default_config["security_priorities"],
            ignore_patterns=self.default_config["ignore_patterns"],
            code_patterns=self.default_config["code_patterns"],
            review_settings=self.default_config["review_settings"],
            custom_rules={},
            raw_sections={},
        )

    def should_ignore_file(self, file_path: str, ignore_patterns: list[str]) -> bool:
        """
        Check if a file should be ignored based on patterns.

        Args:
            file_path: Path to the file
            ignore_patterns: List of glob patterns

        Returns:
            True if file should be ignored
        """
        import fnmatch

        for pattern in ignore_patterns:
            # Handle directory wildcards
            if pattern.endswith("/**"):
                prefix = pattern[:-3]
                # Check if it's a complete path component, not just a prefix
                if (
                    file_path == prefix
                    or file_path.startswith(prefix + "/")
                    or f"/{prefix}/" in file_path
                    or file_path.endswith(f"/{prefix}")
                ):
                    return True

            # Handle file wildcards
            if pattern.startswith("*") and (
                fnmatch.fnmatch(file_path, pattern)
                or fnmatch.fnmatch(file_path.split("/")[-1], pattern)
            ):
                return True

            # Handle exact matches
            if fnmatch.fnmatch(file_path, pattern) or file_path.endswith(pattern.lstrip("*")):
                return True

            # Handle path-based patterns
            if pattern in file_path or file_path.startswith(pattern.rstrip("*")):
                return True

        return False
