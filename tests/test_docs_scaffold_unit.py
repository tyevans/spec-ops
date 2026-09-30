"""Comprehensive unit tests for docs_scaffold.py and scaffold_handler.py to maximize mutant kill rate."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from spec_ops.cli.parser import build_parser
from spec_ops.cli.scaffold_handler import handle_scaffold_command
from spec_ops.config.loader import load_config
from spec_ops.docs.auditor import DocsAuditor
from spec_ops.scaffold.docs_scaffold import (
    DocumentationExistsError,
    InvalidBoundedContextError,
    check_docs_exist,
    get_quadrant_paths,
    get_visualizer_deep_link,
    normalize_title,
    render_explanation_architecture,
    render_explanation_index,
    render_howto_doc,
    render_reference_doc,
    render_tutorial_doc,
    scaffold_bc_docs,
    update_index_md,
    validate_bc_name,
)


def test_validate_bc_name_valid():
    assert validate_bc_name("billing") == "billing"
    assert validate_bc_name("Billing") == "billing"
    assert validate_bc_name("  BILLING  ") == "billing"
    assert validate_bc_name("order-processing") == "order-processing"
    assert validate_bc_name("user_auth_123") == "user_auth_123"


def test_validate_bc_name_invalid_empty():
    with pytest.raises(InvalidBoundedContextError, match="cannot be empty"):
        validate_bc_name("")
    with pytest.raises(InvalidBoundedContextError, match="cannot be empty"):
        validate_bc_name("   ")
    with pytest.raises(InvalidBoundedContextError, match="cannot be empty"):
        validate_bc_name(None)  # type: ignore


def test_validate_bc_name_invalid_traversal():
    with pytest.raises(InvalidBoundedContextError, match="traversal"):
        validate_bc_name("../billing")
    with pytest.raises(InvalidBoundedContextError, match="traversal"):
        validate_bc_name("billing/sub")
    with pytest.raises(InvalidBoundedContextError, match="traversal"):
        validate_bc_name("billing\\sub")
    with pytest.raises(InvalidBoundedContextError, match="traversal"):
        validate_bc_name("billing\x00sub")
    with pytest.raises(InvalidBoundedContextError, match="traversal"):
        validate_bc_name("..")


def test_validate_bc_name_invalid_characters():
    with pytest.raises(InvalidBoundedContextError, match="pattern"):
        validate_bc_name("billing.sub")
    with pytest.raises(InvalidBoundedContextError, match="pattern"):
        validate_bc_name("billing sub")
    with pytest.raises(InvalidBoundedContextError, match="pattern"):
        validate_bc_name("billing@sub")


def test_normalize_title():
    assert normalize_title("billing", "Billing Subsystem") == "Billing Subsystem"
    assert normalize_title("billing", "  Billing Subsystem  ") == "Billing Subsystem"
    assert normalize_title("billing", None) == "Billing"
    assert normalize_title("billing", "") == "Billing"
    assert normalize_title("billing", "   ") == "Billing"
    assert normalize_title("billing-subsystem", None) == "Billing Subsystem"
    assert normalize_title("billing_subsystem", None) == "Billing Subsystem"
    assert normalize_title("user_auth-engine", None) == "User Auth Engine"


def test_get_visualizer_deep_link():
    link = get_visualizer_deep_link("billing")
    assert link == "../../visualizer/?focus=billing#tab=canvas&focus=billing"

    link_empty_prefix = get_visualizer_deep_link("billing", "")
    assert link_empty_prefix == "visualizer/?focus=billing#tab=canvas&focus=billing"

    link_custom_prefix = get_visualizer_deep_link("billing", "custom/")
    assert link_custom_prefix == "custom/visualizer/?focus=billing#tab=canvas&focus=billing"


def test_get_quadrant_paths(tmp_path: Path):
    quads = get_quadrant_paths(tmp_path, "billing")
    assert quads["tutorials"] == tmp_path / "docs" / "tutorials" / "billing"
    assert quads["how-to"] == tmp_path / "docs" / "how-to" / "billing"
    assert quads["reference"] == tmp_path / "docs" / "reference" / "billing"
    assert quads["explanation"] == tmp_path / "docs" / "explanation" / "billing"


def test_check_docs_exist(tmp_path: Path):
    assert not check_docs_exist(tmp_path, "billing")

    quads = get_quadrant_paths(tmp_path, "billing")
    quads["reference"].mkdir(parents=True, exist_ok=True)
    assert not check_docs_exist(tmp_path, "billing")

    (quads["reference"] / "other.txt").write_text("not a markdown file", encoding="utf-8")
    assert not check_docs_exist(tmp_path, "billing")

    (quads["reference"] / "index.md").write_text("# Reference", encoding="utf-8")
    assert check_docs_exist(tmp_path, "billing")


def test_template_renderers():
    tut = render_tutorial_doc("billing", "Billing Engine")
    assert 'title: "Billing Engine Tutorials"' in tut
    assert 'bounded_context: "billing"' in tut
    assert 'quadrant: "tutorials"' in tut
    assert 'governing_prd: "PRD-0005"' in tut
    assert 'governing_story: "US-0071"' in tut
    assert "# Billing Engine Tutorials" in tut
    assert "../../visualizer/?focus=billing#tab=canvas&focus=billing" in tut

    howto = render_howto_doc("billing", "Billing Engine")
    assert 'title: "Billing Engine How-To Guides"' in howto
    assert 'quadrant: "how-to"' in howto
    assert "# Billing Engine How-To Guides" in howto
    assert "../../visualizer/?focus=billing#tab=canvas&focus=billing" in howto

    ref = render_reference_doc("billing", "Billing Engine")
    assert 'title: "Billing Engine Technical Reference"' in ref
    assert 'quadrant: "reference"' in ref
    assert "# Billing Engine Technical Reference" in ref
    assert "../../visualizer/?focus=billing#tab=canvas&focus=billing" in ref

    exp_idx = render_explanation_index("billing", "Billing Engine")
    assert 'title: "Billing Engine Domain Concepts & Boundaries"' in exp_idx
    assert 'quadrant: "explanation"' in exp_idx
    assert "# Billing Engine Domain Concepts & Boundaries" in exp_idx
    assert "../../visualizer/?focus=billing#tab=canvas&focus=billing" in exp_idx

    exp_arch = render_explanation_architecture("billing", "Billing Engine")
    assert 'title: "Billing Engine Architecture & Domain Model"' in exp_arch
    assert 'quadrant: "explanation"' in exp_arch
    assert "# Billing Engine Architecture & Domain Model" in exp_arch
    assert "../../visualizer/?focus=billing#tab=canvas&focus=billing" in exp_arch


def test_update_index_md_no_index(tmp_path: Path):
    assert update_index_md(tmp_path, "billing", "Billing Engine") is None


def test_update_index_md_with_sections(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    index_file = docs_dir / "index.md"

    # Case 1: Without existing ## Bounded Contexts
    index_file.write_text("# Project Docs\n\nWelcome.\n", encoding="utf-8")
    updated_path = update_index_md(tmp_path, "billing", "Billing Engine")
    assert updated_path == index_file
    content = index_file.read_text(encoding="utf-8")
    assert "## Bounded Contexts" in content
    assert "### Billing Engine (`billing`)" in content
    assert "tutorials/billing/index.md" in content

    # Case 2: Already contains this bounded context (should not duplicate)
    update_index_md(tmp_path, "billing", "Billing Engine")
    content2 = index_file.read_text(encoding="utf-8")
    assert content2.count("### Billing Engine (`billing`)") == 1

    # Case 3: Contains ## Bounded Contexts, adding a second bounded context
    update_index_md(tmp_path, "shipping", "Shipping Engine")
    content3 = index_file.read_text(encoding="utf-8")
    assert "### Billing Engine (`billing`)" in content3
    assert "### Shipping Engine (`shipping`)" in content3


def test_scaffold_bc_docs_full_lifecycle(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.md").write_text("# Home\n", encoding="utf-8")

    created = scaffold_bc_docs(tmp_path, bc="billing", title="Billing Engine", force=False)
    assert len(created) == 6  # 5 docs + index.md

    assert (docs_dir / "tutorials" / "billing" / "index.md").exists()
    assert (docs_dir / "how-to" / "billing" / "index.md").exists()
    assert (docs_dir / "reference" / "billing" / "index.md").exists()
    assert (docs_dir / "explanation" / "billing" / "index.md").exists()
    assert (docs_dir / "explanation" / "billing" / "architecture.md").exists()

    # Re-scaffold without force must raise
    with pytest.raises(DocumentationExistsError):
        scaffold_bc_docs(tmp_path, bc="billing", title="Billing Engine", force=False)

    # Re-scaffold with force must succeed
    overwritten = scaffold_bc_docs(tmp_path, bc="billing", title="Billing Engine", force=True)
    assert len(overwritten) == 6


def test_handle_scaffold_command_agents(tmp_path: Path, capsys):
    parser = build_parser()
    config = load_config(root_dir=tmp_path)
    (tmp_path / "specops.toml").write_text('[project]\nname = "Test"\n', encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")

    args = argparse.Namespace(command="scaffold", scaffold_action="agents")
    ret = handle_scaffold_command(args, config, parser)
    assert ret == 0
    captured = capsys.readouterr()
    assert "✨" in captured.out


def test_handle_scaffold_command_docs(tmp_path: Path, capsys):
    parser = build_parser()
    config = load_config(root_dir=tmp_path)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")

    # Missing bc
    args_missing = argparse.Namespace(command="scaffold", scaffold_action="docs", bc=None)
    assert handle_scaffold_command(args_missing, config, parser) == 1
    captured = capsys.readouterr()
    assert "--bc / --bounded-context is required" in captured.out

    # Success
    args_ok = argparse.Namespace(
        command="scaffold",
        scaffold_action="docs",
        bc="billing",
        title="Billing Subsystem",
        force=False,
    )
    ret = handle_scaffold_command(args_ok, config, parser)
    assert ret == 0
    captured = capsys.readouterr()
    assert "Successfully scaffolded Diataxis documentation" in captured.out

    # Duplicate without force
    assert handle_scaffold_command(args_ok, config, parser) == 1
    captured = capsys.readouterr()
    assert "already exists" in captured.out

    # Duplicate with force
    args_force = argparse.Namespace(
        command="scaffold",
        scaffold_action="docs",
        bc="billing",
        title="Billing Subsystem",
        force=True,
    )
    assert handle_scaffold_command(args_force, config, parser) == 0

    # Invalid bc
    args_invalid = argparse.Namespace(
        command="scaffold",
        scaffold_action="docs",
        bc="../invalid/bc",
        title=None,
        force=False,
    )
    assert handle_scaffold_command(args_invalid, config, parser) == 1


def test_handle_scaffold_command_help_fallback(tmp_path: Path):
    parser = build_parser()
    config = load_config(root_dir=tmp_path)
    args = argparse.Namespace(command="scaffold", scaffold_action=None)
    with pytest.raises(SystemExit):
        handle_scaffold_command(args, config, parser)


def test_scaffolding_diataxis_audit_clean(tmp_path: Path):
    """Verifies that newly scaffolded bounded context docs immediately pass spec-ops docs audit."""
    parser = build_parser()
    docs_dir = tmp_path / "docs"
    for q in ["tutorials", "how-to", "reference", "explanation", "project"]:
        (docs_dir / q).mkdir(parents=True, exist_ok=True)
        (docs_dir / q / "starter.md").write_text("# Starter\n", encoding="utf-8")
    (docs_dir / "index.md").write_text("# Home\n", encoding="utf-8")
    (docs_dir / "operating-manual.md").write_text("# Operating Manual\n", encoding="utf-8")

    from spec_ops.scaffold.diataxis import DEFAULT_REFERENCE_CLI

    (docs_dir / "reference" / "cli.md").write_text(
        DEFAULT_REFERENCE_CLI.format(project_name="TestProject"), encoding="utf-8"
    )

    scaffold_bc_docs(tmp_path, bc="billing", title="Billing Subsystem")

    auditor = DocsAuditor(docs_dir, parser=parser)
    report = auditor.run_audit()
    assert report.is_clean
    assert len(report.errors) == 0
    assert len(report.warnings) == 0
