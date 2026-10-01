"""Cross-Context Interface Auditor and Multi-Agent Collaborative Review Radar.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0106, US-0115.
"""

from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

BOUNDED_CONTEXTS = (
    "core", "worker", "prd", "rescue", "scaffold", "security",
    "graph", "backlog", "visualizer", "cli", "tui", "adrs", "config", "release"
)

CONTEXT_LAYERS: dict[str, int] = {
    "core": 0, "security": 1, "graph": 1, "backlog": 1, "prd": 1,
    "adrs": 1, "config": 1, "worker": 2, "rescue": 2, "scaffold": 2,
    "release": 2, "visualizer": 3, "tui": 3, "cli": 3,
}


@dataclass
class ApiSymbol:
    name: str
    kind: str  # "function", "class"
    is_public: bool
    params: list[str] = field(default_factory=list)
    required_params: list[str] = field(default_factory=list)
    methods: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class InterfaceDiff:
    symbol_name: str
    kind: str
    change_type: str  # "breaking", "non_breaking", "internal"
    details: str


@dataclass
class WorktreeAudit:
    worktree: str
    path: str
    branch: str
    context: str
    risk_score: int
    risk_level: str
    violations: list[str] = field(default_factory=list)
    breaking_changes: list[InterfaceDiff] = field(default_factory=list)
    non_breaking_changes: list[InterfaceDiff] = field(default_factory=list)
    internal_changes: list[InterfaceDiff] = field(default_factory=list)
    affected_contexts: list[str] = field(default_factory=list)


def partition_ast_symbols(source_code: str) -> tuple[dict[str, ApiSymbol], dict[str, ApiSymbol]]:
    """Deterministically partitions AST module symbols into public contracts and private internals."""
    public_symbols: dict[str, ApiSymbol] = {}
    private_symbols: dict[str, ApiSymbol] = {}
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return public_symbols, private_symbols

    explicit_all: set[str] | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        explicit_all = {
                            elt.value for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        }

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_pub = (node.name in explicit_all) if explicit_all is not None else not node.name.startswith("_")
            num_req = len(node.args.args) - len(node.args.defaults)
            req = [a.arg for a in node.args.args[:num_req]]
            all_params = [a.arg for a in node.args.args]
            sym = ApiSymbol(name=node.name, kind="function", is_public=is_pub, params=all_params, required_params=req)
            (public_symbols if is_pub else private_symbols)[node.name] = sym
        elif isinstance(node, ast.ClassDef):
            is_pub = (node.name in explicit_all) if explicit_all is not None else not node.name.startswith("_")
            methods: dict[str, list[str]] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_") or item.name == "__init__":
                        num_r = len(item.args.args) - len(item.args.defaults)
                        methods[item.name] = [a.arg for a in item.args.args[:num_r]]
            sym = ApiSymbol(name=node.name, kind="class", is_public=is_pub, methods=methods)
            (public_symbols if is_pub else private_symbols)[node.name] = sym

    return public_symbols, private_symbols


def extract_cli_options(source_code: str) -> set[str]:
    """Extracts CLI options added via add_argument from Python source AST."""
    options: set[str] = set()
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return options
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("-"):
                    options.add(arg.value)
    return options


