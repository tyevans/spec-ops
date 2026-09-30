"""Unit and error branch tests for visualizer bundle exporter (ADR-0003, ADR-0009)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.bundle import (
    MAX_BUNDLE_BYTES,
    compile_bundle,
    export_bundle,
    serialize_bundle_data,
    validate_airgap_integrity,
)


def test_validate_airgap_integrity_detects_external_scripts():
    assert validate_airgap_integrity('<script src="http://cdn.com/app.js"></script>') is False
    assert validate_airgap_integrity("<script src='https://cdn.com/app.js'></script>") is False
    assert validate_airgap_integrity('<SCRIPT SRC="HTTP://CDN.COM/APP.JS"></SCRIPT>') is False


def test_validate_airgap_integrity_detects_external_stylesheets():
    assert validate_airgap_integrity('<link rel="stylesheet" href="http://cdn.com/app.css">') is False
    assert validate_airgap_integrity("<link href='https://cdn.com/app.css' rel='stylesheet'>") is False


def test_validate_airgap_integrity_allows_clean_html():
    clean_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <style>body { color: red; }</style>
        <link rel="icon" href="favicon.ico">
      </head>
      <body>
        <script>console.log("hello"); window.test = "\\u003cscript src='http://not-a-tag'>";</script>
      </body>
    </html>
    """
    assert validate_airgap_integrity(clean_html) is True


def test_serialize_bundle_data(tmp_path: Path):
    init_project(tmp_path, name="BundleTest")
    config = load_config(root_dir=tmp_path)
    data = serialize_bundle_data(config)

    assert "nodes" in data
    assert "edges" in data
    assert "telemetry" in data
    assert isinstance(data["telemetry"], list)


def test_compile_bundle_escaping_and_template(tmp_path: Path):
    init_project(tmp_path, name="BundleEscapeTest")
    config = load_config(root_dir=tmp_path)

    bundle_html = compile_bundle(config, back_link="custom/back.html")
    assert "href=\"custom/back.html\"" in bundle_html
    assert "BundleEscapeTest" in bundle_html
    assert "<script" in bundle_html
    # Inlined JSON must not contain raw "<" inside data payload
    assert "\\u003c" in bundle_html or "<" in bundle_html


def test_export_bundle_airgap_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    init_project(tmp_path, name="AirgapFailTest")
    config = load_config(root_dir=tmp_path)

    # Force compile_bundle to return HTML with external script
    monkeypatch.setattr(
        "spec_ops.visualizer.bundle.compile_bundle",
        lambda *args, **kwargs: '<html><script src="https://cdn.jsdelivr.net/npm/d3@7"></script></html>',
    )

    out_file = tmp_path / "dist" / "fail.html"
    with pytest.raises(ValueError, match="Airgap integrity check failed"):
        export_bundle(config, output_path=out_file)


def test_export_bundle_size_limit_exceeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    init_project(tmp_path, name="SizeFailTest")
    config = load_config(root_dir=tmp_path)

    # Set MAX_BUNDLE_BYTES artificially low to trigger size check
    monkeypatch.setattr("spec_ops.visualizer.bundle.MAX_BUNDLE_BYTES", 50)

    out_file = tmp_path / "dist" / "oversized.html"
    with pytest.raises(ValueError, match="exceeds 50 byte"):
        export_bundle(config, output_path=out_file)
