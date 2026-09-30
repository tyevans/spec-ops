"""Hypothesis property tests for security waivers (ADR-0009)."""

from __future__ import annotations

import datetime
from hypothesis import given, strategies as st

from spec_ops.security.waivers import (
    Waiver,
    compute_waiver_signature,
    is_waiver_expired,
    normalize_waiver_id,
    parse_waiver_content,
    parse_waiver_date,
    verify_waiver_signature,
)


@given(st.integers(min_value=1, max_value=999999))
def test_waiver_id_formatting_idempotence(num: int):
    raw_str = f"WAIVER-{num}"
    norm = normalize_waiver_id(raw_str)
    assert norm.startswith("WAIVER-")
    assert normalize_waiver_id(norm) == norm
    assert normalize_waiver_id(num) == norm


@given(st.dates(), st.dates())
def test_waiver_expiration_parsing_and_invariants(exp_date: datetime.date, ref_date: datetime.date):
    parsed = parse_waiver_date(exp_date.isoformat())
    assert parsed == exp_date
    assert parse_waiver_date(exp_date) == exp_date

    w = Waiver(
        id="WAIVER-001",
        package="test-pkg",
        signer="Sasha",
        expires=exp_date,
        signature="test-sig",
    )
    expected_expired = exp_date < ref_date
    assert is_waiver_expired(w, reference_date=ref_date) == expected_expired


@given(
    pkg=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=15),
    signer=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=15),
    w_id=st.integers(min_value=1, max_value=999),
    exp_date=st.dates(min_value=datetime.date(2000, 1, 1), max_value=datetime.date(2099, 12, 31)),
)
def test_waiver_signature_validation_and_tamper_detection(
    pkg: str, signer: str, w_id: int, exp_date: datetime.date
):
    wid_str = f"WAIVER-{w_id:03d}"
    sig = compute_waiver_signature(wid_str, pkg, signer, exp_date)

    w = Waiver(
        id=wid_str,
        package=pkg,
        signer=signer,
        expires=exp_date,
        signature=sig,
    )
    # Valid signature check
    assert verify_waiver_signature(w) is True

    # Tampering with package
    w_tampered_pkg = Waiver(
        id=wid_str,
        package=pkg + "_tampered",
        signer=signer,
        expires=exp_date,
        signature=sig,
    )
    assert verify_waiver_signature(w_tampered_pkg) is False

    # Tampering with signer
    w_tampered_signer = Waiver(
        id=wid_str,
        package=pkg,
        signer=signer + "_other",
        expires=exp_date,
        signature=sig,
    )
    assert verify_waiver_signature(w_tampered_signer) is False

    # Tampering with expiration
    w_tampered_exp = Waiver(
        id=wid_str,
        package=pkg,
        signer=signer,
        expires=exp_date + datetime.timedelta(days=1),
        signature=sig,
    )
    assert verify_waiver_signature(w_tampered_exp) is False


@given(
    pkg_key=st.sampled_from(["package", "package_name", "dependency"]),
    signer_key=st.sampled_from(["signer", "signed_by", "approved_by"]),
    date_key=st.sampled_from(["expires", "expiration", "expiration_date"]),
    sig_key=st.sampled_from(["signature", "sig", "pgp_signature"]),
    w_num=st.integers(min_value=1, max_value=999),
    exp_date=st.dates(min_value=datetime.date(2020, 1, 1), max_value=datetime.date(2035, 12, 31)),
)
def test_waiver_frontmatter_field_diversity(
    pkg_key: str, signer_key: str, date_key: str, sig_key: str, w_num: int, exp_date: datetime.date
):
    content = (
        f"---\n"
        f"id: WAIVER-{w_num}\n"
        f"{pkg_key}: my-sample-lib\n"
        f"{signer_key}: Sasha\n"
        f"{date_key}: {exp_date.isoformat()}\n"
        f"{sig_key}: sha256:0123456789abcdef\n"
        f"reason: Diverse frontmatter test\n"
        f"---\n"
        f"Body content\n"
    )
    waiver = parse_waiver_content(content)
    assert waiver is not None
    assert waiver.id == f"WAIVER-{w_num:03d}"
    assert waiver.package == "my-sample-lib"
    assert waiver.signer == "Sasha"
    assert waiver.expires == exp_date
    assert waiver.signature == "sha256:0123456789abcdef"
