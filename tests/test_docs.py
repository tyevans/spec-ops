"""Tests for Diataxis documentation scaffolding and static site builder."""

import subprocess
import sys
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.docs.builder import build_docs_site, simple_markdown_to_html
from spec_ops.scaffold.init import init_project


def test_init_diataxis_scaffolding(tmp_path: Path):
    target = tmp_path / "diataxis_app"
    created = init_project(target, name="DiataxisApp", diataxis=True)

    assert (target / "docs" / "tutorials" / "01-getting-started.md").is_file()
    assert (target / "docs" / "how-to" / "bootstrap-project.md").is_file()
    assert (target / "docs" / "reference" / "cli.md").is_file()
    assert (target / "docs" / "explanation" / "project-management-as-code.md").is_file()
    assert (target / "docs" / "contributing.md").is_file()
    assert (target / "docs" / "index.md").is_file()
    assert (target / "docs" / "operating-manual.md").is_file()

    index_text = (target / "docs" / "index.md").read_text(encoding="utf-8")
    assert "Diataxis framework" in index_text

    manual_text = (target / "docs" / "operating-manual.md").read_text(encoding="utf-8")
    assert "# DiataxisApp Agent Operating Manual" in manual_text


def test_init_no_diataxis_scaffolding(tmp_path: Path):
    target = tmp_path / "no_diataxis"
    init_project(target, name="NoDiataxis", diataxis=False)

    assert not (target / "docs" / "tutorials").exists()
    assert not (target / "docs" / "how-to").exists()
    assert not (target / "docs" / "explanation").exists()
    assert not (target / "docs" / "reference").exists()
    # But docs/project still exists
    assert (target / "docs" / "project" / "backlog" / "PRIORITY.md").is_file()


def test_docs_builder_site_generation(tmp_path: Path):
    target = tmp_path / "site_app"
    init_project(target, name="SiteApp", diataxis=True)

    config = load_config(target)
    out_dir = build_docs_site(config, base_url="/site-app/")

    assert (out_dir / "index.html").is_file()
    assert (out_dir / "visualizer" / "index.html").is_file()
    assert (out_dir / "project-data.json").is_file()
    assert (out_dir / "search-index.json").is_file()
    assert (out_dir / ".nojekyll").is_file()

    # Check generated html
    index_html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "<title>SiteApp Documentation — SiteApp Documentation</title>" in index_html
    assert 'href="/site-app/tutorials/01-getting-started.html"' in index_html

    # Check search index
    search_json = (out_dir / "search-index.json").read_text(encoding="utf-8")
    assert "01-getting-started.html" in search_json


def test_cli_docs_build(tmp_path: Path):
    target = tmp_path / "cli_docs_app"
    subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "init", "--name", "CliDocs", "--dir", str(target), "--diataxis"],
        check=True,
        capture_output=True,
    )

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "docs", "build", "--base-url", "/clidocs/"],
        cwd=str(target),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Compiled Diataxis documentation" in res.stdout
    assert (target / "site" / "index.html").is_file()
    assert (target / "site" / "visualizer" / "index.html").is_file()


def test_simple_markdown_to_html_formatting():
    md = """# Sample Heading
> Important note here

- List item 1
- List item 2 with `inline code` and [Link](guide.md)

1. First step
2. Second step

| Col 1 | Col 2 |
|---|---|
| Val 1 | Val 2 |

```python
def foo():
    return 42
```
"""
    html_out = simple_markdown_to_html(md)
    assert "<h1>Sample Heading</h1>" in html_out
    assert "<blockquote>" in html_out
    assert "<ul>" in html_out
    assert '<a href="guide.html">Link</a>' in html_out
    assert "<ol>" in html_out
    assert '<div class="table-wrapper"><table>' in html_out
    assert '<code class="language-python">' in html_out
