"""Tests for SeverityClassifier and SeverityLevel."""

import pytest

from suggestions.severity import SeverityClassifier, SeverityLevel


class TestSeverityLevel:
    """Tests for the SeverityLevel enum."""

    def test_error_value(self):
        assert SeverityLevel.ERROR == "error"
        assert SeverityLevel.ERROR.value == "error"

    def test_warning_value(self):
        assert SeverityLevel.WARNING == "warning"
        assert SeverityLevel.WARNING.value == "warning"

    def test_suggestion_value(self):
        assert SeverityLevel.SUGGESTION == "suggestion"
        assert SeverityLevel.SUGGESTION.value == "suggestion"

    def test_note_value(self):
        assert SeverityLevel.NOTE == "note"
        assert SeverityLevel.NOTE.value == "note"

    def test_severity_level_is_str_enum(self):
        """SeverityLevel values can be used directly as strings."""
        assert isinstance(SeverityLevel.ERROR, str)
        assert f"level: {SeverityLevel.ERROR}" == "level: error"

    def test_construct_from_string(self):
        """SeverityLevel can be constructed from a valid string."""
        assert SeverityLevel("error") is SeverityLevel.ERROR
        assert SeverityLevel("warning") is SeverityLevel.WARNING
        assert SeverityLevel("suggestion") is SeverityLevel.SUGGESTION
        assert SeverityLevel("note") is SeverityLevel.NOTE

    def test_construct_from_invalid_string_raises(self):
        """Invalid string raises ValueError."""
        with pytest.raises(ValueError):
            SeverityLevel("critical")


class TestSeverityClassifierInit:
    """Tests for SeverityClassifier initialization."""

    def test_init(self):
        """SeverityClassifier can be instantiated."""
        classifier = SeverityClassifier()
        assert classifier is not None

    def test_severity_order_has_all_levels(self):
        """SEVERITY_ORDER contains all severity levels."""
        assert SeverityLevel.ERROR in SeverityClassifier.SEVERITY_ORDER
        assert SeverityLevel.WARNING in SeverityClassifier.SEVERITY_ORDER
        assert SeverityLevel.SUGGESTION in SeverityClassifier.SEVERITY_ORDER
        assert SeverityLevel.NOTE in SeverityClassifier.SEVERITY_ORDER

    def test_severity_order_priorities(self):
        """Error has lowest number (highest priority), note has highest."""
        order = SeverityClassifier.SEVERITY_ORDER
        assert order[SeverityLevel.ERROR] < order[SeverityLevel.WARNING]
        assert order[SeverityLevel.WARNING] < order[SeverityLevel.SUGGESTION]
        assert order[SeverityLevel.SUGGESTION] < order[SeverityLevel.NOTE]

    def test_category_severity_mapping(self):
        """CATEGORY_SEVERITY has expected categories."""
        cats = SeverityClassifier.CATEGORY_SEVERITY
        assert "security" in cats
        assert "logic" in cats
        assert "style" in cats
        assert "pattern" in cats


