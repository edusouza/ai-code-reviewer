"""LangGraph workflow components."""

# Avoid circular imports by using lazy loading
__all__ = [
    "ReviewState",
    "ChunkInfo",
    "Suggestion",
    "ReviewConfig",
    "ReviewMetadata",
    "build_review_graph",
    "create_review_workflow",
    "FirestoreCheckpointer",
]


def __getattr__(name: str) -> object:  # noqa: PLR0911
    if name in ["ReviewState", "ChunkInfo", "Suggestion", "ReviewConfig", "ReviewMetadata"]:
        from src.graph.state import (  # noqa: F401
            ChunkInfo,
            ReviewConfig,
            ReviewMetadata,
            ReviewState,
            Suggestion,
        )

        return locals()[name]
    elif name in ["build_review_graph", "create_review_workflow"]:
        from src.graph.builder import (  # noqa: F401
            build_review_graph,
            create_review_workflow,
        )

        return locals()[name]
    elif name == "FirestoreCheckpointer":
        from src.graph.checkpointer import FirestoreCheckpointer  # noqa: F401

        return FirestoreCheckpointer
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
