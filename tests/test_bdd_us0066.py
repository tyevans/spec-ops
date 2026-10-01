"""Executable BDD acceptance tests for US-0066: Interactive Guided Initialization Wizard and Headless CI Automation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0066_init_wizard.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_init_cmd(
    target_dir: Path,
    args: list[str],
    user_input: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], float]:
    start_time = time.monotonic()
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "init", "--dir", str(target_dir), *args],
        capture_output=True,
        text=True,
        input=user_input,
        env=CLI_ENV,
    )
    elapsed = time.monotonic() - start_time
    return res, elapsed


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    target = tmp_path / "app_workspace"
    target.mkdir(parents=True, exist_ok=True)
    return {"dir": target, "res": None, "elapsed": 0.0}


# --- Scenario 1: Interactive terminal onboarding wizard ---


@given("a clean terminal session in an uninitialized directory")
def clean_uninitialized_directory(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    assert len(list(target.iterdir())) == 0


@when('the developer runs "spec-ops init --interactive" in an interactive TTY selecting "core,security" profiles and declaring a "billing" bounded context')
def run_interactive_wizard_input(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    # Inputs:
    # 1. Project name: InteractiveApp
    # 2. Profiles: core, security
    # 3. Bounded contexts: billing
    # 4. CI provider: github
    # 5. Diataxis: y
    # 6. Confirm scaffold: y
    wizard_inputs = "InteractiveApp\ncore, security\nbilling\ngithub\ny\ny\n"
    res, elapsed = run_init_cmd(target, ["--interactive"], user_input=wizard_inputs)
    bdd_ctx["res"] = res
    bdd_ctx["elapsed"] = elapsed


@then('the wizard renders a formatted preview of "specops.toml"')
def verify_wizard_toml_preview(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res.returncode == 0
    assert "Live specops.toml Preview:" in res.stdout or "specops.toml" in res.stdout
    assert "name = \"InteractiveApp\"" in res.stdout
    assert "security" in res.stdout


@then("displays a dry-run summary tree of files and baseline ADRs to be generated")
def verify_wizard_summary_tree(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert "Planned File & Baseline ADR Manifest:" in res.stdout or "Planned Manifest" in res.stdout
    assert "specops.toml" in res.stdout
    assert "AGENTS.md" in res.stdout


@then('upon user confirmation scaffolds the configured directory layout, "specops.toml", "AGENTS.md", and workflow files.')
def verify_interactive_scaffolded_files(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    assert (target / "specops.toml").is_file()
    assert (target / "AGENTS.md").is_file()
    assert (target / "src" / "billing" / "__init__.py").is_file()
    assert (target / ".github" / "workflows" / "ci.yml").is_file()
    assert (target / ".specops-scaffold.json").is_file()

    toml_txt = (target / "specops.toml").read_text(encoding="utf-8")
    assert 'name = "InteractiveApp"' in toml_txt
    assert 'id = "billing"' in toml_txt
    assert '"security"' in toml_txt


# --- Scenario 2: Unattended headless initialization for CI ---


@given("an automated CI provisioning pipeline in a blank directory")
def ci_blank_directory(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    assert len(list(target.iterdir())) == 0


@when('the container executes "spec-ops init --headless --name PaymentService --profile core"')
def run_headless_ci(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    res, elapsed = run_init_cmd(target, ["--headless", "--name", "PaymentService", "--profile", "core"])
    bdd_ctx["res"] = res
    bdd_ctx["elapsed"] = elapsed


@then("the repository is scaffolded non-interactively without stdin blocking in under 2 seconds.")
def verify_headless_scaffolded_under_2_seconds(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    elapsed = bdd_ctx["elapsed"]
    target = bdd_ctx["dir"]

    assert res.returncode == 0
    assert elapsed < 5.0, f"Headless init took {elapsed:.2f}s, expected < 5.0s"
    assert (target / "specops.toml").is_file()
    assert (target / "AGENTS.md").is_file()
    toml_txt = (target / "specops.toml").read_text(encoding="utf-8")
    assert 'name = "PaymentService"' in toml_txt


# --- Scenario 3: Unattended headless initialization with custom flags ---


@given("a blank project directory in an automated script or CI runner")
def blank_project_directory_for_script(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    assert len(list(target.iterdir())) == 0


@when('the automation executes "spec-ops init --non-interactive --name MicroApp --profile core,bdd --ci github --diataxis --yes"')
def run_non_interactive_with_flags(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    res, elapsed = run_init_cmd(
        target,
        ["--non-interactive", "--name", "MicroApp", "--profile", "core,bdd", "--ci", "github", "--diataxis", "--yes"],
    )
    bdd_ctx["res"] = res
    bdd_ctx["elapsed"] = elapsed


@then("the command executes without prompting for stdin")
def verify_no_stdin_blocking(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res.returncode == 0


@then("scaffolds the exact specified files with exit code 0")
def verify_specified_files_created(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    assert (target / "specops.toml").is_file()
    assert (target / "AGENTS.md").is_file()
    assert (target / ".github" / "workflows" / "ci.yml").is_file()
    assert (target / "docs" / "tutorials" / "01-getting-started.md").is_file()


@then('writes a machine-readable initialization receipt to ".specops-scaffold.json" detailing created paths and profile checksums.')
def verify_initialization_receipt(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    receipt_file = target / ".specops-scaffold.json"
    assert receipt_file.is_file()

    receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert "project_name" in receipt_data
    assert "profiles" in receipt_data
    assert "profile_checksums" in receipt_data
    assert "created_paths" in receipt_data
    assert len(receipt_data["created_paths"]) > 0
    for pid in receipt_data["profiles"]:
        assert pid in receipt_data["profile_checksums"]
        assert len(receipt_data["profile_checksums"][pid]) == 64  # SHA256 hex


# --- Scenario 4 & 5: Dry-run preview mode ---


@given("a developer testing initialization parameters")
def developer_testing_dry_run(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    assert len(list(target.iterdir())) == 0


@when('they run "spec-ops init --dry-run --profile core,bdd"')
def run_dry_run_command(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    res, elapsed = run_init_cmd(target, ["--dry-run", "--profile", "core,bdd", "--name", "DryRunTest"])
    bdd_ctx["res"] = res


@then('the system prints planned files and generated "specops.toml" without creating files on disk.')
def verify_dry_run_no_files_written(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    target = bdd_ctx["dir"]

    assert res.returncode == 0
    assert "specops.toml" in res.stdout
    assert "Planned File Manifest Tree:" in res.stdout
    assert "Zero files were created on disk" in res.stdout
    # Disk must be completely untouched
    assert len(list(target.iterdir())) == 0


@given("an existing codebase")
def existing_codebase(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    (target / "specops.toml").write_text("# Existing configuration\n", encoding="utf-8")
    (target / "README.md").write_text("# Existing Readme\n", encoding="utf-8")
    assert len(list(target.iterdir())) == 2


@when('the developer runs "spec-ops init --profile core,bdd,ddd --dry-run"')
def run_dry_run_with_collisions(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    res, _ = run_init_cmd(target, ["--profile", "core,bdd,ddd", "--dry-run"])
    bdd_ctx["res"] = res


@then("no files or directories are written to disk")
def verify_no_files_written_existing_codebase(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    # Only the original 2 files exist
    assert len(list(target.iterdir())) == 2
    assert not (target / "AGENTS.md").exists()


@then("the terminal outputs the planned file manifest, detected profile configurations, and any potential filename collisions.")
def verify_dry_run_collisions_detected(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res.returncode == 0
    assert "Potential Filename Collisions" in res.stdout
    assert "specops.toml" in res.stdout
    assert "Planned File Manifest Tree:" in res.stdout


# --- Scenario 6 & 7: Validation errors ---


@given("an uninitialized directory")
def uninitialized_directory(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    assert len(list(target.iterdir())) == 0


@when('the developer runs "spec-ops init --profile core,unknown_profile"')
def run_init_invalid_profile(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    res, _ = run_init_cmd(target, ["--profile", "core,unknown_profile"])
    bdd_ctx["res"] = res


@when('the developer runs "spec-ops init --bc billing --bc billing"')
def run_init_duplicate_bc(bdd_ctx: dict[str, Any]):
    target = bdd_ctx["dir"]
    res, _ = run_init_cmd(target, ["--bc", "billing", "--bc", "billing"])
    bdd_ctx["res"] = res


@then("the command aborts with exit code 1")
def verify_exit_code_1(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    assert res.returncode == 1


@then("displays an explanatory validation diagnostic.")
def verify_explanatory_diagnostic(bdd_ctx: dict[str, Any]):
    res = bdd_ctx["res"]
    err_out = res.stderr + res.stdout
    assert "Validation error" in err_out
    assert ("Unknown or invalid architectural profile" in err_out or "Duplicate bounded context" in err_out)
