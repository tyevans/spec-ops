"""Comprehensive unit tests for Shannon entropy secret scanner rule plugin engine."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.security.entropy_plugins import (
    EntropyFinding,
    EntropyRule,
    EntropyScannerConfig,
    ShannonEntropyScanner,
    calculate_entropy,
)

# High-entropy test tokens with pragma allowlist annotations
SAMPLE_BASE64_TOKEN = "v7mK9pL2xR4wT8qZ1yB3cD5fG6hJ0kM9nQ2sU4vW7xY="  # pragma: allowlist secret
SAMPLE_HEX_TOKEN = "a1b2c3d4e5f67890123456789abcdef012345678"  # pragma: allowlist secret
SAMPLE_UUID = "c9a646d3-9c61-4cd9-bc15-47044d6fb330"  # pragma: allowlist secret
SAMPLE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # pragma: allowlist secret


def test_calculate_entropy_edge_cases():
    assert calculate_entropy("") == 0.0
    assert calculate_entropy("a") == 0.0
    assert calculate_entropy("zzzzzzzzzz") == 0.0
    assert calculate_entropy("01" * 50) == 1.0
    assert calculate_entropy(SAMPLE_BASE64_TOKEN) > 4.5  # pragma: allowlist secret


def test_entropy_rule_validation():
    rule = EntropyRule(name="test-rule", threshold=4.2, min_length=16, alphabet_type="hex")
    assert rule.name == "test-rule"
    assert rule.threshold == 4.2
    assert rule.min_length == 16
    assert rule.alphabet_type == "hex"

    with pytest.raises(ValueError, match="Invalid alphabet_type"):
        EntropyRule(name="invalid", alphabet_type="invalid_alphabet")


def test_entropy_finding_attributes_and_masking():
    finding = EntropyFinding(
        token=SAMPLE_BASE64_TOKEN,  # pragma: allowlist secret
        line_number=42,
        file_path="src/config.py",
        entropy=4.85,
        rule_name="b64-rule",
        reason="Exceeded threshold",
    )
    assert finding.token == SAMPLE_BASE64_TOKEN  # pragma: allowlist secret
    assert finding.line_number == 42
    assert finding.masked_token.startswith("v7mK****")
    assert finding.masked_token.endswith("7xY=")

    d = finding.to_dict()
    assert d["line_number"] == 42
    assert d["rule_name"] == "b64-rule"
    assert d["entropy"] == 4.85

    short_finding = EntropyFinding(
        token="short",
        line_number=1,
        file_path="test.py",
        entropy=2.0,
        rule_name="short-rule",
        reason="test",
    )
    assert short_finding.masked_token == "****"


def test_entropy_scanner_config_serialization(tmp_path: Path):
    yaml_content = """
entropy:
  threshold: 4.8
  ignore_uuids: true
  ignore_shas: false
  allowlist_patterns:
    - "^TEST_SECRET_.*"
  rules:
    - name: "custom-api"
      threshold: 4.2
      min_length: 25
      alphabet_type: "base64"
      custom_regex: "API_KEY_[A-Za-z0-9+/=]{25,}"
"""
    config = EntropyScannerConfig.from_yaml(yaml_content)
    assert config.ignore_uuids is True
    assert config.ignore_shas is False
    assert "^TEST_SECRET_.*" in config.allowlist_patterns
    assert len(config.rules) == 1
    assert config.rules[0].name == "custom-api"
    assert config.rules[0].threshold == 4.2
    assert config.rules[0].alphabet_type == "base64"

    # Test loading from project directory
    proj_dir = tmp_path / "my_project"
    specops_dir = proj_dir / ".specops"
    specops_dir.mkdir(parents=True)
    (specops_dir / "security.yaml").write_text(yaml_content, encoding="utf-8")

    loaded_config = EntropyScannerConfig.load_from_project(proj_dir)
    assert len(loaded_config.rules) == 1
    assert loaded_config.rules[0].name == "custom-api"


def test_scanner_with_custom_regex_rule():
    config = EntropyScannerConfig(
        rules=[
            EntropyRule(
                name="custom-jwt",
                threshold=3.0,
                min_length=10,
                custom_regex=r"JWT_TOKEN\s*=\s*['\"]([^'\"]+)['\"]",
            )
        ]
    )
    scanner = ShannonEntropyScanner(config)

    content = f'JWT_TOKEN = "{SAMPLE_BASE64_TOKEN}"\nOTHER_TOKEN = "ignored_token_value_here"\n'  # pragma: allowlist secret
    findings = scanner.scan_text(content, file_path="auth.py")

    assert len(findings) == 1
    assert findings[0].rule_name == "custom-jwt"
    assert findings[0].token == SAMPLE_BASE64_TOKEN  # pragma: allowlist secret


def test_scanner_uuid_and_sha_filters():
    config = EntropyScannerConfig(
        rules=[EntropyRule(name="all-rule", threshold=1.0, min_length=10, alphabet_type="all")],
        ignore_uuids=True,
        ignore_shas=True,
    )
    scanner = ShannonEntropyScanner(config)

    text = f"""
