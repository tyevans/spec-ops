"""GitHub Pages deployment workflow scaffolding for SpecOps."""

from __future__ import annotations


def generate_pages_workflow(
    project_name: str = "SpecOps",
    base_url: str | None = None,
    timeout_minutes: int = 15,
) -> str:
    """Generates an opinionated GitHub Actions workflow to compile and deploy documentation to GitHub Pages."""
    base_url_flag = f"--base-url {base_url}" if base_url else "--base-url /${{ github.event.repository.name }}/"

    return f"""name: Deploy Documentation & Living Visualizer to GitHub Pages ({project_name})

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy-pages:
    environment:
      name: github-pages
      url: ${{{{ steps.deployment.outputs.page_url }}}}
    runs-on: ubuntu-latest
    timeout-minutes: {timeout_minutes}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
          enable-cache: true

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: uv sync

      - name: Build Diataxis Documentation and Living Visualizer
        run: uv run spec-ops docs build {base_url_flag}

      - name: Setup Pages
        uses: actions/configure-pages@v5

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site/

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
"""
