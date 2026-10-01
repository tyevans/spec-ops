"""Hypothesis property tests for Shannon entropy secret scanner rule plugin engine."""

from __future__ import annotations

import math
import random
import re
import string
import uuid
from hypothesis import given
from hypothesis import strategies as st

from spec_ops.security.entropy_plugins import (
    EntropyRule,
    EntropyScannerConfig,
    ShannonEntropyScanner,
    calculate_entropy,
)

ALPHANUM = string.ascii_letters + string.digits
BASE64_ALPHABET = string.ascii_letters + string.digits + "+/="


@given(text=st.text())
def test_property_calculate_entropy_bounded_and_finite(text: str):
    """Mathematical Invariant: Shannon entropy is non-negative, finite, and bounded by log2(len(set(text))) <= 8.0."""
    entropy = calculate_entropy(text)

    # 1. Non-negative
    assert entropy >= 0.0, f"Entropy was negative: {entropy}"

    # 2. Finite
    assert math.isfinite(entropy), f"Entropy was not finite: {entropy}"

    # 3. Bounded by 8.0
    assert entropy <= 8.0, f"Entropy exceeded 8.0 bits: {entropy}"

    # 4. Bounded strictly by log2(len(set(text)))
    unique_count = len(set(text))
    if unique_count <= 1:
        assert entropy == 0.0, f"Expected 0.0 for uniform/empty text, got {entropy}"
    else:
        max_bound = math.log2(unique_count)
        assert entropy <= max_bound + 1e-9, f"Entropy {entropy} exceeded theoretical max {max_bound}"


@given(char=st.characters(), count=st.integers(min_value=1, max_value=500))
def test_property_uniform_repetition_zero_entropy(char: str, count: int):
    """Invariant: A string composed entirely of a single repeated character has entropy 0.0."""
    text = char * count
    assert calculate_entropy(text) == 0.0


@given(text=st.text(min_size=1, max_size=200))
def test_property_permutation_invariance(text: str):
    """Invariant: Permuting character order in text does not change its Shannon entropy."""
    chars = list(text)
    random.shuffle(chars)
    shuffled = "".join(chars)
    e1 = calculate_entropy(text)
    e2 = calculate_entropy(shuffled)
    assert math.isclose(e1, e2, rel_tol=1e-9, abs_tol=1e-9)


@given(u=st.uuids())
def test_property_uuid_ignoring_when_configured(u: uuid.UUID):
    """Invariant: Valid UUIDs are reliably ignored when ignore_uuids is enabled."""
    uuid_str = str(u)
    config = EntropyScannerConfig(
        rules=[EntropyRule(name="test", threshold=1.0, min_length=10, alphabet_type="all")],
        ignore_uuids=True,
    )
    scanner = ShannonEntropyScanner(config)
    assert scanner.is_ignored(uuid_str) is True

    # When ignore_uuids is False, it is not ignored by UUID filter
    config_strict = EntropyScannerConfig(
        rules=[EntropyRule(name="test", threshold=1.0, min_length=10, alphabet_type="all")],
        ignore_uuids=False,
        ignore_shas=False,
    )
    scanner_strict = ShannonEntropyScanner(config_strict)
    assert scanner_strict.is_ignored(uuid_str) is False


@given(sha_len=st.sampled_from([40, 64]), hex_chars=st.text(alphabet="0123456789abcdef", min_size=64, max_size=64))
def test_property_sha_ignoring_when_configured(sha_len: int, hex_chars: str):
    """Invariant: Standard Git SHA-1 and SHA-256 strings are ignored when ignore_shas is enabled."""
    sha_str = hex_chars[:sha_len]
    config = EntropyScannerConfig(
        rules=[EntropyRule(name="test", threshold=1.0, min_length=10, alphabet_type="all")],
        ignore_shas=True,
    )
    scanner = ShannonEntropyScanner(config)
    assert scanner.is_ignored(sha_str) is True

    config_strict = EntropyScannerConfig(
        rules=[EntropyRule(name="test", threshold=1.0, min_length=10, alphabet_type="all")],
        ignore_shas=False,
        ignore_uuids=False,
    )
    scanner_strict = ShannonEntropyScanner(config_strict)
    assert scanner_strict.is_ignored(sha_str) is False


@given(
    token=st.text(alphabet=ALPHANUM, min_size=20, max_size=40),
    pragma=st.sampled_from([
        "# pragma: allowlist secret",
        "# pragma:allowlist secret",
        "# spec-ops:ignore-secret",
        "// pragma: allowlist secret",
    ]),
)
def test_property_pragma_same_line_and_previous_line_immunity(token: str, pragma: str):
    """Invariant: Pragma secret allowlist markers prevent any findings on the current or subsequent line."""
    scanner = ShannonEntropyScanner(
        EntropyScannerConfig(
            rules=[EntropyRule(name="catch-all", threshold=0.1, min_length=10, alphabet_type="all")]
        )
    )

    # 1. Same line pragma
    line_same = f'KEY = "{token}"  {pragma}\n'  # pragma: allowlist secret
    findings_same = scanner.scan_text(line_same)
    assert len(findings_same) == 0

    # 2. Previous line pragma
    text_prev = f"{pragma}\nKEY = \"{token}\"\n"  # pragma: allowlist secret
    findings_prev = scanner.scan_text(text_prev)
    assert len(findings_prev) == 0


@given(
    prefix=st.text(alphabet=string.ascii_letters, min_size=5, max_size=10),
    suffix=st.text(alphabet=ALPHANUM, min_size=20, max_size=30),
)
def test_property_allowlist_patterns_invariance(prefix: str, suffix: str):
    """Invariant: Tokens matching user-configured allowlist patterns are consistently ignored."""
    token = f"{prefix}_{suffix}"
    config = EntropyScannerConfig(
        rules=[EntropyRule(name="test", threshold=0.1, min_length=10, alphabet_type="all")],
        allowlist_patterns=[f"^{re.escape(prefix)}_.*"],
    )
    scanner = ShannonEntropyScanner(config)
    assert scanner.is_ignored(token) is True
    findings = scanner.scan_text(f'VAL = "{token}"\n')  # pragma: allowlist secret
    assert len(findings) == 0
