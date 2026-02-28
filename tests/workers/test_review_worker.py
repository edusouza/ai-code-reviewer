"""Tests for the ReviewWorker and ReviewJob classes."""

import asyncio
import json
import signal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from models.events import PRAction, PREvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pr_event_dict(**overrides):
    """Return a dict suitable for embedding inside a Pub/Sub message."""
    base = {
        "provider": "github",
        "repo_owner": "myorg",
        "repo_name": "myrepo",
        "pr_number": 42,
        "action": "opened",
        "branch": "feature/new-thing",
        "target_branch": "main",
        "commit_sha": "abc123",
        "pr_title": "Add new feature",
        "pr_body": "This PR adds a new feature",
        "author": "johndoe",
        "url": "https://github.com/myorg/myrepo/pull/42",
        "raw_payload": {},
    }
    base.update(overrides)
    return base


def _make_message(pr_event_dict=None, priority=5, delivery_attempt=1, message_id="msg-123"):
    """Build a fake Pub/Sub Message object."""
    pr_event_dict = pr_event_dict or _make_pr_event_dict()
    data = json.dumps({"pr_event": pr_event_dict, "priority": priority}).encode("utf-8")

    message = Mock()
    message.data = data
    message.message_id = message_id
    message.delivery_attempt = delivery_attempt
    message.ack = Mock()
    message.nack = Mock()
    return message


# ---------------------------------------------------------------------------
# ReviewJob tests
# ---------------------------------------------------------------------------


class TestReviewJob:
    """Tests for ReviewJob dataclass and factory method."""

    def test_from_message_basic(self):
        """from_message should parse a well-formed Pub/Sub message."""
        from workers.review_worker import ReviewJob

        msg = _make_message(priority=3, delivery_attempt=2, message_id="id-abc")
        job = ReviewJob.from_message(msg)

        assert job.id == "id-abc"
        assert isinstance(job.pr_event, PREvent)
        assert job.pr_event.provider == "github"
        assert job.pr_event.repo_owner == "myorg"
        assert job.pr_event.repo_name == "myrepo"
        assert job.pr_event.pr_number == 42
        assert job.priority == 3
        assert job.delivery_attempt == 2
        assert isinstance(job.received_at, datetime)

    def test_from_message_default_priority(self):
        """When priority is missing, it should default to 5."""
        from workers.review_worker import ReviewJob

        data = json.dumps({"pr_event": _make_pr_event_dict()}).encode("utf-8")
        msg = Mock()
        msg.data = data
        msg.message_id = "id-1"
        msg.delivery_attempt = 1

        job = ReviewJob.from_message(msg)
        assert job.priority == 5

    def test_from_message_none_delivery_attempt(self):
        """When delivery_attempt is None, it should default to 1."""
        from workers.review_worker import ReviewJob

        msg = _make_message(delivery_attempt=None)
        job = ReviewJob.from_message(msg)
        assert job.delivery_attempt == 1

    def test_from_message_invalid_json_raises(self):
        """Malformed JSON should raise."""
        from workers.review_worker import ReviewJob

        msg = Mock()
        msg.data = b"not-json"
        msg.message_id = "id-bad"
        msg.delivery_attempt = 1

        with pytest.raises(json.JSONDecodeError):
            ReviewJob.from_message(msg)

    def test_from_message_missing_pr_event_raises(self):
        """Missing pr_event key should raise."""
        from workers.review_worker import ReviewJob

        msg = Mock()
        msg.data = json.dumps({"priority": 5}).encode("utf-8")
        msg.message_id = "id-miss"
        msg.delivery_attempt = 1

        with pytest.raises(KeyError):
            ReviewJob.from_message(msg)


# ---------------------------------------------------------------------------
# ReviewWorker.__init__ tests
# ---------------------------------------------------------------------------


