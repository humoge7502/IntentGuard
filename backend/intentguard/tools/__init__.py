"""Tool registry assembly."""
from __future__ import annotations

from intentguard.tools.adapters import (
    AgentInbox,
    BankingAPI,
    EmailAPI,
    FileStore,
    ShoppingAPI,
    WebBrowser,
)
from intentguard.tools.base import ToolRegistry

__all__ = [
    "AgentInbox",
    "BankingAPI",
    "EmailAPI",
    "FileStore",
    "ShoppingAPI",
    "WebBrowser",
    "ToolRegistry",
    "default_registry",
]


def default_registry() -> ToolRegistry:
    """The sandbox toolset. Real integrations (§12) register additional
    adapters; the firewall and capability system are tool-agnostic."""
    registry = ToolRegistry()
    registry.register(ShoppingAPI())
    registry.register(BankingAPI())
    registry.register(EmailAPI())
    registry.register(WebBrowser())
    registry.register(FileStore())
    registry.register(AgentInbox())
    return registry
