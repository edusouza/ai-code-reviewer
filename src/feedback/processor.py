"""Feedback processor for handling and storing feedback."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from config.settings import settings
from feedback.classifier import EmojiClassifier, FeedbackType
from observability.langfuse_client import get_langfuse
from observability.metrics import get_metrics_client

logger = logging.getLogger(__name__)


class FeedbackProcessor:
    """Process and store feedback from users."""

    def __init__(
        self, firestore_db: Any | None = None, classifier: EmojiClassifier | None = None
    ):
        """
        Initialize the feedback processor.

        Args:
            firestore_db: Optional Firestore client
            classifier: Optional emoji classifier
        """
        self.classifier = classifier or EmojiClassifier()
        self._db = firestore_db
        self._initialized = False

    async def _initialize_db(self):
        """Lazy initialization of Firestore client."""
        if self._initialized or self._db is not None:
            return

        try:
            from google.cloud import firestore

            self._db = firestore.Client(project=settings.project_id)
            self._initialized = True
            logger.info("Feedback processor Firestore client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")

    async def process_feedback(self, feedback_data: dict[str, Any]) -> dict[str, Any]:
        """
        Process incoming feedback.

        Args:
            feedback_data: Raw feedback data from webhook

        Returns:
            Processed feedback record
        """
        await self._initialize_db()

        # Extract emojis
        emojis = self._extract_emojis(feedback_data)

        # Classify feedback
        classification = self.classifier.classify(emojis)

        # Create feedback record
        record = {
            "id": f"fb_{datetime.utcnow().timestamp()}_{hash(str(feedback_data)) & 0xFFFF}",
            "provider": feedback_data.get("provider", "unknown"),
            "event_type": feedback_data.get("event_type", "unknown"),
            "repo_owner": feedback_data.get("repo_owner", ""),
            "repo_name": feedback_data.get("repo_name", ""),
            "pr_number": feedback_data.get("pr_number", 0),
            "file_path": feedback_data.get("file_path", ""),
            "line_number": feedback_data.get("line_number", 0),
            "user": feedback_data.get("user", ""),
            "emojis": emojis,
            "primary_emoji": classification.primary_emoji,
            "feedback_type": classification.feedback_type.value,
            "score": classification.score,
            "confidence": classification.confidence,
            "comment_body": self._get_comment_body(feedback_data),
            "is_actionable": self.classifier.is_actionable(classification),
            "timestamp": datetime.utcnow(),
            "raw_payload": feedback_data.get("raw_payload", {}),
        }

        try:
            # Store in Firestore
            await self._store_feedback(record)

            # Submit score to LangFuse
            await self._submit_to_langfuse(record)

            # Record metrics
            await self._record_metrics(record)

            logger.info(
                f"Processed feedback: {record['id']} - "
                f"{classification.feedback_type.value} "
                f"(score: {classification.score:.2f})"
            )

            return record

        except Exception as e:
            logger.error(f"Failed to process feedback: {e}")
            raise

    def _extract_emojis(self, feedback_data: dict[str, Any]) -> list[str]:
        """Extract emojis from feedback data."""
        emojis = []

        # Direct emoji field
        if "emoji" in feedback_data:
            emoji = feedback_data["emoji"]
            if isinstance(emoji, str):
                emojis.append(emoji)
            elif isinstance(emoji, list):
                emojis.extend(emoji)

        # Multiple emojis
        if "emojis" in feedback_data:
            emoji_list = feedback_data["emojis"]
            if isinstance(emoji_list, list):
                emojis.extend(emoji_list)
            elif isinstance(emoji_list, str):
                emojis.append(emoji_list)

        # Extract from comment body
        comment_body = self._get_comment_body(feedback_data)
        if comment_body:
            from feedback.webhook import FeedbackWebhookHandler

            handler = FeedbackWebhookHandler()
            body_emojis = handler._extract_emojis(comment_body)
            emojis.extend(body_emojis)

        # Remove duplicates while preserving order
        seen = set()
        unique_emojis = []
        for emoji in emojis:
            if emoji not in seen:
                seen.add(emoji)
                unique_emojis.append(emoji)

        return unique_emojis

    def _get_comment_body(self, feedback_data: dict[str, Any]) -> str:
        """Extract comment body from feedback data."""
        for key in ["comment_body", "note_body", "review_body"]:
            if key in feedback_data:
                return str(feedback_data[key])
        return ""

    async def _store_feedback(self, record: dict[str, Any]):
        """Store feedback record in Firestore."""
        if not self._db:
            logger.warning("Firestore not available, skipping storage")
            return

        try:
            doc_ref = self._db.collection("feedback").document(record["id"])

            # Convert datetime to ISO format for Firestore
            record_copy = record.copy()
            record_copy["timestamp"] = record["timestamp"].isoformat()

            # Remove raw_payload to avoid oversized documents
            record_copy.pop("raw_payload", None)

            await asyncio.get_event_loop().run_in_executor(None, lambda: doc_ref.set(record_copy))

            logger.debug(f"Stored feedback record: {record['id']}")

        except Exception as e:
            logger.error(f"Failed to store feedback: {e}")
            raise

    async def _submit_to_langfuse(self, record: dict[str, Any]):
        """Submit feedback score to LangFuse."""
        langfuse = get_langfuse()
        if not langfuse:
            return

        try:
            # Try to find associated trace
            review_id = await self._find_review_id(record)

            if review_id:
                # Submit as trace score
                langfuse.score_trace(
                    trace_id=review_id,
                    name="user_feedback",
                    value=record["score"],
                    comment=f"{record['feedback_type']} feedback from {record['user']}",
                )

                logger.debug(f"Submitted feedback to LangFuse for trace: {review_id}")

        except Exception as e:
            logger.error(f"Failed to submit to LangFuse: {e}")
            # Don't raise - this is best-effort

    async def _find_review_id(self, record: dict[str, Any]) -> str | None:
        """Find the associated review ID for a feedback record."""
        if not self._db:
            return None

        try:
            # Query reviews collection by PR info
            reviews_ref = self._db.collection("reviews")
            query = (
                reviews_ref.where("repo_owner", "==", record["repo_owner"])
                .where("repo_name", "==", record["repo_name"])
                .where("pr_number", "==", record["pr_number"])
                .order_by("completed_at", direction="DESCENDING")
                .limit(1)
            )

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            if docs:
                return docs[0].id

            return None

        except Exception as e:
            logger.error(f"Failed to find review ID: {e}")
            return None

    async def _record_metrics(self, record: dict[str, Any]):
        """Record feedback metrics."""
        metrics = get_metrics_client()
        if not metrics:
            return

        try:
            metrics.record_feedback_metrics(
                feedback_type=record["feedback_type"],
                score=record["score"],
                provider=record["provider"],
            )
        except Exception as e:
            logger.error(f"Failed to record metrics: {e}")

    async def get_feedback_summary(
        self, repo_owner: str, repo_name: str, days: int = 30
    ) -> dict[str, Any]:
        """
        Get feedback summary for a repository.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            days: Number of days to look back

        Returns:
            Feedback summary statistics
        """
        await self._initialize_db()

        if not self._db:
            return {"error": "Database not available"}

        try:
            from datetime import timedelta

            start_date = datetime.utcnow() - timedelta(days=days)

            feedback_ref = self._db.collection("feedback")
            query = (
                feedback_ref.where("repo_owner", "==", repo_owner)
                .where("repo_name", "==", repo_name)
                .where("timestamp", ">=", start_date.isoformat())
            )

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            feedbacks = [doc.to_dict() for doc in docs]

            if not feedbacks:
                return {"total": 0, "period_days": days, "message": "No feedback found"}

            # Calculate statistics
            total = len(feedbacks)
            positive = sum(
                1 for f in feedbacks if f.get("feedback_type") == FeedbackType.POSITIVE.value
            )
            negative = sum(
                1 for f in feedbacks if f.get("feedback_type") == FeedbackType.NEGATIVE.value
            )
            neutral = sum(
                1 for f in feedbacks if f.get("feedback_type") == FeedbackType.NEUTRAL.value
            )
            confused = sum(
                1 for f in feedbacks if f.get("feedback_type") == FeedbackType.CONFUSED.value
            )

            avg_score = sum(f.get("score", 0) for f in feedbacks) / total if total > 0 else 0
            actionable = sum(1 for f in feedbacks if f.get("is_actionable", False))

            return {
                "total": total,
                "period_days": days,
                "breakdown": {
                    "positive": positive,
                    "negative": negative,
                    "neutral": neutral,
                    "confused": confused,
                },
                "percentages": {
                    "positive": (positive / total * 100) if total > 0 else 0,
                    "negative": (negative / total * 100) if total > 0 else 0,
                    "neutral": (neutral / total * 100) if total > 0 else 0,
                    "confused": (confused / total * 100) if total > 0 else 0,
                },
                "average_score": round(avg_score, 2),
                "actionable_count": actionable,
                "satisfaction_rate": (positive / total * 100) if total > 0 else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get feedback summary: {e}")
            return {"error": str(e)}

    async def get_recent_feedback(
        self, repo_owner: str, repo_name: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get recent feedback for a repository.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            limit: Maximum number of items to return

        Returns:
            List of feedback records
        """
        await self._initialize_db()

        if not self._db:
            return []

        try:
            feedback_ref = self._db.collection("feedback")
            query = (
                feedback_ref.where("repo_owner", "==", repo_owner)
                .where("repo_name", "==", repo_name)
                .order_by("timestamp", direction="DESCENDING")
                .limit(limit)
            )

            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(query.stream())
            )

            return [doc.to_dict() for doc in docs]

        except Exception as e:
            logger.error(f"Failed to get recent feedback: {e}")
            return []


# Global processor instance
_feedback_processor: FeedbackProcessor | None = None


def get_feedback_processor() -> FeedbackProcessor:
    """Get or create the global feedback processor."""
    global _feedback_processor
    if _feedback_processor is None:
        _feedback_processor = FeedbackProcessor()
    return _feedback_processor
