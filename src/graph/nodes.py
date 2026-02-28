import asyncio
from datetime import UTC, datetime
from typing import Any

from src.agents.factory import AgentFactory
from src.graph.state import ChunkInfo, ReviewMetadata, ReviewState, Suggestion
from src.models.events import ReviewComment
from src.providers.factory import ProviderFactory
from src.suggestions.deduplicator import Deduplicator
from src.suggestions.severity import SeverityClassifier


async def ingest_pr_node(state: ReviewState) -> dict[str, Any]:
    """Fetch PR diff and AGENTS.md from the provider."""
    try:
        pr_event = state["pr_event"]
        provider = ProviderFactory.get_provider(pr_event.provider)

        # Fetch PR diff
        pr_diff = await provider.get_pr_diff(
            pr_event.repo_owner, pr_event.repo_name, pr_event.pr_number
        )

        # Fetch AGENTS.md if exists
        try:
            agnets_md = await provider.get_file_content(
                pr_event.repo_owner, pr_event.repo_name, "AGENTS.md", pr_event.commit_sha
            )
        except Exception:
            agnets_md = None

        # Initialize metadata
        metadata: ReviewMetadata = {
            "review_id": f"{pr_event.provider}_{pr_event.repo_owner}_{pr_event.repo_name}_{pr_event.pr_number}_{datetime.now(UTC).timestamp()}",
            "started_at": datetime.now(UTC),
            "completed_at": None,
            "current_step": "ingest_pr",
            "agent_results": {},
            "error_count": 0,
        }

        # Initialize config if not present
        review_config = state.get("config")
        if not review_config:
            review_config = {
                "max_suggestions": 50,
                "severity_threshold": "suggestion",
                "enable_agents": {"security": True, "style": True, "logic": True, "pattern": True},
                "custom_rules": {},
            }

        return {
            "pr_diff": pr_diff,
            "agnets_md": agnets_md,
            "metadata": metadata,
            "config": review_config,
            "current_chunk_index": 0,
            "chunks": [],
            "suggestions": [],
            "raw_agent_outputs": {},
            "validated_suggestions": [],
            "rejected_suggestions": [],
            "comments": [],
            "error": None,
            "should_stop": False,
        }

    except Exception as e:
        return {"error": f"Failed to ingest PR: {str(e)}", "should_stop": True}


async def chunk_analyzer_node(state: ReviewState) -> dict[str, Any]:
    """Split large PRs into manageable chunks."""
    try:
        pr_diff = state.get("pr_diff", "")

        if not pr_diff:
            return {"should_stop": True, "error": "No PR diff to analyze"}

        # Parse diff and create chunks
        chunks: list[ChunkInfo] = []
        current_file = ""
        current_content: list[str] = []
        current_start = 0

        for line in pr_diff.split("\n"):
            if line.startswith("diff --git"):
                # Save previous chunk
                if current_file and current_content:
                    chunks.append(
                        {
                            "file_path": current_file,
                            "start_line": current_start,
                            "end_line": current_start + len(current_content) - 1,
                            "content": "\n".join(current_content),
                            "language": _detect_language(current_file),
                        }
                    )

                # Start new file
                parts = line.split(" ")
                if len(parts) >= 3:
                    current_file = parts[2][2:]  # Remove "b/" prefix
                current_content = []
                current_start = 0

            elif line.startswith("@@"):
                # Extract line number from hunk header
                try:
                    line_info = line.split("@@")[1].strip()
                    current_start = int(line_info.split("+")[1].split(",")[0])
                except (IndexError, ValueError):  # fmt: skip
                    pass
                current_content.append(line)

            elif line.startswith("+") or line.startswith("-"):
                current_content.append(line)

        # Save last chunk
        if current_file and current_content:
            chunks.append(
                {
                    "file_path": current_file,
                    "start_line": current_start,
                    "end_line": current_start + len(current_content) - 1,
                    "content": "\n".join(current_content),
                    "language": _detect_language(current_file),
                }
            )

        # Update metadata
        metadata = state["metadata"]
        metadata["current_step"] = "chunk_analyzer"

        return {"chunks": chunks, "metadata": metadata}

    except Exception as e:
        return {"error": f"Failed to analyze chunks: {str(e)}", "should_stop": True}


def _detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
    }

    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    return "unknown"


