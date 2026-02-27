from src.graph.state import Suggestion


class Deduplicator:
    """Remove duplicate suggestions."""

    def __init__(self, line_tolerance: int = 3, message_similarity_threshold: float = 0.8):
        """
        Initialize deduplicator.

        Args:
            line_tolerance: Lines within this range are considered same location
            message_similarity_threshold: Similarity threshold for message comparison
        """
        self.line_tolerance = line_tolerance
        self.message_similarity_threshold = message_similarity_threshold

    def deduplicate(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """
        Remove duplicate suggestions.

        Args:
            suggestions: List of suggestions

        Returns:
            Deduplicated list
        """
        if not suggestions:
            return []

        # Group by file
        by_file: dict[str, list[Suggestion]] = {}
        for s in suggestions:
            file_path = s["file_path"]
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(s)

        # Deduplicate each file's suggestions
        result = []
        for _file_path, file_suggestions in by_file.items():
            deduped = self._deduplicate_file_suggestions(file_suggestions)
            result.extend(deduped)

        return result

    def _deduplicate_file_suggestions(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """Deduplicate suggestions within a single file."""
        if len(suggestions) <= 1:
            return suggestions

        # Sort by line number
        sorted_suggestions = sorted(suggestions, key=lambda s: s["line_number"])

        result = []
        seen: set[str] = set()

        for suggestion in sorted_suggestions:
            # Create a signature for comparison
            signature = self._create_signature(suggestion)

            # Check if this is a duplicate
            is_duplicate = False
            for seen_sig in seen:
                if self._is_duplicate(signature, seen_sig):
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen.add(signature)
                result.append(suggestion)

        return result

    def _create_signature(self, suggestion: Suggestion) -> str:
        """Create a signature for deduplication comparison."""
        # Normalize message
        message = suggestion["message"].lower().strip()
        message = " ".join(message.split())  # Normalize whitespace

        # Round line number to tolerance
        line_bucket = suggestion["line_number"] // self.line_tolerance

        # Create signature
        category = suggestion["category"]
        return f"{category}:{line_bucket}:{message[:100]}"

    def _is_duplicate(self, sig1: str, sig2: str) -> bool:
        """Check if two signatures represent duplicates."""
        parts1 = sig1.split(":", 2)
        parts2 = sig2.split(":", 2)

        # Must be same category
        if parts1[0] != parts2[0]:
            return False

        # Must be in same line bucket
        if parts1[1] != parts2[1]:
            return False

        # Check message similarity
        msg1 = parts1[2] if len(parts1) > 2 else ""
        msg2 = parts2[2] if len(parts2) > 2 else ""

        similarity = self._calculate_similarity(msg1, msg2)
        return similarity >= self.message_similarity_threshold

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two strings."""
        if s1 == s2:
            return 1.0

        if not s1 or not s2:
            return 0.0

        # Use Jaccard similarity on word sets
        words1 = set(s1.split())
        words2 = set(s2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def deduplicate_by_priority(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """
        Deduplicate keeping highest priority suggestion.

        Priority order:
        1. Error severity
        2. Higher confidence
        3. Security category

        Args:
            suggestions: List of suggestions

        Returns:
            Deduplicated list with highest priority kept
        """
        if not suggestions:
            return []

        # Group by location
        by_location: dict[str, list[Suggestion]] = {}
        for s in suggestions:
            key = f"{s['file_path']}:{s['line_number']}"
            if key not in by_location:
                by_location[key] = []
            by_location[key].append(s)

        # Select highest priority from each location
        result = []
        for location_suggestions in by_location.values():
            best = self._select_highest_priority(location_suggestions)
            result.append(best)

        return result

    def _select_highest_priority(self, suggestions: list[Suggestion]) -> Suggestion:
        """Select the highest priority suggestion."""
        severity_order = {"error": 0, "warning": 1, "suggestion": 2, "note": 3}
        category_priority = {"security": 0, "logic": 1, "pattern": 2, "style": 3}

        def priority_key(s):
            return (
                severity_order.get(s["severity"], 4),
                category_priority.get(s["category"], 5),
                -s.get("confidence", 0),
            )

        return min(suggestions, key=priority_key)
