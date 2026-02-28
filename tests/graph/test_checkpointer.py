"""Tests for the FirestoreCheckpointer class."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(thread_id="thread-abc"):
    """Return a standard config dict with configurable.thread_id."""
    return {"configurable": {"thread_id": thread_id}}


def _make_checkpoint_data(
    thread_id="thread-abc",
    version=1,
    ts="2024-01-01T00:00:00",
    channel_values=None,
    channel_versions=None,
    versions_seen=None,
    pending_sends=None,
    metadata=None,
):
    """Return a dict matching the shape stored in Firestore."""
    return {
        "v": version,
        "ts": ts,
        "id": thread_id,
        "channel_values": channel_values or {},
        "channel_versions": channel_versions or {"__start__": 1},
        "versions_seen": versions_seen or {"__start__": {"__start__": 1}},
        "pending_sends": pending_sends or [],
        "metadata": metadata or {"source": "test"},
        "updated_at": "2024-01-01T00:00:00",
    }


def _create_checkpointer():
    """Create a FirestoreCheckpointer with mocked Firestore client."""
    with patch("graph.checkpointer.settings") as mock_settings:
        mock_settings.project_id = "test-project"
        with patch("graph.checkpointer.FirestoreClient") as mock_fs_cls:
            mock_db = Mock()
            mock_collection = Mock()
            mock_db.collection.return_value = mock_collection
            mock_fs_cls.return_value = mock_db

            from graph.checkpointer import FirestoreCheckpointer

            cp = FirestoreCheckpointer()

            return cp, mock_db, mock_collection


# ---------------------------------------------------------------------------
# FirestoreCheckpointer.__init__ tests
# ---------------------------------------------------------------------------


class TestFirestoreCheckpointerInit:
    """Tests for __init__."""

    def test_init_creates_firestore_client(self):
        """__init__ creates a Firestore client and collection reference."""
        cp, mock_db, mock_collection = _create_checkpointer()

        assert cp.db is mock_db
        assert cp.collection is mock_collection
        mock_db.collection.assert_called_once_with("review_checkpoints")

    def test_init_uses_settings_project_id(self):
        """__init__ passes settings.project_id to FirestoreClient."""
        with patch("graph.checkpointer.settings") as mock_settings:
            mock_settings.project_id = "custom-proj-xyz"
            with patch("graph.checkpointer.FirestoreClient") as mock_fs_cls:
                mock_db = Mock()
                mock_collection = Mock()
                mock_db.collection.return_value = mock_collection
                mock_fs_cls.return_value = mock_db

                from graph.checkpointer import FirestoreCheckpointer

                cp = FirestoreCheckpointer()

                mock_fs_cls.assert_called_once_with(project="custom-proj-xyz")
                assert cp.db is mock_db


# ---------------------------------------------------------------------------
# FirestoreCheckpointer.get_tuple tests
# ---------------------------------------------------------------------------


class TestFirestoreCheckpointerGetTuple:
    """Tests for get_tuple."""

    def test_get_tuple_no_thread_id_returns_none(self):
        """get_tuple returns None when thread_id is missing."""
        cp, _, _ = _create_checkpointer()

        result = cp.get_tuple({})
        assert result is None

        result = cp.get_tuple({"configurable": {}})
        assert result is None

    def test_get_tuple_document_not_found_returns_none(self):
        """get_tuple returns None when Firestore doc does not exist."""
        cp, _, mock_collection = _create_checkpointer()

        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_doc.exists = False
        mock_doc_ref.get.return_value = mock_doc
        mock_collection.document.return_value = mock_doc_ref

        config = _make_config("thread-missing")
        result = cp.get_tuple(config)

        assert result is None
        mock_collection.document.assert_called_once_with("thread-missing")

    def test_get_tuple_returns_checkpoint_tuple(self):
        """get_tuple returns a CheckpointTuple with correct data."""
        cp, _, mock_collection = _create_checkpointer()

        stored_data = _make_checkpoint_data(
            thread_id="thread-1",
            version=2,
            ts="2024-06-15T10:00:00",
            channel_values={"key": "value"},
            channel_versions={"ch": 1},
            versions_seen={"ch": {"ch": 1}},
            pending_sends=["send1"],
            metadata={"step": "fetch_diff"},
        )

        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = stored_data
        mock_doc_ref.get.return_value = mock_doc
        mock_collection.document.return_value = mock_doc_ref

        config = _make_config("thread-1")
        result = cp.get_tuple(config)

        assert result is not None
        assert result.config == config
        assert result.checkpoint["v"] == 2
        assert result.checkpoint["ts"] == "2024-06-15T10:00:00"
        assert result.checkpoint["id"] == "thread-1"
        assert result.checkpoint["channel_values"] == {"key": "value"}
        assert result.checkpoint["channel_versions"] == {"ch": 1}
        assert result.checkpoint["versions_seen"] == {"ch": {"ch": 1}}
        assert result.checkpoint["pending_sends"] == ["send1"]
        assert result.metadata == {"step": "fetch_diff"}
        assert result.parent_config is None
        assert result.pending_writes is None

    def test_get_tuple_missing_id_defaults_to_thread_id(self):
        """When 'id' is missing from stored data, thread_id is used."""
        cp, _, mock_collection = _create_checkpointer()

        stored_data = _make_checkpoint_data(thread_id="t-1")
        del stored_data["id"]  # Remove id

        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = stored_data
        mock_doc_ref.get.return_value = mock_doc
        mock_collection.document.return_value = mock_doc_ref

        result = cp.get_tuple(_make_config("t-1"))

        assert result.checkpoint["id"] == "t-1"

    def test_get_tuple_missing_pending_sends_defaults_to_empty(self):
        """When pending_sends is missing, defaults to []."""
        cp, _, mock_collection = _create_checkpointer()

        stored_data = _make_checkpoint_data()
        del stored_data["pending_sends"]

        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = stored_data
        mock_doc_ref.get.return_value = mock_doc
        mock_collection.document.return_value = mock_doc_ref

        result = cp.get_tuple(_make_config())

        assert result.checkpoint["pending_sends"] == []

    def test_get_tuple_missing_metadata_defaults_to_empty_dict(self):
        """When metadata is missing, defaults to {}."""
        cp, _, mock_collection = _create_checkpointer()

        stored_data = _make_checkpoint_data()
        del stored_data["metadata"]

        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = stored_data
        mock_doc_ref.get.return_value = mock_doc
        mock_collection.document.return_value = mock_doc_ref

        result = cp.get_tuple(_make_config())

        assert result.metadata == {}

    def test_get_tuple_deserializes_pydantic_channel_values(self):
        """get_tuple deserializes pydantic-serialized channel values."""
        cp, _, mock_collection = _create_checkpointer()

        stored_data = _make_checkpoint_data(
            channel_values={
                "pr_event": {
                    "_type": "pydantic",
                    "_class": "PREvent",
                    "_data": {
                        "provider": "github",
                        "repo_owner": "org",
                        "repo_name": "repo",
                        "pr_number": 1,
                        "action": "opened",
                        "branch": "feat",
                        "target_branch": "main",
                        "commit_sha": "abc",
                    },
                }
            }
        )

        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = stored_data
        mock_doc_ref.get.return_value = mock_doc
        mock_collection.document.return_value = mock_doc_ref

        result = cp.get_tuple(_make_config())

        pr_event = result.checkpoint["channel_values"]["pr_event"]
        # It should be a PREvent instance
        from src.models.events import PREvent

        assert isinstance(pr_event, PREvent)
        assert pr_event.provider == "github"
        assert pr_event.pr_number == 1

    def test_get_tuple_deserializes_datetime_channel_values(self):
        """get_tuple deserializes datetime-serialized channel values."""
        cp, _, mock_collection = _create_checkpointer()

        stored_data = _make_checkpoint_data(
            channel_values={
                "started_at": {
                    "_type": "datetime",
                    "_data": "2024-06-15T10:30:00",
                }
            }
        )

        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = stored_data
        mock_doc_ref.get.return_value = mock_doc
        mock_collection.document.return_value = mock_doc_ref

        result = cp.get_tuple(_make_config())

        started_at = result.checkpoint["channel_values"]["started_at"]
        assert isinstance(started_at, datetime)
        assert started_at.year == 2024
        assert started_at.month == 6


# ---------------------------------------------------------------------------
# FirestoreCheckpointer.put tests
# ---------------------------------------------------------------------------


class TestFirestoreCheckpointerPut:
    """Tests for put."""

    def test_put_no_thread_id_raises(self):
        """put raises ValueError when thread_id is missing."""
        cp, _, _ = _create_checkpointer()

        checkpoint = {
            "v": 1,
            "ts": "2024-01-01T00:00:00",
            "id": "x",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
        }

        with pytest.raises(ValueError, match="thread_id is required"):
            cp.put({}, checkpoint, {})

        with pytest.raises(ValueError, match="thread_id is required"):
            cp.put({"configurable": {}}, checkpoint, {})

    def test_put_saves_checkpoint_to_firestore(self):
        """put writes the checkpoint data to Firestore."""
        cp, _, mock_collection = _create_checkpointer()

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        checkpoint = {
            "v": 3,
            "ts": "2024-06-15T12:00:00",
            "id": "ckpt-1",
            "channel_values": {"key": "val"},
            "channel_versions": {"ch": 2},
            "versions_seen": {"ch": {"ch": 2}},
            "pending_sends": ["s1"],
        }
        metadata = {"source": "input", "step": 0}

        config = _make_config("thread-put-1")
        result = cp.put(config, checkpoint, metadata)

        assert result == {"configurable": {"thread_id": "thread-put-1"}}

        mock_collection.document.assert_called_once_with("thread-put-1")
        mock_doc_ref.set.assert_called_once()

        saved_data = mock_doc_ref.set.call_args[0][0]
        assert saved_data["v"] == 3
        assert saved_data["ts"] == "2024-06-15T12:00:00"
        assert saved_data["id"] == "ckpt-1"
        assert saved_data["channel_versions"] == {"ch": 2}
        assert saved_data["versions_seen"] == {"ch": {"ch": 2}}
        assert saved_data["pending_sends"] == ["s1"]
        assert saved_data["metadata"] == {"source": "input", "step": 0}
        assert "updated_at" in saved_data

    def test_put_serializes_channel_values(self):
        """put calls _serialize_state on channel_values before writing."""
        cp, _, mock_collection = _create_checkpointer()

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        # Create a mock pydantic model in channel_values
        mock_model = Mock()
        mock_model.__class__.__name__ = "PREvent"
        mock_model.dict.return_value = {"provider": "github"}
        mock_model.dict = Mock(return_value={"provider": "github"})

        checkpoint = {
            "v": 1,
            "ts": "t",
            "id": "i",
            "channel_values": {"model": mock_model},
            "channel_versions": {},
            "versions_seen": {},
        }

        cp.put(_make_config("t1"), checkpoint, {})

        saved_data = mock_doc_ref.set.call_args[0][0]
        serialized_cv = saved_data["channel_values"]
        assert serialized_cv["model"]["_type"] == "pydantic"
        assert serialized_cv["model"]["_class"] == "PREvent"

    def test_put_missing_pending_sends_defaults_to_empty(self):
        """When checkpoint has no pending_sends key, defaults to []."""
        cp, _, mock_collection = _create_checkpointer()

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        checkpoint = {
            "v": 1,
            "ts": "t",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
        }

        cp.put(_make_config("t1"), checkpoint, {})

        saved_data = mock_doc_ref.set.call_args[0][0]
        assert saved_data["pending_sends"] == []
        # id should default to thread_id
        assert saved_data["id"] == "t1"

    def test_put_none_metadata_saved_as_empty_dict(self):
        """When metadata is falsy, it's saved as {}."""
        cp, _, mock_collection = _create_checkpointer()

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        checkpoint = {
            "v": 1,
            "ts": "t",
            "id": "i",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
        }

        cp.put(_make_config("t1"), checkpoint, None)

        saved_data = mock_doc_ref.set.call_args[0][0]
        assert saved_data["metadata"] == {}

    def test_put_with_new_versions_parameter(self):
        """put accepts new_versions parameter without error."""
        cp, _, mock_collection = _create_checkpointer()

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        checkpoint = {
            "v": 1,
            "ts": "t",
            "id": "i",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
        }

        # Should not raise - new_versions is accepted but not used in current impl
        result = cp.put(_make_config("t1"), checkpoint, {}, new_versions={"ch": 2})
        assert result == {"configurable": {"thread_id": "t1"}}


