"""Unit tests for cryptographic release verification and keyring engine (ADR-0014, PRD-0002)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from spec_ops.cli.release_handler import handle_release_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.security.ed25519 import (
    _Q,
    ed25519_keypair,
    ed25519_sign,
    ed25519_verify,
    ssh_decode_ed25519_pub,
    ssh_encode_ed25519_pub,
)
from spec_ops.security.release_verifier import (
    AuthorizedSigner,
    ReleaseVerificationResult,
    canonical_manifest_bytes,
    parse_allowed_signers,
    sign_release_manifest,
    verify_release_manifest_data,
    verify_release_manifest_file,
)


def test_ed25519_edge_cases():
    seed = b"unit_test_seed_1234567890123456"
    _, pub = ed25519_keypair(seed)
    msg = b"test message"
    sig = ed25519_sign(seed, pub, msg)

    # Valid
    assert ed25519_verify(pub, msg, sig) is True

    # Invalid lengths
    assert ed25519_verify(pub[:31], msg, sig) is False
    assert ed25519_verify(pub, msg, sig[:63]) is False
    assert ed25519_verify(b"short", msg, sig) is False

    # Signature scalar >= group order Q
    bad_sig = bytearray(sig)
    bad_s = _Q + 1
    bad_sig[32:] = bad_s.to_bytes(32, "little")
    assert ed25519_verify(pub, msg, bytes(bad_sig)) is False

    # Non-32 byte seed auto-hashes
    seed_short = b"short_seed"
    s1, p1 = ed25519_keypair(seed_short)
    assert len(s1) == 32
    assert len(p1) == 32


def test_ssh_decode_ed25519_pub_edge_cases():
    assert ssh_decode_ed25519_pub("invalid string not base64 !!!") is None
    assert ssh_decode_ed25519_pub("") is None

    # Hex string
    raw = b"h" * 32
    hex_str = raw.hex()
    assert ssh_decode_ed25519_pub(hex_str) == raw

    # Raw 32 bytes base64
    import base64

    b64_raw = base64.b64encode(raw).decode()
    assert ssh_decode_ed25519_pub(b64_raw) == raw

    # OpenSSH wire format
    ssh_line = ssh_encode_ed25519_pub(raw)
    assert ssh_decode_ed25519_pub(ssh_line) == raw


def test_parse_allowed_signers_comprehensive(tmp_path: Path):
    content = """
    # Comment line
    
    # Another comment
    user1@example.com,user2@example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGtra2tra2tra2tra2tra2tra2tra2tra2tra2tra2tr key comment
    * namespaces="file,git" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGtra2tra2tra2tra2tra2tra2tra2tra2tra2tra2tr
    short_line
    invalid_opt foo=bar
    """
    keyring_file = tmp_path / ".allowed_signers"
    keyring_file.write_text(content, encoding="utf-8")

    signers = parse_allowed_signers(keyring_file)
    assert len(signers) == 2

    s1 = signers[0]
    assert s1.principals == ["user1@example.com", "user2@example.com"]
    assert s1.key_type == "ssh-ed25519"
    assert len(s1.pubkey_bytes) == 32
    assert s1.comment == "key comment"

    s2 = signers[1]
    assert s2.principals == ["*"]
    assert s2.namespaces == ["file", "git"]


def test_canonical_manifest_bytes():
    m1 = {"b": 2, "a": 1, "signature": "sig123", "sig": "s"}
    m2 = {"a": 1, "b": 2}
    assert canonical_manifest_bytes(m1) == canonical_manifest_bytes(m2)
    assert b"signature" not in canonical_manifest_bytes(m1)


def test_sign_and_verify_hmac():
    manifest = {
        "prd": {"id": "PRD-0001"},
        "verified_tree_digest": "0" * 64,
        "uat_verification": {"status": "Approved"},
    }
    secret = b"hmac_shared_secret_key"
    signer = "sasha@specops.dev"
    signed = sign_release_manifest(manifest, secret, signer, algorithm="hmac-sha256")

    assert signed["signer"] == signer
    assert signed["signature_algorithm"] == "hmac-sha256"
    assert "signature" in signed

    auth_signer = AuthorizedSigner(
        principals=[signer],
        key_type="hmac-sha256",
        pubkey_bytes=secret,
        raw_key="",
    )

    res = verify_release_manifest_data(signed, [auth_signer])
    assert res.valid is True


def test_verify_release_manifest_missing_signature_and_unauthorized():
    manifest = {
        "prd": {"id": "PRD-0001"},
        "signer": "eve@attacker.com",
    }
    auth_signer = AuthorizedSigner(
        principals=["alice@specops.dev"],
        key_type="ssh-ed25519",
        pubkey_bytes=b"k" * 32,
        raw_key="",
    )

    res = verify_release_manifest_data(manifest, [auth_signer])
    assert res.valid is False
    assert any("not found in authorized signers keyring" in err for err in res.errors)
    assert any("manifest lacks cryptographic signature" in err for err in res.errors)


def test_verify_release_manifest_file_io(tmp_path: Path):
    # Non-existent
    res = verify_release_manifest_file(tmp_path / "nonexistent.json")
    assert res.valid is False
    assert "not found" in res.message

    # Malformed JSON
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json...", encoding="utf-8")
    res = verify_release_manifest_file(bad_json)
    assert res.valid is False
    assert "Invalid manifest JSON" in res.message


def test_verify_release_manifest_strict_checks(tmp_path: Path):
    seed = b"strict_seed_12345678901234567890"
    _, pub = ed25519_keypair(seed)
    signer = "sasha@specops.dev"

    manifest = {
        "prd": {"id": "PRD-0001"},
        "verified_tree_digest": "0" * 64,
        "uat_verification": {"status": "Pending"},
    }
    signed = sign_release_manifest(manifest, seed, signer, algorithm="ed25519")

    auth_signer = AuthorizedSigner(
        principals=[signer],
        key_type="ssh-ed25519",
        pubkey_bytes=pub,
        raw_key="",
    )

    # In non-strict mode, pending UAT does not fail signature validity
    res_non_strict = verify_release_manifest_data(signed, [auth_signer], strict=False)
    assert res_non_strict.valid is True

    # In strict mode, pending UAT fails
    res_strict = verify_release_manifest_data(signed, [auth_signer], strict=True)
    assert res_strict.valid is False
    assert any("requires Approved UAT status" in err for err in res_strict.errors)


def test_handle_release_command_verify_cli(tmp_path: Path, capsys: pytest.CaptureFixture):
    seed = b"cli_test_seed_123456789012345678"
    _, pub = ed25519_keypair(seed)
    ssh_line = ssh_encode_ed25519_pub(pub)

    keyring = tmp_path / ".allowed_signers"
    keyring.write_text(f"auditor@specops.dev {ssh_line}\n", encoding="utf-8")

    manifest = {
        "prd": {"id": "PRD-0001"},
        "verified_tree_digest": "0" * 64,
        "uat_verification": {"status": "Approved"},
    }
    signed = sign_release_manifest(manifest, seed, "auditor@specops.dev", algorithm="ed25519")
    m_file = tmp_path / "manifest.json"
    m_file.write_text(json.dumps(signed), encoding="utf-8")

    config = SpecOpsConfig(root_dir=tmp_path)
    parser = argparse.ArgumentParser()

    # Test JSON mode
    args_json = argparse.Namespace(
        release_action="verify",
        manifest=str(m_file),
        keyring=str(keyring),
        strict=False,
        json=True,
    )
    rc = handle_release_command(args_json, config, parser)
    assert rc == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["valid"] is True
    assert report["signer"] == "auditor@specops.dev"

    # Test human-readable mode
    args_human = argparse.Namespace(
        release_action="verify",
        manifest=str(m_file),
        keyring=str(keyring),
        strict=False,
        json=False,
    )
    rc = handle_release_command(args_human, config, parser)
    assert rc == 0
    captured = capsys.readouterr()
    assert "VALID" in captured.out
    assert "PASSED" in captured.out
