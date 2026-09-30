"""Unit tests for arch_checker.py to maximize mutant kill rate under mutmut."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec_ops.core.arch_checker import (
    ArchitectureChecker,
    ArchitectureReport,
    ArchitectureViolation,
    get_module_for_file,
    matches_rule,
    parse_python_imports,
    parse_ts_imports,
)


def test_parse_python_imports_basic_and_from():
    code = """
import os
import sys, math
from pathlib import Path
from typing import Any, List
"""
    imports = parse_python_imports(code, file_module="app.core")
    assert "os" in imports
    assert "sys" in imports
    assert "math" in imports
    assert "pathlib" in imports
    assert "typing" in imports


def test_parse_python_imports_relative():
    code = """
from .models import Item
from ..service import Service
from ...root import Root
"""
    imports = parse_python_imports(code, file_module="app.orders.domain.models")
    assert "app.orders.domain.models.models" not in imports
    # level 1 from app.orders.domain.models: base parts are app.orders.domain -> app.orders.domain.models
    assert "app.orders.domain.models" in imports
    # level 2: base parts app.orders -> app.orders.service
    assert "app.orders.service" in imports
    # level 3: base parts app -> app.root
    assert "app.root" in imports


def test_parse_python_imports_syntax_error():
    code = "def invalid_syntax(:"
    imports = parse_python_imports(code, file_module="app")
    assert imports == []


def test_parse_ts_imports():
    code = """
import { Order } from "./order";
import StripeClient from "src/billing/infrastructure";
const helper = require('auth/jwt');
"""
    imports = parse_ts_imports(code, file_path="src/orders/service.ts")
    assert "order" in imports
    assert "billing.infrastructure" in imports
    assert "auth.jwt" in imports


def test_get_module_for_file():
    assert get_module_for_file("src/orders/domain/model.py") == "orders.domain.model"
    assert get_module_for_file("billing/service.py") == "billing.service"
    assert get_module_for_file("app.py") == "app"


def test_matches_rule():
    # Wildcard prefix
    assert matches_rule("billing", "billing.*") is True
    assert matches_rule("billing.infrastructure", "billing.*") is True
    assert matches_rule("billing_service", "billing.*") is False
    assert matches_rule("orders.billing", "billing.*") is False

    # Exact match
    assert matches_rule("orders.infrastructure", "orders.infrastructure") is True
    assert matches_rule("orders.domain", "orders.infrastructure") is False

    # Fnmatch glob
    assert matches_rule("src.orders.repo", "*.repo") is True
    assert matches_rule("src.orders.repo", "*.service") is False


def test_architecture_violation_formatting():
    v1 = ArchitectureViolation(
        file_path="src/orders/domain/order.py",
        imported_module="billing.infrastructure",
        rule_description="Domain purity",
        is_domain_leak=True,
    )
    msg1 = v1.format_message()
    assert "Architecture Invariant Violated: Domain layer cannot import external infrastructure 'billing.infrastructure'" in msg1
    assert "src/orders/domain/order.py" in msg1

    v2 = ArchitectureViolation(
        file_path="src/billing/service.py",
        imported_module="auth.secret",
        rule_description="Rule: billing cannot import auth",
        is_domain_leak=False,
    )
    msg2 = v2.format_message()
    assert "Forbidden import 'auth.secret'" in msg2
    assert "Rule: billing cannot import auth" in msg2


def test_architecture_report_clean():
    rep = ArchitectureReport(violations=[], cycles=[], contexts_scanned=["orders", "billing"])
    assert rep.is_valid is True
    out = rep.format_output()
    assert "Invariant Met: Bounded context boundary rules validated with 0 violations." in out


def test_architecture_report_violations_and_cycles():
    v = ArchitectureViolation(
        file_path="src/a.py",
        imported_module="b.infra",
        rule_description="Test",
        is_domain_leak=False,
    )
    rep = ArchitectureReport(violations=[v], cycles=["auth <-> users"], contexts_scanned=["auth", "users"])
    assert rep.is_valid is False
    out = rep.format_output()
    assert "Cyclic Architecture Dependency Detected: auth <-> users" in out
    assert "src/a.py" in out


def test_architecture_checker_full_discovery_and_rules(tmp_path: Path):
    src = tmp_path / "src"
    (src / "orders" / "domain").mkdir(parents=True, exist_ok=True)
    (src / "orders" / "infrastructure").mkdir(parents=True, exist_ok=True)
    (src / "billing" / "infrastructure").mkdir(parents=True, exist_ok=True)

    (src / "orders" / "domain" / "order.py").write_text(
        "from billing.infrastructure import StripeClient\n",
        encoding="utf-8",
    )
    (src / "orders" / "infrastructure" / "repo.py").write_text(
        "# clean repo\n",
        encoding="utf-8",
    )
    (src / "billing" / "infrastructure" / "client.py").write_text(
        "# clean client\n",
        encoding="utf-8",
    )

    toml_data = {
        "architecture": {
            "bounded_contexts": {
                "orders": {"forbidden_imports": ["billing.*"]},
                "billing": {},
            },
            "boundary_rules": {
                "orders.domain": ["orders.infrastructure", "billing.*"],
            },
        }
    }

    checker = ArchitectureChecker(tmp_path, toml_data=toml_data)
    assert "orders" in checker.bounded_contexts
    assert "billing" in checker.bounded_contexts
    assert len(checker.rules) >= 2

    report = checker.check()
    assert not report.is_valid
    assert len(report.violations) >= 1
    assert any(v.is_domain_leak for v in report.violations)


def test_architecture_checker_cyclic_detection(tmp_path: Path):
    src = tmp_path / "src"
    (src / "auth").mkdir(parents=True, exist_ok=True)
    (src / "users").mkdir(parents=True, exist_ok=True)

    (src / "auth" / "service.py").write_text("import users.manager\n", encoding="utf-8")
    (src / "users" / "manager.py").write_text("import auth.token\n", encoding="utf-8")

    checker = ArchitectureChecker(tmp_path, toml_data={})
    report = checker.check()
    assert not report.is_valid
    assert "auth <-> users" in report.cycles or "users <-> auth" in report.cycles
