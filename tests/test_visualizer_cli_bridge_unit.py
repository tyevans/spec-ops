"""Unit tests for src/spec_ops/visualizer/cli_bridge.py to maximize mutant kill rate under mutmut."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

from spec_ops.config.loader import load_config
from spec_ops.visualizer.cli_bridge import (
    generate_entity_deep_link,
    handle_visualizer_command,
    normalize_entity_id,
)


def test_normalize_entity_id():
    assert normalize_entity_id(None) is None
    assert normalize_entity_id("") is None
    assert normalize_entity_id("   ") is None
    assert normalize_entity_id("0009") == "TASK-0009"
    assert normalize_entity_id("42") == "TASK-0042"
    assert normalize_entity_id("task-0009") == "TASK-0009"
    assert normalize_entity_id("TASK-0009") == "TASK-0009"
    assert normalize_entity_id("prd-0001") == "PRD-0001"
    assert normalize_entity_id("ADR-0003") == "ADR-0003"
    assert normalize_entity_id("core") == "CORE"


def test_generate_entity_deep_link():
    # Base url tests without entity
    assert generate_entity_deep_link(None) == "http://127.0.0.1:8787/"
    assert generate_entity_deep_link("") == "http://127.0.0.1:8787/"
    assert generate_entity_deep_link(None, host="localhost", port=9000) == "http://localhost:9000/"
    assert generate_entity_deep_link(None, tab="kanban") == "http://127.0.0.1:8787/#tab=kanban"

    # Default graph tab
    assert generate_entity_deep_link("TASK-0009") == "http://127.0.0.1:8787/#entity=TASK-0009"
    assert generate_entity_deep_link("0009") == "http://127.0.0.1:8787/#entity=TASK-0009"
    assert generate_entity_deep_link("task-0009", host="0.0.0.0", port=8080) == "http://0.0.0.0:8080/#entity=TASK-0009"
    assert generate_entity_deep_link("TASK-0009", tab="graph") == "http://127.0.0.1:8787/#entity=TASK-0009"

    # Non-graph tab
    assert generate_entity_deep_link("TASK-0009", tab="kanban") == "http://127.0.0.1:8787/#tab=kanban&entity=TASK-0009"
    assert generate_entity_deep_link("ADR-0002", tab="adrs") == "http://127.0.0.1:8787/#tab=adrs&entity=ADR-0002"


def test_handle_visualizer_command_export(tmp_path: Path):
    config = load_config(root_dir=Path.cwd())
    args = argparse.Namespace(
        viz_action="export",
        out_pos=str(tmp_path / "custom.html"),
        output="dist/index.html",
        build=None,
    )
    with patch("spec_ops.visualizer.bundle.export_bundle", return_value=tmp_path / "custom.html") as mock_exp:
        code = handle_visualizer_command(args, config)
        assert code == 0
        mock_exp.assert_called_once()


def test_handle_visualizer_command_build(tmp_path: Path):
    config = load_config(root_dir=Path.cwd())
    args = argparse.Namespace(
        viz_action=None,
        build=str(tmp_path / "built.html"),
    )
    with patch("spec_ops.visualizer.bundle.export_bundle", return_value=tmp_path / "built.html") as mock_exp:
        code = handle_visualizer_command(args, config)
        assert code == 0
        mock_exp.assert_called_once()


def test_handle_visualizer_command_serve_with_entity():
    config = load_config(root_dir=Path.cwd())
    args = argparse.Namespace(
        viz_action=None,
        build=None,
        port=8787,
        host="127.0.0.1",
        entity="TASK-0009",
    )
    with patch("spec_ops.visualizer.server.serve_visualizer") as mock_serve, \
         patch("threading.Thread") as mock_thread:
        code = handle_visualizer_command(args, config)
        assert code == 0
        mock_serve.assert_called_once_with(config, host="127.0.0.1", port=8787)
        mock_thread.assert_called_once()
