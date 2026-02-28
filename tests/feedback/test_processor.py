"""Tests for feedback processor module."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from feedback.classifier import ClassificationResult, EmojiClassifier, FeedbackType
from feedback.processor import FeedbackProcessor, get_feedback_processor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classification(
    feedback_type=FeedbackType.POSITIVE,
    score=0.8,
    confidence=0.9,
    primary_emoji="👍",
    all_emojis=None,
):
    return ClassificationResult(
        feedback_type=feedback_type,
        score=score,
        confidence=confidence,
        primary_emoji=primary_emoji,
        all_emojis=all_emojis or ["👍"],
    )


def _make_feedback_data(**overrides):
    base = {
        "provider": "github",
        "event_type": "comment_reaction",
        "repo_owner": "myorg",
        "repo_name": "myrepo",
        "pr_number": 42,
        "file_path": "src/main.py",
        "line_number": 10,
        "user": "johndoe",
        "emoji": "👍",
        "raw_payload": {"some": "data"},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestFeedbackProcessorInit:
    """Tests for FeedbackProcessor.__init__."""

    def test_default_initialization(self):
        """Processor uses a default EmojiClassifier and no db."""
        processor = FeedbackProcessor()
        assert isinstance(processor.classifier, EmojiClassifier)
        assert processor._db is None
        assert processor._initialized is False

    def test_custom_classifier(self):
        """Processor accepts a custom classifier."""
        custom = Mock(spec=EmojiClassifier)
        processor = FeedbackProcessor(classifier=custom)
        assert processor.classifier is custom

    def test_custom_firestore_db(self):
        """Processor accepts a pre-configured Firestore client."""
        mock_db = Mock()
        processor = FeedbackProcessor(firestore_db=mock_db)
        assert processor._db is mock_db
        assert processor._initialized is False


# ---------------------------------------------------------------------------
# _initialize_db
# ---------------------------------------------------------------------------


class TestInitializeDb:
    """Tests for lazy Firestore initialization."""

    @pytest.mark.asyncio
    async def test_skips_when_already_initialized(self):
        """Should not re-init when _initialized is True."""
        processor = FeedbackProcessor()
        processor._initialized = True
        processor._db = Mock()

        with patch("feedback.processor.settings") as _settings:
            await processor._initialize_db()
            # settings should never be accessed
            _settings.assert_not_called()

        # db stays unchanged
        assert processor._db is not None

    @pytest.mark.asyncio
    async def test_skips_when_db_is_already_set(self):
        """Should not re-init when _db was passed in constructor."""
        mock_db = Mock()
        processor = FeedbackProcessor(firestore_db=mock_db)

        await processor._initialize_db()
        assert processor._db is mock_db
        assert processor._initialized is False  # did not set flag

    @pytest.mark.asyncio
    async def test_initializes_firestore_client(self):
        """Should create a Firestore client when none is provided."""
        processor = FeedbackProcessor()

        mock_client = Mock()
        with (
            patch.dict("sys.modules", {"google.cloud.firestore": Mock()}),
            patch(
                "feedback.processor.settings",
                Mock(project_id="test-project"),
            ),
        ):
            # Patch the import inside _initialize_db
            mock_module = Mock()
            mock_module.Client.return_value = mock_client
            with patch.dict("sys.modules", {"google.cloud.firestore": mock_module}):
                await processor._initialize_db()

        assert processor._db is mock_client
        assert processor._initialized is True

    @pytest.mark.asyncio
    async def test_handles_firestore_init_failure(self):
        """Should log error and keep _db as None on failure."""
        processor = FeedbackProcessor()

        with patch.dict(
            "sys.modules", {"google": None, "google.cloud": None, "google.cloud.firestore": None}
        ):
            # Force the import to raise
            with patch(
                "builtins.__import__",
                side_effect=ImportError("no module"),
            ):
                await processor._initialize_db()

        assert processor._db is None
        assert processor._initialized is False


# ---------------------------------------------------------------------------
# _get_comment_body
# ---------------------------------------------------------------------------


class TestGetCommentBody:
    """Tests for extracting comment body from feedback data."""

    def test_comment_body_key(self):
        processor = FeedbackProcessor()
        assert processor._get_comment_body({"comment_body": "hello"}) == "hello"

    def test_note_body_key(self):
        processor = FeedbackProcessor()
        assert processor._get_comment_body({"note_body": "note text"}) == "note text"

    def test_review_body_key(self):
        processor = FeedbackProcessor()
        assert processor._get_comment_body({"review_body": "review text"}) == "review text"

    def test_priority_order(self):
        """comment_body has highest priority."""
        processor = FeedbackProcessor()
        data = {
            "comment_body": "first",
            "note_body": "second",
            "review_body": "third",
        }
        assert processor._get_comment_body(data) == "first"

    def test_empty_when_no_key(self):
        processor = FeedbackProcessor()
        assert processor._get_comment_body({"foo": "bar"}) == ""

    def test_converts_non_string_to_string(self):
        processor = FeedbackProcessor()
        assert processor._get_comment_body({"comment_body": 12345}) == "12345"


# ---------------------------------------------------------------------------
# _extract_emojis
# ---------------------------------------------------------------------------


class TestExtractEmojis:
    """Tests for emoji extraction from feedback data."""

    def test_single_emoji_string(self):
        processor = FeedbackProcessor()
        data = {"emoji": "👍"}
        result = processor._extract_emojis(data)
        assert "👍" in result

    def test_emoji_list(self):
        processor = FeedbackProcessor()
        data = {"emoji": ["👍", "🎉"]}
        result = processor._extract_emojis(data)
        assert "👍" in result
        assert "🎉" in result

    def test_emojis_key_list(self):
        processor = FeedbackProcessor()
        data = {"emojis": ["🚀", "💯"]}
        result = processor._extract_emojis(data)
        assert "🚀" in result
        assert "💯" in result

    def test_emojis_key_string(self):
        processor = FeedbackProcessor()
        data = {"emojis": "🚀"}
        result = processor._extract_emojis(data)
        assert "🚀" in result

    def test_deduplication_preserves_order(self):
        processor = FeedbackProcessor()
        data = {"emoji": ["👍", "🎉", "👍"]}
        result = processor._extract_emojis(data)
        assert result.count("👍") == 1
        # order preserved: 👍 before 🎉
        assert result.index("👍") < result.index("🎉")

    def test_extracts_from_comment_body(self):
        """Emojis in the comment body should be extracted too."""
        processor = FeedbackProcessor()
        data = {"comment_body": "Great job! 👍"}
        with patch("feedback.webhook.FeedbackWebhookHandler") as MockHandler:
            handler_instance = MockHandler.return_value
            handler_instance._extract_emojis.return_value = ["👍"]
            result = processor._extract_emojis(data)

        assert "👍" in result

    def test_empty_data(self):
        processor = FeedbackProcessor()
        result = processor._extract_emojis({})
        assert result == []

    def test_both_emoji_and_emojis_merged(self):
        processor = FeedbackProcessor()
        data = {"emoji": "👍", "emojis": ["🎉"]}
        result = processor._extract_emojis(data)
        assert "👍" in result
        assert "🎉" in result


# ---------------------------------------------------------------------------
# _store_feedback
# ---------------------------------------------------------------------------


class TestStoreFeedback:
    """Tests for Firestore storage."""

    @pytest.mark.asyncio
    async def test_skips_when_no_db(self):
        """Should log warning and return when db is None."""
        processor = FeedbackProcessor()
        # No db, should not raise
        await processor._store_feedback({"id": "test", "timestamp": datetime.utcnow()})

    @pytest.mark.asyncio
    async def test_stores_record_in_firestore(self):
        """Should set document in the feedback collection."""
        mock_db = Mock()
        mock_doc_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        processor = FeedbackProcessor(firestore_db=mock_db)
        record = {
            "id": "fb_123",
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "raw_payload": {"big": "data"},
            "score": 0.8,
        }

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock()
            await processor._store_feedback(record)

        mock_db.collection.assert_called_once_with("feedback")
        mock_db.collection.return_value.document.assert_called_once_with("fb_123")

    @pytest.mark.asyncio
    async def test_removes_raw_payload_before_storage(self):
        """Record copy should not contain raw_payload."""
        mock_db = Mock()
        mock_doc_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        processor = FeedbackProcessor(firestore_db=mock_db)
        record = {
            "id": "fb_123",
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "raw_payload": {"big": "data"},
        }

        stored_data = {}

        def capture_set(data):
            stored_data.update(data)

        mock_doc_ref.set = capture_set

        with patch("asyncio.get_event_loop") as mock_loop:
            # Make run_in_executor call the lambda immediately
            async def fake_run(executor, fn):
                fn()

            mock_loop.return_value.run_in_executor = fake_run
            await processor._store_feedback(record)

        assert "raw_payload" not in stored_data
        assert stored_data["timestamp"] == "2024-01-01T12:00:00"

    @pytest.mark.asyncio
    async def test_raises_on_firestore_error(self):
        """Should re-raise Firestore errors."""
        mock_db = Mock()
        mock_db.collection.side_effect = RuntimeError("Firestore down")

        processor = FeedbackProcessor(firestore_db=mock_db)
        record = {"id": "fb_123", "timestamp": datetime.utcnow()}

        with pytest.raises(RuntimeError, match="Firestore down"):
            await processor._store_feedback(record)


# ---------------------------------------------------------------------------
# _submit_to_langfuse
# ---------------------------------------------------------------------------


class TestSubmitToLangfuse:
    """Tests for LangFuse score submission."""

    @pytest.mark.asyncio
    async def test_skips_when_langfuse_not_available(self):
        """Should return immediately when get_langfuse() is None."""
        processor = FeedbackProcessor()
        with patch("feedback.processor.get_langfuse", return_value=None):
            await processor._submit_to_langfuse(
                {"score": 0.5, "feedback_type": "positive", "user": "joe"}
            )

    @pytest.mark.asyncio
    async def test_submits_score_when_review_found(self):
        """Should call score_trace when a review ID is found."""
        mock_langfuse = Mock()
        processor = FeedbackProcessor(firestore_db=Mock())

        record = {
            "score": 0.8,
            "feedback_type": "positive",
            "user": "johndoe",
            "repo_owner": "org",
            "repo_name": "repo",
            "pr_number": 42,
        }

        with patch("feedback.processor.get_langfuse", return_value=mock_langfuse):
            with patch.object(
                processor, "_find_review_id", new_callable=AsyncMock, return_value="review-abc"
            ):
                await processor._submit_to_langfuse(record)

        mock_langfuse.score_trace.assert_called_once_with(
            trace_id="review-abc",
            name="user_feedback",
            value=0.8,
            comment="positive feedback from johndoe",
        )

    @pytest.mark.asyncio
    async def test_skips_score_when_no_review_found(self):
        """Should not call score_trace when no review ID is found."""
        mock_langfuse = Mock()
        processor = FeedbackProcessor(firestore_db=Mock())

        record = {
            "score": 0.5,
            "feedback_type": "neutral",
            "user": "joe",
            "repo_owner": "org",
            "repo_name": "repo",
            "pr_number": 1,
        }

        with patch("feedback.processor.get_langfuse", return_value=mock_langfuse):
            with patch.object(
                processor, "_find_review_id", new_callable=AsyncMock, return_value=None
            ):
                await processor._submit_to_langfuse(record)

        mock_langfuse.score_trace.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_raise_on_langfuse_error(self):
        """LangFuse submission is best-effort; errors should not propagate."""
        mock_langfuse = Mock()
        mock_langfuse.score_trace.side_effect = RuntimeError("LangFuse error")
        processor = FeedbackProcessor(firestore_db=Mock())

        record = {
            "score": 0.5,
            "feedback_type": "positive",
            "user": "joe",
            "repo_owner": "org",
            "repo_name": "repo",
            "pr_number": 1,
        }

        with patch("feedback.processor.get_langfuse", return_value=mock_langfuse):
            with patch.object(
                processor, "_find_review_id", new_callable=AsyncMock, return_value="trace-1"
            ):
                # Should not raise
                await processor._submit_to_langfuse(record)


# ---------------------------------------------------------------------------
# _find_review_id
# ---------------------------------------------------------------------------


class TestFindReviewId:
    """Tests for finding the associated review ID."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_db(self):
        processor = FeedbackProcessor()
        result = await processor._find_review_id(
            {"repo_owner": "o", "repo_name": "r", "pr_number": 1}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_doc_id_when_found(self):
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.id = "review-xyz"

        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]
        mock_db.collection.return_value = mock_query

        processor = FeedbackProcessor(firestore_db=mock_db)
        record = {"repo_owner": "org", "repo_name": "repo", "pr_number": 42}

        with patch("asyncio.get_event_loop") as mock_loop:

            async def fake_run(executor, fn):
                return fn()

            mock_loop.return_value.run_in_executor = fake_run
            result = await processor._find_review_id(record)

        assert result == "review-xyz"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_docs(self):
        mock_db = Mock()
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = []
        mock_db.collection.return_value = mock_query

        processor = FeedbackProcessor(firestore_db=mock_db)
        record = {"repo_owner": "org", "repo_name": "repo", "pr_number": 42}

        with patch("asyncio.get_event_loop") as mock_loop:

            async def fake_run(executor, fn):
                return fn()

            mock_loop.return_value.run_in_executor = fake_run
            result = await processor._find_review_id(record)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        mock_db = Mock()
        mock_db.collection.side_effect = RuntimeError("db error")

        processor = FeedbackProcessor(firestore_db=mock_db)
        record = {"repo_owner": "org", "repo_name": "repo", "pr_number": 42}

        result = await processor._find_review_id(record)
        assert result is None


