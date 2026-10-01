"""Hypothesis generative property tests for zero-trust worker process sandboxing (ADR-0009)."""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.worker.sandbox_env import (
    APPROVED_COMMAND_PREFIXES,
    DEFAULT_TOOLCHAIN_ENV_VARS,
    SENSITIVE_KEYWORDS,
    SENSITIVE_PREFIXES,
    is_command_approved,
    is_sensitive_key,
    is_sensitive_value,
    sanitize_environment,
)

env_key_strategy = st.text(
    alphabet=st.characters(whitelist_categories=["Lu", "Ll", "Nd", "Pc", "Pd"], min_codepoint=32, max_codepoint=126),
    min_size=1,
    max_size=50,
)

env_val_strategy = st.text(
    min_size=0,
    max_size=200,
)

arbitrary_env_strategy = st.dictionaries(
    keys=env_key_strategy,
    values=env_val_strategy,
    max_size=30,
)


@given(env=arbitrary_env_strategy)
@settings(max_examples=100)
def test_arbitrary_dict_sanitization_deterministic_and_safe(env: dict[str, str]):
    """Sanitizing any arbitrary dictionary deterministically retains exclusively allowlisted, non-sensitive entries."""
    res = sanitize_environment(env)

    # 1. Result must be a dictionary
    assert isinstance(res, dict)

    # 2. Exclusively allowlisted entries
    for k in res.keys():
        assert k in DEFAULT_TOOLCHAIN_ENV_VARS

    # 3. No sensitive keys ever survive
    for k in res.keys():
        assert not is_sensitive_key(k)

    # 4. No sensitive/secret values survive
    for k, v in res.items():
        assert not is_sensitive_value(v, is_path=(k == "PATH"))

    # 5. Determinism: identical input yields identical output
    res2 = sanitize_environment(env)
    assert res == res2

    # 6. Idempotence: re-sanitizing output is a no-op
    res3 = sanitize_environment(res)
    assert res3 == res


@given(
    prefix=st.sampled_from(SENSITIVE_PREFIXES),
    suffix=st.text(min_size=1, max_size=20),
    value=st.text(min_size=1, max_size=50),
)
@settings(max_examples=50)
def test_sensitive_prefixes_always_filtered(prefix: str, suffix: str, value: str):
    """Variables with sensitive prefixes are stripped even if explicitly added to allowed_vars."""
    sensitive_key = f"{prefix}{suffix}"
    env = {sensitive_key: value, "USER": "safe_user"}
    res = sanitize_environment(env, allowed_vars=[sensitive_key, "USER"])
    assert sensitive_key not in res
    assert res.get("USER") == "safe_user"


@given(
    keyword=st.sampled_from(SENSITIVE_KEYWORDS),
    prefix=st.text(min_size=0, max_size=10),
    suffix=st.text(min_size=0, max_size=10),
    value=st.text(min_size=1, max_size=50),
)
@settings(max_examples=50)
def test_sensitive_keywords_always_filtered(keyword: str, prefix: str, suffix: str, value: str):
    """Variables with sensitive keywords anywhere in the key are stripped."""
    sensitive_key = f"{prefix}_{keyword}_{suffix}"
    env = {sensitive_key: value, "LANG": "en_US.UTF-8"}
    res = sanitize_environment(env, allowed_vars=[sensitive_key, "LANG"])
    assert sensitive_key not in res
    assert res.get("LANG") == "en_US.UTF-8"


@given(
    key=st.sampled_from(["HOME", "USER", "LANG", "TERM", "VIRTUAL_ENV"]),
    secret_prefix=st.sampled_from(["sk-proj-", "ghp_", "AKIA"]),
    secret_suffix=st.text(
        alphabet=string.ascii_letters + string.digits,
        min_size=25,
        max_size=40,
    ),
)
@settings(max_examples=50)
def test_high_entropy_secret_values_always_filtered(key: str, secret_prefix: str, secret_suffix: str):
    """Allowlisted keys containing high-entropy secret patterns are stripped."""
    secret_val = f"{secret_prefix}{secret_suffix}"
    env = {key: secret_val}
    res = sanitize_environment(env)
    assert key not in res


@given(
    approved_prefix=st.sampled_from(APPROVED_COMMAND_PREFIXES),
    extra_args=st.lists(
        st.text(alphabet=string.ascii_lowercase + string.digits + "_-", min_size=1, max_size=15),
        max_size=4,
    ),
)
@settings(max_examples=50)
def test_approved_commands_validation_property(approved_prefix: str, extra_args: list[str]):
    """Commands starting with approved prefixes pass validation without exception."""
    cmd = [approved_prefix] + extra_args
    is_ok, reason, bin_name = is_command_approved(cmd)
    assert is_ok is True
    assert bin_name is None
