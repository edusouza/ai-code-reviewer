"""Tests for learning.vector_store module."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from learning.vector_store import (
    VectorDocument,
    VertexVectorStore,
    get_vector_store,
    init_vector_store,
)

# ---------------------------------------------------------------------------
# VectorDocument dataclass
# ---------------------------------------------------------------------------


class TestVectorDocument:
    """Tests for the VectorDocument dataclass."""

    def test_create_with_all_fields(self):
        doc = VectorDocument(
            id="doc_1",
            content="print('hello')",
            embedding=[0.1, 0.2, 0.3],
            metadata={"language": "python"},
            score=0.95,
        )
        assert doc.id == "doc_1"
        assert doc.content == "print('hello')"
        assert doc.embedding == [0.1, 0.2, 0.3]
        assert doc.metadata == {"language": "python"}
        assert doc.score == 0.95

    def test_create_with_defaults(self):
        doc = VectorDocument(
            id="doc_2",
            content="some content",
            embedding=None,
            metadata={},
        )
        assert doc.score is None
        assert doc.embedding is None

    def test_create_with_empty_metadata(self):
        doc = VectorDocument(id="x", content="", embedding=None, metadata={})
        assert doc.metadata == {}


# ---------------------------------------------------------------------------
# VertexVectorStore.__init__
# ---------------------------------------------------------------------------


class TestVertexVectorStoreInit:
    """Tests for VertexVectorStore constructor."""

    @patch("learning.vector_store.settings")
    def test_defaults(self, mock_settings):
        mock_settings.project_id = "test-project"
        store = VertexVectorStore()
        assert store.project_id == "test-project"
        assert store.location == "us-central1"
        assert store.index_id is None
        assert store.endpoint_id is None
        assert store.embedding_model == "textembedding-gecko@003"
        assert store._initialized is False
        assert store._index_client is None
        assert store._endpoint_client is None
        assert store._embedding_client is None

    @patch("learning.vector_store.settings")
    def test_custom_params(self, mock_settings):
        mock_settings.project_id = "default-project"
        store = VertexVectorStore(
            project_id="custom-project",
            location="europe-west1",
            index_id="idx-123",
            endpoint_id="ep-456",
            embedding_model="textembedding-gecko@002",
        )
        assert store.project_id == "custom-project"
        assert store.location == "europe-west1"
        assert store.index_id == "idx-123"
        assert store.endpoint_id == "ep-456"
        assert store.embedding_model == "textembedding-gecko@002"

    @patch("learning.vector_store.settings")
    def test_project_id_falls_back_to_settings(self, mock_settings):
        mock_settings.project_id = "settings-project"
        store = VertexVectorStore(project_id=None)
        assert store.project_id == "settings-project"


# ---------------------------------------------------------------------------
# VertexVectorStore.initialize
# ---------------------------------------------------------------------------


class TestVertexVectorStoreInitialize:
    """Tests for the lazy initialization method."""

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore()
        store._initialized = True
        # Should return immediately without doing anything
        await store.initialize()
        assert store._initialized is True

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_initialize_success_without_index(self, mock_settings):
        import sys

        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")

        mock_aiplatform_init = MagicMock()
        mock_embedding_cls = MagicMock()
        mock_embedding_instance = MagicMock()
        mock_embedding_cls.from_pretrained.return_value = mock_embedding_instance

        # Build mock module hierarchy for google.cloud.aiplatform
        mock_gca = MagicMock()
        mock_gca.init = mock_aiplatform_init

        # Build mock module for vertexai.language_models
        mock_vlm = MagicMock()
        mock_vlm.TextEmbeddingModel = mock_embedding_cls

        modules_patch = {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.aiplatform": mock_gca,
            "vertexai": MagicMock(),
            "vertexai.language_models": mock_vlm,
        }

        with patch.dict(sys.modules, modules_patch):
            await store.initialize()

        assert store._initialized is True
        assert store._embedding_client is mock_embedding_instance

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_initialize_with_index_and_endpoint(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1", endpoint_id="ep-1")

        mock_aiplatform_init = MagicMock()
        mock_embedding_cls = MagicMock()
        mock_embedding_instance = MagicMock()
        mock_embedding_cls.from_pretrained.return_value = mock_embedding_instance

        mock_index_cls = MagicMock()
        mock_index_instance = MagicMock()
        mock_index_cls.return_value = mock_index_instance

        mock_endpoint_cls = MagicMock()
        mock_endpoint_instance = MagicMock()
        mock_endpoint_cls.return_value = mock_endpoint_instance

        with (
            patch("google.cloud.aiplatform.init", mock_aiplatform_init, create=True),
            patch(
                "vertexai.language_models.TextEmbeddingModel",
                mock_embedding_cls,
                create=True,
            ),
            patch(
                "google.cloud.aiplatform.matching_engine.MatchingEngineIndex",
                mock_index_cls,
                create=True,
            ),
            patch(
                "google.cloud.aiplatform.matching_engine.MatchingEngineIndexEndpoint",
                mock_endpoint_cls,
                create=True,
            ),
        ):
            await store.initialize()

        assert store._initialized is True
        assert store._embedding_client is mock_embedding_instance
        assert store._index_client is mock_index_instance
        assert store._endpoint_client is mock_endpoint_instance

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_initialize_with_index_but_no_endpoint(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1", endpoint_id=None)

        mock_aiplatform_init = MagicMock()
        mock_embedding_cls = MagicMock()
        mock_embedding_cls.from_pretrained.return_value = MagicMock()
        mock_index_cls = MagicMock()
        mock_index_cls.return_value = MagicMock()

        with (
            patch("google.cloud.aiplatform.init", mock_aiplatform_init, create=True),
            patch(
                "vertexai.language_models.TextEmbeddingModel",
                mock_embedding_cls,
                create=True,
            ),
            patch(
                "google.cloud.aiplatform.matching_engine.MatchingEngineIndex",
                mock_index_cls,
                create=True,
            ),
            patch(
                "google.cloud.aiplatform.matching_engine.MatchingEngineIndexEndpoint",
                MagicMock(),
                create=True,
            ),
        ):
            await store.initialize()

        assert store._initialized is True
        assert store._endpoint_client is None

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_initialize_import_error(self, mock_settings):
        """ImportError should be caught gracefully."""
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")

        with patch(
            "builtins.__import__",
            side_effect=ImportError("no module google"),
        ):
            await store.initialize()

        assert store._initialized is False

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_initialize_generic_error(self, mock_settings):
        """Generic exceptions should be caught gracefully."""
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")

        with patch(
            "builtins.__import__",
            side_effect=RuntimeError("unexpected"),
        ):
            await store.initialize()

        assert store._initialized is False


# ---------------------------------------------------------------------------
# VertexVectorStore.generate_embedding
# ---------------------------------------------------------------------------


class TestGenerateEmbedding:
    """Tests for generate_embedding."""

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_no_embedding_client_returns_dummy(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        store._embedding_client = None

        result = await store.generate_embedding("some text")
        assert result == [0.0] * 768

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_successful_embedding(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True

        mock_emb_result = MagicMock()
        mock_emb_result.values = [0.1, 0.2, 0.3]
        mock_client = MagicMock()
        mock_client.get_embeddings.return_value = [mock_emb_result]
        store._embedding_client = mock_client

        result = await store.generate_embedding("test text")
        assert result == [0.1, 0.2, 0.3]
        mock_client.get_embeddings.assert_called_once_with(["test text"])

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_truncates_long_text(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True

        mock_emb_result = MagicMock()
        mock_emb_result.values = [1.0]
        mock_client = MagicMock()
        mock_client.get_embeddings.return_value = [mock_emb_result]
        store._embedding_client = mock_client

        long_text = "x" * 20000
        result = await store.generate_embedding(long_text)
        # Should truncate to 10000 chars
        call_args = mock_client.get_embeddings.call_args[0][0]
        assert len(call_args[0]) == 10000
        assert result == [1.0]

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_empty_embeddings_returned(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True

        mock_client = MagicMock()
        mock_client.get_embeddings.return_value = []
        store._embedding_client = mock_client

        result = await store.generate_embedding("test")
        assert result == [0.0] * 768

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_none_embeddings_returned(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True

        mock_client = MagicMock()
        mock_client.get_embeddings.return_value = None
        store._embedding_client = mock_client

        result = await store.generate_embedding("test")
        assert result == [0.0] * 768

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_exception_returns_dummy(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True

        mock_client = MagicMock()
        mock_client.get_embeddings.side_effect = RuntimeError("API error")
        store._embedding_client = mock_client

        result = await store.generate_embedding("test")
        assert result == [0.0] * 768

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_calls_initialize(self, mock_settings):
        """generate_embedding should call initialize() first."""
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = False
        store._embedding_client = None

        with patch.object(store, "initialize", new_callable=AsyncMock) as mock_init:
            result = await store.generate_embedding("text")
            mock_init.assert_awaited_once()

        assert result == [0.0] * 768


# ---------------------------------------------------------------------------
# VertexVectorStore.add_documents
# ---------------------------------------------------------------------------


class TestAddDocuments:
    """Tests for add_documents."""

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_no_index_client(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        store._index_client = None

        result = await store.add_documents([])
        assert result is False

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_adds_documents_successfully(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        store._index_client = MagicMock()

        doc1 = VectorDocument(
            id="d1",
            content="code1",
            embedding=[0.1, 0.2],
            metadata={"type": "good_practice", "language": "python"},
        )
        doc2 = VectorDocument(
            id="d2",
            content="code2",
            embedding=None,
            metadata={"type": "anti_pattern", "language": "java"},
        )

        with patch.object(
            store, "generate_embedding", new_callable=AsyncMock, return_value=[0.5, 0.6]
        ):
            result = await store.add_documents([doc1, doc2])

        assert result is True
        # doc1 already had embedding, doc2 should have gotten one
        assert doc1.embedding == [0.1, 0.2]
        assert doc2.embedding == [0.5, 0.6]

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_add_documents_exception(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        store._index_client = MagicMock()

        doc = VectorDocument(
            id="d1",
            content="code",
            embedding=None,  # None so generate_embedding is called
            metadata={"type": "x", "language": "py"},
        )

        with patch.object(
            store,
            "generate_embedding",
            new_callable=AsyncMock,
            side_effect=RuntimeError("embed fail"),
        ):
            result = await store.add_documents([doc])

        assert result is False

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_add_documents_with_missing_metadata_keys(self, mock_settings):
        """Metadata may not have 'type' or 'language' keys."""
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        store._index_client = MagicMock()

        doc = VectorDocument(
            id="d1",
            content="code",
            embedding=[0.1],
            metadata={},
        )

        result = await store.add_documents([doc])
        assert result is True

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_add_documents_calls_initialize(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = False
        store._index_client = None

        with patch.object(store, "initialize", new_callable=AsyncMock) as mock_init:
            result = await store.add_documents([])
            mock_init.assert_awaited_once()

        assert result is False


# ---------------------------------------------------------------------------
# VertexVectorStore.search
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for search."""

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_no_endpoint_client(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        store._endpoint_client = None

        result = await store.search("query")
        assert result == []

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_search_success(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1")
        store._initialized = True

        neighbor = MagicMock()
        neighbor.id = "n1"
        neighbor.metadata = {"content": "some code", "language": "python"}
        neighbor.distance = 0.85

        mock_endpoint = MagicMock()
        mock_endpoint.find_neighbors.return_value = [[neighbor]]
        store._endpoint_client = mock_endpoint

        with patch.object(
            store, "generate_embedding", new_callable=AsyncMock, return_value=[0.1, 0.2]
        ):
            results = await store.search("test query", top_k=3)

        assert len(results) == 1
        assert results[0].id == "n1"
        assert results[0].score == 0.85
        assert results[0].content == "some code"

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_search_with_filters(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1")
        store._initialized = True

        mock_endpoint = MagicMock()
        mock_endpoint.find_neighbors.return_value = [[]]
        store._endpoint_client = mock_endpoint

        with patch.object(store, "generate_embedding", new_callable=AsyncMock, return_value=[0.1]):
            await store.search(
                "query",
                filter_type="good_practice",
                filter_language="python",
            )

        call_kwargs = mock_endpoint.find_neighbors.call_args[1]
        assert call_kwargs["filter"] is not None
        filters = call_kwargs["filter"]
        assert len(filters) == 2
        assert filters[0]["namespace"] == "type"
        assert filters[0]["allow_list"] == ["good_practice"]
        assert filters[1]["namespace"] == "language"
        assert filters[1]["allow_list"] == ["python"]

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_search_no_filters(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1")
        store._initialized = True

        mock_endpoint = MagicMock()
        mock_endpoint.find_neighbors.return_value = [[]]
        store._endpoint_client = mock_endpoint

        with patch.object(store, "generate_embedding", new_callable=AsyncMock, return_value=[0.1]):
            await store.search("query")

        call_kwargs = mock_endpoint.find_neighbors.call_args[1]
        assert call_kwargs["filter"] is None

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_search_with_only_type_filter(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1")
        store._initialized = True

        mock_endpoint = MagicMock()
        mock_endpoint.find_neighbors.return_value = [[]]
        store._endpoint_client = mock_endpoint

        with patch.object(store, "generate_embedding", new_callable=AsyncMock, return_value=[0.1]):
            await store.search("q", filter_type="idiom")

        call_kwargs = mock_endpoint.find_neighbors.call_args[1]
        filters = call_kwargs["filter"]
        assert len(filters) == 1
        assert filters[0]["namespace"] == "type"

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_search_with_only_language_filter(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1")
        store._initialized = True

        mock_endpoint = MagicMock()
        mock_endpoint.find_neighbors.return_value = [[]]
        store._endpoint_client = mock_endpoint

        with patch.object(store, "generate_embedding", new_callable=AsyncMock, return_value=[0.1]):
            await store.search("q", filter_language="rust")

        call_kwargs = mock_endpoint.find_neighbors.call_args[1]
        filters = call_kwargs["filter"]
        assert len(filters) == 1
        assert filters[0]["namespace"] == "language"

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_search_empty_results(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1")
        store._initialized = True

        mock_endpoint = MagicMock()
        mock_endpoint.find_neighbors.return_value = []
        store._endpoint_client = mock_endpoint

        with patch.object(store, "generate_embedding", new_callable=AsyncMock, return_value=[0.1]):
            results = await store.search("query")

        assert results == []

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_search_exception(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1")
        store._initialized = True

        mock_endpoint = MagicMock()
        mock_endpoint.find_neighbors.side_effect = RuntimeError("search fail")
        store._endpoint_client = mock_endpoint

        with patch.object(store, "generate_embedding", new_callable=AsyncMock, return_value=[0.1]):
            results = await store.search("query")

        assert results == []

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_search_multiple_neighbors(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p", index_id="idx-1")
        store._initialized = True

        n1 = MagicMock()
        n1.id = "n1"
        n1.metadata = {"content": "c1"}
        n1.distance = 0.9

        n2 = MagicMock()
        n2.id = "n2"
        n2.metadata = {"content": "c2"}
        n2.distance = 0.7

        mock_endpoint = MagicMock()
        mock_endpoint.find_neighbors.return_value = [[n1, n2]]
        store._endpoint_client = mock_endpoint

        with patch.object(store, "generate_embedding", new_callable=AsyncMock, return_value=[0.1]):
            results = await store.search("query", top_k=5)

        assert len(results) == 2
        assert results[0].id == "n1"
        assert results[1].id == "n2"


# ---------------------------------------------------------------------------
# VertexVectorStore.delete_documents
# ---------------------------------------------------------------------------


class TestDeleteDocuments:
    """Tests for delete_documents."""

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_no_index_client(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        store._index_client = None

        result = await store.delete_documents(["id1"])
        assert result is False

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        mock_index = MagicMock()
        store._index_client = mock_index

        result = await store.delete_documents(["id1", "id2"])
        assert result is True
        mock_index.remove_datapoints.assert_called_once_with(datapoint_ids=["id1", "id2"])

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_delete_exception(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True
        mock_index = MagicMock()
        mock_index.remove_datapoints.side_effect = RuntimeError("fail")
        store._index_client = mock_index

        result = await store.delete_documents(["id1"])
        assert result is False

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_delete_calls_initialize(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = False
        store._index_client = None

        with patch.object(store, "initialize", new_callable=AsyncMock) as mock_init:
            result = await store.delete_documents(["id1"])
            mock_init.assert_awaited_once()

        assert result is False


# ---------------------------------------------------------------------------
# VertexVectorStore.get_document
# ---------------------------------------------------------------------------


class TestGetDocument:
    """Tests for get_document."""

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_returns_none(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True

        result = await store.get_document("some-id")
        assert result is None

    @patch("learning.vector_store.settings")
    @pytest.mark.asyncio
    async def test_returns_none_with_namespace(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        store._initialized = True

        result = await store.get_document("some-id", namespace="custom")
        assert result is None


# ---------------------------------------------------------------------------
# VertexVectorStore.generate_document_id
# ---------------------------------------------------------------------------


class TestGenerateDocumentId:
    """Tests for generate_document_id."""

    @patch("learning.vector_store.settings")
    def test_deterministic(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        id1 = store.generate_document_id("content", {"language": "python", "type": "idiom"})
        id2 = store.generate_document_id("content", {"language": "python", "type": "idiom"})
        assert id1 == id2

    @patch("learning.vector_store.settings")
    def test_different_content_different_id(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        id1 = store.generate_document_id("content_a", {"language": "python"})
        id2 = store.generate_document_id("content_b", {"language": "python"})
        assert id1 != id2

    @patch("learning.vector_store.settings")
    def test_different_language_different_id(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        id1 = store.generate_document_id("code", {"language": "python"})
        id2 = store.generate_document_id("code", {"language": "java"})
        assert id1 != id2

    @patch("learning.vector_store.settings")
    def test_format(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        doc_id = store.generate_document_id("content", {"language": "py", "type": "t"})
        assert doc_id.startswith("doc_")
        # md5 hex[:16]
        assert len(doc_id) == 4 + 16  # "doc_" + 16 hex chars

    @patch("learning.vector_store.settings")
    def test_missing_metadata_keys(self, mock_settings):
        mock_settings.project_id = "p"
        store = VertexVectorStore(project_id="p")
        doc_id = store.generate_document_id("content", {})
        expected_hash_input = "content::"
        expected = f"doc_{hashlib.md5(expected_hash_input.encode()).hexdigest()[:16]}"
        assert doc_id == expected


# ---------------------------------------------------------------------------
# Module-level functions: init_vector_store / get_vector_store
# ---------------------------------------------------------------------------


class TestModuleLevelFunctions:
    """Tests for init_vector_store and get_vector_store."""

    @patch("learning.vector_store.settings")
    def test_init_vector_store(self, mock_settings):
        mock_settings.project_id = "p"

        import learning.vector_store as vs_mod

        old_store = vs_mod._vector_store
        try:
            store = init_vector_store(project_id="test-proj", index_id="idx-1", endpoint_id="ep-1")
            assert isinstance(store, VertexVectorStore)
            assert store.project_id == "test-proj"
            assert store.index_id == "idx-1"
            assert store.endpoint_id == "ep-1"

            assert get_vector_store() is store
        finally:
            vs_mod._vector_store = old_store

    @patch("learning.vector_store.settings")
    def test_get_vector_store_returns_none_initially(self, mock_settings):
        mock_settings.project_id = "p"

        import learning.vector_store as vs_mod

        old_store = vs_mod._vector_store
        try:
            vs_mod._vector_store = None
            assert get_vector_store() is None
        finally:
            vs_mod._vector_store = old_store

    @patch("learning.vector_store.settings")
    def test_init_vector_store_default_params(self, mock_settings):
        mock_settings.project_id = "default-proj"

        import learning.vector_store as vs_mod

        old_store = vs_mod._vector_store
        try:
            store = init_vector_store()
            assert store.project_id == "default-proj"
            assert store.index_id is None
            assert store.endpoint_id is None
        finally:
            vs_mod._vector_store = old_store
