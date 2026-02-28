"""Tests for cost.optimizer module."""

import cost.optimizer as opt_mod
from cost.optimizer import (
    FileInfo,
    FilePriority,
    LargePROptimizer,
    get_optimizer,
    init_optimizer,
)


# ---------------------------------------------------------------------------
# FilePriority enum
# ---------------------------------------------------------------------------
class TestFilePriority:
    """Tests for the FilePriority enum."""

    def test_values_ordering(self):
        """Values should be ordered from SKIP(1) to CRITICAL(5)."""
        assert FilePriority.SKIP.value == 1
        assert FilePriority.LOW.value == 2
        assert FilePriority.MEDIUM.value == 3
        assert FilePriority.HIGH.value == 4
        assert FilePriority.CRITICAL.value == 5

    def test_comparison(self):
        assert FilePriority.CRITICAL.value > FilePriority.HIGH.value
        assert FilePriority.HIGH.value > FilePriority.MEDIUM.value
        assert FilePriority.MEDIUM.value > FilePriority.LOW.value
        assert FilePriority.LOW.value > FilePriority.SKIP.value


# ---------------------------------------------------------------------------
# FileInfo dataclass
# ---------------------------------------------------------------------------
class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_creation(self):
        fi = FileInfo(
            path="src/main.py",
            language="python",
            additions=10,
            deletions=5,
            change_type="modified",
            priority=FilePriority.HIGH,
            review_reason="Important",
            estimated_tokens=800,
        )
        assert fi.path == "src/main.py"
        assert fi.language == "python"
        assert fi.additions == 10
        assert fi.deletions == 5
        assert fi.change_type == "modified"
        assert fi.priority == FilePriority.HIGH
        assert fi.review_reason == "Important"
        assert fi.estimated_tokens == 800


# ---------------------------------------------------------------------------
# LargePROptimizer init
# ---------------------------------------------------------------------------
class TestLargePROptimizerInit:
    """Tests for LargePROptimizer constructor."""

    def test_defaults(self):
        opt = LargePROptimizer()
        assert opt.max_tokens == 100000
        assert opt.max_files == 50
        assert opt.min_priority == FilePriority.MEDIUM

    def test_custom_values(self):
        opt = LargePROptimizer(
            max_tokens_per_review=50000,
            max_files_to_review=20,
            min_priority_for_inclusion=FilePriority.HIGH,
        )
        assert opt.max_tokens == 50000
        assert opt.max_files == 20
        assert opt.min_priority == FilePriority.HIGH

    def test_compiled_patterns_populated(self):
        opt = LargePROptimizer()
        assert FilePriority.CRITICAL in opt._compiled_patterns
        assert FilePriority.HIGH in opt._compiled_patterns
        assert FilePriority.LOW in opt._compiled_patterns
        assert FilePriority.SKIP in opt._compiled_patterns
        # MEDIUM has no explicit patterns in PRIORITY_PATTERNS
        assert FilePriority.MEDIUM not in opt._compiled_patterns


# ---------------------------------------------------------------------------
# _detect_language
# ---------------------------------------------------------------------------
class TestDetectLanguage:
    """Tests for _detect_language."""

    def test_python(self):
        opt = LargePROptimizer()
        assert opt._detect_language("src/main.py") == "python"

    def test_javascript(self):
        opt = LargePROptimizer()
        assert opt._detect_language("app.js") == "javascript"
        assert opt._detect_language("component.jsx") == "javascript"

    def test_typescript(self):
        opt = LargePROptimizer()
        assert opt._detect_language("app.ts") == "typescript"
        assert opt._detect_language("component.tsx") == "typescript"

    def test_java(self):
        opt = LargePROptimizer()
        assert opt._detect_language("Main.java") == "java"

    def test_go(self):
        opt = LargePROptimizer()
        assert opt._detect_language("main.go") == "go"

    def test_rust(self):
        opt = LargePROptimizer()
        assert opt._detect_language("lib.rs") == "rust"

    def test_c(self):
        opt = LargePROptimizer()
        assert opt._detect_language("main.c") == "c"
        assert opt._detect_language("header.h") == "c"

    def test_cpp(self):
        opt = LargePROptimizer()
        assert opt._detect_language("main.cpp") == "cpp"
        assert opt._detect_language("header.hpp") == "cpp"

    def test_csharp(self):
        opt = LargePROptimizer()
        assert opt._detect_language("Program.cs") == "csharp"

    def test_ruby(self):
        opt = LargePROptimizer()
        assert opt._detect_language("app.rb") == "ruby"

    def test_php(self):
        opt = LargePROptimizer()
        assert opt._detect_language("index.php") == "php"

    def test_swift(self):
        opt = LargePROptimizer()
        assert opt._detect_language("ViewController.swift") == "swift"

    def test_kotlin(self):
        opt = LargePROptimizer()
        assert opt._detect_language("Main.kt") == "kotlin"

    def test_scala(self):
        opt = LargePROptimizer()
        assert opt._detect_language("App.scala") == "scala"

    def test_unknown(self):
        opt = LargePROptimizer()
        assert opt._detect_language("data.csv") == "unknown"
        assert opt._detect_language("Makefile") == "unknown"
        assert opt._detect_language("file.xyz") == "unknown"


