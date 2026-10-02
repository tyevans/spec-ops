"""Site bundler application service.

Coordinates full documentation site compilation, interactive visualizer bundle embedding,
and PRD roadmap exports across docs, visualizer, and prd contexts. Governed by ADR-0021.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig


@dataclass
class BundlingResult:
    """Outcome of full documentation site bundling."""

    output_dir: Path
    pages_compiled: int
    visualizer_embedded: bool
    roadmap_exported: bool
    details: dict[str, Any] | None = None


class SiteBundlerService:
    """Application service coordinating multi-context documentation and site bundling."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.root_dir = config.root_dir

    def bundle_documentation_suite(
        self,
        target_dir: str | Path | None = None,
        include_visualizer: bool = True,
        include_roadmap: bool = True,
    ) -> BundlingResult:
        """Assembles complete Diataxis documentation site with embedded visualizer and roadmaps."""
        out_path = Path(target_dir).resolve() if target_dir else (self.root_dir / "dist" / "site")
        out_path.mkdir(parents=True, exist_ok=True)

        # 1. Compile Diataxis markdown documentation via docs context
        from ..docs.builder import build_docs_site

        site_res = build_docs_site(
            config=self.config,
            out_dir=out_path,
            include_visualizer=False,  # Bundler handles visualizer coordination
        )
        doc_count = len(list(out_path.glob("**/*.html")))

        # 2. Compile and embed standalone visualizer bundle via visualizer context
        vis_embedded = False
        if include_visualizer:
            from ..visualizer.generator import generate_standalone_html

            vis_html = generate_standalone_html(self.config, back_link="../index.html")
            vis_dir = out_path / "visualizer"
            vis_dir.mkdir(parents=True, exist_ok=True)
            (vis_dir / "index.html").write_text(vis_html, encoding="utf-8")
            (out_path / "visualizer.html").write_text(vis_html, encoding="utf-8")
            vis_embedded = True

        # 3. Export PRD roadmaps via prd context
        roadmap_exported = False
        if include_roadmap:
            from ..prd.exporter import export_roadmap

            try:
                assets_dir = out_path / "assets"
                assets_dir.mkdir(parents=True, exist_ok=True)
                export_roadmap(self.config, format="svg", output_path=assets_dir / "roadmap.svg")
                export_roadmap(self.config, output_path=out_path / "roadmap.html")
                roadmap_exported = True
            except Exception:
                roadmap_exported = False

        return BundlingResult(
            output_dir=out_path,
            pages_compiled=doc_count,
            visualizer_embedded=vis_embedded,
            roadmap_exported=roadmap_exported,
        )
