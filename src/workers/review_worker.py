"""Pub/Sub worker for processing review jobs asynchronously."""

import asyncio
import json
import logging
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message

from config.settings import settings
from models.events import PREvent

logger = logging.getLogger(__name__)


@dataclass
class ReviewJob:
    """A review job message."""

    id: str
    pr_event: PREvent
    priority: int
    received_at: datetime
    delivery_attempt: int = 1

    @classmethod
    def from_message(cls, message: Message) -> "ReviewJob":
        """Create ReviewJob from Pub/Sub message."""
        data = json.loads(message.data.decode("utf-8"))

        return cls(
            id=message.message_id,
            pr_event=PREvent(**data["pr_event"]),
            priority=data.get("priority", 5),
            received_at=datetime.utcnow(),
            delivery_attempt=message.delivery_attempt or 1,
        )


class ReviewWorker:
    """Pub/Sub worker for processing code review jobs."""

    def __init__(
        self,
        project_id: str | None = None,
        subscription_id: str = "review-jobs-sub",
        max_workers: int = 10,
        max_retries: int = 3,
        dlq_topic: str = "review-jobs-dlq",
    ):
        """
        Initialize the review worker.

        Args:
            project_id: GCP project ID
            subscription_id: Pub/Sub subscription ID
            max_workers: Maximum concurrent workers
            max_retries: Maximum retry attempts
            dlq_topic: Dead letter queue topic
        """
        self.project_id = project_id or settings.project_id
        self.subscription_id = subscription_id
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.dlq_topic = dlq_topic

        self.subscriber = None
        self.publisher = None
        self.subscription_path = None
        self.streaming_pull_future = None
        self._shutdown = False
        self._semaphore = asyncio.Semaphore(max_workers)
        self._active_workers = 0

        # Metrics
        self.jobs_processed = 0
        self.jobs_failed = 0
        self.jobs_dlq = 0

        # Processing callback
        self._process_callback: Callable[[ReviewJob], Any] | None = None

    def initialize(self) -> None:
        """Initialize Pub/Sub clients."""
        try:
            from typing import cast

            self.subscriber = SubscriberClient()
            self.publisher = PublisherClient()

            self.subscription_path = cast(SubscriberClient, self.subscriber).subscription_path(
                self.project_id, self.subscription_id
            )

            logger.info(
                f"Review worker initialized - subscription: {self.subscription_id}, "
                f"max_workers: {self.max_workers}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Pub/Sub clients: {e}")
            raise

    def on_job(self, callback: Callable[[ReviewJob], Any]) -> None:
        """
        Decorator to register job processing callback.

        Args:
            callback: Async function to process jobs
        """
        self._process_callback = callback
        return None

    def start(self) -> None:
        """Start the worker."""
        if not self.subscriber:
            self.initialize()

        if not self.subscriber:
            raise RuntimeError("Subscriber failed to initialize")

        if not self._process_callback:
            raise ValueError("No processing callback registered. Use @worker.on_job decorator.")

        logger.info("Starting review worker...")

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start streaming pull
        from google.cloud.pubsub_v1.types import FlowControl

        flow_control = FlowControl(max_messages=self.max_workers * 2)

        self.streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path,
            callback=self._message_callback,
            flow_control=flow_control,
            await_callbacks_on_shutdown=True,
        )

        logger.info(f"Worker started, listening on {self.subscription_path}")

        # Block and wait for messages
        try:
            self.streaming_pull_future.result()
        except Exception as e:
            logger.error(f"Streaming pull error: {e}")
            self.streaming_pull_future.cancel()
            self.streaming_pull_future.result()

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self._shutdown = True

        if self.streaming_pull_future:
            self.streaming_pull_future.cancel()

        sys.exit(0)

    def _message_callback(self, message: Message) -> None:
        """Callback for received messages."""
        # Create new event loop for this thread if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Schedule the async processing
        loop.create_task(self._process_message(message))

    async def _process_message(self, message: Message) -> None:
        """Process a single message."""
        self._active_workers += 1
        try:
            async with self._semaphore:
                job = None

                try:
                    # Parse message
                    job = ReviewJob.from_message(message)

                    logger.info(
                        f"Processing job {job.id} - "
                        f"{job.pr_event.repo_owner}/{job.pr_event.repo_name}#{job.pr_event.pr_number} "
                        f"(attempt {job.delivery_attempt})"
                    )

                    # Process the job
                    if self._process_callback:
                        await self._process_callback(job)

                    # Acknowledge message
                    message.ack()

                    self.jobs_processed += 1

                    logger.info(
                        f"Job {job.id} completed successfully "
                        f"(total processed: {self.jobs_processed})"
                    )

                except Exception as e:
                    logger.error(f"Error processing job {job.id if job else 'unknown'}: {e}")

                    await self._handle_failure(message, job, e)
        finally:
            self._active_workers -= 1

    async def _handle_failure(
        self,
        message: Message,
        job: ReviewJob | None,
        error: Exception,
    ) -> None:
        """Handle message processing failure."""
        delivery_attempt = message.delivery_attempt or 1

        if delivery_attempt >= self.max_retries:
            # Send to DLQ
            logger.error(
                f"Job {job.id if job else 'unknown'} failed after {delivery_attempt} attempts, "
                f"sending to DLQ"
            )

            await self._send_to_dlq(message, error)
            message.ack()  # Acknowledge to remove from main queue
            self.jobs_dlq += 1
        else:
            # Nack for retry
            logger.warning(
                f"Job {job.id if job else 'unknown'} failed (attempt {delivery_attempt}), "
                f"will retry"
            )
            message.nack()
            self.jobs_failed += 1

    async def _send_to_dlq(self, message: Message, error: Exception) -> None:
        """Send failed message to dead letter queue."""
        if not self.publisher:
            logger.error("Cannot send to DLQ: publisher not initialized")
            return
        try:
            dlq_topic_path = self.publisher.topic_path(self.project_id, self.dlq_topic)

            # Add error information to message
            data = json.loads(message.data.decode("utf-8"))
            data["_dlq_info"] = {
                "original_subscription": self.subscription_id,
                "failed_at": datetime.utcnow().isoformat(),
                "error": str(error),
                "delivery_attempts": message.delivery_attempt,
            }

            # Publish to DLQ
            future = self.publisher.publish(
                dlq_topic_path,
                json.dumps(data).encode("utf-8"),
                original_message_id=message.message_id,
            )

            # Properly await the future result
            message_id = await asyncio.wrap_future(asyncio.ensure_future(future))

            logger.info(f"Message {message_id} sent to DLQ")

        except Exception as e:
            logger.error(f"Failed to send message to DLQ: {e}")

    async def publish_review_request(self, pr_event: PREvent, priority: int = 5) -> str:
        """
        Publish a review request to the queue.

        Args:
            pr_event: PR event data
            priority: Job priority (1-10, lower is higher priority)

        Returns:
            Message ID
        """
        if not self.publisher:
            self.initialize()

        if not self.publisher:
            raise RuntimeError("Publisher failed to initialize")

        topic_path = self.publisher.topic_path(self.project_id, settings.pubsub_topic)

        message_data = {
            "pr_event": pr_event.model_dump(),
            "priority": priority,
            "published_at": datetime.utcnow().isoformat(),
        }

        future = self.publisher.publish(
            topic_path,
            json.dumps(message_data).encode("utf-8"),
            priority=str(priority),
            provider=pr_event.provider,
            repo=f"{pr_event.repo_owner}/{pr_event.repo_name}",
            pr_number=str(pr_event.pr_number),
        )

        # Properly await the future result
        message_id = await asyncio.wrap_future(asyncio.ensure_future(future))

        logger.info(
            f"Published review request: {message_id} - "
            f"{pr_event.repo_owner}/{pr_event.repo_name}#{pr_event.pr_number}"
        )

        return message_id

    def get_stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        return {
            "jobs_processed": self.jobs_processed,
            "jobs_failed": self.jobs_failed,
            "jobs_dlq": self.jobs_dlq,
            "subscription": self.subscription_id,
            "max_workers": self.max_workers,
            "active_workers": self._active_workers,
        }

    def close(self) -> None:
        """Close the worker and cleanup resources."""
        logger.info("Closing review worker...")

        if self.streaming_pull_future:
            self.streaming_pull_future.cancel()

        if self.subscriber:
            self.subscriber.close()

        if self.publisher:
            self.publisher.transport.close()

        logger.info("Review worker closed")


