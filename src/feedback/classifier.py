"""Emoji classifier for categorizing feedback sentiment."""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback based on sentiment."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    CONFUSED = "confused"
    MIXED = "mixed"


@dataclass
class ClassificationResult:
    """Result of emoji classification."""

    feedback_type: FeedbackType
    score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    primary_emoji: str | None
    all_emojis: list[str]


class EmojiClassifier:
    """Classifier for categorizing emojis and reactions."""

    # Emoji sentiment mappings
    POSITIVE_EMOJIS = {
        "👍": 1.0,
        "👍🏻": 1.0,
        "👍🏼": 1.0,
        "👍🏽": 1.0,
        "👍🏾": 1.0,
        "👍🏿": 1.0,  # Thumbs up variants
        "❤️": 1.0,
        "🧡": 1.0,
        "💛": 1.0,
        "💚": 1.0,
        "💙": 1.0,
        "💜": 1.0,
        "🖤": 0.8,
        "🤍": 0.9,
        "🤎": 0.9,
        "💯": 1.0,
        "🎉": 1.0,
        "🚀": 0.9,
        "✅": 0.9,
        "☑️": 0.8,
        "✔️": 0.9,
        "🌟": 1.0,
        "⭐": 0.9,
        "🔥": 0.8,
        "💪": 0.8,
        "🙌": 0.9,
        "👏": 0.9,
        "🎊": 0.9,
        "🏆": 1.0,
        "🥇": 1.0,
        "🏅": 0.9,
        "🎯": 0.8,
        "✨": 0.8,
        "😄": 0.9,
        "😃": 0.9,
        "😀": 0.8,
        "😊": 0.9,
        "🙂": 0.7,
        "😎": 0.8,
        "🤩": 1.0,
        "🥳": 0.9,
        "😍": 1.0,
        "🥰": 1.0,
        "😘": 0.9,
    }

    NEGATIVE_EMOJIS = {
        "👎": -1.0,
        "👎🏻": -1.0,
        "👎🏼": -1.0,
        "👎🏽": -1.0,
        "👎🏾": -1.0,
        "👎🏿": -1.0,  # Thumbs down variants
        "❌": -0.9,
        "❎": -0.8,
        "🚫": -0.9,
        "⛔": -0.9,
        "🛑": -0.9,
        "⚠️": -0.6,
        "🔴": -0.7,
        "😞": -0.8,
        "😔": -0.8,
        "😟": -0.7,
        "😕": -0.6,
        "☹️": -0.7,
        "🙁": -0.7,
        "😣": -0.8,
        "😖": -0.8,
        "😫": -0.8,
        "😩": -0.8,
        "😢": -0.9,
        "😭": -1.0,
        "😤": -0.8,
        "😠": -0.9,
        "😡": -1.0,
        "🤬": -1.0,
        "👿": -0.9,
        "😈": -0.7,
        "💔": -1.0,
        "😰": -0.7,
        "😥": -0.8,
        "😓": -0.6,
        "💩": -0.8,
        "🤮": -0.9,
        "🤢": -0.8,
    }

    NEUTRAL_EMOJIS = {
        "👀": 0.0,
        "👁️": 0.0,
        "🤔": 0.0,
        "💭": 0.0,
        "🤷": 0.0,
        "🤷‍♂️": 0.0,
        "🤷‍♀️": 0.0,
        "😐": 0.0,
        "😑": 0.0,
        "😶": 0.0,
        "🙄": -0.1,
        "📌": 0.0,
        "📍": 0.0,
        "🔖": 0.0,
        "📝": 0.0,
        "📋": 0.0,
    }

    CONFUSED_EMOJIS = {
        "😕": 0.0,
        "🤔": 0.0,
        "🧐": 0.1,
        "😵": -0.2,
        "😵‍💫": -0.2,
        "🤯": 0.0,
        "❓": 0.0,
        "❔": 0.0,
        "❗": 0.0,
        "❕": 0.0,
        "⁉️": 0.0,
        "‼️": 0.0,
        "💡": 0.3,
        "🤨": -0.1,
    }

    def __init__(self) -> None:
        """Initialize the classifier."""
        # Combine all emoji mappings
        self.emoji_scores = {}
        self.emoji_scores.update(self.POSITIVE_EMOJIS)
        self.emoji_scores.update(self.NEGATIVE_EMOJIS)
        self.emoji_scores.update(self.NEUTRAL_EMOJIS)
        self.emoji_scores.update(self.CONFUSED_EMOJIS)

    def classify(self, emojis: list[str]) -> ClassificationResult:
        """
        Classify a list of emojis.

        Args:
            emojis: List of emojis to classify

        Returns:
            ClassificationResult with feedback type and score
        """
        if not emojis:
            return ClassificationResult(
                feedback_type=FeedbackType.NEUTRAL,
                score=0.0,
                confidence=0.0,
                primary_emoji=None,
                all_emojis=[],
            )

        # Calculate sentiment scores
        scores = []
        for emoji in emojis:
            score = self.emoji_scores.get(emoji, 0.0)
            scores.append(score)

        if not scores:
            return ClassificationResult(
                feedback_type=FeedbackType.NEUTRAL,
                score=0.0,
                confidence=0.3,
                primary_emoji=emojis[0] if emojis else None,
                all_emojis=emojis,
            )

        # Calculate average score
        avg_score = sum(scores) / len(scores)

        # Determine feedback type
        if all(s > 0.5 for s in scores):
            feedback_type = FeedbackType.POSITIVE
            confidence = min(sum(scores) / len(scores), 1.0)
        elif all(s < -0.5 for s in scores):
            feedback_type = FeedbackType.NEGATIVE
            confidence = min(abs(avg_score), 1.0)
        elif any(emoji in self.CONFUSED_EMOJIS for emoji in emojis):
            feedback_type = FeedbackType.CONFUSED
            confidence = 0.6
        elif max(scores) > 0.3 and min(scores) < -0.3:
            feedback_type = FeedbackType.MIXED
            confidence = 0.5
        else:
            feedback_type = FeedbackType.NEUTRAL
            confidence = 0.4

        # Find primary emoji (strongest sentiment)
        if scores:
            max_score_idx = max(range(len(scores)), key=lambda i: abs(scores[i]))
            primary_emoji = emojis[max_score_idx]
        else:
            primary_emoji = emojis[0] if emojis else ""

        return ClassificationResult(
            feedback_type=feedback_type,
            score=avg_score,
            confidence=confidence,
            primary_emoji=primary_emoji,
            all_emojis=emojis,
        )

    def classify_single(self, emoji: str) -> ClassificationResult:
        """
        Classify a single emoji.

        Args:
            emoji: Single emoji to classify

        Returns:
            ClassificationResult
        """
        return self.classify([emoji])

    def get_sentiment_description(self, result: ClassificationResult) -> str:
        """
        Get a human-readable description of the sentiment.

        Args:
            result: Classification result

        Returns:
            Description string
        """
        descriptions = {
            FeedbackType.POSITIVE: "Positive feedback",
            FeedbackType.NEGATIVE: "Negative feedback",
            FeedbackType.NEUTRAL: "Neutral feedback",
            FeedbackType.CONFUSED: "User is confused or has questions",
            FeedbackType.MIXED: "Mixed feedback with both positive and negative elements",
        }

        base = descriptions.get(result.feedback_type, "Unknown feedback")

        if result.primary_emoji:
            return f"{base} (emoji: {result.primary_emoji}, score: {result.score:.2f})"

        return f"{base} (score: {result.score:.2f})"

    def is_actionable(self, result: ClassificationResult) -> bool:
        """
        Determine if feedback requires action.

        Args:
            result: Classification result

        Returns:
            True if feedback should trigger a follow-up action
        """
        # Negative or confused feedback is actionable
        if result.feedback_type in [FeedbackType.NEGATIVE, FeedbackType.CONFUSED]:
            return True

        # Mixed feedback with significant negative component
        return bool(result.feedback_type == FeedbackType.MIXED and result.score < -0.2)

    def extract_keywords(self, text: str) -> list[str]:
        """
        Extract sentiment keywords from text.

        Args:
            text: Text to analyze

        Returns:
            List of sentiment keywords found
        """
        positive_keywords = [
            "good",
            "great",
            "awesome",
            "excellent",
            "perfect",
            "thanks",
            "thank you",
            "helpful",
            "useful",
        ]
        negative_keywords = [
            "bad",
            "wrong",
            "incorrect",
            "error",
            "mistake",
            "terrible",
            "awful",
            "useless",
            "confusing",
        ]

        text_lower = text.lower()
        found_keywords = []

        for word in positive_keywords:
            if word in text_lower:
                found_keywords.append(f"+{word}")

        for word in negative_keywords:
            if word in text_lower:
                found_keywords.append(f"-{word}")

        return found_keywords
