"""Executable BDD test runner for US-0110: Real-Time Secret and High-Entropy Credential Detection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.worker import BacklogWorkerEngine
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

scenarios("features/us_0110_secret_detection_worktree_diffs.feature")


@pytest.fixture
def bdd_us0110_context(tmp_path: Path) -> dict[str, Any]:
    """Sets up an isolated git repository for US-0110 scenarios."""
    init_project(tmp_path, name="US0110SecretRepo", profiles=["core", "bdd", "ddd", "security"])

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Security Officer Sasha"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "sasha@specops.dev"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial scaffold"], cwd=tmp_path, check=True)

    return {"dir": tmp_path, "res": None, "feedback": "", "preflight_ok": None}


@given("an autonomous agent worktree where an agent or developer has written an OpenAI API key, AWS secret access key, or RSA private key into a source file")
def developer_writes_secrets_into_file(bdd_us0110_context: dict[str, Any]):
    target = bdd_us0110_context["dir"]
    src_file = target / "src" / "app.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text(
        "# Configuration\n"
        "import os\n\n"
        "def init():\n"
        '    return "sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z"\n',  # pragma: allowlist secret
        encoding="utf-8",
    )


@given("an autonomous agent worktree with feature modifications referencing credentials strictly through environment variables")
def agent_worktree_with_env_var_credentials(bdd_us0110_context: dict[str, Any]):
    target = bdd_us0110_context["dir"]
    src_file = target / "src" / "config.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text(
        "import os\n\n"
        'api_key = os.environ.get("OPENAI_API_KEY")\n'
        'aws_key = os.getenv("AWS_SECRET_ACCESS_KEY")\n',
        encoding="utf-8",
    )


@given('an autonomous worker session where the agent generates a ".env", ".env.production", or "id_rsa" file')
def agent_generates_sensitive_dotfile(bdd_us0110_context: dict[str, Any]):
    target = bdd_us0110_context["dir"]
    dotfile = target / ".env.production"
    dotfile.write_text("DATABASE_PASSWORD=supersecretpassword123!\n", encoding="utf-8")


@when('the worker engine executes "spec-ops health --security" prior to git commit')
def worker_executes_health_security_cli(bdd_us0110_context: dict[str, Any]):
    target = bdd_us0110_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health", "--security"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_us0110_context["res"] = res
    bdd_us0110_context["feedback"] = res.stdout


@when('the preflight command "spec-ops health --security" executes')
def preflight_command_health_security_executes(bdd_us0110_context: dict[str, Any]):
    target = bdd_us0110_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health", "--security"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_us0110_context["res"] = res


@when("the worker engine executes preflight verification")
def worker_engine_executes_preflight_for_dotfile(bdd_us0110_context: dict[str, Any]):
    target = bdd_us0110_context["dir"]
    cfg = load_config(target)
    engine = BacklogWorkerEngine(cfg)
    ok, feedback = engine.run_preflight(target)
    bdd_us0110_context["preflight_ok"] = ok
    bdd_us0110_context["feedback"] = feedback

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health", "--security"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_us0110_context["res"] = res


@then("the scanner detects the high-entropy credential pattern")
def verify_scanner_detects_high_entropy_pattern(bdd_us0110_context: dict[str, Any]):
    output = bdd_us0110_context["res"].stdout
    assert "High-entropy secret" in output or "sk-proj-****4x9Z" in output


@then("the preflight check exits with returncode 1, aborting the commit")
def verify_preflight_aborts_commit(bdd_us0110_context: dict[str, Any]):
    assert bdd_us0110_context["res"].returncode == 1
    if bdd_us0110_context["preflight_ok"] is not None:
        assert bdd_us0110_context["preflight_ok"] is False


@then(parsers.parse('diagnostic feedback listing the offending file path, line number, and masked token snippet (e.g., "{example}") is returned to the agent prompt for self-healing remediation.'))
def verify_diagnostic_feedback_full(bdd_us0110_context: dict[str, Any], example: str):
    combined = bdd_us0110_context["res"].stdout + "\n" + bdd_us0110_context["feedback"]
    assert "app.py" in combined
    assert "sk-proj-****4x9Z" in combined


@then('"spec-ops health --security" flags the presence of unignored sensitive files')
def verify_flags_unignored_sensitive_files(bdd_us0110_context: dict[str, Any]):
    output = bdd_us0110_context["res"].stdout
    assert "Unignored sensitive file detected" in output or ".env.production" in output


@then('the commit is aborted with actionable instructions to add the file to ".gitignore" and remove it from git staging.')
def verify_commit_aborted_with_gitignore_staging_instructions(bdd_us0110_context: dict[str, Any]):
    assert bdd_us0110_context["res"].returncode == 1
    combined = bdd_us0110_context["res"].stdout + "\n" + bdd_us0110_context["feedback"]
    assert ".gitignore" in combined
    assert "staging" in combined


@then("the check exits with returncode 0")
def verify_check_exits_zero(bdd_us0110_context: dict[str, Any]):
    assert bdd_us0110_context["res"].returncode == 0


@then('reports "Security Invariant Met: 0 credential leaks detected in working tree".')
def verify_security_invariant_met_in_working_tree(bdd_us0110_context: dict[str, Any]):
    assert "Security Invariant Met: 0 credential leaks detected in working tree" in bdd_us0110_context["res"].stdout