# ---------------------------------------------------------------------------
# FirestoreCheckpointer.put_writes tests
# ---------------------------------------------------------------------------


class TestFirestoreCheckpointerPutWrites:
    """Tests for put_writes."""

    def test_put_writes_no_thread_id_returns_early(self):
        """put_writes returns None silently when thread_id is missing."""
        cp, _, mock_collection = _create_checkpointer()

        result = cp.put_writes({}, [("ch", "val")], "task-1")
        assert result is None
        mock_collection.document.assert_not_called()

    def test_put_writes_empty_configurable(self):
        """put_writes returns None when configurable is empty."""
        cp, _, mock_collection = _create_checkpointer()

        result = cp.put_writes({"configurable": {}}, [("ch", "val")], "task-1")
        assert result is None
        mock_collection.document.assert_not_called()

    def test_put_writes_saves_writes_to_firestore(self):
        """put_writes saves writes under the correct document ID."""
        cp, _, mock_collection = _create_checkpointer()

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        writes = [("channel_a", "value_1"), ("channel_b", {"nested": True})]
        cp.put_writes(_make_config("thread-w1"), writes, "task-42")

        mock_collection.document.assert_called_once_with("thread-w1_writes_task-42")
        mock_doc_ref.set.assert_called_once()

        saved = mock_doc_ref.set.call_args[0][0]
        assert saved["thread_id"] == "thread-w1"
        assert saved["task_id"] == "task-42"
        assert len(saved["writes"]) == 2
        assert saved["writes"][0] == {"channel": "channel_a", "value": "value_1"}
        assert saved["writes"][1] == {"channel": "channel_b", "value": "{'nested': True}"}
        assert "updated_at" in saved

    def test_put_writes_empty_writes_list(self):
        """put_writes works with an empty writes list."""
        cp, _, mock_collection = _create_checkpointer()

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        cp.put_writes(_make_config("t1"), [], "task-0")

        saved = mock_doc_ref.set.call_args[0][0]
        assert saved["writes"] == []


