"""Automated pre-commit git hook installer and supply-chain sentinel (ADR-0002, ADR-0018, ADR-0019)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.loader import load_config
from ..config.models import SpecOpsConfig

HOOK_START_MARKER: str = "# >>> SpecOps Pre-Commit Hook Sentinel >>>"
HOOK_END_MARKER: str = "# <<< SpecOps Pre-Commit Hook Sentinel <<<"
NO_TRAILING_NL_TAG: str = "# [spec-ops: no-trailing-newline]"


@dataclass
class HookSentinelResult:
    """Outcome of real-time pre-commit sentinel inspection on staged changes."""

    ok: bool
    violations: list[str] = field(default_factory=list)
    lockfile_ok: bool = True
    secrets_ok: bool = True
    file_lengths_ok: bool = True
    staged_files_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serializes sentinel evaluation to dictionary for JSON output."""
        return {
            "ok": self.ok,
            "violations": list(self.violations),
            "lockfile_ok": self.lockfile_ok,
            "secrets_ok": self.secrets_ok,
            "file_lengths_ok": self.file_lengths_ok,
            "staged_files_count": self.staged_files_count,
        }


def generate_hook_payload(python_executable: str | None = None) -> str:
    """Renders the standard SpecOps pre-commit hook payload with sentinel markers."""
    py_bin = python_executable or sys.executable
    lines = [
        HOOK_START_MARKER,
        "# SpecOps Pre-Commit Hook Sentinel: invokes security and lockfile verification checks (ADR-0002, ADR-0018, ADR-0019)",
        'if [ -n "$SPEC_OPS_BIN" ] && [ -x "$SPEC_OPS_BIN" ]; then',
        '    "$SPEC_OPS_BIN" security hook run || exit 1',
        'elif [ -n "$SPEC_OPS_PYTHON" ] && [ -x "$SPEC_OPS_PYTHON" ]; then',
        '    "$SPEC_OPS_PYTHON" -m spec_ops.cli.main security hook run || exit 1',
        'elif [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/spec-ops" ]; then',
        '    "$VIRTUAL_ENV/bin/spec-ops" security hook run || exit 1',
        "elif command -v spec-ops >/dev/null 2>&1; then",
        "    spec-ops security hook run || exit 1",
        "elif command -v uv >/dev/null 2>&1; then",
        "    uv run spec-ops security hook run || exit 1",
        'elif [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then',
        '    "$VIRTUAL_ENV/bin/python" -m spec_ops.cli.main security hook run || exit 1',
    ]
    if py_bin:
        lines.extend([
            f'elif [ -x "{py_bin}" ]; then',
            f'    "{py_bin}" -m spec_ops.cli.main security hook run || exit 1',
        ])
    lines.extend([
        "elif command -v python3 >/dev/null 2>&1; then",
        "    python3 -m spec_ops.cli.main security hook run || exit 1",
        "elif command -v python >/dev/null 2>&1; then",
        "    python -m spec_ops.cli.main security hook run || exit 1",
        "fi",
        HOOK_END_MARKER,
        "",
    ])
    return "\n".join(lines)


def strip_sentinel_block(content: str) -> str | None:
    """Strips the SpecOps sentinel block from hook script content.

    Returns None if the remaining content is empty or contains only a standard shebang.
    """
    if HOOK_START_MARKER not in content:
        return content

    end_marker = f"{HOOK_END_MARKER}\n"

    # Check if no-trailing-newline tag is present
    no_nl_start = f"\n{NO_TRAILING_NL_TAG}\n{HOOK_START_MARKER}\n"
    start_idx = content.find(no_nl_start)
    if start_idx != -1:
        end_idx = content.find(end_marker, start_idx)
        if end_idx != -1:
            end_idx += len(end_marker)
            remaining = content[:start_idx] + content[end_idx:]
            stripped = remaining.strip()
            if not stripped or stripped in ("#!/bin/sh", "#!/bin/bash"):
                return None
            return remaining

    # Standard case (with trailing newline preserved)
    start_marker = f"\n{HOOK_START_MARKER}\n"
    start_idx = content.find(start_marker)
    if start_idx != -1:
        end_idx = content.find(end_marker, start_idx)
        if end_idx != -1:
            end_idx += len(end_marker)
            remaining = content[:start_idx] + content[end_idx:]
            stripped = remaining.strip()
            if not stripped or stripped in ("#!/bin/sh", "#!/bin/bash"):
                return None
            return remaining

    start_idx = content.find(HOOK_START_MARKER)
    if start_idx != -1:
        end_idx = content.find(end_marker, start_idx)
        if end_idx != -1:
            end_idx += len(end_marker)
            remaining = content[:start_idx] + content[end_idx:]
            stripped = remaining.strip()
            if not stripped or stripped in ("#!/bin/sh", "#!/bin/bash"):
                return None
            return remaining

    return content


