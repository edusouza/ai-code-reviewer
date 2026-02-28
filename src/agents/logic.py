import re
from typing import Any

from src.agents.base import BaseAgent
from src.graph.state import ChunkInfo, Suggestion
from src.llm.client import VertexAIClient


class LogicAgent(BaseAgent):
    """Agent that finds bugs and logic errors in code."""

    def __init__(self) -> None:
        super().__init__(name="logic", priority=2)
        self.llm_client = VertexAIClient()
        self.bug_patterns = self._load_bug_patterns()

    def _load_bug_patterns(self) -> list[dict[str, Any]]:
        """Load common bug patterns."""
        return [
            {
                "name": "null_check_order",
                "pattern": r"(if|while)\s*\(\s*\w+\s*==\s*(None|null|NULL)\s*\)\s*&&",
                "message": "Potential null pointer - check null first before accessing",
                "severity": "warning",
                "languages": ["python", "javascript", "typescript", "java", "c", "cpp"],
            },
            {
                "name": "unreachable_code",
                "pattern": r"return\s+.+\n.+[^\n]",
                "message": "Code after return statement is unreachable",
                "severity": "error",
                "languages": ["python", "javascript", "typescript", "java", "go", "c", "cpp"],
            },
            {
                "name": "variable_shadowing",
                "pattern": r"\b(\w+)\s*=\s*.+\n.*\b\1\s*=",
                "message": "Variable may be shadowed or reassigned unexpectedly",
                "severity": "suggestion",
                "languages": ["python", "javascript", "typescript", "java", "go"],
            },
            {
                "name": "infinite_loop",
                "pattern": r"while\s*\(\s*true\s*\)|while\s+True:",
                "message": "Potential infinite loop - ensure proper exit condition",
                "severity": "warning",
                "languages": ["python", "javascript", "typescript", "java", "c", "cpp"],
            },
            {
                "name": "unused_variable",
                "pattern": r"^(\w+)\s*=\s*.+$\n(?!.*\b\1\b)",
                "message": "Variable assigned but never used",
                "severity": "suggestion",
                "languages": ["python", "javascript", "typescript", "java", "go", "c", "cpp"],
            },
            {
                "name": "off_by_one",
                "pattern": r"range\s*\(\s*len\s*\(|for\s*\(\s*int\s+\w+\s*=\s*0;\s*\w+\s*<\s*.+\.(length|size)",
                "message": "Potential off-by-one error - verify loop bounds",
                "severity": "warning",
                "languages": ["python", "javascript", "typescript", "java", "c", "cpp"],
            },
            {
                "name": "division_by_zero",
                "pattern": r"/\s*\w+\s*(?![;{])|/\s*\w+\s*$",
                "message": "Potential division by zero - add zero check",
                "severity": "warning",
                "languages": ["python", "javascript", "typescript", "java", "c", "cpp", "go"],
            },
            {
                "name": "resource_leak",
                "pattern": r"open\s*\(|fopen\s*\(|File\s*\(",
                "message": "File/resource opened - ensure it's properly closed",
                "severity": "warning",
                "languages": ["python", "c", "cpp", "java"],
            },
        ]

    def get_system_prompt(self) -> str:
        """Get the system prompt for logic analysis."""
        return """You are a code quality expert analyzing code for logic errors and bugs.

Look for:
1. Off-by-one errors
2. Null/None pointer dereferences
3. Resource leaks (files, connections)
4. Infinite loops
5. Unreachable code
6. Race conditions
7. Logic errors in conditionals
8. Type mismatches
9. Edge cases not handled
10. Incorrect error handling

For each issue found, provide:
- Line number
- Description of the bug
- Severity (error/warning/suggestion)
- Suggested fix
- Confidence score (0.0-1.0)

Format your response as a JSON array of findings."""

    async def analyze(self, chunk: ChunkInfo, context: dict[str, Any]) -> list[Suggestion]:
        """Analyze code for logic errors and bugs."""
        suggestions = []

        # Pattern-based detection
        for pattern_def in self.bug_patterns:
            if chunk["language"] in pattern_def["languages"]:
                matches = list(re.finditer(pattern_def["pattern"], chunk["content"], re.MULTILINE))
                for match in matches[:3]:  # Limit to 3 matches per pattern
                    line_num = chunk["start_line"] + chunk["content"][: match.start()].count("\n")
                    suggestions.append(
                        self.format_suggestion(
                            file_path=chunk["file_path"],
                            line_number=line_num,
                            message=pattern_def["message"],
                            severity=pattern_def["severity"],
                            category="logic",
                            confidence=0.75,
                        )
                    )

        # Language-specific logic checks
        if chunk["language"] == "python":
            suggestions.extend(self._check_python_logic(chunk))
        elif chunk["language"] in ["javascript", "typescript"]:
            suggestions.extend(self._check_js_logic(chunk))

        # LLM-based analysis for complex bugs
        try:
            llm_suggestions = await self._llm_analysis(chunk, context)
            suggestions.extend(llm_suggestions)
        except Exception:
            pass  # LLM analysis is best-effort; continue with pattern-based results

        return suggestions

    def _check_python_logic(self, chunk: ChunkInfo) -> list[Suggestion]:
        """Check Python-specific logic issues."""
        suggestions = []
        content = chunk["content"]
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line_num = chunk["start_line"] + i

            # Check for list modification during iteration
            if re.search(r"for\s+\w+\s+in\s+\w+", line):
                # Look ahead for modification
                remaining_content = "\n".join(lines[i : i + 10])
                if re.search(r"\w+\.(append|extend|remove|pop|del)", remaining_content):
                    suggestions.append(
                        self.format_suggestion(
                            file_path=chunk["file_path"],
                            line_number=line_num,
                            message="Potential modification of list during iteration",
                            severity="warning",
                            category="logic",
                            confidence=0.7,
                        )
                    )

            # Check for except/pass
            if re.search(r"except.*:\s*$", line):
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                if re.search(r"^\s*pass\s*$", next_line):
                    suggestions.append(
                        self.format_suggestion(
                            file_path=chunk["file_path"],
                            line_number=line_num,
                            message="Bare except/pass - consider logging or handling the exception",
                            severity="warning",
                            category="logic",
                            confidence=0.85,
                        )
                    )

            # Check for mutable default
            if re.search(r"def\s+\w+\s*\([^)]*=\s*\[|def\s+\w+\s*\([^)]*=\s*\{", line):
                suggestions.append(
                    self.format_suggestion(
                        file_path=chunk["file_path"],
                        line_number=line_num,
                        message="Mutable default argument - use None and initialize inside function",
                        severity="error",
                        suggestion="def func(arg=None):\n    if arg is None:\n        arg = []",
                        category="logic",
                        confidence=0.9,
                    )
                )

        return suggestions

    def _check_js_logic(self, chunk: ChunkInfo) -> list[Suggestion]:
        """Check JavaScript/TypeScript-specific logic issues."""
        suggestions = []
        content = chunk["content"]
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line_num = chunk["start_line"] + i

            # Check for callback without error handling
            if re.search(r"\.(then|catch)\s*\(", line) and not re.search(
                r"catch|reject|error", content
            ):
                suggestions.append(
                    self.format_suggestion(
                        file_path=chunk["file_path"],
                        line_number=line_num,
                        message="Promise chain without error handling - add .catch()",
                        severity="warning",
                        category="logic",
                        confidence=0.75,
                    )
                )

            # Check for async without await
            if re.search(r"async\s+function|async\s*\(", line):
                func_content = "\n".join(lines[i : i + 20])
                if not re.search(r"\bawait\b", func_content):
                    suggestions.append(
                        self.format_suggestion(
                            file_path=chunk["file_path"],
                            line_number=line_num,
                            message="Async function without await - may not need async",
                            severity="suggestion",
                            category="logic",
                            confidence=0.7,
                        )
                    )

        return suggestions

    async def _llm_analysis(self, chunk: ChunkInfo, context: dict[str, Any]) -> list[Suggestion]:
        """Use LLM for deeper logic analysis."""
        if len(chunk["content"]) < 100:
            return []

        prompt = f"""Analyze this {chunk["language"]} code for logic errors and bugs:

```
{chunk["content"]}
```

Look for: off-by-one errors, null pointer issues, resource leaks, infinite loops, edge cases, type mismatches.

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
                        message=finding.get("message", "Logic issue detected"),
                        severity=finding.get("severity", "warning"),
                        suggestion=finding.get("suggestion"),
                        category="logic",
                        confidence=finding.get("confidence", 0.7),
                    )
                )

            return suggestions

        except Exception:
            return []

    def should_analyze(self, chunk: ChunkInfo) -> bool:
        """Logic agent analyzes all code files."""
        language: str = chunk.get("language", "unknown")
        return language != "unknown"
