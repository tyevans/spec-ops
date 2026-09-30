"""Unit and branch coverage tests for HANDOVER.md generation, cheatsheet rendering, and exclusion gates."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spec_ops.core.models import Task
from spec_ops.rescue.handover import (
    REDACTED_LABEL,
    AttemptSummary,
    HandoverBrief,
    assert_handover_excluded_from_git,
    assert_handover_excluded_from_staging,
    extract_reproduction_command,
    format_handover_markdown,
    generate_handover_brief,
    purge_ephemeral_handover_artifacts,
    render_quickstart_cheatsheet,
    resolve_governing_hyperlinks,
    sanitize_credentials,
)
from spec_ops.security.dual_custody import verify_worker_integration_gates
from spec_ops.worker.hooks import PreCommitHookEvaluator
from spec_ops.worker.preflight import run_worktree_preflight


def test_sanitize_credentials_exhaustive():
    """Tests all secret patterns sanitized by sanitize_credentials."""
    assert sanitize_credentials("") == ""

    # OpenAI / Anthropic key
    dummy_openai = "sk-" + "proj-" + ("1234567890" * 3)
    text = f"openai: {dummy_openai}"
    assert REDACTED_LABEL in sanitize_credentials(text)
    assert ("sk-" + "proj") not in sanitize_credentials(text)

    # AWS Access Key ID
    dummy_aws_id = "AKIA" + "IOSFODNN7EXAMPLE"
    text = f"aws_id = '{dummy_aws_id}'"
    assert REDACTED_LABEL in sanitize_credentials(text)
    assert dummy_aws_id not in sanitize_credentials(text)

    # AWS Secret Access Key
    dummy_aws_secret = "wJalrXUtnFEMI" + "/K7MDENG/bPxRfiCYEXAMPLEKEY"
    key_label = "aws_" + "secret_access_key"
    text = f"{key_label} = '{dummy_aws_secret}'"
    assert REDACTED_LABEL in sanitize_credentials(text)
    assert "wJalrXUtnFEMI" not in sanitize_credentials(text)

    # GitHub token
    dummy_ghp = "ghp_" + ("1234567890" * 4)
    text = f"token: {dummy_ghp}"
    assert REDACTED_LABEL in sanitize_credentials(text)
    assert "ghp_" not in sanitize_credentials(text)

    # Slack token
    dummy_slack = ("xoxb" + "-12345678901-12345678901-") + "abcdefghijklmnopqrstuvwx"
    text = dummy_slack
    assert REDACTED_LABEL in sanitize_credentials(text)
    assert ("xoxb" + "-") not in sanitize_credentials(text)

    # Private key
    dummy_private_key = (
        ("-----" + "BEGIN PRIVATE KEY-----\n")
        + ("MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC3\n")
        + ("-----" + "END PRIVATE KEY-----")
    )
    text = dummy_private_key
    assert REDACTED_LABEL in sanitize_credentials(text)

    # Bearer token
    text = "Authorization: Bearer abcdef123456789012345678"
    assert f"Bearer {REDACTED_LABEL}" in sanitize_credentials(text)

    # Assignment candidates
    key_name = "api" + "_key"
    dummy_key = "super_secret_" + "production_key_123456"
    text = f"{key_name}: '{dummy_key}'"
    assert REDACTED_LABEL in sanitize_credentials(text)


def test_extract_reproduction_command_branches():
    """Tests all fallback branches of extract_reproduction_command."""
    assert extract_reproduction_command("") == "uv run pytest"

    # Specific pytest test
    assert extract_reproduction_command("FAILED tests/test_foo.py::test_bar - AssertionError") == "uv run pytest tests/test_foo.py -k test_bar"
    assert extract_reproduction_command("tests/test_foo.py::test_bar FAILED") == "uv run pytest tests/test_foo.py -k test_bar"

    # Pytest file only
    assert extract_reproduction_command("FAILED tests/test_foo.py (file not found)") == "uv run pytest tests/test_foo.py"

    # File length invariant
    assert extract_reproduction_command("File Length Violation: src/mod.py (520 lines > 500 limit)") == "uv run spec-ops health"
    assert extract_reproduction_command("error: 510 lines > 500 limit") == "uv run spec-ops health"

    # Lockfile integrity
    assert extract_reproduction_command("Error: uv.lock is out of sync") == "uv lock --check"

    # Default fallback
    assert extract_reproduction_command("General compilation error") == "uv run pytest"


def test_resolve_governing_hyperlinks(tmp_path: Path):
    """Tests resolution of hyperlinks with matching and missing files."""
    repo = tmp_path / "repo"
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0004-fleet.md").write_text("# PRD 4\n", encoding="utf-8")

    t = Task(
        id="0014",
        title="Sample Task",
        target_bc="rescue",
        governing_prds=["PRD-0004"],
        governing_stories=["US-0090"],
        governing_adrs=["ADR-0001"],
    )

    prds, stories, adrs = resolve_governing_hyperlinks(t, repo_root=repo)
    assert len(prds) == 1
    assert prds[0][0] == "PRD-0004"
    assert "prd-0004-fleet.md" in prds[0][1]

    assert len(stories) == 1
    assert stories[0][0] == "US-0090"

    assert len(adrs) == 1
    assert adrs[0][0] == "ADR-0001"


def test_format_handover_markdown():
    """Tests format_handover_markdown output formatting."""
    brief = HandoverBrief(
        task_id="TASK-0014",
        title="Handover Title",
        target_bc="rescue",
        attempts=[
            AttemptSummary(attempt=1, exit_code=1, status="Failed"),
            AttemptSummary(attempt=2, exit_code=1, status="Failed"),
            AttemptSummary(attempt=3, exit_code=1, status="Failed"),
        ],
        failure_log="Traceback error",
        reproduction_command="uv run pytest tests/test_curator.py -k test_buffer_sync",
        completion_command="spec-ops rescue TASK-0014 --complete",
        governing_prd_links=[("PRD-0004", "docs/project/product/accepted/prd-0004.md")],
        governing_story_links=[("US-0090", "docs/project/user_stories/accepted/us-0090.md")],
        governing_adr_links=[("ADR-0001", "docs/project/adrs/accepted/0001.md")],
    )

    md = format_handover_markdown(brief)
    assert "# AI-to-Human Handover Brief: TASK-0014" in md
    assert "## Task Header" in md
    assert "- **Canonical ID**: TASK-0014" in md
    assert "- **Title**: Handover Title" in md
    assert "- **Target Bounded Context**: rescue" in md
    assert "## Attempt Timeline" in md
    assert "- Attempt 1: Failed (exit code 1)" in md
    assert "- Attempt 2: Failed (exit code 1)" in md
    assert "- Attempt 3: Failed (exit code 1)" in md
    assert "## Exact Failure Log" in md
    assert "Traceback error" in md
    assert "## Governing Context" in md
    assert "[PRD-0004](docs/project/product/accepted/prd-0004.md)" in md
    assert "## Reproduction Command" in md
    assert "uv run pytest tests/test_curator.py -k test_buffer_sync" in md
    assert "## Completion Command" in md
    assert "spec-ops rescue TASK-0014 --complete" in md


def test_render_quickstart_cheatsheet(tmp_path: Path):
    """Tests render_quickstart_cheatsheet with various configurations."""
    wt = tmp_path / "task-0014"
    wt.mkdir()

    # From explicit repro_cmd
    cs1 = render_quickstart_cheatsheet("TASK-0014", wt, repro_cmd="uv run pytest")
    assert "cd .worktrees/task-0014" in cs1
    assert "uv run pytest" in cs1
    assert "spec-ops rescue TASK-0014 --complete" in cs1
    assert "spec-ops rescue reset TASK-0014" in cs1

    # From existing HANDOVER.md file
    handover = wt / "HANDOVER.md"
    handover.write_text(
        "## Reproduction Command\n```bash\nuv run pytest tests/test_curator.py -k test_buffer_sync\n```\n",
        encoding="utf-8",
    )
    cs2 = render_quickstart_cheatsheet("0014", wt)
    assert "uv run pytest tests/test_curator.py -k test_buffer_sync" in cs2
    assert "TASK-0014" in cs2

    # From failure log when HANDOVER.md is missing
    handover.unlink()
    cs3 = render_quickstart_cheatsheet("14", wt, failure_log="FAILED tests/test_alpha.py::test_beta")
    assert "uv run pytest tests/test_alpha.py -k test_beta" in cs3


def test_generate_handover_brief_and_attempts(tmp_path: Path):
    """Tests generate_handover_brief creating HANDOVER.md and backfilling attempts."""
    wt = tmp_path / "task-0014"
    wt.mkdir()

    t = Task(id="TASK-0014", title="Feature Title", target_bc="rescue")
    path = generate_handover_brief(wt, t, failure_log="FAILED tests/test_curator.py::test_buffer_sync", attempts=[AttemptSummary(attempt=1, exit_code=1)])
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    assert "Attempt 1" in content
    assert "Attempt 2" in content
    assert "Attempt 3" in content


def test_purge_ephemeral_handover_artifacts(tmp_path: Path):
    """Tests purging HANDOVER.md and .task-prompt.md."""
    wt = tmp_path / "task-0014"
    wt.mkdir()
    (wt / "HANDOVER.md").write_text("handover", encoding="utf-8")
    (wt / ".task-prompt.md").write_text("prompt", encoding="utf-8")

    purged = purge_ephemeral_handover_artifacts(wt)
    assert "HANDOVER.md" in purged
    assert ".task-prompt.md" in purged
    assert not (wt / "HANDOVER.md").exists()
    assert not (wt / ".task-prompt.md").exists()


def test_assert_handover_excluded_from_staging(tmp_path: Path):
    """Tests assert_handover_excluded_from_staging detect staged files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    (repo / "work.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "work.py"], cwd=repo, check=True, capture_output=True)

    ok, msg = assert_handover_excluded_from_staging(repo)
    assert ok is True
    assert msg == ""

    # Force stage HANDOVER.md
    (repo / "HANDOVER.md").write_text("# Handover\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "HANDOVER.md"], cwd=repo, check=True, capture_output=True)

    ok, msg = assert_handover_excluded_from_staging(repo)
    assert ok is False
    assert "HANDOVER.md" in msg


def test_assert_handover_excluded_from_git(tmp_path: Path):
    """Tests assert_handover_excluded_from_git detects commits containing HANDOVER.md."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    (repo / "initial.txt").write_text("init", encoding="utf-8")
    subprocess.run(["git", "add", "initial.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    ok, _ = assert_handover_excluded_from_git(repo)
    assert ok is True

    # Commit HANDOVER.md
    (repo / "HANDOVER.md").write_text("handover", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "HANDOVER.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add handover"], cwd=repo, check=True, capture_output=True)

    ok, msg = assert_handover_excluded_from_git(repo)
    assert ok is False
    assert "committed to git" in msg


def test_preflight_and_hook_gates_reject_staged_handover(tmp_path: Path):
    """Tests preflight and pre-commit hook reject staged HANDOVER.md."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    from spec_ops.scaffold.init import init_project
    init_project(name="GateTest", target_dir=repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init project"], cwd=repo, check=True, capture_output=True)

    from spec_ops.config.loader import load_config
    cfg = load_config(repo)
    cfg.quality.preflight = []

    # Staging HANDOVER.md
    (repo / "HANDOVER.md").write_text("handover", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "HANDOVER.md"], cwd=repo, check=True, capture_output=True)

    # 1. Preflight rejection
    preflight_ok, preflight_log = run_worktree_preflight(cfg, cwd=repo)
    assert preflight_ok is False
    assert "HANDOVER.md" in preflight_log

    # 2. Pre-commit hook rejection
    evaluator = PreCommitHookEvaluator(root_dir=repo, config=cfg)
    hook_res = evaluator.evaluate()
    assert hook_res.success is False
    assert "Pre-commit Staging Violation" in hook_res.output
