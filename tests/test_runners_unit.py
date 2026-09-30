"""Unit tests for pluggable agent runners to maximize mutmut kill rate."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from spec_ops.config.models import ExecutionSettings, SpecOpsConfig
from spec_ops.worker.runners import (
    AgentRunner,
    build_agent_cmd,
    interpolate_runner_template,
    prepare_runner_environment,
)


def test_interpolate_empty_or_whitespace():
    assert interpolate_runner_template("", Path("p.md")) == []
    assert interpolate_runner_template("   ", Path("p.md")) == []


def test_interpolate_agy_defaults():
    res = interpolate_runner_template("agy -p {prompt}", Path("p.md"), prompt="hello")
    assert res == ["agy", "--dangerously-skip-permissions", "-p", "hello"]

    # When --dangerously-skip-permissions is already present
    res2 = interpolate_runner_template("agy --dangerously-skip-permissions -p {prompt}", Path("p.md"), prompt="hello")
    assert res2 == ["agy", "--dangerously-skip-permissions", "-p", "hello"]

    # When continue_session is True
    res3 = interpolate_runner_template("agy -p {prompt}", Path("p.md"), prompt="hello", continue_session=True)
    assert res3 == ["agy", "--dangerously-skip-permissions", "-c", "-p", "hello"]

    # When -c already present
    res4 = interpolate_runner_template("agy -c -p {prompt}", Path("p.md"), prompt="hello", continue_session=True)
    assert res4 == ["agy", "--dangerously-skip-permissions", "-c", "-p", "hello"]

    # When --continue already present
    res5 = interpolate_runner_template("agy --continue -p {prompt}", Path("p.md"), prompt="hello", continue_session=True)
    assert res5 == ["agy", "--dangerously-skip-permissions", "--continue", "-p", "hello"]


def test_interpolate_with_worktree_dir(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    p_file = Path(".task-prompt.md")

    res = interpolate_runner_template(
        "aider --message-file {prompt_file} --dir {SPEC_OPS_WORKTREE} --pwd {PWD}",
        prompt_file=p_file,
        worktree_dir=wt,
    )
    expected_prompt = str((wt / p_file).resolve())
    expected_wt = str(wt.resolve())

    assert res == [
        "aider",
        "--message-file",
        expected_prompt,
        "--dir",
        expected_wt,
        "--pwd",
        expected_wt,
    ]


def test_interpolate_absolute_prompt_file(tmp_path: Path):
    p_file = (tmp_path / "abs-prompt.md").resolve()
    p_file.write_text("prompt content", encoding="utf-8")

    res = interpolate_runner_template("claude --file {prompt_file}", prompt_file=p_file)
    assert res == ["claude", "--file", str(p_file)]


def test_interpolate_missing_placeholders_appends_file(tmp_path: Path):
    p_file = tmp_path / "p.md"
    p_file.write_text("data", encoding="utf-8")

    res = interpolate_runner_template("my-tool --flag", prompt_file=p_file)
    assert res == ["my-tool", "--flag", str(p_file.resolve())]


def test_interpolate_with_env_dict():
    res = interpolate_runner_template(
        "tool --flag {CUSTOM_VAR} {prompt_file}",
        prompt_file=Path("p.md"),
        env={"CUSTOM_VAR": "val123"},
    )
    assert res[2] == "val123"


def test_prepare_runner_environment_custom_and_default(tmp_path: Path):
    custom_env = {"MY_KEY": "MY_VAL"}
    env = prepare_runner_environment(tmp_path, base_env=custom_env)

    assert env["MY_KEY"] == "MY_VAL"
    assert env["SPEC_OPS_WORKTREE"] == str(tmp_path.resolve())
    assert env["PWD"] == str(tmp_path.resolve())

    # Default base_env=None
    env_default = prepare_runner_environment(tmp_path)
    assert env_default["SPEC_OPS_WORKTREE"] == str(tmp_path.resolve())
    assert env_default["PWD"] == str(tmp_path.resolve())


def test_agent_runner_class(tmp_path: Path):
    cfg = SpecOpsConfig(
        execution=ExecutionSettings(agent_command="aider --file {prompt_file}"),
        root_dir=tmp_path,
    )
    runner = AgentRunner(cfg)
    p_file = tmp_path / "task.md"
    p_file.write_text("hello", encoding="utf-8")

    argv = runner.build_command(prompt_file=p_file, worktree_dir=tmp_path)
    assert argv == ["aider", "--file", str(p_file.resolve())]

    env = runner.prepare_environment(tmp_path)
    assert env["SPEC_OPS_WORKTREE"] == str(tmp_path.resolve())


def test_build_agent_cmd_public_helper():
    res = build_agent_cmd("echo {prompt}", prompt="foo", prompt_file=Path("p.md"))
    assert res == ["echo", "foo"]
