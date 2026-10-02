"""Blackbox frontdoor verification for TASK-0235: Decouple Docs from PRD.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path

from spec_ops.app.site_bundler import SiteBundlerService
from spec_ops.config.loader import load_config
from spec_ops.docs.builder import (
    build_docs_site,
    register_default_roadmap_exporter,
)
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_docs_builder_has_no_prd_imports():
    """Verify that src/spec_ops/docs/builder.py contains zero imports of spec_ops.prd."""
    builder_file = Path("src/spec_ops/docs/builder.py")
    assert builder_file.is_file(), "builder.py must exist"

    code = builder_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    prd_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "prd" in alias.name:
                    prd_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "prd" in mod:
                prd_imports.append(mod)

    assert not prd_imports, f"Found illegal prd imports in docs/builder.py: {prd_imports}"


def test_docs_to_prd_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from docs -> prd."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    docs_prd_violations = [
        v for v in violations
        if v.get("source") == "docs" and v.get("target") == "prd"
    ]
    assert not docs_prd_violations, f"Active docs -> prd violations detected: {docs_prd_violations}"


def test_build_docs_site_injected_roadmap_exporter(tmp_path: Path):
    """Verify build_docs_site accepts an injected roadmap exporter without static prd import."""
    target = tmp_path / "proj"
    init_project(target, name="TestProj", diataxis=True)
    config = load_config(target)

    recorded_calls: list[Path] = []

    def custom_exporter(cfg, **kwargs):
        out = kwargs.get("output_path")
        if out:
            out.write_text("<svg>custom roadmap</svg>", encoding="utf-8")
            recorded_calls.append(out)

    out_site = tmp_path / "site"
    build_docs_site(config, out_dir=out_site, roadmap_exporter=custom_exporter)

    assert len(recorded_calls) == 1
    svg_file = out_site / "assets" / "roadmap.svg"
    assert svg_file.is_file()
    assert svg_file.read_text(encoding="utf-8") == "<svg>custom roadmap</svg>"


def test_build_docs_site_registered_roadmap_exporter(tmp_path: Path):
    """Verify build_docs_site invokes registered default roadmap exporter."""
    target = tmp_path / "proj_reg"
    init_project(target, name="TestProjReg", diataxis=True)
    config = load_config(target)

    recorded_calls: list[Path] = []

    def custom_reg_exporter(cfg, **kwargs):
        out = kwargs.get("output_path")
        if out:
            out.write_text("<svg>registered roadmap</svg>", encoding="utf-8")
            recorded_calls.append(out)

    try:
        register_default_roadmap_exporter(custom_reg_exporter)
        out_site = tmp_path / "site_reg"
        build_docs_site(config, out_dir=out_site)

        assert len(recorded_calls) == 1
        svg_file = out_site / "assets" / "roadmap.svg"
        assert svg_file.is_file()
        assert svg_file.read_text(encoding="utf-8") == "<svg>registered roadmap</svg>"
    finally:
        register_default_roadmap_exporter(None)


def test_site_bundler_service_orchestration(tmp_path: Path):
    """Verify SiteBundlerService bundles docs and exports roadmaps at layer 4."""
    target = tmp_path / "proj_bundler"
    init_project(target, name="TestProjBundler", diataxis=True)
    config = load_config(target)

    bundler = SiteBundlerService(config)
    result = bundler.bundle_documentation_suite(target_dir=tmp_path / "bundled_site")

    assert result.pages_compiled > 0
    assert result.visualizer_embedded is True
    assert (tmp_path / "bundled_site" / "index.html").is_file()
    assert (tmp_path / "bundled_site" / "visualizer" / "index.html").is_file()
