"""Stella Workflow package."""

from .brokers.base import BrokerFactory
from .loop import in_loop
from .workflow import ColoredFormatter, Colors, StellaAgent, logger

__all__ = [
    'BrokerFactory',
    'Colors',
    'ColoredFormatter',
    'in_loop',
    'logger',
    'StellaAgent',
]

# Alias for backward compatibility
stella_agent = StellaAgent