# ---------------------------------------------------------------------------
# _record_metrics
# ---------------------------------------------------------------------------


class TestRecordMetrics:
    """Tests for metrics recording."""

    @pytest.mark.asyncio
    async def test_skips_when_no_metrics_client(self):
        processor = FeedbackProcessor()
        with patch("feedback.processor.get_metrics_client", return_value=None):
            await processor._record_metrics(
                {"feedback_type": "positive", "score": 0.8, "provider": "github"}
            )

    @pytest.mark.asyncio
    async def test_records_metrics(self):
        mock_metrics = Mock()
        processor = FeedbackProcessor()

        record = {"feedback_type": "positive", "score": 0.8, "provider": "github"}

        with patch("feedback.processor.get_metrics_client", return_value=mock_metrics):
            await processor._record_metrics(record)

        mock_metrics.record_feedback_metrics.assert_called_once_with(
            feedback_type="positive",
            score=0.8,
            provider="github",
        )

    @pytest.mark.asyncio
    async def test_does_not_raise_on_metrics_error(self):
        mock_metrics = Mock()
        mock_metrics.record_feedback_metrics.side_effect = RuntimeError("metrics error")
        processor = FeedbackProcessor()

        record = {"feedback_type": "positive", "score": 0.8, "provider": "github"}

        with patch("feedback.processor.get_metrics_client", return_value=mock_metrics):
            # Should not raise
            await processor._record_metrics(record)


