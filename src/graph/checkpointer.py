from collections.abc import Iterator
from datetime import datetime
from typing import Any, cast

from google.cloud.firestore import Client as FirestoreClient
from langgraph.checkpoint.base import (  # type: ignore[attr-defined]
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

from src.config.settings import settings


class FirestoreCheckpointer(BaseCheckpointSaver):
    """Custom LangGraph checkpointer using Firestore."""

    def __init__(self) -> None:
        super().__init__()
        self.db = FirestoreClient(project=settings.project_id)
        self.collection = self.db.collection("review_checkpoints")

    def get_tuple(self, config: dict[str, Any]) -> CheckpointTuple | None:  # type: ignore[override]
        """Load checkpoint tuple from Firestore."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None

        doc_ref = self.collection.document(thread_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        checkpoint = cast(
            Checkpoint,
            {
                "v": data["v"],
                "ts": data["ts"],
                "id": data.get("id", thread_id),
                "channel_values": self._deserialize_state(data["channel_values"]),
                "channel_versions": data["channel_versions"],
                "versions_seen": data["versions_seen"],
                "pending_sends": data.get("pending_sends", []),
            },
        )
        metadata = cast(
            CheckpointMetadata,
            data.get("metadata", {}),
        )

        return CheckpointTuple(  # type: ignore[call-arg]
            config=config,  # type: ignore[arg-type]
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=None,
            pending_writes=None,
        )

    def put(  # type: ignore[override]
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save checkpoint to Firestore."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id is required in config")

        doc_ref = self.collection.document(thread_id)
        doc_ref.set(
            {
                "v": checkpoint["v"],
                "ts": checkpoint["ts"],
                "id": checkpoint.get("id", thread_id),
                "channel_values": self._serialize_state(checkpoint["channel_values"]),
                "channel_versions": checkpoint["channel_versions"],
                "versions_seen": checkpoint["versions_seen"],
                "pending_sends": checkpoint.get("pending_sends", []),
                "metadata": metadata if metadata else {},
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

        return {"configurable": {"thread_id": thread_id}}

    def put_writes(  # type: ignore[override]
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Save intermediate writes linked to a checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return

        doc_ref = self.collection.document(f"{thread_id}_writes_{task_id}")
        doc_ref.set(
            {
                "thread_id": thread_id,
                "task_id": task_id,
                "writes": [{"channel": channel, "value": str(value)} for channel, value in writes],
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

    def list(  # type: ignore[override]
        self,
        config: dict[str, Any],
        *,
        filter: dict[str, Any] | None = None,
        before: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints that match a given configuration."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return

        docs = self.collection.where("thread_id", "==", thread_id).order_by("ts").stream()

        for count, doc in enumerate(docs):
            if limit and count >= limit:
                break

            data = doc.to_dict()
            checkpoint = cast(
                Checkpoint,
                {
                    "v": data["v"],
                    "ts": data["ts"],
                    "id": data.get("id", ""),
                    "channel_values": self._deserialize_state(data["channel_values"]),
                    "channel_versions": data["channel_versions"],
                    "versions_seen": data["versions_seen"],
                    "pending_sends": data.get("pending_sends", []),
                },
            )
            metadata = cast(
                CheckpointMetadata,
                data.get("metadata", {}),
            )

            yield CheckpointTuple(  # type: ignore[call-arg]
                config=config,  # type: ignore[arg-type]
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
                pending_writes=None,
            )

    def _serialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Serialize state for Firestore storage."""
        serialized = {}
        for key, value in state.items():
            if hasattr(value, "dict"):
                # Pydantic model
                serialized[key] = {
                    "_type": "pydantic",
                    "_class": value.__class__.__name__,
                    "_data": value.dict(),
                }
            elif isinstance(value, datetime):
                serialized[key] = {"_type": "datetime", "_data": value.isoformat()}
            else:
                serialized[key] = value
        return serialized

    def _deserialize_state(self, data: dict[str, Any]) -> dict[str, Any]:
        """Deserialize state from Firestore."""
        deserialized = {}
        for key, value in data.items():
            if isinstance(value, dict) and "_type" in value:
                if value["_type"] == "pydantic":
                    # Reconstruct pydantic model
                    from src.models.events import PREvent, ReviewComment

                    class_map = {"PREvent": PREvent, "ReviewComment": ReviewComment}
                    model_class = class_map.get(value["_class"])
                    if model_class:
                        deserialized[key] = model_class(**value["_data"])
                    else:
                        deserialized[key] = value["_data"]
                elif value["_type"] == "datetime":
                    deserialized[key] = datetime.fromisoformat(value["_data"])
                else:
                    deserialized[key] = value
            else:
                deserialized[key] = value
        return deserialized
