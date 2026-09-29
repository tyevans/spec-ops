"""Credential signature patterns and sensitive dotfile definitions."""

from __future__ import annotations

import re

# pragma: no mutate start
OPENAI_KEY_PATTERN = re.compile(
    r"\b(sk-(?:proj-|ant-)?[a-zA-Z0-9_-]{20,})\b"
)

AWS_ACCESS_KEY_ID_PATTERN = re.compile(
    r"\b(AKIA[0-9A-Z]{16})\b"
)

AWS_SECRET_KEY_PATTERN = re.compile(
    r"(?i)(?:aws_secret_access_key|aws_secret_key|aws_access_secret)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"
)

GITHUB_TOKEN_PATTERN = re.compile(
    r"\b(gh[pousr]_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{22,255})\b"
)

SLACK_TOKEN_PATTERN = re.compile(
    r"\b(xox[baprs]-[0-9a-zA-Z]{10,48})\b"
)

PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"
)

ASSIGNMENT_CANDIDATE_PATTERN = re.compile(
    r"(?i)(?:secret|token|api_key|apikey|password|credential|access_key|auth_token)\s*[:=]\s*['\"]([^'\"]{16,})['\"]"
)

QUOTED_TOKEN_PATTERN = re.compile(
    r"['\"]([A-Za-z0-9/+=_-]{20,})['\"]"
)

SENSITIVE_DOTFILE_NAMES = frozenset({
    ".env",
    ".env.production",
    ".env.local",
    ".env.development",
    ".env.staging",
    ".env.test",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
})

EXCLUDED_DOTFILE_SUFFIXES = (
    ".example",
    ".sample",
    ".template",
    ".dist",
    ".pub",
)
# pragma: no mutate end


def is_sensitive_dotfile(filename: str) -> bool:
    """Checks whether a given file name corresponds to a sensitive dotfile or private key."""
    if filename in SENSITIVE_DOTFILE_NAMES:
        return True

    for excluded in EXCLUDED_DOTFILE_SUFFIXES:
        if filename.endswith(excluded):
            return False

    if filename.startswith(".env."):
        return True

    if filename.startswith("id_rsa") or filename.startswith("id_ed25519") or filename.startswith("id_ecdsa"):
        return True

    return False
