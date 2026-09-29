"""Unit and mutation tests for secret scanning, entropy, patterns, and dotfile checks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from spec_ops.security.secrets.entropy import is_high_entropy, mask_secret, shannon_entropy
from spec_ops.security.secrets.patterns import is_sensitive_dotfile
from spec_ops.security.secrets.scanner import (
    SecretScanReport,
    SecretViolation,
    scan_diff,
    scan_dotfiles,
    scan_line,
    scan_text,
    scan_worktree,
)


def test_shannon_entropy_basics():
    assert shannon_entropy("") == 0.0
    assert shannon_entropy(b"") == 0.0
    assert shannon_entropy("aaaa") == 0.0
    assert shannon_entropy(b"aaaa") == 0.0
    # Two symbols in equal proportions: 1.0 bit
    assert pytest.approx(shannon_entropy("ab"), 0.01) == 1.0
    assert pytest.approx(shannon_entropy(b"ab"), 0.01) == 1.0
    # Four symbols in equal proportions: 2.0 bits
    assert pytest.approx(shannon_entropy("abcd"), 0.01) == 2.0


def test_shannon_entropy_bounds():
    # Byte distribution with all 256 byte values: exactly 8.0 bits
    all_bytes = bytes(range(256))
    assert pytest.approx(shannon_entropy(all_bytes), 0.001) == 8.0


def test_is_high_entropy():
    # Below min_length
    assert not is_high_entropy("short", threshold=3.5, min_length=16)
    assert not is_high_entropy("123456789012345", threshold=3.5, min_length=16)

    # High entropy strings
    aws_secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert is_high_entropy(aws_secret, threshold=3.7, min_length=16)

    # String with 16 distinct chars has entropy exactly 4.0.
    # Kills mutant mutating default threshold 3.7 -> 4.7
    token_16_unique = "abcdefghijklmnop"
    assert is_high_entropy(token_16_unique)
    assert not is_high_entropy(token_16_unique, threshold=4.5)

    # Boundary min_length = 16: len 15 is False, len 16 is True
    assert not is_high_entropy("abcdefghijklmno", threshold=3.7)
    assert is_high_entropy("abcdefghijklmnop", threshold=3.7)

    # Low entropy repeated string of sufficient length
    low_entropy = "abcdefabcdefabcdefabcdef"
    assert not is_high_entropy(low_entropy, threshold=3.7, min_length=16)


def test_mask_secret_formats():
    assert mask_secret("") == "****"
    assert mask_secret("sk-proj-1234567890abcdef4x9Z") == "sk-proj-****4x9Z"
    assert mask_secret("sk-proj-1234") == "sk-proj-****1234"
    assert mask_secret("sk-proj-123") == "sk-proj-****"

    assert mask_secret("sk-ant-1234567890abcdef4x9Z") == "sk-ant-****4x9Z"
    assert mask_secret("sk-ant-1234") == "sk-ant-****1234"
    assert mask_secret("sk-ant-123") == "sk-ant-****"

    assert mask_secret("sk-1234567890abcdef4x9Z") == "sk-****4x9Z"
    assert mask_secret("sk-1234") == "sk-****1234"
    assert mask_secret("sk-123") == "sk-****"

    assert mask_secret("ghp_1234567890abcdefghijklmnopqrst4x9Z") == "ghp_****4x9Z"
    assert mask_secret("ghp_12345678") == "ghp_****5678"
    assert mask_secret("ghp_1234567") == "ghp_****"

    # Exact entropy threshold equality: kills >= mutated to >
    assert is_high_entropy("ab", threshold=1.0, min_length=2)
    assert not is_high_entropy("ab", threshold=1.0001, min_length=2)

    assert mask_secret("github_pat_123456789012") == "gith****9012"
    assert mask_secret("github_pat_") == "gith****"
    assert mask_secret("AKIAIOSFODNN7EXAMPLE") == "AKIA****MPLE"
    assert mask_secret("AKIA1234") == "AKIA****1234"
    assert mask_secret("AKIA123") == "AKIA****"

    assert mask_secret("-----BEGIN RSA PRIVATE KEY-----") == "-----BEGIN RSA PRIVATE KEY--****"
    assert mask_secret("-----BEGIN SHORT") == "-----BEGIN SHORT****"

    assert mask_secret("123456789012") == "1234****9012"
    assert mask_secret("12345678901") == "12****01"
    assert mask_secret("12345678") == "12****78"
    assert mask_secret("1234567") == "****"
    assert mask_secret("tiny") == "****"


def test_is_sensitive_dotfile():
    assert is_sensitive_dotfile(".env")
    assert is_sensitive_dotfile(".env.production")
    assert is_sensitive_dotfile(".env.local")
    assert is_sensitive_dotfile(".env.development")
    assert is_sensitive_dotfile(".env.staging")
    assert is_sensitive_dotfile(".env.test")
    assert is_sensitive_dotfile(".env.custom_backup")

    assert is_sensitive_dotfile("id_rsa")
    assert is_sensitive_dotfile("id_rsa_backup")
    assert is_sensitive_dotfile("id_ed25519")
    assert is_sensitive_dotfile("id_ed25519_custom")
    assert is_sensitive_dotfile("id_ecdsa")
    assert is_sensitive_dotfile("id_ecdsa_custom")
    assert is_sensitive_dotfile("id_dsa")

    # Excluded files
    assert not is_sensitive_dotfile(".env.example")
    assert not is_sensitive_dotfile(".env.sample")
    assert not is_sensitive_dotfile(".env.template")
    assert not is_sensitive_dotfile(".env.dist")
    assert not is_sensitive_dotfile("id_rsa.pub")
    assert not is_sensitive_dotfile("normal_file.py")


def test_scan_line_openai_and_anthropic():
    line = 'client = OpenAI(api_key="sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z")'
    violations = scan_line(line, line_number=12, file_path="src/app.py")
    assert len(violations) == 1
    assert violations[0].secret_type == "OpenAI/Anthropic API Key"
    assert violations[0].line_number == 12
    assert violations[0].file_path == "src/app.py"
    assert violations[0].masked_token == "sk-proj-****4x9Z"


def test_scan_line_aws_credentials():
    line_id = 'AWS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"'
    violations_id = scan_line(line_id, line_number=5, file_path="src/aws.py")
    assert len(violations_id) == 1
    assert violations_id[0].secret_type == "AWS Access Key ID"
    assert violations_id[0].masked_token == "AKIA****MPLE"

    line_sec = 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
    violations_sec = scan_line(line_sec, line_number=6, file_path="src/aws.py")
    assert len(violations_sec) == 1
    assert violations_sec[0].secret_type == "AWS Secret Access Key"


def test_scan_line_private_key():
    line = "-----BEGIN RSA PRIVATE KEY-----"
    violations = scan_line(line, line_number=1, file_path="keys/id_rsa")
    assert len(violations) == 1
    assert violations[0].secret_type == "Cryptographic Private Key"


def test_scan_line_github_and_slack():
    line_gh = 'token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz12"'
    violations_gh = scan_line(line_gh, line_number=10, file_path="src/gh.py")
    assert any("GitHub" in v.secret_type for v in violations_gh)

    line_slack = 'slack_token = "xoxb-123456789012-1234567890123-abcdefghijklmnopqrstuvwx"'
    violations_slack = scan_line(line_slack, line_number=15, file_path="src/slack.py")
    assert any("Slack" in v.secret_type for v in violations_slack)


def test_scan_line_environment_variables_not_flagged():
    line1 = 'api_key = os.environ.get("OPENAI_API_KEY")'
    line2 = 'aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")'
    line3 = 'token = process.env.GITHUB_TOKEN'
    assert len(scan_line(line1, line_number=1, file_path="src/cfg.py")) == 0
    assert len(scan_line(line2, line_number=2, file_path="src/cfg.py")) == 0
    assert len(scan_line(line3, line_number=3, file_path="src/cfg.py")) == 0


def test_scan_diff_parsing():
    diff_text = """diff --git a/src/client.py b/src/client.py