UUID_VAL = "{SAMPLE_UUID}"
SHA_VAL = "{SAMPLE_SHA256}"
"""  # pragma: allowlist secret
    findings = scanner.scan_text(text)
    assert len(findings) == 0


def test_scanner_allowlist_patterns():
    config = EntropyScannerConfig(
        rules=[EntropyRule(name="all-rule", threshold=1.0, min_length=10, alphabet_type="all")],
        allowlist_patterns=["^SAFE_.*"],
    )
    scanner = ShannonEntropyScanner(config)

    text = f'SAFE_TOKEN = "{SAMPLE_BASE64_TOKEN}"\n'  # pragma: allowlist secret
    findings = scanner.scan_text(text)
    # The pattern matches the token or prefix
    scanner.config.allowlist_patterns = [SAMPLE_BASE64_TOKEN[:10]]  # pragma: allowlist secret
    findings = scanner.scan_text(f'VAL = "{SAMPLE_BASE64_TOKEN}"\n')  # pragma: allowlist secret
    assert len(findings) == 0


def test_scanner_pragma_allowlist_variations():
    scanner = ShannonEntropyScanner(
        EntropyScannerConfig(
            rules=[EntropyRule(name="all-rule", threshold=1.0, min_length=10, alphabet_type="all")]
        )
    )

    # 1. Same line pragma
    line1 = f'KEY1 = "{SAMPLE_BASE64_TOKEN}"  # pragma: allowlist secret\n'  # pragma: allowlist secret
    assert len(scanner.scan_text(line1)) == 0

    # 2. Previous line pragma
    text2 = f'# pragma: allowlist secret\nKEY2 = "{SAMPLE_BASE64_TOKEN}"\n'  # pragma: allowlist secret
    assert len(scanner.scan_text(text2)) == 0

    # 3. Unannotated line should be flagged
    text3 = f'KEY3 = "{SAMPLE_BASE64_TOKEN}"\n'  # pragma: allowlist secret
    assert len(scanner.scan_text(text3)) == 1


def test_scanner_file_and_directory_scan(tmp_path: Path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    dirty_file = tmp_path / "dirty.py"
    dirty_file.write_text(f'SECRET = "{SAMPLE_BASE64_TOKEN}"\n', encoding="utf-8")  # pragma: allowlist secret

    scanner = ShannonEntropyScanner()
    clean_findings = scanner.scan_file(clean_file)
    assert len(clean_findings) == 0

    dirty_findings = scanner.scan_file(dirty_file)
    assert len(dirty_findings) == 1

    dir_findings = scanner.scan_directory(tmp_path)
    assert len(dir_findings) == 1
    assert dir_findings[0].file_path == str(dirty_file)


def test_cli_security_scan_frontdoor(tmp_path: Path):
    # Test CLI invocation with clean directory
    clean_dir = tmp_path / "clean_proj"
    clean_dir.mkdir()
    (clean_dir / "main.py").write_text("print('clean')\n", encoding="utf-8")

    res_clean = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "security",
            "scan",
            "--entropy",
            "--path",
            str(clean_dir),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert res_clean.returncode == 0
    data = json.loads(res_clean.stdout)
    assert data["is_clean"] is True
    assert data["findings_count"] == 0

    # Test CLI invocation with dirty file
    dirty_file = tmp_path / "dirty.py"
    dirty_file.write_text(f'SECRET_KEY = "{SAMPLE_BASE64_TOKEN}"\n', encoding="utf-8")  # pragma: allowlist secret

    res_dirty = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "security",
            "scan",
            "--entropy",
            "--threshold",
            "4.0",
            "--path",
            str(dirty_file),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert res_dirty.returncode == 1
    data_dirty = json.loads(res_dirty.stdout)
    assert data_dirty["is_clean"] is False
    assert data_dirty["findings_count"] >= 1