class TestReviewWorkerInit:
    """Tests for ReviewWorker constructor."""

    @patch("workers.review_worker.settings")
    def test_default_init(self, mock_settings):
        """Default init uses settings.project_id."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "my-project"

        worker = ReviewWorker()

        assert worker.project_id == "my-project"
        assert worker.subscription_id == "review-jobs-sub"
        assert worker.max_workers == 10
        assert worker.max_retries == 3
        assert worker.dlq_topic == "review-jobs-dlq"
        assert worker.subscriber is None
        assert worker.publisher is None
        assert worker.subscription_path is None
        assert worker.streaming_pull_future is None
        assert worker._shutdown is False
        assert worker._active_workers == 0
        assert worker.jobs_processed == 0
        assert worker.jobs_failed == 0
        assert worker.jobs_dlq == 0
        assert worker._process_callback is None

    @patch("workers.review_worker.settings")
    def test_custom_init(self, mock_settings):
        """Custom parameters override defaults."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "default-project"

        worker = ReviewWorker(
            project_id="custom-project",
            subscription_id="custom-sub",
            max_workers=5,
            max_retries=7,
            dlq_topic="custom-dlq",
        )

        assert worker.project_id == "custom-project"
        assert worker.subscription_id == "custom-sub"
        assert worker.max_workers == 5
        assert worker.max_retries == 7
        assert worker.dlq_topic == "custom-dlq"

    @patch("workers.review_worker.settings")
    def test_project_id_from_settings_when_none(self, mock_settings):
        """When project_id is None, settings.project_id is used."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "settings-project"

        worker = ReviewWorker(project_id=None)
        assert worker.project_id == "settings-project"


# ---------------------------------------------------------------------------
# ReviewWorker.initialize tests
# ---------------------------------------------------------------------------


class TestReviewWorkerInitialize:
    """Tests for ReviewWorker.initialize."""

    @patch("workers.review_worker.settings")
    @patch("workers.review_worker.PublisherClient")
    @patch("workers.review_worker.SubscriberClient")
    def test_initialize_creates_clients(self, mock_sub_cls, mock_pub_cls, mock_settings):
        """initialize() creates subscriber, publisher, and subscription_path."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        mock_sub_instance = Mock()
        mock_sub_instance.subscription_path.return_value = (
            "projects/proj/subscriptions/review-jobs-sub"
        )
        mock_sub_cls.return_value = mock_sub_instance

        mock_pub_instance = Mock()
        mock_pub_cls.return_value = mock_pub_instance

        worker = ReviewWorker(project_id="proj")
        worker.initialize()

        assert worker.subscriber is mock_sub_instance
        assert worker.publisher is mock_pub_instance
        assert worker.subscription_path == "projects/proj/subscriptions/review-jobs-sub"
        mock_sub_instance.subscription_path.assert_called_once_with("proj", "review-jobs-sub")

    @patch("workers.review_worker.settings")
    @patch("workers.review_worker.SubscriberClient", side_effect=Exception("connection failed"))
    def test_initialize_raises_on_failure(self, mock_sub_cls, mock_settings):
        """initialize() propagates exceptions from client creation."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(project_id="proj")
        with pytest.raises(Exception, match="connection failed"):
            worker.initialize()


# ---------------------------------------------------------------------------
# ReviewWorker.on_job tests
# ---------------------------------------------------------------------------


class TestReviewWorkerOnJob:
    """Tests for on_job callback registration."""

    @patch("workers.review_worker.settings")
    def test_on_job_registers_callback(self, mock_settings):
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"
        worker = ReviewWorker()

        async def my_callback(job):
            pass

        result = worker.on_job(my_callback)
        assert result is None
        assert worker._process_callback is my_callback


# ---------------------------------------------------------------------------
# ReviewWorker.start tests
# ---------------------------------------------------------------------------


class TestReviewWorkerStart:
    """Tests for start()."""

    @patch("workers.review_worker.settings")
    def test_start_without_callback_raises(self, mock_settings):
        """start() raises ValueError if no callback registered."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        # Give it a subscriber so it does not try to call initialize
        worker.subscriber = Mock()

        with pytest.raises(ValueError, match="No processing callback registered"):
            worker.start()

    @patch("workers.review_worker.settings")
    def test_start_calls_initialize_if_subscriber_is_none(self, mock_settings):
        """start() calls initialize() when subscriber is None."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        worker._process_callback = AsyncMock()

        # Make initialize set the subscriber
        mock_subscriber = Mock()
        mock_subscriber.subscription_path.return_value = "path"
        mock_future = Mock()
        mock_future.result.return_value = None
        mock_subscriber.subscribe.return_value = mock_future

        with patch.object(worker, "initialize") as mock_init:
            # After initialize, subscriber should be set
            def set_subscriber():
                worker.subscriber = mock_subscriber
                worker.subscription_path = "path"

            mock_init.side_effect = lambda: set_subscriber()

            worker.start()

            mock_init.assert_called_once()
            mock_subscriber.subscribe.assert_called_once()

    @patch("workers.review_worker.settings")
    def test_start_raises_if_subscriber_still_none_after_init(self, mock_settings):
        """start() raises RuntimeError if subscriber is still None after initialize."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        worker._process_callback = AsyncMock()

        with patch.object(worker, "initialize"):
            # initialize does nothing, subscriber stays None
            with pytest.raises(RuntimeError, match="Subscriber failed to initialize"):
                worker.start()

    @patch("workers.review_worker.settings")
    @patch("workers.review_worker.signal.signal")
    def test_start_sets_up_signal_handlers(self, mock_signal, mock_settings):
        """start() registers SIGINT and SIGTERM handlers."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        mock_subscriber = Mock()
        mock_subscriber.subscription_path.return_value = "path"
        mock_future = Mock()
        mock_future.result.return_value = None
        mock_subscriber.subscribe.return_value = mock_future

        worker = ReviewWorker()
        worker.subscriber = mock_subscriber
        worker.subscription_path = "path"
        worker._process_callback = AsyncMock()

        worker.start()

        # Should have registered both signal handlers
        calls = mock_signal.call_args_list
        sig_nums = [c[0][0] for c in calls]
        assert signal.SIGINT in sig_nums
        assert signal.SIGTERM in sig_nums

    @patch("workers.review_worker.settings")
    def test_start_handles_streaming_pull_exception(self, mock_settings):
        """start() catches and cancels future on streaming pull error."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        mock_subscriber = Mock()
        mock_future = Mock()
        # First result() call raises, second (after cancel) returns None
        mock_future.result.side_effect = [Exception("pull error"), None]
        mock_subscriber.subscribe.return_value = mock_future

        worker = ReviewWorker()
        worker.subscriber = mock_subscriber
        worker.subscription_path = "path"
        worker._process_callback = AsyncMock()

        worker.start()

        mock_future.cancel.assert_called_once()