index 1234567..89abcdef 100644
--- a/src/client.py
+++ b/src/client.py
@@ -10,3 +10,4 @@ def init():
     env = "prod"
+    key = "sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z"
     return True
"""
    violations = scan_diff(diff_text)
    assert len(violations) == 1
    assert violations[0].file_path == "src/client.py"
    assert violations[0].line_number == 11
    assert violations[0].masked_token == "sk-proj-****4x9Z"


def test_scan_dotfiles_in_git_repo(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)

    # 1. Create .env (unignored)
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=BAR\n", encoding="utf-8")

    violations = scan_dotfiles(tmp_path)
    assert len(violations) == 1
    assert violations[0].file_path == ".env"
    assert ".gitignore" in violations[0].action_instructions
    assert "git staging" in violations[0].action_instructions

    # 2. Add to .gitignore
    gi = tmp_path / ".gitignore"
    gi.write_text(".env\n", encoding="utf-8")
    violations_after_ignore = scan_dotfiles(tmp_path)
    assert len(violations_after_ignore) == 0


def test_scan_worktree_clean_and_dirty(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)

    # Initial commit
    f1 = tmp_path / "hello.py"
    f1.write_text("print('hello')\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, check=True)

    # Clean worktree
    report_clean = scan_worktree(tmp_path)
    assert report_clean.is_clean

    # Add secret
    f1.write_text('key = "sk-proj-abc123def456ghi789jkl012mno345pqr4x9Z"\n', encoding="utf-8")
    report_dirty = scan_worktree(tmp_path)
    assert not report_dirty.is_clean
    assert len(report_dirty.secret_violations) == 1
    diag = report_dirty.format_diagnostics()
    assert "sk-proj-****4x9Z" in diag
    assert "hello.py" in diag
