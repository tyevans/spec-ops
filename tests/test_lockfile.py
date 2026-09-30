"""Unit and regression tests for supply-chain lockfile verification and slopsquatting defense."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.security.lockfile import (
    PROTECTED_DEPENDENCY_FILES,
    check_diff_for_dependency_modifications,
    check_worktree_dependency_integrity,
    get_worktree_modified_files,
    inspect_lockfile,
    validate_package_hashes,
    validate_package_name,
    validate_package_pinning,
    verify_lockfile,
    verify_uv_lock,
)

VALID_SHA256 = "sha256:ba0d2089de75ea0310e2dde03160e6ca10009947fb95a182f9b54021bb272e34"


def test_validate_package_name_valid():
    assert validate_package_name("requests")[0] is True
    assert validate_package_name("annotated-types")[0] is True
    assert validate_package_name("my_package.v2")[0] is True
    assert validate_package_name("A123")[0] is True


def test_validate_package_name_invalid():
    assert validate_package_name("")[0] is False
    assert validate_package_name("   ")[0] is False
    assert validate_package_name(None)[0] is False
    assert validate_package_name(123)[0] is False
    assert validate_package_name("foo bar")[0] is False
    assert validate_package_name("-foo")[0] is False
    assert validate_package_name("foo-")[0] is False
    assert validate_package_name("foo/bar")[0] is False
    assert validate_package_name("@evil/pkg")[0] is False


def test_validate_package_pinning_valid():
    assert validate_package_pinning("foo", "1.0.0")[0] is True
    assert validate_package_pinning("foo", "0.8.0.post1")[0] is True
    assert validate_package_pinning("foo", "2.0.0b3")[0] is True


def test_validate_package_pinning_invalid():
    assert validate_package_pinning("foo", "")[0] is False
    assert validate_package_pinning("foo", None)[0] is False
    assert validate_package_pinning("foo", "*")[0] is False
    assert validate_package_pinning("foo", ">=1.0.0")[0] is False
    assert validate_package_pinning("foo", "<2.0")[0] is False
    assert validate_package_pinning("foo", "~=1.0")[0] is False
    assert validate_package_pinning("foo", "^1.0")[0] is False
    assert validate_package_pinning("foo", "!=1.0")[0] is False
    assert validate_package_pinning("foo", "1.0 2.0")[0] is False


def test_validate_package_hashes_editable_and_git():
    # Editable / virtual local workspace packages require no remote hashes
    assert validate_package_hashes({"name": "spec-ops", "source": {"editable": "."}})[0] is True
    assert validate_package_hashes({"name": "spec-ops", "source": {"virtual": "."}})[0] is True
    assert validate_package_hashes({"name": "my-tool", "source": {"git": "https://github.com/foo/bar"}})[0] is True


def test_validate_package_hashes_missing_records():
    res, msg = validate_package_hashes({"name": "slop", "source": {"registry": "https://pypi.org/simple"}})
    assert res is False
    assert "lacks cryptographic records" in msg


def test_validate_package_hashes_sdist():
    # Valid sdist hash
    pkg_valid = {
        "name": "foo",
        "sdist": {"hash": VALID_SHA256},
    }
    assert validate_package_hashes(pkg_valid)[0] is True

    # Missing hash in sdist dict
    pkg_missing = {"name": "foo", "sdist": {}}
    assert validate_package_hashes(pkg_missing)[0] is False

    # Corrupted / non-sha256 hash
    pkg_corrupted = {"name": "foo", "sdist": {"hash": "md5:12345"}}
    assert validate_package_hashes(pkg_corrupted)[0] is False

    pkg_short = {"name": "foo", "sdist": {"hash": "sha256:abc"}}
    assert validate_package_hashes(pkg_short)[0] is False


def test_validate_package_hashes_wheels():
    pkg_valid = {
        "name": "foo",
        "wheels": [{"hash": VALID_SHA256}],
    }
    assert validate_package_hashes(pkg_valid)[0] is True

    # Corrupted wheel hash
    pkg_bad = {
        "name": "foo",
        "wheels": [{"hash": "sha256:not-hex-64"}],
    }
    assert validate_package_hashes(pkg_bad)[0] is False

    # Wheel missing hash
    pkg_no_hash = {"name": "foo", "wheels": [{}]}
    assert validate_package_hashes(pkg_no_hash)[0] is False

    # Empty wheels list without sdist
    pkg_empty = {"name": "foo", "wheels": []}
    assert validate_package_hashes(pkg_empty)[0] is False


def test_inspect_lockfile_missing(tmp_path: Path):
    res = inspect_lockfile(tmp_path / "nonexistent.lock")
    assert res.valid is False
    assert "not found" in res.errors[0]


def test_inspect_lockfile_malformed_toml(tmp_path: Path):
    bad_toml = tmp_path / "uv.lock"
    bad_toml.write_text("invalid = [toml content", encoding="utf-8")
    res = inspect_lockfile(bad_toml)
    assert res.valid is False
    assert "Failed to parse lockfile TOML" in res.errors[0]


def test_inspect_lockfile_package_not_list(tmp_path: Path):
    bad = tmp_path / "uv.lock"
    bad.write_text('package = "not a list"\n', encoding="utf-8")
    res = inspect_lockfile(bad)
    assert res.valid is False
    assert "is not a list" in res.errors[0]


def test_inspect_lockfile_corrupted_package(tmp_path: Path):
    f = tmp_path / "uv.lock"
    f.write_text('package = [123]\n', encoding="utf-8")
    res = inspect_lockfile(f)
    assert res.valid is False
    assert "Corrupted package record" in res.errors[0]


def test_inspect_lockfile_slopsquatting_unpinned(tmp_path: Path):
    f = tmp_path / "uv.lock"
    f.write_text(
        'version = 1\n[[package]]\nname = "slop-hallucination"\nversion = "*"\n',
        encoding="utf-8",
    )
    res = inspect_lockfile(f)
    assert res.valid is False
    assert any("unpinned" in e for e in res.errors)


def test_inspect_lockfile_current_repo(tmp_path: Path):
    # Verify current repo uv.lock passes inspection
    current_lock = Path(__file__).resolve().parent.parent / "uv.lock"
    if current_lock.is_file():
        res = inspect_lockfile(current_lock)
        assert res.valid is True
        assert res.packages_checked > 0


def test_check_diff_for_dependency_modifications():
    # Clean non-dependency files
    ok, errs = check_diff_for_dependency_modifications(
        ["src/spec_ops/main.py", "tests/test_app.py", "README.md"],
        allows_dependencies=False,
    )
    assert ok is True
    assert errs == []

    # Unauthorized pyproject.toml modification
    ok, errs = check_diff_for_dependency_modifications(
        ["pyproject.toml"],
        allows_dependencies=False,
    )
    assert ok is False
    assert "Unauthorized Dependency Modification" in errs[0]

    # Unauthorized uv.lock modification in subdirectory
    ok, errs = check_diff_for_dependency_modifications(
        ["subdir/uv.lock"],
        allows_dependencies=False,
    )
    assert ok is False
    assert "Unauthorized Dependency Modification" in errs[0]

    # Authorized dependency modification
    ok, errs = check_diff_for_dependency_modifications(
        ["pyproject.toml", "uv.lock"],
        allows_dependencies=True,
    )
    assert ok is True
    assert errs == []


def test_check_worktree_dependency_integrity_clean(tmp_path: Path):
    # Init clean git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    ok, errors = check_worktree_dependency_integrity(tmp_path, allows_dependencies=False)
    assert ok is True
    assert errors == []


def test_check_worktree_dependency_integrity_unauthorized(tmp_path: Path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nname="test"\nversion="0.1.0"\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # Modify pyproject.toml without permission
    (tmp_path / "pyproject.toml").write_text('[project]\nname="test"\nversion="0.1.0"\ndependencies=["slop"]\n', encoding="utf-8")

    ok, errors = check_worktree_dependency_integrity(tmp_path, allows_dependencies=False)
    assert ok is False
    assert any("Unauthorized Dependency Modification" in e for e in errors)