# ---------------------------------------------------------------------------
# ReviewWorker._signal_handler tests
# ---------------------------------------------------------------------------


class TestReviewWorkerSignalHandler:
    """Tests for _signal_handler."""

    @patch("workers.review_worker.settings")
    def test_signal_handler_cancels_future_and_exits(self, mock_settings):
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        mock_future = Mock()
        worker.streaming_pull_future = mock_future

        with pytest.raises(SystemExit):
            worker._signal_handler(signal.SIGINT, None)

        assert worker._shutdown is True
        mock_future.cancel.assert_called_once()

    @patch("workers.review_worker.settings")
    def test_signal_handler_no_future(self, mock_settings):
        """Signal handler works when streaming_pull_future is None."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        worker.streaming_pull_future = None

        with pytest.raises(SystemExit):
            worker._signal_handler(signal.SIGTERM, None)

        assert worker._shutdown is True


# ---------------------------------------------------------------------------
# ReviewWorker._process_message tests
# ---------------------------------------------------------------------------


class TestReviewWorkerProcessMessage:
    """Tests for _process_message."""

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_process_message_happy_path(self, mock_settings):
        """Successful message processing: parse, callback, ack, metrics."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        callback = AsyncMock()
        worker._process_callback = callback

        msg = _make_message()

        await worker._process_message(msg)

        callback.assert_awaited_once()
        # The first argument to the callback is a ReviewJob
        job_arg = callback.call_args[0][0]
        assert job_arg.id == "msg-123"
        assert job_arg.pr_event.repo_owner == "myorg"

        msg.ack.assert_called_once()
        assert worker.jobs_processed == 1
        assert worker._active_workers == 0  # decremented in finally

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_process_message_callback_exception_triggers_failure_handling(
        self, mock_settings
    ):
        """When callback raises, _handle_failure is called and message is nacked."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        worker._process_callback = AsyncMock(side_effect=RuntimeError("processing failed"))

        msg = _make_message(delivery_attempt=1)

        await worker._process_message(msg)

        # Not acked (failure)
        msg.ack.assert_not_called()
        # Nacked for retry (delivery_attempt 1 < max_retries 3)
        msg.nack.assert_called_once()
        assert worker.jobs_failed == 1
        assert worker._active_workers == 0

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_process_message_parse_error_triggers_failure(self, mock_settings):
        """Malformed message triggers failure handling."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        worker._process_callback = AsyncMock()

        msg = Mock()
        msg.data = b"bad-json"
        msg.message_id = "bad-msg"
        msg.delivery_attempt = 1
        msg.ack = Mock()
        msg.nack = Mock()

        await worker._process_message(msg)

        msg.nack.assert_called_once()
        assert worker.jobs_failed == 1

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_process_message_no_callback_still_acks(self, mock_settings):
        """When no callback is registered, message is still acked (no exception raised)."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        worker._process_callback = None  # No callback

        msg = _make_message()

        await worker._process_message(msg)

        msg.ack.assert_called_once()
        assert worker.jobs_processed == 1

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_process_message_active_workers_count(self, mock_settings):
        """_active_workers is incremented during processing and decremented after."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        observed_active = []

        async def capture_active(job):
            observed_active.append(worker._active_workers)

        worker._process_callback = capture_active

        msg = _make_message()
        await worker._process_message(msg)

        assert observed_active == [1]
        assert worker._active_workers == 0


