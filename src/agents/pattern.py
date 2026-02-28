import re
from typing import Any

from src.agents.base import BaseAgent
from src.graph.state import ChunkInfo, Suggestion
from src.llm.client import VertexAIClient


class PatternAgent(BaseAgent):
    """Agent that compares code against learned patterns and best practices."""

    def __init__(self) -> None:
        super().__init__(name="pattern", priority=3)
        self.llm_client = VertexAIClient()
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> dict[str, list[dict[str, Any]]]:
        """Load design patterns and best practices."""
        return {
            "python": [
                {
                    "anti_pattern": r"except\s*Exception\s*as\s*e:\s*print\s*\(\s*e\s*\)",
                    "message": "Bare exception with print - use logging instead",
                    "suggestion": "except SpecificException as e:\n    logger.error(f'Error: {e}')",
                    "severity": "warning",
                },
                {
                    "anti_pattern": r"open\s*\([^)]+\)(?!\s+as\s+\w+\s*:|\s*\w+\s*=).*\.(read|write)",
                    "message": "File not opened with context manager - resource may leak",
                    "suggestion": "with open(filename, 'r') as f:\n    content = f.read()",
                    "severity": "warning",
                },
                {
                    "anti_pattern": r"\.format\s*\(|%\s*\(|\+\s*['\"]",
                    "message": "Consider using f-strings for better readability",
                    "suggestion": "f'String with {variable}'",
                    "severity": "suggestion",
                },
            ],
            "javascript": [
                {
                    "anti_pattern": r"var\s+",
                    "message": "Use const or let instead of var",
                    "suggestion": "const variable = value;",
                    "severity": "suggestion",
                },
                {
                    "anti_pattern": r"\.then\s*\([^)]*\)\s*\.then",
                    "message": "Consider using async/await for better readability",
                    "suggestion": "const result = await asyncFunction();",
                    "severity": "suggestion",
                },
                {
                    "anti_pattern": r"callback\s*\(|function\s*\([^)]*\)\s*\{[^}]*\}\s*\)",
                    "message": "Consider using arrow functions for cleaner code",
                    "suggestion": "(param) => { return value; }",
                    "severity": "note",
                },
            ],
            "typescript": [
                {
                    "anti_pattern": r":\s*any\s*[;=)]",
                    "message": "Avoid using 'any' type - use specific types",
                    "suggestion": "Use proper TypeScript interfaces or types",
                    "severity": "suggestion",
                },
                {
                    "anti_pattern": r"!\s*\w+",
                    "message": "Non-null assertion may cause runtime errors",
                    "suggestion": "Add proper null checks",
                    "severity": "warning",
                },
            ],
            "java": [
                {
                    "anti_pattern": r"System\.out\.print",
                    "message": "Use logging framework instead of System.out",
                    "suggestion": 'logger.info("message");',
                    "severity": "suggestion",
                },
                {
                    "anti_pattern": r"catch\s*\(\s*Exception\s+e\s*\)\s*\{\s*\}",
                    "message": "Empty catch block - exceptions are silently ignored",
                    "suggestion": 'catch (SpecificException e) { logger.error("Error", e); }',
                    "severity": "warning",
                },
            ],
        }

    def get_system_prompt(self) -> str:
        """Get the system prompt for pattern analysis."""
        return """You are an expert in design patterns and code quality.

Compare the code against best practices for the language:
1. Design patterns usage
2. Idiomatic code style
3. Performance patterns
4. Error handling patterns
5. API design patterns
6. Code organization
7. Common anti-patterns
8. SOLID principles
9. DRY principle violations
10. Language-specific idioms

For each pattern issue found, provide:
- Line number
- Description of the pattern issue
- Severity (error/warning/suggestion)
- Suggested improvement
- Confidence score (0.0-1.0)

Format your response as a JSON array of findings."""

    async def analyze(self, chunk: ChunkInfo, context: dict[str, Any]) -> list[Suggestion]:
        """Analyze code for pattern violations."""
        suggestions = []
        language = chunk["language"]

        # Pattern-based detection for known languages
        if language in self.patterns:
            for pattern in self.patterns[language]:
                for match in re.finditer(pattern["anti_pattern"], chunk["content"], re.IGNORECASE):
                    line_num = chunk["start_line"] + chunk["content"][: match.start()].count("\n")
                    suggestions.append(
                        self.format_suggestion(
                            file_path=chunk["file_path"],
                            line_number=line_num,
                            message=pattern["message"],
                            severity=pattern["severity"],
                            suggestion=pattern.get("suggestion"),
                            category="pattern",
                            confidence=0.8,
                        )
                    )

        # Check for AGENTS.md patterns if available
        agnets_md = context.get("agnets_md")
        if agnets_md:
            custom_suggestions = self._check_custom_patterns(chunk, agnets_md)
            suggestions.extend(custom_suggestions)

        # LLM-based pattern analysis
        try:
            llm_suggestions = await self._llm_analysis(chunk, context)
            suggestions.extend(llm_suggestions)
        except Exception:
            pass  # LLM analysis is best-effort; continue with pattern-based results

        return suggestions

    def _check_custom_patterns(self, chunk: ChunkInfo, agnets_md: str) -> list[Suggestion]:
        """Check against custom patterns from AGENTS.md."""
        suggestions = []

        # Parse AGENTS.md for custom rules
        # Format: ## Rule: Rule Name
        # Description: ...
        # Pattern: regex pattern
        # Message: message to show
        # Severity: warning/error/suggestion

        rule_pattern = (
            r"##\s*Rule:\s*(.+?)\n.*?Pattern:\s*`(.+?)`.*?Message:\s*(.+?)\n.*?Severity:\s*(\w+)"
        )

        for match in re.finditer(rule_pattern, agnets_md, re.DOTALL | re.IGNORECASE):
            pattern_str = match.group(2).strip()
            message = match.group(3).strip()
            severity = match.group(4).strip()

            try:
                for pm in re.finditer(pattern_str, chunk["content"], re.MULTILINE):
                    line_num = chunk["start_line"] + chunk["content"][: pm.start()].count("\n")
                    suggestions.append(
                        self.format_suggestion(
                            file_path=chunk["file_path"],
                            line_number=line_num,
                            message=f"[AGENTS.md] {message}",
                            severity=severity,
                            category="pattern",
                            confidence=0.85,
                        )
                    )
            except re.error:
                # Invalid regex pattern, skip
                continue

        return suggestions

    async def _llm_analysis(self, chunk: ChunkInfo, context: dict[str, Any]) -> list[Suggestion]:
        """Use LLM for pattern analysis."""
        if len(chunk["content"]) < 100:
            return []

        agnets_md = context.get("agnets_md", "No custom patterns")

        prompt = f"""Analyze this {chunk["language"]} code for design patterns and best practices:

```
{chunk["content"]}
```

Custom patterns from AGENTS.md:
{agnets_md[:500] if agnets_md else "None"}

Check for: design patterns, idiomatic code, anti-patterns, SOLID principles, DRY violations.

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
                        message=finding.get("message", "Pattern issue detected"),
                        severity=finding.get("severity", "suggestion"),
                        suggestion=finding.get("suggestion"),
                        category="pattern",
                        confidence=finding.get("confidence", 0.7),
                    )
                )

            return suggestions

        except Exception:
            return []

    def should_analyze(self, chunk: ChunkInfo) -> bool:
        """Pattern agent analyzes all code files."""
        language: str = chunk.get("language", "unknown")
        return language != "unknown"
