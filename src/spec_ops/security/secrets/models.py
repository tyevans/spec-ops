"""Data models for secret scanning and credential violation reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_clean": self.is_clean,
            "secret_violations": [
                {
                    "file_path": sv.file_path,
                    "line_number": sv.line_number,
                    "secret_type": sv.secret_type,
                    "masked_token": sv.masked_token,
                    "raw_snippet": sv.raw_snippet,
                }
                for sv in self.secret_violations
            ],
            "dotfile_violations": [
                {
                    "file_path": dv.file_path,
                    "action_instructions": dv.action_instructions,
                }
                for dv in self.dotfile_violations
            ],
            "violations_count": len(self.secret_violations) + len(self.dotfile_violations),
        }
