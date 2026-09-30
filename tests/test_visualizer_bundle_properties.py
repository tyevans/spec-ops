"""Hypothesis property-based tests for visualizer bundle and airgap invariants (ADR-0009)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.bundle import (
    compile_bundle,
    export_bundle,
    validate_airgap_integrity,
)


@st.composite
def project_and_links(draw):
    name = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-", min_size=1, max_size=30))
    back_link = draw(st.sampled_from(["../index.html", "/docs/", "index.html", "./overview.html", "https-fake-ref-not-tag"]))
    return name, back_link


@settings(max_examples=25, deadline=None)
@given(data=project_and_links())
def test_property_standalone_html_bundle_zero_external_network_dependencies(tmp_path_factory, data):
    """Generative property invariant (ADR-0009): Generated bundle contains ZERO external script or style tags."""
    name, back_link = data
    tmp_path = tmp_path_factory.mktemp(f"vis_prop_{name[:10]}")
    init_project(tmp_path, name=name)
    config = load_config(root_dir=tmp_path)

    html = compile_bundle(config, back_link=back_link)

    # Invariant 1: Airgap integrity passes
    assert validate_airgap_integrity(html) is True

    # Invariant 2: Zero external <script src="http..."> or <link ... href="http...">
    external_scripts = re.findall(r'<script\b[^>]*\bsrc=["\']https?://', html, re.IGNORECASE)
    assert len(external_scripts) == 0, f"Found external scripts: {external_scripts}"

    external_links = re.findall(r'<link\b[^>]*\bhref=["\']https?://', html, re.IGNORECASE)
    assert len(external_links) == 0, f"Found external stylesheets: {external_links}"

    # Invariant 3: Back link is accurately rendered
    assert f'href="{back_link}"' in html

    # Invariant 4: Basic HTML structural validity
    assert html.startswith("<!DOCTYPE html>") or "<!DOCTYPE html>" in html
    assert "</html>" in html
    assert "window.PROJECT_DATA" in html


@settings(max_examples=10, deadline=None)
@given(filename=st.sampled_from(["index.html", "spec-ops-visualizer.html", "dashboard.html"]))
def test_property_export_bundle_file_invariants(tmp_path_factory, filename):
    """Property test verifying exported bundle size, path creation, and airgap invariants on disk."""
    tmp_path = tmp_path_factory.mktemp("export_prop")
    init_project(tmp_path, name="PropExport")
    config = load_config(root_dir=tmp_path)

    out_file = tmp_path / "dist" / "nested" / filename
    result_path = export_bundle(config, output_path=out_file)

    assert result_path.exists()
    assert result_path == out_file
    size = result_path.stat().st_size
    assert 0 < size <= 2 * 1024 * 1024  # Under 2MB limit

    content = result_path.read_text(encoding="utf-8")
    assert validate_airgap_integrity(content) is True
