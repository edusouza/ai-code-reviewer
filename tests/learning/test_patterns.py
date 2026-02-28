"""Tests for learning.patterns module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from learning.patterns import (
    CodePattern,
    PatternExtractor,
    PatternManager,
    PatternRetriever,
    PatternType,
    get_pattern_manager,
    init_pattern_manager,
)
from learning.vector_store import VectorDocument

# ---------------------------------------------------------------------------
# PatternType enum
# ---------------------------------------------------------------------------


class TestPatternType:
    """Tests for PatternType enum values."""

    def test_all_values(self):
        assert PatternType.GOOD_PRACTICE.value == "good_practice"
        assert PatternType.ANTI_PATTERN.value == "anti_pattern"
        assert PatternType.DESIGN_PATTERN.value == "design_pattern"
        assert PatternType.IDIOM.value == "idiom"
        assert PatternType.BEST_PRACTICE.value == "best_practice"
        assert PatternType.SECURITY_PATTERN.value == "security_pattern"
        assert PatternType.PERFORMANCE_PATTERN.value == "performance_pattern"

    def test_from_value(self):
        assert PatternType("good_practice") is PatternType.GOOD_PRACTICE
        assert PatternType("anti_pattern") is PatternType.ANTI_PATTERN

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            PatternType("nonexistent")


# ---------------------------------------------------------------------------
# CodePattern dataclass
# ---------------------------------------------------------------------------


class TestCodePattern:
    """Tests for CodePattern dataclass."""

    def test_create_full(self):
        p = CodePattern(
            id="pat_123",
            name="Dependency Injection",
            description="Use DI for loose coupling",
            pattern_type=PatternType.DESIGN_PATTERN,
            language="python",
            code_example="class Service:\n    def __init__(self, repo): ...",
            counter_example="class Service:\n    repo = Repository()",
            rationale="Improves testability",
            tags=["python", "design_pattern"],
            source_file="src/service.py",
            confidence=0.9,
            metadata={"extracted_at": "2024-01-01"},
        )
        assert p.id == "pat_123"
        assert p.name == "Dependency Injection"
        assert p.pattern_type is PatternType.DESIGN_PATTERN
        assert p.counter_example is not None
        assert p.confidence == 0.9

    def test_create_minimal(self):
        p = CodePattern(
            id="pat_0",
            name="N",
            description="D",
            pattern_type=PatternType.GOOD_PRACTICE,
            language="python",
            code_example="",
            counter_example=None,
            rationale="",
            tags=[],
            source_file=None,
            confidence=0.0,
            metadata={},
        )
        assert p.counter_example is None
        assert p.source_file is None
        assert p.tags == []


# ---------------------------------------------------------------------------
# PatternExtractor
# ---------------------------------------------------------------------------


class TestPatternExtractor:
    """Tests for PatternExtractor."""

    def test_init_with_client(self):
        client = Mock()
        extractor = PatternExtractor(llm_client=client)
        assert extractor.llm_client is client

    def test_init_without_client(self):
        extractor = PatternExtractor()
        assert extractor.llm_client is None

    # --- extract_patterns_from_file ---

    @pytest.mark.asyncio
    async def test_extract_from_file_no_llm_client(self):
        extractor = PatternExtractor(llm_client=None)
        result = await extractor.extract_patterns_from_file("src/main.py", "code", "python")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_from_file_success(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "patterns": [
                    {
                        "name": "Context Manager",
                        "type": "idiom",
                        "description": "Uses context managers for resource management",
                        "code_example": "with open('f') as f: ...",
                        "rationale": "Ensures cleanup",
                    },
                    {
                        "name": "Type Hints",
                        "type": "good_practice",
                        "description": "Uses type hints",
                        "code_example": "def foo(x: int) -> str: ...",
                        "rationale": "Improves readability",
                    },
                ]
            }
        )
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_file(
            "src/util.py", "def foo(x: int) -> str:\n    ...", "python"
        )

        assert len(result) == 2
        assert result[0].name == "Context Manager"
        assert result[0].pattern_type is PatternType.IDIOM
        assert result[0].language == "python"
        assert result[0].source_file == "src/util.py"
        assert result[0].confidence == 0.8
        assert "python" in result[0].tags
        assert "idiom" in result[0].tags
        assert result[0].counter_example is None
        assert result[0].metadata == {"extracted_at": "timestamp"}

        assert result[1].name == "Type Hints"
        assert result[1].pattern_type is PatternType.GOOD_PRACTICE

    @pytest.mark.asyncio
    async def test_extract_from_file_pattern_id_generation(self):
        """IDs should be deterministic based on file_path + name."""
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "patterns": [
                    {
                        "name": "TestPattern",
                        "type": "good_practice",
                        "description": "d",
                        "code_example": "c",
                        "rationale": "r",
                    }
                ]
            }
        )
        extractor = PatternExtractor(llm_client=mock_llm)

        result = await extractor.extract_patterns_from_file("path.py", "code", "py")
        expected_id = f"pat_{hash('path.py' + 'TestPattern') & 0xFFFFFF}"
        assert result[0].id == expected_id

    @pytest.mark.asyncio
    async def test_extract_from_file_default_type(self):
        """When type is missing, default to 'good_practice'."""
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "patterns": [
                    {
                        "name": "NoType",
                        "description": "d",
                        "code_example": "c",
                        "rationale": "r",
                    }
                ]
            }
        )
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_file("f.py", "code", "py")
        assert result[0].pattern_type is PatternType.GOOD_PRACTICE
        # tags should use "general" when type is missing
        assert "general" in result[0].tags

    @pytest.mark.asyncio
    async def test_extract_from_file_empty_patterns(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(return_value={"patterns": []})
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_file("f.py", "code", "py")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_from_file_no_patterns_key(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(return_value={})
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_file("f.py", "code", "py")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_from_file_llm_exception(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(side_effect=RuntimeError("LLM fail"))
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_file("f.py", "code", "py")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_from_file_truncates_content(self):
        """File content should be truncated to 8000 chars in prompt."""
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(return_value={"patterns": []})
        extractor = PatternExtractor(llm_client=mock_llm)

        long_content = "x" * 20000
        await extractor.extract_patterns_from_file("f.py", long_content, "python")

        # Check the prompt passed to generate_json
        call_kwargs = mock_llm.generate_json.call_args[1]
        prompt = call_kwargs["prompt"]
        # The truncated content should appear in the prompt
        assert "x" * 8000 in prompt
        assert "x" * 8001 not in prompt

    @pytest.mark.asyncio
    async def test_extract_from_file_with_context(self):
        """Context param is accepted but currently not used in prompt."""
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(return_value={"patterns": []})
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_file(
            "f.py", "code", "py", context="extra context"
        )
        assert result == []

    # --- extract_patterns_from_review_feedback ---

    @pytest.mark.asyncio
    async def test_extract_from_feedback_no_llm_client(self):
        extractor = PatternExtractor(llm_client=None)
        result = await extractor.extract_patterns_from_review_feedback([], "feedback", "python")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_from_feedback_success(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "patterns": [
                    {
                        "name": "Input Validation",
                        "type": "good_practice",
                        "description": "Always validate inputs",
                        "code_example": "if not data: raise ValueError",
                        "counter_example": "def f(data): return data",
                        "rationale": "Prevents invalid state",
                    }
                ]
            }
        )
        extractor = PatternExtractor(llm_client=mock_llm)

        changes = [
            {"file_path": "src/handler.py", "content": "def handle(data): ..."},
            {"file_path": "src/model.py", "content": "class User: ..."},
        ]
        result = await extractor.extract_patterns_from_review_feedback(
            changes, "Great input validation!", "python"
        )

        assert len(result) == 1
        p = result[0]
        assert p.name == "Input Validation"
        assert p.pattern_type is PatternType.GOOD_PRACTICE
        assert p.counter_example == "def f(data): return data"
        assert p.confidence == 0.7
        assert p.source_file is None
        assert "from_feedback" in p.tags
        assert p.metadata == {"extracted_from": "feedback"}

    @pytest.mark.asyncio
    async def test_extract_from_feedback_id_generation(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "patterns": [
                    {
                        "name": "Test",
                        "type": "anti_pattern",
                        "description": "d",
                        "code_example": "c",
                        "rationale": "r",
                    }
                ]
            }
        )
        extractor = PatternExtractor(llm_client=mock_llm)
        feedback = "A" * 200  # Test truncation in id hash
        result = await extractor.extract_patterns_from_review_feedback([], feedback, "py")
        expected_id = f"pat_fb_{hash(feedback[:100] + 'Test') & 0xFFFFFF}"
        assert result[0].id == expected_id

    @pytest.mark.asyncio
    async def test_extract_from_feedback_anti_pattern(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "patterns": [
                    {
                        "name": "Catch-all Exception",
                        "type": "anti_pattern",
                        "description": "Avoid bare except",
                        "code_example": "try: ... except Exception as e: ...",
                        "counter_example": "try: ... except: ...",
                        "rationale": "Loses error info",
                    }
                ]
            }
        )
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_review_feedback([], "feedback", "python")
        assert result[0].pattern_type is PatternType.ANTI_PATTERN
        assert result[0].counter_example == "try: ... except: ..."

    @pytest.mark.asyncio
    async def test_extract_from_feedback_no_counter_example(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "patterns": [
                    {
                        "name": "P",
                        "description": "d",
                        "code_example": "c",
                        "rationale": "r",
                    }
                ]
            }
        )
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_review_feedback([], "fb", "py")
        assert result[0].counter_example is None

    @pytest.mark.asyncio
    async def test_extract_from_feedback_exception(self):
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(side_effect=ValueError("bad json"))
        extractor = PatternExtractor(llm_client=mock_llm)
        result = await extractor.extract_patterns_from_review_feedback([], "fb", "py")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_from_feedback_limits_changes(self):
        """Only first 5 changes are included and each truncated to 2000 chars."""
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(return_value={"patterns": []})
        extractor = PatternExtractor(llm_client=mock_llm)

        changes = [{"file_path": f"file_{i}.py", "content": "x" * 3000} for i in range(10)]
        await extractor.extract_patterns_from_review_feedback(changes, "feedback", "python")

        call_kwargs = mock_llm.generate_json.call_args[1]
        prompt = call_kwargs["prompt"]
        # Only 5 files should appear
        assert "file_0.py" in prompt
        assert "file_4.py" in prompt
        assert "file_5.py" not in prompt

    @pytest.mark.asyncio
    async def test_extract_from_feedback_missing_file_path(self):
        """Changes without file_path should use 'unknown'."""
        mock_llm = Mock()
        mock_llm.generate_json = AsyncMock(return_value={"patterns": []})
        extractor = PatternExtractor(llm_client=mock_llm)

        changes = [{"content": "code"}]
        await extractor.extract_patterns_from_review_feedback(changes, "feedback", "python")

        call_kwargs = mock_llm.generate_json.call_args[1]
        prompt = call_kwargs["prompt"]
        assert "unknown" in prompt


# ---------------------------------------------------------------------------
# PatternRetriever
# ---------------------------------------------------------------------------


class TestPatternRetriever:
    """Tests for PatternRetriever."""

    def test_init_with_store(self):
        store = Mock()
        retriever = PatternRetriever(vector_store=store)
        assert retriever.vector_store is store

    @patch("learning.patterns.get_vector_store", return_value=None)
    def test_init_without_store(self, mock_get):
        retriever = PatternRetriever()
        assert retriever.vector_store is None

    @patch("learning.patterns.get_vector_store")
    def test_init_default_store(self, mock_get):
        mock_store = Mock()
        mock_get.return_value = mock_store
        retriever = PatternRetriever()
        assert retriever.vector_store is mock_store

    # --- find_relevant_patterns ---

    @pytest.mark.asyncio
    async def test_find_relevant_no_store(self):
        retriever = PatternRetriever(vector_store=None)
        result = await retriever.find_relevant_patterns("code", "python")
        assert result == []

    @pytest.mark.asyncio
    async def test_find_relevant_success(self):
        doc = VectorDocument(
            id="p1",
            content="example code",
            embedding=None,
            metadata={
                "name": "Pattern A",
                "description": "Good pattern",
                "type": "good_practice",
                "language": "python",
                "rationale": "Because reasons",
                "tags": ["python"],
                "source_file": "src/a.py",
                "confidence": 0.9,
            },
            score=0.88,
        )
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[doc])

        retriever = PatternRetriever(vector_store=mock_store)
        result = await retriever.find_relevant_patterns("def foo(): pass", "python")

        assert len(result) == 1
        assert result[0].id == "p1"
        assert result[0].name == "Pattern A"
        assert result[0].pattern_type is PatternType.GOOD_PRACTICE
        assert result[0].confidence == 0.88

    @pytest.mark.asyncio
    async def test_find_relevant_with_pattern_type_filter(self):
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[])

        retriever = PatternRetriever(vector_store=mock_store)
        await retriever.find_relevant_patterns(
            "code",
            "python",
            pattern_types=[PatternType.SECURITY_PATTERN],
            top_k=3,
        )

        call_kwargs = mock_store.search.call_args[1]
        assert call_kwargs["filter_type"] == "security_pattern"
        assert call_kwargs["top_k"] == 3
        assert call_kwargs["filter_language"] == "python"

    @pytest.mark.asyncio
    async def test_find_relevant_no_pattern_type_filter(self):
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[])

        retriever = PatternRetriever(vector_store=mock_store)
        await retriever.find_relevant_patterns("code", "python")

        call_kwargs = mock_store.search.call_args[1]
        assert call_kwargs["filter_type"] is None

    @pytest.mark.asyncio
    async def test_find_relevant_exception(self):
        mock_store = Mock()
        mock_store.search = AsyncMock(side_effect=RuntimeError("fail"))

        retriever = PatternRetriever(vector_store=mock_store)
        result = await retriever.find_relevant_patterns("code", "python")
        assert result == []

    @pytest.mark.asyncio
    async def test_find_relevant_invalid_document(self):
        """If _document_to_pattern returns None, it should be filtered out."""
        doc = VectorDocument(
            id="bad",
            content="c",
            embedding=None,
            metadata={"type": "nonexistent_type"},
            score=0.5,
        )
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[doc])

        retriever = PatternRetriever(vector_store=mock_store)
        result = await retriever.find_relevant_patterns("code", "python")
        # The invalid type should cause _document_to_pattern to return None
        assert result == []

    @pytest.mark.asyncio
    async def test_find_relevant_multiple_docs(self):
        doc1 = VectorDocument(
            id="p1",
            content="c1",
            embedding=None,
            metadata={
                "name": "A",
                "description": "d",
                "type": "good_practice",
                "language": "py",
                "rationale": "r",
            },
            score=0.9,
        )
        doc2 = VectorDocument(
            id="p2",
            content="c2",
            embedding=None,
            metadata={
                "name": "B",
                "description": "d2",
                "type": "idiom",
                "language": "py",
                "rationale": "r2",
            },
            score=0.7,
        )
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[doc1, doc2])

        retriever = PatternRetriever(vector_store=mock_store)
        result = await retriever.find_relevant_patterns("code", "py", top_k=10)
        assert len(result) == 2
        assert result[0].name == "A"
        assert result[1].name == "B"

    # --- find_patterns_for_suggestion ---

    @pytest.mark.asyncio
    async def test_find_for_suggestion_no_store(self):
        retriever = PatternRetriever(vector_store=None)
        result = await retriever.find_patterns_for_suggestion(
            "file.py", 10, "null pointer", "python"
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_find_for_suggestion_success(self):
        doc = VectorDocument(
            id="s1",
            content="validate input",
            embedding=None,
            metadata={
                "name": "Input Validation",
                "description": "Validate all inputs",
                "type": "good_practice",
                "language": "python",
                "rationale": "Prevents errors",
            },
            score=0.85,
        )
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[doc])

        retriever = PatternRetriever(vector_store=mock_store)
        result = await retriever.find_patterns_for_suggestion(
            "src/handler.py", 42, "Missing input validation", "python"
        )

        assert len(result) == 1
        assert result[0].name == "Input Validation"
        mock_store.search.assert_awaited_once_with(
            query="Missing input validation", top_k=3, filter_language="python"
        )

    @pytest.mark.asyncio
    async def test_find_for_suggestion_exception(self):
        mock_store = Mock()
        mock_store.search = AsyncMock(side_effect=RuntimeError("fail"))

        retriever = PatternRetriever(vector_store=mock_store)
        result = await retriever.find_patterns_for_suggestion("f.py", 1, "issue", "python")
        assert result == []

    @pytest.mark.asyncio
    async def test_find_for_suggestion_filters_invalid(self):
        doc = VectorDocument(
            id="bad",
            content="c",
            embedding=None,
            metadata={"type": "INVALID"},
            score=0.5,
        )
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[doc])

        retriever = PatternRetriever(vector_store=mock_store)
        result = await retriever.find_patterns_for_suggestion("f.py", 1, "issue", "py")
        assert result == []

    # --- get_common_patterns ---

    @pytest.mark.asyncio
    async def test_get_common_patterns_returns_empty(self):
        retriever = PatternRetriever(vector_store=Mock())
        result = await retriever.get_common_patterns("python")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_common_patterns_with_type_filter(self):
        retriever = PatternRetriever(vector_store=Mock())
        result = await retriever.get_common_patterns(
            "python", pattern_type=PatternType.IDIOM, limit=5
        )
        assert result == []

    # --- _create_search_query ---

    def test_create_search_query_basic(self):
        retriever = PatternRetriever(vector_store=Mock())
        query = retriever._create_search_query("x = 1", "python")
        assert "python" in query

    def test_create_search_query_with_function(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "def my_function(x):\n    return x + 1"
        query = retriever._create_search_query(code, "python")
        assert "python" in query
        assert "my_function" in query
        assert "function" in query

    def test_create_search_query_with_class(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "class MyClass:\n    pass"
        query = retriever._create_search_query(code, "python")
        assert "MyClass" in query
        assert "class" in query

    def test_create_search_query_with_loop(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "for i in range(10):\n    print(i)"
        query = retriever._create_search_query(code, "python")
        assert "loop" in query

    def test_create_search_query_with_while_loop(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "while True:\n    break"
        query = retriever._create_search_query(code, "python")
        assert "loop" in query

    def test_create_search_query_with_conditional(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "if x > 0:\n    return True"
        query = retriever._create_search_query(code, "python")
        assert "conditional" in query

    def test_create_search_query_strips_strings(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "x = \"hello world\"\ny = 'foo'"
        query = retriever._create_search_query(code, "python")
        # Strings should be replaced with "..."
        assert "hello world" not in query
        assert "foo" not in query

    def test_create_search_query_strips_comments(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "x = 1  # this is a comment\ny = 2"
        query = retriever._create_search_query(code, "python")
        assert "comment" not in query

    def test_create_search_query_limits_identifiers(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "def a():\n  pass\ndef b():\n  pass\ndef c():\n  pass\ndef d():\n  pass"
        query = retriever._create_search_query(code, "python")
        # Should only include top 3 identifiers
        parts = query.split()
        # Count how many of a, b, c, d appear
        id_count = sum(1 for p in parts if p in ("a", "b", "c", "d"))
        assert id_count <= 3

    def test_create_search_query_js_function(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = "function fetchData() {\n    return fetch(url);\n}"
        query = retriever._create_search_query(code, "javascript")
        assert "javascript" in query
        assert "fetchData" in query

    def test_create_search_query_all_structures(self):
        retriever = PatternRetriever(vector_store=Mock())
        code = (
            "class Foo:\n"
            "    def bar(self):\n"
            "        for i in range(10):\n"
            "            if i > 5:\n"
            "                pass\n"
        )
        query = retriever._create_search_query(code, "python")
        assert "python" in query
        assert "Foo" in query
        assert "bar" in query
        assert "function" in query
        assert "class" in query
        assert "loop" in query
        assert "conditional" in query

    # --- _document_to_pattern ---

    def test_document_to_pattern_success(self):
        retriever = PatternRetriever(vector_store=Mock())
        doc = VectorDocument(
            id="doc1",
            content="example code",
            embedding=None,
            metadata={
                "name": "My Pattern",
                "description": "A good pattern",
                "type": "good_practice",
                "language": "python",
                "rationale": "because",
                "tags": ["python", "good"],
                "source_file": "src/a.py",
                "counter_example": "bad code",
            },
            score=0.92,
        )
        pattern = retriever._document_to_pattern(doc)
        assert pattern is not None
        assert pattern.id == "doc1"
        assert pattern.name == "My Pattern"
        assert pattern.description == "A good pattern"
        assert pattern.pattern_type is PatternType.GOOD_PRACTICE
        assert pattern.language == "python"
        assert pattern.code_example == "example code"
        assert pattern.counter_example == "bad code"
        assert pattern.rationale == "because"
        assert pattern.tags == ["python", "good"]
        assert pattern.source_file == "src/a.py"
        assert pattern.confidence == 0.92

    def test_document_to_pattern_missing_fields(self):
        retriever = PatternRetriever(vector_store=Mock())
        doc = VectorDocument(
            id="doc2",
            content="code",
            embedding=None,
            metadata={},
            score=None,
        )
        pattern = retriever._document_to_pattern(doc)
        assert pattern is not None
        assert pattern.name == "Unnamed Pattern"
        assert pattern.description == ""
        assert pattern.pattern_type is PatternType.GOOD_PRACTICE
        assert pattern.language == "unknown"
        assert pattern.rationale == ""
        assert pattern.tags == []
        assert pattern.source_file is None
        assert pattern.counter_example is None
        assert pattern.confidence == 0.5  # score is None -> 0.5

    def test_document_to_pattern_invalid_type(self):
        retriever = PatternRetriever(vector_store=Mock())
        doc = VectorDocument(
            id="doc3",
            content="code",
            embedding=None,
            metadata={"type": "TOTALLY_INVALID"},
            score=0.5,
        )
        # ValueError from PatternType() -> returns None
        pattern = retriever._document_to_pattern(doc)
        assert pattern is None

    def test_document_to_pattern_score_zero(self):
        retriever = PatternRetriever(vector_store=Mock())
        doc = VectorDocument(
            id="doc4",
            content="code",
            embedding=None,
            metadata={"type": "idiom"},
            score=0.0,
        )
        pattern = retriever._document_to_pattern(doc)
        assert pattern is not None
        # score 0.0 is falsy, so `or 0.5` kicks in
        assert pattern.confidence == 0.5


# ---------------------------------------------------------------------------
# PatternManager
# ---------------------------------------------------------------------------


class TestPatternManager:
    """Tests for PatternManager."""

    @patch("learning.patterns.get_vector_store", return_value=None)
    def test_init_defaults(self, mock_get):
        manager = PatternManager()
        assert manager.vector_store is None
        assert manager.extractor is None
        assert isinstance(manager.retriever, PatternRetriever)

    def test_init_with_all_params(self):
        store = Mock()
        extractor = Mock()
        manager = PatternManager(vector_store=store, extractor=extractor)
        assert manager.vector_store is store
        assert manager.extractor is extractor
        assert manager.retriever.vector_store is store

    # --- learn_from_good_code ---

    @pytest.mark.asyncio
    async def test_learn_from_good_code_no_extractor(self):
        manager = PatternManager(vector_store=Mock(), extractor=None)
        result = await manager.learn_from_good_code("f.py", "code", "python")
        assert result == []

    @pytest.mark.asyncio
    async def test_learn_from_good_code_success(self):
        mock_extractor = Mock()
        pattern = CodePattern(
            id="p1",
            name="Test",
            description="d",
            pattern_type=PatternType.GOOD_PRACTICE,
            language="python",
            code_example="code",
            counter_example=None,
            rationale="r",
            tags=["python"],
            source_file="f.py",
            confidence=0.8,
            metadata={"extracted_at": "ts"},
        )
        mock_extractor.extract_patterns_from_file = AsyncMock(return_value=[pattern])

        mock_store = Mock()
        mock_store.add_documents = AsyncMock()

        manager = PatternManager(vector_store=mock_store, extractor=mock_extractor)
        result = await manager.learn_from_good_code("f.py", "code", "python")

        assert len(result) == 1
        assert result[0].name == "Test"
        mock_store.add_documents.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_learn_from_good_code_no_vector_store(self):
        mock_extractor = Mock()
        pattern = CodePattern(
            id="p1",
            name="Test",
            description="d",
            pattern_type=PatternType.GOOD_PRACTICE,
            language="python",
            code_example="code",
            counter_example=None,
            rationale="r",
            tags=[],
            source_file=None,
            confidence=0.8,
            metadata={},
        )
        mock_extractor.extract_patterns_from_file = AsyncMock(return_value=[pattern])

        manager = PatternManager(vector_store=None, extractor=mock_extractor)
        result = await manager.learn_from_good_code("f.py", "code", "py")

        assert len(result) == 1
        # Should not crash without vector store

    @pytest.mark.asyncio
    async def test_learn_from_good_code_empty_patterns(self):
        mock_extractor = Mock()
        mock_extractor.extract_patterns_from_file = AsyncMock(return_value=[])

        mock_store = Mock()
        mock_store.add_documents = AsyncMock()

        manager = PatternManager(vector_store=mock_store, extractor=mock_extractor)
        result = await manager.learn_from_good_code("f.py", "code", "py")

        assert result == []
        # add_documents should still be called with empty list -- actually it's called
        # only if patterns are non-empty? Let's check: _store_patterns is called
        # regardless because `if self.vector_store:` is true and patterns can be empty
        mock_store.add_documents.assert_awaited_once()

    # --- learn_from_feedback ---

    @pytest.mark.asyncio
    async def test_learn_from_feedback_no_extractor(self):
        manager = PatternManager(vector_store=Mock(), extractor=None)
        result = await manager.learn_from_feedback(
            pr_number=1,
            repo_info={"owner": "org", "name": "repo"},
            feedback="good",
            code_changes=[],
            language="python",
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_learn_from_feedback_success(self):
        mock_extractor = Mock()
        pattern = CodePattern(
            id="p1",
            name="Test",
            description="d",
            pattern_type=PatternType.GOOD_PRACTICE,
            language="python",
            code_example="code",
            counter_example=None,
            rationale="r",
            tags=["python"],
            source_file=None,
            confidence=0.7,
            metadata={"extracted_from": "feedback"},
        )
        mock_extractor.extract_patterns_from_review_feedback = AsyncMock(return_value=[pattern])

        mock_store = Mock()
        mock_store.add_documents = AsyncMock()

        manager = PatternManager(vector_store=mock_store, extractor=mock_extractor)
        result = await manager.learn_from_feedback(
            pr_number=42,
            repo_info={"owner": "myorg", "name": "myrepo"},
            feedback="Great job!",
            code_changes=[{"file_path": "f.py", "content": "code"}],
            language="python",
        )

        assert len(result) == 1
        # Check metadata was enriched
        assert result[0].metadata["learned_from"] == "PR #42"
        assert result[0].metadata["repo"] == "myorg/myrepo"
        mock_store.add_documents.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_learn_from_feedback_no_vector_store(self):
        mock_extractor = Mock()
        pattern = CodePattern(
            id="p1",
            name="Test",
            description="d",
            pattern_type=PatternType.GOOD_PRACTICE,
            language="python",
            code_example="code",
            counter_example=None,
            rationale="r",
            tags=[],
            source_file=None,
            confidence=0.7,
            metadata={},
        )
        mock_extractor.extract_patterns_from_review_feedback = AsyncMock(return_value=[pattern])

        manager = PatternManager(vector_store=None, extractor=mock_extractor)
        result = await manager.learn_from_feedback(
            pr_number=1,
            repo_info={"owner": "", "name": ""},
            feedback="fb",
            code_changes=[],
            language="py",
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_learn_from_feedback_repo_info_missing_keys(self):
        mock_extractor = Mock()
        pattern = CodePattern(
            id="p1",
            name="T",
            description="d",
            pattern_type=PatternType.GOOD_PRACTICE,
            language="py",
            code_example="c",
            counter_example=None,
            rationale="r",
            tags=[],
            source_file=None,
            confidence=0.7,
            metadata={},
        )
        mock_extractor.extract_patterns_from_review_feedback = AsyncMock(return_value=[pattern])

        manager = PatternManager(vector_store=None, extractor=mock_extractor)
        result = await manager.learn_from_feedback(
            pr_number=1,
            repo_info={},
            feedback="fb",
            code_changes=[],
            language="py",
        )
        assert result[0].metadata["repo"] == "/"

    # --- get_patterns_for_review ---

    @pytest.mark.asyncio
    async def test_get_patterns_for_review_no_patterns(self):
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[])
        manager = PatternManager(vector_store=mock_store)

        result = await manager.get_patterns_for_review("code", "python")
        assert result == ""

    @pytest.mark.asyncio
    async def test_get_patterns_for_review_with_patterns(self):
        doc = VectorDocument(
            id="p1",
            content="example code here",
            embedding=None,
            metadata={
                "name": "Input Validation",
                "description": "Validate user inputs",
                "type": "good_practice",
                "language": "python",
                "rationale": "Prevents bugs",
                "tags": ["python"],
            },
            score=0.88,
        )
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[doc])

        manager = PatternManager(vector_store=mock_store)
        result = await manager.get_patterns_for_review("some code", "python")

        assert "### Relevant Patterns from Repository Knowledge Base" in result
        assert "**Input Validation** (good_practice)" in result
        assert "Validate user inputs" in result
        assert "example code here" in result
        assert "*Rationale: Prevents bugs*" in result

    @pytest.mark.asyncio
    async def test_get_patterns_for_review_no_rationale(self):
        doc = VectorDocument(
            id="p1",
            content="code",
            embedding=None,
            metadata={
                "name": "P",
                "description": "d",
                "type": "idiom",
                "language": "py",
                "rationale": "",
            },
            score=0.5,
        )
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[doc])

        manager = PatternManager(vector_store=mock_store)
        result = await manager.get_patterns_for_review("code", "python")

        # Empty rationale should not produce a rationale line
        assert "*Rationale: *" not in result

    @pytest.mark.asyncio
    async def test_get_patterns_for_review_multiple_patterns(self):
        doc1 = VectorDocument(
            id="p1",
            content="code1",
            embedding=None,
            metadata={
                "name": "Pattern A",
                "description": "desc A",
                "type": "good_practice",
                "language": "python",
                "rationale": "reason A",
            },
            score=0.9,
        )
        doc2 = VectorDocument(
            id="p2",
            content="code2",
            embedding=None,
            metadata={
                "name": "Pattern B",
                "description": "desc B",
                "type": "anti_pattern",
                "language": "python",
                "rationale": "reason B",
            },
            score=0.7,
        )
        mock_store = Mock()
        mock_store.search = AsyncMock(return_value=[doc1, doc2])

        manager = PatternManager(vector_store=mock_store)
        result = await manager.get_patterns_for_review("code", "python")

        assert "Pattern A" in result
        assert "Pattern B" in result
        assert "reason A" in result
        assert "reason B" in result

    # --- _store_patterns ---

    @pytest.mark.asyncio
    async def test_store_patterns_no_store(self):
        manager = PatternManager(vector_store=None)
        # Should not raise
        await manager._store_patterns([])

    @pytest.mark.asyncio
    async def test_store_patterns_creates_documents(self):
        mock_store = Mock()
        mock_store.add_documents = AsyncMock()

        manager = PatternManager(vector_store=mock_store)

        pattern = CodePattern(
            id="p1",
            name="Test Pattern",
            description="A test",
            pattern_type=PatternType.IDIOM,
            language="python",
            code_example="x = 1",
            counter_example=None,
            rationale="Simple assignment",
            tags=["python", "idiom"],
            source_file="f.py",
            confidence=0.8,
            metadata={"extracted_at": "now"},
        )

        await manager._store_patterns([pattern])

        mock_store.add_documents.assert_awaited_once()
        docs = mock_store.add_documents.call_args[0][0]
        assert len(docs) == 1
        doc = docs[0]
        assert doc.id == "p1"
        assert doc.content == "x = 1"
        assert doc.embedding is None
        assert doc.metadata["name"] == "Test Pattern"
        assert doc.metadata["description"] == "A test"
        assert doc.metadata["type"] == "idiom"
        assert doc.metadata["language"] == "python"
        assert doc.metadata["rationale"] == "Simple assignment"
        assert doc.metadata["tags"] == ["python", "idiom"]
        assert doc.metadata["source_file"] == "f.py"
        assert doc.metadata["confidence"] == 0.8
        assert doc.metadata["extracted_at"] == "now"

    @pytest.mark.asyncio
    async def test_store_patterns_multiple(self):
        mock_store = Mock()
        mock_store.add_documents = AsyncMock()
        manager = PatternManager(vector_store=mock_store)

        patterns = [
            CodePattern(
                id=f"p{i}",
                name=f"P{i}",
                description="d",
                pattern_type=PatternType.GOOD_PRACTICE,
                language="py",
                code_example=f"code_{i}",
                counter_example=None,
                rationale="r",
                tags=[],
                source_file=None,
                confidence=0.5,
                metadata={},
            )
            for i in range(3)
        ]

        await manager._store_patterns(patterns)

        docs = mock_store.add_documents.call_args[0][0]
        assert len(docs) == 3
        assert docs[0].id == "p0"
        assert docs[1].id == "p1"
        assert docs[2].id == "p2"


# ---------------------------------------------------------------------------
# Module-level functions: init_pattern_manager / get_pattern_manager
# ---------------------------------------------------------------------------


class TestModuleLevelFunctions:
    """Tests for init_pattern_manager and get_pattern_manager."""

    def test_init_pattern_manager_with_llm(self):
        import learning.patterns as pm

        old = pm._pattern_manager
        try:
            mock_store = Mock()
            mock_llm = Mock()

            manager = init_pattern_manager(vector_store=mock_store, llm_client=mock_llm)

            assert isinstance(manager, PatternManager)
            assert manager.vector_store is mock_store
            assert manager.extractor is not None
            assert manager.extractor.llm_client is mock_llm
            assert get_pattern_manager() is manager
        finally:
            pm._pattern_manager = old

    def test_init_pattern_manager_without_llm(self):
        import learning.patterns as pm

        old = pm._pattern_manager
        try:
            mock_store = Mock()
            manager = init_pattern_manager(vector_store=mock_store, llm_client=None)
            assert manager.extractor is None
            assert get_pattern_manager() is manager
        finally:
            pm._pattern_manager = old

    def test_init_pattern_manager_no_params(self):
        import learning.patterns as pm

        old = pm._pattern_manager
        try:
            manager = init_pattern_manager()
            assert isinstance(manager, PatternManager)
            assert manager.extractor is None
        finally:
            pm._pattern_manager = old

    def test_get_pattern_manager_returns_none_initially(self):
        import learning.patterns as pm

        old = pm._pattern_manager
        try:
            pm._pattern_manager = None
            assert get_pattern_manager() is None
        finally:
            pm._pattern_manager = old
