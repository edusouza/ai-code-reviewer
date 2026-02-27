"""Pattern extraction and retrieval for code learning."""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from learning.vector_store import VectorDocument, VertexVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Types of code patterns."""

    GOOD_PRACTICE = "good_practice"
    ANTI_PATTERN = "anti_pattern"
    DESIGN_PATTERN = "design_pattern"
    IDIOM = "idiom"
    BEST_PRACTICE = "best_practice"
    SECURITY_PATTERN = "security_pattern"
    PERFORMANCE_PATTERN = "performance_pattern"


@dataclass
class CodePattern:
    """A learned code pattern."""

    id: str
    name: str
    description: str
    pattern_type: PatternType
    language: str
    code_example: str
    counter_example: str | None
    rationale: str
    tags: list[str]
    source_file: str | None
    confidence: float
    metadata: dict[str, Any]


class PatternExtractor:
    """Extract patterns from code using LLM analysis."""

    def __init__(self, llm_client: Any | None = None):
        """
        Initialize the pattern extractor.

        Args:
            llm_client: LLM client for pattern extraction
        """
        self.llm_client = llm_client

    async def extract_patterns_from_file(
        self, file_path: str, file_content: str, language: str, context: str | None = None
    ) -> list[CodePattern]:
        """
        Extract patterns from a code file.

        Args:
            file_path: Path to the file
            file_content: File content
            language: Programming language
            context: Additional context

        Returns:
            List of extracted patterns
        """
        if not self.llm_client:
            logger.warning("No LLM client available for pattern extraction")
            return []

        try:
            prompt = f"""Analyze the following {language} code and extract any notable patterns.

File: {file_path}

Code:
```{language}
{file_content[:8000]}  # Limit content length
```

Extract the following:
1. Good practices demonstrated in this code
2. Any design patterns used
3. Language-specific idioms
4. Performance optimizations
5. Security best practices

For each pattern found, provide:
- Name: Short, descriptive name
- Type: good_practice, design_pattern, idiom, or security_pattern
- Description: Clear explanation
- Code Example: The relevant code snippet
- Rationale: Why this is a good pattern

Respond in JSON format:
{{
    "patterns": [
        {{
            "name": "pattern name",
            "type": "pattern_type",
            "description": "description",
            "code_example": "code snippet",
            "rationale": "explanation"
        }}
    ]
}}"""

            response = await self.llm_client.generate_json(
                prompt=prompt,
                system_prompt="You are a code analysis expert. Extract patterns and best practices from code.",
                temperature=0.3,
            )

            patterns = []
            for p in response.get("patterns", []):
                pattern = CodePattern(
                    id=f"pat_{hash(file_path + p['name']) & 0xFFFFFF}",
                    name=p["name"],
                    description=p["description"],
                    pattern_type=PatternType(p.get("type", "good_practice")),
                    language=language,
                    code_example=p["code_example"],
                    counter_example=None,
                    rationale=p["rationale"],
                    tags=[language, p.get("type", "general")],
                    source_file=file_path,
                    confidence=0.8,
                    metadata={"extracted_at": "timestamp"},
                )
                patterns.append(pattern)

            logger.info(f"Extracted {len(patterns)} patterns from {file_path}")
            return patterns

        except Exception as e:
            logger.error(f"Failed to extract patterns from {file_path}: {e}")
            return []

    async def extract_patterns_from_review_feedback(
        self, code_changes: list[dict[str, Any]], feedback: str, language: str
    ) -> list[CodePattern]:
        """
        Extract patterns from review feedback.

        Args:
            code_changes: List of code changes
            feedback: Review feedback text
            language: Programming language

        Returns:
            List of patterns derived from feedback
        """
        if not self.llm_client:
            return []

        try:
            changes_text = "\n\n".join(
                [
                    f"File: {c.get('file_path', 'unknown')}\n```\n{c.get('content', '')[:2000]}\n```"
                    for c in code_changes[:5]  # Limit changes
                ]
            )

            prompt = f"""Based on the following code review feedback, extract patterns.

Code Changes:
{changes_text}

Feedback:
{feedback}

Extract patterns that:
1. Explain what the reviewer liked (good patterns)
2. Explain what should be avoided (anti-patterns)
3. Demonstrate best practices

For each pattern, provide:
- Name
- Type (good_practice or anti_pattern)
- Description
- Code example
- Counter-example (if anti-pattern)
- Rationale

