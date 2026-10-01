"""Hypothesis property tests for pre-commit git hook generation and installation (ADR-0009)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.security.git_hooks import (
    HOOK_END_MARKER,
    HOOK_START_MARKER,
    inject_sentinel_block,
    install_hook,
    resolve_hooks_dir,
    strip_sentinel_block,
    NO_TRAILING_NL_TAG,
    uninstall_hook,
    verify_hook,
)

# Generator for plausible POSIX shell script content without our private markers
safe_script_text = st.text(
    alphabet=st.characters(
        blacklist_characters=("\r", "\x00"),
        blacklist_categories=("Cs",),
    ),
    min_size=0,
    max_size=500,
).filter(
    lambda s: HOOK_START_MARKER not in s
    and HOOK_END_MARKER not in s
    and NO_TRAILING_NL_TAG not in s
)


@given(safe_script_text)
@settings(max_examples=50, deadline=None)
def test_property_inject_and_strip_roundtrip(script: str):
    """Property Invariant: Injecting and stripping the sentinel block roundtrips cleanly."""
    injected = inject_sentinel_block(script)
    assert HOOK_START_MARKER in injected
    assert HOOK_END_MARKER in injected

    stripped = strip_sentinel_block(injected)

    # If the original was empty or just a standard shebang, strip returns None
    if not script or script.strip() in ("", "#!/bin/sh", "#!/bin/bash"):
        assert stripped is None
    else:
        assert stripped == script


@given(safe_script_text)
@settings(max_examples=50, deadline=None)
def test_property_inject_idempotency(script: str):
    """Property Invariant: Multiple inject calls are idempotent and do not duplicate sentinel blocks."""
    once = inject_sentinel_block(script)
    twice = inject_sentinel_block(once)
    assert once == twice
    assert once.count(HOOK_START_MARKER) == 1
    assert once.count(HOOK_END_MARKER) == 1


@given(safe_script_text)
@settings(max_examples=25, deadline=None)
def test_property_filesystem_hook_lifecycle_roundtrip(tmp_path_factory, script: str):
    """Property Invariant: install_hook and uninstall_hook on disk roundtrips without orphaned files."""
    test_dir = tmp_path_factory.mktemp("git_repo")
    subprocess.run(["git", "init", "-q"], cwd=test_dir, check=True)

    hooks_dir = test_dir / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "pre-commit"

    had_prior_content = bool(script and script.strip() not in ("", "#!/bin/sh", "#!/bin/bash"))
    if had_prior_content:
        hook_file.write_text(script, encoding="utf-8")

    # Snapshot existing files in hooks_dir before install
    initial_files = set(hooks_dir.iterdir())

    # Install
    ok_inst, path_inst, _ = install_hook(test_dir)
    assert ok_inst
    assert path_inst == hook_file
    assert hook_file.is_file()

    # Verify
    ok_ver, _ = verify_hook(test_dir)
    assert ok_ver

    # Uninstall
    ok_uninst, path_uninst, _ = uninstall_hook(test_dir)
    assert ok_uninst

    # Check state after uninstall
    current_files = set(hooks_dir.iterdir())
    assert current_files == initial_files

    if had_prior_content:
        assert hook_file.is_file()
        assert hook_file.read_text(encoding="utf-8") == script
    else:
        assert not hook_file.exists()
