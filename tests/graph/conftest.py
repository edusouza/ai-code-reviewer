"""Conftest for graph tests - mock missing Google Cloud and langgraph modules."""

import sys
import types
from typing import Any, NamedTuple
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Mock google.cloud.firestore (not installed in test environment)
# ---------------------------------------------------------------------------
_firestore_mod = types.ModuleType("google.cloud.firestore")
_firestore_mod.Client = MagicMock
sys.modules.setdefault("google.cloud.firestore", _firestore_mod)

# ---------------------------------------------------------------------------
# 2. Patch langgraph.checkpoint.base to add CheckpointMetadata if missing,
#    and update CheckpointTuple to accept metadata/pending_writes if needed.
# ---------------------------------------------------------------------------
import langgraph.checkpoint.base as _lcb  # noqa: E402

if not hasattr(_lcb, "CheckpointMetadata"):
    _lcb.CheckpointMetadata = dict  # type: ignore[attr-defined]

# The installed CheckpointTuple may not have metadata/pending_writes fields.
# The source code creates CheckpointTuple with those extra keyword args.
# Provide a compatible replacement if needed.
_existing_fields = getattr(_lcb.CheckpointTuple, "_fields", ())
if "metadata" not in _existing_fields:

    class _CheckpointTuple(NamedTuple):
        config: dict
        checkpoint: Any
        metadata: Any = None
        parent_config: dict | None = None
        pending_writes: Any = None

    _lcb.CheckpointTuple = _CheckpointTuple  # type: ignore[assignment,misc]
