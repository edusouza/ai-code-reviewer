from enum import StrEnum
from typing import Any

from src.graph.state import Suggestion


class SeverityLevel(StrEnum):
    """Severity levels in order of importance."""

    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"
    NOTE = "note"


class SeverityClassifier:
    """Classify and filter suggestions by severity."""

    # Severity priority (lower = more severe)
    SEVERITY_ORDER = {
        SeverityLevel.ERROR: 0,
        SeverityLevel.WARNING: 1,
        SeverityLevel.SUGGESTION: 2,
        SeverityLevel.NOTE: 3,
    }

    # Category overrides for severity
    CATEGORY_SEVERITY = {
        "security": {"default": SeverityLevel.WARNING, "high": SeverityLevel.ERROR},
        "logic": {"default": SeverityLevel.WARNING, "high": SeverityLevel.ERROR},
        "style": {"default": SeverityLevel.SUGGESTION},
        "pattern": {"default": SeverityLevel.SUGGESTION},
    }

    def __init__(self) -> None:
        pass

    def classify(self, suggestion: Suggestion) -> SeverityLevel:
        """
        Classify a suggestion's severity.

        Args:
            suggestion: Suggestion to classify

        Returns:
            Severity level
        """
        # Start with suggested severity
        severity = suggestion.get("severity", "suggestion")

        try:
            current_level = SeverityLevel(severity)
        except ValueError:
            current_level = SeverityLevel.SUGGESTION

        # Adjust based on category and confidence
        category = suggestion.get("category", "general")
        confidence = suggestion.get("confidence", 0.5)

        # High confidence security/logic issues are errors
        if category in ["security", "logic"] and confidence >= 0.9:
            return SeverityLevel.ERROR

        # Low confidence errors become warnings
        if current_level == SeverityLevel.ERROR and confidence < 0.7:
            return SeverityLevel.WARNING

        return current_level

    def filter_by_threshold(
        self, suggestions: list[Suggestion], threshold: str = "suggestion"
    ) -> list[Suggestion]:
        """
        Filter suggestions by severity threshold.

        Args:
            suggestions: List of suggestions
            threshold: Minimum severity to include

        Returns:
            Filtered suggestions
        """
        try:
            threshold_level = SeverityLevel(threshold)
        except ValueError:
            threshold_level = SeverityLevel.SUGGESTION

        threshold_priority = self.SEVERITY_ORDER[threshold_level]

        filtered = []
        for suggestion in suggestions:
            classified = self.classify(suggestion)
            suggestion["severity"] = classified.value

            if self.SEVERITY_ORDER[classified] <= threshold_priority:
                filtered.append(suggestion)

        return filtered

    def sort_by_severity(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """
        Sort suggestions by severity (most severe first).

        Args:
            suggestions: List of suggestions

        Returns:
            Sorted suggestions
        """

        def sort_key(s: Suggestion) -> tuple[int, float, str]:
            severity = self.classify(s)
            return (
                self.SEVERITY_ORDER[severity],
                -s.get("confidence", 0),  # Higher confidence first
                s.get("category", ""),  # Alphabetically by category
            )

        return sorted(suggestions, key=sort_key)

    def get_severity_stats(self, suggestions: list[Suggestion]) -> dict[str, Any]:
        """
        Get statistics about severity distribution.

        Args:
            suggestions: List of suggestions

        Returns:
            Statistics dictionary
        """
        stats: dict[str, Any] = {
            "error": 0,
            "warning": 0,
            "suggestion": 0,
            "note": 0,
            "total": len(suggestions),
        }

        for suggestion in suggestions:
            severity = self.classify(suggestion).value
            stats[severity] = stats.get(severity, 0) + 1

        # Calculate percentages
        if stats["total"] > 0:
            for level in ["error", "warning", "suggestion", "note"]:
                stats[f"{level}_percent"] = round(stats[level] / stats["total"] * 100, 1)

        return stats

    def should_block_merge(self, suggestions: list[Suggestion]) -> bool:
        """
        Determine if review should block merge.

        Args:
            suggestions: List of suggestions

        Returns:
            True if merge should be blocked
        """
        for suggestion in suggestions:
            severity = self.classify(suggestion)
            if severity == SeverityLevel.ERROR:
                return True

        return False

    def get_max_severity(self, suggestions: list[Suggestion]) -> SeverityLevel:
        """
        Get the maximum severity level in suggestions.

        Args:
            suggestions: List of suggestions

        Returns:
            Maximum severity level
        """
        if not suggestions:
            return SeverityLevel.NOTE

        max_priority = float("inf")
        max_severity = SeverityLevel.NOTE

        for suggestion in suggestions:
            severity = self.classify(suggestion)
            priority = self.SEVERITY_ORDER[severity]
            if priority < max_priority:
                max_priority = priority
                max_severity = severity

        return max_severity
