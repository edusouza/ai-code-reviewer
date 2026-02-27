from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.graph.state import ChunkInfo, Suggestion


class BaseAgent(ABC):
    """Abstract base class for all review agents."""
    
    def __init__(self, name: str, priority: int = 5):
        """
        Initialize the agent.
        
        Args:
            name: Agent name/identifier
            priority: Priority level (1-10, lower is higher priority)
        """
        self.name = name
        self.priority = priority
    
    @abstractmethod
    async def analyze(self, chunk: ChunkInfo, context: Dict[str, Any]) -> List[Suggestion]:
        """
        Analyze a code chunk and return suggestions.
        
        Args:
            chunk: Code chunk information
            context: Additional context (config, AGENTS.md, etc.)
            
        Returns:
            List of suggestions found by this agent
        """
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent.
        
        Returns:
            System prompt string
        """
        pass
    
    def should_analyze(self, chunk: ChunkInfo) -> bool:
        """
        Determine if this agent should analyze the given chunk.
        
        Args:
            chunk: Code chunk information
            
        Returns:
            True if agent should analyze this chunk
        """
        return True
    
    def format_suggestion(
        self,
        file_path: str,
        line_number: int,
        message: str,
        severity: str = "suggestion",
        suggestion: str = None,
        category: str = "general",
        confidence: float = 0.8
    ) -> Suggestion:
        """
        Format a suggestion with standard fields.
        
        Args:
            file_path: Path to the file
            line_number: Line number in the file
            message: Suggestion message
            severity: Severity level (error, warning, suggestion, note)
            suggestion: Suggested code replacement
            category: Category of the issue
            confidence: Confidence score (0.0-1.0)
            
        Returns:
            Formatted Suggestion dictionary
        """
        return {
            "file_path": file_path,
            "line_number": line_number,
            "message": message,
            "severity": severity,
            "suggestion": suggestion,
            "agent_type": self.name,
            "confidence": confidence,
            "category": category
        }