# ---------------------------------------------------------------------------
# ReviewWorker._handle_failure tests
# ---------------------------------------------------------------------------


class TestReviewWorkerHandleFailure:
    """Tests for _handle_failure."""

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_handle_failure_nacks_when_under_max_retries(self, mock_settings):
        """Under max retries: nack for retry."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(max_retries=3)

        msg = Mock()
        msg.delivery_attempt = 1
        msg.nack = Mock()
        msg.ack = Mock()

        job = Mock()
        job.id = "job-1"

        await worker._handle_failure(msg, job, RuntimeError("fail"))

        msg.nack.assert_called_once()
        msg.ack.assert_not_called()
        assert worker.jobs_failed == 1
        assert worker.jobs_dlq == 0

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_handle_failure_sends_to_dlq_at_max_retries(self, mock_settings):
        """At max retries: send to DLQ and ack."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(max_retries=3)

        msg = _make_message(delivery_attempt=3)

        with patch.object(worker, "_send_to_dlq", new_callable=AsyncMock) as mock_dlq:
            await worker._handle_failure(msg, None, RuntimeError("final fail"))

        mock_dlq.assert_awaited_once()
        msg.ack.assert_called_once()
        assert worker.jobs_dlq == 1
        assert worker.jobs_failed == 0

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_handle_failure_sends_to_dlq_above_max_retries(self, mock_settings):
        """Above max retries: same behavior as at max retries."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(max_retries=3)

        msg = _make_message(delivery_attempt=5)

        with patch.object(worker, "_send_to_dlq", new_callable=AsyncMock) as mock_dlq:
            await worker._handle_failure(msg, None, RuntimeError("x"))

        mock_dlq.assert_awaited_once()
        msg.ack.assert_called_once()
        assert worker.jobs_dlq == 1

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_handle_failure_none_delivery_attempt(self, mock_settings):
        """When delivery_attempt is None, defaults to 1 (under max retries)."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(max_retries=3)

        msg = Mock()
        msg.delivery_attempt = None
        msg.nack = Mock()
        msg.ack = Mock()

        await worker._handle_failure(msg, None, RuntimeError("fail"))

        msg.nack.assert_called_once()
        assert worker.jobs_failed == 1


