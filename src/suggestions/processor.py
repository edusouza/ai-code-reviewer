from typing import Any, cast

from src.graph.state import Suggestion
from src.llm.judge import LLMJudge
from src.suggestions.deduplicator import Deduplicator
from src.suggestions.severity import SeverityClassifier


class SuggestionProcessor:
    """Main pipeline for processing suggestions."""

    def __init__(self, max_suggestions: int = 50, severity_threshold: str = "suggestion"):
        """
        Initialize the suggestion processor.

        Args:
            max_suggestions: Maximum number of suggestions to return
            severity_threshold: Minimum severity level to include
        """
        self.max_suggestions = max_suggestions
        self.severity_threshold = severity_threshold
        self.deduplicator = Deduplicator()
        self.severity_classifier = SeverityClassifier()
        self.judge = LLMJudge()

    async def process(
        self,
        suggestions: list[Suggestion],
        enable_deduplication: bool = True,
        enable_severity_filter: bool = True,
        enable_validation: bool = True,
        enable_ranking: bool = True,
    ) -> dict[str, Any]:
        """
        Process suggestions through the full pipeline.

        Args:
            suggestions: Raw suggestions from agents
            enable_deduplication: Whether to deduplicate suggestions
            enable_severity_filter: Whether to filter by severity
            enable_validation: Whether to validate with LLM judge
            enable_ranking: Whether to rank suggestions

        Returns:
            Dictionary with processed suggestions and metadata
        """
        original_count = len(suggestions)
        metadata: dict[str, Any] = {"original_count": original_count, "steps": []}

        # Step 1: Deduplicate
        if enable_deduplication:
            suggestions = self.deduplicator.deduplicate(suggestions)
            metadata["steps"].append(
                {
                    "step": "deduplication",
                    "count": len(suggestions),
                    "removed": original_count - len(suggestions),
                }
            )

        # Step 2: Severity filter
        if enable_severity_filter:
            suggestions = self.severity_classifier.filter_by_threshold(
                suggestions, self.severity_threshold
            )
            metadata["steps"].append(
                {
                    "step": "severity_filter",
                    "count": len(suggestions),
                    "threshold": self.severity_threshold,
                }
            )

        # Step 3: Validate with LLM judge
        if enable_validation:
            validated = []
            rejected = []
            for suggestion in suggestions:
                is_valid = await self.judge.validate_suggestion(suggestion)
                if is_valid:
                    validated.append(suggestion)
                else:
                    rejected.append(suggestion)
            suggestions = validated
            metadata["steps"].append(
                {"step": "validation", "count": len(suggestions), "rejected": len(rejected)}
            )

        # Step 4: Rank and limit
        if enable_ranking and len(suggestions) > self.max_suggestions:
            suggestions = await self.judge.rank_suggestions(suggestions, top_k=self.max_suggestions)
            metadata["steps"].append(
                {"step": "ranking", "count": len(suggestions), "limit": self.max_suggestions}
            )
        elif len(suggestions) > self.max_suggestions:
            # Simple truncation if ranking disabled
            suggestions = suggestions[: self.max_suggestions]
            metadata["steps"].append(
                {"step": "truncation", "count": len(suggestions), "limit": self.max_suggestions}
            )

        # Calculate statistics
        severity_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for s in suggestions:
            severity_counts[s["severity"]] = severity_counts.get(s["severity"], 0) + 1
            category_counts[s["category"]] = category_counts.get(s["category"], 0) + 1

        metadata["final_count"] = len(suggestions)
        metadata["severity_counts"] = severity_counts
        metadata["category_counts"] = category_counts

        return {"suggestions": suggestions, "metadata": metadata}

    async def quick_process(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """
        Quick processing without LLM validation.

        Args:
            suggestions: Raw suggestions

        Returns:
            Processed suggestions
        """
        result = await self.process(
            suggestions,
            enable_deduplication=True,
            enable_severity_filter=True,
            enable_validation=False,
            enable_ranking=False,
        )
        return cast(list[Suggestion], result["suggestions"])

    async def strict_process(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """
        Strict processing with all validations.

        Args:
            suggestions: Raw suggestions

        Returns:
            Processed suggestions
        """
        result = await self.process(
            suggestions,
            enable_deduplication=True,
            enable_severity_filter=True,
            enable_validation=True,
            enable_ranking=True,
        )
        return cast(list[Suggestion], result["suggestions"])