def diff_module_interfaces(old_code: str, new_code: str) -> list[InterfaceDiff]:
    """Diffs observable API contracts between baseline and active AST."""
    old_pub, old_priv = partition_ast_symbols(old_code)
    new_pub, new_priv = partition_ast_symbols(new_code)
    diffs: list[InterfaceDiff] = []

    for name, sym in old_pub.items():
        if name not in new_pub:
            diffs.append(InterfaceDiff(name, sym.kind, "breaking", f"Public {sym.kind} '{name}' was removed."))
        else:
            new_sym = new_pub[name]
            if sym.kind == "function":
                for p in sym.params:
                    if p not in new_sym.params:
                        diffs.append(InterfaceDiff(name, "function", "breaking", f"Parameter '{p}' removed from '{name}'."))
                for p in new_sym.required_params:
                    if p not in sym.params:
                        diffs.append(InterfaceDiff(name, "function", "breaking", f"New required parameter '{p}' added to '{name}'."))
            elif sym.kind == "class":
                for m in sym.methods:
                    if m not in new_sym.methods:
                        diffs.append(InterfaceDiff(f"{name}.{m}", "method", "breaking", f"Public method '{m}' removed."))

    for name, sym in new_pub.items():
        if name not in old_pub:
            diffs.append(InterfaceDiff(name, sym.kind, "non_breaking", f"New public {sym.kind} '{name}' introduced."))

    for name in new_priv:
        if name not in old_priv:
            diffs.append(InterfaceDiff(name, "internal", "internal", f"Internal helper '{name}' modified."))

    for opt in extract_cli_options(old_code) - extract_cli_options(new_code):
        diffs.append(InterfaceDiff(opt, "cli_option", "breaking", f"CLI option '{opt}' was removed."))
    for opt in extract_cli_options(new_code) - extract_cli_options(old_code):
        diffs.append(InterfaceDiff(opt, "cli_option", "non_breaking", f"CLI option '{opt}' was added."))

    if not diffs and old_code != new_code:
        diffs.append(InterfaceDiff("<body_logic>", "internal", "internal", "Internal implementation logic updated."))
    return diffs


def extract_imports(source_code: str) -> list[str]:
    """Extracts all imported module and package names from source text."""
    imports: list[str] = []
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def determine_context(path_str: str) -> str:
    """Maps a source file path to its governing bounded context."""
    norm = path_str.replace("\\", "/")
    for bc in BOUNDED_CONTEXTS:
        if f"/{bc}/" in f"/{norm}/" or norm.startswith(f"{bc}/") or f"src/{bc}/" in norm:
            return bc
    return "core" if "domain" in norm else "worker" if "infrastructure" in norm else "core"


def determine_context_from_import(imp: str) -> str | None:
    """Identifies target bounded context from an import statement."""
    if imp.startswith("spec_ops."):
        parts = imp.split(".")
        if len(parts) > 1 and parts[1] in CONTEXT_LAYERS:
            return parts[1]
    return imp if imp in CONTEXT_LAYERS else "worker" if "infrastructure" in imp else None


def check_adr0007_violations(file_path: str, source_code: str) -> list[str]:
    """Audits source code imports against ADR-0007 directional layering invariants."""
    violations: list[str] = []
    norm = file_path.replace("\\", "/")
    is_domain = "/domain/" in f"/{norm}/" or norm.startswith("domain/") or "domain.py" in norm or "/core/" in f"/{norm}/"
    src_ctx = determine_context(norm)
    src_layer = CONTEXT_LAYERS.get(src_ctx, 0 if is_domain else None)

    for imp in extract_imports(source_code):
        is_infra = imp == "infrastructure" or imp.startswith("infrastructure.") or ".infrastructure" in imp
        if is_domain and is_infra:
            violations.append(
                f"Architectural boundary violation (ADR-0007): Pure domain module '{norm}' "
                f"cannot import external infrastructure '{imp}'."
            )
            continue
        if (is_domain or src_ctx == "core") and any(
            imp.startswith(f"spec_ops.{h}") or imp == h or imp.startswith(f"{h}.")
            for h in ("worker", "rescue", "cli", "tui", "visualizer", "scaffold")
        ):
            violations.append(
                f"Architectural boundary violation (ADR-0007): Pure domain context '{src_ctx}' "
                f"cannot import infrastructure module '{imp}'."
            )
            continue
        imp_ctx = determine_context_from_import(imp)
        if src_ctx and imp_ctx and src_ctx != imp_ctx:
            tgt_layer = CONTEXT_LAYERS.get(imp_ctx)
            if src_layer is not None and tgt_layer is not None and src_layer < tgt_layer:
                violations.append(
                    f"Architectural boundary violation (ADR-0007): Bounded context '{src_ctx}' (layer {src_layer}) "
                    f"cannot import higher layer '{imp_ctx}' (layer {tgt_layer}) via '{imp}'."
                )
    return violations


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        res = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=False)
        return res.stdout.strip() if res.returncode == 0 else ""
    except Exception:
        return ""


