"""Unit tests for Cryptographic Commit Attestation and Sigstore Keyring Validator."""

from __future__ import annotations

from pathlib import Path
import pytest

from spec_ops.security.commit_attestation import (
    CommitAttestation,
    CommitVerificationReport,
    ParsedCommitObject,
    evaluate_commit_signature,
    load_keyring_entries,
    parse_commit_object,
    verify_commits_cli,
)


SAMPLE_SSH_COMMIT = """tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904
parent a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
author Developer <dev@example.com> 1700000000 +0000
committer Committer <committer@example.com> 1700000000 +0000
gpgsig -----BEGIN SSH SIGNATURE-----
 U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg...
 -----END SSH SIGNATURE-----

feat: Initial signed commit
"""

SAMPLE_PGP_COMMIT = """tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904
author PGP Signer <pgp@example.com> 1700000000 +0000
committer PGP Signer <pgp@example.com> 1700000000 +0000
gpgsig -----BEGIN PGP SIGNATURE-----
 Version: GnuPG v2
 ...
 -----END PGP SIGNATURE-----

fix: PGP signed commit
"""

SAMPLE_UNSIGNED_COMMIT = """tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904
author Unsigned <unsigned@example.com> 1700000000 +0000
committer Unsigned <unsigned@example.com> 1700000000 +0000

chore: Plain unsigned commit
"""


def test_parse_commit_object_ssh() -> None:
    """Assert parsing extracts SSH signature and metadata."""
    obj = parse_commit_object(SAMPLE_SSH_COMMIT)
    assert obj.tree == "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    assert obj.parents == ["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"]
    assert "dev@example.com" in obj.author
    assert "committer@example.com" in obj.committer
    assert obj.sig_type == "ssh"
    assert "BEGIN SSH SIGNATURE" in obj.gpgsig
    assert obj.message == "feat: Initial signed commit"

    d = obj.to_dict()
    assert d["has_signature"] is True
    assert d["sig_type"] == "ssh"


def test_parse_commit_object_pgp_and_unsigned() -> None:
    """Assert parsing extracts PGP signature and handles unsigned commits."""
    pgp_obj = parse_commit_object(SAMPLE_PGP_COMMIT)
    assert pgp_obj.sig_type == "pgp"
    assert "BEGIN PGP SIGNATURE" in pgp_obj.gpgsig

    uns_obj = parse_commit_object(SAMPLE_UNSIGNED_COMMIT)
    assert uns_obj.sig_type == "none"
    assert uns_obj.gpgsig == ""
    assert uns_obj.message == "chore: Plain unsigned commit"


def test_load_keyring_entries(tmp_path: Path) -> None:
    """Assert keyring loader extracts identities and key blobs."""
    assert load_keyring_entries(None) == set()
    assert load_keyring_entries(tmp_path / "missing") == set()

    keyring_file = tmp_path / "allowed_signers"
    keyring_file.write_text(
        """# Allowed signers
alice@example.com,bob@example.com namespaces="git" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI12345
maintainer@company.com namespaces="git" SHA256:abcdef1234567890
""",
        encoding="utf-8",
    )
    entries = load_keyring_entries(keyring_file)
    assert "alice@example.com" in entries
    assert "bob@example.com" in entries
    assert "maintainer@company.com" in entries
    assert "sha256:abcdef1234567890" in entries


def test_evaluate_commit_signature_flags() -> None:
    """Assert signature evaluation handles G, B, N, U flags correctly."""
    # Unsigned (N)
    uns = evaluate_commit_signature("abc1234", "Dev <dev@test.com>", "Dev <dev@test.com>", "N", "", "")
    assert uns.is_valid is False
    assert uns.sig_status == "UNSIGNED"

    # Bad signature (B)
    bad = evaluate_commit_signature("abc1234", "Dev <dev@test.com>", "Dev <dev@test.com>", "B", "", "")
    assert bad.is_valid is False
    assert bad.sig_status == "INVALID"

    # Good signature with matching keyring (G)
    good = evaluate_commit_signature(
        "abc1234", "Dev <dev@test.com>", "Dev <dev@test.com>", "G",
        "dev@test.com", "SHA256:key123",
        authorized_keys={"dev@test.com"},
    )
    assert good.is_valid is True
    assert good.sig_status == "VALID"

    # Good signature with unlisted signer
    untrusted = evaluate_commit_signature(
        "abc1234", "Hacker <evil@test.com>", "Hacker <evil@test.com>", "G",
        "evil@test.com", "SHA256:evilkey",
        authorized_keys={"maintainer@test.com"},
    )
    assert untrusted.is_valid is False
    assert untrusted.sig_status == "UNTRUSTED_SIGNER"


def test_commit_verification_report_formatting() -> None:
    """Assert report serialization and text rendering."""
    clean_rep = CommitVerificationReport(
        rev_range="HEAD~1..HEAD",
        commits=[
            CommitAttestation(
                commit_sha="1111222233334444",
                author="Dev <dev@test.com>",
                committer="Dev <dev@test.com>",
                signer="dev@test.com",
                key_id="SHA256:key123",
                sig_status="VALID",
                sig_type="ssh",
                is_valid=True,
            )
        ],
        is_clean=True,
        total_verified=1,
        total_failed=0,
    )
    text = clean_rep.format_text()
    assert "Cryptographic Provenance Verified" in text
    assert clean_rep.to_dict()["is_clean"] is True

    bad_rep = CommitVerificationReport(
        rev_range="HEAD~2..HEAD",
        commits=[
            CommitAttestation(
                commit_sha="5555666677778888",
                author="Unsigned <u@test.com>",
                committer="Unsigned <u@test.com>",
                signer="",
                key_id="",
                sig_status="UNSIGNED",
                sig_type="none",
                is_valid=False,
                diagnostics=["Commit lacks cryptographic signature."],
            )
        ],
        is_clean=False,
        total_verified=0,
        total_failed=1,
    )
    bad_text = bad_rep.format_text()
    assert "Attestation Violations Detected" in bad_text
    assert "55556666" in bad_text