async def parallel_agents_node(state: ReviewState) -> dict[str, Any]:
    """Run all 4 agents concurrently on the current chunk."""
    try:
        chunks = state.get("chunks", [])
        current_index = state.get("current_chunk_index", 0)

        if current_index >= len(chunks):
            return {"should_stop": True}

        chunk = chunks[current_index]
        config = state["config"]
        agnets_md = state.get("agnets_md")

        # Create agent factory
        factory = AgentFactory()
        agents = []

        if config["enable_agents"].get("security", True):
            agents.append(factory.create_agent("security"))
        if config["enable_agents"].get("style", True):
            agents.append(factory.create_agent("style"))
        if config["enable_agents"].get("logic", True):
            agents.append(factory.create_agent("logic"))
        if config["enable_agents"].get("pattern", True):
            agents.append(factory.create_agent("pattern"))

        # Run agents concurrently
        context = {
            "agnets_md": agnets_md,
            "config": config,
            "chunk_index": current_index,
            "total_chunks": len(chunks),
        }

        tasks = [agent.analyze(chunk, context) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect suggestions
        all_suggestions: list[Suggestion] = []
        raw_outputs = state.get("raw_agent_outputs", {}).copy()

        for _i, (agent, result) in enumerate(zip(agents, results, strict=False)):
            if isinstance(result, Exception):
                # Log error but continue
                continue

            agent_type = agent.__class__.__name__.lower().replace("agent", "")
            # At this point, result is not an Exception (we continued above)
            # but mypy doesn't know that, so we cast it
            from typing import cast

            typed_result = cast(list[Suggestion], result)
            raw_outputs[agent_type] = typed_result
            all_suggestions.extend(typed_result)

        # Update metadata
        metadata = state["metadata"]
        metadata["current_step"] = "parallel_agents"
        metadata["agent_results"][f"chunk_{current_index}"] = {
            "agents_run": len(agents),
            "suggestions_found": len(all_suggestions),
        }

        return {
            "suggestions": state.get("suggestions", []) + all_suggestions,
            "raw_agent_outputs": raw_outputs,
            "current_chunk_index": current_index + 1,
            "metadata": metadata,
        }

    except Exception as e:
        return {
            "error": f"Failed to run agents: {str(e)}",
            "current_chunk_index": state.get("current_chunk_index", 0)
            + 1,  # Continue to next chunk
        }


async def aggregate_results_node(state: ReviewState) -> dict[str, Any]:
    """Merge agent outputs and deduplicate suggestions."""
    try:
        suggestions = state.get("suggestions", [])

        # Deduplicate
        deduplicator = Deduplicator()
        unique_suggestions = deduplicator.deduplicate(suggestions)

        # Update metadata
        metadata = state["metadata"]
        metadata["current_step"] = "aggregate"

        return {"suggestions": unique_suggestions, "metadata": metadata}

    except Exception as e:
        return {"error": f"Failed to aggregate results: {str(e)}"}


async def severity_filter_node(state: ReviewState) -> dict[str, Any]:
    """Apply severity limits and filter suggestions."""
    try:
        suggestions = state.get("suggestions", [])
        config = state["config"]

        # Classify and filter by severity
        classifier = SeverityClassifier()
        filtered = classifier.filter_by_threshold(
            suggestions, config.get("severity_threshold", "suggestion")
        )

        # Apply max suggestions limit
        max_suggestions = config.get("max_suggestions", 50)
        filtered = filtered[:max_suggestions]

        # Update metadata
        metadata = state["metadata"]
        metadata["current_step"] = "severity_filter"

        return {"suggestions": filtered, "metadata": metadata}

    except Exception as e:
        return {"error": f"Failed to filter by severity: {str(e)}"}


async def llm_judge_node(state: ReviewState) -> dict[str, Any]:
    """Validate suggestions using LLM-as-judge."""
    try:
        suggestions = state.get("suggestions", [])

        if not suggestions:
            return {"validated_suggestions": [], "rejected_suggestions": []}

        # Use LLM judge to validate
        from src.llm.judge import LLMJudge

        judge = LLMJudge()

        validated = []
        rejected = []

        for suggestion in suggestions:
            is_valid = await judge.validate_suggestion(suggestion)
            if is_valid:
                validated.append(suggestion)
            else:
                rejected.append(suggestion)

        # Update metadata
        metadata = state["metadata"]
        metadata["current_step"] = "llm_judge"

        return {
            "validated_suggestions": validated,
            "rejected_suggestions": rejected,
            "suggestions": validated,  # Use validated for downstream
            "metadata": metadata,
        }

    except Exception as e:
        return {
            "error": f"Failed to validate suggestions: {str(e)}",
            "validated_suggestions": state.get("suggestions", []),
            "rejected_suggestions": [],
        }


async def publish_comments_node(state: ReviewState) -> dict[str, Any]:
    """Post review comments to the provider."""
    try:
        pr_event = state["pr_event"]
        suggestions = state.get("validated_suggestions", state.get("suggestions", []))

        # Convert suggestions to ReviewComment format
        comments: list[ReviewComment] = []
        for suggestion in suggestions:
            comments.append(
                ReviewComment(
                    file_path=suggestion["file_path"],
                    line_number=suggestion["line_number"],
                    message=suggestion["message"],
                    severity=suggestion["severity"],
                    suggestion=suggestion.get("suggestion"),
                )
            )

        # Post to provider
        provider = ProviderFactory.get_provider(pr_event.provider)
        await provider.post_review_comments(
            pr_event.repo_owner, pr_event.repo_name, pr_event.pr_number, comments
        )

        # Update metadata
        metadata = state["metadata"]
        metadata["current_step"] = "publish"
        metadata["completed_at"] = datetime.now(UTC)

        # Create summary
        summary = _create_summary(comments)
        passed = len([c for c in comments if c.severity == "error"]) == 0

        return {"comments": comments, "summary": summary, "passed": passed, "metadata": metadata}

    except Exception as e:
        return {"error": f"Failed to publish comments: {str(e)}", "should_stop": True}


def _create_summary(comments: list[ReviewComment]) -> str:
    """Create a summary of the review."""
    error_count = sum(1 for c in comments if c.severity == "error")
    warning_count = sum(1 for c in comments if c.severity == "warning")
    suggestion_count = sum(1 for c in comments if c.severity == "suggestion")

    lines = [
        "## AI Code Review Summary",
        "",
        f"- **Errors:** {error_count}",
        f"- **Warnings:** {warning_count}",
        f"- **Suggestions:** {suggestion_count}",
        "",
    ]

    if error_count > 0:
        lines.append("⚠️ Please address the errors before merging.")
    elif warning_count > 0:
        lines.append("⚡ Please consider addressing the warnings.")
    else:
        lines.append("✅ All checks passed!")

    return "\n".join(lines)
