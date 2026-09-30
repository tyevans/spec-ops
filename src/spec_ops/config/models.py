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
    file_warning_threshold: int = 400
    buffer_target: int = 10
    buffer_warning_threshold: int = 6
    components: list[ComponentConfig] = field(default_factory=list)


@dataclass
class QualitySettings:
    testing_style: str = "blackbox-frontdoor"
    require_bdd: bool = True
    enforce_lockfile: bool = True
    preflight: list[str] = field(
        default_factory=lambda: ["pytest"]
    )


@dataclass
class SandboxSettings:
    enabled: bool = False
    allowed_commands: list[str] = field(default_factory=lambda: ["uv", "git", "pytest", "ruff"])
    isolate_network: bool = False


@dataclass
class ExecutionSettings:
    agent_command: str = "agy --dangerously-skip-permissions -p {prompt}"
    reviewer_command: str = ""
    agent_max_attempts: int = 3
    git_branch_prefix: str = "feat/"
    backlog_isolation: bool = True
    enable_review: bool = True
    target_agents: list[str] = field(default_factory=list)
    sandbox: SandboxSettings = field(default_factory=SandboxSettings)


@dataclass
class LicenseSettings:
    allowed: list[str] = field(default_factory=list)
    profile: str = "permissive"


@dataclass
class ComplianceSettings:
    require_signed_commits: bool = False
    dual_custody: bool = False
    allowed_signers_file: str = ".ssh/allowed_signers"
    authorized_signers: list[str] = field(default_factory=list)


@dataclass
class SecuritySettings:
    secret_scanning: bool = True
    lockfile_immutability: bool = True
    enforce_lockfile: bool = True
    sandbox_enabled: bool = True
    allowed_commands: list[str] = field(default_factory=lambda: ["pytest", "git", "uv"])
    reporting_contact: str = "security@example.com"
    pgp_fingerprint: str = "ABCD 1234 EF56 7890 ABCD 1234 EF56 7890 SPEC OPS1"
    licenses: LicenseSettings = field(default_factory=LicenseSettings)
    allowed_licenses: list[str] = field(default_factory=list)
    compliance: ComplianceSettings = field(default_factory=ComplianceSettings)


@dataclass
class SpecOpsConfig:
    project: ProjectSettings = field(default_factory=ProjectSettings)
    architecture: ArchitectureSettings = field(default_factory=ArchitectureSettings)
    vertical_slices: list[SliceConfig] = field(default_factory=list)
    quality: QualitySettings = field(default_factory=QualitySettings)
    execution: ExecutionSettings = field(default_factory=ExecutionSettings)
    security: SecuritySettings | None = None
    root_dir: Path = field(default_factory=Path.cwd)

    @property
    def require_signed_commits(self) -> bool:
        if self.security and self.security.compliance:
            return self.security.compliance.require_signed_commits
        return False

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

    @property
    def docs_dir(self) -> Path:
        return (self.root_dir / "docs").resolve()
