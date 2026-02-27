from typing import Any

from src.agents.base import BaseAgent
from src.agents.logic import LogicAgent
from src.agents.pattern import PatternAgent
from src.agents.security import SecurityAgent
from src.agents.style import StyleAgent


class AgentFactory:
    """Factory for creating agent instances."""

    _agents: dict[str, type] = {
        "security": SecurityAgent,
        "style": StyleAgent,
        "logic": LogicAgent,
        "pattern": PatternAgent,
    }

    @classmethod
    def register_agent(cls, name: str, agent_class: type) -> None:
        """
        Register a new agent type.

        Args:
            name: Agent identifier
            agent_class: Agent class
        """
        cls._agents[name] = agent_class

    @classmethod
    def create_agent(cls, name: str, **kwargs: Any) -> BaseAgent:
        """
        Create an agent instance.

        Args:
            name: Agent identifier
            **kwargs: Additional arguments for agent initialization

        Returns:
            Agent instance

        Raises:
            ValueError: If agent type is not registered
        """
        if name not in cls._agents:
            raise ValueError(f"Unknown agent type: {name}. Available: {list(cls._agents.keys())}")

        agent_class = cls._agents[name]
        return agent_class(**kwargs)

    @classmethod
    def list_agents(cls) -> list[str]:
        """
        List all registered agent types.

        Returns:
            List of agent names
        """
        return list(cls._agents.keys())

    @classmethod
    def create_all_agents(cls, config: dict[str, bool] = None) -> list[BaseAgent]:
        """
        Create all enabled agents.

        Args:
            config: Dict mapping agent names to enabled status

        Returns:
            List of agent instances
        """
        agents = []

        for name in cls._agents.keys():
            if config is None or config.get(name, True):
                agents.append(cls.create_agent(name))

        return agents
