"""Large PR optimization for cost and performance."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FilePriority(Enum):
    """Priority levels for files in a PR."""

    CRITICAL = 5  # Must review (e.g., config files, security-related)
    HIGH = 4  # Important (e.g., core business logic)
    MEDIUM = 3  # Standard (e.g., utility functions)
    LOW = 2  # Less important (e.g., tests, documentation)
    SKIP = 1  # Can skip (e.g., generated files)


@dataclass
class FileInfo:
    """Information about a file in a PR."""

    path: str
    language: str
    additions: int
    deletions: int
    change_type: str  # added, modified, deleted, renamed
    priority: FilePriority
    review_reason: str
    estimated_tokens: int


class LargePROptimizer:
    """Optimize review of large PRs to manage cost and time."""

    # File extensions and their priorities
    PRIORITY_PATTERNS = {
        FilePriority.CRITICAL: [
            r".*\.config\.(js|ts|json|yaml|yml)$",
            r".*Dockerfile.*",
            r".*docker-compose.*",
            r".*\.env.*",
            r".*secrets?.*",
            r".*auth.*\.py$",
            r".*security.*\.py$",
            r".*password.*\.py$",
            r".*encrypt.*\.py$",
        ],
        FilePriority.HIGH: [
            r".*/(models|schemas|entities)/.*\.py$",
            r".*/services/.*\.py$",
            r".*/controllers?/.*\.py$",
            r".*/handlers?/.*\.py$",
            r".*/core/.*\.py$",
            r".*/main\.py$",
            r".*app\.py$",
            r".*/(api|routes)/.*\.(js|ts)$",
        ],
        FilePriority.LOW: [
            r".*\.test\.(py|js|ts)$",
            r".*\.spec\.(py|js|ts)$",
            r".*test_.*\.py$",
            r".*/tests?/.*\.py$",
            r".*/__tests__/.*\.(js|ts)$",
            r".*\.md$",
            r".*README.*",
            r".*CHANGELOG.*",
            r".*\.rst$",
        ],
        FilePriority.SKIP: [
            r".*\.min\.(js|css)$",
            r".*bundle\.(js|css)$",
            r".*\.lock$",
            r".*yarn\.lock$",
            r".*package-lock\.json$",
            r".*\.map$",
            r".*/dist/.*",
            r".*/build/.*",
            r".*/node_modules/.*",
            r".*/\.venv/.*",
            r".*__pycache__.*",
            r".*\.pyc$",
        ],
    }

    # Language multipliers for token estimation
    TOKEN_MULTIPLIERS = {
        "python": 1.0,
        "javascript": 0.8,
        "typescript": 0.8,
        "java": 1.2,
        "go": 0.9,
        "rust": 1.0,
        "c": 1.0,
        "cpp": 1.1,
        "csharp": 1.1,
        "ruby": 0.9,
        "php": 1.0,
        "swift": 1.0,
        "kotlin": 1.0,
        "scala": 1.2,
        "default": 1.0,
    }

    def __init__(
        self,
        max_tokens_per_review: int = 100000,
        max_files_to_review: int = 50,
        min_priority_for_inclusion: FilePriority = FilePriority.MEDIUM,
    ):
        """
        Initialize the optimizer.

        Args:
            max_tokens_per_review: Maximum tokens to process per review
            max_files_to_review: Maximum files to include
            min_priority_for_inclusion: Minimum priority level to include
        """
        self.max_tokens = max_tokens_per_review
        self.max_files = max_files_to_review
        self.min_priority = min_priority_for_inclusion

        import re

        self._compiled_patterns: dict[FilePriority, list[Any]] = {}
        for priority, patterns in self.PRIORITY_PATTERNS.items():
            self._compiled_patterns[priority] = [re.compile(p) for p in patterns]

    def prioritize_files(self, files: list[dict[str, Any]]) -> list[FileInfo]:
        """
        Prioritize files for review based on importance.

        Args:
            files: List of file change information from provider

        Returns:
            List of prioritized FileInfo objects
        """
        file_infos = []

        for file_data in files:
            path = file_data.get("path", "")
            language = self._detect_language(path)

            # Calculate priority
            priority = self._calculate_priority(path, file_data, language)

            # Estimate tokens
            additions = file_data.get("additions", 0)
            deletions = file_data.get("deletions", 0)
            estimated_tokens = self._estimate_tokens(additions, deletions, language)

            # Determine review reason
            review_reason = self._get_review_reason(priority, path, file_data)

            file_info = FileInfo(
                path=path,
                language=language,
                additions=additions,
                deletions=deletions,
                change_type=file_data.get("status", "modified"),
                priority=priority,
                review_reason=review_reason,
                estimated_tokens=estimated_tokens,
            )

            file_infos.append(file_info)

        # Sort by priority (highest first), then by estimated tokens
        file_infos.sort(key=lambda f: (-f.priority.value, f.estimated_tokens))

        return file_infos

    def select_files_for_review(
        self, file_infos: list[FileInfo], budget_enforcer: Any | None = None
    ) -> tuple[list[FileInfo], list[FileInfo], dict[str, Any]]:
        """
        Select which files to review within constraints.

        Args:
            file_infos: Prioritized file information
            budget_enforcer: Optional budget enforcer for cost checks

        Returns:
            Tuple of (selected files, skipped files, summary)
        """
        selected: list[FileInfo] = []
        skipped: list[FileInfo] = []
        total_tokens = 0

        for file_info in file_infos:
            # Check if file meets minimum priority
            if file_info.priority.value < self.min_priority.value:
                skipped.append(file_info)
                continue

            # Check if adding this file would exceed limits
            projected_tokens = total_tokens + file_info.estimated_tokens

            if len(selected) >= self.max_files:
                file_info.review_reason += f" (Skipped: max {self.max_files} files reached)"
                skipped.append(file_info)
                continue

            if projected_tokens > self.max_tokens:
                file_info.review_reason += f" (Skipped: would exceed {self.max_tokens} token limit)"
                skipped.append(file_info)
                continue

            # Add to selected
            selected.append(file_info)
            total_tokens += file_info.estimated_tokens

        # Generate summary
        summary = {
            "total_files": len(file_infos),
            "files_selected": len(selected),
            "files_skipped": len(skipped),
            "total_tokens": sum(f.estimated_tokens for f in file_infos),
            "tokens_selected": total_tokens,
            "priority_breakdown": self._get_priority_breakdown(selected),
            "language_breakdown": self._get_language_breakdown(selected),
        }

        logger.info(
            f"Selected {len(selected)}/{len(file_infos)} files for review "
            f"({total_tokens}/{self.max_tokens} tokens)"
        )

        return selected, skipped, summary

    def chunk_large_files(
        self, file_info: FileInfo, content: str, chunk_size: int = 5000
    ) -> list[dict[str, Any]]:
        """
        Split large files into reviewable chunks.

        Args:
            file_info: File information
            content: Full file content
            chunk_size: Maximum chunk size in characters

        Returns:
            List of chunk information
        """
        if len(content) <= chunk_size:
            return [
                {
                    "file_info": file_info,
                    "content": content,
                    "start_line": 1,
                    "end_line": content.count("\n") + 1,
                    "is_full_file": True,
                }
            ]

        chunks = []
        lines = content.split("\n")
        current_chunk_lines: list[str] = []
        current_chunk_size = 0
        start_line = 1
        line_number = 0

        for line in lines:
            line_number += 1
            line_size = len(line)

            # Check if adding this line would exceed chunk size
            if current_chunk_size + line_size > chunk_size and current_chunk_lines:
                # Save current chunk
                chunk_content = "\n".join(current_chunk_lines)
                chunks.append(
                    {
                        "file_info": file_info,
                        "content": chunk_content,
                        "start_line": start_line,
                        "end_line": line_number - 1,
                        "is_full_file": False,
                    }
                )

                # Start new chunk
                current_chunk_lines = [line]
                current_chunk_size = line_size
                start_line = line_number
            else:
                current_chunk_lines.append(line)
                current_chunk_size += line_size + 1  # +1 for newline

        # Don't forget the last chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            chunks.append(
                {
                    "file_info": file_info,
                    "content": chunk_content,
                    "start_line": start_line,
                    "end_line": line_number,
                    "is_full_file": len(chunks) == 0,
                }
            )

        logger.debug(f"Split {file_info.path} into {len(chunks)} chunks")
        return chunks

    def _calculate_priority(
        self, path: str, file_data: dict[str, Any], language: str
    ) -> FilePriority:
        """Calculate the priority of a file."""
        # Check patterns in priority order
        for priority in [
            FilePriority.SKIP,
            FilePriority.LOW,
            FilePriority.HIGH,
            FilePriority.CRITICAL,
        ]:
            for pattern in self._compiled_patterns.get(priority, []):
                if pattern.match(path):
                    return priority

        # Check for large deletions (refactoring)
        deletions = file_data.get("deletions", 0)
        if deletions > 100:
            return FilePriority.HIGH

        # Check for new files
        if file_data.get("status") == "added":
            return FilePriority.HIGH

        # Default to medium
        return FilePriority.MEDIUM

    def _detect_language(self, path: str) -> str:
        """Detect programming language from file path."""
        import os

        ext = os.path.splitext(path)[1].lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
        }

        return language_map.get(ext, "unknown")

    def _estimate_tokens(self, additions: int, deletions: int, language: str) -> int:
        """Estimate token count for a file change."""
        # Base estimate: ~4 characters per token
        total_lines = additions + deletions
        base_tokens = total_lines * 20  # Assume ~80 chars per line

        # Apply language multiplier
        multiplier = self.TOKEN_MULTIPLIERS.get(language, 1.0)

        # Add overhead for context
        overhead = 500  # System prompt, file path, etc.

        return int(base_tokens * multiplier) + overhead

    def _get_review_reason(
        self, priority: FilePriority, path: str, file_data: dict[str, Any]
    ) -> str:
        """Generate a reason for including/excluding a file."""
        reasons = {
            FilePriority.CRITICAL: "Critical file requiring review (config/security)",
            FilePriority.HIGH: "High priority file (core logic or new file)",
            FilePriority.MEDIUM: "Standard file for review",
            FilePriority.LOW: "Low priority (tests or docs)",
            FilePriority.SKIP: "Skipped (generated or build file)",
        }

        base_reason = reasons.get(priority, "Unknown priority")

        # Add context
        if file_data.get("status") == "added":
            base_reason += " [NEW FILE]"
        elif file_data.get("status") == "deleted":
            base_reason += " [DELETED]"
        elif file_data.get("deletions", 0) > file_data.get("additions", 0):
            base_reason += " [MAJOR REFACTORING]"

        return base_reason

    def _get_priority_breakdown(self, files: list[FileInfo]) -> dict[str, int]:
        """Get count of files by priority."""
        breakdown: dict[str, int] = {}
        for priority in FilePriority:
            count = sum(1 for f in files if f.priority == priority)
            if count > 0:
                breakdown[priority.name] = count
        return breakdown

    def _get_language_breakdown(self, files: list[FileInfo]) -> dict[str, int]:
        """Get count of files by language."""
        breakdown: dict[str, int] = {}
        for file in files:
            lang = file.language
            breakdown[lang] = breakdown.get(lang, 0) + 1
        return breakdown

    def generate_review_summary(self, selected: list[FileInfo], skipped: list[FileInfo]) -> str:
        """
        Generate a summary of file selection for PR comments.

        Args:
            selected: Selected files
            skipped: Skipped files

        Returns:
            Summary text
        """
        lines = ["### 📊 Review Scope\n"]
        lines.append(f"**Files reviewed:** {len(selected)}")
        lines.append(f"**Files skipped:** {len(skipped)}")
        lines.append(f"**Estimated tokens:** {sum(f.estimated_tokens for f in selected):,}\n")

        if skipped:
            lines.append("**Skipped files:**")
            for f in skipped[:10]:  # Show first 10
                lines.append(f"- `{f.path}` - {f.review_reason}")
            if len(skipped) > 10:
                lines.append(f"- ... and {len(skipped) - 10} more")
            lines.append("")

        lines.append(
            "*Note: Large PRs are automatically optimized to focus on the most important changes.*"
        )

        return "\n".join(lines)


# Global optimizer instance
_optimizer: LargePROptimizer | None = None


def init_optimizer(
    max_tokens_per_review: int = 100000, max_files_to_review: int = 50
) -> LargePROptimizer:
    """
    Initialize the global optimizer.

    Args:
        max_tokens_per_review: Maximum tokens per review
        max_files_to_review: Maximum files to review

    Returns:
        LargePROptimizer instance
    """
    global _optimizer
    _optimizer = LargePROptimizer(
        max_tokens_per_review=max_tokens_per_review, max_files_to_review=max_files_to_review
    )
    return _optimizer


def get_optimizer() -> LargePROptimizer | None:
    """Get the global optimizer instance."""
    return _optimizer
