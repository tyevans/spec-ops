"""Generative property-based tests using Hypothesis for secret detection and entropy invariants."""

from __future__ import annotations

import string
from hypothesis import given
from hypothesis import strategies as st

from spec_ops.security.secrets.entropy import is_high_entropy, mask_secret, shannon_entropy
from spec_ops.security.secrets.scanner import scan_line, scan_text

# Character sets for high-entropy tokens
ALPHANUM = string.ascii_letters + string.digits
BASE64_CHARS = string.ascii_letters + string.digits + "/+="

# Strategies for generating secrets
openai_tokens = st.text(alphabet=ALPHANUM, min_size=20, max_size=50).map(lambda s: f"sk-proj-{s}")
aws_access_keys = st.text(alphabet=string.ascii_uppercase + string.digits, min_size=16, max_size=16).map(
    lambda s: f"AKIA{s}"
)
aws_secret_keys = st.text(alphabet=BASE64_CHARS, min_size=40, max_size=40).filter(
    lambda s: is_high_entropy(s, threshold=3.5, min_length=30)
)
ignore_directives = st.sampled_from([
    "# spec-ops:ignore-secret",
    "# spec-ops: ignore-secret",
    "# spec-ops:ignore_secret",
    "# pragma: allowlist secret",
    "# pragma:allowlist secret",
    "# pragma: allowlist-secret",
    "// spec-ops:ignore-secret",
    "// pragma: allowlist secret",
])


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


@given(token=openai_tokens)
def test_property_openai_secrets_strictly_detected(token: str):
    """Property Invariant: All generated valid OpenAI secret tokens are strictly detected."""
    line = f'OPENAI_API_KEY = "{token}"'
    violations = scan_line(line, line_number=1, file_path="config.py")
    assert len(violations) >= 1
    assert any(v.secret_type == "OpenAI/Anthropic API Key" for v in violations)


@given(key_id=aws_access_keys)
def test_property_aws_access_keys_strictly_detected(key_id: str):
    """Property Invariant: All generated valid AWS Access Key IDs are strictly detected."""
    line = f'aws_access_key_id = "{key_id}"'
    violations = scan_line(line, line_number=1, file_path="aws.py")
    assert len(violations) >= 1
    assert any(v.secret_type == "AWS Access Key ID" for v in violations)


@given(
    token=openai_tokens,
    directive=ignore_directives,
    prefix_space=st.text(alphabet=" \t", min_size=1, max_size=5),
)
def test_property_inline_ignores_strictly_honored_for_secrets(
    token: str,
    directive: str,
    prefix_space: str,
):
    """Property Invariant: Inline suppression directives strictly suppress secret violations."""
    line = f'api_key = "{token}"{prefix_space}{directive}'
    violations = scan_line(line, line_number=1, file_path="app.py")
    assert len(violations) == 0


@given(
    key_id=aws_access_keys,
    directive=ignore_directives,
)
def test_property_inline_ignores_honored_for_aws_keys(key_id: str, directive: str):
    """Property Invariant: Inline suppression directives suppress AWS Access Key violations."""
    line = f'export AWS_KEY="{key_id}" {directive}'
    violations = scan_line(line, line_number=5, file_path="deploy.sh")
    assert len(violations) == 0


@given(
    random_payload=st.text(alphabet=ALPHANUM, min_size=16, max_size=60),
    var_name=st.sampled_from(["secret", "token", "api_key", "password", "access_key"]),
    directive=ignore_directives,
)
def test_property_inline_ignores_honored_across_randomized_payloads(
    random_payload: str,
    var_name: str,
    directive: str,
):
    """Property Invariant: Inline suppression directives suppress any credential assignment."""
    line = f'{var_name} = "{random_payload}"  {directive}'
    violations = scan_line(line, line_number=42, file_path="settings.py")
    assert len(violations) == 0


@given(text=st.text())
def test_property_scanner_robustness_on_arbitrary_streams(text: str):
    """Scanner Robustness Invariant: scan_text handles arbitrary unicode, null bytes, and symbols without crashing."""
    violations = scan_text(text, file_path="test_stream.txt")
    assert isinstance(violations, list)
    for v in violations:
        assert v.file_path == "test_stream.txt"
        assert isinstance(v.masked_token, str)
        assert isinstance(v.secret_type, str)