# Global worker instance
_worker: ReviewWorker | None = None


def init_worker(
    project_id: str | None = None,
    subscription_id: str = "review-jobs-sub",
    max_workers: int = 10,
) -> ReviewWorker:
    """
    Initialize the global review worker.

    Args:
        project_id: GCP project ID
        subscription_id: Pub/Sub subscription ID
        max_workers: Maximum concurrent workers

    Returns:
        ReviewWorker instance
    """
    global _worker
    _worker = ReviewWorker(
        project_id=project_id, subscription_id=subscription_id, max_workers=max_workers
    )
    return _worker


def get_worker() -> ReviewWorker | None:
    """Get the global worker instance."""
    return _worker


# Example usage with LangGraph workflow
async def process_review_job(job: ReviewJob) -> None:
    """
    Example job processor that triggers the LangGraph workflow.

    This function would be registered with the worker using:

    @worker.on_job
    async def process_review_job(job: ReviewJob) -> None:
        ...
    """
    from graph.builder import build_review_graph
    from graph.state import ReviewConfig, ReviewMetadata, ReviewState
    from observability.langfuse_client import get_langfuse

    # Initialize LangFuse trace
    langfuse = get_langfuse()
    trace_id = None
    if langfuse:
        trace_id = langfuse.create_trace(
            name="pr_review",
            metadata={
                "repo": f"{job.pr_event.repo_owner}/{job.pr_event.repo_name}",
                "pr_number": job.pr_event.pr_number,
                "provider": job.pr_event.provider,
            },
        )

    try:
        # Create the review graph
        graph = build_review_graph()

        # Initialize state
        initial_state: ReviewState = {
            "pr_event": job.pr_event,
            "config": ReviewConfig(
                max_suggestions=50,
                severity_threshold="suggestion",
                enable_agents={"security": True, "style": True, "logic": True, "pattern": True},
                custom_rules={},
            ),
            "pr_diff": "",
            "agents_md": None,
            "chunks": [],
            "current_chunk_index": 0,
            "suggestions": [],
            "raw_agent_outputs": {},
            "validated_suggestions": [],
            "rejected_suggestions": [],
            "comments": [],
            "summary": "",
            "passed": True,
            "metadata": ReviewMetadata(
                review_id=job.id,
                started_at=datetime.utcnow(),
                completed_at=None,
                current_step="initialized",
                agent_results={},
                error_count=0,
            ),
            "error": None,
            "should_stop": False,
        }

        # Run the workflow
        result = await graph.ainvoke(initial_state)

        # Complete trace
        if langfuse and trace_id:
            langfuse.end_trace(
                trace_id=trace_id,
                metadata={
                    "status": "completed",
                    "suggestions_count": len(result.get("suggestions", [])),
                    "passed": result.get("passed", True),
                },
            )

        logger.info(
            f"Review completed for {job.pr_event.repo_name}#{job.pr_event.pr_number}: "
            f"{len(result.get('suggestions', []))} suggestions"
        )

    except Exception as e:
        logger.error(f"Review workflow failed: {e}")

        if langfuse and trace_id:
            langfuse.end_trace(trace_id=trace_id, metadata={"status": "failed", "error": str(e)})

        raise
