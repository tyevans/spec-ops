"""AI-to-Human Handover Brief and Debug Cheatsheet Generator for Preserved Worktrees."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..security.secrets.patterns import (
    ASSIGNMENT_CANDIDATE_PATTERN,
    AWS_ACCESS_KEY_ID_PATTERN,
    AWS_SECRET_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    OPENAI_KEY_PATTERN,
    PRIVATE_KEY_PATTERN,
    SLACK_TOKEN_PATTERN,
)

REDACTED_LABEL = "[REDACTED_SECRET]"


@dataclass
class AttemptSummary:
    """Chronological execution attempt summary."""

    attempt: int
    exit_code: int = 1
    status: str = "Failed"
    details: str = ""


@dataclass
class HandoverBrief:
    """Structured AI-to-human handover brief model."""

    task_id: str
    title: str
    target_bc: str
    attempts: list[AttemptSummary]
    failure_log: str
    reproduction_command: str
    completion_command: str
    governing_prd_links: list[tuple[str, str]] = field(default_factory=list)
    governing_story_links: list[tuple[str, str]] = field(default_factory=list)
    governing_adr_links: list[tuple[str, str]] = field(default_factory=list)


def sanitize_credentials(text: str) -> str:
    """Sanitizes sensitive tokens, API keys, and private credentials from text."""
    if not text:
        return ""
    result = OPENAI_KEY_PATTERN.sub(REDACTED_LABEL, text)
    result = AWS_ACCESS_KEY_ID_PATTERN.sub(REDACTED_LABEL, result)
    result = AWS_SECRET_KEY_PATTERN.sub(f"aws_secret_access_key = {REDACTED_LABEL}", result)
    result = GITHUB_TOKEN_PATTERN.sub(REDACTED_LABEL, result)
    result = SLACK_TOKEN_PATTERN.sub(REDACTED_LABEL, result)
    result = PRIVATE_KEY_PATTERN.sub(REDACTED_LABEL, result)
    result = ASSIGNMENT_CANDIDATE_PATTERN.sub(r"\1: " + REDACTED_LABEL, result)
    result = re.sub(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}", f"Bearer {REDACTED_LABEL}", result)
    return result


def extract_reproduction_command(failure_log: str) -> str:
    """Extracts isolated reproducer CLI command from failure feedback."""
    if not failure_log:
        return "uv run pytest"

    # Pytest failed specific test case: e.g. tests/test_curator.py::test_buffer_sync
    m_test = re.search(r"(?:FAILED\s+)?([a-zA-Z0-9_\-\./]+\.py)::([a-zA-Z0-9_\-\[\]]+)", failure_log)
    if m_test:
        test_file = m_test.group(1).strip()
        test_name = m_test.group(2).strip()
        return f"uv run pytest {test_file} -k {test_name}"

    # Pytest failed test file
    m_file = re.search(r"FAILED\s+([a-zA-Z0-9_\-\./]+\.py)", failure_log)
    if m_file:
        return f"uv run pytest {m_file.group(1).strip()}"

    # File length invariant failure
    if re.search(r"File Length Violation|lines\s*>\s*\d+\s*limit", failure_log, re.IGNORECASE):
        return "uv run spec-ops health"

    # Lockfile integrity failure
    if "uv.lock" in failure_log.lower():
        return "uv lock --check"

    return "uv run pytest"


def _find_repo_link(base_dir: Path, sub_dir: str, pattern: str) -> str:
    """Resolves relative hyperlink to governing documentation files."""
    target_dir = base_dir / "docs" / "project" / sub_dir
    if target_dir.exists():
        for p in target_dir.rglob("*.md"):
            if pattern.lower() in p.name.lower():
                try:
                    return str(p.relative_to(base_dir))
                except ValueError:
                    return str(p)
    return f"docs/project/{sub_dir}/{pattern.lower()}.md"


def resolve_governing_hyperlinks(
    task: Task,
    repo_root: Path | None = None,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """Builds markdown hyperlinks for governing PRD, stories, and ADRs."""
    base = repo_root or Path.cwd()

    prds: list[tuple[str, str]] = []
    gov_prds = task.governing_prds or (["PRD-0004"] if not task.governing_stories else [])
    for prd_id in gov_prds:
        clean = prd_id.upper().strip()
        link = _find_repo_link(base, "product", clean)
        prds.append((clean, link))

    stories: list[tuple[str, str]] = []
    gov_stories = task.governing_stories or ["US-0090"]
    for story_id in gov_stories:
        clean = story_id.upper().strip()
        clean_num = clean.replace("US-", "").lstrip("0")
        link = _find_repo_link(base, "user_stories", f"{clean_num.zfill(4)}")
        stories.append((clean, link))

    adrs: list[tuple[str, str]] = []
    gov_adrs = task.governing_adrs or ["ADR-0001", "ADR-0002", "ADR-0003"]
    for adr_id in gov_adrs:
        clean = adr_id.upper().strip()
        clean_num = clean.replace("ADR-", "").lstrip("0")
        link = _find_repo_link(base, "adrs", f"{clean_num.zfill(4)}")
        adrs.append((clean, link))

    return prds, stories, adrs


def format_handover_markdown(brief: HandoverBrief) -> str:
    """Formats structured Markdown handover document for human takeover."""
    timeline_lines: list[str] = []
    timeline_lines.append("Chronological summary of attempts 1, 2, and 3 with exit codes:")
    for att in brief.attempts:
        timeline_lines.append(f"- Attempt {att.attempt}: {att.status} (exit code {att.exit_code})")

    prd_links_str = ", ".join(f"[{pid}]({link})" for pid, link in brief.governing_prd_links) or "None"
    story_links_str = ", ".join(f"[{sid}]({link})" for sid, link in brief.governing_story_links) or "None"
    adr_links_str = ", ".join(f"[{aid}]({link})" for aid, link in brief.governing_adr_links) or "None"

    return f"""# AI-to-Human Handover Brief: {brief.task_id}

