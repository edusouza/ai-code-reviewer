"""Decorators for tracing workflows, agents, and LLM calls."""

import functools
import inspect
import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from observability.langfuse_client import current_span_id, current_trace_id, get_langfuse

logger = logging.getLogger(__name__)


def trace_workflow(name: str | None = None):
    """
    Decorator to trace an entire workflow.

    Args:
        name: Trace name (defaults to function name)

    Usage:
        @trace_workflow("code_review")
        async def review_pr(pr_event):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            langfuse = get_langfuse()
            trace_name = name or func.__name__

            # Extract metadata from arguments
            metadata = _extract_metadata(func, args, kwargs)

            # Create trace
            trace_id = None
            if langfuse:
                trace_id = langfuse.create_trace(name=trace_name, metadata=metadata)

            try:
                # Execute function
                result = await func(*args, **kwargs)

                # End trace successfully
                if langfuse and trace_id:
                    langfuse.end_trace(
                        trace_id=trace_id,
                        output=_safe_serialize(result),
                        metadata={"status": "success"},
                    )

                return result

            except Exception as e:
                # End trace with error
                if langfuse and trace_id:
                    langfuse.end_trace(
                        trace_id=trace_id, metadata={"status": "error", "error": str(e)}
                    )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            langfuse = get_langfuse()
            trace_name = name or func.__name__

            metadata = _extract_metadata(func, args, kwargs)

            trace_id = None
            if langfuse:
                trace_id = langfuse.create_trace(name=trace_name, metadata=metadata)

            try:
                result = func(*args, **kwargs)

                if langfuse and trace_id:
                    langfuse.end_trace(
                        trace_id=trace_id,
                        output=_safe_serialize(result),
                        metadata={"status": "success"},
                    )

                return result

            except Exception as e:
                if langfuse and trace_id:
                    langfuse.end_trace(
                        trace_id=trace_id, metadata={"status": "error", "error": str(e)}
                    )
                raise

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def trace_agent(name: str | None = None, agent_type: str | None = None):
    """
    Decorator to trace agent execution.

    Args:
        name: Span name (defaults to function name)
        agent_type: Type of agent (e.g., 'security', 'style')

    Usage:
        @trace_agent(name="security_check", agent_type="security")
        async def analyze_security(chunk, context):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            langfuse = get_langfuse()
            span_name = name or func.__name__

            # Get current trace/span IDs
            trace_id = current_trace_id.get()
            parent_span_id = current_span_id.get()

            metadata = {"agent_type": agent_type or "unknown", "function": func.__name__}

            # Extract input data
            input_data = _extract_input_data(args, kwargs)

            span_id = None
            if langfuse:
                span_id = langfuse.create_span(
                    name=span_name,
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                    metadata=metadata,
                    input_data=input_data,
                )

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)

                duration = time.time() - start_time

                if langfuse and span_id:
                    langfuse.update_span(
                        span_id=span_id,
                        output=_safe_serialize(result),
                        metadata={
                            "duration_seconds": duration,
                            "suggestions_count": len(result) if isinstance(result, list) else 0,
                        },
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time

                if langfuse and span_id:
                    langfuse.update_span(
                        span_id=span_id,
                        metadata={"error": str(e), "duration_seconds": duration},
                        level="ERROR",
                        status_message=str(e),
                    )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            langfuse = get_langfuse()
            span_name = name or func.__name__

            trace_id = current_trace_id.get()
            parent_span_id = current_span_id.get()

            metadata = {"agent_type": agent_type or "unknown", "function": func.__name__}

            input_data = _extract_input_data(args, kwargs)

            span_id = None
            if langfuse:
                span_id = langfuse.create_span(
                    name=span_name,
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                    metadata=metadata,
                    input_data=input_data,
                )

            start_time = time.time()
            try:
                result = func(*args, **kwargs)

                duration = time.time() - start_time

                if langfuse and span_id:
                    langfuse.update_span(
                        span_id=span_id,
                        output=_safe_serialize(result),
                        metadata={"duration_seconds": duration},
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time

                if langfuse and span_id:
                    langfuse.update_span(
                        span_id=span_id,
                        metadata={"error": str(e), "duration_seconds": duration},
                        level="ERROR",
                    )
                raise

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def trace_llm(model_name: str | None = None):
    """
    Decorator to trace LLM calls.

    Args:
        model_name: Name of the LLM model being used

    Usage:
        @trace_llm(model_name="gemini-pro")
        async def generate_response(prompt):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            langfuse = get_langfuse()

            trace_id = current_trace_id.get()
            parent_span_id = current_span_id.get()

            # Extract prompt and parameters
            prompt = _extract_prompt(args, kwargs)
            generation_params = _extract_generation_params(kwargs)

            span_id = None
            if langfuse:
                span_id = langfuse.create_span(
                    name=f"llm_call_{model_name or 'unknown'}",
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                    metadata={
                        "model": model_name or "unknown",
                        "type": "llm_generation",
                        **generation_params,
                    },
                    input_data={"prompt": prompt[:1000] if prompt else None},  # Truncate for size
                )

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)

                duration = time.time() - start_time

                # Extract token usage if available
                token_usage = _extract_token_usage(result)

                if langfuse and span_id:
                    langfuse.update_span(
                        span_id=span_id,
                        output=_safe_serialize(result)[:1000],  # Truncate for size
                        metadata={
                            "duration_seconds": duration,
                            "completion_tokens": token_usage.get("completion_tokens"),
                            "prompt_tokens": token_usage.get("prompt_tokens"),
                            "total_tokens": token_usage.get("total_tokens"),
                        },
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time

                if langfuse and span_id:
                    langfuse.update_span(
                        span_id=span_id,
                        metadata={"error": str(e), "duration_seconds": duration},
                        level="ERROR",
                    )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            langfuse = get_langfuse()

            trace_id = current_trace_id.get()
            parent_span_id = current_span_id.get()

            prompt = _extract_prompt(args, kwargs)
            generation_params = _extract_generation_params(kwargs)

            span_id = None
            if langfuse:
                span_id = langfuse.create_span(
                    name=f"llm_call_{model_name or 'unknown'}",
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                    metadata={
                        "model": model_name or "unknown",
                        "type": "llm_generation",
                        **generation_params,
                    },
                    input_data={"prompt": prompt[:1000] if prompt else None},
                )

            start_time = time.time()
            try:
                result = func(*args, **kwargs)

                duration = time.time() - start_time
                token_usage = _extract_token_usage(result)

                if langfuse and span_id:
                    langfuse.update_span(
                        span_id=span_id,
                        output=_safe_serialize(result)[:1000],
                        metadata={"duration_seconds": duration, **token_usage},
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time

                if langfuse and span_id:
                    langfuse.update_span(
                        span_id=span_id,
                        metadata={"error": str(e), "duration_seconds": duration},
                        level="ERROR",
                    )
                raise

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


@contextmanager
def trace_span(name: str, metadata: dict[str, Any] | None = None):
    """
    Context manager for creating a span.

    Usage:
        with trace_span("database_query", {"table": "users"}):
            result = db.query(...)
    """
    langfuse = get_langfuse()
    trace_id = current_trace_id.get()
    parent_span_id = current_span_id.get()

    span_id = None
    if langfuse:
        span_id = langfuse.create_span(
            name=name, trace_id=trace_id, parent_span_id=parent_span_id, metadata=metadata or {}
        )

    try:
        yield span_id
        if langfuse and span_id:
            langfuse.update_span(span_id=span_id)
    except Exception as e:
        if langfuse and span_id:
            langfuse.update_span(span_id=span_id, level="ERROR", status_message=str(e))
        raise


def _extract_metadata(func: Callable, args: tuple, kwargs: dict) -> dict[str, Any]:
    """Extract metadata from function arguments."""
    metadata: dict[str, Any] = {"function": func.__name__, "module": func.__module__}

    # Try to extract PR info from first argument
    if args and hasattr(args[0], "provider"):
        obj = args[0]
        metadata["provider"] = getattr(obj, "provider", None)
        repo_owner = getattr(obj, "repo_owner", "") or ""
        repo_name = getattr(obj, "repo_name", "") or ""
        metadata["repo"] = f"{repo_owner}/{repo_name}"
        metadata["pr_number"] = getattr(obj, "pr_number", None)

    return metadata


def _extract_input_data(args: tuple, kwargs: dict) -> dict[str, Any] | None:
    """Extract input data from function arguments."""
    data = {}

    if args:
        first_arg = args[0]
        if hasattr(first_arg, "file_path"):
            data["file_path"] = first_arg.file_path
        if hasattr(first_arg, "language"):
            data["language"] = first_arg.language

    return data if data else None


def _extract_prompt(args: tuple, kwargs: dict) -> str | None:
    """Extract prompt from LLM call arguments."""
    # Common argument names for prompts
    prompt_keys = ["prompt", "messages", "content", "input", "text"]

    # Check kwargs
    for key in prompt_keys:
        if key in kwargs:
            return str(kwargs[key])

    # Check args (usually first positional arg)
    if args and isinstance(args[0], str):
        return args[0]

    return None


def _extract_generation_params(kwargs: dict) -> dict[str, Any]:
    """Extract generation parameters from kwargs."""
    params = {}
    param_keys = ["temperature", "max_tokens", "top_p", "top_k", "model"]

    for key in param_keys:
        if key in kwargs:
            params[key] = kwargs[key]

    return params


def _extract_token_usage(result: Any) -> dict[str, int | None]:
    """Extract token usage information from result."""
    usage: dict[str, int | None] = {
        "completion_tokens": None,
        "prompt_tokens": None,
        "total_tokens": None,
    }

    if hasattr(result, "usage"):
        usage_obj = result.usage
        if hasattr(usage_obj, "completion_tokens"):
            usage["completion_tokens"] = usage_obj.completion_tokens
        if hasattr(usage_obj, "prompt_tokens"):
            usage["prompt_tokens"] = usage_obj.prompt_tokens
        if hasattr(usage_obj, "total_tokens"):
            usage["total_tokens"] = usage_obj.total_tokens
    elif isinstance(result, dict):
        usage["completion_tokens"] = result.get("completion_tokens")
        usage["prompt_tokens"] = result.get("prompt_tokens")
        usage["total_tokens"] = result.get("total_tokens")

    return usage


def _safe_serialize(obj: Any) -> Any:
    """Safely serialize an object for tracing."""
    try:
        if hasattr(obj, "dict"):
            return obj.dict()
        elif hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return str(obj)
    except Exception:
        return str(obj)
