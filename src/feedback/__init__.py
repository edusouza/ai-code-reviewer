"""Feedback system for processing user reactions and comments."""

from feedback.classifier import ClassificationResult, EmojiClassifier, FeedbackType
from feedback.processor import FeedbackProcessor, get_feedback_processor
from feedback.webhook import (
    FeedbackWebhookHandler,
    bitbucket_feedback_webhook,
    feedback_handler,
    github_feedback_webhook,
    gitlab_feedback_webhook,
    router,
)

__all__ = [
    # Webhook
    "router",
    "FeedbackWebhookHandler",
    "feedback_handler",
    "github_feedback_webhook",
    "gitlab_feedback_webhook",
    "bitbucket_feedback_webhook",
    # Classifier
    "EmojiClassifier",
    "ClassificationResult",
    "FeedbackType",
    # Processor
    "FeedbackProcessor",
    "get_feedback_processor",
]
