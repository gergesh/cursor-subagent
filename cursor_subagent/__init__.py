#!/usr/bin/env python3
"""
cursor-subagent - Transparent wrapper for cursor-agent with isolated agent configurations.
"""

__version__ = "0.3.0"

from .server import main

__all__ = ["main", "__version__"]
