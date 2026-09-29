"""Scaffolding package for SpecOps."""

from .adapters import (
    generate_antigravity_rules,
    generate_claude_rules,
    generate_cursor_rules,
    get_antigravity_slash_commands,
    parse_target_agents,
    scaffold_agent_adapters,
)
from .init import init_project

__all__ = [
    "init_project",
    "generate_claude_rules",
    "generate_cursor_rules",
    "generate_antigravity_rules",
    "get_antigravity_slash_commands",
    "parse_target_agents",
    "scaffold_agent_adapters",
]
