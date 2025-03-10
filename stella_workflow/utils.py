"""Shared utility classes and functions for stella_workflow."""

class Colors:
    """ANSI color codes for terminal output formatting."""
    HEADER = '\033[95m'
    INFO = '\033[36m'      # Bright Cyan
    DEBUG = '\033[32m'     # Bright Green
    WARNING = '\033[33m'   # Bright Yellow
    ERROR = '\033[31m'     # Bright Red
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ORANGE = '\033[38;5;208m'  # Add orange color
