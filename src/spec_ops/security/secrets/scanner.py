"""Worktree diff scanner for high-entropy credentials and sensitive files."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .dotfiles import EXCLUDED_SCAN_DIRS, scan_dotfiles
from .entropy import is_high_entropy, mask_secret, shannon_entropy
from .models import DotfileViolation, SecretScanReport, SecretViolation
from .patterns import (
    ASSIGNMENT_CANDIDATE_PATTERN,
    AWS_ACCESS_KEY_ID_PATTERN,
    AWS_SECRET_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    OPENAI_KEY_PATTERN,
    PRIVATE_KEY_PATTERN,
    QUOTED_TOKEN_PATTERN,
    SLACK_TOKEN_PATTERN,
    is_sensitive_dotfile,
)

__all__ = [
    "DotfileViolation",
    "EXCLUDED_SCAN_DIRS",
    "INLINE_IGNORE_PATTERN",
    "SecretScanReport",
    "SecretViolation",
    "scan_diff",
    "scan_dotfiles",
    "scan_file",
    "scan_line",
    "scan_text",
    "scan_worktree",
]

INLINE_IGNORE_PATTERN = re.compile(
    r"(?:#|//|/\*)\s*(?:spec-ops:\s*ignore[-_]secret|pragma:\s*allowlist[-_\s]secret)",
    re.IGNORECASE,
)


def scan_line(
    line: str,
    line_number: int | None = None,
    file_path: str = "",
    threshold: float | None = None,
) -> list[SecretViolation]:
    """Scans a single source line for hardcoded secrets, API keys, and high-entropy tokens."""
    if INLINE_IGNORE_PATTERN.search(line):
        return []

    violations: list[SecretViolation] = []
    seen_tokens: set[str] = set()

    # 1. Cryptographic Private Key Header
    if PRIVATE_KEY_PATTERN.search(line):
        m = PRIVATE_KEY_PATTERN.search(line)
        token = m.group(0) if m else line
        violations.append(SecretViolation(
            file_path=file_path,
            line_number=line_number,
            secret_type="Cryptographic Private Key",
            masked_token=mask_secret(token),
            raw_snippet=line.strip(),
        ))
        seen_tokens.add(token)

    # 2. OpenAI / Anthropic API Key
    for m in OPENAI_KEY_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens:
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="OpenAI/Anthropic API Key",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    # 3. AWS Access Key ID
    for m in AWS_ACCESS_KEY_ID_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens:
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="AWS Access Key ID",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    # 4. AWS Secret Access Key Pattern
    aws_th = threshold if threshold is not None else 3.5
    for m in AWS_SECRET_KEY_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens and is_high_entropy(token, threshold=aws_th, min_length=30):
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="AWS Secret Access Key",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    # 5. GitHub Token
    for m in GITHUB_TOKEN_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens:
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="GitHub Access Token",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    # 6. Slack Token
    for m in SLACK_TOKEN_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens:
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="Slack Token",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    # 7. Assignment of High-Entropy Token
    assign_th = threshold if threshold is not None else 3.6
    for m in ASSIGNMENT_CANDIDATE_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens and is_high_entropy(token, threshold=assign_th, min_length=16):
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="High-Entropy Credential Assignment",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    # 8. Standalone Quoted High-Entropy Token
    quoted_th = max(threshold, 4.0) if threshold is not None else 4.2
    for m in QUOTED_TOKEN_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens and is_high_entropy(token, threshold=quoted_th, min_length=32):
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="High-Entropy Secret Literal",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    return violations


def scan_text(
    text: str,
    file_path: str = "",
    threshold: float | None = None,
) -> list[SecretViolation]:
    """Scans multi-line source text for hardcoded secrets and credentials."""
    violations: list[SecretViolation] = []
    for line_idx, line in enumerate(text.splitlines(), start=1):
        violations.extend(scan_line(line, line_number=line_idx, file_path=file_path, threshold=threshold))
    return violations


def scan_diff(diff_text: str, threshold: float | None = None) -> list[SecretViolation]:
    """Parses unified git diff output and scans newly added lines for credentials."""
    violations: list[SecretViolation] = []
    current_file = ""
    current_line = 0

    hunk_header_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git"):
            current_line = 0
        elif raw_line.startswith("+++ b/"):
            current_file = raw_line[6:].strip()
        elif raw_line.startswith("@@"):
            m = hunk_header_re.match(raw_line)
            if m:
                current_line = int(m.group(1))
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            added_content = raw_line[1:]
            violations.extend(
                scan_line(added_content, line_number=current_line, file_path=current_file, threshold=threshold)
            )
            current_line += 1
        elif raw_line.startswith(" "):
            current_line += 1

    return violations


def scan_file(file_path: Path, threshold: float | None = None) -> SecretScanReport:
    """Scans a single file on disk for credentials and sensitive dotfile naming."""
    dotfile_violations: list[DotfileViolation] = []
    if is_sensitive_dotfile(file_path.name):
        dotfile_violations.append(
            DotfileViolation(
                file_path=str(file_path),
                action_instructions=f"Action: Add '{file_path.name}' to .gitignore and remove it from git staging.",
            )
        )
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        secret_violations = scan_text(content, file_path=str(file_path), threshold=threshold)
    except OSError:
        secret_violations = []

    return SecretScanReport(secret_violations=secret_violations, dotfile_violations=dotfile_violations)


def _scan_staged_git(
    root_dir: Path,
    threshold: float | None = None,
) -> tuple[list[SecretViolation], list[DotfileViolation]]:
    """Scans git staged changes only."""
    sec_violations: list[SecretViolation] = []
    dot_violations: list[DotfileViolation] = []

    staged_diff = subprocess.run(
        ["git", "diff", "--cached"],
        cwd=root_dir,
        capture_output=True,
        text=True,
    )
    if staged_diff.returncode == 0 and staged_diff.stdout:
        sec_violations.extend(scan_diff(staged_diff.stdout, threshold=threshold))

    staged_names = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=root_dir,
        capture_output=True,
        text=True,
    )
    if staged_names.returncode == 0 and staged_names.stdout:
        for rel_file in staged_names.stdout.splitlines():
            f_name = Path(rel_file.strip()).name
            if is_sensitive_dotfile(f_name):
                dot_violations.append(
                    DotfileViolation(
                        file_path=rel_file.strip(),
                        action_instructions=f"Action: Remove staged '{rel_file.strip()}' and add to .gitignore.",
                    )
                )

    return sec_violations, dot_violations


def scan_worktree(
    root_dir: Path,
    staged_only: bool = False,
    threshold: float | None = None,
) -> SecretScanReport:
    """Scans worktree changes (staged or full worktree diffs) for credentials."""
    is_git_repo = (root_dir / ".git").exists()

    if staged_only and is_git_repo:
        sec_list, dot_list = _scan_staged_git(root_dir, threshold=threshold)
        return SecretScanReport(secret_violations=sec_list, dotfile_violations=dot_list)

    dotfile_violations = scan_dotfiles(root_dir)
    secret_violations: list[SecretViolation] = []

    if is_git_repo:
        diff_cmd = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=root_dir,
            capture_output=True,
            text=True,
        )
        if diff_cmd.returncode == 0 and diff_cmd.stdout:
            secret_violations.extend(scan_diff(diff_cmd.stdout, threshold=threshold))
        else:
            staged = subprocess.run(["git", "diff", "--cached"], cwd=root_dir, capture_output=True, text=True)
            if staged.returncode == 0 and staged.stdout:
                secret_violations.extend(scan_diff(staged.stdout, threshold=threshold))
            unstaged = subprocess.run(["git", "diff"], cwd=root_dir, capture_output=True, text=True)
            if unstaged.returncode == 0 and unstaged.stdout:
                secret_violations.extend(scan_diff(unstaged.stdout, threshold=threshold))

        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root_dir,
            capture_output=True,
            text=True,
        )
        if untracked.returncode == 0 and untracked.stdout:
            for rel_file in untracked.stdout.splitlines():
                f_path = root_dir / rel_file.strip()
                if f_path.is_file() and not any(part in EXCLUDED_SCAN_DIRS for part in f_path.parts):
                    try:
                        content = f_path.read_text(encoding="utf-8", errors="ignore")
                        secret_violations.extend(
                            scan_text(content, file_path=rel_file.strip(), threshold=threshold)
                        )
                    except OSError:
                        continue

        branch_check = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root_dir,
            capture_output=True,
            text=True,
        )
        curr_branch = branch_check.stdout.strip()
        if curr_branch and curr_branch != "main":
            main_check = subprocess.run(
                ["git", "rev-parse", "--verify", "main"],
                cwd=root_dir,
                capture_output=True,
            )
            if main_check.returncode == 0:
                branch_diff = subprocess.run(
                    ["git", "diff", "main...HEAD"],
                    cwd=root_dir,
                    capture_output=True,
                    text=True,
                )
                if branch_diff.returncode == 0 and branch_diff.stdout:
                    secret_violations.extend(scan_diff(branch_diff.stdout, threshold=threshold))
    else:
        for p in root_dir.rglob("*"):
            if not p.is_file() or any(part in EXCLUDED_SCAN_DIRS for part in p.parts):
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                rel = str(p.relative_to(root_dir))
                secret_violations.extend(scan_text(content, file_path=rel, threshold=threshold))
            except OSError:
                continue

    deduped_secrets: list[SecretViolation] = []
    seen_sec: set[tuple[str, int | None, str]] = set()
    for sv in secret_violations:
        key = (sv.file_path, sv.line_number, sv.masked_token)
        if key not in seen_sec:
            seen_sec.add(key)
            deduped_secrets.append(sv)

    return SecretScanReport(secret_violations=deduped_secrets, dotfile_violations=dotfile_violations)
