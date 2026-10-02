"""Hypothesis property tests for Commit Attestation and Keyring Validator."""

from __future__ import annotations

from hypothesis import given, strategies as st

from spec_ops.security.commit_attestation import (
    ParsedCommitObject,
    evaluate_commit_signature,
    parse_commit_object,
)


@given(content=st.text(max_size=3000))
def test_property_parse_commit_object_resilient(content: str) -> None:
    """Invariant: Any arbitrary string is safely parsed into a valid ParsedCommitObject."""
    obj = parse_commit_object(content)
    assert isinstance(obj, ParsedCommitObject)
    assert obj.sig_type in {"none", "ssh", "pgp", "sigstore", "unknown"}
    d = obj.to_dict()
    assert isinstance(d, dict)
    assert "has_signature" in d
    assert "sig_type" in d


@given(
    sha=st.text(max_size=40),
    author=st.text(max_size=100),
    committer=st.text(max_size=100),
    flag=st.sampled_from(["G", "U", "B", "N", "E", "X", "Y", "R", ""]),
    signer=st.text(max_size=100),
    key_id=st.text(max_size=100),
    strict=st.booleans(),
)
def test_property_evaluate_commit_signature_invariants(
    sha: str,
    author: str,
    committer: str,
    flag: str,
    signer: str,
    key_id: str,
    strict: bool,
) -> None:
    """Invariant: Signature evaluation handles arbitrary inputs safely and respects hard security rules."""
    att = evaluate_commit_signature(
        commit_sha=sha,
        author=author,
        committer=committer,
        git_sig_flag=flag,
        signer=signer,
        key_id=key_id,
        strict=strict,
    )
    assert isinstance(att.is_valid, bool)
    assert isinstance(att.sig_status, str)

    # Invariant: Unsigned flag 'N' must never produce valid status
    if flag == "N":
        assert att.is_valid is False
        assert att.sig_status == "UNSIGNED"

    # Invariant: Corrupt/bad flag 'B' must never produce valid status
    if flag == "B":
        assert att.is_valid is False
        assert att.sig_status == "INVALID"