def inject_sentinel_block(existing_content: str | None, python_executable: str | None = None) -> str:
    """Injects or replaces the SpecOps sentinel block, preserving custom commands."""
    payload = generate_hook_payload(python_executable=python_executable)
    if not existing_content or not existing_content.strip():
        return f"#!/bin/sh\n\n{payload}"

    clean_existing = strip_sentinel_block(existing_content)
    if not clean_existing or not clean_existing.strip():
        return f"#!/bin/sh\n\n{payload}"

    if clean_existing.endswith("\n"):
        return f"{clean_existing}\n{payload}"
    return f"{clean_existing}\n{NO_TRAILING_NL_TAG}\n{payload}"


def resolve_hooks_dir(repo_dir: Path | str) -> Path:
    """Resolves target .git/hooks directory for main repository or worktree."""
    root = Path(repo_dir).resolve()
    git_entry = root / ".git"

    if git_entry.exists():
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--git-path", "hooks"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            if res.returncode == 0 and res.stdout.strip():
                p = Path(res.stdout.strip())
                return p if p.is_absolute() else (root / p).resolve()
        except OSError:
            pass

    return root / ".git" / "hooks"


def install_hook(
    repo_dir: Path | str,
    force: bool = False,
    python_executable: str | None = None,
) -> tuple[bool, Path, str]:
    """Installs or updates the pre-commit hook sentinel in .git/hooks/pre-commit."""
    hooks_dir = resolve_hooks_dir(repo_dir)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "pre-commit"

    existing_content: str | None = None
    if hook_file.is_file():
        existing_content = hook_file.read_text(encoding="utf-8", errors="replace")
        if not force and HOOK_START_MARKER in existing_content:
            pass  # Already installed, but updating payload is safe and idempotent

    new_content = inject_sentinel_block(existing_content, python_executable=python_executable)
    hook_file.write_text(new_content, encoding="utf-8")
    hook_file.chmod(0o755)

    return True, hook_file, f"Installed pre-commit hook sentinel into {hook_file}"


def uninstall_hook(repo_dir: Path | str) -> tuple[bool, Path, str]:
    """Uninstalls the pre-commit hook sentinel from .git/hooks/pre-commit."""
    hooks_dir = resolve_hooks_dir(repo_dir)
    hook_file = hooks_dir / "pre-commit"

    if not hook_file.is_file():
        return False, hook_file, f"Pre-commit hook not found at {hook_file}"

    content = hook_file.read_text(encoding="utf-8", errors="replace")
    if HOOK_START_MARKER not in content:
        return False, hook_file, f"Pre-commit hook at {hook_file} does not contain SpecOps sentinel"

    remaining = strip_sentinel_block(content)
    if remaining is None:
        hook_file.unlink()
        return True, hook_file, f"Removed pre-commit hook file at {hook_file}"

    hook_file.write_text(remaining, encoding="utf-8")
    hook_file.chmod(0o755)
    return True, hook_file, f"Removed SpecOps sentinel block from {hook_file}"


def verify_hook(repo_dir: Path | str) -> tuple[bool, str]:
    """Verifies that the pre-commit hook exists, is executable, and has SpecOps sentinel."""
    hooks_dir = resolve_hooks_dir(repo_dir)
    hook_file = hooks_dir / "pre-commit"

    if not hook_file.is_file():
        return False, f"Pre-commit hook not found at {hook_file}"

    if not os.access(hook_file, os.X_OK):
        return False, f"Pre-commit hook at {hook_file} is not executable"

    content = hook_file.read_text(encoding="utf-8", errors="replace")
    if HOOK_START_MARKER not in content:
        return False, f"Pre-commit hook at {hook_file} is missing SpecOps sentinel marker"

    return True, f"Pre-commit hook verified and active at {hook_file}"


