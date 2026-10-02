"""Architectural layer contracts, bounded context independence, and import linter loader."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore


@dataclass
class ArchitecturalContract:
    """Represents architectural layers, independent sibling contexts, and forbidden rules."""

    context_layers: dict[str, int] = field(default_factory=dict)
    independent_pairs: set[tuple[str, str]] = field(default_factory=set)
    forbidden_rules: dict[str, list[str]] = field(default_factory=dict)
    ordered_layers: list[list[str]] = field(default_factory=list)
    ignored_imports: list[str] = field(default_factory=list)

    def get_layer(self, context: str) -> int | None:
        return self.context_layers.get(context)

    def is_independent(self, src: str, tgt: str) -> bool:
        return (src, tgt) in self.independent_pairs

    def is_forbidden(self, src: str, tgt: str) -> bool:
        import fnmatch
        for p in self.forbidden_rules.get(src, []):
            if fnmatch.fnmatch(tgt, p) or tgt == p:
                return True
        return False

    def is_ignored_import(self, src_mod: str, tgt_imp: str) -> bool:
        return is_ignored_import(src_mod, tgt_imp, self.ignored_imports)


def is_ignored_import(src_mod: str, tgt_imp: str, ignored_list: list[str]) -> bool:
    """Checks whether an import edge matches any waived / ignored imports in the contract."""
    import fnmatch
    for entry in ignored_list:
        if " -> " in entry:
            s_pat, t_pat = [p.strip() for p in entry.split(" -> ")]
            s_clean = s_pat.replace("spec_ops.", "")
            t_clean = t_pat.replace("spec_ops.", "")
            match_src = (
                fnmatch.fnmatch(src_mod, s_clean)
                or fnmatch.fnmatch(src_mod, s_pat)
                or fnmatch.fnmatch(f"spec_ops.{src_mod}", s_pat)
            )
            match_tgt = (
                fnmatch.fnmatch(tgt_imp, t_clean)
                or fnmatch.fnmatch(tgt_imp, t_pat)
                or fnmatch.fnmatch(f"spec_ops.{tgt_imp}", t_pat)
            )
            if match_src and match_tgt:
                return True
    return False


def load_architectural_layers_and_rules(
    root_dir: Path | str,
) -> tuple[dict[str, int], set[tuple[str, str]], dict[str, list[str]], list[list[str]]]:
    """Loads layer contracts, independent sibling pairs, and forbidden rules from pyproject.toml / specops.toml."""
    contract = load_architectural_contract(Path(root_dir))
    return (
        contract.context_layers,
        contract.independent_pairs,
        contract.forbidden_rules,
        contract.ordered_layers,
    )


def load_architectural_contract(root_dir: Path | str) -> ArchitecturalContract:
    """Parses import-linter contracts from pyproject.toml and architectural layers from specops.toml."""
    root = Path(root_dir).resolve()
    context_layers: dict[str, int] = {}
    independent_pairs: set[tuple[str, str]] = set()
    forbidden_rules: dict[str, list[str]] = {}
    ordered_layers: list[list[str]] = []
    ignored_imports: list[str] = []

    # 1. Inspect pyproject.toml [tool.importlinter]
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            contracts = data.get("tool", {}).get("importlinter", {}).get("contracts", [])
            for c in contracts:
                c_type = c.get("type")
                if c_type == "layers":
                    layer_lines = c.get("layers", [])
                    parsed_layers: list[list[str]] = []
                    # Reversed so lowest layer = 0, highest = max
                    for idx, line in enumerate(reversed(layer_lines)):
                        layer_bcs: list[str] = []
                        if "|" in line:
                            mods = [m.strip().split(".")[-1] for m in line.split("|")]
                            for m in mods:
                                context_layers[m] = idx
                                layer_bcs.append(m)
                            for m1 in mods:
                                for m2 in mods:
                                    if m1 != m2:
                                        independent_pairs.add((m1, m2))
                        elif ":" in line:
                            mods = [m.strip().split(".")[-1] for m in line.split(":")]
                            for m in mods:
                                context_layers[m] = idx
                                layer_bcs.append(m)
                        else:
                            mod = line.strip().split(".")[-1]
                            context_layers[mod] = idx
                            layer_bcs.append(mod)
                        parsed_layers.append(layer_bcs)
                    if parsed_layers:
                        ordered_layers = parsed_layers
                    ignored_imports.extend(c.get("ignore_imports", []))
                elif c_type == "independence":
                    mods = [m.strip().split(".")[-1] for m in c.get("modules", [])]
                    for m1 in mods:
                        for m2 in mods:
                            if m1 != m2:
                                independent_pairs.add((m1, m2))
                    ignored_imports.extend(c.get("ignore_imports", []))
                elif c_type == "forbidden":
                    srcs = [m.strip().split(".")[-1] for m in c.get("source_modules", [])]
                    forbs = [m.strip().split(".")[-1] for m in c.get("forbidden_modules", [])]
                    for s in srcs:
                        forbidden_rules.setdefault(s, []).extend(forbs)
                    ignored_imports.extend(c.get("ignore_imports", []))
        except Exception:
            pass

    # 2. Inspect specops.toml
    specops_path = root / "specops.toml"
    if specops_path.exists():
        try:
            data = tomllib.loads(specops_path.read_text(encoding="utf-8"))
            arch = data.get("architecture", {})
            if not context_layers and "layers" in arch:
                for k, v in arch["layers"].items():
                    context_layers[k] = int(v)
            indep = arch.get("independent_contexts", {})
            for pair in indep.get("pairs", []):
                if len(pair) == 2:
                    independent_pairs.add((pair[0], pair[1]))
                    independent_pairs.add((pair[1], pair[0]))
        except Exception:
            pass

    # 3. Fallback to review_radar.CONTEXT_LAYERS if no layers found
    if not context_layers:
        try:
            from .review_radar import CONTEXT_LAYERS
            context_layers.update(CONTEXT_LAYERS)
        except Exception:
            pass

    # If ordered_layers empty, reconstruct from context_layers
    if not ordered_layers and context_layers:
        max_layer = max(context_layers.values())
        reconstructed: list[list[str]] = [[] for _ in range(max_layer + 1)]
        for k, v in sorted(context_layers.items()):
            reconstructed[v].append(k)
        ordered_layers = [l for l in reconstructed if l]

    return ArchitecturalContract(
        context_layers=context_layers,
        independent_pairs=independent_pairs,
        forbidden_rules=forbidden_rules,
        ordered_layers=ordered_layers,
        ignored_imports=ignored_imports,
    )