# ---------------------------------------------------------------------------
# ReviewWorker._send_to_dlq tests
# ---------------------------------------------------------------------------


class TestReviewWorkerSendToDlq:
    """Tests for _send_to_dlq."""

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_send_to_dlq_no_publisher(self, mock_settings):
        """If publisher is None, logs error and returns early."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        worker.publisher = None

        msg = _make_message()
        # Should not raise
        await worker._send_to_dlq(msg, RuntimeError("err"))

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_send_to_dlq_publishes_enriched_message(self, mock_settings):
        """DLQ message includes _dlq_info with error details."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(project_id="proj", dlq_topic="my-dlq")

        mock_publisher = Mock()
        mock_publisher.topic_path.return_value = "projects/proj/topics/my-dlq"

        # Create a proper future that can be awaited
        future = asyncio.get_event_loop().create_future()
        future.set_result("dlq-msg-id")
        mock_publisher.publish.return_value = future

        worker.publisher = mock_publisher

        msg = _make_message(message_id="orig-123")

        await worker._send_to_dlq(msg, RuntimeError("something broke"))

        mock_publisher.topic_path.assert_called_once_with("proj", "my-dlq")
        mock_publisher.publish.assert_called_once()

        # Check the published data contains _dlq_info
        call_args = mock_publisher.publish.call_args
        published_data = json.loads(call_args[0][1].decode("utf-8"))
        assert "_dlq_info" in published_data
        assert published_data["_dlq_info"]["error"] == "something broke"
        assert published_data["_dlq_info"]["original_subscription"] == "review-jobs-sub"
        assert call_args[1]["original_message_id"] == "orig-123"

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_send_to_dlq_handles_publish_exception(self, mock_settings):
        """Exception during DLQ publish is caught and logged."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(project_id="proj")

        mock_publisher = Mock()
        mock_publisher.topic_path.return_value = "path"
        mock_publisher.publish.side_effect = Exception("publish failed")
        worker.publisher = mock_publisher

        msg = _make_message()

        # Should not raise
        await worker._send_to_dlq(msg, RuntimeError("err"))


# ---------------------------------------------------------------------------
# ReviewWorker.publish_review_request tests
# ---------------------------------------------------------------------------


class TestReviewWorkerPublishReviewRequest:
    """Tests for publish_review_request."""

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_publish_review_request_success(self, mock_settings):
        """Publishes a review request and returns the message ID."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"
        mock_settings.pubsub_topic = "code-reviews"

        worker = ReviewWorker(project_id="proj")

        mock_publisher = Mock()
        mock_publisher.topic_path.return_value = "projects/proj/topics/code-reviews"

        future = asyncio.get_event_loop().create_future()
        future.set_result("published-msg-id")
        mock_publisher.publish.return_value = future
        worker.publisher = mock_publisher

        pr_event = PREvent(
            provider="github",
            repo_owner="org",
            repo_name="repo",
            pr_number=10,
            action=PRAction.OPENED,
            branch="feat",
            target_branch="main",
            commit_sha="sha123",
        )

        result = await worker.publish_review_request(pr_event, priority=2)

        assert result == "published-msg-id"
        mock_publisher.topic_path.assert_called_once_with("proj", "code-reviews")
        mock_publisher.publish.assert_called_once()

        # Verify the message content
        call_args = mock_publisher.publish.call_args
        published_data = json.loads(call_args[0][1].decode("utf-8"))
        assert published_data["priority"] == 2
        assert published_data["pr_event"]["provider"] == "github"
        assert published_data["pr_event"]["pr_number"] == 10
        assert "published_at" in published_data

        # Verify keyword arguments (attributes)
        assert call_args[1]["priority"] == "2"
        assert call_args[1]["provider"] == "github"
        assert call_args[1]["repo"] == "org/repo"
        assert call_args[1]["pr_number"] == "10"

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_publish_review_request_calls_initialize_if_no_publisher(self, mock_settings):
        """publish_review_request initializes publisher if not present."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"
        mock_settings.pubsub_topic = "code-reviews"

        worker = ReviewWorker(project_id="proj")
        assert worker.publisher is None

        mock_publisher = Mock()
        mock_publisher.topic_path.return_value = "path"
        future = asyncio.get_event_loop().create_future()
        future.set_result("id")
        mock_publisher.publish.return_value = future

        with patch.object(worker, "initialize") as mock_init:

            def set_publisher():
                worker.publisher = mock_publisher

            mock_init.side_effect = lambda: set_publisher()

            pr_event = PREvent(
                provider="github",
                repo_owner="org",
                repo_name="repo",
                pr_number=1,
                action=PRAction.OPENED,
                branch="b",
                target_branch="main",
                commit_sha="s",
            )

            result = await worker.publish_review_request(pr_event)
            mock_init.assert_called_once()
            assert result == "id"

    @pytest.mark.asyncio
    @patch("workers.review_worker.settings")
    async def test_publish_review_request_raises_if_publisher_still_none(self, mock_settings):
        """RuntimeError if publisher is still None after initialize."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(project_id="proj")

        with patch.object(worker, "initialize"):
            pr_event = PREvent(
                provider="github",
                repo_owner="org",
                repo_name="repo",
                pr_number=1,
                action=PRAction.OPENED,
                branch="b",
                target_branch="main",
                commit_sha="s",
            )

            with pytest.raises(RuntimeError, match="Publisher failed to initialize"):
                await worker.publish_review_request(pr_event)


