"""Feedback system for processing user reactions and comments."""
from feedback.webhook import (
    router,
    FeedbackWebhookHandler,
    feedback_handler,
    github_feedback_webhook,
    gitlab_feedback_webhook,
    bitbucket_feedback_webhook
)
from feedback.classifier import (
    EmojiClassifier,
    ClassificationResult,
    FeedbackType
)
from feedback.processor import (
    FeedbackProcessor,
    get_feedback_processor
)

__all__ = [
    # Webhook
    'router',
    'FeedbackWebhookHandler',
    'feedback_handler',
    'github_feedback_webhook',
    'gitlab_feedback_webhook',
    'bitbucket_feedback_webhook',
    # Classifier
    'EmojiClassifier',
    'ClassificationResult',
    'FeedbackType',
    # Processor
    'FeedbackProcessor',
    'get_feedback_processor'
]
