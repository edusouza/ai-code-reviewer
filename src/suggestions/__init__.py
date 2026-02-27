"""Suggestion processing components."""

from src.suggestions.processor import SuggestionProcessor
from src.suggestions.deduplicator import Deduplicator
from src.suggestions.severity import SeverityClassifier, SeverityLevel

__all__ = [
    "SuggestionProcessor",
    "Deduplicator",
    "SeverityClassifier",
    "SeverityLevel",
]
