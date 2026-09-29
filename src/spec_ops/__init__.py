"""SpecOps: Opinionated Project Management as Code and Autonomous Delivery Engine."""

from .cli.main import main
from .config.loader import load_config
from .config.models import SpecOpsConfig
from .core.models import ADR, PRD, Persona, ProjectData, Task, UserStory
from .core.parser import SpecOpsParser
from .scaffold.init import init_project

__version__ = "0.1.0"

__all__ = [
    "ADR",
    "PRD",
    "Persona",
    "ProjectData",
    "SpecOpsConfig",
    "SpecOpsParser",
    "Task",
    "UserStory",
    "init_project",
    "load_config",
    "main",
]
