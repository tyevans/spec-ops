"""Supply-chain lockfile mutation sentinel and pre-execution hook (ADR-0018, US-0028)."""

from __future__ import annotations

import datetime
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..config.models import SpecOpsConfig

PROTECTED_LOCKFILES: frozenset[str] = frozenset({
    "uv.lock",
    "package-lock.json",
    "poetry.lock",
    "Cargo.lock",
    "requirements.txt",
})


def is_protected_lockfile(path_or_name: str | Path) -> bool:
    """Returns True if the file or filename is a protected supply-chain lockfile."""
    name = Path(str(path_or_name).strip().strip('"')).name
    return name in PROTECTED_LOCKFILES


@dataclass
class LockfileSentinelResult:
    """Evaluation result from Lockfile Mutation Sentinel inspection."""

    ok: bool
    violations: list[str] = field(default_factory=list)
    modified_lockfiles: list[str] = field(default_factory=list)
    remediated: list[str] = field(default_factory=list)
    waiver_applied: bool = False
    waiver_details: str | None = None

    @property
    def valid(self) -> bool:
        """Alias for ok to preserve consistency across validation gates."""
        return self.ok

    def to_dict(self) -> dict[str, Any]:
        """Serializes result to structured dictionary for JSON reporting."""
        return {
            "ok": self.ok,
            "valid": self.valid,
            "violations": list(self.violations),
            "modified_lockfiles": list(self.modified_lockfiles),
            "remediated": list(self.remediated),
            "waiver_applied": self.waiver_applied,
            "waiver_details": self.waiver_details,
        }


def detect_lockfile_mutations(
    repo_dir: Path | str,
    base_ref: str | None = None,
    changed_files: Iterable[str] | None = None,
) -> list[str]:
    """Detects modified, staged, or untracked supply-chain lockfiles."""
    if changed_files is not None:
        detected: set[str] = set()
        for f in changed_files:
            clean = str(f).strip().strip('"')
            if is_protected_lockfile(clean):
                detected.add(clean)
        return sorted(detected)

    worktree_path = Path(repo_dir).resolve()
    if not (worktree_path / ".git").exists():
        # Fallback to direct inspection if directory is not a git repo
        return [
            lockfile
            for lockfile in sorted(PROTECTED_LOCKFILES)
            if (worktree_path / lockfile).exists()
        ]

    modified: set[str] = set()

    # 1. Porcelain status catches staged, unstaged, and untracked changes
    st_res = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if st_res.returncode == 0:
        for raw_line in st_res.stdout.splitlines():
            if len(raw_line) > 3:
                path_part = raw_line[3:].strip().strip('"')
                if " -> " in path_part:
                    path_part = path_part.split(" -> ")[1].strip().strip('"')
                if is_protected_lockfile(path_part):
                    modified.add(path_part)

    # 2. Check committed branch changes against base_ref if specified
    if base_ref:
        diff_res = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )
        if diff_res.returncode != 0:
            diff_res = subprocess.run(
                ["git", "diff", "--name-only", base_ref],
                cwd=worktree_path,
                capture_output=True,
                text=True,
            )
        if diff_res.returncode == 0:
            for line in diff_res.stdout.splitlines():
                clean_path = line.strip().strip('"')
                if is_protected_lockfile(clean_path):
                    modified.add(clean_path)

    return sorted(modified)


def _check_task_waiver(worktree_path: Path) -> tuple[bool, str | None]:
    """Inspects active worktree task frontmatter for dependency authorization."""
    import re
    import yaml

    # Check if cwd or branch contains a task identifier
    m = re.search(r"task[-/](\d+)", worktree_path.name, re.IGNORECASE)
    task_num = m.group(1) if m else None
    if not task_num:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                mb = re.search(r"task[-/](\d+)", res.stdout.strip(), re.IGNORECASE)
                if mb:
                    task_num = mb.group(1)
        except Exception:
            pass

    if not task_num:
        return False, None

    candidate_files: list[Path] = []
    backlog_dir = worktree_path / "docs" / "project" / "backlog"
    if backlog_dir.is_dir():
        candidate_files.extend(backlog_dir.glob("*/*.md"))

    for cf in candidate_files:
        if task_num not in cf.name:
            continue
        try:
            content = cf.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1])
                    if isinstance(fm, dict):
                        if fm.get("allows_dependencies") is True:
                            tid = fm.get("id", cf.stem)
                            return True, f"Backlog task '{tid}' frontmatter explicitly sets 'allows_dependencies: true'"
                        if fm.get("allows_lockfile_mutation") is True:
                            tid = fm.get("id", cf.stem)
                            return True, f"Backlog task '{tid}' frontmatter explicitly sets 'allows_lockfile_mutation: true'"
        except Exception:
            continue

    return False, None