# ---------------------------------------------------------------------------
# _estimate_tokens
# ---------------------------------------------------------------------------
class TestEstimateTokens:
    """Tests for _estimate_tokens."""

    def test_python_tokens(self):
        opt = LargePROptimizer()
        tokens = opt._estimate_tokens(10, 5, "python")
        # (10+5) * 20 * 1.0 + 500 = 300 + 500 = 800
        assert tokens == 800

    def test_javascript_tokens(self):
        opt = LargePROptimizer()
        tokens = opt._estimate_tokens(10, 5, "javascript")
        # (15) * 20 * 0.8 + 500 = 240 + 500 = 740
        assert tokens == 740

    def test_java_tokens(self):
        opt = LargePROptimizer()
        tokens = opt._estimate_tokens(10, 5, "java")
        # (15) * 20 * 1.2 + 500 = 360 + 500 = 860
        assert tokens == 860

    def test_zero_changes(self):
        opt = LargePROptimizer()
        tokens = opt._estimate_tokens(0, 0, "python")
        # 0 * 20 * 1.0 + 500 = 500
        assert tokens == 500

    def test_unknown_language_default_multiplier(self):
        opt = LargePROptimizer()
        tokens = opt._estimate_tokens(10, 0, "unknown")
        # 10 * 20 * 1.0 + 500 = 700
        assert tokens == 700

    def test_large_changes(self):
        opt = LargePROptimizer()
        tokens = opt._estimate_tokens(1000, 500, "python")
        # 1500 * 20 * 1.0 + 500 = 30500
        assert tokens == 30500


