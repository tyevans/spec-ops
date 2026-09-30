"""Generative property invariant tests for HANDOVER.md generation and secret exclusion (ADR-0009)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.models import Task
from spec_ops.rescue.handover import (
    REDACTED_LABEL,
    extract_reproduction_command,
    format_handover_markdown,
    generate_handover_brief,
    sanitize_credentials,
)
from spec_ops.security.secrets.patterns import (
    AWS_ACCESS_KEY_ID_PATTERN,
    AWS_SECRET_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    OPENAI_KEY_PATTERN,
    PRIVATE_KEY_PATTERN,
    SLACK_TOKEN_PATTERN,
)

# Hypothesis strategy for generating secret tokens
secret_tokens = st.one_of(
    st.from_regex(r"sk-[a-zA-Z0-9]{24}", fullmatch=True),
    st.from_regex(r"AKIA[A-Z0-9]{16}", fullmatch=True),
    st.from_regex(r"ghp_[a-zA-Z0-9]{36}", fullmatch=True),
    st.from_regex(r"xoxb-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{24}", fullmatch=True),
    st.just(
        ("-----" + "BEGIN PRIVATE KEY-----\n")
        + ("MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC3\n")
        + ("-----" + "END PRIVATE KEY-----")
    ),
    st.from_regex(r"Bearer [a-zA-Z0-9_\-\.]{24}", fullmatch=True),
)

safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "P")),
    min_size=1,
    max_size=200,
)


@settings(max_examples=40, deadline=None)
@given(prefix=safe_text, secret=secret_tokens, suffix=safe_text)
def test_generated_handover_never_contains_unescaped_credentials(tmp_path_factory, prefix: str, secret: str, suffix: str):
    """Asserts that generated HANDOVER.md never contains unescaped credentials or secrets (ADR-0009)."""
    raw_log = f"{prefix}\nError occurred with token: {secret}\n{suffix}"
    sanitized = sanitize_credentials(raw_log)

    # Invariant: Secret patterns must not match in sanitized output
    assert not OPENAI_KEY_PATTERN.search(sanitized)
    assert not AWS_ACCESS_KEY_ID_PATTERN.search(sanitized)
    assert not GITHUB_TOKEN_PATTERN.search(sanitized)
    assert not SLACK_TOKEN_PATTERN.search(sanitized)
    assert not PRIVATE_KEY_PATTERN.search(sanitized)
    assert "Bearer ey" not in sanitized

    # Invariant: File output must be sanitized
    tmp = tmp_path_factory.mktemp("wt")
    t = Task(id="0014", title="Test Task", target_bc="rescue")
    handover_path = generate_handover_brief(tmp, t, failure_log=raw_log)
    content = handover_path.read_text(encoding="utf-8")

    assert not OPENAI_KEY_PATTERN.search(content)
    assert not AWS_ACCESS_KEY_ID_PATTERN.search(content)
    assert not GITHUB_TOKEN_PATTERN.search(content)
    assert not SLACK_TOKEN_PATTERN.search(content)
    assert not PRIVATE_KEY_PATTERN.search(content)


@settings(max_examples=25, deadline=None)
@given(
    task_num=st.integers(min_value=1, max_value=9999),
    failure_snippet=safe_text,
)
def test_generated_handover_is_ignored_by_git_status(tmp_path_factory, task_num: int, failure_snippet: str):
    """Asserts that generated HANDOVER.md files are ignored by git status (ADR-0009)."""
    repo = tmp_path_factory.mktemp("git_repo")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    # Create .gitignore with HANDOVER.md
    (repo / ".gitignore").write_text(".worktrees/\nHANDOVER.md\n.task-prompt.md\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)

    # Generate HANDOVER.md inside repo (simulating worktree working tree)
    t = Task(id=str(task_num), title=f"Task {task_num}", target_bc="rescue")
    generate_handover_brief(repo, t, failure_log=failure_snippet)

    # Check git status
    st_res = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True)
    # Invariant: HANDOVER.md must not appear in untracked files
    assert "HANDOVER.md" not in st_res.stdout


@settings(max_examples=30, deadline=None)
@given(
    task_id=st.from_regex(r"TASK-[0-9]{4}", fullmatch=True),
    title=safe_text,
    failure_log=safe_text,
)
def test_handover_markdown_structure_invariants(task_id: str, title: str, failure_log: str):
    """Asserts that format_handover_markdown produces all 6 mandatory sections."""
    t = Task(id=task_id, title=title, target_bc="rescue")
    prds = [("PRD-0004", "docs/project/product/accepted/prd-0004.md")]
    stories = [("US-0090", "docs/project/user_stories/accepted/us-0090.md")]
    adrs = [("ADR-0001", "docs/project/adrs/accepted/0001.md")]

    from spec_ops.rescue.handover import AttemptSummary, HandoverBrief

    brief = HandoverBrief(
        task_id=task_id,
        title=title,
        target_bc="rescue",
        attempts=[
            AttemptSummary(attempt=1, exit_code=1, status="Failed"),
            AttemptSummary(attempt=2, exit_code=1, status="Failed"),
            AttemptSummary(attempt=3, exit_code=1, status="Failed"),
        ],
        failure_log=failure_log,
        reproduction_command="uv run pytest tests/test_curator.py -k test_buffer_sync",
        completion_command=f"spec-ops rescue {task_id} --complete",
        governing_prd_links=prds,
        governing_story_links=stories,
        governing_adr_links=adrs,
    )
    md = format_handover_markdown(brief)

    # Mandatory 6 sections
    assert "## Task Header" in md
    assert "## Attempt Timeline" in md
    assert "## Exact Failure Log" in md
    assert "## Governing Context" in md
    assert "## Reproduction Command" in md
    assert "## Completion Command" in md

    # Exact content preservation
    assert task_id in md
    assert "Attempt 1" in md
    assert "Attempt 2" in md
    assert "Attempt 3" in md
    assert f"spec-ops rescue {task_id} --complete" in md


@settings(max_examples=30, deadline=None)
@given(
    module_name=st.from_regex(r"[a-z_]{3,12}", fullmatch=True),
    func_name=st.from_regex(r"[a-z_]{3,12}", fullmatch=True),
)
def test_reproduction_command_deterministic(module_name: str, func_name: str):
    """Asserts that extract_reproduction_command consistently generates valid command lines."""
    log = f"FAILED tests/test_{module_name}.py::test_{func_name} - AssertionError: failed"
    cmd = extract_reproduction_command(log)
    assert cmd == f"uv run pytest tests/test_{module_name}.py -k test_{func_name}"

    log_file_only = f"FAILED tests/test_{module_name}.py - ModuleNotFoundError"
    cmd_file = extract_reproduction_command(log_file_only)
    assert cmd_file == f"uv run pytest tests/test_{module_name}.py"

    health_log = "File Length Violation: src/parser.py (540 lines > 500 limit)"
    cmd_health = extract_reproduction_command(health_log)
    assert cmd_health == "uv run spec-ops health"

    lock_log = "Error: uv.lock is out of sync"
    cmd_lock = extract_reproduction_command(lock_log)
    assert cmd_lock == "uv lock --check"
