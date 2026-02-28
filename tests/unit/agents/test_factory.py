"""Tests for AgentFactory."""

from unittest.mock import Mock, patch

import pytest

from agents.base import BaseAgent
from agents.factory import AgentFactory


@pytest.fixture(autouse=True)
def _reset_agents_registry():
    """Reset the AgentFactory._agents to its original state after each test.

    This prevents test pollution when register_agent modifies the class-level dict.
    """
    original = dict(AgentFactory._agents)
    yield
    AgentFactory._agents = original


class TestAgentFactoryListAgents:
    """Tests for AgentFactory.list_agents."""

    def test_list_agents_returns_default_agents(self):
        """Default agents include security, style, logic, pattern."""
        agents = AgentFactory.list_agents()
        assert isinstance(agents, list)
        assert "security" in agents
        assert "style" in agents
        assert "logic" in agents
        assert "pattern" in agents

    def test_list_agents_returns_four_defaults(self):
        """There are exactly four default agents."""
        agents = AgentFactory.list_agents()
        assert len(agents) == 4

    def test_list_agents_returns_new_list_each_call(self):
        """Each call returns a separate list object."""
        agents_a = AgentFactory.list_agents()
        agents_b = AgentFactory.list_agents()
        assert agents_a == agents_b
        assert agents_a is not agents_b


class TestAgentFactoryRegisterAgent:
    """Tests for AgentFactory.register_agent."""

    def test_register_new_agent(self):
        """Registering a new agent type makes it available."""

        class FakeAgent:
            pass

        AgentFactory.register_agent("fake", FakeAgent)
        assert "fake" in AgentFactory.list_agents()

    def test_register_overwrites_existing(self):
        """Registering with an existing name overwrites it."""

        class NewSecurityAgent:
            pass

        AgentFactory.register_agent("security", NewSecurityAgent)
        assert AgentFactory._agents["security"] is NewSecurityAgent

    def test_register_multiple_agents(self):
        """Multiple new agents can be registered."""

        class AgentA:
            pass

        class AgentB:
            pass

        AgentFactory.register_agent("agent_a", AgentA)
        AgentFactory.register_agent("agent_b", AgentB)
        agents = AgentFactory.list_agents()
        assert "agent_a" in agents
        assert "agent_b" in agents


