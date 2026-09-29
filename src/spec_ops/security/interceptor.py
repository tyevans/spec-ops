"""Subshell execution interceptor and command allowlist verification engine."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from .models import SecurityViolationEvent

FORBIDDEN_UTILITIES = {
    "curl",
    "wget",
    "sudo",
    "su",
    "nc",
    "netcat",
    "ncat",
    "telnet",
    "ssh",
    "scp",
    "sftp",
    "rm",
}

# Regex to detect subshell command substitutions: $(cmd) or `cmd`
SUBSHELL_DOLLAR_RE = re.compile(r"\$\((.*?)\)")
SUBSHELL_BACKTICK_RE = re.compile(r"`(.*?)`")

# Regex to split on unquoted operators: ;, &&, ||, |, |, &
OPERATORS = [";", "&&", "||", "|&", "|", "&"]


def split_compound_commands(cmd_str: str) -> list[str]:
    """Splits a compound command string into individual statements respecting quotes."""
    segments: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(cmd_str)

    while i < n:
        char = cmd_str[i]

        if escaped:
            current.append(char)
            escaped = False
            i += 1
            continue

        if char == "\\" and not in_single:
            escaped = True
            current.append(char)
            i += 1
            continue

        if char == "'" and not in_double:
            in_single = not in_single
            current.append(char)
            i += 1
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            current.append(char)
            i += 1
            continue

        if not in_single and not in_double:
            # Check 2-char operators: &&, ||, |&
            two = cmd_str[i : i + 2]
            if two in ("&&", "||", "|&"):
                seg = "".join(current).strip()
                if seg:
                    segments.append(seg)
                current = []
                i += 2
                continue
            # Check 1-char operators: ;, |, &, \n
            if char in (";", "|", "&", "\n"):
                seg = "".join(current).strip()
                if seg:
                    segments.append(seg)
                current = []
                i += 1
                continue

        current.append(char)
        i += 1

    remaining = "".join(current).strip()
    if remaining:
        segments.append(remaining)

    return segments


def is_destructive_rm(tokens: list[str]) -> bool:
    """Detects destructive rm command invocations like 'rm -rf /'."""
    if not tokens:
        return False
    binary = Path(tokens[0]).name
    if binary != "rm":
        return False

    has_recursive = False
    has_force = False
    targets: list[str] = []

    for t in tokens[1:]:
        if t.startswith("-") and not t.startswith("--"):
            if "r" in t or "R" in t:
                has_recursive = True
            if "f" in t:
                has_force = True
        elif t in ("--recursive", "-r", "-R"):
            has_recursive = True
        elif t in ("--force", "-f"):
            has_force = True
        elif not t.startswith("-"):
            targets.append(t)

    destructive_roots = {"/", "/*", "/etc", "/var", "/usr", "/root"}
    if has_recursive and any(target in destructive_roots for target in targets):
        return True
    return False


def is_index_in_single_quotes(cmd_str: str, index: int) -> bool:
    """Returns True if character at index is inside single quotes '...'."""
    in_single = False
    in_double = False
    escaped = False
    for i, char in enumerate(cmd_str):
        if i >= index:
            break
        if escaped:
            escaped = False
            continue
        if char == "\\" and not in_single:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
    return in_single


def is_index_escaped(cmd_str: str, index: int) -> bool:
    """Returns True if character at index is preceded by an odd number of backslashes."""
    count = 0
    k = index - 1
    while k >= 0 and cmd_str[k] == "\\":
        count += 1
        k -= 1
    return count % 2 == 1


def extract_executables_with_context(cmd_str: str) -> list[tuple[str, list[str], bool]]:
    """Extracts executable binaries, token lists, and single-quote status from a command string."""
    results: list[tuple[str, list[str], bool]] = []

    # 1. Extract embedded command substitutions $(...)
    for m in SUBSHELL_DOLLAR_RE.finditer(cmd_str):
        if is_index_escaped(cmd_str, m.start()):
            continue
        sub = m.group(1).strip()
        if sub:
            quoted = is_index_in_single_quotes(cmd_str, m.start())
            inner = extract_executables_with_context(sub)
            results.extend([(b, t, quoted or q) for b, t, q in inner])

    # 2. Extract backtick substitutions `...`
    for m in SUBSHELL_BACKTICK_RE.finditer(cmd_str):
        if is_index_escaped(cmd_str, m.start()):
            continue
        sub = m.group(1).strip()
        if sub:
            quoted = is_index_in_single_quotes(cmd_str, m.start())
            inner = extract_executables_with_context(sub)
            results.extend([(b, t, quoted or q) for b, t, q in inner])

    # 3. Clean subshell placeholders from the outer string to avoid re-parsing
    cleaned = SUBSHELL_DOLLAR_RE.sub(" ", cmd_str)
    cleaned = SUBSHELL_BACKTICK_RE.sub(" ", cleaned)

    # 4. Split on compound operators (&&, ||, ;, |, &)
    segments = split_compound_commands(cleaned)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        try:
            tokens = shlex.split(seg)
        except ValueError:
            tokens = seg.split()

        if not tokens:
            continue

        # Skip leading environment assignments: FOO=bar BAZ=qux cmd
        idx = 0
        while idx < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", tokens[idx]):
            idx += 1

        if idx >= len(tokens):
            continue

        cmd_token = tokens[idx]
        cmd_tokens = tokens[idx:]

        # Check for shell wrapper: bash -c "..." or sh -c "..."
        bin_name = Path(cmd_token).name
        if bin_name in ("bash", "sh", "zsh", "dash", "ksh"):
            if "-c" in cmd_tokens:
                c_idx = cmd_tokens.index("-c")
                if c_idx + 1 < len(cmd_tokens):
                    sub_cmd = cmd_tokens[c_idx + 1]
                    inner = extract_executables_with_context(sub_cmd)
                    results.extend([(b, t, False) for b, t, _ in inner])

        results.append((bin_name, cmd_tokens, False))

    return results


def extract_executables(cmd_str: str) -> list[tuple[str, list[str]]]:
    """Extracts all executable binaries and their token lists from a command string.

    Recursively inspects subshell substitutions ($(...), `...`), compound operators,
    and shell wrapper invocations (bash -c, sh -c).
    """
    return [(b, t) for b, t, _ in extract_executables_with_context(cmd_str)]


def validate_command(
    cmd: str | list[str],
    allowed_commands: list[str] | set[str] | None = None,
    prohibited_commands: list[str] | set[str] | None = None,
) -> tuple[bool, str, str | None]:
    """Validates if a command string or token list is permissible under sandbox policy.

    Returns:
        (is_allowed, reason, prohibited_binary_or_none)
    """
    if isinstance(cmd, list):
        cmd_str = " ".join(shlex.quote(c) for c in cmd)
    else:
        cmd_str = str(cmd)

    allowed = set(allowed_commands) if allowed_commands is not None else None
    prohibited = set(prohibited_commands or FORBIDDEN_UTILITIES)

    executables = extract_executables_with_context(cmd_str)
    if not executables:
        return True, "No executable binaries found.", None

    for bin_name, tokens, is_single_quoted in executables:
        # Check destructive commands (e.g. rm -rf /)
        if is_destructive_rm(tokens):
            return (
                False,
                f"Destructive filesystem deletion command prohibited: {' '.join(tokens)}",
                "rm",
            )

        # Check explicit prohibited utilities
        if bin_name in prohibited:
            return (
                False,
                f"Utility '{bin_name}' is explicitly forbidden by security sandbox policy.",
                bin_name,
            )

        # Check allowlist if configured and command is not inside literal single quotes
        if not is_single_quoted and allowed is not None and bin_name not in allowed:
            # Allow common harmless builtins/wrappers if they don't violate prohibitions
            harmless_builtins = {"echo", "true", "false", "exit", "test", "cd", "export", "set", "pwd"}
            if bin_name not in harmless_builtins:
                return (
                    False,
                    f"Command '{bin_name}' is not in allowlisted execution commands: {sorted(allowed)}",
                    bin_name,
                )

    return True, "Command is permissible.", None



def resolve_audit_log_path(worktree_dir: Path | str) -> Path:
    """Resolves target audit log file location."""
    wt_path = Path(worktree_dir).resolve()
    return wt_path / ".security-audit.log"


def record_security_violation(
    worktree_dir: Path | str,
    command: str,
    prohibited_binary: str,
    parent_pid: int | None = None,
    details: str = "",
) -> Path:
    """Appends structured security alert event to .worktrees/<task-id>/.security-audit.log."""
    log_path = resolve_audit_log_path(worktree_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    event = SecurityViolationEvent(
        command=command,
        prohibited_binary=prohibited_binary,
        parent_pid=parent_pid if parent_pid is not None else os.getpid(),
        details=details,
    )

    with log_path.open("a", encoding="utf-8") as f:
        f.write(event.to_json() + "\n")

    return log_path


def create_interceptor_shims(
    shim_dir: Path,
    audit_log_path: Path,
    prohibited_bins: set[str] | list[str] | None = None,
) -> Path:
    """Generates executable PATH shims for forbidden utilities that terminate with exit code 126."""
    shim_dir.mkdir(parents=True, exist_ok=True)
    bins = set(prohibited_bins or FORBIDDEN_UTILITIES)

    shim_template = """#!/bin/sh
# SpecOps Process Sandbox Interceptor Shim
PPID_VAL=${{PPID:-$$}}
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)
CMD_NAME="{bin_name}"
FULL_CMD="$CMD_NAME $*"
echo "{{\\"timestamp\\": \\"$TIMESTAMP\\", \\"event\\": \\"SECURITY_ALERT_COMMAND_PROHIBITED\\", \\"command\\": \\"$FULL_CMD\\", \\"prohibited_binary\\": \\"$CMD_NAME\\", \\"parent_pid\\": $PPID_VAL, \\"exit_code\\": 126, \\"details\\": \\"Intercepted via PATH execution shim\\"}}" >> "{audit_log}"
echo "Command Prohibited: execution of '$CMD_NAME' is forbidden by sandbox policy (exit code 126)" >&2
exit 126
"""

    for b in bins:
        target = shim_dir / b
        target.write_text(
            shim_template.format(bin_name=b, audit_log=str(audit_log_path.resolve())),
            encoding="utf-8",
        )
        target.chmod(0o755)

    return shim_dir
