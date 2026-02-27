from datetime import datetime
from typing import Any

from google.cloud import firestore
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint

from src.config.settings import settings


class FirestoreCheckpointer(BaseCheckpointSaver):
    """Custom LangGraph checkpointer using Firestore."""

    def __init__(self):
        super().__init__()
        self.db = firestore.Client(project=settings.project_id)
        self.collection = self.db.collection("review_checkpoints")

    def get(self, config: dict[str, Any]) -> Checkpoint | None:
        """Load checkpoint from Firestore."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None

        doc_ref = self.collection.document(thread_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        return Checkpoint(
            v=data["v"],
            ts=data["ts"],
            channel_values=self._deserialize_state(data["channel_values"]),
            channel_versions=data["channel_versions"],
            versions_seen=data["versions_seen"],
        )

    def put(self, config: dict[str, Any], checkpoint: Checkpoint) -> dict[str, Any]:
        """Save checkpoint to Firestore."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id is required in config")

        doc_ref = self.collection.document(thread_id)
        doc_ref.set(
            {
                "v": checkpoint["v"],
                "ts": checkpoint["ts"],
                "channel_values": self._serialize_state(checkpoint["channel_values"]),
                "channel_versions": checkpoint["channel_versions"],
                "versions_seen": checkpoint["versions_seen"],
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

        return {"configurable": {"thread_id": thread_id}}

    def list(self, config: dict[str, Any]) -> list[Checkpoint]:
        """List all checkpoints for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return []

        docs = self.collection.where("thread_id", "==", thread_id).order_by("ts").stream()
        checkpoints = []

        for doc in docs:
            data = doc.to_dict()
            checkpoints.append(
                Checkpoint(
                    v=data["v"],
                    ts=data["ts"],
                    channel_values=self._deserialize_state(data["channel_values"]),
                    channel_versions=data["channel_versions"],
                    versions_seen=data["versions_seen"],
                )
            )

        return checkpoints

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
