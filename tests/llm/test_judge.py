"""Tests for LLMJudge."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from graph.state import Suggestion


def _make_suggestion(**overrides) -> Suggestion:
    """Helper to create a Suggestion dict with defaults."""
    base: Suggestion = {
        "file_path": "src/main.py",
        "line_number": 10,
        "message": "Test issue",
        "severity": "warning",
        "suggestion": "Fix it",
        "agent_type": "test",
        "confidence": 0.8,
        "category": "test",
    }
    base.update(overrides)
    return base


class TestLLMJudgeInit:
    """Test LLMJudge initialization."""

    @patch("llm.judge.ModelRouter")
    def test_init_creates_router(self, mock_router_class):
        """Test that init creates a ModelRouter."""
        from llm.judge import LLMJudge

        mock_router_instance = Mock()
        mock_router_class.return_value = mock_router_instance

        judge = LLMJudge()

        mock_router_class.assert_called_once()
        assert judge.router is mock_router_instance


class TestLLMJudgeValidateSuggestion:
    """Test LLMJudge.validate_suggestion method."""

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_validate_suggestion_valid(self, mock_router_class):
        """Test validating a suggestion that is deemed valid."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(
            return_value={"valid": True, "reason": "Good suggestion"}
        )
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestion = _make_suggestion()

        result = await judge.validate_suggestion(suggestion)

        assert result is True
        mock_router.route_json.assert_called_once()

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_validate_suggestion_invalid(self, mock_router_class):
        """Test validating a suggestion that is deemed invalid."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(
            return_value={"valid": False, "reason": "Not actionable"}
        )
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestion = _make_suggestion()

        result = await judge.validate_suggestion(suggestion)

        assert result is False

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_validate_suggestion_missing_valid_key(self, mock_router_class):
        """Test that missing 'valid' key defaults to True."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value={"reason": "Some reason"})
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestion = _make_suggestion()

        result = await judge.validate_suggestion(suggestion)

        assert result is True

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_validate_suggestion_exception_returns_true(self, mock_router_class):
        """Test that exceptions during validation default to accepting the suggestion."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(side_effect=Exception("LLM Error"))
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestion = _make_suggestion()

        result = await judge.validate_suggestion(suggestion)

        assert result is True

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_validate_suggestion_uses_balanced_tier(self, mock_router_class):
        """Test that validation uses BALANCED tier."""
        from llm.judge import LLMJudge
        from llm.router import ModelTier

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value={"valid": True})
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        await judge.validate_suggestion(_make_suggestion())

        call_kwargs = mock_router.route_json.call_args.kwargs
        assert call_kwargs["tier"] == ModelTier.BALANCED

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_validate_suggestion_prompt_contains_details(self, mock_router_class):
        """Test that the validation prompt includes all suggestion details."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value={"valid": True})
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestion = _make_suggestion(
            file_path="src/handler.py",
            line_number=42,
            category="security",
            severity="error",
            message="SQL injection vulnerability",
            suggestion="Use parameterized queries",
            confidence=0.95,
        )

        await judge.validate_suggestion(suggestion)

        call_kwargs = mock_router.route_json.call_args.kwargs
        prompt = call_kwargs["prompt"]
        assert "src/handler.py" in prompt
        assert "42" in prompt
        assert "security" in prompt
        assert "error" in prompt
        assert "SQL injection vulnerability" in prompt
        assert "Use parameterized queries" in prompt
        assert "0.95" in prompt

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_validate_suggestion_no_suggestion_field(self, mock_router_class):
        """Test validation when suggestion field is None (uses .get with default)."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value={"valid": True})
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        # When suggestion is None, .get returns None (key exists), not "N/A"
        suggestion = _make_suggestion(suggestion=None)
        await judge.validate_suggestion(suggestion)

        call_kwargs = mock_router.route_json.call_args.kwargs
        prompt = call_kwargs["prompt"]
        assert "None" in prompt

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_validate_suggestion_missing_suggestion_key(self, mock_router_class):
        """Test validation when suggestion key is completely absent (get returns N/A)."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value={"valid": True})
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestion = _make_suggestion()
        # Remove the 'suggestion' key entirely so .get defaults to "N/A"
        del suggestion["suggestion"]
        await judge.validate_suggestion(suggestion)

        call_kwargs = mock_router.route_json.call_args.kwargs
        prompt = call_kwargs["prompt"]
        assert "N/A" in prompt


