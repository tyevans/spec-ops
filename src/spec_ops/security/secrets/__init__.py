"""Secret and high-entropy credential detection package."""

from .entropy import is_high_entropy, mask_secret, shannon_entropy
from .patterns import is_sensitive_dotfile
from .scanner import (
    DotfileViolation,
    SecretScanReport,
    SecretViolation,
    scan_diff,
    scan_dotfiles,
    scan_line,
    scan_text,
    scan_worktree,
)

__all__ = [
    "DotfileViolation",
    "SecretScanReport",
    "SecretViolation",
    "is_high_entropy",
    "is_sensitive_dotfile",
    "mask_secret",
    "scan_diff",
    "scan_dotfiles",
    "scan_line",
    "scan_text",
    "scan_worktree",
    "shannon_entropy",
]
