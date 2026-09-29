"""Configuration data models for SpecOps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ComponentConfig:
    id: str
    name: str
    path: str = ""
    description: str = ""


@dataclass
class SliceConfig:
    type: str
    name: str
    prefix: str = ""
    requires_adr: bool = False
    description: str = ""


@dataclass
class ProjectSettings:
    name: str = "MyProject"
    repo: str = ""
    docs_dir: str = "docs/project"
    site_output: str = "dist/site"


@dataclass
class ArchitectureSettings:
    file_length_limit: int = 500
    buffer_target: int = 10
    buffer_warning_threshold: int = 6
    components: list[ComponentConfig] = field(default_factory=list)


@dataclass
class QualitySettings:
    testing_style: str = "blackbox-frontdoor"
    require_bdd: bool = True
    preflight: list[str] = field(
        default_factory=lambda: ["pytest"]
    )


@dataclass
class ExecutionSettings:
    agent_command: str = "agy -p '{prompt}'"
    agent_max_attempts: int = 3
    git_branch_prefix: str = "feat/"
    backlog_isolation: bool = True


@dataclass
class SpecOpsConfig:
    project: ProjectSettings = field(default_factory=ProjectSettings)
    architecture: ArchitectureSettings = field(default_factory=ArchitectureSettings)
    vertical_slices: list[SliceConfig] = field(default_factory=list)
    quality: QualitySettings = field(default_factory=QualitySettings)
    execution: ExecutionSettings = field(default_factory=ExecutionSettings)
    root_dir: Path = field(default_factory=Path.cwd)

    @property
    def project_docs_dir(self) -> Path:
        return (self.root_dir / self.project.docs_dir).resolve()

    @property
    def backlog_dir(self) -> Path:
        return self.project_docs_dir / "backlog"

    @property
    def prd_dir(self) -> Path:
        return self.project_docs_dir / "product"

    @property
    def user_stories_dir(self) -> Path:
        return self.project_docs_dir / "user_stories"

    @property
    def adr_dir(self) -> Path:
        return self.project_docs_dir / "adrs"