def discover_worktrees(root_path: Path) -> list[tuple[str, Path, str]]:
    """Discovers all active worktrees and dedicated feature branches for this repository."""
    results: list[tuple[str, Path, str]] = []
    seen: set[Path] = set()

    repo_root = root_path
    if (root_path / ".git").is_file():
        try:
            content = (root_path / ".git").read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                raw_gitdir = content.split("gitdir:", 1)[1].strip()
                gitdir_path = (root_path / raw_gitdir).resolve()
                if ".git" in gitdir_path.parts:
                    idx = gitdir_path.parts.index(".git")
                    repo_root = Path(*gitdir_path.parts[:idx]).resolve()
        except Exception:
            pass

    raw_wt = _run_git(["worktree", "list", "--porcelain"], root_path)
    cur_p, cur_b = None, "HEAD"
    for line in raw_wt.splitlines():
        if line.startswith("worktree "):
            cur_p = Path(line.split("worktree ", 1)[1]).resolve()
        elif line.startswith("branch "):
            cur_b = line.split("branch ", 1)[1].replace("refs/heads/", "")
        elif not line.strip() and cur_p:
            if (cur_p == root_path or cur_p == repo_root or repo_root in cur_p.parents) and cur_p not in seen:
                results.append((cur_p.name, cur_p, cur_b))
                seen.add(cur_p)
            cur_p, cur_b = None, "HEAD"
    if cur_p and (cur_p == root_path or cur_p == repo_root or repo_root in cur_p.parents) and cur_p not in seen:
        results.append((cur_p.name, cur_p, cur_b))
        seen.add(cur_p)

    for base in (repo_root, root_path):
        wt_dir = base / ".worktrees"
        if wt_dir.is_dir():
            for d in sorted(wt_dir.iterdir()):
                if d.is_dir() and d not in seen:
                    results.append((d.name, d, _run_git(["rev-parse", "--abbrev-ref", "HEAD"], d) or "detached"))
                    seen.add(d)

    if root_path not in seen:
        results.append((root_path.name, root_path, _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root_path) or "main"))
    return results


def audit_worktree(name: str, wt_path: Path, branch: str, root_path: Path) -> WorktreeAudit:
    """Audits a single worktree for boundary violations, public API breaks, and blast radius."""
    diff_raw = _run_git(["diff", "--name-only", "main"], wt_path)
    status_raw = _run_git(["status", "--porcelain"], wt_path)
    candidates = {l.strip() for l in diff_raw.splitlines() if l.strip().endswith(".py")}
    candidates.update(l[3:].strip() for l in status_raw.splitlines() if l[3:].strip().endswith(".py"))

    is_git = (wt_path / ".git").exists() or (wt_path / ".git").is_file()
    if not candidates and not is_git and wt_path.is_dir():
        for p in wt_path.rglob("*.py"):
            if not any(x in p.parts for x in (".git", ".venv", "__pycache__")):
                candidates.add(str(p.relative_to(wt_path)))

    breaking, non_breaking, internal, violations = [], [], [], []
    contexts_touched: set[str] = set()
    removed_opts: set[str] = set()
    added_opts: set[str] = set()

    for rel_path in sorted(candidates):
        full_p = wt_path / rel_path
        if not full_p.is_file():
            continue
        cur_code = full_p.read_text(encoding="utf-8", errors="ignore")
        base_code = _run_git(["show", f"main:{rel_path}"], wt_path)
        contexts_touched.add(determine_context(rel_path))

        old_cli = extract_cli_options(base_code)
        new_cli = extract_cli_options(cur_code)
        removed_opts.update(old_cli - new_cli)
        added_opts.update(new_cli - old_cli)

        for d in diff_module_interfaces(base_code, cur_code):
            if d.kind == "cli_option":
                continue
            (breaking if d.change_type == "breaking" else non_breaking if d.change_type == "non_breaking" else internal).append(d)
        violations.extend(check_adr0007_violations(rel_path, cur_code))

    for opt in sorted(removed_opts - added_opts):
        breaking.append(InterfaceDiff(opt, "cli_option", "breaking", f"CLI option '{opt}' was removed."))
    for opt in sorted(added_opts - removed_opts):
        non_breaking.append(InterfaceDiff(opt, "cli_option", "non_breaking", f"CLI option '{opt}' was added."))

    primary_ctx = list(contexts_touched)[0] if contexts_touched else "core"
    affected = sorted(contexts_touched - {primary_ctx})
    risk = max(0, min(100, len(violations) * 50 + len(breaking) * 25 + len(affected) * 10 + min(15, len(non_breaking) * 5)))
    r_level = "LOW" if risk <= 20 else "MEDIUM" if risk <= 50 else "HIGH" if risk <= 75 else "CRITICAL"

    return WorktreeAudit(
        worktree=name, path=str(wt_path), branch=branch, context=primary_ctx,
        risk_score=risk, risk_level=r_level, violations=violations,
        breaking_changes=breaking, non_breaking_changes=non_breaking,
        internal_changes=internal, affected_contexts=affected,
    )


