"""Unit tests for automated pre-commit git hook installer and supply-chain sentinel."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.security.git_hooks import (
    HOOK_END_MARKER,
    HOOK_START_MARKER,
    install_hook,
    resolve_hooks_dir,
    run_hook_sentinel,
    uninstall_hook,
    verify_hook,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "test_repo"
    repo.mkdir()
    init_project(name="UnitHookApp", target_dir=repo)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def test_install_and_uninstall_lifecycle(git_repo: Path):
    hooks_dir = resolve_hooks_dir(git_repo)
    hook_file = hooks_dir / "pre-commit"

    # Initially no hook exists
    assert not hook_file.exists()
    ok_ver, _ = verify_hook(git_repo)
    assert not ok_ver

    # Install
    ok, path, msg = install_hook(git_repo)
    assert ok
    assert path == hook_file
    assert hook_file.is_file()
    assert os.access(hook_file, os.X_OK)

    # Verify
    ok_ver, msg_ver = verify_hook(git_repo)
    assert ok_ver
    assert "verified" in msg_ver.lower()

    # Uninstall
    ok_un, path_un, msg_un = uninstall_hook(git_repo)
    assert ok_un
    assert not hook_file.exists()


def test_install_preserves_custom_hook(git_repo: Path):
    hooks_dir = resolve_hooks_dir(git_repo)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "pre-commit"

    custom_script = "#!/bin/sh\n# Custom CI hook\necho 'running lint'\n"
    hook_file.write_text(custom_script, encoding="utf-8")
    hook_file.chmod(0o755)

    # Install SpecOps hook into existing script
    ok, _, _ = install_hook(git_repo)
    assert ok
    content = hook_file.read_text(encoding="utf-8")
    assert "running lint" in content
    assert HOOK_START_MARKER in content
    assert HOOK_END_MARKER in content

    # Uninstall should cleanly restore custom script
    ok_un, _, _ = uninstall_hook(git_repo)
    assert ok_un
    assert hook_file.is_file()
    assert hook_file.read_text(encoding="utf-8") == custom_script


def test_verify_hook_failure_conditions(git_repo: Path):
    hooks_dir = resolve_hooks_dir(git_repo)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "pre-commit"

    # Missing file
    if hook_file.exists():
        hook_file.unlink()
    ok, msg = verify_hook(git_repo)
    assert not ok
    assert "not found" in msg.lower()

    # Non-executable file
    hook_file.write_text(f"#!/bin/sh\n{HOOK_START_MARKER}\n{HOOK_END_MARKER}\n", encoding="utf-8")
    hook_file.chmod(0o644)
    ok, msg = verify_hook(git_repo)
    assert not ok
    assert "not executable" in msg.lower()

    # Executable but missing sentinel marker
    hook_file.write_text("#!/bin/sh\necho 'hello'\n", encoding="utf-8")
    hook_file.chmod(0o755)
    ok, msg = verify_hook(git_repo)
    assert not ok
    assert "missing specops sentinel" in msg.lower()


def test_run_hook_sentinel_empty_staged(git_repo: Path):
    res = run_hook_sentinel(git_repo)
    assert res.ok
    assert res.staged_files_count == 0
    assert len(res.violations) == 0


def test_run_hook_sentinel_clean_staged(git_repo: Path):
    clean_file = git_repo / "src" / "clean_module.py"
    clean_file.parent.mkdir(parents=True, exist_ok=True)
    clean_file.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")

    subprocess.run(["git", "add", "src/clean_module.py"], cwd=git_repo, check=True)

    res = run_hook_sentinel(git_repo)
    assert res.ok
    assert res.staged_files_count >= 1
    assert len(res.violations) == 0


def test_run_hook_sentinel_blocks_unapproved_lockfile(git_repo: Path):
    lockfile = git_repo / "uv.lock"
    lockfile.write_text("# unapproved package tampering\n[package]\nname = 'malicious'\n", encoding="utf-8")

    subprocess.run(["git", "add", "uv.lock"], cwd=git_repo, check=True)

    res = run_hook_sentinel(git_repo)
    assert not res.ok
    assert not res.lockfile_ok
    assert any("uv.lock" in v for v in res.violations)
    assert any("ADR-0018" in v for v in res.violations)


def test_run_hook_sentinel_allows_waived_lockfile(git_repo: Path):
    # Configure waiver in specops.toml
    cfg_file = git_repo / "specops.toml"
    cfg_content = cfg_file.read_text(encoding="utf-8")
    cfg_content += "\n[security]\nlockfile_immutability = false\n"
    cfg_file.write_text(cfg_content, encoding="utf-8")

    lockfile = git_repo / "uv.lock"
    lockfile.write_text("# waived lockfile update\n", encoding="utf-8")
    subprocess.run(["git", "add", "uv.lock"], cwd=git_repo, check=True)

    config = load_config(root_dir=git_repo)
    res = run_hook_sentinel(git_repo, config=config)
    assert res.ok
    assert res.lockfile_ok


def test_run_hook_sentinel_blocks_secrets(git_repo: Path):
    secret_file = git_repo / "config.py"
    secret_file.write_text(
        "OPENAI_API_KEY = 'sk-proj-abcdef1234567890abcdef1234567890'\n",  # pragma: allowlist secret
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "config.py"], cwd=git_repo, check=True)

    res = run_hook_sentinel(git_repo)
    assert not res.ok
    assert not res.secrets_ok
    assert any("ADR-0019" in v for v in res.violations)


def test_run_hook_sentinel_blocks_oversized_file(git_repo: Path):
    oversized = git_repo / "oversized_module.py"
    # Write 510 lines
    oversized.write_text("\n".join([f"# line {i}" for i in range(510)]) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "oversized_module.py"], cwd=git_repo, check=True)

    res = run_hook_sentinel(git_repo)
    assert not res.ok
    assert not res.file_lengths_ok
    assert any("ADR-0002" in v for v in res.violations)


def test_cli_hook_subcommands(git_repo: Path, monkeypatch):
    monkeypatch.chdir(git_repo)

    # CLI install
    assert main(["security", "hook", "install"]) == 0
    # CLI verify
    assert main(["security", "hook", "verify"]) == 0
    # CLI run on clean staged
    assert main(["security", "hook", "run"]) == 0
    # CLI uninstall
    assert main(["security", "hook", "uninstall"]) == 0
    # CLI verify after uninstall fails
    assert main(["security", "hook", "verify"]) == 1