# ---------------------------------------------------------------------------
# FirestoreCheckpointer.list tests
# ---------------------------------------------------------------------------


class TestFirestoreCheckpointerList:
    """Tests for list."""

    def test_list_no_thread_id_yields_nothing(self):
        """list yields nothing when thread_id is missing."""
        cp, _, _ = _create_checkpointer()

        results = list(cp.list({}))
        assert results == []

        results = list(cp.list({"configurable": {}}))
        assert results == []

    def test_list_returns_checkpoint_tuples(self):
        """list yields CheckpointTuple for each doc found."""
        cp, _, mock_collection = _create_checkpointer()

        doc1_data = _make_checkpoint_data(thread_id="t1", version=1, ts="2024-01-01T00:00:00")
        doc2_data = _make_checkpoint_data(thread_id="t1", version=2, ts="2024-01-02T00:00:00")

        mock_doc1 = Mock()
        mock_doc1.to_dict.return_value = doc1_data
        mock_doc2 = Mock()
        mock_doc2.to_dict.return_value = doc2_data

        mock_query = Mock()
        mock_query.order_by.return_value = Mock()
        mock_query.order_by.return_value.stream.return_value = iter([mock_doc1, mock_doc2])
        mock_collection.where.return_value = mock_query

        config = _make_config("t1")
        results = list(cp.list(config))

        assert len(results) == 2
        assert results[0].checkpoint["v"] == 1
        assert results[1].checkpoint["v"] == 2
        assert results[0].config == config
        assert results[0].parent_config is None
        assert results[0].pending_writes is None

    def test_list_with_limit(self):
        """list respects the limit parameter."""
        cp, _, mock_collection = _create_checkpointer()

        docs = []
        for i in range(5):
            doc = Mock()
            doc.to_dict.return_value = _make_checkpoint_data(
                thread_id="t1", version=i, ts=f"2024-01-0{i + 1}T00:00:00"
            )
            docs.append(doc)

        mock_query = Mock()
        mock_query.order_by.return_value = Mock()
        mock_query.order_by.return_value.stream.return_value = iter(docs)
        mock_collection.where.return_value = mock_query

        results = list(cp.list(_make_config("t1"), limit=3))

        assert len(results) == 3
        assert results[0].checkpoint["v"] == 0
        assert results[2].checkpoint["v"] == 2

    def test_list_with_limit_zero_returns_nothing(self):
        """list with limit=0 yields nothing (0 is falsy, so limit check: `if limit and count >= limit`)."""
        cp, _, mock_collection = _create_checkpointer()

        # With limit=0, the condition `if limit and count >= limit` is False because `limit=0` is falsy
        # So it actually returns all docs. Let's verify this behavior.
        doc = Mock()
        doc.to_dict.return_value = _make_checkpoint_data(thread_id="t1", version=1)

        mock_query = Mock()
        mock_query.order_by.return_value = Mock()
        mock_query.order_by.return_value.stream.return_value = iter([doc])
        mock_collection.where.return_value = mock_query

        # limit=0 is falsy, so it won't break early
        results = list(cp.list(_make_config("t1"), limit=0))
        assert len(results) == 1

    def test_list_no_documents_yields_nothing(self):
        """list yields nothing when no documents match."""
        cp, _, mock_collection = _create_checkpointer()

        mock_query = Mock()
        mock_query.order_by.return_value = Mock()
        mock_query.order_by.return_value.stream.return_value = iter([])
        mock_collection.where.return_value = mock_query

        results = list(cp.list(_make_config("t1")))
        assert results == []

    def test_list_queries_firestore_correctly(self):
        """list queries Firestore with the correct where clause and ordering."""
        cp, _, mock_collection = _create_checkpointer()

        mock_query = Mock()
        mock_order = Mock()
        mock_order.stream.return_value = iter([])
        mock_query.order_by.return_value = mock_order
        mock_collection.where.return_value = mock_query

        list(cp.list(_make_config("thread-xyz")))

        mock_collection.where.assert_called_once_with("thread_id", "==", "thread-xyz")
        mock_query.order_by.assert_called_once_with("ts")

    def test_list_deserializes_channel_values(self):
        """list deserializes pydantic and datetime channel values."""
        cp, _, mock_collection = _create_checkpointer()

        doc_data = _make_checkpoint_data(
            channel_values={
                "started_at": {"_type": "datetime", "_data": "2024-03-15T08:00:00"},
                "plain": "value",
            }
        )

        mock_doc = Mock()
        mock_doc.to_dict.return_value = doc_data

        mock_query = Mock()
        mock_query.order_by.return_value = Mock()
        mock_query.order_by.return_value.stream.return_value = iter([mock_doc])
        mock_collection.where.return_value = mock_query

        results = list(cp.list(_make_config("t1")))

        assert len(results) == 1
        cv = results[0].checkpoint["channel_values"]
        assert isinstance(cv["started_at"], datetime)
        assert cv["plain"] == "value"

    def test_list_missing_optional_fields(self):
        """list handles docs missing optional fields like id, pending_sends, metadata."""
        cp, _, mock_collection = _create_checkpointer()

        doc_data = {
            "v": 1,
            "ts": "2024-01-01",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
        }

        mock_doc = Mock()
        mock_doc.to_dict.return_value = doc_data

        mock_query = Mock()
        mock_query.order_by.return_value = Mock()
        mock_query.order_by.return_value.stream.return_value = iter([mock_doc])
        mock_collection.where.return_value = mock_query

        results = list(cp.list(_make_config("t1")))

        assert len(results) == 1
        assert results[0].checkpoint["id"] == ""
        assert results[0].checkpoint["pending_sends"] == []
        assert results[0].metadata == {}


