"""AI agents for code review."""

# Avoid circular imports by not importing everything at module level
# Import specific agents only when needed

__all__ = [
    "BaseAgent",
    "SecurityAgent",
    "StyleAgent",
    "LogicAgent",
    "PatternAgent",
    "AgentFactory",
]


# Lazy imports to prevent circular dependency issues
def __getattr__(name: str) -> object:
    if name == "BaseAgent":
        from src.agents.base import BaseAgent

        return BaseAgent
    elif name == "AgentFactory":
        from src.agents.factory import AgentFactory

        return AgentFactory
    elif name == "LogicAgent":
        from src.agents.logic import LogicAgent

        return LogicAgent
    elif name == "PatternAgent":
        from src.agents.pattern import PatternAgent

        return PatternAgent
    elif name == "SecurityAgent":
        from src.agents.security import SecurityAgent

        return SecurityAgent
    elif name == "StyleAgent":
        from src.agents.style import StyleAgent

        return StyleAgent
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
