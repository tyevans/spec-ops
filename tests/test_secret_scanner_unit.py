"""Unit tests for secret scanning, entropy analysis, inline suppression, and CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.security.secrets.dotfiles import scan_dotfiles
from spec_ops.security.secrets.entropy import is_high_entropy, mask_secret, shannon_entropy
from spec_ops.security.secrets.models import SecretScanReport, SecretViolation
from spec_ops.security.secrets.patterns import is_sensitive_dotfile
from spec_ops.security.secrets.scanner import (
    scan_diff,
    scan_file,
    scan_line,
    scan_text,
    scan_worktree,
)
from spec_ops.worker.hooks import PreCommitHookEvaluator


def test_shannon_entropy_basics():
    assert shannon_entropy("") == 0.0
    assert shannon_entropy(b"") == 0.0
    assert shannon_entropy("aaaa") == 0.0
    assert pytest.approx(shannon_entropy("ab"), 0.01) == 1.0
    assert pytest.approx(shannon_entropy("abcd"), 0.01) == 2.0


def test_is_high_entropy():
    assert not is_high_entropy("short", threshold=3.5, min_length=16)
    assert not is_high_entropy("123456789012345", threshold=3.5, min_length=16)
    aws_secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # pragma: allowlist secret
    assert is_high_entropy(aws_secret, threshold=3.7, min_length=16)
    token_16_unique = "abcdefghijklmnop"
    assert is_high_entropy(token_16_unique)
    assert not is_high_entropy(token_16_unique, threshold=4.5)


def test_mask_secret_formats():
    assert mask_secret("") == "****"
    assert mask_secret("sk-proj-1234567890abcdef4x9Z") == "sk-proj-****4x9Z"  # pragma: allowlist secret
    assert mask_secret("sk-ant-1234567890abcdef4x9Z") == "sk-ant-****4x9Z"  # pragma: allowlist secret
    assert mask_secret("ghp_1234567890abcdefghijklmnopqrst4x9Z") == "ghp_****4x9Z"  # pragma: allowlist secret
    assert mask_secret("AKIAIOSFODNN7EXAMPLE") == "AKIA****MPLE"  # pragma: allowlist secret
    assert mask_secret("-----BEGIN RSA PRIVATE KEY-----") == "-----BEGIN RSA PRIVATE KEY--****"  # pragma: allowlist secret


def test_is_sensitive_dotfile():
    assert is_sensitive_dotfile(".env")
    assert is_sensitive_dotfile(".env.production")
    assert is_sensitive_dotfile("id_rsa")
    assert not is_sensitive_dotfile(".env.example")
    assert not is_sensitive_dotfile("id_rsa.pub")
    assert not is_sensitive_dotfile("main.py")


def test_scan_line_inline_suppression():
    # Secret without ignore directive
    line_raw = 'client = OpenAI(api_key="sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z")'  # pragma: allowlist secret
    assert len(scan_line(line_raw)) == 1

    # Secret with # spec-ops:ignore-secret
    line_ignored_1 = f'{line_raw}  # spec-ops:ignore-secret'
    assert len(scan_line(line_ignored_1)) == 0

    # Secret with # pragma: allowlist secret
    line_ignored_2 = f'{line_raw}  # pragma: allowlist secret'
    assert len(scan_line(line_ignored_2)) == 0

    # Secret with // spec-ops:ignore-secret
    line_ignored_3 = f'{line_raw}  // spec-ops:ignore-secret'
    assert len(scan_line(line_ignored_3)) == 0

    # Secret with comment whitespace variations
    line_ignored_4 = f'{line_raw}  # spec-ops: ignore-secret'
    assert len(scan_line(line_ignored_4)) == 0


def test_scan_file(tmp_path: Path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("import os\nprint(os.getenv('KEY'))\n", encoding="utf-8")
    rep_clean = scan_file(clean_file)
    assert rep_clean.is_clean

    dirty_file = tmp_path / "dirty.py"
    dirty_file.write_text('KEY = "sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z"\n', encoding="utf-8")  # pragma: allowlist secret
    rep_dirty = scan_file(dirty_file)
    assert not rep_dirty.is_clean
    assert len(rep_dirty.secret_violations) == 1


from spec_ops.scaffold.init import init_project


def test_pre_commit_hook_evaluator_rejects_secrets(tmp_path: Path):
    init_project(name="HookApp", target_dir=tmp_path)
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tester@test.dev"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)


    evaluator = PreCommitHookEvaluator(root_dir=tmp_path)
    res_clean = evaluator.evaluate()
    assert res_clean.success is True
    assert res_clean.exit_code == 0

    # Add secret to working tree
    src = tmp_path / "app.py"
    src.write_text('SECRET = "sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z"\n', encoding="utf-8")  # pragma: allowlist secret
    res_dirty = evaluator.evaluate()
    assert res_dirty.success is False
    assert res_dirty.exit_code == 1
    assert "Secret Scanning & Credential Leak Violations" in res_dirty.output
    assert "sk-proj-****4x9Z" in res_dirty.output


def test_scan_secrets_cli_clean_and_dirty(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tester@test.dev"], cwd=tmp_path, check=True)

    # 1. Clean run
    res_clean = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "security", "scan-secrets", "--path", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res_clean.returncode == 0
    assert "0 credential leaks detected" in res_clean.stdout

    # 2. Add secret
    leak_file = tmp_path / "secrets.py"
    leak_file.write_text('key = "sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z"\n', encoding="utf-8")  # pragma: allowlist secret

    res_dirty = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "security", "scan-secrets", "--path", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res_dirty.returncode == 1
    assert "sk-proj-****4x9Z" in res_dirty.stderr or "sk-proj-****4x9Z" in res_dirty.stdout

    # 3. JSON format
    res_json = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "security", "scan-secrets", "--path", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
    )
    assert res_json.returncode == 1
    data = json.loads(res_json.stdout)
    assert data["is_clean"] is False
    assert len(data["secret_violations"]) == 1

    # 4. Inline suppression suppresses violation
    leak_file.write_text('key = "sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z"  # spec-ops:ignore-secret\n', encoding="utf-8")
    res_suppressed = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "security", "scan-secrets", "--path", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res_suppressed.returncode == 0
    assert "0 credential leaks detected" in res_suppressed.stdout


def test_scan_secrets_cli_staged_only(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tester@test.dev"], cwd=tmp_path, check=True)

    # Initial commit
    init_f = tmp_path / "README.md"
    init_f.write_text("# Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # Unstaged secret
    unstaged_file = tmp_path / "unstaged.py"
    unstaged_file.write_text('api_key = "sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z"\n', encoding="utf-8")  # pragma: allowlist secret

    # With --staged, unstaged file is not flagged
    res_staged = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "security", "scan-secrets", "--path", str(tmp_path), "--staged"],
        capture_output=True,
        text=True,
    )
    assert res_staged.returncode == 0

    # Stage the file
    subprocess.run(["git", "add", "unstaged.py"], cwd=tmp_path, check=True)
    res_staged_dirty = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "security", "scan-secrets", "--path", str(tmp_path), "--staged"],
        capture_output=True,
        text=True,
    )
    assert res_staged_dirty.returncode == 1
    assert "sk-proj-****4x9Z" in res_staged_dirty.stderr or "sk-proj-****4x9Z" in res_staged_dirty.stdout