# ---------------------------------------------------------------------------
# FirestoreCheckpointer._serialize_state tests
# ---------------------------------------------------------------------------


class TestFirestoreCheckpointerSerializeState:
    """Tests for _serialize_state."""

    def test_serialize_plain_values(self):
        """Plain values (str, int, list, dict) pass through unchanged."""
        cp, _, _ = _create_checkpointer()

        state = {
            "str_key": "hello",
            "int_key": 42,
            "list_key": [1, 2, 3],
            "dict_key": {"nested": True},
            "none_key": None,
            "bool_key": True,
        }

        result = cp._serialize_state(state)

        assert result["str_key"] == "hello"
        assert result["int_key"] == 42
        assert result["list_key"] == [1, 2, 3]
        assert result["dict_key"] == {"nested": True}
        assert result["none_key"] is None
        assert result["bool_key"] is True

    def test_serialize_pydantic_model(self):
        """Pydantic models are serialized with _type, _class, _data."""
        cp, _, _ = _create_checkpointer()

        from src.models.events import PRAction, PREvent

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

        state = {"pr_event": pr_event}

        result = cp._serialize_state(state)

        assert result["pr_event"]["_type"] == "pydantic"
        assert result["pr_event"]["_class"] == "PREvent"
        assert isinstance(result["pr_event"]["_data"], dict)
        assert result["pr_event"]["_data"]["provider"] == "github"
        assert result["pr_event"]["_data"]["pr_number"] == 1

    def test_serialize_datetime(self):
        """datetime values are serialized with _type and _data."""
        cp, _, _ = _create_checkpointer()

        dt = datetime(2024, 6, 15, 10, 30, 0)
        state = {"timestamp": dt}

        result = cp._serialize_state(state)

        assert result["timestamp"]["_type"] == "datetime"
        assert result["timestamp"]["_data"] == "2024-06-15T10:30:00"

    def test_serialize_mixed_state(self):
        """State with mixed types serializes correctly."""
        cp, _, _ = _create_checkpointer()

        from src.models.events import PRAction, PREvent

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

        state = {
            "pr_event": pr_event,
            "started_at": datetime(2024, 1, 1),
            "count": 5,
            "name": "test",
        }

        result = cp._serialize_state(state)

        assert result["pr_event"]["_type"] == "pydantic"
        assert result["started_at"]["_type"] == "datetime"
        assert result["count"] == 5
        assert result["name"] == "test"

    def test_serialize_empty_state(self):
        """Empty state serializes to empty dict."""
        cp, _, _ = _create_checkpointer()

        result = cp._serialize_state({})
        assert result == {}

    def test_serialize_review_comment_model(self):
        """ReviewComment pydantic model is serialized correctly."""
        cp, _, _ = _create_checkpointer()

        from src.models.events import ReviewComment

        comment = ReviewComment(
            file_path="src/main.py",
            line_number=42,
            message="Fix this",
            severity="error",
        )

        result = cp._serialize_state({"comment": comment})

        assert result["comment"]["_type"] == "pydantic"
        assert result["comment"]["_class"] == "ReviewComment"
        assert result["comment"]["_data"]["file_path"] == "src/main.py"
        assert result["comment"]["_data"]["line_number"] == 42