# ---------------------------------------------------------------------------
# process_feedback (integration of the above)
# ---------------------------------------------------------------------------


class TestProcessFeedback:
    """Tests for the main process_feedback method."""

    @pytest.mark.asyncio
    async def test_happy_path(self):
        """Full processing flow with all mocks."""
        mock_db = Mock()
        mock_classifier = Mock(spec=EmojiClassifier)
        classification = _make_classification()
        mock_classifier.classify.return_value = classification
        mock_classifier.is_actionable.return_value = False

        processor = FeedbackProcessor(firestore_db=mock_db, classifier=mock_classifier)

        with (
            patch.object(processor, "_store_feedback", new_callable=AsyncMock) as mock_store,
            patch.object(processor, "_submit_to_langfuse", new_callable=AsyncMock) as mock_langfuse,
            patch.object(processor, "_record_metrics", new_callable=AsyncMock) as mock_metrics,
            patch.object(processor, "_extract_emojis", return_value=["👍"]),
        ):
            data = _make_feedback_data()
            result = await processor.process_feedback(data)

        # Verify record structure
        assert result["provider"] == "github"
        assert result["event_type"] == "comment_reaction"
        assert result["repo_owner"] == "myorg"
        assert result["repo_name"] == "myrepo"
        assert result["pr_number"] == 42
        assert result["file_path"] == "src/main.py"
        assert result["line_number"] == 10
        assert result["user"] == "johndoe"
        assert result["emojis"] == ["👍"]
        assert result["primary_emoji"] == "👍"
        assert result["feedback_type"] == "positive"
        assert result["score"] == 0.8
        assert result["confidence"] == 0.9
        assert result["is_actionable"] is False
        assert isinstance(result["timestamp"], datetime)
        assert result["id"].startswith("fb_")

        mock_store.assert_awaited_once()
        mock_langfuse.assert_awaited_once()
        mock_metrics.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_id_format(self):
        """Record id follows the expected pattern."""
        mock_classifier = Mock(spec=EmojiClassifier)
        mock_classifier.classify.return_value = _make_classification()
        mock_classifier.is_actionable.return_value = False

        processor = FeedbackProcessor(firestore_db=Mock(), classifier=mock_classifier)

        with (
            patch.object(processor, "_store_feedback", new_callable=AsyncMock),
            patch.object(processor, "_submit_to_langfuse", new_callable=AsyncMock),
            patch.object(processor, "_record_metrics", new_callable=AsyncMock),
            patch.object(processor, "_extract_emojis", return_value=["👍"]),
        ):
            result = await processor.process_feedback(_make_feedback_data())

        assert result["id"].startswith("fb_")

    @pytest.mark.asyncio
    async def test_defaults_for_missing_fields(self):
        """Missing fields should get sensible defaults."""
        mock_classifier = Mock(spec=EmojiClassifier)
        mock_classifier.classify.return_value = _make_classification()
        mock_classifier.is_actionable.return_value = False

        processor = FeedbackProcessor(firestore_db=Mock(), classifier=mock_classifier)

        with (
            patch.object(processor, "_store_feedback", new_callable=AsyncMock),
            patch.object(processor, "_submit_to_langfuse", new_callable=AsyncMock),
            patch.object(processor, "_record_metrics", new_callable=AsyncMock),
            patch.object(processor, "_extract_emojis", return_value=[]),
        ):
            result = await processor.process_feedback({})

        assert result["provider"] == "unknown"
        assert result["event_type"] == "unknown"
        assert result["repo_owner"] == ""
        assert result["repo_name"] == ""
        assert result["pr_number"] == 0
        assert result["file_path"] == ""
        assert result["line_number"] == 0
        assert result["user"] == ""
        assert result["raw_payload"] == {}

    @pytest.mark.asyncio
    async def test_raises_when_store_fails(self):
        """Should propagate storage errors."""
        mock_classifier = Mock(spec=EmojiClassifier)
        mock_classifier.classify.return_value = _make_classification()
        mock_classifier.is_actionable.return_value = False

        processor = FeedbackProcessor(firestore_db=Mock(), classifier=mock_classifier)

        with (
            patch.object(
                processor,
                "_store_feedback",
                new_callable=AsyncMock,
                side_effect=RuntimeError("storage error"),
            ),
            patch.object(processor, "_extract_emojis", return_value=["👍"]),
        ):
            with pytest.raises(RuntimeError, match="storage error"):
                await processor.process_feedback(_make_feedback_data())

    @pytest.mark.asyncio
    async def test_calls_initialize_db(self):
        """Should call _initialize_db."""
        mock_classifier = Mock(spec=EmojiClassifier)
        mock_classifier.classify.return_value = _make_classification()
        mock_classifier.is_actionable.return_value = False

        processor = FeedbackProcessor(firestore_db=Mock(), classifier=mock_classifier)

        with (
            patch.object(processor, "_initialize_db", new_callable=AsyncMock) as mock_init,
            patch.object(processor, "_store_feedback", new_callable=AsyncMock),
            patch.object(processor, "_submit_to_langfuse", new_callable=AsyncMock),
            patch.object(processor, "_record_metrics", new_callable=AsyncMock),
            patch.object(processor, "_extract_emojis", return_value=[]),
        ):
            await processor.process_feedback({})

        mock_init.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_comment_body_extracted(self):
        """Comment body should appear in the record."""
        mock_classifier = Mock(spec=EmojiClassifier)
        mock_classifier.classify.return_value = _make_classification()
        mock_classifier.is_actionable.return_value = False

        processor = FeedbackProcessor(firestore_db=Mock(), classifier=mock_classifier)

        with (
            patch.object(processor, "_store_feedback", new_callable=AsyncMock),
            patch.object(processor, "_submit_to_langfuse", new_callable=AsyncMock),
            patch.object(processor, "_record_metrics", new_callable=AsyncMock),
            patch.object(processor, "_extract_emojis", return_value=["👍"]),
        ):
            data = _make_feedback_data(comment_body="Nice work!")
            result = await processor.process_feedback(data)

        assert result["comment_body"] == "Nice work!"