def get_staged_files(repo_dir: Path) -> list[str]:
    """Retrieves list of relative file paths currently staged in git index."""
    res = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        return [line.strip().strip('"') for line in res.stdout.splitlines() if line.strip()]

    st_res = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    staged: list[str] = []
    if st_res.returncode == 0:
        for line in st_res.stdout.splitlines():
            if len(line) > 3:
                index_col = line[0]
                if index_col not in (" ", "?"):
                    path_part = line[3:].strip().strip('"')
                    if " -> " in path_part:
                        path_part = path_part.split(" -> ")[1].strip().strip('"')
                    staged.append(path_part)
    return staged


def run_hook_sentinel(
    repo_dir: Path | str,
    config: SpecOpsConfig | None = None,
) -> HookSentinelResult:
    """Executes real-time pre-commit sentinel checks on staged changes."""
    root = Path(repo_dir).resolve()
    cfg = config or load_config(root_dir=root)
    staged_files = get_staged_files(root)

    if not staged_files:
        return HookSentinelResult(ok=True, staged_files_count=0)

    violations: list[str] = []
    lockfile_ok = True
    secrets_ok = True
    file_lengths_ok = True

    # 1. Lockfile Immutability Sentinel (ADR-0018)
    from .lockfile_sentinel import inspect_lockfile_sentinel, is_protected_lockfile

    staged_lockfiles = [f for f in staged_files if is_protected_lockfile(f)]
    if staged_lockfiles:
        lock_res = inspect_lockfile_sentinel(root, config=cfg, changed_files=staged_lockfiles)
        if not lock_res.ok:
            lockfile_ok = False
            violations.extend(lock_res.violations)

    # 2. Secret Scanning Sentinel (ADR-0019)
    from .secrets.scanner import scan_worktree

    sec_report = scan_worktree(root, staged_only=True)
    if not sec_report.is_clean:
        secrets_ok = False
        for sv in sec_report.secret_violations:
            violations.append(
                f"Secret Leak Violation (ADR-0019): {sv.secret_type} in {sv.file_path}:{sv.line_number} ({sv.masked_token})"
            )
        for dv in sec_report.dotfile_violations:
            violations.append(
                f"Dotfile Violation (ADR-0019): {dv.file_path} - {dv.action_instructions}"
            )

    # 3. File Length Invariant Sentinel (<500 lines per ADR-0002)
    from ..core.debt_baseline import (
        EXCLUDE_DIRS,
        SOURCE_EXTENSIONS,
        evaluate_file_debt,
        load_grandfathered_debt,
    )

    limit = cfg.architecture.file_length_limit if cfg and cfg.architecture else 500
    baseline = load_grandfathered_debt(root)

    for rel_path_str in staged_files:
        p = Path(rel_path_str)
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix not in SOURCE_EXTENSIONS:
            continue

        content: str | None = None
        show_res = subprocess.run(
            ["git", "show", f":{rel_path_str}"],
            cwd=root,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if show_res.returncode == 0:
            content = show_res.stdout
        else:
            disk_file = root / rel_path_str
            if disk_file.is_file():
                content = disk_file.read_text(encoding="utf-8", errors="replace")

        if content is None:
            continue

        line_count = len(content.splitlines())
        debt_eval = evaluate_file_debt(rel_path_str, line_count, baseline, limit)
        if debt_eval.is_violation:
            file_lengths_ok = False
            violations.append(
                f"File Length Violation (ADR-0002): Staged file '{rel_path_str}' ({line_count} lines) "
                f"exceeds limit ({debt_eval.baseline_lines or limit} lines)."
            )

    ok = lockfile_ok and secrets_ok and file_lengths_ok
    return HookSentinelResult(
        ok=ok,
        violations=violations,
        lockfile_ok=lockfile_ok,
        secrets_ok=secrets_ok,
        file_lengths_ok=file_lengths_ok,
        staged_files_count=len(staged_files),
    )
