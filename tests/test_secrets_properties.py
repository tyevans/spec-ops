"""Generative property-based tests using Hypothesis for secret detection and entropy invariants."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from spec_ops.security.secrets.entropy import is_high_entropy, mask_secret, shannon_entropy
from spec_ops.security.secrets.scanner import scan_text


@given(text=st.text())
def test_property_shannon_entropy_unicode_bounds(text: str):
    """Mathematical Invariant: Shannon entropy is strictly bounded in [0.0, 8.0] for any text."""
    entropy = shannon_entropy(text)
    assert 0.0 <= entropy <= 8.0


@given(data=st.binary())
def test_property_shannon_entropy_binary_bounds(data: bytes):
    """Mathematical Invariant: Shannon entropy is strictly bounded in [0.0, 8.0] for any binary stream."""
    entropy = shannon_entropy(data)
    assert 0.0 <= entropy <= 8.0


@given(
    data=st.binary(min_size=1),
    byte_val=st.integers(min_value=0, max_value=255),
)
def test_property_shannon_entropy_monotonous_zero_for_uniform_single_byte(data: bytes, byte_val: int):
    """Entropy Invariant: A sequence of identical bytes always has entropy 0.0."""
    uniform = bytes([byte_val] * len(data))
    assert shannon_entropy(uniform) == 0.0


@given(text=st.text())
def test_property_mask_secret_robustness(text: str):
    """Masking Robustness Invariant: mask_secret never crashes and always contains asterisks for non-empty text."""
    masked = mask_secret(text)
    assert isinstance(masked, str)
    if text:
        assert "****" in masked


@given(text=st.text())
def test_property_scanner_robustness_on_arbitrary_streams(text: str):
    """Scanner Robustness Invariant: scan_text handles arbitrary unicode, null bytes, and symbols without crashing."""
    violations = scan_text(text, file_path="test_stream.txt")
    assert isinstance(violations, list)
    for v in violations:
        assert v.file_path == "test_stream.txt"
        assert isinstance(v.masked_token, str)
        assert isinstance(v.secret_type, str)