# ---------------------------------------------------------------------------
# _calculate_priority
# ---------------------------------------------------------------------------
class TestCalculatePriority:
    """Tests for _calculate_priority."""

    def test_dockerfile_is_critical(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("Dockerfile", {}, "unknown")
        assert p == FilePriority.CRITICAL

    def test_docker_compose_is_critical(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("docker-compose.yml", {}, "unknown")
        assert p == FilePriority.CRITICAL

    def test_env_file_is_critical(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority(".env.production", {}, "unknown")
        assert p == FilePriority.CRITICAL

    def test_config_json_is_critical(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("app.config.json", {}, "unknown")
        assert p == FilePriority.CRITICAL

    def test_auth_py_is_critical(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("src/auth.py", {}, "python")
        assert p == FilePriority.CRITICAL

    def test_security_py_is_critical(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("lib/security.py", {}, "python")
        assert p == FilePriority.CRITICAL

    def test_core_module_is_high(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("src/core/engine.py", {}, "python")
        assert p == FilePriority.HIGH

    def test_services_module_is_high(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("src/services/user_service.py", {}, "python")
        assert p == FilePriority.HIGH

    def test_models_module_is_high(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("src/models/user.py", {}, "python")
        assert p == FilePriority.HIGH

    def test_main_py_is_high(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("src/main.py", {}, "python")
        assert p == FilePriority.HIGH

    def test_test_file_is_low(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("test_something.py", {}, "python")
        assert p == FilePriority.LOW

    def test_tests_dir_is_low(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("tests/test_unit.py", {}, "python")
        assert p == FilePriority.LOW

    def test_markdown_is_low(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("docs/guide.md", {}, "unknown")
        assert p == FilePriority.LOW

    def test_readme_is_low(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("README.md", {}, "unknown")
        assert p == FilePriority.LOW

    def test_minified_js_is_skip(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("vendor/lib.min.js", {}, "javascript")
        assert p == FilePriority.SKIP

    def test_lock_file_is_skip(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("yarn.lock", {}, "unknown")
        assert p == FilePriority.SKIP

    def test_package_lock_is_skip(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("package-lock.json", {}, "unknown")
        assert p == FilePriority.SKIP

    def test_node_modules_is_skip(self):
        opt = LargePROptimizer()
        # Pattern is .*/node_modules/.* so it needs a path prefix
        p = opt._calculate_priority("vendor/node_modules/pkg/index.js", {}, "javascript")
        assert p == FilePriority.SKIP

    def test_pycache_is_skip(self):
        opt = LargePROptimizer()
        p = opt._calculate_priority("src/__pycache__/mod.cpython-311.pyc", {}, "unknown")
        assert p == FilePriority.SKIP

    def test_large_deletions_are_high(self):
        """Files with >100 deletions get HIGH priority."""
        opt = LargePROptimizer()
        p = opt._calculate_priority("src/utils.py", {"deletions": 150}, "python")
        assert p == FilePriority.HIGH

    def test_new_file_is_high(self):
        """Newly added files get HIGH priority."""
        opt = LargePROptimizer()
        p = opt._calculate_priority("src/new_feature.py", {"status": "added"}, "python")
        assert p == FilePriority.HIGH

    def test_default_is_medium(self):
        """Unmatched files with small changes default to MEDIUM."""
        opt = LargePROptimizer()
        p = opt._calculate_priority(
            "src/helper.py", {"deletions": 5, "status": "modified"}, "python"
        )
        assert p == FilePriority.MEDIUM

    def test_priority_order_critical_over_skip(self):
        """If a pattern matches both SKIP and CRITICAL, last match wins (CRITICAL checked last)."""
        opt = LargePROptimizer()
        # auth.py matches CRITICAL
        p = opt._calculate_priority("src/auth.py", {}, "python")
        assert p == FilePriority.CRITICAL


# ---------------------------------------------------------------------------
# _get_review_reason
# ---------------------------------------------------------------------------
class TestGetReviewReason:
    """Tests for _get_review_reason."""

    def test_critical_reason(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(FilePriority.CRITICAL, "Dockerfile", {})
        assert "Critical" in reason

    def test_high_reason(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(FilePriority.HIGH, "src/app.py", {})
        assert "High priority" in reason

    def test_medium_reason(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(FilePriority.MEDIUM, "src/utils.py", {})
        assert "Standard" in reason

    def test_low_reason(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(FilePriority.LOW, "test_x.py", {})
        assert "Low priority" in reason

    def test_skip_reason(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(FilePriority.SKIP, "bundle.js", {})
        assert "Skipped" in reason

    def test_new_file_annotation(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(FilePriority.HIGH, "src/new.py", {"status": "added"})
        assert "[NEW FILE]" in reason

    def test_deleted_file_annotation(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(FilePriority.HIGH, "src/old.py", {"status": "deleted"})
        assert "[DELETED]" in reason

    def test_refactoring_annotation(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(
            FilePriority.MEDIUM,
            "src/refactored.py",
            {"deletions": 50, "additions": 10},
        )
        assert "[MAJOR REFACTORING]" in reason

    def test_no_annotation_when_additions_gte_deletions(self):
        opt = LargePROptimizer()
        reason = opt._get_review_reason(
            FilePriority.MEDIUM,
            "src/balanced.py",
            {"deletions": 10, "additions": 10},
        )
        assert "[MAJOR REFACTORING]" not in reason
        assert "[NEW FILE]" not in reason
        assert "[DELETED]" not in reason


# ---------------------------------------------------------------------------
# prioritize_files
# ---------------------------------------------------------------------------
class TestPrioritizeFiles:
    """Tests for prioritize_files."""

    def test_empty_list(self):
        opt = LargePROptimizer()
        result = opt.prioritize_files([])
        assert result == []

    def test_single_file(self):
        opt = LargePROptimizer()
        files = [{"path": "src/main.py", "additions": 10, "deletions": 5, "status": "modified"}]
        result = opt.prioritize_files(files)
        assert len(result) == 1
        assert result[0].path == "src/main.py"
        assert result[0].language == "python"
        assert result[0].additions == 10
        assert result[0].deletions == 5

    def test_sorting_by_priority(self):
        """Higher priority files come first."""
        opt = LargePROptimizer()
        files = [
            {"path": "README.md", "additions": 1, "deletions": 0, "status": "modified"},
            {"path": "Dockerfile", "additions": 5, "deletions": 2, "status": "modified"},
            {"path": "src/helper.py", "additions": 3, "deletions": 1, "status": "modified"},
        ]
        result = opt.prioritize_files(files)

        # Dockerfile -> CRITICAL, helper.py -> MEDIUM, README.md -> LOW
        assert result[0].path == "Dockerfile"
        assert result[0].priority == FilePriority.CRITICAL
        assert result[-1].priority.value <= result[0].priority.value

    def test_sorting_tiebreak_by_tokens(self):
        """Files with same priority are sorted by estimated_tokens ascending."""
        opt = LargePROptimizer()
        files = [
            {"path": "src/big.py", "additions": 100, "deletions": 50, "status": "modified"},
            {"path": "src/small.py", "additions": 5, "deletions": 2, "status": "modified"},
        ]
        result = opt.prioritize_files(files)

        # Both are MEDIUM, smaller tokens first
        assert result[0].estimated_tokens <= result[1].estimated_tokens

    def test_missing_fields_default(self):
        """Missing additions/deletions/status default gracefully."""
        opt = LargePROptimizer()
        files = [{"path": "src/foo.py"}]
        result = opt.prioritize_files(files)
        assert len(result) == 1
        assert result[0].additions == 0
        assert result[0].deletions == 0
        assert result[0].change_type == "modified"

    def test_multiple_file_types(self):
        """Mix of file types are correctly detected."""
        opt = LargePROptimizer()
        files = [
            {"path": "app.js", "additions": 5, "deletions": 0},
            {"path": "server.py", "additions": 10, "deletions": 3},
            {"path": "Main.java", "additions": 20, "deletions": 10},
        ]
        result = opt.prioritize_files(files)
        languages = {fi.language for fi in result}
        assert "javascript" in languages
        assert "python" in languages
        assert "java" in languages


# ---------------------------------------------------------------------------
# select_files_for_review
# ---------------------------------------------------------------------------
class TestSelectFilesForReview:
    """Tests for select_files_for_review."""

    def _make_file_info(
        self,
        path: str = "src/file.py",
        priority: FilePriority = FilePriority.MEDIUM,
        tokens: int = 1000,
    ) -> FileInfo:
        return FileInfo(
            path=path,
            language="python",
            additions=10,
            deletions=5,
            change_type="modified",
            priority=priority,
            review_reason="test",
            estimated_tokens=tokens,
        )

    def test_empty_input(self):
        opt = LargePROptimizer()
        selected, skipped, summary = opt.select_files_for_review([])
        assert selected == []
        assert skipped == []
        assert summary["total_files"] == 0
        assert summary["files_selected"] == 0

    def test_all_files_selected_under_limits(self):
        opt = LargePROptimizer(max_tokens_per_review=100000, max_files_to_review=50)
        files = [self._make_file_info(f"src/f{i}.py", tokens=500) for i in range(5)]
        selected, skipped, summary = opt.select_files_for_review(files)

        assert len(selected) == 5
        assert len(skipped) == 0
        assert summary["files_selected"] == 5
        assert summary["tokens_selected"] == 2500

    def test_skip_below_min_priority(self):
        """Files below min_priority are skipped."""
        opt = LargePROptimizer(min_priority_for_inclusion=FilePriority.HIGH)
        files = [
            self._make_file_info("critical.py", FilePriority.CRITICAL, 500),
            self._make_file_info("high.py", FilePriority.HIGH, 500),
            self._make_file_info("medium.py", FilePriority.MEDIUM, 500),
            self._make_file_info("low.py", FilePriority.LOW, 500),
            self._make_file_info("skip.py", FilePriority.SKIP, 500),
        ]
        selected, skipped, summary = opt.select_files_for_review(files)

        assert len(selected) == 2  # CRITICAL + HIGH
        assert len(skipped) == 3
        selected_paths = {f.path for f in selected}
        assert "critical.py" in selected_paths
        assert "high.py" in selected_paths

    def test_max_files_limit(self):
        """Stop selecting after max_files."""
        opt = LargePROptimizer(max_files_to_review=3, max_tokens_per_review=1000000)
        files = [self._make_file_info(f"src/f{i}.py", tokens=100) for i in range(10)]
        selected, skipped, summary = opt.select_files_for_review(files)

        assert len(selected) == 3
        assert len(skipped) == 7
        assert summary["files_selected"] == 3

    def test_max_tokens_limit(self):
        """Stop selecting when tokens would exceed limit."""
        opt = LargePROptimizer(max_tokens_per_review=2500, max_files_to_review=100)
        files = [self._make_file_info(f"src/f{i}.py", tokens=1000) for i in range(5)]
        selected, skipped, summary = opt.select_files_for_review(files)

        assert len(selected) == 2  # 2 * 1000 = 2000 <= 2500; 3rd would be 3000 > 2500
        assert len(skipped) == 3
        assert summary["tokens_selected"] == 2000

    def test_skipped_reason_max_files(self):
        """Skipped files get reason annotation for max files."""
        opt = LargePROptimizer(max_files_to_review=1, max_tokens_per_review=1000000)
        files = [
            self._make_file_info("first.py", tokens=100),
            self._make_file_info("second.py", tokens=100),
        ]
        selected, skipped, summary = opt.select_files_for_review(files)

        assert len(skipped) == 1
        assert "max 1 files" in skipped[0].review_reason

    def test_skipped_reason_max_tokens(self):
        """Skipped files get reason annotation for token limit."""
        opt = LargePROptimizer(max_tokens_per_review=500, max_files_to_review=100)
        files = [
            self._make_file_info("small.py", tokens=400),
            self._make_file_info("big.py", tokens=600),
        ]
        selected, skipped, summary = opt.select_files_for_review(files)

        assert len(skipped) == 1
        assert "token limit" in skipped[0].review_reason

    def test_summary_has_priority_breakdown(self):
        opt = LargePROptimizer()
        files = [
            self._make_file_info("a.py", FilePriority.CRITICAL, 500),
            self._make_file_info("b.py", FilePriority.HIGH, 500),
            self._make_file_info("c.py", FilePriority.MEDIUM, 500),
        ]
        selected, skipped, summary = opt.select_files_for_review(files)

        bd = summary["priority_breakdown"]
        assert bd.get("CRITICAL") == 1
        assert bd.get("HIGH") == 1
        assert bd.get("MEDIUM") == 1

    def test_summary_has_language_breakdown(self):
        opt = LargePROptimizer()
        fi1 = self._make_file_info("a.py", tokens=500)
        fi1.language = "python"
        fi2 = self._make_file_info("b.py", tokens=500)
        fi2.language = "javascript"
        selected, skipped, summary = opt.select_files_for_review([fi1, fi2])

        lb = summary["language_breakdown"]
        assert lb.get("python") == 1
        assert lb.get("javascript") == 1


# ---------------------------------------------------------------------------
# _get_priority_breakdown / _get_language_breakdown
# ---------------------------------------------------------------------------
class TestBreakdownHelpers:
    """Tests for breakdown helper methods."""

    def test_priority_breakdown_empty(self):
        opt = LargePROptimizer()
        result = opt._get_priority_breakdown([])
        assert result == {}

    def test_priority_breakdown_counts(self):
        opt = LargePROptimizer()
        files = [
            FileInfo("a", "py", 1, 0, "m", FilePriority.HIGH, "", 0),
            FileInfo("b", "py", 1, 0, "m", FilePriority.HIGH, "", 0),
            FileInfo("c", "py", 1, 0, "m", FilePriority.LOW, "", 0),
        ]
        result = opt._get_priority_breakdown(files)
        assert result == {"HIGH": 2, "LOW": 1}

    def test_language_breakdown_empty(self):
        opt = LargePROptimizer()
        result = opt._get_language_breakdown([])
        assert result == {}

    def test_language_breakdown_counts(self):
        opt = LargePROptimizer()
        files = [
            FileInfo("a", "python", 1, 0, "m", FilePriority.MEDIUM, "", 0),
            FileInfo("b", "python", 1, 0, "m", FilePriority.MEDIUM, "", 0),
            FileInfo("c", "go", 1, 0, "m", FilePriority.MEDIUM, "", 0),
        ]
        result = opt._get_language_breakdown(files)
        assert result == {"python": 2, "go": 1}


# ---------------------------------------------------------------------------
# chunk_large_files
# ---------------------------------------------------------------------------
class TestChunkLargeFiles:
    """Tests for chunk_large_files."""

    def _make_fi(self, path: str = "src/file.py") -> FileInfo:
        return FileInfo(
            path=path,
            language="python",
            additions=100,
            deletions=50,
            change_type="modified",
            priority=FilePriority.MEDIUM,
            review_reason="test",
            estimated_tokens=5000,
        )

    def test_small_file_single_chunk(self):
        """Content smaller than chunk_size returns one full-file chunk."""
        opt = LargePROptimizer()
        fi = self._make_fi()
        content = "line1\nline2\nline3"

        chunks = opt.chunk_large_files(fi, content, chunk_size=5000)

        assert len(chunks) == 1
        assert chunks[0]["is_full_file"] is True
        assert chunks[0]["content"] == content
        assert chunks[0]["start_line"] == 1
        assert chunks[0]["end_line"] == 3

    def test_exact_chunk_size_single_chunk(self):
        """Content exactly at chunk_size returns one chunk."""
        opt = LargePROptimizer()
        fi = self._make_fi()
        content = "x" * 100

        chunks = opt.chunk_large_files(fi, content, chunk_size=100)

        assert len(chunks) == 1
        assert chunks[0]["is_full_file"] is True

    def test_large_file_multiple_chunks(self):
        """Content larger than chunk_size is split into multiple chunks."""
        opt = LargePROptimizer()
        fi = self._make_fi()
        # Create content that is clearly larger than chunk_size
        lines = [f"line {i}: " + "x" * 40 for i in range(100)]
        content = "\n".join(lines)

        chunks = opt.chunk_large_files(fi, content, chunk_size=200)

        assert len(chunks) > 1
        # First chunk should not be full file
        assert chunks[0]["is_full_file"] is False
        # Last chunk
        assert chunks[-1]["end_line"] == 100
        # All chunks should have file_info reference
        for chunk in chunks:
            assert chunk["file_info"] is fi

    def test_chunks_cover_all_lines(self):
        """Chunks should cover every line without gaps."""
        opt = LargePROptimizer()
        fi = self._make_fi()
        lines = [f"line{i}" + "x" * 50 for i in range(50)]
        content = "\n".join(lines)

        chunks = opt.chunk_large_files(fi, content, chunk_size=200)

        # Verify continuity
        assert chunks[0]["start_line"] == 1
        for i in range(1, len(chunks)):
            assert chunks[i]["start_line"] == chunks[i - 1]["end_line"] + 1

    def test_empty_content(self):
        """Empty string produces a single chunk."""
        opt = LargePROptimizer()
        fi = self._make_fi()
        chunks = opt.chunk_large_files(fi, "", chunk_size=100)

        assert len(chunks) == 1
        assert chunks[0]["is_full_file"] is True
        assert chunks[0]["content"] == ""

    def test_single_long_line(self):
        """A single line longer than chunk_size still appears in a chunk."""
        opt = LargePROptimizer()
        fi = self._make_fi()
        content = "x" * 10000

        chunks = opt.chunk_large_files(fi, content, chunk_size=500)

        # The single line will form one chunk (since there's no prior chunk to flush)
        assert len(chunks) == 1
        assert chunks[0]["content"] == content

    def test_last_chunk_full_file_flag(self):
        """If there is only one chunk produced, is_full_file is True for the last chunk."""
        opt = LargePROptimizer()
        fi = self._make_fi()
        content = "short content"

        chunks = opt.chunk_large_files(fi, content, chunk_size=5000)

        assert chunks[-1]["is_full_file"] is True


# ---------------------------------------------------------------------------
# generate_review_summary
# ---------------------------------------------------------------------------
class TestGenerateReviewSummary:
    """Tests for generate_review_summary."""

    def _make_fi(
        self,
        path: str = "src/file.py",
        priority: FilePriority = FilePriority.MEDIUM,
        tokens: int = 1000,
        reason: str = "Standard file",
    ) -> FileInfo:
        return FileInfo(
            path=path,
            language="python",
            additions=10,
            deletions=5,
            change_type="modified",
            priority=priority,
            review_reason=reason,
            estimated_tokens=tokens,
        )

    def test_no_skipped_files(self):
        opt = LargePROptimizer()
        selected = [self._make_fi("a.py"), self._make_fi("b.py")]
        skipped: list[FileInfo] = []

        text = opt.generate_review_summary(selected, skipped)

        assert "Files reviewed:** 2" in text
        assert "Files skipped:** 0" in text
        assert "Skipped files:" not in text

    def test_with_skipped_files(self):
        opt = LargePROptimizer()
        selected = [self._make_fi("a.py")]
        skipped = [self._make_fi("b.py", reason="Skipped (lock file)")]

        text = opt.generate_review_summary(selected, skipped)

        assert "Files skipped:** 1" in text
        assert "Skipped files:" in text
        assert "`b.py`" in text

    def test_more_than_10_skipped(self):
        """Only first 10 skipped files shown, with a '... and N more' line."""
        opt = LargePROptimizer()
        selected = [self._make_fi("a.py")]
        skipped = [self._make_fi(f"skip{i}.py") for i in range(15)]

        text = opt.generate_review_summary(selected, skipped)

        assert "... and 5 more" in text

    def test_exactly_10_skipped(self):
        """With exactly 10 skipped, no '... and N more' line."""
        opt = LargePROptimizer()
        selected = [self._make_fi("a.py")]
        skipped = [self._make_fi(f"skip{i}.py") for i in range(10)]

        text = opt.generate_review_summary(selected, skipped)

        assert "... and" not in text

    def test_estimated_tokens_in_summary(self):
        opt = LargePROptimizer()
        selected = [self._make_fi("a.py", tokens=5000)]
        text = opt.generate_review_summary(selected, [])
        assert "5,000" in text

    def test_empty_review(self):
        opt = LargePROptimizer()
        text = opt.generate_review_summary([], [])
        assert "Files reviewed:** 0" in text

    def test_note_always_present(self):
        opt = LargePROptimizer()
        text = opt.generate_review_summary([], [])
        assert "automatically optimized" in text


# ---------------------------------------------------------------------------
# Module-level functions
# ---------------------------------------------------------------------------
class TestModuleFunctions:
    """Tests for init_optimizer and get_optimizer."""

    def test_init_optimizer_defaults(self):
        old = opt_mod._optimizer
        try:
            result = init_optimizer()
            assert isinstance(result, LargePROptimizer)
            assert result.max_tokens == 100000
            assert result.max_files == 50
            assert get_optimizer() is result
        finally:
            opt_mod._optimizer = old

    def test_init_optimizer_custom(self):
        old = opt_mod._optimizer
        try:
            result = init_optimizer(max_tokens_per_review=50000, max_files_to_review=25)
            assert result.max_tokens == 50000
            assert result.max_files == 25
            assert get_optimizer() is result
        finally:
            opt_mod._optimizer = old

    def test_get_optimizer_before_init(self):
        old = opt_mod._optimizer
        try:
            opt_mod._optimizer = None
            assert get_optimizer() is None
        finally:
            opt_mod._optimizer = old


# ---------------------------------------------------------------------------
# Integration-style: prioritize_files -> select_files_for_review
# ---------------------------------------------------------------------------
class TestPrioritizeAndSelectIntegration:
    """Integration test combining prioritize_files and select_files_for_review."""

    def test_full_pipeline(self):
        opt = LargePROptimizer(max_tokens_per_review=50000, max_files_to_review=10)

        raw_files = [
            {"path": "Dockerfile", "additions": 3, "deletions": 1, "status": "modified"},
            {"path": "src/core/engine.py", "additions": 50, "deletions": 20, "status": "modified"},
            {"path": "src/utils.py", "additions": 10, "deletions": 5, "status": "modified"},
            {"path": "README.md", "additions": 2, "deletions": 0, "status": "modified"},
            {"path": "package-lock.json", "additions": 500, "deletions": 200, "status": "modified"},
            {"path": "src/new_module.py", "additions": 80, "deletions": 0, "status": "added"},
        ]

        prioritized = opt.prioritize_files(raw_files)
        assert len(prioritized) == 6

        # Verify order: CRITICAL first
        assert prioritized[0].priority == FilePriority.CRITICAL

        selected, skipped, summary = opt.select_files_for_review(prioritized)

        # SKIP files should be skipped, LOW may be skipped depending on min_priority
        skipped_paths = {f.path for f in skipped}
        assert "package-lock.json" in skipped_paths  # SKIP priority

        # README.md is LOW, below default MEDIUM threshold
        assert "README.md" in skipped_paths

        # Core files should be selected
        selected_paths = {f.path for f in selected}
        assert "Dockerfile" in selected_paths
        assert "src/core/engine.py" in selected_paths

        assert summary["total_files"] == 6
        assert summary["files_selected"] + summary["files_skipped"] == 6