# ---------------------------------------------------------------------------
# FirestoreCheckpointer._deserialize_state tests
# ---------------------------------------------------------------------------


class TestFirestoreCheckpointerDeserializeState:
    """Tests for _deserialize_state."""

    def test_deserialize_plain_values(self):
        """Plain values pass through unchanged."""
        cp, _, _ = _create_checkpointer()

        data = {
            "str_key": "hello",
            "int_key": 42,
            "list_key": [1, 2],
            "none_key": None,
        }

        result = cp._deserialize_state(data)

        assert result == data

    def test_deserialize_pydantic_pr_event(self):
        """PREvent pydantic model is deserialized correctly."""
        cp, _, _ = _create_checkpointer()

        data = {
            "pr_event": {
                "_type": "pydantic",
                "_class": "PREvent",
                "_data": {
                    "provider": "github",
                    "repo_owner": "org",
                    "repo_name": "repo",
                    "pr_number": 42,
                    "action": "opened",
                    "branch": "feat",
                    "target_branch": "main",
                    "commit_sha": "abc",
                },
            }
        }

        result = cp._deserialize_state(data)

        from src.models.events import PREvent

        assert isinstance(result["pr_event"], PREvent)
        assert result["pr_event"].provider == "github"
        assert result["pr_event"].pr_number == 42

    def test_deserialize_pydantic_review_comment(self):
        """ReviewComment pydantic model is deserialized correctly."""
        cp, _, _ = _create_checkpointer()

        data = {
            "comment": {
                "_type": "pydantic",
                "_class": "ReviewComment",
                "_data": {
                    "file_path": "src/main.py",
                    "line_number": 10,
                    "message": "Issue found",
                    "severity": "warning",
                },
            }
        }

        result = cp._deserialize_state(data)

        from src.models.events import ReviewComment

        assert isinstance(result["comment"], ReviewComment)
        assert result["comment"].file_path == "src/main.py"
        assert result["comment"].line_number == 10

    def test_deserialize_unknown_pydantic_class(self):
        """Unknown pydantic class returns raw _data dict."""
        cp, _, _ = _create_checkpointer()

        data = {
            "unknown": {
                "_type": "pydantic",
                "_class": "UnknownModel",
                "_data": {"key": "value"},
            }
        }

        result = cp._deserialize_state(data)

        assert result["unknown"] == {"key": "value"}

    def test_deserialize_datetime(self):
        """datetime values are deserialized from ISO format."""
        cp, _, _ = _create_checkpointer()

        data = {
            "started_at": {
                "_type": "datetime",
                "_data": "2024-06-15T10:30:00",
            }
        }

        result = cp._deserialize_state(data)

        assert isinstance(result["started_at"], datetime)
        assert result["started_at"] == datetime(2024, 6, 15, 10, 30, 0)

    def test_deserialize_unknown_type(self):
        """Unknown _type values are returned as-is (the whole dict)."""
        cp, _, _ = _create_checkpointer()

        data = {
            "weird": {
                "_type": "unknown_type",
                "_data": "some data",
            }
        }

        result = cp._deserialize_state(data)

        # The whole dict is returned as-is
        assert result["weird"] == {"_type": "unknown_type", "_data": "some data"}

    def test_deserialize_empty_data(self):
        """Empty data returns empty dict."""
        cp, _, _ = _create_checkpointer()

        result = cp._deserialize_state({})
        assert result == {}

    def test_deserialize_dict_without_type_key(self):
        """Regular dicts (without _type key) pass through unchanged."""
        cp, _, _ = _create_checkpointer()

        data = {
            "config": {"max_suggestions": 50, "threshold": "warning"},
        }

        result = cp._deserialize_state(data)

        assert result["config"] == {"max_suggestions": 50, "threshold": "warning"}

    def test_deserialize_mixed_state(self):
        """Mixed state with various types deserializes correctly."""
        cp, _, _ = _create_checkpointer()

        data = {
            "pr_event": {
                "_type": "pydantic",
                "_class": "PREvent",
                "_data": {
                    "provider": "github",
                    "repo_owner": "org",
                    "repo_name": "repo",
                    "pr_number": 1,
                    "action": "opened",
                    "branch": "b",
                    "target_branch": "main",
                    "commit_sha": "s",
                },
            },
            "started_at": {
                "_type": "datetime",
                "_data": "2024-01-01T00:00:00",
            },
            "count": 5,
            "name": "test",
        }

        result = cp._deserialize_state(data)

        from src.models.events import PREvent

        assert isinstance(result["pr_event"], PREvent)
        assert isinstance(result["started_at"], datetime)
        assert result["count"] == 5
        assert result["name"] == "test"


