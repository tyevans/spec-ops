"""Hypothesis generative property tests for initialization wizard and headless scaffolding (ADR-0009)."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.scaffold.wizard import (
    InitValidationError,
    WizardConfig,
    plan_initialization,
    validate_init_options,
)
from spec_ops.scaffold.init import init_project


# Strategies
VALID_PROJECT_NAMES = st.from_regex(r"[A-Z][a-zA-Z0-9_]{2,12}", fullmatch=True)
AVAILABLE_PROFILES = ["core", "bdd", "ddd", "security"]
VALID_PROFILES_LIST = st.lists(
    st.sampled_from(AVAILABLE_PROFILES),
    min_size=1,
    max_size=4,
    unique=True,
)
AVAILABLE_BCS = ["billing", "orders", "inventory", "shipping", "payments", "identity"]
VALID_BCS_LIST = st.lists(
    st.sampled_from(AVAILABLE_BCS),
    min_size=0,
    max_size=3,
    unique=True,
)


@settings(max_examples=30, deadline=None)
@given(
    project_name=VALID_PROJECT_NAMES,
    profiles=VALID_PROFILES_LIST,
    bounded_contexts=VALID_BCS_LIST,
)
def test_property_dry_run_headless_ast_invariance(
    project_name: str,
    profiles: list[str],
    bounded_contexts: list[str],
):
    """Assert that dry-run plan AST matches headless on-disk AST without side-effects."""
    tmp_base = Path(tempfile.mkdtemp(prefix="specops_hyp_"))
    try:
        headless_dir = tmp_base / "headless"
        dry_run_dir = tmp_base / "dry_run"
        headless_dir.mkdir()
        dry_run_dir.mkdir()

        # 1. Generate plan for dry-run
        dry_config = WizardConfig(
            name=project_name,
            target_dir=dry_run_dir,
            profiles=profiles,
            bounded_contexts=bounded_contexts,
            dry_run=True,
        )
        plan = plan_initialization(dry_config)
        plan_ast = plan.config_ast

        # Assert dry-run directory remains completely empty
        assert len(list(dry_run_dir.iterdir())) == 0, "Dry-run must not create files on disk"

        # 2. Execute headless initialization
        init_project(
            target_dir=headless_dir,
            name=project_name,
            profiles=profiles,
            bounded_contexts=bounded_contexts,
        )

        # 3. Read on-disk specops.toml
        specops_path = headless_dir / "specops.toml"
        assert specops_path.is_file(), "Headless must create specops.toml"
        on_disk_toml = specops_path.read_text(encoding="utf-8")
        disk_ast = tomllib.loads(on_disk_toml)

        # 4. AST Invariance assertion
        assert plan_ast == disk_ast, "Plan AST and on-disk configuration AST must be identical"

        # Receipt verification
        receipt_path = headless_dir / ".specops-scaffold.json"
        assert receipt_path.is_file()

    finally:
        shutil.rmtree(tmp_base, ignore_errors=True)


@settings(max_examples=25, deadline=None)
@given(
    project_name=VALID_PROJECT_NAMES,
    invalid_profile=st.text(
        alphabet=st.characters(categories=["Lu", "Ll"]),
        min_size=3,
        max_size=10,
    ).filter(lambda s: s.lower() not in AVAILABLE_PROFILES and s.lower() != "base"),
)
def test_property_invalid_profile_zero_pollution(project_name: str, invalid_profile: str):
    """Validation failure on invalid profile must raise and cause zero directory pollution."""
    tmp_base = Path(tempfile.mkdtemp(prefix="specops_err_"))
    try:
        target = tmp_base / "target"
        target.mkdir()

        try:
            validate_init_options(project_name, [invalid_profile], [], target)
            assert False, f"Expected InitValidationError for invalid profile '{invalid_profile}'"
        except InitValidationError:
            pass

        # Zero directory pollution
        assert len(list(target.iterdir())) == 0
    finally:
        shutil.rmtree(tmp_base, ignore_errors=True)


@settings(max_examples=20, deadline=None)
@given(
    project_name=VALID_PROJECT_NAMES,
    dup_bc=st.sampled_from(AVAILABLE_BCS),
)
def test_property_duplicate_bc_zero_pollution(project_name: str, dup_bc: str):
    """Validation failure on duplicate bounded context must raise and leave zero files."""
    tmp_base = Path(tempfile.mkdtemp(prefix="specops_dup_"))
    try:
        target = tmp_base / "target"
        target.mkdir()

        try:
            validate_init_options(project_name, ["core"], [dup_bc, dup_bc], target)
            assert False, f"Expected InitValidationError for duplicate bounded context '{dup_bc}'"
        except InitValidationError:
            pass

        assert len(list(target.iterdir())) == 0
    finally:
        shutil.rmtree(tmp_base, ignore_errors=True)
