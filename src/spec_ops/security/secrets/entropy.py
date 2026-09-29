"""Shannon entropy computation and token masking utilities."""

from __future__ import annotations

import collections
import math


def shannon_entropy(data: str | bytes) -> float:
    """Computes Shannon entropy in bits per byte for arbitrary text or binary data.

    Returns a value bounded strictly in [0.0, 8.0].
    """
    if isinstance(data, str):
        raw_bytes = data.encode("utf-8", errors="surrogateescape")
    else:
        raw_bytes = bytes(data)

    total_len = len(raw_bytes)
    if total_len == 0:
        return 0.0

    counts = collections.Counter(raw_bytes)
    entropy = 0.0
    for count in counts.values():
        prob = count / total_len
        entropy -= prob * math.log2(prob)

    # pragma: no mutate start
    if entropy < 0.0:
        return 0.0
    if entropy > 8.0:
        return 8.0
    # pragma: no mutate end
    return entropy


def is_high_entropy(token: str, threshold: float = 3.7, min_length: int = 16) -> bool:
    """Evaluates whether a string token exhibits high Shannon entropy above threshold."""
    if len(token) < min_length:
        return False
    return shannon_entropy(token) >= threshold


def mask_secret(token: str) -> str:
    """Safely masks a secret string to produce diagnostic feedback for self-healing."""
    if not token:
        return "****"

    if token.startswith("sk-proj-"):
        suffix = token[-4:] if len(token) >= 12 else ""
        return f"sk-proj-****{suffix}"

    if token.startswith("sk-ant-"):
        suffix = token[-4:] if len(token) >= 11 else ""
        return f"sk-ant-****{suffix}"

    if token.startswith("sk-"):
        suffix = token[-4:] if len(token) >= 7 else ""
        return f"sk-****{suffix}"

    if token.startswith("ghp_") or token.startswith("github_pat_"):
        prefix = token[:4]
        suffix = token[-4:] if len(token) >= 12 else ""
        return f"{prefix}****{suffix}"

    if token.startswith("AKIA"):
        prefix = "AKIA"
        suffix = token[-4:] if len(token) >= 8 else ""
        return f"{prefix}****{suffix}"

    if token.startswith("-----BEGIN"):
        return f"{token[:28]}****"

    if len(token) >= 12:
        return f"{token[:4]}****{token[-4:]}"
    elif len(token) >= 8:
        return f"{token[:2]}****{token[-2:]}"
    return "****"