# ---------------------------------------------------------------------------
# ReviewWorker.get_stats tests
# ---------------------------------------------------------------------------


class TestReviewWorkerGetStats:
    """Tests for get_stats."""

    @patch("workers.review_worker.settings")
    def test_get_stats_returns_expected_keys(self, mock_settings):
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker(subscription_id="my-sub", max_workers=5)
        worker.jobs_processed = 10
        worker.jobs_failed = 2
        worker.jobs_dlq = 1
        worker._active_workers = 3

        stats = worker.get_stats()

        assert stats == {
            "jobs_processed": 10,
            "jobs_failed": 2,
            "jobs_dlq": 1,
            "subscription": "my-sub",
            "max_workers": 5,
            "active_workers": 3,
        }


# ---------------------------------------------------------------------------
# ReviewWorker.close tests
# ---------------------------------------------------------------------------


class TestReviewWorkerClose:
    """Tests for close."""

    @patch("workers.review_worker.settings")
    def test_close_cancels_future_and_closes_clients(self, mock_settings):
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        mock_future = Mock()
        mock_subscriber = Mock()
        mock_publisher = Mock()
        mock_publisher.transport = Mock()

        worker.streaming_pull_future = mock_future
        worker.subscriber = mock_subscriber
        worker.publisher = mock_publisher

        worker.close()

        mock_future.cancel.assert_called_once()
        mock_subscriber.close.assert_called_once()
        mock_publisher.transport.close.assert_called_once()

    @patch("workers.review_worker.settings")
    def test_close_with_no_clients(self, mock_settings):
        """close() works when all clients are None."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        # All None by default, should not raise
        worker.close()

    @patch("workers.review_worker.settings")
    def test_close_with_partial_clients(self, mock_settings):
        """close() works when only some clients are set."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()
        mock_subscriber = Mock()
        worker.subscriber = mock_subscriber

        worker.close()

        mock_subscriber.close.assert_called_once()


# ---------------------------------------------------------------------------
# ReviewWorker._message_callback tests
# ---------------------------------------------------------------------------


