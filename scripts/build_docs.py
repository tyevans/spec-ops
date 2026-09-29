#!/usr/bin/env python3
"""SpecOps Documentation & Project Visualizer Site Builder.

Compiles Diataxis documentation into a clean static site, embeds the standalone
2D project visualizer, exports project graph metadata, and prepares artifacts
for deployment to GitHub Pages.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from spec_ops.config.loader import load_config
from spec_ops.docs.builder import build_docs_site


def main() -> None:
    config = load_config(ROOT_DIR)
    out_dir = build_docs_site(config)
    print(f"🎉 SpecOps Documentation Site generated in {out_dir}")


if __name__ == "__main__":
    main()