# ---------------------------------------------------------------------------
# Roundtrip serialize/deserialize tests
# ---------------------------------------------------------------------------


class TestFirestoreCheckpointerRoundtrip:
    """Tests for serialize-then-deserialize roundtrips."""

    def test_roundtrip_plain_values(self):
        """Plain values survive a serialize/deserialize roundtrip."""
        cp, _, _ = _create_checkpointer()

        state = {"a": 1, "b": "hello", "c": [1, 2], "d": None}
        serialized = cp._serialize_state(state)
        deserialized = cp._deserialize_state(serialized)

        assert deserialized == state

    def test_roundtrip_datetime(self):
        """datetime values survive a serialize/deserialize roundtrip."""
        cp, _, _ = _create_checkpointer()

        dt = datetime(2024, 6, 15, 10, 30, 0)
        state = {"ts": dt}

        serialized = cp._serialize_state(state)
        deserialized = cp._deserialize_state(serialized)

        assert deserialized["ts"] == dt

    def test_roundtrip_pydantic_pr_event(self):
        """PREvent survives a serialize/deserialize roundtrip."""
        cp, _, _ = _create_checkpointer()

        from src.models.events import PRAction, PREvent

        original = PREvent(
            provider="github",
            repo_owner="org",
            repo_name="repo",
            pr_number=42,
            action=PRAction.OPENED,
            branch="feat",
            target_branch="main",
            commit_sha="abc123",
            pr_title="Test PR",
            author="johndoe",
        )

        state = {"pr_event": original}
        serialized = cp._serialize_state(state)
        deserialized = cp._deserialize_state(serialized)

        recovered = deserialized["pr_event"]
        assert isinstance(recovered, PREvent)
        assert recovered.provider == original.provider
        assert recovered.repo_owner == original.repo_owner
        assert recovered.pr_number == original.pr_number
        assert recovered.pr_title == original.pr_title
        assert recovered.author == original.author

    def test_roundtrip_review_comment(self):
        """ReviewComment survives a serialize/deserialize roundtrip."""
        cp, _, _ = _create_checkpointer()

        from src.models.events import ReviewComment

        original = ReviewComment(
            file_path="src/app.py",
            line_number=99,
            message="Potential issue",
            severity="warning",
            suggestion="Fix it",
        )

        state = {"comment": original}
        serialized = cp._serialize_state(state)
        deserialized = cp._deserialize_state(serialized)

        recovered = deserialized["comment"]
        assert isinstance(recovered, ReviewComment)
        assert recovered.file_path == "src/app.py"
        assert recovered.line_number == 99
        assert recovered.message == "Potential issue"
        assert recovered.suggestion == "Fix it"
