"""Developer environment diagnostic and automated onboarding repair tool."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..backlog.health import HealthChecker
from ..config.loader import load_config
from ..config.models import SpecOpsConfig
from ..worker.hooks import install_pre_commit_hook


@dataclass
class DoctorCheckResult:
    """Diagnostic outcome for an individual developer tooling check."""

    component: str
    check: str
    status: str  # "PASS" or "FAIL"
    message: str = ""
    fixable: bool = False


@dataclass
class DoctorReport:
    """Comprehensive environment diagnostic audit report."""

    results: list[DoctorCheckResult] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return all(r.status == "PASS" for r in self.results)

    @property
    def issues_count(self) -> int:
        return sum(1 for r in self.results if r.status == "FAIL")


class DeveloperEnvironmentDoctor:
    """Audits local developer tooling and workspace health with automated repair."""

    def __init__(self, root_dir: Path | None = None, config: SpecOpsConfig | None = None):
        self.root_dir = (Path(root_dir) if root_dir else Path.cwd()).resolve()
        self.config = config or load_config(root_dir=self.root_dir)

    def _resolve_hooks_dir(self) -> Path:
        """Determines the active git hooks directory."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--git-path", "hooks"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            p = Path(res.stdout.strip())
            return p if p.is_absolute() else (self.root_dir / p).resolve()
        except Exception:
            return (self.root_dir / ".git" / "hooks").resolve()

    def check_uv(self) -> DoctorCheckResult:
        """Audits UV package manager availability and lockfile synchronization."""
        comp = "UV Package Manager"
        chk = "UV installed and lockfile synchronized (uv lock --check)"
        if not shutil.which("uv"):
            return DoctorCheckResult(comp, chk, "FAIL", "UV is not installed or not in PATH.", fixable=False)
        if not (self.root_dir / "pyproject.toml").is_file():
            return DoctorCheckResult(comp, chk, "FAIL", "pyproject.toml not found in repository root.", fixable=False)
        try:
            res = subprocess.run(
                ["uv", "lock", "--check"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                return DoctorCheckResult(comp, chk, "PASS", "UV is installed and lockfile is synchronized.")
            return DoctorCheckResult(comp, chk, "FAIL", "uv lock --check failed (lockfile out of sync).", fixable=True)
        except Exception as e:
            return DoctorCheckResult(comp, chk, "FAIL", f"Failed to execute uv lock --check: {e}", fixable=False)

    def check_git_worktrees(self) -> DoctorCheckResult:
        """Audits .gitignore configuration for isolated worker worktrees."""
        comp = "Git Worktree Setup"
        chk = ".worktrees/ directory configured in .gitignore"
        gi = self.root_dir / ".gitignore"
        if not gi.is_file():
            return DoctorCheckResult(comp, chk, "FAIL", ".gitignore does not exist.", fixable=True)
        lines = [line.strip() for line in gi.read_text(encoding="utf-8").splitlines()]
        configured = any(
            line in (".worktrees", ".worktrees/", ".worktrees/*", "/.worktrees", "/.worktrees/")
            for line in lines
        )
        if configured:
            return DoctorCheckResult(comp, chk, "PASS", ".worktrees/ is configured in .gitignore.")
        return DoctorCheckResult(comp, chk, "FAIL", ".worktrees/ is not configured in .gitignore.", fixable=True)

    def check_pre_commit_hooks(self) -> DoctorCheckResult:
        """Audits active git pre-commit hook enforcing SpecOps health checks."""
        comp = "Pre-Commit Hooks"
        chk = "Git pre-commit hook active with spec-ops health check"
        hooks_dir = self._resolve_hooks_dir()
        hook_file = hooks_dir / "pre-commit"
        fallback = self.root_dir / ".git" / "hooks" / "pre-commit"
        target = hook_file if hook_file.is_file() else fallback

        if not target.is_file():
            return DoctorCheckResult(comp, chk, "FAIL", "pre-commit hook file does not exist.", fixable=True)
        if not os.access(target, os.X_OK):
            return DoctorCheckResult(comp, chk, "FAIL", "pre-commit hook is not executable.", fixable=True)
        try:
            content = target.read_text(encoding="utf-8")
            if "spec-ops health" in content:
                return DoctorCheckResult(comp, chk, "PASS", "Git pre-commit hook active with spec-ops health check.")
            return DoctorCheckResult(comp, chk, "FAIL", "pre-commit hook does not invoke spec-ops health.", fixable=True)
        except Exception as e:
            return DoctorCheckResult(comp, chk, "FAIL", f"Could not read pre-commit hook: {e}", fixable=True)

    def check_line_limits(self) -> DoctorCheckResult:
        """Audits repository source files against configured file length limits."""
        comp = "Line Limit Health"
        chk = "Zero source files exceed configured limit (<500 lines)"
        try:
            checker = HealthChecker(self.config)
            rep = checker.run_check()
            if not rep.violations:
                return DoctorCheckResult(comp, chk, "PASS", "Zero source files exceed configured limit (<500 lines).")
            return DoctorCheckResult(
                comp, chk, "FAIL", f"{len(rep.violations)} source file(s) violate length limits.", fixable=False
            )
        except Exception as e:
            return DoctorCheckResult(comp, chk, "FAIL", f"Health check failed: {e}", fixable=False)

    def check_debt_baseline_gitignore(self) -> DoctorCheckResult:
        """Audits .gitignore configuration to ensure grandfathered debt baseline is not suppressed."""
        comp = "Technical Debt Baseline"
        chk = "Debt baseline not suppressed by .gitignore"
        gi = self.root_dir / ".gitignore"
        if not gi.is_file():
            return DoctorCheckResult(comp, chk, "PASS", ".gitignore does not exist.")
        content = gi.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines()]
        blanket = any(line in (".specops", ".specops/", "/.specops", "/.specops/") for line in lines)
        if blanket:
            return DoctorCheckResult(
                comp,
                chk,
                "FAIL",
                "Blanket .specops/ in .gitignore suppresses .specops/grandfathered_debt.json.",
                fixable=True,
            )
        return DoctorCheckResult(comp, chk, "PASS", "Debt baseline is not suppressed by .gitignore.")

    def audit(self) -> DoctorReport:
        """Runs all developer workspace diagnostic checks."""
        return DoctorReport(
            results=[
                self.check_uv(),
                self.check_git_worktrees(),
                self.check_debt_baseline_gitignore(),
                self.check_pre_commit_hooks(),
                self.check_line_limits(),
            ]
        )

    def fix(self) -> list[str]:
        """Automatically repairs missing workspace configuration and hooks."""
        repairs: list[str] = []

        # 1. Repair gitignore
        if self.check_git_worktrees().status == "FAIL":
            gi = self.root_dir / ".gitignore"
            if gi.is_file():
                content = gi.read_text(encoding="utf-8")
                if content and not content.endswith("\n"):
                    content += "\n"
                content += ".worktrees/\n"
                gi.write_text(content, encoding="utf-8")
            else:
                gi.write_text(".worktrees/\n", encoding="utf-8")
            (self.root_dir / ".worktrees").mkdir(parents=True, exist_ok=True)
            repairs.append("Configured .worktrees/ in .gitignore")

        # 1b. Repair debt baseline suppression in gitignore
        if self.check_debt_baseline_gitignore().status == "FAIL":
            from ..core.debt_baseline import ensure_debt_baseline_unignored

            if ensure_debt_baseline_unignored(self.root_dir):
                repairs.append("Unignored .specops/grandfathered_debt.json in .gitignore")


        # 2. Repair pre-commit hook
        if self.check_pre_commit_hooks().status == "FAIL":
            install_pre_commit_hook(self.root_dir)
            active_hooks = self._resolve_hooks_dir()
            if active_hooks != (self.root_dir / ".git" / "hooks"):
                active_hooks.mkdir(parents=True, exist_ok=True)
                target_hook = active_hooks / "pre-commit"
                hook_content = (
                    "#!/usr/bin/env bash\n"
                    "# SpecOps spec-ops-health pre-commit hook\n"
                    "exec uv run spec-ops health\n"
                )
                target_hook.write_text(hook_content, encoding="utf-8")
                target_hook.chmod(0o755)
            repairs.append("Installed git pre-commit hook")

        # 3. Repair UV lockfile if fixable and needed
        uv_status = self.check_uv()
        if uv_status.status == "FAIL" and uv_status.fixable:
            try:
                res = subprocess.run(["uv", "lock"], cwd=self.root_dir, capture_output=True, text=True)
                if res.returncode == 0:
                    repairs.append("Synchronized uv.lock via uv lock")
            except Exception:
                pass

        return repairs


def handle_doctor_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """CLI dispatcher for spec-ops doctor [--fix]."""
    doctor = DeveloperEnvironmentDoctor(config.root_dir, config)

    if getattr(args, "fix", False):
        repairs = doctor.fix()
        if repairs:
            for r in repairs:
                print(f"🔧 Repaired: {r}")

    report = doctor.audit()

    if getattr(args, "json", False):
        payload = {
            "is_healthy": report.is_healthy,
            "issues_count": report.issues_count,
            "checks": [
                {
                    "component": r.component,
                    "check": r.check,
                    "status": r.status,
                    "message": r.message,
                }
                for r in report.results
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0 if report.is_healthy else 1

    console = Console()
    table = Table(title="SpecOps Developer Workspace Doctor", expand=True)
    table.add_column("Component", style="bold cyan")
    table.add_column("Check", style="white")
    table.add_column("Status", style="bold")
    for r in report.results:
        st_style = "bold green" if r.status == "PASS" else "bold red"
        table.add_row(r.component, r.check, f"[{st_style}]{r.status}[/{st_style}]")

    console.print(table)

    if report.is_healthy:
        print("\nDevelopment environment is healthy and ready for active engineering.")
        return 0

    cnt = report.issues_count
    issue_str = f"{cnt} issue{'s' if cnt != 1 else ''} require{'s' if cnt == 1 else ''} resolution"
    print(f"\n❌ {issue_str}.")
    print("👉 Run 'spec-ops doctor --fix' to automatically repair workspace issues.")
    return 1
