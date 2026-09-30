"""Unit tests for wizard.py to maximize mutant kill rate under mutmut."""

from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from spec_ops.profiles.composer import ResolvedComposition
from spec_ops.config.models import SliceConfig
from spec_ops.scaffold.wizard import (
    InitValidationError,
    WizardConfig,
    compute_profile_checksums,
    handle_init_command,
    plan_initialization,
    render_dry_run,
    render_preview_tree,
    run_interactive_wizard,
    serialize_specops_toml,
    validate_init_options,
)


def test_validate_init_options_success(tmp_path: Path):
    validate_init_options("MyProject", ["core", "bdd"], ["billing", "orders"], tmp_path)


def test_validate_init_options_empty_name(tmp_path: Path):
    with pytest.raises(InitValidationError, match="Project name cannot be empty"):
        validate_init_options("", ["core"], [], tmp_path)
    with pytest.raises(InitValidationError, match="Project name cannot be empty"):
        validate_init_options("   ", ["core"], [], tmp_path)


def test_validate_init_options_null_byte_in_name(tmp_path: Path):
    with pytest.raises(InitValidationError, match="null bytes"):
        validate_init_options("My\0Project", ["core"], [], tmp_path)


@pytest.mark.parametrize("bad_char", ["/", "\\", ":", "*", "?", '"', "<", ">", "|"])
def test_validate_init_options_forbidden_chars_in_name(tmp_path: Path, bad_char: str):
    with pytest.raises(InitValidationError, match="forbidden characters"):
        validate_init_options(f"Proj{bad_char}ect", ["core"], [], tmp_path)


def test_validate_init_options_null_byte_in_dir(tmp_path: Path):
    with pytest.raises(InitValidationError, match="null bytes"):
        validate_init_options("Project", ["core"], [], Path("some/\0/dir"))


def test_validate_init_options_empty_profiles(tmp_path: Path):
    with pytest.raises(InitValidationError, match="At least one architectural profile"):
        validate_init_options("Project", [], [], tmp_path)


def test_validate_init_options_unknown_profile(tmp_path: Path):
    with pytest.raises(InitValidationError, match="Unknown or invalid architectural profile: 'nonexistent_foo'"):
        validate_init_options("Project", ["nonexistent_foo"], [], tmp_path)


def test_validate_init_options_duplicate_bc(tmp_path: Path):
    with pytest.raises(InitValidationError, match="Duplicate bounded context declared: 'billing'"):
        validate_init_options("Project", ["core"], ["billing", "billing"], tmp_path)


def test_validate_init_options_case_insensitive_duplicate_bc(tmp_path: Path):
    with pytest.raises(InitValidationError, match="Duplicate bounded context declared: 'BILLING'"):
        validate_init_options("Project", ["core"], ["billing", "BILLING"], tmp_path)


def test_validate_init_options_core_bc_reserved(tmp_path: Path):
    with pytest.raises(InitValidationError, match="'core' is the reserved baseline component"):
        validate_init_options("Project", ["core"], ["core"], tmp_path)
    with pytest.raises(InitValidationError, match="'core' is the reserved baseline component"):
        validate_init_options("Project", ["core"], ["CORE"], tmp_path)


def test_validate_init_options_illegal_bc_chars(tmp_path: Path):
    with pytest.raises(InitValidationError, match="Illegal bounded context identifier"):
        validate_init_options("Project", ["core"], ["billing space"], tmp_path)
    with pytest.raises(InitValidationError, match="Illegal bounded context identifier"):
        validate_init_options("Project", ["core"], ["billing/sub"], tmp_path)


def test_compute_profile_checksums():
    checksums = compute_profile_checksums(["core", "bdd", "unknown_profile_xyz"])
    assert "core" in checksums
    assert len(checksums["core"]) == 64
    assert "bdd" in checksums
    assert len(checksums["bdd"]) == 64
    assert "unknown_profile_xyz" in checksums
    assert len(checksums["unknown_profile_xyz"]) == 64


def test_serialize_specops_toml_customizations():
    comp = ResolvedComposition(
        profile_ids=["core", "security"],
        adrs=[],
        file_length_limit=350,
        overrides={"quality": {"require_mutation_testing": True}},
        slices=[SliceConfig(type="audit", name="Audit Slices", prefix="AUDIT:", requires_adr=True)],
        version="1.2.3",
    )
    toml = serialize_specops_toml(
        comp,
        project_name="CustomApp",
        bounded_contexts=["billing"],
        agents=["claude", "cursor"],
    )
    assert 'name = "CustomApp"' in toml
    assert "file_length_limit = 350" in toml
    assert "require_mutation_testing = true" in toml
    assert 'id = "billing"' in toml
    assert 'name = "Billing"' in toml
    assert 'path = "src/billing"' in toml
    assert 'type = "audit"' in toml
    assert 'target_agents = ["claude", "cursor"]' in toml
    assert 'version = "1.2.3"' in toml
    assert "[security]" in toml


