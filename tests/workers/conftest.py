"""Conftest for workers tests - mock missing Google Cloud modules."""

import sys
import types
from unittest.mock import MagicMock

# We need to create proper mock modules for google.cloud.pubsub_v1
# before any test imports workers.review_worker (which triggers the
# workers/__init__.py eager import chain).


class _FakeMessage:
    """Stand-in for google.cloud.pubsub_v1.subscriber.message.Message."""

    pass


class _FakeFlowControl:
    """Stand-in for google.cloud.pubsub_v1.types.FlowControl."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# Build the mock module tree
_pubsub_mod = types.ModuleType("google.cloud.pubsub_v1")
_pubsub_mod.PublisherClient = MagicMock
_pubsub_mod.SubscriberClient = MagicMock

_subscriber_mod = types.ModuleType("google.cloud.pubsub_v1.subscriber")
_message_mod = types.ModuleType("google.cloud.pubsub_v1.subscriber.message")
_message_mod.Message = _FakeMessage

_types_mod = types.ModuleType("google.cloud.pubsub_v1.types")
_types_mod.FlowControl = _FakeFlowControl

sys.modules.setdefault("google.cloud.pubsub_v1", _pubsub_mod)
sys.modules.setdefault("google.cloud.pubsub_v1.subscriber", _subscriber_mod)
sys.modules.setdefault("google.cloud.pubsub_v1.subscriber.message", _message_mod)
sys.modules.setdefault("google.cloud.pubsub_v1.types", _types_mod)
