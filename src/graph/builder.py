from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from src.graph.nodes import (
    aggregate_results_node,
    chunk_analyzer_node,
    ingest_pr_node,
    llm_judge_node,
    parallel_agents_node,
    publish_comments_node,
    severity_filter_node,
)
from src.graph.state import ReviewState


def should_continue_chunks(state: ReviewState) -> str:
    """Determine if we should continue processing chunks."""
    if state.get("should_stop", False):
        return "aggregate"

    current_index = state.get("current_chunk_index", 0)
    total_chunks = len(state.get("chunks", []))

    if current_index < total_chunks:
        return "parallel_agents"
    return "aggregate"


def has_suggestions(state: ReviewState) -> str:
    """Determine if there are suggestions to process."""
    suggestions = state.get("suggestions", [])
    if not suggestions or state.get("should_stop", False):
        return "publish"
    return "severity_filter"


def should_publish(state: ReviewState) -> str:
    """Determine if we should publish comments."""
    if state.get("error") or state.get("should_stop", False):
        return END
    return "publish"


def build_review_graph(checkpointer: BaseCheckpointSaver = None) -> Any:
    """Build and return the review workflow graph."""

    # Create the graph
    workflow = StateGraph(ReviewState)

    # Add nodes
    workflow.add_node("ingest_pr", ingest_pr_node)
    workflow.add_node("chunk_analyzer", chunk_analyzer_node)
    workflow.add_node("parallel_agents", parallel_agents_node)
    workflow.add_node("aggregate", aggregate_results_node)
    workflow.add_node("severity_filter", severity_filter_node)
    workflow.add_node("llm_judge", llm_judge_node)
    workflow.add_node("publish", publish_comments_node)

    # Define edges
    workflow.set_entry_point("ingest_pr")
    workflow.add_edge("ingest_pr", "chunk_analyzer")
    workflow.add_edge("chunk_analyzer", "parallel_agents")

    # Conditional edge: process all chunks or move to aggregate
    workflow.add_conditional_edges(
        "parallel_agents",
        should_continue_chunks,
        {
            "parallel_agents": "parallel_agents",  # Loop back for next chunk
            "aggregate": "aggregate",
        },
    )

    # Conditional edge: check if we have suggestions
    workflow.add_conditional_edges(
        "aggregate", has_suggestions, {"severity_filter": "severity_filter", "publish": "publish"}
    )

    workflow.add_edge("severity_filter", "llm_judge")
    workflow.add_edge("llm_judge", "publish")

    # Conditional edge: check if we should end
    workflow.add_conditional_edges("publish", should_publish, {END: END})

    # Compile with checkpointer if provided
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()


def create_review_workflow(thread_id: str, checkpointer: BaseCheckpointSaver = None) -> Any:
    """Create a configured review workflow."""
    graph = build_review_graph(checkpointer)

    return {"graph": graph, "config": {"configurable": {"thread_id": thread_id}}}
