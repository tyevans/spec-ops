"""Blackbox frontdoor verification for TASK-0236: Decouple Docs from Visualizer.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path

from spec_ops.app.site_bundler import SiteBundlerService
from spec_ops.config.loader import load_config
from spec_ops.docs.builder import (
    build_docs_site,
    register_default_project_serializer,
    register_default_visualizer_generator,
)
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_docs_builder_has_no_visualizer_imports():
    """Verify that src/spec_ops/docs/builder.py contains zero imports of spec_ops.visualizer."""
    builder_file = Path("src/spec_ops/docs/builder.py")
    assert builder_file.is_file(), "builder.py must exist"

    code = builder_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    viz_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "visualizer" in alias.name:
                    viz_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "visualizer" in mod:
                viz_imports.append(mod)

    assert not viz_imports, f"Found illegal visualizer imports in docs/builder.py: {viz_imports}"


def test_docs_to_visualizer_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from docs -> visualizer."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    docs_viz_violations = [
        v for v in violations
        if v.get("source") == "docs" and v.get("target") == "visualizer"
    ]
    assert not docs_viz_violations, f"Active docs -> visualizer violations detected: {docs_viz_violations}"


def test_build_docs_site_injected_visualizer_generator(tmp_path: Path):
    """Verify build_docs_site accepts an injected visualizer generator without static import."""
    target = tmp_path / "proj"
    init_project(target, name="TestProj", diataxis=True)
    config = load_config(target)

    recorded_calls: list[str] = []

    def custom_generator(cfg, **kwargs):
        recorded_calls.append("generated")
        return "<html><body>Custom Visualizer</body></html>"

    out_site = tmp_path / "site"
    build_docs_site(config, out_dir=out_site, visualizer_generator=custom_generator)

    assert len(recorded_calls) == 1
    vis_html = out_site / "visualizer" / "index.html"
    assert vis_html.is_file()
    assert "Custom Visualizer" in vis_html.read_text(encoding="utf-8")


def test_build_docs_site_registered_visualizer_generator(tmp_path: Path):
    """Verify build_docs_site invokes registered default visualizer generator."""
    target = tmp_path / "proj_reg"
    init_project(target, name="TestProjReg", diataxis=True)
    config = load_config(target)

    recorded_calls: list[str] = []

    def custom_reg_generator(cfg, **kwargs):
        recorded_calls.append("reg_generated")
        return "<html><body>Registered Visualizer</body></html>"

    try:
        register_default_visualizer_generator(custom_reg_generator)
        out_site = tmp_path / "site_reg"
        build_docs_site(config, out_dir=out_site)

        assert len(recorded_calls) == 1
        vis_html = out_site / "visualizer" / "index.html"
        assert vis_html.is_file()
        assert "Registered Visualizer" in vis_html.read_text(encoding="utf-8")
    finally:
        register_default_visualizer_generator(None)


def test_site_bundler_service_embeds_visualizer_and_project_data(tmp_path: Path):
    """Verify SiteBundlerService embeds visualizer and project-data.json at layer 4."""
    target = tmp_path / "proj_bundler"
    init_project(target, name="TestProjBundler", diataxis=True)
    config = load_config(target)

    bundler = SiteBundlerService(config)
    result = bundler.bundle_documentation_suite(target_dir=tmp_path / "bundled_site")

    assert result.pages_compiled > 0
    assert result.visualizer_embedded is True
    assert (tmp_path / "bundled_site" / "visualizer" / "index.html").is_file()
    assert (tmp_path / "bundled_site" / "project-data.json").is_file()
