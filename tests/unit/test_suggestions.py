"""Tests for suggestion processing."""

from unittest.mock import AsyncMock, patch

import pytest

from suggestions.deduplicator import Deduplicator
from suggestions.processor import SuggestionProcessor


@pytest.mark.unit
class TestSuggestionProcessor:
    """Test suite for SuggestionProcessor."""

    def test_init(self):
        """Test processor initialization."""
        processor = SuggestionProcessor(max_suggestions=50, severity_threshold="warning")

        assert processor.max_suggestions == 50
        assert processor.severity_threshold == "warning"
        assert processor.deduplicator is not None
        assert processor.severity_classifier is not None
        assert processor.judge is not None

    def test_init_defaults(self):
        """Test processor initialization with defaults."""
        processor = SuggestionProcessor()

        assert processor.max_suggestions == 50
        assert processor.severity_threshold == "suggestion"

    @pytest.mark.asyncio
    async def test_process_full_pipeline(self, sample_suggestions):
        """Test full processing pipeline."""
        processor = SuggestionProcessor(max_suggestions=10)

        with (
            patch.object(processor.deduplicator, "deduplicate", return_value=sample_suggestions),
            patch.object(
                processor.severity_classifier,
                "filter_by_threshold",
                return_value=sample_suggestions,
            ),
            patch.object(processor.judge, "validate_suggestion", AsyncMock(return_value=True)),
        ):
            result = await processor.process(
                sample_suggestions,
                enable_deduplication=True,
                enable_severity_filter=True,
                enable_validation=True,
                enable_ranking=False,
            )

        assert "suggestions" in result
        assert "metadata" in result
        assert result["metadata"]["original_count"] == len(sample_suggestions)

    @pytest.mark.asyncio
    async def test_process_no_deduplication(self, sample_suggestions):
        """Test processing without deduplication."""
        processor = SuggestionProcessor()

        result = await processor.process(
            sample_suggestions,
            enable_deduplication=False,
            enable_severity_filter=False,
            enable_validation=False,
            enable_ranking=False,
        )

        assert len(result["suggestions"]) == len(sample_suggestions)

    @pytest.mark.asyncio
    async def test_process_with_validation(self, sample_suggestions):
        """Test processing with LLM validation."""
        processor = SuggestionProcessor()

        with patch.object(processor.judge, "validate_suggestion", AsyncMock(return_value=True)):
            result = await processor.process(
                sample_suggestions,
                enable_deduplication=False,
                enable_severity_filter=False,
                enable_validation=True,
                enable_ranking=False,
            )

        assert result["metadata"]["steps"][0]["step"] == "validation"

    @pytest.mark.asyncio
    async def test_process_with_rejection(self, sample_suggestions):
        """Test processing with some suggestions rejected."""
        processor = SuggestionProcessor()

        # Mock validation to reject first suggestion
        async def mock_validate(suggestion):
            return suggestion["severity"] != "error"

        with patch.object(processor.judge, "validate_suggestion", mock_validate):
            result = await processor.process(
                sample_suggestions,
                enable_deduplication=False,
                enable_severity_filter=False,
                enable_validation=True,
                enable_ranking=False,
            )

        # Should have filtered out error severity
        validation_step = [s for s in result["metadata"]["steps"] if s["step"] == "validation"][0]
        assert validation_step["rejected"] == 1

    @pytest.mark.asyncio
    async def test_process_with_ranking(self, sample_suggestions):
        """Test processing with ranking."""
        processor = SuggestionProcessor(max_suggestions=2)

        with patch.object(
            processor.judge, "rank_suggestions", AsyncMock(return_value=sample_suggestions[:2])
        ):
            result = await processor.process(
                sample_suggestions,
                enable_deduplication=False,
                enable_severity_filter=False,
                enable_validation=False,
                enable_ranking=True,
            )

        assert result["metadata"]["steps"][0]["step"] == "ranking"
        assert result["metadata"]["steps"][0]["limit"] == 2

    @pytest.mark.asyncio
    async def test_process_simple_truncation(self, sample_suggestions):
        """Test simple truncation without ranking."""
        processor = SuggestionProcessor(max_suggestions=2)

        result = await processor.process(
            sample_suggestions,
            enable_deduplication=False,
            enable_severity_filter=False,
            enable_validation=False,
            enable_ranking=False,
        )

        assert len(result["suggestions"]) == 2
        assert result["metadata"]["steps"][0]["step"] == "truncation"

    @pytest.mark.asyncio
    async def test_process_severity_counts(self, sample_suggestions):
        """Test that severity counts are calculated."""
        processor = SuggestionProcessor()

        result = await processor.process(
            sample_suggestions,
            enable_deduplication=False,
            enable_severity_filter=False,
            enable_validation=False,
            enable_ranking=False,
        )

        assert "severity_counts" in result["metadata"]
        assert result["metadata"]["severity_counts"]["error"] == 1
        assert result["metadata"]["severity_counts"]["warning"] == 1
        assert result["metadata"]["severity_counts"]["suggestion"] == 1

    @pytest.mark.asyncio
    async def test_process_category_counts(self, sample_suggestions):
        """Test that category counts are calculated."""
        processor = SuggestionProcessor()

        result = await processor.process(
            sample_suggestions,
            enable_deduplication=False,
            enable_severity_filter=False,
            enable_validation=False,
            enable_ranking=False,
        )

        assert "category_counts" in result["metadata"]
        assert result["metadata"]["category_counts"]["security"] == 1
        assert result["metadata"]["category_counts"]["style"] == 1
        assert result["metadata"]["category_counts"]["logic"] == 1

    @pytest.mark.asyncio
    async def test_quick_process(self, sample_suggestions):
        """Test quick processing method."""
        processor = SuggestionProcessor()

        suggestions = await processor.quick_process(sample_suggestions)

        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_strict_process(self, sample_suggestions):
        """Test strict processing method."""
        processor = SuggestionProcessor()

        with (
            patch.object(processor.judge, "validate_suggestion", AsyncMock(return_value=True)),
            patch.object(
                processor.judge, "rank_suggestions", AsyncMock(return_value=sample_suggestions)
            ),
        ):
            suggestions = await processor.strict_process(sample_suggestions)

        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_process_empty_suggestions(self):
        """Test processing empty suggestions list."""
        processor = SuggestionProcessor()

        result = await processor.process([])

        assert result["suggestions"] == []
        assert result["metadata"]["original_count"] == 0
        assert result["metadata"]["final_count"] == 0