# ---------------------------------------------------------------------------
# get_feedback_summary
# ---------------------------------------------------------------------------


class TestGetFeedbackSummary:
    """Tests for get_feedback_summary."""

    @pytest.mark.asyncio
    async def test_returns_error_when_no_db(self):
        processor = FeedbackProcessor()
        processor._initialized = True  # Skip _initialize_db so _db stays None
        result = await processor.get_feedback_summary("org", "repo")
        assert result == {"error": "Database not available"}

    @pytest.mark.asyncio
    async def test_returns_no_feedback_message(self):
        mock_db = Mock()
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = []
        mock_db.collection.return_value = mock_query

        processor = FeedbackProcessor(firestore_db=mock_db)

        with patch("asyncio.get_event_loop") as mock_loop:

            async def fake_run(executor, fn):
                return fn()

            mock_loop.return_value.run_in_executor = fake_run
            result = await processor.get_feedback_summary("org", "repo", days=30)

        assert result["total"] == 0
        assert result["period_days"] == 30
        assert "No feedback found" in result["message"]

    @pytest.mark.asyncio
    async def test_calculates_correct_statistics(self):
        mock_db = Mock()
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = []
        mock_db.collection.return_value = mock_query

        # Create mock docs
        def make_doc(feedback_type, score, is_actionable=False):
            doc = Mock()
            doc.to_dict.return_value = {
                "feedback_type": feedback_type,
                "score": score,
                "is_actionable": is_actionable,
            }
            return doc

        mock_docs = [
            make_doc(FeedbackType.POSITIVE.value, 0.8),
            make_doc(FeedbackType.POSITIVE.value, 0.9),
            make_doc(FeedbackType.NEGATIVE.value, -0.7, True),
            make_doc(FeedbackType.NEUTRAL.value, 0.0),
            make_doc(FeedbackType.CONFUSED.value, -0.3, True),
        ]
        mock_query.stream.return_value = mock_docs

        processor = FeedbackProcessor(firestore_db=mock_db)

        with patch("asyncio.get_event_loop") as mock_loop:

            async def fake_run(executor, fn):
                return fn()

            mock_loop.return_value.run_in_executor = fake_run
            result = await processor.get_feedback_summary("org", "repo", days=14)

        assert result["total"] == 5
        assert result["period_days"] == 14
        assert result["breakdown"]["positive"] == 2
        assert result["breakdown"]["negative"] == 1
        assert result["breakdown"]["neutral"] == 1
        assert result["breakdown"]["confused"] == 1
        assert result["percentages"]["positive"] == pytest.approx(40.0)
        assert result["percentages"]["negative"] == pytest.approx(20.0)
        assert result["percentages"]["neutral"] == pytest.approx(20.0)
        assert result["percentages"]["confused"] == pytest.approx(20.0)
        # avg = (0.8 + 0.9 + (-0.7) + 0.0 + (-0.3)) / 5 = 0.14
        assert result["average_score"] == pytest.approx(0.14, abs=0.01)
        assert result["actionable_count"] == 2
        assert result["satisfaction_rate"] == pytest.approx(40.0)

    @pytest.mark.asyncio
    async def test_returns_error_on_exception(self):
        mock_db = Mock()
        mock_db.collection.side_effect = RuntimeError("db error")

        processor = FeedbackProcessor(firestore_db=mock_db)
        result = await processor.get_feedback_summary("org", "repo")

        assert "error" in result
        assert "db error" in result["error"]

    @pytest.mark.asyncio
    async def test_calls_initialize_db(self):
        processor = FeedbackProcessor()

        with patch.object(processor, "_initialize_db", new_callable=AsyncMock) as mock_init:
            result = await processor.get_feedback_summary("org", "repo")

        mock_init.assert_awaited_once()
        assert result == {"error": "Database not available"}


