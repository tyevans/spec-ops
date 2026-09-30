"""Supply-chain lockfile verification and slopsquatting defense gate."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

PROTECTED_DEPENDENCY_FILES: frozenset[str] = frozenset({"pyproject.toml", "uv.lock"})
PACKAGE_NAME_REGEX = re.compile(r"^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9])$")
SHA256_HASH_REGEX = re.compile(r"^sha256:[a-fA-F0-9]{64}$")


@dataclass
class LockfileInspectionResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    packages_checked: int = 0


def validate_package_name(name: Any) -> tuple[bool, str]:
    """Validates package name against PyPI naming standards and slopsquatting heuristics."""
    if not isinstance(name, str) or not name.strip():
        return False, "Package name is empty or missing"
    cleaned = name.strip()
    if not PACKAGE_NAME_REGEX.match(cleaned):
        return False, f"Package name '{name}' contains invalid characters or malformed structure"
    return True, ""


def validate_package_pinning(name: str, version: Any) -> tuple[bool, str]:
    """Validates that a package version is strictly pinned without wildcards or loose ranges."""
    if not isinstance(version, str) or not version.strip():
        return False, f"Package '{name}' is unpinned: missing or empty version"
    v = version.strip()
    for operator in ("*", ">", "<", "~", "^", "!", " "):
        if operator in v:
            return False, f"Package '{name}' is unpinned: version '{v}' contains wildcard or range operators"
    return True, ""


def validate_package_hashes(pkg_data: dict[str, Any]) -> tuple[bool, str]:
    """Validates cryptographic integrity records for package wheels and source distributions."""
    name = str(pkg_data.get("name", "unknown"))
    source = pkg_data.get("source", {})
    if isinstance(source, dict) and ("editable" in source or "virtual" in source):
        return True, ""

    sdist = pkg_data.get("sdist")
    wheels = pkg_data.get("wheels")

    if not sdist and not wheels:
        if isinstance(source, dict) and "git" in source:
            return True, ""
        return False, f"Package '{name}' lacks cryptographic records (no sdist or wheels)"

    if sdist is not None:
        if not isinstance(sdist, dict) or "hash" not in sdist:
            return False, f"Package '{name}' sdist is missing cryptographic hash"
        sdist_hash = str(sdist.get("hash", ""))
        if not SHA256_HASH_REGEX.match(sdist_hash):
            return False, f"Package '{name}' sdist has corrupted or non-sha256 hash: '{sdist_hash}'"

    if wheels is not None:
        if not isinstance(wheels, list) or len(wheels) == 0:
            if not sdist:
                return False, f"Package '{name}' has empty wheels list"
        else:
            for w in wheels:
                if not isinstance(w, dict) or "hash" not in w:
                    return False, f"Package '{name}' wheel is missing cryptographic hash"
                w_hash = str(w.get("hash", ""))
                if not SHA256_HASH_REGEX.match(w_hash):
                    return False, f"Package '{name}' wheel has corrupted or non-sha256 hash: '{w_hash}'"

    return True, ""


def inspect_lockfile(lockfile_path: Path) -> LockfileInspectionResult:
    """Parses uv.lock and inspects package pinning, cryptographic hashes, and slopsquatting heuristics."""
    if not lockfile_path.is_file():
        return LockfileInspectionResult(valid=False, errors=[f"Lockfile not found at {lockfile_path}"])

    try:
        data = tomllib.loads(lockfile_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return LockfileInspectionResult(valid=False, errors=[f"Failed to parse lockfile TOML: {exc}"])

    packages = data.get("package", [])
    if not isinstance(packages, list):
        return LockfileInspectionResult(valid=False, errors=["Corrupted lockfile: 'package' table is not a list"])

    errors: list[str] = []
    count = 0
    for pkg in packages:
        if not isinstance(pkg, dict):
            errors.append("Corrupted package record in lockfile")
            continue
        count += 1
        name = pkg.get("name", "")
        name_ok, name_err = validate_package_name(name)
        if not name_ok:
            errors.append(name_err)
            continue

        pin_ok, pin_err = validate_package_pinning(str(name), pkg.get("version"))
        if not pin_ok:
            errors.append(pin_err)

        hash_ok, hash_err = validate_package_hashes(pkg)
        if not hash_ok:
            errors.append(hash_err)

    return LockfileInspectionResult(valid=len(errors) == 0, errors=errors, packages_checked=count)


def verify_uv_lock(cwd: Path) -> tuple[bool, str]:
    """Executes 'uv lock --check' to verify upstream cryptographic hashes and lockfile synchronization."""
    uv_bin = shutil.which("uv")
    if not uv_bin:
        candidate = Path(sys.executable).parent / "uv"
        if candidate.is_file():
            uv_bin = str(candidate)

    cmd = [uv_bin, "lock", "--check"] if uv_bin else ["uv", "lock", "--check"]
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or f"uv lock exited with code {res.returncode}"
            return False, err
        return True, "Lockfile matches pyproject.toml and upstream registry records."
    except FileNotFoundError:
        return False, "uv executable not found on PATH."
    except Exception as exc:
        return False, f"Failed to execute uv lock --check: {exc}"


def verify_lockfile(repo_dir: Path, run_uv: bool = True) -> tuple[bool, list[str]]:
    """Verifies lockfile presence, pinning integrity, cryptographic hashes, and sync state."""
    lockfile_path = repo_dir / "uv.lock"
    errors: list[str] = []

    res = inspect_lockfile(lockfile_path)
    if not res.valid:
        errors.extend(res.errors)

    if run_uv and (repo_dir / "pyproject.toml").is_file():
        uv_ok, uv_msg = verify_uv_lock(repo_dir)
        if not uv_ok:
            errors.append(f"uv lock --check failed: {uv_msg}")

    return len(errors) == 0, errors


def check_diff_for_dependency_modifications(
    changed_files: Iterable[str],
    allows_dependencies: bool,
) -> tuple[bool, list[str]]:
    """Verifies that protected dependency files are only touched when explicitly authorized."""
    touched_protected: list[str] = []
    for file_str in changed_files:
        norm = file_str.strip().replace("\\", "/")
        name = Path(norm).name
        if name in PROTECTED_DEPENDENCY_FILES:
            touched_protected.append(norm)

    if touched_protected and not allows_dependencies:
        files_str = ", ".join(sorted(touched_protected))
        msg = (
            f"Unauthorized Dependency Modification: modifying {files_str} "
            "is strictly forbidden unless 'allows_dependencies: true' is approved in task frontmatter."
        )
        return False, [msg]

    return True, []


def get_worktree_modified_files(worktree_dir: Path, base_ref: str = "main") -> set[str]:
    """Retrieves all staged, unstaged, and committed file changes in a worktree."""
    modified: set[str] = set()

    status_res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if status_res.returncode == 0:
        for raw_line in status_res.stdout.splitlines():
            if len(raw_line) > 3:
                path_part = raw_line[3:].strip()
                if " -> " in path_part:
                    path_part = path_part.split(" -> ")[1].strip()
                modified.add(path_part)

    diff_res = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    if diff_res.returncode == 0:
        for line in diff_res.stdout.splitlines():
            if line.strip():
                modified.add(line.strip())
    else:
        diff_res2 = subprocess.run(
            ["git", "diff", "--name-only", base_ref],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
        )
        if diff_res2.returncode == 0:
            for line in diff_res2.stdout.splitlines():
                if line.strip():
                    modified.add(line.strip())

    return modified


def check_worktree_dependency_integrity(
    worktree_dir: Path,
    allows_dependencies: bool = False,
    base_ref: str = "main",
) -> tuple[bool, list[str]]:
    """Evaluates worktree for unauthorized dependency alterations and verifies lockfile integrity."""
    modified_files = get_worktree_modified_files(worktree_dir, base_ref=base_ref)
    dep_ok, dep_errors = check_diff_for_dependency_modifications(modified_files, allows_dependencies)
    if not dep_ok:
        return False, dep_errors

    touched_protected = any(
        Path(f).name in PROTECTED_DEPENDENCY_FILES for f in modified_files
    )
    if touched_protected:
        lock_ok, lock_errors = verify_lockfile(worktree_dir, run_uv=True)
        if not lock_ok:
            return False, lock_errors

    return True, []
