"""Prompt construction and agent command formatting utilities."""

from __future__ import annotations

import shlex
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.models import Task


def build_task_prompt(task: Task, config: SpecOpsConfig) -> str:
    """Constructs explicit prompt contract for autonomous coding agents."""
    from ..worker.claimer import hydrate_task_prompt
    return hydrate_task_prompt(task, config)


from ..worker.runners import build_agent_cmd