class TestSeverityClassifierClassify:
    """Tests for SeverityClassifier.classify."""

    def setup_method(self):
        self.classifier = SeverityClassifier()

    def test_classify_uses_suggestion_severity(self):
        """A plain suggestion with valid severity returns that severity."""
        suggestion = {
            "severity": "warning",
            "category": "general",
            "confidence": 0.5,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.WARNING

    def test_classify_default_severity_when_missing(self):
        """When severity is missing, defaults to 'suggestion'."""
        suggestion = {"category": "general", "confidence": 0.5}
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.SUGGESTION

    def test_classify_invalid_severity_defaults_to_suggestion(self):
        """Invalid severity string defaults to SUGGESTION."""
        suggestion = {
            "severity": "critical",
            "category": "general",
            "confidence": 0.5,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.SUGGESTION

    def test_classify_high_confidence_security_returns_error(self):
        """Security issue with confidence >= 0.9 becomes ERROR."""
        suggestion = {
            "severity": "suggestion",
            "category": "security",
            "confidence": 0.95,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.ERROR

    def test_classify_high_confidence_logic_returns_error(self):
        """Logic issue with confidence >= 0.9 becomes ERROR."""
        suggestion = {
            "severity": "warning",
            "category": "logic",
            "confidence": 0.9,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.ERROR

    def test_classify_security_below_threshold_not_promoted(self):
        """Security issue with confidence < 0.9 is NOT promoted to error."""
        suggestion = {
            "severity": "warning",
            "category": "security",
            "confidence": 0.89,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.WARNING

    def test_classify_low_confidence_error_becomes_warning(self):
        """Error with confidence < 0.7 is demoted to WARNING."""
        suggestion = {
            "severity": "error",
            "category": "general",
            "confidence": 0.5,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.WARNING

    def test_classify_error_at_threshold_stays_error(self):
        """Error with confidence exactly 0.7 stays as ERROR."""
        suggestion = {
            "severity": "error",
            "category": "general",
            "confidence": 0.7,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.ERROR

    def test_classify_error_above_threshold_stays_error(self):
        """Error with confidence > 0.7 stays as ERROR."""
        suggestion = {
            "severity": "error",
            "category": "general",
            "confidence": 0.85,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.ERROR

    def test_classify_note_stays_note(self):
        """Note with default confidence stays as NOTE."""
        suggestion = {
            "severity": "note",
            "category": "style",
            "confidence": 0.5,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.NOTE

    def test_classify_missing_category_defaults_general(self):
        """Missing category defaults to 'general' and no promotion."""
        suggestion = {"severity": "warning", "confidence": 0.95}
        result = self.classifier.classify(suggestion)
        # category is 'general', so no security/logic promotion
        assert result == SeverityLevel.WARNING

    def test_classify_missing_confidence_defaults_half(self):
        """Missing confidence defaults to 0.5."""
        suggestion = {"severity": "error", "category": "general"}
        # confidence defaults to 0.5, which is < 0.7, so error -> warning
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.WARNING

    def test_classify_high_confidence_security_overrides_low_severity(self):
        """High confidence security overrides even NOTE severity."""
        suggestion = {
            "severity": "note",
            "category": "security",
            "confidence": 0.95,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.ERROR

    def test_classify_style_category_not_promoted(self):
        """Style category with high confidence is not promoted."""
        suggestion = {
            "severity": "suggestion",
            "category": "style",
            "confidence": 0.99,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.SUGGESTION

    def test_classify_pattern_category_not_promoted(self):
        """Pattern category with high confidence is not promoted."""
        suggestion = {
            "severity": "suggestion",
            "category": "pattern",
            "confidence": 0.99,
        }
        result = self.classifier.classify(suggestion)
        assert result == SeverityLevel.SUGGESTION


class TestSeverityClassifierFilterByThreshold:
    """Tests for SeverityClassifier.filter_by_threshold."""

    def setup_method(self):
        self.classifier = SeverityClassifier()

    def _make_suggestion(self, severity="suggestion", category="general", confidence=0.8):
        return {
            "severity": severity,
            "category": category,
            "confidence": confidence,
        }

    def test_filter_default_threshold_includes_all_except_notes(self):
        """Default threshold 'suggestion' includes error, warning, suggestion."""
        suggestions = [
            self._make_suggestion(severity="error", confidence=0.8),
            self._make_suggestion(severity="warning"),
            self._make_suggestion(severity="suggestion"),
            self._make_suggestion(severity="note"),
        ]
        filtered = self.classifier.filter_by_threshold(suggestions)
        assert len(filtered) == 3

    def test_filter_error_threshold_only_errors(self):
        """Threshold 'error' only includes errors."""
        suggestions = [
            self._make_suggestion(severity="error", confidence=0.8),
            self._make_suggestion(severity="warning"),
            self._make_suggestion(severity="suggestion"),
        ]
        filtered = self.classifier.filter_by_threshold(suggestions, threshold="error")
        assert len(filtered) == 1
        assert filtered[0]["severity"] == "error"

    def test_filter_warning_threshold(self):
        """Threshold 'warning' includes errors and warnings."""
        suggestions = [
            self._make_suggestion(severity="error", confidence=0.8),
            self._make_suggestion(severity="warning"),
            self._make_suggestion(severity="suggestion"),
            self._make_suggestion(severity="note"),
        ]
        filtered = self.classifier.filter_by_threshold(suggestions, threshold="warning")
        assert len(filtered) == 2

    def test_filter_note_threshold_includes_all(self):
        """Threshold 'note' includes everything."""
        suggestions = [
            self._make_suggestion(severity="error", confidence=0.8),
            self._make_suggestion(severity="warning"),
            self._make_suggestion(severity="suggestion"),
            self._make_suggestion(severity="note"),
        ]
        filtered = self.classifier.filter_by_threshold(suggestions, threshold="note")
        assert len(filtered) == 4

    def test_filter_updates_severity_in_suggestions(self):
        """filter_by_threshold updates the 'severity' field after classification."""
        # High confidence security issue -- classify() promotes it to ERROR
        suggestion = self._make_suggestion(
            severity="suggestion", category="security", confidence=0.95
        )
        filtered = self.classifier.filter_by_threshold([suggestion], threshold="error")
        assert len(filtered) == 1
        assert filtered[0]["severity"] == "error"

    def test_filter_empty_list(self):
        """Filtering an empty list returns an empty list."""
        filtered = self.classifier.filter_by_threshold([])
        assert filtered == []

    def test_filter_invalid_threshold_defaults_to_suggestion(self):
        """Invalid threshold string defaults to 'suggestion' level."""
        suggestions = [
            self._make_suggestion(severity="error", confidence=0.8),
            self._make_suggestion(severity="note"),
        ]
        filtered = self.classifier.filter_by_threshold(suggestions, threshold="invalid")
        # defaults to suggestion threshold: includes error but not note
        assert len(filtered) == 1

    def test_filter_preserves_original_suggestions(self):
        """Filtered list contains the same dict objects (mutated in place)."""
        suggestions = [
            self._make_suggestion(severity="error", confidence=0.8),
        ]
        filtered = self.classifier.filter_by_threshold(suggestions)
        assert filtered[0] is suggestions[0]


class TestSeverityClassifierSortBySeverity:
    """Tests for SeverityClassifier.sort_by_severity."""

    def setup_method(self):
        self.classifier = SeverityClassifier()

    def test_sort_by_severity_order(self):
        """Suggestions are sorted by severity: error first, note last."""
        suggestions = [
            {"severity": "note", "category": "general", "confidence": 0.5},
            {"severity": "error", "category": "general", "confidence": 0.8},
            {"severity": "suggestion", "category": "general", "confidence": 0.5},
            {"severity": "warning", "category": "general", "confidence": 0.5},
        ]
        sorted_suggestions = self.classifier.sort_by_severity(suggestions)

        severities = [self.classifier.classify(s) for s in sorted_suggestions]
        assert severities[0] == SeverityLevel.ERROR
        assert severities[-1] == SeverityLevel.NOTE

    def test_sort_empty_list(self):
        """Sorting empty list returns empty list."""
        assert self.classifier.sort_by_severity([]) == []

    def test_sort_single_item(self):
        """Sorting single item returns single item."""
        s = {"severity": "warning", "category": "general", "confidence": 0.5}
        result = self.classifier.sort_by_severity([s])
        assert len(result) == 1
        assert result[0] is s

    def test_sort_by_confidence_within_same_severity(self):
        """Within same severity, higher confidence comes first."""
        suggestions = [
            {"severity": "warning", "category": "general", "confidence": 0.5},
            {"severity": "warning", "category": "general", "confidence": 0.9},
        ]
        sorted_suggestions = self.classifier.sort_by_severity(suggestions)
        assert sorted_suggestions[0]["confidence"] == 0.9
        assert sorted_suggestions[1]["confidence"] == 0.5

    def test_sort_by_category_within_same_severity_and_confidence(self):
        """Within same severity and confidence, sort alphabetically by category."""
        suggestions = [
            {"severity": "warning", "category": "style", "confidence": 0.5},
            {"severity": "warning", "category": "logic", "confidence": 0.5},
        ]
        sorted_suggestions = self.classifier.sort_by_severity(suggestions)
        assert sorted_suggestions[0]["category"] == "logic"
        assert sorted_suggestions[1]["category"] == "style"

    def test_sort_does_not_modify_original(self):
        """sort_by_severity returns a new list, not mutating the original."""
        suggestions = [
            {"severity": "note", "category": "general", "confidence": 0.5},
            {"severity": "error", "category": "general", "confidence": 0.8},
        ]
        original_order = list(suggestions)
        self.classifier.sort_by_severity(suggestions)
        # The original list should be unchanged
        assert suggestions == original_order


class TestSeverityClassifierGetSeverityStats:
    """Tests for SeverityClassifier.get_severity_stats."""

    def setup_method(self):
        self.classifier = SeverityClassifier()

    def test_stats_empty_list(self):
        """Stats for empty list have zero totals and no percents."""
        stats = self.classifier.get_severity_stats([])
        assert stats["total"] == 0
        assert stats["error"] == 0
        assert stats["warning"] == 0
        assert stats["suggestion"] == 0
        assert stats["note"] == 0
        # No percentages when total is 0
        assert "error_percent" not in stats

    def test_stats_counts(self):
        """Stats correctly counts each severity level."""
        suggestions = [
            {"severity": "error", "category": "general", "confidence": 0.8},
            {"severity": "error", "category": "general", "confidence": 0.8},
            {"severity": "warning", "category": "general", "confidence": 0.5},
            {"severity": "suggestion", "category": "general", "confidence": 0.5},
            {"severity": "note", "category": "general", "confidence": 0.5},
        ]
        stats = self.classifier.get_severity_stats(suggestions)
        assert stats["total"] == 5
        assert stats["error"] == 2
        assert stats["warning"] == 1
        assert stats["suggestion"] == 1
        assert stats["note"] == 1

    def test_stats_percentages(self):
        """Stats calculates percentages when total > 0."""
        suggestions = [
            {"severity": "error", "category": "general", "confidence": 0.8},
            {"severity": "warning", "category": "general", "confidence": 0.5},
        ]
        stats = self.classifier.get_severity_stats(suggestions)
        assert stats["error_percent"] == 50.0
        assert stats["warning_percent"] == 50.0
        assert stats["suggestion_percent"] == 0.0
        assert stats["note_percent"] == 0.0

    def test_stats_all_same_severity(self):
        """Stats with all same severity shows 100% for that level."""
        suggestions = [
            {"severity": "warning", "category": "general", "confidence": 0.5},
            {"severity": "warning", "category": "general", "confidence": 0.5},
            {"severity": "warning", "category": "general", "confidence": 0.5},
        ]
        stats = self.classifier.get_severity_stats(suggestions)
        assert stats["warning"] == 3
        assert stats["warning_percent"] == 100.0
        assert stats["error_percent"] == 0.0

    def test_stats_with_reclassification(self):
        """Stats uses classify(), so reclassification affects counts."""
        # High confidence security => classified as ERROR even if original is suggestion
        suggestions = [
            {"severity": "suggestion", "category": "security", "confidence": 0.95},
        ]
        stats = self.classifier.get_severity_stats(suggestions)
        assert stats["error"] == 1
        assert stats["suggestion"] == 0


class TestSeverityClassifierShouldBlockMerge:
    """Tests for SeverityClassifier.should_block_merge."""

    def setup_method(self):
        self.classifier = SeverityClassifier()

    def test_block_when_error_present(self):
        """Should block if any suggestion classifies as ERROR."""
        suggestions = [
            {"severity": "error", "category": "general", "confidence": 0.8},
        ]
        assert self.classifier.should_block_merge(suggestions) is True

    def test_no_block_warnings_only(self):
        """Should not block if only warnings are present."""
        suggestions = [
            {"severity": "warning", "category": "general", "confidence": 0.5},
        ]
        assert self.classifier.should_block_merge(suggestions) is False

    def test_no_block_empty_list(self):
        """Should not block if no suggestions."""
        assert self.classifier.should_block_merge([]) is False

    def test_block_with_promoted_error(self):
        """Should block if a suggestion is promoted to ERROR by classify."""
        # High confidence security issue promotes to ERROR
        suggestions = [
            {"severity": "suggestion", "category": "security", "confidence": 0.95},
        ]
        assert self.classifier.should_block_merge(suggestions) is True

    def test_no_block_with_demoted_error(self):
        """Should not block if an error is demoted to WARNING by classify."""
        # Low confidence error gets demoted to WARNING
        suggestions = [
            {"severity": "error", "category": "general", "confidence": 0.3},
        ]
        assert self.classifier.should_block_merge(suggestions) is False

    def test_block_among_many_suggestions(self):
        """Should block if at least one ERROR exists among many."""
        suggestions = [
            {"severity": "note", "category": "general", "confidence": 0.5},
            {"severity": "suggestion", "category": "general", "confidence": 0.5},
            {"severity": "error", "category": "general", "confidence": 0.8},
            {"severity": "warning", "category": "general", "confidence": 0.5},
        ]
        assert self.classifier.should_block_merge(suggestions) is True


class TestSeverityClassifierGetMaxSeverity:
    """Tests for SeverityClassifier.get_max_severity."""

    def setup_method(self):
        self.classifier = SeverityClassifier()

    def test_max_severity_empty_list(self):
        """Empty list returns NOTE (least severe)."""
        result = self.classifier.get_max_severity([])
        assert result == SeverityLevel.NOTE

    def test_max_severity_single_error(self):
        """Single error returns ERROR."""
        suggestions = [
            {"severity": "error", "category": "general", "confidence": 0.8},
        ]
        assert self.classifier.get_max_severity(suggestions) == SeverityLevel.ERROR

    def test_max_severity_mixed(self):
        """Mixed severities returns the most severe (ERROR)."""
        suggestions = [
            {"severity": "note", "category": "general", "confidence": 0.5},
            {"severity": "warning", "category": "general", "confidence": 0.5},
            {"severity": "error", "category": "general", "confidence": 0.8},
            {"severity": "suggestion", "category": "general", "confidence": 0.5},
        ]
        assert self.classifier.get_max_severity(suggestions) == SeverityLevel.ERROR

    def test_max_severity_only_notes(self):
        """Only notes returns NOTE."""
        suggestions = [
            {"severity": "note", "category": "general", "confidence": 0.5},
            {"severity": "note", "category": "general", "confidence": 0.5},
        ]
        assert self.classifier.get_max_severity(suggestions) == SeverityLevel.NOTE

    def test_max_severity_only_warnings(self):
        """Only warnings returns WARNING."""
        suggestions = [
            {"severity": "warning", "category": "general", "confidence": 0.5},
        ]
        assert self.classifier.get_max_severity(suggestions) == SeverityLevel.WARNING

    def test_max_severity_with_promotion(self):
        """Max severity considers classify() promotion."""
        # High confidence security -> promoted to ERROR
        suggestions = [
            {"severity": "suggestion", "category": "security", "confidence": 0.95},
            {"severity": "warning", "category": "general", "confidence": 0.5},
        ]
        assert self.classifier.get_max_severity(suggestions) == SeverityLevel.ERROR

    def test_max_severity_with_demotion(self):
        """Max severity considers classify() demotion."""
        # Low confidence error -> demoted to WARNING
        suggestions = [
            {"severity": "error", "category": "general", "confidence": 0.3},
            {"severity": "note", "category": "general", "confidence": 0.5},
        ]
        # The "error" gets demoted to WARNING, so max is WARNING
        assert self.classifier.get_max_severity(suggestions) == SeverityLevel.WARNING