class TestReviewWorkerMessageCallback:
    """Tests for _message_callback."""

    @patch("workers.review_worker.settings")
    def test_message_callback_creates_task(self, mock_settings):
        """_message_callback schedules _process_message as a task on the event loop."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()

        msg = _make_message()

        # Create a mock event loop
        mock_loop = Mock()
        mock_loop.is_closed.return_value = False
        mock_loop.create_task = Mock()

        with patch("workers.review_worker.asyncio.get_event_loop", return_value=mock_loop):
            worker._message_callback(msg)

        mock_loop.create_task.assert_called_once()

    @patch("workers.review_worker.settings")
    def test_message_callback_creates_new_loop_on_runtime_error(self, mock_settings):
        """When no event loop exists, a new one is created."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()

        msg = _make_message()

        mock_new_loop = Mock()
        mock_new_loop.create_task = Mock()

        with (
            patch(
                "workers.review_worker.asyncio.get_event_loop",
                side_effect=RuntimeError("no loop"),
            ),
            patch(
                "workers.review_worker.asyncio.new_event_loop",
                return_value=mock_new_loop,
            ),
            patch("workers.review_worker.asyncio.set_event_loop") as mock_set,
        ):
            worker._message_callback(msg)

        mock_set.assert_called_once_with(mock_new_loop)
        mock_new_loop.create_task.assert_called_once()

    @patch("workers.review_worker.settings")
    def test_message_callback_creates_new_loop_on_closed_loop(self, mock_settings):
        """When the existing event loop is closed, a new one is created."""
        from workers.review_worker import ReviewWorker

        mock_settings.project_id = "proj"

        worker = ReviewWorker()

        msg = _make_message()

        mock_closed_loop = Mock()
        mock_closed_loop.is_closed.return_value = True

        mock_new_loop = Mock()
        mock_new_loop.create_task = Mock()

        with (
            patch(
                "workers.review_worker.asyncio.get_event_loop",
                return_value=mock_closed_loop,
            ),
            patch(
                "workers.review_worker.asyncio.new_event_loop",
                return_value=mock_new_loop,
            ),
            patch("workers.review_worker.asyncio.set_event_loop") as mock_set,
        ):
            worker._message_callback(msg)

        mock_set.assert_called_once_with(mock_new_loop)
        mock_new_loop.create_task.assert_called_once()


# ---------------------------------------------------------------------------
# Module-level functions: init_worker, get_worker
# ---------------------------------------------------------------------------


class TestModuleLevelFunctions:
    """Tests for init_worker and get_worker module-level functions."""

    @patch("workers.review_worker.settings")
    def test_init_worker(self, mock_settings):
        from workers.review_worker import ReviewWorker, get_worker, init_worker

        mock_settings.project_id = "proj"

        worker = init_worker(project_id="test-proj", subscription_id="test-sub", max_workers=3)

        assert isinstance(worker, ReviewWorker)
        assert worker.project_id == "test-proj"
        assert worker.subscription_id == "test-sub"
        assert worker.max_workers == 3

        # get_worker should return the same instance
        assert get_worker() is worker

    @patch("workers.review_worker.settings")
    def test_get_worker_returns_none_initially(self, mock_settings):
        """Before init_worker, get_worker returns None (or a previously set value)."""
        import workers.review_worker as mod

        mock_settings.project_id = "proj"

        # Store original and reset
        original = mod._worker
        mod._worker = None

        try:
            assert mod.get_worker() is None
        finally:
            mod._worker = original


# ---------------------------------------------------------------------------
# process_review_job (example async function)
# ---------------------------------------------------------------------------


