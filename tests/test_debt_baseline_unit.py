"""Unit tests for debt_baseline.py to maximize mutant kill rate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_ops.core.debt_baseline import (
    evaluate_file_debt,
    load_grandfathered_debt,
    normalize_rel_path,
    save_grandfathered_debt,
    scan_and_record_grandfathered_debt,
    update_specops_toml_grandfathered,
)


def test_normalize_rel_path():
    assert normalize_rel_path("src\\module\\file.py") == "src/module/file.py"
    assert normalize_rel_path("./src/module/file.py") == "src/module/file.py"
    assert normalize_rel_path(Path("src/module/file.py")) == "src/module/file.py"


def test_load_grandfathered_debt_json_formats(tmp_path: Path):
    dot_specops = tmp_path / ".specops"
    dot_specops.mkdir()

    # 1. Versioned files dict format
    json_file = dot_specops / "grandfathered_debt.json"
    json_file.write_text(json.dumps({"version": 1, "files": {"src/a.py": 550}}), encoding="utf-8")
    loaded = load_grandfathered_debt(tmp_path)
    assert loaded == {"src/a.py": 550}

    # 2. Dict format with line_count
    json_file.write_text(json.dumps({"src/b.py": {"line_count": 600}}), encoding="utf-8")
    loaded = load_grandfathered_debt(tmp_path)
    assert loaded == {"src/b.py": 600}

    # 3. List of dicts format
    json_file.write_text(json.dumps([{"path": "src/c.py", "lines": 650}]), encoding="utf-8")
    loaded = load_grandfathered_debt(tmp_path)
    assert loaded == {"src/c.py": 650}


def test_load_grandfathered_debt_legacy_alias(tmp_path: Path):
    dot_specops = tmp_path / ".spec-ops"
    dot_specops.mkdir()
    json_file = dot_specops / "debt-baseline.json"
    json_file.write_text(json.dumps({"src/legacy_old.py": 580}), encoding="utf-8")

    loaded = load_grandfathered_debt(tmp_path)
    assert loaded == {"src/legacy_old.py": 580}



def test_load_grandfathered_debt_toml_fallback(tmp_path: Path):
    toml_path = tmp_path / "specops.toml"
    toml_path.write_text(
        """
[invariants.file_limits]
grandfathered = ["src/legacy.py"]
""",
        encoding="utf-8",
    )
    src_file = tmp_path / "src" / "legacy.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("\n".join(f"# line {i}" for i in range(540)) + "\n", encoding="utf-8")

    loaded = load_grandfathered_debt(tmp_path)
    assert "src/legacy.py" in loaded
    assert loaded["src/legacy.py"] == 540


def test_save_and_update_toml(tmp_path: Path):
    baseline = {"src/legacy_1.py": 520, "src/legacy_2.py": 540}
    saved_json = save_grandfathered_debt(tmp_path, baseline)
    assert saved_json.is_file()
    data = json.loads(saved_json.read_text(encoding="utf-8"))
    assert data["files"] == baseline

    toml_path = update_specops_toml_grandfathered(tmp_path, list(baseline.keys()))
    assert toml_path.is_file()
    content = toml_path.read_text(encoding="utf-8")
    assert "[invariants.file_limits]" in content
    assert "src/legacy_1.py" in content
    assert "src/legacy_2.py" in content


def test_evaluate_file_debt():
    baseline = {"src/legacy.py": 550}

    # Grandfathered within baseline
    ev_gf = evaluate_file_debt("src/legacy.py", 540, baseline, limit=500)
    assert ev_gf.status == "grandfathered"
    assert ev_gf.is_violation is False
    assert ev_gf.baseline_lines == 550

    # Grandfathered at baseline
    ev_exact = evaluate_file_debt("src/legacy.py", 550, baseline, limit=500)
    assert ev_exact.status == "grandfathered"
    assert ev_exact.is_violation is False

    # Grandfathered expanded beyond baseline
    ev_exp = evaluate_file_debt("src/legacy.py", 551, baseline, limit=500)
    assert ev_exp.status == "expanded"
    assert ev_exp.is_violation is True

    # New file unexempt violation
    ev_unex = evaluate_file_debt("src/new.py", 520, baseline, limit=500)
    assert ev_unex.status == "unexempt"
    assert ev_unex.is_violation is True

    # Clean file
    ev_clean = evaluate_file_debt("src/clean.py", 350, baseline, limit=500)
    assert ev_clean.status == "clean"
    assert ev_clean.is_violation is False


def test_scan_and_record_grandfathered_debt(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "huge.py").write_text("\n".join(f"# line {i}" for i in range(530)) + "\n", encoding="utf-8")
    (src / "small.py").write_text("\n".join(f"# line {i}" for i in range(100)) + "\n", encoding="utf-8")

    oversized = scan_and_record_grandfathered_debt(tmp_path, limit=500)
    assert "src/huge.py" in oversized
    assert oversized["src/huge.py"] == 530
    assert "src/small.py" not in oversized


def test_scan_and_record_excludes_hidden_tooling_directories(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "huge.py").write_text("\n".join(f"# line {i}" for i in range(530)) + "\n", encoding="utf-8")

    claude_dir = tmp_path / ".claude" / "worktrees" / "sub"
    claude_dir.mkdir(parents=True)
    (claude_dir / "hidden_huge.py").write_text("\n".join(f"# line {i}" for i in range(600)) + "\n", encoding="utf-8")

    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir(parents=True)
    (cursor_dir / "cursor_huge.py").write_text("\n".join(f"# line {i}" for i in range(700)) + "\n", encoding="utf-8")

    oversized = scan_and_record_grandfathered_debt(tmp_path, limit=500)
    assert "src/huge.py" in oversized
    assert not any(".claude" in k or ".cursor" in k for k in oversized.keys())