Respond in JSON format with a "patterns" array."""

            response = await self.llm_client.generate_json(
                prompt=prompt,
                system_prompt="Extract patterns from code review feedback.",
                temperature=0.3,
            )

            patterns = []
            for p in response.get("patterns", []):
                pattern = CodePattern(
                    id=f"pat_fb_{hash(feedback[:100] + p['name']) & 0xFFFFFF}",
                    name=p["name"],
                    description=p["description"],
                    pattern_type=PatternType(p.get("type", "good_practice")),
                    language=language,
                    code_example=p["code_example"],
                    counter_example=p.get("counter_example"),
                    rationale=p["rationale"],
                    tags=[language, "from_feedback"],
                    source_file=None,
                    confidence=0.7,
                    metadata={"extracted_from": "feedback"},
                )
                patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.error(f"Failed to extract patterns from feedback: {e}")
            return []


class PatternRetriever:
    """Retrieve relevant patterns for code reviews."""

    def __init__(self, vector_store: VertexVectorStore | None = None):
        """
        Initialize the pattern retriever.

        Args:
            vector_store: Vector store for semantic search
        """
        self.vector_store = vector_store or get_vector_store()

    async def find_relevant_patterns(
        self,
        code_chunk: str,
        language: str,
        pattern_types: list[PatternType] | None = None,
        top_k: int = 5,
    ) -> list[CodePattern]:
        """
        Find patterns relevant to a code chunk.

        Args:
            code_chunk: Code to find patterns for
            language: Programming language
            pattern_types: Types of patterns to search for
            top_k: Number of patterns to return

        Returns:
            List of relevant patterns
        """
        if not self.vector_store:
            logger.warning("Vector store not available, returning empty patterns")
            return []

        try:
            # Create search query from code
            search_query = self._create_search_query(code_chunk, language)

            # Search vector store
            filter_type = pattern_types[0].value if pattern_types else None
            documents = await self.vector_store.search(
                query=search_query, top_k=top_k, filter_type=filter_type, filter_language=language
            )

            # Convert to CodePattern objects
            patterns = []
            for doc in documents:
                pattern = self._document_to_pattern(doc)
                if pattern:
                    patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.error(f"Failed to find patterns: {e}")
            return []

    async def find_patterns_for_suggestion(
        self, file_path: str, line_number: int, issue_description: str, language: str
    ) -> list[CodePattern]:
        """
        Find patterns that relate to a specific suggestion/issue.

        Args:
            file_path: Path to the file
            line_number: Line number of the issue
            issue_description: Description of the issue
            language: Programming language

        Returns:
            List of relevant patterns
        """
        if not self.vector_store:
            return []

        try:
            # Search by issue description
            documents = await self.vector_store.search(
                query=issue_description, top_k=3, filter_language=language
            )

            patterns = []
            for doc in documents:
                pattern = self._document_to_pattern(doc)
                if pattern:
                    patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.error(f"Failed to find patterns for suggestion: {e}")
            return []

    async def get_common_patterns(
        self, language: str, pattern_type: PatternType | None = None, limit: int = 10
    ) -> list[CodePattern]:
        """
        Get commonly used patterns for a language.

        Args:
            language: Programming language
            pattern_type: Optional pattern type filter
            limit: Maximum number of patterns

        Returns:
            List of common patterns
        """
        # This would query a curated list or use frequency data
        # For now, return empty list
        logger.debug(f"Getting common patterns for {language}")
        return []

    def _create_search_query(self, code_chunk: str, language: str) -> str:
        """Create a search query from code chunk."""
        # Extract key elements from code
        # Remove comments and strings
        code_clean = re.sub(r'["\'][^"\']*["\']', '"..."', code_chunk)
        code_clean = re.sub(r"#.*$", "", code_clean, flags=re.MULTILINE)

        # Extract function/class names
        identifiers = re.findall(r"\b(def|class|function)\s+(\w+)", code_clean)
        keywords = [id[1] for id in identifiers]

        # Build query
        query_parts = [language]
        query_parts.extend(keywords[:3])  # Top 3 identifiers

        # Add code structure hints
        if "def " in code_chunk:
            query_parts.append("function")
        if "class " in code_chunk:
            query_parts.append("class")
        if "for " in code_chunk or "while " in code_chunk:
            query_parts.append("loop")
        if "if " in code_chunk:
            query_parts.append("conditional")

        return " ".join(query_parts)

    def _document_to_pattern(self, doc: VectorDocument) -> CodePattern | None:
        """Convert a vector document to a CodePattern."""
        try:
            metadata = doc.metadata

            return CodePattern(
                id=doc.id,
                name=metadata.get("name", "Unnamed Pattern"),
                description=metadata.get("description", ""),
                pattern_type=PatternType(metadata.get("type", "good_practice")),
                language=metadata.get("language", "unknown"),
                code_example=doc.content,
                counter_example=metadata.get("counter_example"),
                rationale=metadata.get("rationale", ""),
                tags=metadata.get("tags", []),
                source_file=metadata.get("source_file"),
                confidence=doc.score or 0.5,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to convert document to pattern: {e}")
            return None


class PatternManager:
    """Manager for storing and retrieving code patterns."""

    def __init__(
        self,
        vector_store: VertexVectorStore | None = None,
        extractor: PatternExtractor | None = None,
    ):
        """
        Initialize the pattern manager.

        Args:
            vector_store: Vector store for persistence
            extractor: Pattern extractor
        """
        self.vector_store = vector_store or get_vector_store()
        self.extractor = extractor
        self.retriever = PatternRetriever(vector_store)

    async def learn_from_good_code(
        self, file_path: str, file_content: str, language: str, source: str = "manual"
    ) -> list[CodePattern]:
        """
        Learn patterns from well-written code.

        Args:
            file_path: Path to the file
            file_content: File content
            language: Programming language
            source: Source of the code (e.g., 'manual', 'approved_pr')

        Returns:
            List of learned patterns
        """
        if not self.extractor:
            logger.warning("No pattern extractor configured")
            return []

        # Extract patterns
        patterns = await self.extractor.extract_patterns_from_file(
            file_path, file_content, language
        )

        # Store in vector store
        if self.vector_store:
            await self._store_patterns(patterns)

        logger.info(f"Learned {len(patterns)} patterns from {file_path}")
        return patterns

    async def learn_from_feedback(
        self,
        pr_number: int,
        repo_info: dict[str, str],
        feedback: str,
        code_changes: list[dict[str, Any]],
        language: str,
    ) -> list[CodePattern]:
        """
        Learn patterns from positive feedback on reviews.

        Args:
            pr_number: PR number
            repo_info: Repository information
            feedback: Feedback text
            code_changes: Code changes
            language: Programming language

        Returns:
            List of learned patterns
        """
        if not self.extractor:
            return []

        patterns = await self.extractor.extract_patterns_from_review_feedback(
            code_changes, feedback, language
        )

        # Add metadata
        for pattern in patterns:
            pattern.metadata["learned_from"] = f"PR #{pr_number}"
            pattern.metadata["repo"] = f"{repo_info.get('owner', '')}/{repo_info.get('name', '')}"

        if self.vector_store:
            await self._store_patterns(patterns)

        return patterns

    async def get_patterns_for_review(
        self, code_chunk: str, language: str, context: dict[str, Any] | None = None
    ) -> str:
        """
        Get patterns formatted for inclusion in review context.

        Args:
            code_chunk: Code being reviewed
            language: Programming language
            context: Additional context

        Returns:
            Formatted patterns string
        """
        patterns = await self.retriever.find_relevant_patterns(code_chunk, language, top_k=3)

        if not patterns:
            return ""

        formatted = ["### Relevant Patterns from Repository Knowledge Base\n"]

        for pattern in patterns:
            formatted.append(f"**{pattern.name}** ({pattern.pattern_type.value})")
            formatted.append(f"{pattern.description}\n")
            formatted.append("Example:")
            formatted.append(f"```{pattern.language}")
            formatted.append(pattern.code_example)
            formatted.append("```\n")

            if pattern.rationale:
                formatted.append(f"*Rationale: {pattern.rationale}*\n")

        return "\n".join(formatted)

    async def _store_patterns(self, patterns: list[CodePattern]) -> None:
        """Store patterns in the vector store."""
        if not self.vector_store:
            return

        documents = []
        for pattern in patterns:
            doc = VectorDocument(
                id=pattern.id,
                content=pattern.code_example,
                embedding=None,
                metadata={
                    "name": pattern.name,
                    "description": pattern.description,
                    "type": pattern.pattern_type.value,
                    "language": pattern.language,
                    "rationale": pattern.rationale,
                    "tags": pattern.tags,
                    "source_file": pattern.source_file,
                    "confidence": pattern.confidence,
                    **pattern.metadata,
                },
            )
            documents.append(doc)

        await self.vector_store.add_documents(documents)


# Global manager instance
_pattern_manager: PatternManager | None = None


def init_pattern_manager(
    vector_store: VertexVectorStore | None = None, llm_client: Any | None = None
) -> PatternManager:
    """
    Initialize the global pattern manager.

    Args:
        vector_store: Vector store instance
        llm_client: LLM client for extraction

    Returns:
        PatternManager instance
    """
    global _pattern_manager

    extractor = PatternExtractor(llm_client) if llm_client else None
    _pattern_manager = PatternManager(vector_store, extractor)

    return _pattern_manager


def get_pattern_manager() -> PatternManager | None:
    """Get the global pattern manager."""
    return _pattern_manager