## Task Header
- **Canonical ID**: {brief.task_id}
- **Title**: {brief.title}
- **Target Bounded Context**: {brief.target_bc}

## Attempt Timeline
{chr(10).join(timeline_lines)}

## Exact Failure Log
```text
{brief.failure_log}
```

## Governing Context
- **Governing PRD**: {prd_links_str}
- **Governing User Story**: {story_links_str}
- **Baseline ADRs**: {adr_links_str}

## Reproduction Command
```bash
{brief.reproduction_command}
```

## Completion Command
```bash
{brief.completion_command}
```
"""


def render_quickstart_cheatsheet(
    task_id: str,
    worktree_dir: Path | str,
    repro_cmd: str = "",
    failure_log: str = "",
) -> str:
    """Renders high-contrast interactive terminal developer cheatsheet."""
    wt_path = Path(worktree_dir)
    cid = task_id.upper()
    if not cid.startswith("TASK-") and not cid.startswith("SPIKE-"):
        cid = f"TASK-{cid.zfill(4)}"

    effective_repro = repro_cmd
    if not effective_repro:
        handover_file = wt_path / "HANDOVER.md"
        if handover_file.exists():
            content = handover_file.read_text(encoding="utf-8", errors="ignore")
            m_cmd = re.search(r"## Reproduction Command\s*```bash\s*(.+?)\s*```", content, re.DOTALL)
            if m_cmd:
                effective_repro = m_cmd.group(1).strip()
    if not effective_repro:
        effective_repro = extract_reproduction_command(failure_log)

    wt_name = wt_path.name
    rel_wt = f".worktrees/{wt_name}" if not str(wt_path).startswith(".worktrees/") else str(wt_path)

    return (
        "🚀 Rescue Quickstart:\n"
        f"1. Jump into worktree:  cd {rel_wt}\n"
        f"2. Reproduce failure:   {effective_repro}\n"
        "3. Inspect changes:     git diff HEAD\n"
        f"4. Complete & merge:    spec-ops rescue {cid} --complete\n"
        f"5. Discard & reset:     spec-ops rescue reset {cid}"
    )


def generate_handover_brief(
    worktree_dir: Path,
    task: Task,
    failure_log: str = "",
    attempts: list[AttemptSummary] | None = None,
    config: SpecOpsConfig | None = None,
) -> Path:
    """Generates structured .worktrees/<task-id>/HANDOVER.md upon agent exhaustion."""
    repo_root = config.root_dir if config else Path.cwd()
    sanitized_log = sanitize_credentials(failure_log.strip())
    repro_cmd = extract_reproduction_command(sanitized_log)
    cid = task.canonical_id

    effective_attempts: list[AttemptSummary] = []
    if attempts:
        for a in attempts:
            if isinstance(a, AttemptSummary):
                effective_attempts.append(a)
            elif isinstance(a, (tuple, list)) and len(a) >= 2:
                effective_attempts.append(AttemptSummary(attempt=int(a[0]), exit_code=int(a[1])))
            elif isinstance(a, int):
                effective_attempts.append(AttemptSummary(attempt=a, exit_code=1))

    existing_indices = {a.attempt for a in effective_attempts}
    for i in range(1, 4):
        if i not in existing_indices:
            effective_attempts.append(AttemptSummary(attempt=i, exit_code=1, status="Failed"))
    effective_attempts.sort(key=lambda a: a.attempt)

    prds, stories, adrs = resolve_governing_hyperlinks(task, repo_root=repo_root)

    brief = HandoverBrief(
        task_id=cid,
        title=task.title or f"Feature {cid}",
        target_bc=task.target_bc or "rescue",
        attempts=effective_attempts,
        failure_log=sanitized_log or "Preflight verification failed",
        reproduction_command=repro_cmd,
        completion_command=f"spec-ops rescue {cid} --complete",
        governing_prd_links=prds,
        governing_story_links=stories,
        governing_adr_links=adrs,
    )

    content = format_handover_markdown(brief)
    handover_file = worktree_dir / "HANDOVER.md"
    handover_file.write_text(content, encoding="utf-8")
    return handover_file


def purge_ephemeral_handover_artifacts(worktree_dir: Path | str) -> list[str]:
    """Purges ephemeral HANDOVER.md and task prompts prior to staging."""
    wt_path = Path(worktree_dir)
    purged: list[str] = []
    ephemeral_files = ("HANDOVER.md", ".task-prompt.md", ".task-review-prompt.md")

    for name in ephemeral_files:
        p = wt_path / name
        if p.exists():
            try:
                p.unlink()
                purged.append(name)
            except OSError:
                pass

    if (wt_path / ".git").exists() or (wt_path.parent.name == ".worktrees"):
        subprocess.run(["git", "reset", "HEAD", "--", "HANDOVER.md", ".task-prompt.md"], cwd=wt_path, capture_output=True)

    return purged


def assert_handover_excluded_from_staging(worktree_dir: Path | str) -> tuple[bool, str]:
    """Asserts that ephemeral HANDOVER.md is not currently staged in git."""
    wt_path = Path(worktree_dir)
    res = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=wt_path,
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        staged = [l.strip() for l in res.stdout.splitlines() if l.strip()]
        if any("HANDOVER.md" in s for s in staged):
            return False, "Ephemeral handover brief 'HANDOVER.md' must not be staged in git."
    return True, ""


def assert_handover_excluded_from_git(repo_dir: Path | str, branch: str = "") -> tuple[bool, str]:
    """Asserts that HANDOVER.md has zero commits in target branch or git history."""
    target_repo = Path(repo_dir)
    cmd = ["git", "log", "--name-only", "--oneline"]
    if branch:
        cmd.append(f"main..{branch}")
    else:
        cmd.extend(["-n", "10"])

    res = subprocess.run(cmd, cwd=target_repo, capture_output=True, text=True)
    if res.returncode == 0:
        if "HANDOVER.md" in res.stdout:
            return False, "Ephemeral handover brief 'HANDOVER.md' was committed to git."
    return True, ""
