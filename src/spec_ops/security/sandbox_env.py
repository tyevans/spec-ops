"""Zero-trust autonomous worker process sandboxing and environment scrubbing engine.

Governed by ADR-0007, ADR-0010, ADR-0021.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from .secrets.entropy import is_high_entropy
from .secrets.patterns import (
    AWS_ACCESS_KEY_ID_PATTERN,
    AWS_SECRET_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    OPENAI_KEY_PATTERN,
    PRIVATE_KEY_PATTERN,
    SLACK_TOKEN_PATTERN,
)

DEFAULT_TOOLCHAIN_ENV_VARS: frozenset[str] = frozenset({
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "TERM",
    "VIRTUAL_ENV",
})

SENSITIVE_PREFIXES: tuple[str, ...] = (
    "AWS_",
    "GITHUB_",
    "OPENAI_",
)

SENSITIVE_KEYWORDS: tuple[str, ...] = (
    "TOKEN",
    "KEY",
    "SECRET",
    "PASSWORD",
)

SECRET_PATTERNS = (
    OPENAI_KEY_PATTERN,
    AWS_ACCESS_KEY_ID_PATTERN,
    AWS_SECRET_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    SLACK_TOKEN_PATTERN,
    PRIVATE_KEY_PATTERN,
)

TOKEN_VALUE_PREFIXES: tuple[str, ...] = (
    "sk-",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "github_pat_",
    "AKIA",
    "xoxb-",
    "xoxa-",
    "xoxp-",
    "xoxr-",
    "xoxs-",
)


def is_sensitive_key(key: Any) -> bool:
    """Detects if an environment variable key matches sensitive prefixes or keywords."""
    if not isinstance(key, str):
        key = str(key)
    k_upper = key.upper()
    if any(k_upper.startswith(prefix) for prefix in SENSITIVE_PREFIXES):
        return True
    if any(keyword in k_upper for keyword in SENSITIVE_KEYWORDS):
        return True
    return False


def is_sensitive_value(value: Any, is_path: bool = False) -> bool:
    """Detects if an environment variable value matches high-entropy secret patterns."""
    if not isinstance(value, str):
        value = str(value)

    # Check known secret value prefixes
    if any(value.startswith(p) for p in TOKEN_VALUE_PREFIXES):
        return True

    # Check known secret regex signatures
    if any(p.search(value) for p in SECRET_PATTERNS):
        return True

    # For PATH, check each path component individually
    if is_path:
        for component in value.split(":"):
            if component and (
                any(component.startswith(p) for p in TOKEN_VALUE_PREFIXES)
                or any(p.search(component) for p in SECRET_PATTERNS)
            ):
                return True
        return False

    # Check Shannon entropy for tokens of length >= 16
    return is_high_entropy(value, threshold=3.7, min_length=16)


def sanitize_environment(
    env: Mapping[Any, Any] | None = None,
    allowed_vars: Iterable[str] | None = None,
    extra_allowed: Iterable[str] | None = None,
) -> dict[str, str]:
    """Sanitizes an environment dictionary according to zero-trust scrubbing rules.

    - Deterministically retains exclusively allowlisted variables.
    - Strips all keys matching sensitive prefixes (AWS_, GITHUB_, OPENAI_, TOKEN, KEY, SECRET, PASSWORD).
    - Strips all values exhibiting high-entropy secret patterns or signatures.
    - Never raises exceptions on arbitrary input keys or values.
    """
    if env is None:
        source_env: Mapping[Any, Any] = os.environ
    else:
        source_env = env

    effective_allowed = set(allowed_vars if allowed_vars is not None else DEFAULT_TOOLCHAIN_ENV_VARS)
    if extra_allowed:
        effective_allowed.update(extra_allowed)

    sanitized: dict[str, str] = {}

    try:
        items = list(source_env.items())
    except Exception:
        return sanitized

    for raw_k, raw_v in items:
        try:
            k = str(raw_k)
            v = str(raw_v)
        except Exception:
            continue

        # 1. Enforce allowlist
        if k not in effective_allowed:
            continue

        # 2. Reject sensitive key patterns
        if is_sensitive_key(k):
            continue

        # 3. Reject high-entropy secret values
        is_path_var = (k == "PATH")
        if is_sensitive_value(v, is_path=is_path_var):
            continue

        sanitized[k] = v

    return sanitized