def run_review_radar(root_dir: str | Path = ".", json_output: bool = False, target_bc: str | None = None) -> int:
    """Executes the review radar CLI command and outputs formatted visual matrix or JSON."""
    root_path = Path(root_dir).resolve()
    discovered = discover_worktrees(root_path)
    audits: list[WorktreeAudit] = []

    for n, p, b in discovered:
        audit = audit_worktree(n, p, b, root_path)
        if target_bc and audit.context != target_bc and target_bc not in audit.affected_contexts:
            continue
        audits.append(audit)

    total_viol = sum(len(a.violations) for a in audits)
    max_risk = max((a.risk_score for a in audits), default=0)

    if json_output:
        payload = {
            "summary": {"total_worktrees": len(audits), "total_violations": total_viol, "max_risk_score": max_risk, "clean": total_viol == 0},
            "worktrees": [asdict(a) for a in audits],
        }
        print(json.dumps(payload, indent=2))
        return 1 if total_viol > 0 else 0

    print("=" * 80)
    print("                    SPEC-OPS ARCHITECTURAL REVIEW RADAR")
    print("=" * 80)
    print(f"Target Context: {target_bc or 'all'} | Audited Worktrees: {len(audits)} | Violations: {total_viol} | Max Risk: {max_risk}/100")
    print("\n┌" + "─" * 24 + "┬" + "─" * 12 + "┬" + "─" * 10 + "┬" + "─" * 30 + "┐")
    print(f"│ {'Worktree / Branch':<22} │ {'Context':<10} │ {'Risk':<8} │ {'Interface / Boundary Status':<28} │")
    print("├" + "─" * 24 + "┼" + "─" * 12 + "┼" + "─" * 10 + "┼" + "─" * 30 + "┤")
    for a in audits:
        status_str = f"{len(a.breaking_changes)} break, {len(a.violations)} viol" if a.violations or a.breaking_changes else "Compliant (0 break)"
        line_name = f"{a.worktree[:10]} ({a.branch[:9]})"
        print(f"│ {line_name:<22} │ {a.context:<10} │ {a.risk_level:<8} │ {status_str:<28} │")
    print("└" + "─" * 24 + "┴" + "─" * 12 + "┴" + "─" * 10 + "┴" + "─" * 30 + "┘")

    if total_viol > 0:
        print("\n❌ Architectural Boundary Violations Detected (ADR-0007):")
        for a in audits:
            for v in a.violations:
                print(f"   - [{a.worktree}] {v}")
        return 1

    print("\n✅ Review Radar: All interfaces and cross-context boundaries compliant (zero cross-context violations).")
    return 0