def is_lockfile_mutation_waived(
    repo_dir: Path | str,
    modified_lockfiles: Sequence[str],
    config: SpecOpsConfig | None = None,
    task_allows_dependencies: bool = False,
) -> tuple[bool, str | None]:
    """Determines whether an approved waiver exists for lockfile mutations."""
    if not modified_lockfiles:
        return True, None

    if task_allows_dependencies:
        return True, "Task explicitly authorizes dependency mutations (allows_dependencies: true)"

    worktree_path = Path(repo_dir).resolve()

    # 1. Check task frontmatter waiver in worktree
    task_waived, task_reason = _check_task_waiver(worktree_path)
    if task_waived:
        return True, task_reason

    # 2. Check specops.toml configuration waiver
    if config and config.security:
        if not config.security.lockfile_immutability:
            return True, "specops.toml [security]: lockfile_immutability is disabled"
        if getattr(config.security, "allow_lockfile_mutation", False):
            return True, "specops.toml [security]: allow_lockfile_mutation is enabled"

    cfg_file = worktree_path / "specops.toml"
    if cfg_file.is_file():
        try:
            data = tomllib.loads(cfg_file.read_text(encoding="utf-8"))
            sec = data.get("security", {})
            if isinstance(sec, dict):
                if sec.get("lockfile_immutability") is False:
                    return True, "specops.toml [security]: lockfile_immutability is set to false"
                if sec.get("allow_lockfile_mutation") is True or sec.get("allow_dependencies") is True:
                    return True, "specops.toml [security]: lockfile mutation explicitly permitted"
                waivers = sec.get("waivers", {})
                if isinstance(waivers, dict) and waivers.get("allow_lockfile_mutation") is True:
                    return True, "specops.toml [security.waivers]: lockfile mutation permitted"
        except Exception:
            pass

    # 3. Check architectural approval waivers under compliance/waivers
    from .waivers import is_waiver_expired, load_waivers, verify_waiver_signature

    waiver_dirs = [
        worktree_path / "docs" / "project" / "compliance" / "waivers",
        worktree_path / "docs" / "project" / "security" / "waivers",
    ]
    all_waivers = []
    for wd in waiver_dirs:
        if wd.is_dir():
            all_waivers.extend(load_waivers(wd))

    if all_waivers:
        today = datetime.date.today()
        for w in all_waivers:
            if is_waiver_expired(w, today):
                continue
            if not verify_waiver_signature(w) and w.status.lower() not in ("approved", "active"):
                continue

            pkg_name = w.package.strip().lower()
            if pkg_name in ("lockfile", "lockfiles", "dependencies", "all", "*"):
                return True, f"Approved architectural policy waiver '{w.id}' signed by '{w.signer}' (expires {w.expires})"

            for lockfile in modified_lockfiles:
                base_name = Path(lockfile).name.lower()
                stem_name = Path(lockfile).stem.lower()
                if pkg_name in (base_name, stem_name):
                    return True, f"Approved architectural policy waiver '{w.id}' for '{w.package}' signed by '{w.signer}'"

    return False, None


def remediate_lockfile_mutations(
    repo_dir: Path | str,
    lockfiles: Sequence[str],
) -> list[str]:
    """Reverts unauthorized modifications to protected lockfiles."""
    worktree_path = Path(repo_dir).resolve()
    remediated: list[str] = []

    for file_name in lockfiles:
        clean = str(file_name).strip().strip('"')
        file_path = worktree_path / clean

        # Unstage changes from git index
        subprocess.run(
            ["git", "reset", "HEAD", "--", clean],
            cwd=worktree_path,
            capture_output=True,
        )

        # Checkout tracked version from HEAD
        chk_res = subprocess.run(
            ["git", "checkout", "HEAD", "--", clean],
            cwd=worktree_path,
            capture_output=True,
        )

        # If checkout failed because the file was newly added / untracked, remove it
        if chk_res.returncode != 0 and file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass

        remediated.append(clean)

    return remediated


def inspect_lockfile_sentinel(
    repo_dir: Path | str,
    fix: bool = False,
    config: SpecOpsConfig | None = None,
    task_allows_dependencies: bool = False,
    base_ref: str | None = None,
    changed_files: Iterable[str] | None = None,
) -> LockfileSentinelResult:
    """Inspects worktree file state for unauthorized supply-chain lockfile modifications."""
    modified = detect_lockfile_mutations(repo_dir, base_ref=base_ref, changed_files=changed_files)
    if not modified:
        return LockfileSentinelResult(ok=True)

    waived, waiver_reason = is_lockfile_mutation_waived(
        repo_dir,
        modified_lockfiles=modified,
        config=config,
        task_allows_dependencies=task_allows_dependencies,
    )

    if waived:
        return LockfileSentinelResult(
            ok=True,
            modified_lockfiles=modified,
            waiver_applied=True,
            waiver_details=waiver_reason,
        )

    if fix:
        remediated = remediate_lockfile_mutations(repo_dir, modified)
        return LockfileSentinelResult(
            ok=True,
            modified_lockfiles=modified,
            remediated=remediated,
            violations=[
                f"Remediated unauthorized lockfile modification in '{f}'" for f in remediated
            ],
        )

    violations = [
        f"Unauthorized Supply-Chain Lockfile Mutation: modifying '{f}' is strictly prohibited "
        f"without an approved waiver (ADR-0018)."
        for f in modified
    ]
    return LockfileSentinelResult(
        ok=False,
        modified_lockfiles=modified,
        violations=violations,
    )
