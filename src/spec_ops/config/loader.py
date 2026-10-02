"""Configuration loader for SpecOps manifests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore

from .models import (
    ArchitectureSettings,
    ComplianceSettings,
    ComponentConfig,
    DocumentationSettings,
    ExecutionSettings,
    LicenseSettings,
    ProjectSettings,
    QualitySettings,
    SandboxSettings,
    SecuritySettings,
    SliceConfig,
    SpecOpsConfig,
)

CONFIG_FILENAMES = ["specops.toml", ".specops.toml", "pmac.toml", ".pmac.toml"]

DEFAULT_SLICES = [
    SliceConfig(type="spike", name="Architectural Spike", prefix="SPIKE:", requires_adr=True),
    SliceConfig(type="domain", name="Domain & Aggregates"),
    SliceConfig(type="api", name="API & Auth Contracts"),
    SliceConfig(type="ui", name="Component UI & Stories"),
    SliceConfig(type="test", name="E2E Frontdoor Blackbox Suite"),
]


def find_config_file(root_dir: Path | None = None) -> Path | None:
    current = (root_dir or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        for name in CONFIG_FILENAMES:
            candidate = parent / name
            if candidate.is_file():
                return candidate
        if (parent / ".git").exists():
            break
    return None


def load_config(config_path: Path | None = None, root_dir: Path | None = None) -> SpecOpsConfig:
    if config_path and config_path.is_dir():
        root_dir = config_path
        config_path = None
    effective_root = (root_dir or Path.cwd()).resolve()
    target_file = config_path or find_config_file(effective_root)

    if not target_file or not target_file.is_file():
        # Return sensible defaults
        return SpecOpsConfig(
            root_dir=effective_root,
            vertical_slices=list(DEFAULT_SLICES),
        )

    root = target_file.parent
    with target_file.open("rb") as f:
        data = tomllib.load(f)

    # Parse project section
    proj_data = data.get("project", {})
    project = ProjectSettings(
        name=proj_data.get("name", "MyProject"),
        repo=proj_data.get("repo", ""),
        docs_dir=proj_data.get("docs_dir", "docs/project"),
        site_output=proj_data.get("site_output", "dist/site"),
    )

    # Parse architecture section
    arch_data = data.get("architecture", {})
    components = [
        ComponentConfig(
            id=c.get("id", ""),
            name=c.get("name", ""),
            path=c.get("path", ""),
            description=c.get("description", ""),
        )
        for c in arch_data.get("components", [])
        if isinstance(c, dict)
    ]
    architecture = ArchitectureSettings(
        file_length_limit=arch_data.get("file_length_limit", 500),
        file_warning_threshold=arch_data.get("file_warning_threshold", 400),
        buffer_target=arch_data.get("buffer_target", 10),
        buffer_warning_threshold=arch_data.get("buffer_warning_threshold", 6),
        components=components,
    )

    # Parse slices
    slices_data = data.get("vertical_slices", {}).get("slices", [])
    slices = [
        SliceConfig(
            type=s.get("type", "feature"),
            name=s.get("name", ""),
            prefix=s.get("prefix", ""),
            requires_adr=s.get("requires_adr", False),
            description=s.get("description", ""),
        )
        for s in slices_data
        if isinstance(s, dict)
    ] or list(DEFAULT_SLICES)

    # Parse quality
    qual_data = data.get("quality", {})
    quality = QualitySettings(
        testing_style=qual_data.get("testing_style", "blackbox-frontdoor"),
        require_bdd=qual_data.get("require_bdd", True),
        preflight=qual_data.get("preflight", ["pytest"]),
    )

    # Parse execution
    exec_data = data.get("execution", {})
    sb_data = exec_data.get("sandbox")
    if sb_data is not None and isinstance(sb_data, dict):
        sandbox = SandboxSettings(
            enabled=sb_data.get("enabled", True),
            allowed_commands=list(sb_data.get("allowed_commands", ["uv", "git", "pytest", "ruff"])),
            isolate_network=sb_data.get("isolate_network", False),
        )
    else:
        sandbox = SandboxSettings(enabled=False)
    execution = ExecutionSettings(
        agent_command=exec_data.get("agent_command", "agy -p '{prompt}'"),
        reviewer_command=exec_data.get("reviewer_command", ""),
        agent_max_attempts=exec_data.get("agent_max_attempts", 3),
        git_branch_prefix=exec_data.get("git_branch_prefix", "feat/"),
        backlog_isolation=exec_data.get("backlog_isolation", True),
        enable_review=exec_data.get("enable_review", True),
        target_agents=list(exec_data.get("target_agents", [])),
        sandbox=sandbox,
    )

    # Parse security
    sec_data = data.get("security")
    top_allowed = data.get("allowed_licenses")
    comp_data = data.get("compliance")
    security = None
    if sec_data is not None and isinstance(sec_data, dict):
        lic_data = sec_data.get("licenses", {})
        if not isinstance(lic_data, dict):
            lic_data = {}
        allowed = list(lic_data.get("allowed", []))
        if not allowed and "allowed_licenses" in sec_data:
            allowed = list(sec_data.get("allowed_licenses", []))
        if not allowed and top_allowed:
            allowed = list(top_allowed)
        profile = str(lic_data.get("profile", "permissive"))
        license_settings = LicenseSettings(allowed=allowed, profile=profile)

        raw_comp = sec_data.get("compliance", comp_data if isinstance(comp_data, dict) else {})
        if not isinstance(raw_comp, dict):
            raw_comp = {}
        compliance = ComplianceSettings(
            require_signed_commits=bool(raw_comp.get("require_signed_commits", False)),
            dual_custody=bool(raw_comp.get("dual_custody", False)),
            allowed_signers_file=str(raw_comp.get("allowed_signers_file", ".ssh/allowed_signers")),
            authorized_signers=list(raw_comp.get("authorized_signers", [])),
        )

        security = SecuritySettings(
            secret_scanning=sec_data.get("secret_scanning", True),
            lockfile_immutability=sec_data.get("lockfile_immutability", True),
            enforce_lockfile=sec_data.get("enforce_lockfile", True),
            sandbox_enabled=sec_data.get("sandbox_enabled", True),
            allowed_commands=list(sec_data.get("allowed_commands", ["pytest", "git", "uv"])),
            reporting_contact=sec_data.get("reporting_contact", "security@example.com"),
            pgp_fingerprint=sec_data.get("pgp_fingerprint", "ABCD 1234 EF56 7890 ABCD 1234 EF56 7890 SPEC OPS1"),
            licenses=license_settings,
            allowed_licenses=allowed,
            compliance=compliance,
        )
    elif top_allowed or (comp_data is not None and isinstance(comp_data, dict)):
        allowed = list(top_allowed) if top_allowed else []
        license_settings = LicenseSettings(allowed=allowed, profile="permissive")
        if comp_data is not None and isinstance(comp_data, dict):
            compliance = ComplianceSettings(
                require_signed_commits=bool(comp_data.get("require_signed_commits", False)),
                dual_custody=bool(comp_data.get("dual_custody", False)),
                allowed_signers_file=str(comp_data.get("allowed_signers_file", ".ssh/allowed_signers")),
                authorized_signers=list(comp_data.get("authorized_signers", [])),
            )
        else:
            compliance = ComplianceSettings()
        security = SecuritySettings(
            licenses=license_settings,
            allowed_licenses=allowed,
            compliance=compliance,
        )

    # Parse documentation section
    doc_data = data.get("documentation", {})
    doc_docs_dir = doc_data.get("docs_dir")
    if not doc_docs_dir:
        proj_docs = proj_data.get("docs_dir")
        if proj_docs and proj_docs != "docs/project":
            doc_docs_dir = proj_docs
        else:
            doc_docs_dir = "docs"

    documentation = DocumentationSettings(
        docs_dir=doc_docs_dir,
        allowed_directories=list(doc_data.get("allowed_directories", [])),
        ignored_directories=list(
            doc_data.get("ignored_directories", []) + doc_data.get("ignored_dirs", [])
        ),
        allowed_root_files=list(doc_data.get("allowed_root_files", [])),
        ignored_root_files=list(doc_data.get("ignored_root_files", [])),
    )

    return SpecOpsConfig(
        project=project,
        architecture=architecture,
        vertical_slices=slices,
        quality=quality,
        execution=execution,
        documentation=documentation,
        security=security,
        root_dir=root,
    )

