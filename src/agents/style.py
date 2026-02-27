import re
from typing import Any

from src.agents.base import BaseAgent
from src.graph.state import ChunkInfo, Suggestion
from src.llm.client import VertexAIClient


class StyleAgent(BaseAgent):
    """Agent that checks code formatting and style conventions."""

    def __init__(self):
        super().__init__(name="style", priority=5)
        self.llm_client = VertexAIClient()

    def get_system_prompt(self) -> str:
        """Get the system prompt for style analysis."""
        return """You are a code style expert analyzing code for formatting and convention issues.

Check for:
1. Consistent indentation and spacing
2. Line length limits (typically 80-120 characters)
3. Naming conventions (camelCase, snake_case, PascalCase)
4. Import ordering and organization
5. Trailing whitespace
6. Missing docstrings/comments
7. Code complexity and readability
8. Consistent quote usage
9. Blank line usage
10. Bracket/indentation alignment

For each issue found, provide:
- Line number
- Description of the style issue
- Severity (error/warning/suggestion)
- Suggested fix
- Confidence score (0.0-1.0)

Format your response as a JSON array of findings."""

    async def analyze(self, chunk: ChunkInfo, context: dict[str, Any]) -> list[Suggestion]:
        """Analyze code for style issues."""
        suggestions = []
        content = chunk["content"]
        lines = content.split("\n")
        language = chunk["language"]

        # Check each line
        for i, line in enumerate(lines):
            line_num = chunk["start_line"] + i

            # Line length check
            if len(line) > 120:
                suggestions.append(
                    self.format_suggestion(
                        file_path=chunk["file_path"],
                        line_number=line_num,
                        message=f"Line exceeds 120 characters ({len(line)} chars)",
                        severity="suggestion",
                        category="style",
                        confidence=0.9,
                    )
                )

            # Trailing whitespace
            if line.rstrip() != line:
                suggestions.append(
                    self.format_suggestion(
                        file_path=chunk["file_path"],
                        line_number=line_num,
                        message="Trailing whitespace detected",
                        severity="note",
                        suggestion=line.rstrip(),
                        category="style",
                        confidence=1.0,
                    )
                )

            # Language-specific checks
            if language == "python":
                suggestions.extend(self._check_python_style(line, line_num, chunk["file_path"]))
            elif language in ["javascript", "typescript"]:
                suggestions.extend(self._check_js_style(line, line_num, chunk["file_path"]))
            elif language == "java":
                suggestions.extend(self._check_java_style(line, line_num, chunk["file_path"]))

        # Missing docstring check for Python
        if language == "python" and self._is_function_or_class(lines):
            if not self._has_docstring(lines):
                suggestions.append(
                    self.format_suggestion(
                        file_path=chunk["file_path"],
                        line_number=chunk["start_line"],
                        message="Missing docstring for function/class",
                        severity="suggestion",
                        category="style",
                        confidence=0.7,
                    )
                )

        # LLM analysis for complex style issues
        try:
            llm_suggestions = await self._llm_analysis(chunk, context)
            suggestions.extend(llm_suggestions)
        except Exception:
            pass

        return suggestions

    def _check_python_style(self, line: str, line_num: int, file_path: str) -> list[Suggestion]:
        """Check Python-specific style issues."""
        suggestions = []

        # Check for mixed tabs and spaces
        if "\t" in line and "  " in line:
            suggestions.append(
                self.format_suggestion(
                    file_path=file_path,
                    line_number=line_num,
                    message="Mixed tabs and spaces detected",
                    severity="error",
                    category="style",
                    confidence=1.0,
                )
            )

        # Check for bare except
        if re.search(r"\bexcept\s*:", line):
            suggestions.append(
                self.format_suggestion(
                    file_path=file_path,
                    line_number=line_num,
                    message="Bare 'except:' clause - should catch specific exceptions",
                    severity="warning",
                    suggestion="except SpecificException:",
                    category="style",
                    confidence=0.9,
                )
            )

        # Check for mutable default arguments
        if re.search(r"def\s+\w+\s*\([^)]*=[]|{}|\(\)", line):
            suggestions.append(
                self.format_suggestion(
                    file_path=file_path,
                    line_number=line_num,
                    message="Mutable default argument - use None instead",
                    severity="warning",
                    category="style",
                    confidence=0.85,
                )
            )

        return suggestions

    def _check_js_style(self, line: str, line_num: int, file_path: str) -> list[Suggestion]:
        """Check JavaScript/TypeScript-specific style issues."""
        suggestions = []

        # Check for == instead of ===
        if re.search(r"(?<!\!)=(?<!\=)=(?!=)", line) and not re.search(r"===", line):
            if re.search(r"if\s*\(|while\s*\(|return\s+|===?\s+", line):
                suggestions.append(
                    self.format_suggestion(
                        file_path=file_path,
                        line_number=line_num,
                        message="Use '===' instead of '==' for strict equality",
                        severity="suggestion",
                        category="style",
                        confidence=0.8,
                    )
                )

        # Check for var usage
        if re.search(r"\bvar\s+", line):
            suggestions.append(
                self.format_suggestion(
                    file_path=file_path,
                    line_number=line_num,
                    message="Use 'const' or 'let' instead of 'var'",
                    severity="suggestion",
                    category="style",
                    confidence=0.8,
                )
            )

        return suggestions

    def _check_java_style(self, line: str, line_num: int, file_path: str) -> list[Suggestion]:
        """Check Java-specific style issues."""
        suggestions = []

        # Check for proper brace style
        if re.search(r"\)\s*\{", line):
            suggestions.append(
                self.format_suggestion(
                    file_path=file_path,
                    line_number=line_num,
                    message="Consider putting opening brace on same line (K&R style)",
                    severity="note",
                    category="style",
                    confidence=0.6,
                )
            )

        return suggestions

    def _is_function_or_class(self, lines: list[str]) -> bool:
        """Check if lines contain a function or class definition."""
        content = "\n".join(lines)
        return bool(re.search(r"^(def |class )", content, re.MULTILINE))

    def _has_docstring(self, lines: list[str]) -> bool:
        """Check if code has a docstring."""
        content = "\n".join(lines)
        return '"""' in content or "'''" in content

    async def _llm_analysis(self, chunk: ChunkInfo, context: dict[str, Any]) -> list[Suggestion]:
        """Use LLM for deeper style analysis."""
        if len(chunk["content"]) < 100:
            return []

        prompt = f"""Analyze this {chunk["language"]} code for style and formatting issues:

```
{chunk["content"]}
```

Check for: indentation, spacing, naming conventions, complexity, readability, and best practices.

Return JSON array with: line_number, message, severity, suggestion, confidence"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt, system_prompt=self.get_system_prompt(), temperature=0.1
            )

            import json

            findings = json.loads(response)

            suggestions = []
            for finding in findings:
                suggestions.append(
                    self.format_suggestion(
                        file_path=chunk["file_path"],
                        line_number=finding.get("line_number", chunk["start_line"]),
                        message=finding.get("message", "Style issue detected"),
                        severity=finding.get("severity", "suggestion"),
                        suggestion=finding.get("suggestion"),
                        category="style",
                        confidence=finding.get("confidence", 0.6),
                    )
                )

            return suggestions

        except Exception:
            return []

    def should_analyze(self, chunk: ChunkInfo) -> bool:
        """Style agent analyzes all code files."""
        return chunk["language"] != "unknown"