@pytest.mark.unit
class TestDeduplicator:
    """Test suite for Deduplicator."""

    def test_init(self):
        """Test deduplicator initialization."""
        dedup = Deduplicator(line_tolerance=3, message_similarity_threshold=0.8)

        assert dedup.line_tolerance == 3
        assert dedup.message_similarity_threshold == 0.8

    def test_deduplicate_empty(self):
        """Test deduplication of empty list."""
        dedup = Deduplicator()

        result = dedup.deduplicate([])

        assert result == []

    def test_deduplicate_single(self):
        """Test deduplication of single suggestion."""
        dedup = Deduplicator()

        suggestions = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Test issue",
                "category": "style",
            }
        ]

        result = dedup.deduplicate(suggestions)

        assert len(result) == 1

    def test_deduplicate_exact_duplicates(self):
        """Test deduplication of exact duplicates."""
        dedup = Deduplicator()

        suggestions = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Test issue",
                "category": "style",
            },
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Test issue",
                "category": "style",
            },
        ]

        result = dedup.deduplicate(suggestions)

        assert len(result) == 1

    def test_deduplicate_nearby_lines(self):
        """Test deduplication of nearby lines."""
        dedup = Deduplicator(line_tolerance=5)

        suggestions = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Test issue",
                "category": "style",
            },
            {
                "file_path": "test.py",
                "line_number": 11,
                "message": "Test issue",
                "category": "style",
            },
        ]

        result = dedup.deduplicate(suggestions)

        # Should deduplicate since within line tolerance
        assert len(result) == 1

    def test_deduplicate_different_files(self):
        """Test that different files are not deduplicated."""
        dedup = Deduplicator()

        suggestions = [
            {
                "file_path": "test1.py",
                "line_number": 10,
                "message": "Test issue",
                "category": "style",
            },
            {
                "file_path": "test2.py",
                "line_number": 10,
                "message": "Test issue",
                "category": "style",
            },
        ]

        result = dedup.deduplicate(suggestions)

        assert len(result) == 2

    def test_deduplicate_similar_messages(self):
        """Test deduplication of similar messages."""
        dedup = Deduplicator(message_similarity_threshold=0.8)

        suggestions = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Line too long exceeds limit",
                "category": "style",
            },
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Line too long exceeds the limit",
                "category": "style",
            },
        ]

        result = dedup.deduplicate(suggestions)

        # Should deduplicate since messages are similar
        assert len(result) == 1

    def test_deduplicate_different_categories(self):
        """Test that different categories are not deduplicated."""
        dedup = Deduplicator()

        suggestions = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Test issue",
                "category": "style",
            },
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Test issue",
                "category": "security",
            },
        ]

        result = dedup.deduplicate(suggestions)

        assert len(result) == 2

    def test_calculate_similarity_identical(self):
        """Test similarity calculation for identical strings."""
        dedup = Deduplicator()

        similarity = dedup._calculate_similarity("test message", "test message")

        assert similarity == 1.0

    def test_calculate_similarity_completely_different(self):
        """Test similarity calculation for completely different strings."""
        dedup = Deduplicator()

        similarity = dedup._calculate_similarity("abc def", "xyz uvw")

        assert similarity == 0.0

    def test_calculate_similarity_partial(self):
        """Test similarity calculation for partially similar strings."""
        dedup = Deduplicator()

        similarity = dedup._calculate_similarity("line too long", "line is too long")

        assert 0.0 < similarity < 1.0

    def test_calculate_similarity_empty(self):
        """Test similarity calculation with empty strings."""
        dedup = Deduplicator()

        similarity = dedup._calculate_similarity("", "test")

        assert similarity == 0.0

    def test_deduplicate_by_priority(self):
        """Test deduplication by priority."""
        dedup = Deduplicator()

        suggestions = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Style issue",
                "category": "style",
                "severity": "suggestion",
                "confidence": 0.8,
            },
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Security issue",
                "category": "security",
                "severity": "error",
                "confidence": 0.9,
            },
        ]

        result = dedup.deduplicate_by_priority(suggestions)

        # Should keep the security error (higher priority)
        assert len(result) == 1
        assert result[0]["category"] == "security"

    def test_select_highest_priority_error_over_warning(self):
        """Test priority selection: error over warning."""
        dedup = Deduplicator()

        suggestions = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Warning",
                "category": "style",
                "severity": "warning",
                "confidence": 0.9,
            },
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Error",
                "category": "style",
                "severity": "error",
                "confidence": 0.8,
            },
        ]

        best = dedup._select_highest_priority(suggestions)

        assert best["severity"] == "error"

    def test_select_highest_priority_confidence(self):
        """Test priority selection: higher confidence wins."""
        dedup = Deduplicator()

        suggestions = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "Low confidence",
                "category": "style",
                "severity": "warning",
                "confidence": 0.5,
            },
            {
                "file_path": "test.py",
                "line_number": 10,
                "message": "High confidence",
                "category": "style",
                "severity": "warning",
                "confidence": 0.9,
            },
        ]

        best = dedup._select_highest_priority(suggestions)

        assert best["confidence"] == 0.9


