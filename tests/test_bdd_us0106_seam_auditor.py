"""BDD tests for US-0106: Autonomous Bounded Context Seam Auditor and Cross-Context Coupling Heatmap."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.core.seam_auditor import SeamAuditor
from spec_ops.scaffold.init import init_project

scenarios("features/us_0106_seam_auditor.feature")


@pytest.fixture
def bdd_seam_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "seam_app"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="SeamApp", target_dir=repo)

    # Create bounded context structure under src/
    core_dir = repo / "src" / "core"
    vis_dir = repo / "src" / "visualizer"
    core_dir.mkdir(parents=True, exist_ok=True)
    vis_dir.mkdir(parents=True, exist_ok=True)

    (core_dir / "__init__.py").write_text("", encoding="utf-8")
    (core_dir / "service.py").write_text(
        "class CoreService:\n    pass\n",
        encoding="utf-8",
    )

    (vis_dir / "__init__.py").write_text("", encoding="utf-8")
    (vis_dir / "canvas.py").write_text(
        "from core.service import CoreService\nclass Canvas:\n    pass\n",
        encoding="utf-8",
    )

    return {
        "repo": repo,
        "exit_code": None,
        "stdout": "",
        "report": None,
    }


@given("a project repository with clean bounded context separation")
def clean_repository(bdd_seam_ctx: dict[str, Any]) -> None:
    # Contexts are cleanly separated: visualizer imports core, core does not import visualizer or private internals
    pass


@given("a core domain module directly importing private visualizer internals")
def core_importing_private_visualizer(bdd_seam_ctx: dict[str, Any]) -> None:
    repo = bdd_seam_ctx["repo"]
    vis_dir = repo / "src" / "visualizer"
    vis_dir.mkdir(parents=True, exist_ok=True)
    (vis_dir / "_internal.py").write_text("SECRET_VIS_INTERNAL = 42\n", encoding="utf-8")

    core_dir = repo / "src" / "core"
    (core_dir / "leaky_module.py").write_text(
        "from visualizer._internal import SECRET_VIS_INTERNAL\n",
        encoding="utf-8",
    )


@when("the architect runs spec-ops architecture seams")
def run_architecture_seams(bdd_seam_ctx: dict[str, Any]) -> None:
    repo = bdd_seam_ctx["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "architecture", "seams"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_seam_ctx["exit_code"] = res.returncode
    bdd_seam_ctx["stdout"] = res.stdout


@when("spec-ops architecture seams runs with strict mode")
def run_architecture_seams_strict(bdd_seam_ctx: dict[str, Any]) -> None:
    repo = bdd_seam_ctx["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "architecture", "seams", "--strict"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_seam_ctx["exit_code"] = res.returncode
    bdd_seam_ctx["stdout"] = res.stdout


@then("all cross-context imports are verified compliant")
def verify_compliant(bdd_seam_ctx: dict[str, Any]) -> None:
    repo = bdd_seam_ctx["repo"]
    auditor = SeamAuditor(repo)
    report = auditor.audit()
    assert report.is_valid
    assert len(report.violations) == 0
    assert "comply with Domain-Driven Design seams" in bdd_seam_ctx["stdout"]


@then("the illegal cross-context dependency is flagged")
def verify_flagged(bdd_seam_ctx: dict[str, Any]) -> None:
    repo = bdd_seam_ctx["repo"]
    auditor = SeamAuditor(repo)
    report = auditor.audit()
    assert not report.is_valid
    assert len(report.violations) > 0
    assert any("private visualizer internals" in v.reason for v in report.violations)


@then("the command terminates with exit code 0")
def exit_0(bdd_seam_ctx: dict[str, Any]) -> None:
    assert bdd_seam_ctx["exit_code"] == 0


@then("the command terminates with exit code 1")
def exit_1(bdd_seam_ctx: dict[str, Any]) -> None:
    assert bdd_seam_ctx["exit_code"] == 1
