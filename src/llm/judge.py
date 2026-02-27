from src.graph.state import Suggestion
from src.llm.router import ModelRouter, ModelTier


class LLMJudge:
    """LLM-as-judge for validating suggestions."""

    def __init__(self):
        self.router = ModelRouter()

    async def validate_suggestion(self, suggestion: Suggestion) -> bool:
        """
        Validate a single suggestion using LLM.

        Args:
            suggestion: Suggestion to validate

        Returns:
            True if suggestion is valid
        """
        prompt = f"""Validate this code review suggestion:

File: {suggestion["file_path"]}
Line: {suggestion["line_number"]}
Category: {suggestion["category"]}
Severity: {suggestion["severity"]}
Message: {suggestion["message"]}
Suggested fix: {suggestion.get("suggestion", "N/A")}
Confidence: {suggestion["confidence"]}

Evaluate if this suggestion is:
1. Accurate - Does it identify a real issue?
2. Actionable - Can the developer fix it?
3. Appropriate - Is the severity correct?
4. Valuable - Does it improve the code?

Return JSON: {{"valid": true/false, "reason": "brief explanation"}}"""

        try:
            result = await self.router.route_json(prompt=prompt, tier=ModelTier.BALANCED)

            return result.get("valid", True)

        except Exception:
            # If validation fails, accept the suggestion
            return True

    async def rank_suggestions(
        self, suggestions: list[Suggestion], top_k: int = 10
    ) -> list[Suggestion]:
        """
        Rank suggestions by importance and quality.

        Args:
            suggestions: List of suggestions
            top_k: Number of top suggestions to return

        Returns:
            Ranked list of suggestions
        """
        if len(suggestions) <= top_k:
            return suggestions

        # Format suggestions for LLM
        suggestions_text = "\n\n".join(
            [
                f"{i + 1}. [{s['severity'].upper()}] {s['category']}: {s['message']} (confidence: {s['confidence']})"
                for i, s in enumerate(suggestions[:50])  # Limit to 50 for context
            ]
        )

        prompt = f"""Rank these code review suggestions by importance:

{suggestions_text}

Consider:
1. Security issues are most critical
2. Logic errors before style issues
3. High confidence suggestions
4. Actionability

Return the indices (1-based) of the top {top_k} most important suggestions as a JSON array."""

        try:
            result = await self.router.route_json(prompt=prompt, tier=ModelTier.BALANCED)

            indices = result if isinstance(result, list) else result.get("indices", [])

            # Map indices back to suggestions
            ranked = []
            for idx in indices[:top_k]:
                if isinstance(idx, int) and 1 <= idx <= len(suggestions):
                    ranked.append(suggestions[idx - 1])

            # Add remaining suggestions if we didn't get enough
            if len(ranked) < top_k:
                existing = {id(s) for s in ranked}
                for s in suggestions:
                    if id(s) not in existing and len(ranked) < top_k:
                        ranked.append(s)

            return ranked

        except Exception:
            # Fall back to severity-based sorting
            severity_order = {"error": 0, "warning": 1, "suggestion": 2, "note": 3}
            return sorted(
                suggestions,
                key=lambda s: (severity_order.get(s["severity"], 4), -s.get("confidence", 0)),
            )[:top_k]

    async def check_conflicts(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """
        Check for conflicting suggestions and resolve them.

        Args:
            suggestions: List of suggestions

        Returns:
            List of non-conflicting suggestions
        """
        if len(suggestions) <= 1:
            return suggestions

        # Group by file and line
        by_location: dict[str, list[Suggestion]] = {}
        for s in suggestions:
            key = f"{s['file_path']}:{s['line_number']}"
            if key not in by_location:
                by_location[key] = []
            by_location[key].append(s)

        # Check locations with multiple suggestions
        conflicting = []
        for _key, loc_suggestions in by_location.items():
            if len(loc_suggestions) > 1:
                conflicting.extend(loc_suggestions)

        if len(conflicting) < 2:
            return suggestions

        # Format for LLM
        conflict_text = "\n\n".join(
            [f"{i + 1}. {s['category']}: {s['message']}" for i, s in enumerate(conflicting)]
        )

        prompt = f"""These suggestions may conflict. Identify which to keep:

{conflict_text}

Keep suggestions that:
1. Are most specific and actionable
2. Have highest severity
3. Are most likely to improve code quality

Return indices (1-based) of suggestions to KEEP as JSON array."""

        try:
            result = await self.router.route_json(prompt=prompt, tier=ModelTier.BALANCED)

            indices = result if isinstance(result, list) else result.get("indices", [])

            # Build final list
            to_keep = set()
            for idx in indices:
                if isinstance(idx, int) and 1 <= idx <= len(conflicting):
                    to_keep.add(id(conflicting[idx - 1]))

            # Keep non-conflicting and selected conflicting
            result_suggestions = []
            for s in suggestions:
                key = f"{s['file_path']}:{s['line_number']}"
                if key not in by_location or len(by_location[key]) == 1 or id(s) in to_keep:
                    result_suggestions.append(s)

            return result_suggestions

        except Exception:
            # Fall back to keeping all
            return suggestions
