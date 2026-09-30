"""Executable BDD acceptance tests for US-0013: Bounded Context Boundary and Dependency Direction Enforcement."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0013_bounded_context_enforcement.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "ddd_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(repo, name="DDDDemoApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "result": None}


# Scenario 1: Clean repository verifying bounded context isolation
@given('"specops.toml" defines bounded contexts "billing" and "orders"')
def given_specops_toml_defines_bc(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    toml_path = repo / "specops.toml"
    current = toml_path.read_text(encoding="utf-8")
    bc_config = """
[architecture.bounded_contexts.billing]
path = "src/billing"

[architecture.bounded_contexts.orders]
path = "src/orders"
"""
    toml_path.write_text(current.rstrip() + "\n" + bc_config, encoding="utf-8")


@given('specifies that "orders.domain" cannot import from "orders.infrastructure" or "billing.*"')
def given_specifies_boundary_rules(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    toml_path = repo / "specops.toml"
    current = toml_path.read_text(encoding="utf-8")
    rules = """
[architecture.boundary_rules]
"orders.domain" = ["orders.infrastructure", "billing.*"]
"""
    toml_path.write_text(current.rstrip() + "\n" + rules, encoding="utf-8")


@given("all source imports strictly honor these dependency directions")
def given_source_imports_honor(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    (repo / "src" / "orders" / "domain").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "orders" / "domain" / "order_aggregate.py").write_text(
        "class OrderAggregate:\n    def __init__(self, id: str):\n        self.id = id\n",
        encoding="utf-8",
    )
    (repo / "src" / "billing" / "infrastructure").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "billing" / "infrastructure" / "stripe_client.py").write_text(
        "class StripeClient:\n    pass\n",
        encoding="utf-8",
    )


@when('the architect runs "spec-ops health --architecture"')
def when_run_health_architecture(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    result = run_spec_ops(repo, ["health", "--architecture"])
    repo_context["result"] = result


@then("the command exits with code 0")
def then_command_exits_0(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    assert res.returncode == 0, f"Expected 0 but got {res.returncode}. Output: {res.stdout}\n{res.stderr}"


@then('reports "Invariant Met: Bounded context boundary rules validated with 0 violations"')
@then('And reports "Invariant Met: Bounded context boundary rules validated with 0 violations"')
def then_reports_invariant_met(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "Invariant Met: Bounded context boundary rules validated with 0 violations" in out


# Scenario 2: Catching illegal cross-context domain import in CI
@given('an autonomous agent introduces an import "from billing.infrastructure import StripeClient" into "src/orders/domain/order_aggregate.py"')
def given_agent_introduces_illegal_import(repo_context: dict[str, Any]):
    given_specops_toml_defines_bc(repo_context)
    given_specifies_boundary_rules(repo_context)
    repo = repo_context["repo"]
    order_agg = repo / "src" / "orders" / "domain" / "order_aggregate.py"
    order_agg.parent.mkdir(parents=True, exist_ok=True)
    order_agg.write_text(
        "from billing.infrastructure import StripeClient\n\nclass OrderAggregate:\n    pass\n",
        encoding="utf-8",
    )


@when('the preflight command runs "spec-ops health --architecture"')
def when_preflight_runs_architecture(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    result = run_spec_ops(repo, ["health", "--architecture"])
    repo_context["result"] = result


@then("the command exits with code 1")
def then_command_exits_1(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    assert res.returncode == 1, f"Expected 1 but got {res.returncode}. Output: {res.stdout}\n{res.stderr}"


@then('identifies the violating file "src/orders/domain/order_aggregate.py"')
@then('And identifies the violating file "src/orders/domain/order_aggregate.py"')
def then_identifies_violating_file(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "src/orders/domain/order_aggregate.py" in out


@then('reports "Architecture Invariant Violated: Domain layer cannot import external infrastructure \'billing.infrastructure\'"')
@then('And reports "Architecture Invariant Violated: Domain layer cannot import external infrastructure \'billing.infrastructure\'"')
def then_reports_domain_leak(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "Architecture Invariant Violated: Domain layer cannot import external infrastructure 'billing.infrastructure'" in out


# Scenario 3: Detecting circular bounded context dependencies
@given('module "src/auth/service.py" imports "src/users/manager.py"')
def given_auth_imports_users(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    (repo / "src" / "auth").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "auth" / "service.py").write_text(
        "import users.manager\n\ndef auth_service():\n    pass\n",
        encoding="utf-8",
    )


@given('module "src/users/manager.py" imports "src/auth/token.py"')
def given_users_imports_auth(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    (repo / "src" / "users").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "auth" / "token.py").write_text("TOKEN = 'xyz'\n", encoding="utf-8")
    (repo / "src" / "users" / "manager.py").write_text(
        "from auth import token\n\ndef manage_users():\n    pass\n",
        encoding="utf-8",
    )


@then('reports "Cyclic Architecture Dependency Detected: auth <-> users"')
@then('And reports "Cyclic Architecture Dependency Detected: auth <-> users"')
def then_reports_cyclic_dep(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "Cyclic Architecture Dependency Detected: auth <-> users" in out or "Cyclic Architecture Dependency Detected: users <-> auth" in out
