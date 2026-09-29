"""Worktree diff scanner for high-entropy credentials and sensitive files."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .entropy import is_high_entropy, mask_secret, shannon_entropy
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

EXCLUDED_SCAN_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "site",
    ".pytest_cache",
    ".hypothesis",
    "__pycache__",
    ".worktrees",
})


@dataclass
class SecretViolation:
    file_path: str
    line_number: int | None
    secret_type: str
    masked_token: str
    raw_snippet: str = ""


@dataclass
class DotfileViolation:
    file_path: str
    action_instructions: str


@dataclass
class SecretScanReport:
    secret_violations: list[SecretViolation] = field(default_factory=list)
    dotfile_violations: list[DotfileViolation] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.secret_violations) == 0 and len(self.dotfile_violations) == 0

    def format_diagnostics(self) -> str:
        lines: list[str] = []
        if self.dotfile_violations:
            for dv in self.dotfile_violations:
                lines.append(f"❌ Unignored sensitive file detected: {dv.file_path}")
                lines.append(f"   {dv.action_instructions}")
        if self.secret_violations:
            for sv in self.secret_violations:
                loc = f"{sv.file_path}:{sv.line_number}" if sv.line_number is not None else sv.file_path
                lines.append(f"❌ High-entropy secret or credential leak detected at {loc}")
                lines.append(f"   Type: {sv.secret_type}")
                lines.append(f"   Masked Snippet: {sv.masked_token}")
        return "\n".join(lines)


def scan_line(line: str, line_number: int | None = None, file_path: str = "") -> list[SecretViolation]:
    """Scans a single source line for hardcoded secrets, API keys, and high-entropy tokens."""
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
    for m in AWS_SECRET_KEY_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens and is_high_entropy(token, threshold=3.5, min_length=30):
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
    for m in ASSIGNMENT_CANDIDATE_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens and is_high_entropy(token, threshold=3.6, min_length=16):
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="High-Entropy Credential Assignment",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    # 8. Standalone Quoted High-Entropy Token (length >= 32, entropy >= 4.2)
    for m in QUOTED_TOKEN_PATTERN.finditer(line):
        token = m.group(1)
        if token not in seen_tokens and is_high_entropy(token, threshold=4.2, min_length=32):
            violations.append(SecretViolation(
                file_path=file_path,
                line_number=line_number,
                secret_type="High-Entropy Secret Literal",
                masked_token=mask_secret(token),
                raw_snippet=line.strip(),
            ))
            seen_tokens.add(token)

    return violations


def scan_text(text: str, file_path: str = "") -> list[SecretViolation]:
    """Scans multi-line source text for hardcoded secrets and credentials."""
    violations: list[SecretViolation] = []
    for line_idx, line in enumerate(text.splitlines(), start=1):
        violations.extend(scan_line(line, line_number=line_idx, file_path=file_path))
    return violations


def scan_diff(diff_text: str) -> list[SecretViolation]:
    """Parses unified git diff output and scans newly added lines for credentials."""
    violations: list[SecretViolation] = []
    current_file = ""
    current_line = 0

    hunk_header_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git"):
            # Reset
            current_line = 0
        elif raw_line.startswith("+++ b/"):
            current_file = raw_line[6:].strip()
        elif raw_line.startswith("@@"):
            m = hunk_header_re.match(raw_line)
            if m:
                current_line = int(m.group(1))
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            added_content = raw_line[1:]
            violations.extend(scan_line(added_content, line_number=current_line, file_path=current_file))
            current_line += 1
        elif raw_line.startswith(" "):
            current_line += 1

    return violations


def scan_dotfiles(root_dir: Path) -> list[DotfileViolation]:
    """Identifies sensitive dotfiles and private keys that are not ignored by .gitignore."""
    violations: list[DotfileViolation] = []
    is_git_repo = (root_dir / ".git").exists()

    for p in root_dir.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDED_SCAN_DIRS for part in p.parts):
            continue
        if not is_sensitive_dotfile(p.name):
            continue

        rel_path = p.relative_to(root_dir)

        if is_git_repo:
            chk = subprocess.run(
                ["git", "check-ignore", "-q", str(rel_path)],
                cwd=root_dir,
                capture_output=True,
            )
            # If returncode != 0, it is NOT ignored in .gitignore
            if chk.returncode != 0:
                instructions = f"Action: Add '{rel_path}' to .gitignore and remove it from git staging."
                violations.append(DotfileViolation(file_path=str(rel_path), action_instructions=instructions))
            else:
                # Even if ignored, check if it's already tracked in git staging
                tracked = subprocess.run(
                    ["git", "ls-files", str(rel_path)],
                    cwd=root_dir,
                    capture_output=True,
                    text=True,
                )
                if tracked.stdout.strip():
                    instructions = f"Action: Remove tracked '{rel_path}' from git staging."
                    violations.append(DotfileViolation(file_path=str(rel_path), action_instructions=instructions))
        else:
            gitignore_path = root_dir / ".gitignore"
            ignored = False
            if gitignore_path.exists():
                gi_content = gitignore_path.read_text(encoding="utf-8")
                if p.name in gi_content:
                    ignored = True
            if not ignored:
                instructions = f"Action: Add '{rel_path}' to .gitignore."
                violations.append(DotfileViolation(file_path=str(rel_path), action_instructions=instructions))

    return violations


def scan_worktree(root_dir: Path) -> SecretScanReport:
    """Scans worktree changes (unstaged, staged, untracked, and branch diffs) for credentials."""
    dotfile_violations = scan_dotfiles(root_dir)
    secret_violations: list[SecretViolation] = []

    is_git_repo = (root_dir / ".git").exists()

    if is_git_repo:
        # 1. Unstaged + staged diff vs HEAD
        diff_cmd = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=root_dir,
            capture_output=True,
            text=True,
        )
        if diff_cmd.returncode == 0 and diff_cmd.stdout:
            secret_violations.extend(scan_diff(diff_cmd.stdout))
        else:
            # If repo has no commits yet (initial worktree), diff against empty tree or staged diff
            staged = subprocess.run(["git", "diff", "--cached"], cwd=root_dir, capture_output=True, text=True)
            if staged.returncode == 0 and staged.stdout:
                secret_violations.extend(scan_diff(staged.stdout))
            unstaged = subprocess.run(["git", "diff"], cwd=root_dir, capture_output=True, text=True)
            if unstaged.returncode == 0 and unstaged.stdout:
                secret_violations.extend(scan_diff(unstaged.stdout))

        # 2. Untracked files that are not ignored
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
                        secret_violations.extend(scan_text(content, file_path=rel_file.strip()))
                    except OSError:
                        continue

        # 3. Branch diff against main if HEAD is on a feature branch
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
                    secret_violations.extend(scan_diff(branch_diff.stdout))
    else:
        for p in root_dir.rglob("*"):
            if not p.is_file():
                continue
            if any(part in EXCLUDED_SCAN_DIRS for part in p.parts):
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                rel = str(p.relative_to(root_dir))
                secret_violations.extend(scan_text(content, file_path=rel))
            except OSError:
                continue

    # Deduplicate secret violations by file_path, line_number, masked_token
    deduped_secrets: list[SecretViolation] = []
    seen_sec: set[tuple[str, int | None, str]] = set()
    for sv in secret_violations:
        key = (sv.file_path, sv.line_number, sv.masked_token)
        if key not in seen_sec:
            seen_sec.add(key)
            deduped_secrets.append(sv)

    return SecretScanReport(secret_violations=deduped_secrets, dotfile_violations=dotfile_violations)