@pytest.mark.unit
class TestDeduplicatorEdgeCases:
    """Test edge cases for Deduplicator."""

    def test_deduplicate_single_file(self):
        """Test deduplication within single file."""
        dedup = Deduplicator()

        suggestions = [
            {"file_path": "test.py", "line_number": 10, "message": "Issue 1", "category": "style"},
            {"file_path": "test.py", "line_number": 20, "message": "Issue 2", "category": "style"},
            {"file_path": "test.py", "line_number": 30, "message": "Issue 3", "category": "style"},
        ]

        result = dedup.deduplicate(suggestions)

        assert len(result) == 3  # All different locations

    def test_deduplicate_multiple_files(self):
        """Test deduplication across multiple files."""
        dedup = Deduplicator()

        suggestions = [
            {
                "file_path": "file1.py",
                "line_number": 10,
                "message": "Same issue",
                "category": "style",
            },
            {
                "file_path": "file2.py",
                "line_number": 10,
                "message": "Same issue",
                "category": "style",
            },
            {
                "file_path": "file1.py",
                "line_number": 10,
                "message": "Same issue",
                "category": "style",
            },  # Duplicate
        ]

        result = dedup.deduplicate(suggestions)

        assert len(result) == 2  # file1 deduplicated, file2 kept

    def test_create_signature_normalization(self):
        """Test message normalization in signature creation."""
        dedup = Deduplicator()

        suggestion = {
            "file_path": "test.py",
            "line_number": 10,
            "message": "  LINE   TOO   LONG  ",
            "category": "style",
        }

        signature = dedup._create_signature(suggestion)

        # Should be normalized: lowercase and single spaces
        assert "line too long" in signature

    def test_is_duplicate_different_categories(self):
        """Test duplicate detection with different categories."""
        dedup = Deduplicator()

        sig1 = "style:3:line too long"
        sig2 = "security:3:line too long"

        assert dedup._is_duplicate(sig1, sig2) is False

    def test_is_duplicate_different_lines(self):
        """Test duplicate detection with different line buckets."""
        dedup = Deduplicator(line_tolerance=3)

        sig1 = "style:1:line too long"  # line 1-3 bucket
        sig2 = "style:5:line too long"  # line 15-17 bucket (if tolerance is 3)

        # Line buckets: 1//3=0, 10//3=3, so different
        assert dedup._is_duplicate(sig1, sig2) is False