def test_plan_initialization_full_manifest(tmp_path: Path):
    cfg = WizardConfig(
        name="TestProj",
        target_dir=tmp_path,
        profiles=["core", "security"],
        bounded_contexts=["shipping"],
        ci="all",
        diataxis=True,
        github_pages=True,
        pre_commit=True,
        agents=["antigravity", "claude", "cursor"],
    )
    plan = plan_initialization(cfg)
    assert plan.config.name == "TestProj"
    assert "specops.toml" in plan.planned_files
    assert "docs/project/SECURITY.md" in plan.planned_files
    assert "src/shipping/__init__.py" in plan.planned_files
    assert ".github/workflows/ci.yml" in plan.planned_files
    assert ".gitlab-ci.yml" in plan.planned_files
    assert ".github/workflows/deploy-pages.yml" in plan.planned_files
    assert ".pre-commit-config.yaml" in plan.planned_files
    assert "docs/tutorials/01-getting-started.md" in plan.planned_files
    assert "GEMINI.md" in plan.planned_files
    assert "CLAUDE.md" in plan.planned_files
    assert ".cursorrules" in plan.planned_files
    assert plan.collisions == []


def test_plan_initialization_detects_collisions(tmp_path: Path):
    (tmp_path / "specops.toml").write_text("# existing", encoding="utf-8")
    cfg = WizardConfig(name="CollisionProj", target_dir=tmp_path, profiles=["core"])
    plan = plan_initialization(cfg)
    assert "specops.toml" in plan.collisions


def test_render_preview_tree_and_dry_run(tmp_path: Path):
    cfg = WizardConfig(name="RenderProj", target_dir=tmp_path, profiles=["core"])
    plan = plan_initialization(cfg)

    buf = StringIO()
    console = Console(file=buf, color_system=None)
    render_preview_tree(plan, console)
    output = buf.getvalue()
    assert "RenderProj" in output
    assert "specops.toml" in output

    buf2 = StringIO()
    console2 = Console(file=buf2, color_system=None)
    render_dry_run(plan, console2)
    dry_out = buf2.getvalue()
    assert "Dry-Run Preview" in dry_out
    assert "Filename Collisions: None" in dry_out
    assert "Zero files were created on disk" in dry_out


def test_render_dry_run_with_collisions(tmp_path: Path):
    (tmp_path / "specops.toml").write_text("# existing", encoding="utf-8")
    cfg = WizardConfig(name="CollisionProj", target_dir=tmp_path, profiles=["core"])
    plan = plan_initialization(cfg)

    buf = StringIO()
    console = Console(file=buf, color_system=None)
    render_dry_run(plan, console)
    dry_out = buf.getvalue()
    assert "Potential Filename Collisions (1)" in dry_out
    assert "specops.toml" in dry_out


def test_run_interactive_wizard_confirmed(tmp_path: Path):
    in_buf = StringIO("WizardApp\ncore, bdd\norders\ngitlab\ny\ny\n")
    out_buf = StringIO()
    console = Console(file=out_buf, color_system=None)
    console.input = lambda *a, **kw: in_buf.readline().rstrip("\n")  # type: ignore

    cfg = run_interactive_wizard(tmp_path, default_name="DefaultApp", console=console)
    assert cfg is not None
    assert cfg.name == "WizardApp"
    assert cfg.profiles == ["core", "bdd"]
    assert cfg.bounded_contexts == ["orders"]
    assert cfg.ci == "gitlab"
    assert cfg.diataxis is True


def test_run_interactive_wizard_cancelled(tmp_path: Path):
    in_buf = StringIO("CancelApp\ncore\n\ngithub\ny\nn\n")
    out_buf = StringIO()
    console = Console(file=out_buf, color_system=None)
    console.input = lambda *a, **kw: in_buf.readline().rstrip("\n")  # type: ignore

    cfg = run_interactive_wizard(tmp_path, console=console)
    assert cfg is None
    assert "Initialization cancelled by user" in out_buf.getvalue()


def test_handle_init_command_interactive(tmp_path: Path):
    args = argparse.Namespace(
        command="init",
        dir=str(tmp_path),
        interactive=True,
        headless=False,
        dry_run=False,
        profile="core",
        bc=None,
        name="InteractiveTest",
        ci="github",
        diataxis=True,
        github_pages=True,
        pre_commit=True,
        agent=None,
        yes=False,
    )
    in_buf = StringIO("InteractiveTest\ncore\n\ngithub\ny\ny\n")
    out_buf = StringIO()
    console = Console(file=out_buf, color_system=None)
    console.input = lambda *a, **kw: in_buf.readline().rstrip("\n")  # type: ignore

    rc = handle_init_command(args, console=console)
    assert rc == 0
    assert (tmp_path / "specops.toml").is_file()


def test_handle_init_command_dry_run(tmp_path: Path):
    args = argparse.Namespace(
        command="init",
        dir=str(tmp_path),
        interactive=False,
        headless=False,
        dry_run=True,
        profile="core,bdd",
        bc=["billing"],
        name="DryRunApp",
        ci="github",
        diataxis=False,
        github_pages=False,
        pre_commit=False,
        agent=None,
        yes=False,
    )
    out_buf = StringIO()
    console = Console(file=out_buf, color_system=None)

    rc = handle_init_command(args, console=console)
    assert rc == 0
    assert len(list(tmp_path.iterdir())) == 0


def test_handle_init_command_validation_error(tmp_path: Path, capsys):
    args = argparse.Namespace(
        command="init",
        dir=str(tmp_path),
        interactive=False,
        headless=True,
        dry_run=False,
        profile="non_existent_profile",
        bc=None,
        name="FailApp",
        ci="github",
        diataxis=True,
        github_pages=True,
        pre_commit=True,
        agent=None,
        yes=False,
    )
    rc = handle_init_command(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert "Validation error" in err
