"""Tests for SpecOps configuration loading."""

from pathlib import Path

from spec_ops.config.loader import find_config_file, load_config
from spec_ops.config.models import SpecOpsConfig


def test_default_config_fallback(tmp_path: Path):
    cfg = load_config(root_dir=tmp_path)
    assert isinstance(cfg, SpecOpsConfig)
    assert cfg.architecture.file_length_limit == 500
    assert cfg.architecture.buffer_target == 10
    assert len(cfg.vertical_slices) > 0
    assert cfg.quality.testing_style == "blackbox-frontdoor"


def test_custom_specops_toml(tmp_path: Path):
    toml_content = """
[project]
name = "TestPlatform"
repo = "org/test-platform"
docs_dir = "docs/spec"

[architecture]
file_length_limit = 400
buffer_target = 8
buffer_warning_threshold = 4

[[architecture.components]]
id = "auth"
name = "Authentication Service"
path = "services/auth"

[quality]
testing_style = "blackbox-frontdoor"
preflight = ["pytest -q", "flake8"]

[execution]
agent_command = "custom-agent -p '{prompt}'"
agent_max_attempts = 5
"""
    cfg_file = tmp_path / "specops.toml"
    cfg_file.write_text(toml_content.strip(), encoding="utf-8")

    cfg = load_config(config_path=cfg_file)
    assert cfg.project.name == "TestPlatform"
    assert cfg.architecture.file_length_limit == 400
    assert cfg.architecture.buffer_target == 8
    assert len(cfg.architecture.components) == 1
    assert cfg.architecture.components[0].id == "auth"
    assert cfg.quality.preflight == ["pytest -q", "flake8"]
    assert cfg.execution.agent_command == "custom-agent -p '{prompt}'"
    assert cfg.execution.agent_max_attempts == 5
