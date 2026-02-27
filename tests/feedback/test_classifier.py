"""Tests for feedback classifier module."""

from feedback.classifier import ClassificationResult, EmojiClassifier, FeedbackType


class TestEmojiClassifier:
    """Test emoji classification functionality."""

    def test_classify_positive_emoji(self):
        """Test classification of positive emojis."""
        classifier = EmojiClassifier()

        result = classifier.classify(["👍"])

        assert isinstance(result, ClassificationResult)
        assert result.feedback_type == FeedbackType.POSITIVE
        assert result.score > 0
        assert result.primary_emoji == "👍"
        assert result.confidence > 0

    def test_classify_negative_emoji(self):
        """Test classification of negative emojis."""
        classifier = EmojiClassifier()

        result = classifier.classify(["👎"])

        assert result.feedback_type == FeedbackType.NEGATIVE
        assert result.score < 0
        assert result.primary_emoji == "👎"

    def test_classify_neutral_emoji(self):
        """Test classification of neutral/unknown emojis."""
        classifier = EmojiClassifier()

        result = classifier.classify(["📎"])

        assert result.feedback_type == FeedbackType.NEUTRAL
        assert result.score == 0.0

    def test_classify_empty_list(self):
        """Test classification of empty list."""
        classifier = EmojiClassifier()

        result = classifier.classify([])

        assert result.feedback_type == FeedbackType.NEUTRAL
        assert result.primary_emoji is None
        assert result.all_emojis == []

    def test_classify_multiple_positive_emojis(self):
        """Test classification of multiple emojis with same sentiment."""
        classifier = EmojiClassifier()

        result = classifier.classify(["👍", "❤️", "🎉"])

        assert result.feedback_type == FeedbackType.POSITIVE
        assert result.primary_emoji in ["👍", "❤️", "🎉"]
        assert len(result.all_emojis) == 3

    def test_classify_mixed_emojis(self):
        """Test classification of mixed positive and negative emojis."""
        classifier = EmojiClassifier()

        result = classifier.classify(["👍", "👎"])

        # Mixed sentiment should be detected
        assert result.feedback_type == FeedbackType.MIXED

    def test_classify_confused_emojis(self):
        """Test classification of confused/question emojis."""
        classifier = EmojiClassifier()

        result = classifier.classify(["🤔"])

        assert result.feedback_type == FeedbackType.CONFUSED

    def test_classify_single_method(self):
        """Test classify_single method."""
        classifier = EmojiClassifier()

        result = classifier.classify_single("👍")

        assert result.feedback_type == FeedbackType.POSITIVE
        assert result.primary_emoji == "👍"

    def test_get_sentiment_description_positive(self):
        """Test getting sentiment description for positive feedback."""
        classifier = EmojiClassifier()

        result = ClassificationResult(
            feedback_type=FeedbackType.POSITIVE,
            score=0.8,
            confidence=0.9,
            primary_emoji="👍",
            all_emojis=["👍"],
        )

        description = classifier.get_sentiment_description(result)

        assert "positive" in description.lower()

    def test_get_sentiment_description_negative(self):
        """Test getting sentiment description for negative feedback."""
        classifier = EmojiClassifier()

        result = ClassificationResult(
            feedback_type=FeedbackType.NEGATIVE,
            score=-0.8,
            confidence=0.9,
            primary_emoji="👎",
            all_emojis=["👎"],
        )

        description = classifier.get_sentiment_description(result)

        assert "negative" in description.lower()

    def test_classify_very_positive_emojis(self):
        """Test classification of very positive emojis."""
        classifier = EmojiClassifier()

        result = classifier.classify(["🚀", "🔥", "💯"])

        assert result.feedback_type == FeedbackType.POSITIVE
        assert result.score > 0.5

    def test_classify_very_negative_emojis(self):
        """Test classification of very negative emojis."""
        classifier = EmojiClassifier()

        result = classifier.classify(["👎", "💔", "😡"])

        assert result.feedback_type == FeedbackType.NEGATIVE
        assert result.score < -0.5
