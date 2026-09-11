"""IntentGuard — runtime authorization and security control plane for autonomous AI agents.

Core thesis: an LLM may *propose* actions, but an independent, deterministic
enforcement layer decides whether a consequential action may execute, by
checking it against the human's compiled intent, scoped capabilities, policy,
execution context, and accumulated trajectory.
"""

__version__ = "0.1.0"
