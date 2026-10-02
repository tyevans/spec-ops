"""Blackbox frontdoor verification for TASK-0238: Decouple Profiles from Scaffold.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.profiles.security import (
    apply_security_profile,
    register_default_agents_scaffolder,
    sync_security_profile,
)
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_profiles_security_has_no_scaffold_imports():
    """Verify that src/spec_ops/profiles/security.py contains zero imports of spec_ops.scaffold."""
    sec_file = Path("src/spec_ops/profiles/security.py")
    assert sec_file.is_file(), "security.py must exist"

    code = sec_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    scaffold_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "scaffold" in alias.name:
                    scaffold_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "scaffold" in mod:
                scaffold_imports.append(mod)

    assert not scaffold_imports, f"Found illegal scaffold imports in profiles/security.py: {scaffold_imports}"


def test_profiles_to_scaffold_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from profiles -> scaffold."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    prof_scaffold_violations = [
        v for v in violations
        if v.get("source") == "profiles" and v.get("target") == "scaffold"
    ]
    assert not prof_scaffold_violations, f"Active profiles -> scaffold violations detected: {prof_scaffold_violations}"


def test_apply_security_profile_injected_scaffolder(tmp_path: Path):
    """Verify apply_security_profile invokes injected agents scaffolder."""
    called: list[Path] = []

    def custom_scaffolder(root: Path):
        called.append(root)
        (root / "AGENTS.md").write_text("# Injected Agents Manual\n", encoding="utf-8")

    apply_security_profile(tmp_path, sync_worktrees=False, agents_scaffolder=custom_scaffolder)
    assert len(called) == 1
    assert (tmp_path / "AGENTS.md").is_file()
    assert "# Injected Agents Manual" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_sync_security_profile_injected_scaffolder(tmp_path: Path):
    """Verify sync_security_profile invokes injected agents scaffolder."""
    called: list[Path] = []

    def custom_scaffolder(root: Path):
        called.append(root)
        (root / "AGENTS.md").write_text("# Synced Agents Manual\n", encoding="utf-8")

    sync_security_profile(tmp_path, sync_worktrees=False, agents_scaffolder=custom_scaffolder)
    assert len(called) == 1
    assert (tmp_path / "AGENTS.md").is_file()
    assert "# Synced Agents Manual" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_profiles_registered_agents_scaffolder(tmp_path: Path):
    """Verify register_default_agents_scaffolder sets default scaffolder callback."""
    called: list[Path] = []

    def registered_scaffolder(root: Path):
        called.append(root)
        (root / "AGENTS.md").write_text("# Registered Agents Manual\n", encoding="utf-8")

    try:
        register_default_agents_scaffolder(registered_scaffolder)
        apply_security_profile(tmp_path, sync_worktrees=False)
        assert len(called) == 1
        assert "# Registered Agents Manual" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    finally:
        register_default_agents_scaffolder(None)