class TestProcessReviewJob:
    """Tests for the example process_review_job function."""

    @pytest.mark.asyncio
    async def test_process_review_job_happy_path(self):
        """process_review_job builds graph, runs it, and completes trace."""
        from workers.review_worker import ReviewJob, process_review_job

        pr_event = PREvent(
            provider="github",
            repo_owner="org",
            repo_name="repo",
            pr_number=1,
            action=PRAction.OPENED,
            branch="feat",
            target_branch="main",
            commit_sha="sha",
        )

        job = ReviewJob(
            id="job-1",
            pr_event=pr_event,
            priority=5,
            received_at=datetime.utcnow(),
        )

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "suggestions": [{"msg": "test"}],
            "passed": True,
        }

        mock_langfuse = Mock()
        mock_langfuse.create_trace.return_value = "trace-id-1"

        mock_build = Mock(return_value=mock_graph)

        with patch.dict(
            "sys.modules",
            {
                "graph.builder": MagicMock(build_review_graph=mock_build),
                "graph.state": MagicMock(),
                "observability.langfuse_client": MagicMock(
                    get_langfuse=Mock(return_value=mock_langfuse)
                ),
            },
        ):
            await process_review_job(job)

        mock_graph.ainvoke.assert_awaited_once()
        mock_langfuse.create_trace.assert_called_once()
        mock_langfuse.end_trace.assert_called_once()

        # Verify end_trace metadata
        end_call = mock_langfuse.end_trace.call_args
        assert end_call[1]["metadata"]["status"] == "completed"
        assert end_call[1]["metadata"]["suggestions_count"] == 1

    @pytest.mark.asyncio
    async def test_process_review_job_no_langfuse(self):
        """process_review_job works when langfuse is not available."""
        from workers.review_worker import ReviewJob, process_review_job

        pr_event = PREvent(
            provider="github",
            repo_owner="org",
            repo_name="repo",
            pr_number=1,
            action=PRAction.OPENED,
            branch="feat",
            target_branch="main",
            commit_sha="sha",
        )

        job = ReviewJob(
            id="job-1",
            pr_event=pr_event,
            priority=5,
            received_at=datetime.utcnow(),
        )

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"suggestions": [], "passed": True}

        mock_build = Mock(return_value=mock_graph)

        with patch.dict(
            "sys.modules",
            {
                "graph.builder": MagicMock(build_review_graph=mock_build),
                "graph.state": MagicMock(),
                "observability.langfuse_client": MagicMock(get_langfuse=Mock(return_value=None)),
            },
        ):
            await process_review_job(job)

        mock_graph.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_review_job_workflow_failure(self):
        """process_review_job re-raises exception after logging and ending trace."""
        from workers.review_worker import ReviewJob, process_review_job

        pr_event = PREvent(
            provider="github",
            repo_owner="org",
            repo_name="repo",
            pr_number=1,
            action=PRAction.OPENED,
            branch="feat",
            target_branch="main",
            commit_sha="sha",
        )

        job = ReviewJob(
            id="job-1",
            pr_event=pr_event,
            priority=5,
            received_at=datetime.utcnow(),
        )

        mock_graph = AsyncMock()
        mock_graph.ainvoke.side_effect = RuntimeError("workflow crashed")

        mock_langfuse = Mock()
        mock_langfuse.create_trace.return_value = "trace-id-err"

        mock_build = Mock(return_value=mock_graph)

        with patch.dict(
            "sys.modules",
            {
                "graph.builder": MagicMock(build_review_graph=mock_build),
                "graph.state": MagicMock(),
                "observability.langfuse_client": MagicMock(
                    get_langfuse=Mock(return_value=mock_langfuse)
                ),
            },
        ):
            with pytest.raises(RuntimeError, match="workflow crashed"):
                await process_review_job(job)

        # Verify error trace was ended
        end_call = mock_langfuse.end_trace.call_args
        assert end_call[1]["metadata"]["status"] == "failed"
        assert "workflow crashed" in end_call[1]["metadata"]["error"]

    @pytest.mark.asyncio
    async def test_process_review_job_workflow_failure_no_langfuse(self):
        """process_review_job re-raises even when langfuse is None."""
        from workers.review_worker import ReviewJob, process_review_job

        pr_event = PREvent(
            provider="github",
            repo_owner="org",
            repo_name="repo",
            pr_number=1,
            action=PRAction.OPENED,
            branch="feat",
            target_branch="main",
            commit_sha="sha",
        )

        job = ReviewJob(
            id="job-1",
            pr_event=pr_event,
            priority=5,
            received_at=datetime.utcnow(),
        )

        mock_graph = AsyncMock()
        mock_graph.ainvoke.side_effect = ValueError("bad state")

        mock_build = Mock(return_value=mock_graph)

        with (
            patch.dict(
                "sys.modules",
                {
                    "graph.builder": MagicMock(build_review_graph=mock_build),
                    "graph.state": MagicMock(),
                    "observability.langfuse_client": MagicMock(
                        get_langfuse=Mock(return_value=None)
                    ),
                },
            ),
            pytest.raises(ValueError, match="bad state"),
        ):
            await process_review_job(job)
