"""Automated Conventional Commit RFC-822 Trailer Sanitizer and Signer Pre-Gate.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0014, ADR-0016; PRD-0002; US-0113; TASK-0168.
Target Bounded Context: security. File length strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
import subprocess
from typing import Any

from ..config.models import SpecOpsConfig

CONVENTIONAL_COMMIT_PATTERN = re.compile(
    r"^(feat|fix|refactor|docs|test|chore|perf|style|ci|spike|build)"
    r"(\([a-zA-Z0-9_\-\.\/]+\))?!?: (.+)$"
)


def parse_rfc822_trailers(message: str) -> dict[str, str]:
    """Extracts RFC-822 compliant git commit trailers, including folded continuation lines."""
    trailers: dict[str, str] = {}
    lines = message.strip().splitlines()
    current_key: str | None = None

    for line in lines:
        if not line.strip():
            continue
        # Check continuation line (starts with space or tab)
        if current_key and (line.startswith(" ") or line.startswith("\t")):
            trailers[current_key] += " " + line.strip()
            continue

        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9_-]*)\s*:\s*(.+)$", line.strip())
        if m:
            key, val = m.group(1), m.group(2).strip()
            trailers[key] = val
            current_key = key
        else:
            current_key = None

    return trailers


@dataclass
class CommitValidationResult:
    """Detailed validation outcome for a single git commit message and its trailers."""

    commit_hash: str
    subject: str
    is_valid: bool
    conventional_valid: bool
    trailers: dict[str, str]
    missing_trailers: list[str] = field(default_factory=list)
    unresolved_references: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TrailerSanitizer:
    """Validates Conventional Commit formatting and RFC-822 SpecOps traceability trailers."""

    REQUIRED_TRAILERS = ["SpecOps-Task"]

    def __init__(self, root_dir: Path | None = None, strict: bool = False) -> None:
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.strict = strict
        self.docs_dir = self.root_dir / "docs" / "project"

    def _entity_exists(self, prefix: str, entity_id: str) -> bool:
        """Verifies if referenced entity file exists in docs/project/."""
        if not self.docs_dir.exists():
            return True
        clean_num = re.search(r"\d+", entity_id)
        if not clean_num:
            return True
        num_str = f"{int(clean_num.group(0)):04d}"

        subdirs = {
            "TASK": ["backlog"],
            "US": ["user_stories"],
            "PRD": ["product"],
            "ADR": ["adrs"],
        }
        dirs = subdirs.get(prefix.upper(), [])
        for d in dirs:
            target_path = self.docs_dir / d
            if target_path.exists():
                for p in target_path.rglob("*.md"):
                    if num_str in p.name or entity_id.lower() in p.name.lower():
                        return True
        return False

    def validate_commit_message(
        self,
        message: str,
        commit_hash: str = "HEAD",
    ) -> CommitValidationResult:
        """Evaluates commit subject format and RFC-822 trailers for a single commit."""
        clean_msg = message.strip()
        if not clean_msg:
            return CommitValidationResult(
                commit_hash=commit_hash[:8],
                subject="",
                is_valid=False,
                conventional_valid=False,
                trailers={},
                errors=["Commit message is empty."],
            )

        lines = clean_msg.splitlines()
        subject = lines[0].strip()
        conv_match = bool(CONVENTIONAL_COMMIT_PATTERN.match(subject))

        errors: list[str] = []
        warnings: list[str] = []
        missing_trailers: list[str] = []
        unresolved: list[str] = []

        if not conv_match:
            errors.append(f"Subject '{subject}' does not conform to Conventional Commits format 'type(scope): subject'.")

        trailers = parse_rfc822_trailers(clean_msg)

        # Check required trailers
        for req in self.REQUIRED_TRAILERS:
            if req not in trailers or not trailers[req].strip():
                missing_trailers.append(req)
                msg = f"Missing required trailer '{req}'."
                if self.strict:
                    errors.append(msg)
                else:
                    errors.append(msg)

        # Cross-reference entities
        for key, val in trailers.items():
            if key == "SpecOps-Task":
                for tid in [t.strip() for t in val.split(",") if t.strip()]:
                    if not self._entity_exists("TASK", tid):
                        unresolved.append(f"Task {tid}")
            elif key == "SpecOps-Story":
                for sid in [s.strip() for s in val.split(",") if s.strip()]:
                    if not self._entity_exists("US", sid):
                        unresolved.append(f"Story {sid}")
            elif key == "SpecOps-PRD":
                for pid in [p.strip() for p in val.split(",") if p.strip()]:
                    if not self._entity_exists("PRD", pid):
                        unresolved.append(f"PRD {pid}")
            elif key == "SpecOps-ADR":
                for aid in [a.strip() for a in val.split(",") if a.strip()]:
                    if not self._entity_exists("ADR", aid):
                        unresolved.append(f"ADR {aid}")

        if unresolved:
            unresolved_msg = f"Unresolved entity references: {', '.join(unresolved)}."
            if self.strict:
                errors.append(unresolved_msg)
            else:
                warnings.append(unresolved_msg)

        is_valid = len(errors) == 0

        return CommitValidationResult(
            commit_hash=commit_hash[:8],
            subject=subject,
            is_valid=is_valid,
            conventional_valid=conv_match,
            trailers=trailers,
            missing_trailers=missing_trailers,
            unresolved_references=unresolved,
            errors=errors,
            warnings=warnings,
        )

    def get_commits_in_range(self, rev_range: str = "main..HEAD") -> list[tuple[str, str]]:
        """Retrieves list of (commit_hash, full_message) within given git revision range."""
        cmd = ["git", "log", rev_range, "--format=%H%x00%B%x00"]
        try:
            res = subprocess.run(
                cmd,
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                # Fallback to single HEAD commit if range invalid
                res = subprocess.run(
                    ["git", "log", "-1", "--format=%H%x00%B%x00"],
                    cwd=self.root_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            output = res.stdout
        except Exception:
            return []

        commits: list[tuple[str, str]] = []
        tokens = output.split("\x00")
        for i in range(0, len(tokens) - 1, 2):
            chash = tokens[i].strip()
            cmsg = tokens[i + 1].strip() if i + 1 < len(tokens) else ""
            if chash:
                commits.append((chash, cmsg))
        return commits

    def validate_range(self, rev_range: str = "main..HEAD") -> tuple[bool, list[CommitValidationResult]]:
        """Validates all commits in given revision range."""
        commits = self.get_commits_in_range(rev_range)
        results: list[CommitValidationResult] = []
        all_valid = True

        for chash, cmsg in commits:
            res = self.validate_commit_message(cmsg, commit_hash=chash)
            if not res.is_valid:
                all_valid = False
            results.append(res)

        return all_valid, results