class TestLLMJudgeRankSuggestions:
    """Test LLMJudge.rank_suggestions method."""

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_fewer_than_top_k(self, mock_router_class):
        """Test that suggestions are returned as-is when fewer than top_k."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestions = [_make_suggestion(line_number=i) for i in range(5)]
        result = await judge.rank_suggestions(suggestions, top_k=10)

        assert result == suggestions
        # Should not call LLM when fewer than top_k
        mock_router.route_json.assert_not_called()

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_equal_to_top_k(self, mock_router_class):
        """Test that suggestions are returned as-is when equal to top_k."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestions = [_make_suggestion(line_number=i) for i in range(10)]
        result = await judge.rank_suggestions(suggestions, top_k=10)

        assert result == suggestions
        mock_router.route_json.assert_not_called()

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_llm_returns_indices(self, mock_router_class):
        """Test ranking when LLM returns indices as list."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value=[3, 1, 5])
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestions = [_make_suggestion(line_number=i, message=f"Issue {i}") for i in range(10)]
        result = await judge.rank_suggestions(suggestions, top_k=3)

        # Should return suggestions at indices 3, 1, 5 (1-based)
        assert len(result) == 3
        assert result[0]["line_number"] == 2  # index 3 -> suggestions[2]
        assert result[1]["line_number"] == 0  # index 1 -> suggestions[0]
        assert result[2]["line_number"] == 4  # index 5 -> suggestions[4]

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_llm_returns_dict_with_indices(self, mock_router_class):
        """Test ranking when LLM returns dict with indices key."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value={"indices": [2, 4]})
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestions = [_make_suggestion(line_number=i) for i in range(5)]
        result = await judge.rank_suggestions(suggestions, top_k=2)

        assert len(result) == 2
        assert result[0]["line_number"] == 1  # index 2 -> suggestions[1]
        assert result[1]["line_number"] == 3  # index 4 -> suggestions[3]

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_fills_remaining(self, mock_router_class):
        """Test that remaining slots are filled if LLM returns fewer than top_k."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value=[1])
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestions = [_make_suggestion(line_number=i) for i in range(5)]
        result = await judge.rank_suggestions(suggestions, top_k=3)

        assert len(result) == 3
        # First should be the LLM-selected one
        assert result[0]["line_number"] == 0  # index 1 -> suggestions[0]
        # Remaining filled from the rest of the suggestions
        assert result[1]["line_number"] in [1, 2, 3, 4]
        assert result[2]["line_number"] in [1, 2, 3, 4]

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_invalid_indices_skipped(self, mock_router_class):
        """Test that invalid indices (out of range, non-int) are skipped."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value=[0, -1, 100, "invalid", 1])
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestions = [_make_suggestion(line_number=i) for i in range(5)]
        result = await judge.rank_suggestions(suggestions, top_k=3)

        # Only index 1 is valid (1-based, range 1..5), rest are invalid
        assert len(result) == 3
        assert result[0]["line_number"] == 0  # index 1 -> suggestions[0]

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_exception_falls_back_to_severity(self, mock_router_class):
        """Test that exceptions fall back to severity-based sorting."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(side_effect=Exception("LLM Error"))
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        suggestions = [
            _make_suggestion(severity="suggestion", confidence=0.5, line_number=1),
            _make_suggestion(severity="error", confidence=0.9, line_number=2),
            _make_suggestion(severity="warning", confidence=0.7, line_number=3),
            _make_suggestion(severity="note", confidence=0.6, line_number=4),
            _make_suggestion(severity="error", confidence=0.95, line_number=5),
        ]
        result = await judge.rank_suggestions(suggestions, top_k=3)

        # Should be sorted by severity (error < warning < suggestion < note)
        # then by confidence descending
        assert len(result) == 3
        assert result[0]["severity"] == "error"
        assert result[0]["confidence"] == 0.95  # Higher confidence error first
        assert result[1]["severity"] == "error"
        assert result[1]["confidence"] == 0.9
        assert result[2]["severity"] == "warning"

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_exception_unknown_severity(self, mock_router_class):
        """Test fallback sorting with unknown severity levels."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(side_effect=Exception("LLM Error"))
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        # Need more suggestions than top_k to trigger LLM call (and thus exception path)
        suggestions = [
            _make_suggestion(severity="unknown", confidence=0.9, line_number=1),
            _make_suggestion(severity="error", confidence=0.8, line_number=2),
            _make_suggestion(severity="note", confidence=0.5, line_number=3),
        ]
        result = await judge.rank_suggestions(suggestions, top_k=2)

        # error (0) < unknown (4) < note (3), so error first, then note
        assert len(result) == 2
        assert result[0]["severity"] == "error"
        assert result[1]["severity"] == "note"

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_rank_suggestions_limits_to_50_for_context(self, mock_router_class):
        """Test that only first 50 suggestions are included in the prompt."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value=[1, 2, 3])
        mock_router_class.return_value = mock_router

        judge = LLMJudge()

        # Create 60 suggestions
        suggestions = [_make_suggestion(line_number=i) for i in range(60)]
        await judge.rank_suggestions(suggestions, top_k=3)

        call_kwargs = mock_router.route_json.call_args.kwargs
        prompt = call_kwargs["prompt"]

        # Should contain numbering up to 50 but not 51+
        assert "50." in prompt
        assert "51." not in prompt


class TestLLMJudgeCheckConflicts:
    """Test LLMJudge.check_conflicts method."""

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_empty_list(self, mock_router_class):
        """Test with empty suggestions list."""
        from llm.judge import LLMJudge

        judge = LLMJudge()
        result = await judge.check_conflicts([])

        assert result == []

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_single_suggestion(self, mock_router_class):
        """Test with a single suggestion (no conflicts possible)."""
        from llm.judge import LLMJudge

        judge = LLMJudge()
        suggestions = [_make_suggestion()]
        result = await judge.check_conflicts(suggestions)

        assert result == suggestions

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_no_conflicts(self, mock_router_class):
        """Test with suggestions at different locations (no conflicts)."""
        from llm.judge import LLMJudge

        judge = LLMJudge()
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=1),
            _make_suggestion(file_path="a.py", line_number=2),
            _make_suggestion(file_path="b.py", line_number=1),
        ]
        result = await judge.check_conflicts(suggestions)

        # No conflicts, should return all
        assert result == suggestions

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_with_conflicts_llm_resolves(self, mock_router_class):
        """Test conflict resolution when LLM selects which to keep."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        # Keep the first conflicting suggestion (index 1)
        mock_router.route_json = AsyncMock(return_value=[1])
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=10, category="security"),
            _make_suggestion(file_path="a.py", line_number=10, category="style"),
            _make_suggestion(file_path="b.py", line_number=5, category="logic"),
        ]

        result = await judge.check_conflicts(suggestions)

        # Should keep the first conflicting suggestion and the non-conflicting one
        assert len(result) == 2
        categories = [s["category"] for s in result]
        assert "security" in categories
        assert "logic" in categories

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_llm_returns_dict_with_indices(self, mock_router_class):
        """Test conflict resolution when LLM returns dict with indices."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value={"indices": [1, 2]})
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=10, category="security"),
            _make_suggestion(file_path="a.py", line_number=10, category="style"),
            _make_suggestion(file_path="b.py", line_number=5, category="logic"),
        ]

        result = await judge.check_conflicts(suggestions)

        # Both conflicting suggestions should be kept (indices 1 and 2)
        assert len(result) == 3

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_exception_returns_all(self, mock_router_class):
        """Test that exceptions return all suggestions (no filtering)."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(side_effect=Exception("LLM Error"))
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=10, category="security"),
            _make_suggestion(file_path="a.py", line_number=10, category="style"),
        ]

        result = await judge.check_conflicts(suggestions)

        assert result == suggestions

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_invalid_indices_ignored(self, mock_router_class):
        """Test that invalid indices in LLM response are ignored."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value=[0, -1, 100, "bad"])
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=10, category="security"),
            _make_suggestion(file_path="a.py", line_number=10, category="style"),
            _make_suggestion(file_path="b.py", line_number=5, category="logic"),
        ]

        result = await judge.check_conflicts(suggestions)

        # None of the conflicting indices are valid, so conflicting suggestions removed
        # but non-conflicting suggestions (b.py:5) should remain
        assert any(s["file_path"] == "b.py" for s in result)

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_multiple_locations(self, mock_router_class):
        """Test conflict detection across multiple conflicting locations."""
        from llm.judge import LLMJudge

        mock_router = Mock()
        # Keep first from each conflict group
        mock_router.route_json = AsyncMock(return_value=[1, 3])
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=10, category="s1"),
            _make_suggestion(file_path="a.py", line_number=10, category="s2"),
            _make_suggestion(file_path="b.py", line_number=20, category="s3"),
            _make_suggestion(file_path="b.py", line_number=20, category="s4"),
            _make_suggestion(file_path="c.py", line_number=1, category="s5"),
        ]

        result = await judge.check_conflicts(suggestions)

        # Kept: s1 (idx 1), s3 (idx 3) + non-conflicting s5
        categories = [s["category"] for s in result]
        assert "s1" in categories
        assert "s3" in categories
        assert "s5" in categories

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_only_one_conflict_location(self, mock_router_class):
        """Test when conflicting is only at one location with <2 total conflicting."""
        from llm.judge import LLMJudge

        judge = LLMJudge()

        # All at unique locations - no conflicts
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=1, category="s1"),
            _make_suggestion(file_path="a.py", line_number=2, category="s2"),
        ]

        result = await judge.check_conflicts(suggestions)

        # No conflicts, return as-is
        assert result == suggestions

    @patch("llm.judge.ModelRouter")
    @pytest.mark.asyncio
    async def test_check_conflicts_uses_balanced_tier(self, mock_router_class):
        """Test that conflict checking uses BALANCED tier."""
        from llm.judge import LLMJudge
        from llm.router import ModelTier

        mock_router = Mock()
        mock_router.route_json = AsyncMock(return_value=[1])
        mock_router_class.return_value = mock_router

        judge = LLMJudge()
        suggestions = [
            _make_suggestion(file_path="a.py", line_number=10, category="s1"),
            _make_suggestion(file_path="a.py", line_number=10, category="s2"),
        ]

        await judge.check_conflicts(suggestions)

        call_kwargs = mock_router.route_json.call_args.kwargs
        assert call_kwargs["tier"] == ModelTier.BALANCED
