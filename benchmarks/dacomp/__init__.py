"""
DAComp Adapter for Harbor.

Converts DAComp-DA and DAComp-DE tasks into Harbor task format.
"""

from .adapter import DACompDAAdapter, DACompDEAdapter

__all__ = ["DACompDAAdapter", "DACompDEAdapter"]