# ---------------------------------------------------------------------------
# get_recent_feedback
# ---------------------------------------------------------------------------


class TestGetRecentFeedback:
    """Tests for get_recent_feedback."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_db(self):
        processor = FeedbackProcessor()
        result = await processor.get_recent_feedback("org", "repo")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_feedback_list(self):
        mock_db = Mock()
        mock_query = Mock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query

        doc1 = Mock()
        doc1.to_dict.return_value = {"id": "fb_1", "score": 0.5}
        doc2 = Mock()
        doc2.to_dict.return_value = {"id": "fb_2", "score": -0.3}
        mock_query.stream.return_value = [doc1, doc2]
        mock_db.collection.return_value = mock_query

        processor = FeedbackProcessor(firestore_db=mock_db)

        with patch("asyncio.get_event_loop") as mock_loop:

            async def fake_run(executor, fn):
                return fn()

            mock_loop.return_value.run_in_executor = fake_run
            result = await processor.get_recent_feedback("org", "repo", limit=5)

        assert len(result) == 2
        assert result[0]["id"] == "fb_1"
        assert result[1]["id"] == "fb_2"
        mock_query.limit.assert_called_with(5)

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        mock_db = Mock()
        mock_db.collection.side_effect = RuntimeError("db error")

        processor = FeedbackProcessor(firestore_db=mock_db)
        result = await processor.get_recent_feedback("org", "repo")

        assert result == []

    @pytest.mark.asyncio
    async def test_calls_initialize_db(self):
        processor = FeedbackProcessor()

        with patch.object(processor, "_initialize_db", new_callable=AsyncMock) as mock_init:
            result = await processor.get_recent_feedback("org", "repo")

        mock_init.assert_awaited_once()
        assert result == []


# ---------------------------------------------------------------------------
# get_feedback_processor (global singleton)
# ---------------------------------------------------------------------------


class TestGetFeedbackProcessor:
    """Tests for the module-level singleton getter."""

    def test_creates_instance(self):
        with patch("feedback.processor._feedback_processor", None):
            processor = get_feedback_processor()
            assert isinstance(processor, FeedbackProcessor)

    def test_returns_same_instance(self):
        with patch("feedback.processor._feedback_processor", None):
            p1 = get_feedback_processor()
            # Manually set the global so the second call returns it
            with patch("feedback.processor._feedback_processor", p1):
                p2 = get_feedback_processor()
            assert p2 is p1
