"""Unit tests for review radar AST auditor and boundary enforcement.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0106, US-0115.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.core.review_radar import (
    audit_worktree,
    check_adr0007_violations,
    determine_context,
    determine_context_from_import,
    diff_module_interfaces,
    extract_cli_options,
    extract_imports,
    partition_ast_symbols,
    run_review_radar,
)


def test_partition_ast_symbols_without_all():
    code = (
        "def public_func(a: int, b: int = 1) -> int:\n"
        "    return a + b\n\n"
        "def _private_func():\n"
        "    pass\n\n"
        "class PublicService:\n"
        "    def run(self): pass\n"
        "    def _secret(self): pass\n\n"
        "class _PrivateService:\n"
        "    pass\n"
    )
    pub, priv = partition_ast_symbols(code)
    assert "public_func" in pub
    assert pub["public_func"].required_params == ["a"]
    assert pub["public_func"].params == ["a", "b"]
    assert "PublicService" in pub
    assert "run" in pub["PublicService"].methods

    assert "_private_func" in priv
    assert "_PrivateService" in priv
    assert set(pub.keys()).isdisjoint(set(priv.keys()))


def test_partition_ast_symbols_with_explicit_all():
    code = (
        "__all__ = ['exported_func']\n\n"
        "def exported_func(): pass\n"
        "def other_func(): pass\n"
    )
    pub, priv = partition_ast_symbols(code)
    assert "exported_func" in pub
    assert "other_func" in priv
    assert "other_func" not in pub


def test_extract_cli_options():
    code = (
        "parser.add_argument('--json', action='store_true')\n"
        "parser.add_argument('-b', '--bc', help='context')\n"
        "parser.add_argument('positional')\n"
    )
    opts = extract_cli_options(code)
    assert "--json" in opts
    assert "--bc" in opts
    assert "-b" in opts
    assert "positional" not in opts


def test_diff_module_interfaces_breaking_changes():
    old = (
        "def compute(x: int, y: int) -> int:\n"
        "    return x + y\n\n"
        "class Service:\n"
        "    def execute(self): pass\n"
    )
    # Removing parameter 'y' and removing method 'execute'
    new = (
        "def compute(x: int) -> int:\n"
        "    return x\n\n"
        "class Service:\n"
        "    def perform(self): pass\n"
    )
    diffs = diff_module_interfaces(old, new)
    breaking = [d for d in diffs if d.change_type == "breaking"]
    assert any("Parameter 'y' removed" in d.details for d in breaking)
    assert any("Public method 'execute' removed" in d.details for d in breaking)


def test_diff_module_interfaces_required_param_added():
    old = "def fetch(url: str): pass\n"
    new = "def fetch(url: str, timeout: int): pass\n"
    diffs = diff_module_interfaces(old, new)
    breaking = [d for d in diffs if d.change_type == "breaking"]
    assert len(breaking) == 1
    assert "New required parameter 'timeout' added" in breaking[0].details


def test_diff_module_interfaces_non_breaking_and_internal():
    old = "def fetch(url: str): pass\n"
    new = (
        "def _helper(): pass\n\n"
        "def fetch(url: str, timeout: int = 5): pass\n\n"
        "def new_public(): pass\n"
    )
    diffs = diff_module_interfaces(old, new)
    breaking = [d for d in diffs if d.change_type == "breaking"]
    non_breaking = [d for d in diffs if d.change_type == "non_breaking"]
    internal = [d for d in diffs if d.change_type == "internal"]

    assert len(breaking) == 0
    assert any(d.symbol_name == "new_public" for d in non_breaking)
    assert any(d.symbol_name == "_helper" for d in internal)


def test_check_adr0007_pure_domain_cannot_import_infrastructure():
    code = "import infrastructure\n\ndef model(): pass\n"
    violations = check_adr0007_violations("src/domain/model.py", code)
    assert len(violations) >= 1
    assert "ADR-0007" in violations[0]
    assert "cannot import external infrastructure 'infrastructure'" in violations[0]


def test_check_adr0007_core_cannot_import_worker():
    code = "from spec_ops.worker.runners import run_agent\n"
    violations = check_adr0007_violations("src/spec_ops/core/service.py", code)
    assert len(violations) >= 1
    assert "ADR-0007" in violations[0]
    assert "cannot import infrastructure module 'spec_ops.worker.runners'" in violations[0]


def test_check_adr0007_compliant_clean():
    code = "from spec_ops.core.models import Task\n"
    violations = check_adr0007_violations("src/spec_ops/worker/handler.py", code)
    assert len(violations) == 0


def test_determine_context():
    assert determine_context("src/spec_ops/core/models.py") == "core"
    assert determine_context("src/spec_ops/worker/orchestrator.py") == "worker"
    assert determine_context("src/spec_ops/rescue/memory.py") == "rescue"
    assert determine_context("domain/service.py") == "core"
    assert determine_context("infrastructure/db.py") == "worker"


def test_determine_context_from_import():
    assert determine_context_from_import("spec_ops.core.models") == "core"
    assert determine_context_from_import("spec_ops.worker.runners") == "worker"
    assert determine_context_from_import("infrastructure") == "worker"
    assert determine_context_from_import("unknown_pkg") is None


def test_run_review_radar_clean_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    exit_code = run_review_radar(root_dir=tmp_path, json_output=True)
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert "summary" in data
    assert data["summary"]["clean"] is True
    assert data["summary"]["total_violations"] == 0