class TestAgentFactoryCreateAgent:
    """Tests for AgentFactory.create_agent."""

    @patch("agents.factory.SecurityAgent")
    def test_create_security_agent(self, mock_security_cls):
        """create_agent('security') instantiates SecurityAgent."""
        mock_instance = Mock(spec=BaseAgent)
        mock_security_cls.return_value = mock_instance

        AgentFactory._agents["security"] = mock_security_cls
        agent = AgentFactory.create_agent("security")

        mock_security_cls.assert_called_once_with()
        assert agent is mock_instance

    @patch("agents.factory.StyleAgent")
    def test_create_style_agent(self, mock_style_cls):
        """create_agent('style') instantiates StyleAgent."""
        mock_instance = Mock(spec=BaseAgent)
        mock_style_cls.return_value = mock_instance

        AgentFactory._agents["style"] = mock_style_cls
        agent = AgentFactory.create_agent("style")

        mock_style_cls.assert_called_once_with()
        assert agent is mock_instance

    @patch("agents.factory.LogicAgent")
    def test_create_logic_agent(self, mock_logic_cls):
        """create_agent('logic') instantiates LogicAgent."""
        mock_instance = Mock(spec=BaseAgent)
        mock_logic_cls.return_value = mock_instance

        AgentFactory._agents["logic"] = mock_logic_cls
        agent = AgentFactory.create_agent("logic")

        mock_logic_cls.assert_called_once_with()
        assert agent is mock_instance

    @patch("agents.factory.PatternAgent")
    def test_create_pattern_agent(self, mock_pattern_cls):
        """create_agent('pattern') instantiates PatternAgent."""
        mock_instance = Mock(spec=BaseAgent)
        mock_pattern_cls.return_value = mock_instance

        AgentFactory._agents["pattern"] = mock_pattern_cls
        agent = AgentFactory.create_agent("pattern")

        mock_pattern_cls.assert_called_once_with()
        assert agent is mock_instance

    def test_create_unknown_agent_raises_value_error(self):
        """create_agent with unknown name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent type: nonexistent"):
            AgentFactory.create_agent("nonexistent")

    def test_create_unknown_agent_error_lists_available(self):
        """The ValueError message includes available agent names."""
        with pytest.raises(ValueError) as exc_info:
            AgentFactory.create_agent("foobar")

        error_msg = str(exc_info.value)
        assert "security" in error_msg
        assert "style" in error_msg
        assert "logic" in error_msg
        assert "pattern" in error_msg

    def test_create_agent_passes_kwargs(self):
        """create_agent forwards kwargs to the agent constructor."""
        mock_cls = Mock()
        AgentFactory.register_agent("custom", mock_cls)

        AgentFactory.create_agent("custom", foo="bar", baz=42)

        mock_cls.assert_called_once_with(foo="bar", baz=42)

    def test_create_agent_with_no_kwargs(self):
        """create_agent with no kwargs calls constructor with no args."""
        mock_cls = Mock()
        AgentFactory.register_agent("simple", mock_cls)

        AgentFactory.create_agent("simple")

        mock_cls.assert_called_once_with()


class TestAgentFactoryCreateAllAgents:
    """Tests for AgentFactory.create_all_agents."""

    def test_create_all_agents_no_config(self):
        """create_all_agents with no config creates all agents."""
        mock_classes = {}
        for name in ["security", "style", "logic", "pattern"]:
            mock_cls = Mock()
            mock_cls.return_value = Mock(spec=BaseAgent)
            mock_classes[name] = mock_cls
            AgentFactory._agents[name] = mock_cls

        agents = AgentFactory.create_all_agents()

        assert len(agents) == 4
        for mock_cls in mock_classes.values():
            mock_cls.assert_called_once()

    def test_create_all_agents_config_none(self):
        """create_all_agents(config=None) creates all agents."""
        mock_classes = {}
        for name in ["security", "style", "logic", "pattern"]:
            mock_cls = Mock()
            mock_cls.return_value = Mock(spec=BaseAgent)
            mock_classes[name] = mock_cls
            AgentFactory._agents[name] = mock_cls

        agents = AgentFactory.create_all_agents(config=None)

        assert len(agents) == 4

    def test_create_all_agents_with_all_enabled(self):
        """create_all_agents with all enabled creates all agents."""
        mock_classes = {}
        for name in ["security", "style", "logic", "pattern"]:
            mock_cls = Mock()
            mock_cls.return_value = Mock(spec=BaseAgent)
            mock_classes[name] = mock_cls
            AgentFactory._agents[name] = mock_cls

        config = {"security": True, "style": True, "logic": True, "pattern": True}
        agents = AgentFactory.create_all_agents(config=config)

        assert len(agents) == 4

    def test_create_all_agents_with_some_disabled(self):
        """create_all_agents respects disabled agents in config."""
        mock_classes = {}
        for name in ["security", "style", "logic", "pattern"]:
            mock_cls = Mock()
            mock_cls.return_value = Mock(spec=BaseAgent)
            mock_classes[name] = mock_cls
            AgentFactory._agents[name] = mock_cls

        config = {"security": True, "style": False, "logic": True, "pattern": False}
        agents = AgentFactory.create_all_agents(config=config)

        assert len(agents) == 2
        mock_classes["security"].assert_called_once()
        mock_classes["logic"].assert_called_once()
        mock_classes["style"].assert_not_called()
        mock_classes["pattern"].assert_not_called()

    def test_create_all_agents_with_all_disabled(self):
        """create_all_agents with all disabled returns empty list."""
        for name in ["security", "style", "logic", "pattern"]:
            mock_cls = Mock()
            AgentFactory._agents[name] = mock_cls

        config = {"security": False, "style": False, "logic": False, "pattern": False}
        agents = AgentFactory.create_all_agents(config=config)

        assert len(agents) == 0

    def test_create_all_agents_config_missing_key_defaults_true(self):
        """Agents not in config dict default to enabled (True)."""
        mock_classes = {}
        for name in ["security", "style", "logic", "pattern"]:
            mock_cls = Mock()
            mock_cls.return_value = Mock(spec=BaseAgent)
            mock_classes[name] = mock_cls
            AgentFactory._agents[name] = mock_cls

        # Only specify security=False, others should default to True
        config = {"security": False}
        agents = AgentFactory.create_all_agents(config=config)

        assert len(agents) == 3
        mock_classes["security"].assert_not_called()
        mock_classes["style"].assert_called_once()
        mock_classes["logic"].assert_called_once()
        mock_classes["pattern"].assert_called_once()

    def test_create_all_agents_empty_config_enables_all(self):
        """Empty config dict defaults all to True."""
        mock_classes = {}
        for name in ["security", "style", "logic", "pattern"]:
            mock_cls = Mock()
            mock_cls.return_value = Mock(spec=BaseAgent)
            mock_classes[name] = mock_cls
            AgentFactory._agents[name] = mock_cls

        agents = AgentFactory.create_all_agents(config={})

        assert len(agents) == 4

    def test_create_all_agents_returns_list_of_instances(self):
        """Return value is a list of agent instances."""
        mock_cls = Mock()
        instance = Mock(spec=BaseAgent)
        mock_cls.return_value = instance

        for name in ["security", "style", "logic", "pattern"]:
            AgentFactory._agents[name] = mock_cls

        agents = AgentFactory.create_all_agents()

        assert isinstance(agents, list)
        for agent in agents:
            assert agent is instance

    def test_create_all_agents_includes_custom_registered_agent(self):
        """Custom registered agents are included in create_all_agents."""
        # Replace default agents with mocks
        for name in ["security", "style", "logic", "pattern"]:
            mock_cls = Mock()
            mock_cls.return_value = Mock(spec=BaseAgent)
            AgentFactory._agents[name] = mock_cls

        # Register a custom agent
        custom_cls = Mock()
        custom_cls.return_value = Mock(spec=BaseAgent)
        AgentFactory.register_agent("custom", custom_cls)

        agents = AgentFactory.create_all_agents()

        assert len(agents) == 5
        custom_cls.assert_called_once()
